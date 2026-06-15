#!/usr/bin/env bash
#
# Omni GPU 워커(11602 image / 11601 vision)를 호스트에서 직접 관리한다.
#
# 앱을 컨테이너(GPU_WORKER_MODE=always_on)로 옮기면 앱이 더 이상 워커를 자동 기동하지 않는다.
# 이 스크립트가 그 역할을 대신한다 — 기동 레시피는 backend/runtime_workers.py와 동일.
#
# 비밀(HF_TOKEN 등)은 .env에서 런타임에 읽어 워커 프로세스 환경으로만 전달하며, 인자/로그에 남기지 않는다.
#
# 사용법:
#   tools/omni_workers.sh start [image|vision]   # 기본 image. 둘은 VRAM 경합으로 상호배타(다른 하나를 내림)
#   tools/omni_workers.sh stop  [image|vision|all]
#   tools/omni_workers.sh status
#
# 주의(단일 L4 24GB):
#   - image(8bit ~15GB) + vision(4bit ~11GB)는 동시 상주 불가 → start가 다른 하나를 자동 종료.
#   - ComfyUI(8188)가 실제 생성 중이면 ~10GB를 더 쓰므로 Omni image와 겹치면 OOM 위험. 필요시 ComfyUI를 멈춰라.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"   # deskad_keyboard_demo
cd "$SCRIPT_DIR"
ENV_FILE="$SCRIPT_DIR/.env"
CONDA_ENV="${CONDA_ENV:-sprint_high}"
LOG_DIR="$SCRIPT_DIR/data/runtime"

IMAGE_HEALTH="http://127.0.0.1:11602/health"
VISION_HEALTH="http://127.0.0.1:11601/health"
IMAGE_PORT=11602
VISION_PORT=11601

IMAGE_CMD_DEFAULT="PYTHONUNBUFFERED=1 conda run --no-capture-output -n ${CONDA_ENV} python tools/hyperclova_omni_image_server.py"
VISION_CMD_DEFAULT="HYPERCLOVA_OMNI_PORT=11601 HYPERCLOVA_OMNI_LOAD_IN_4BIT=true conda run --no-capture-output -n ${CONDA_ENV} python tools/hyperclova_omni_openai_vision_server.py"

log()  { echo "[omni] $*"; }
warn() { echo "[omni][WARN] $*" >&2; }

# .env를 프로세스 환경으로 로드(주석/빈줄 제외, 첫 '='로 분리, 양끝 따옴표 제거). 값은 출력하지 않는다.
load_env() {
  [[ -f "$ENV_FILE" ]] || { warn ".env 없음($ENV_FILE) — HF_TOKEN/모델 미설정이면 워커가 실패할 수 있음"; return 0; }
  local line key val
  while IFS= read -r line || [[ -n "$line" ]]; do
    case "$line" in ''|\#*) continue;; esac
    [[ "$line" == *=* ]] || continue
    key="${line%%=*}"; val="${line#*=}"
    key="${key// /}"
    [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
    val="${val%\"}"; val="${val#\"}"; val="${val%\'}"; val="${val#\'}"
    export "$key=$val"
  done < "$ENV_FILE"
}

is_up()   { curl -fsS --max-time 3 "$1" >/dev/null 2>&1; }
free_mib() { nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits 2>/dev/null | head -1 | tr -d ' '; }

stop_port() {
  local name=$1 port=$2
  if command -v fuser >/dev/null 2>&1; then
    fuser -k "${port}/tcp" >/dev/null 2>&1 || true
  fi
  log "$name(:$port) 종료 요청"
}

wait_health() {  # url, budget_seconds — sleep 없이 curl 재시도로 대기
  local url=$1 budget=${2:-240} tries
  tries=$(( budget / 3 ))
  curl -fsS --retry "$tries" --retry-delay 3 --retry-all-errors --retry-connrefused --max-time 5 "$url" >/dev/null 2>&1
}

start_worker() {
  local kind=$1 name cmd health port other_port other_health min_free budget
  case "$kind" in
    image)  name=hyperclova_image;  cmd="${HYPERCLOVA_IMAGE_WORKER_CMD:-$IMAGE_CMD_DEFAULT}";  health=$IMAGE_HEALTH;  port=$IMAGE_PORT;  other_port=$VISION_PORT; other_health=$VISION_HEALTH; min_free=16000; budget=300 ;;
    vision) name=hyperclova_vision; cmd="${HYPERCLOVA_VISION_WORKER_CMD:-$VISION_CMD_DEFAULT}"; health=$VISION_HEALTH; port=$VISION_PORT; other_port=$IMAGE_PORT;  other_health=$IMAGE_HEALTH;  min_free=12000; budget=300 ;;
    *) warn "알 수 없는 대상: $kind (image|vision)"; return 2 ;;
  esac

  if is_up "$health"; then log "$name 이미 가동 중 ($health)"; return 0; fi

  # VRAM 경합: 다른 Omni 워커가 떠 있으면 내린다(둘 동시 상주 불가).
  if is_up "$other_health"; then
    warn "다른 Omni 워커가 가동 중 → VRAM 확보 위해 종료(:$other_port)"
    stop_port "other-omni" "$other_port"
  fi

  local freem; freem=$(free_mib || echo 0)
  if [[ -n "$freem" && "$freem" -gt 0 && "$freem" -lt "$min_free" ]]; then
    warn "여유 VRAM ${freem}MiB < 권장 ${min_free}MiB. ComfyUI(8188) 등으로 적재돼 있으면 OOM 위험."
  fi

  load_env
  mkdir -p "$LOG_DIR"
  local logf="$LOG_DIR/${name}_worker.log"
  log "$name 기동: 로그 → $logf"
  # runtime_workers.py와 동일하게 shell이 'VAR=val cmd' 형태를 해석하게 둔다(exec 쓰면 VAR=val 접두가 깨짐).
  setsid bash -c "cd '$SCRIPT_DIR' && $cmd" >>"$logf" 2>&1 </dev/null &

  log "health 대기(최대 ${budget}s)..."
  if wait_health "$health" "$budget"; then
    log "$name READY ✓ ($health)"
    return 0
  fi
  warn "$name 가 ${budget}s 내 health 미응답. 마지막 로그:"
  tail -n 15 "$logf" >&2 || true
  return 1
}

cmd_status() {
  local pairs=(
    "hyperclova_image :11602 $IMAGE_HEALTH"
    "hyperclova_vision :11601 $VISION_HEALTH"
    "text(SEED) :11501 http://127.0.0.1:11501/health"
    "comfyui :8188 http://127.0.0.1:8188/system_stats"
    "ollama :11434 http://127.0.0.1:11434/api/tags"
  )
  echo "GPU free: $(free_mib || echo '?') MiB"
  local p name port url
  for p in "${pairs[@]}"; do
    name=${p%% *}; rest=${p#* }; port=${rest%% *}; url=${rest#* }
    if is_up "$url"; then echo "  UP    $name $port"; else echo "  down  $name $port"; fi
  done
}

main() {
  local action=${1:-status} target=${2:-image}
  case "$action" in
    start) start_worker "$target" ;;
    stop)
      case "$target" in
        image)  stop_port hyperclova_image  "$IMAGE_PORT" ;;
        vision) stop_port hyperclova_vision "$VISION_PORT" ;;
        all)    stop_port hyperclova_image "$IMAGE_PORT"; stop_port hyperclova_vision "$VISION_PORT" ;;
        *) warn "stop 대상: image|vision|all"; return 2 ;;
      esac ;;
    status) cmd_status ;;
    *) echo "usage: $0 {start [image|vision] | stop [image|vision|all] | status}"; return 2 ;;
  esac
}

main "$@"
