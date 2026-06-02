#!/usr/bin/env bash
# DeskAd AI Studio — unified launcher
# Usage: bash start.sh [--restart] [--stop]
set -euo pipefail

CONDA_ENV="sprint_high"
BACKEND_PORT=8010
FRONTEND_PORT=8501
COMFYUI_PORT=8188
OLLAMA_PORT=11434
COMFYUI_SERVICE="${DESKAD_COMFYUI_SERVICE:-comfyui}"
OLLAMA_SERVICE="${DESKAD_OLLAMA_SERVICE:-ollama}"
# Bind Streamlit to loopback only. External access goes through nginx (8443) with basic auth.
# To temporarily expose Streamlit directly for local debugging, set DESKAD_STREAMLIT_HOST=0.0.0.0.
FRONTEND_HOST="${DESKAD_STREAMLIT_HOST:-127.0.0.1}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── helpers ──────────────────────────────────────────────────────────────────
log()  { echo "[deskad] $*"; }
warn() { echo "[deskad][WARN] $*" >&2; }

port_pid() { lsof -ti tcp:"$1" 2>/dev/null || true; }

env_value() {
  local key=$1 default=${2:-} value
  value="${!key:-}"
  if [[ -z "$value" && -f "$SCRIPT_DIR/.env" ]]; then
    value=$(sed -nE "s/^[[:space:]]*${key}[[:space:]]*=[[:space:]]*['\"]?([^'\"]*)['\"]?[[:space:]]*$/\1/p" "$SCRIPT_DIR/.env" | tail -n 1)
  fi
  printf '%s' "${value:-$default}"
}

service_active() {
  local service=$1
  command -v systemctl >/dev/null 2>&1 && systemctl is-active --quiet "$service" >/dev/null 2>&1
}

url_ready() {
  local url=$1
  curl -fsS --max-time 2 "$url" >/dev/null 2>&1
}

kill_port() {
  local port=$1 pid
  pid=$(port_pid "$port")
  if [[ -n "$pid" ]]; then
    log "포트 $port 점유 프로세스($pid) 종료 중..."
    kill "$pid" 2>/dev/null || true
    sleep 1
  fi
}

# ── stop ─────────────────────────────────────────────────────────────────────
cmd_stop() {
  log "서버 종료..."
  kill_port "$BACKEND_PORT"
  kill_port "$FRONTEND_PORT"
  log "종료 완료."
  exit 0
}

# ── preflight ────────────────────────────────────────────────────────────────
preflight() {
  # 절대 사용 금지: JupyterHub 포트
  if [[ "$BACKEND_PORT" == "8000" || "$FRONTEND_PORT" == "8000" ]]; then
    warn "8000 포트는 JupyterHub 전용입니다. start.sh를 수정하지 마세요."
    exit 1
  fi

  # .env 확인 및 권한 잠금
  if [[ ! -f "$SCRIPT_DIR/.env" ]]; then
    warn ".env 파일이 없습니다. .env.example을 복사해 설정하세요:"
    warn "  cp $SCRIPT_DIR/.env.example $SCRIPT_DIR/.env"
    warn "API 키 없이도 기본 기능(GLB 렌더, 템플릿 광고문구)은 동작합니다."
  else
    local mode
    mode=$(stat -c '%a' "$SCRIPT_DIR/.env" 2>/dev/null || echo "")
    if [[ "$mode" != "600" ]]; then
      log ".env 권한을 600으로 잠급니다 (현재: ${mode:-unknown})."
      chmod 600 "$SCRIPT_DIR/.env" 2>/dev/null || warn ".env 권한 변경 실패. 수동으로 chmod 600 .env 를 실행하세요."
    fi
  fi

  # 런타임 상태/캐시 파일 권한 잠금 (메모리/디스크 누출 시 secret-인접 데이터가 새지 않게)
  # jsonl(잡/품질 로그) + json(worker_state, 결과 캐시) + lock(gpu_worker.lock) 전부 0600.
  if [[ -d "$SCRIPT_DIR/data/runtime" ]]; then
    find "$SCRIPT_DIR/data/runtime" -type f -exec chmod 600 {} + 2>/dev/null || true
  fi

  # pre-commit hook 자동 설치 (이미 있으면 건드리지 않음)
  local repo_root hooks_dir
  repo_root=$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null || true)
  if [[ -n "$repo_root" ]]; then
    hooks_dir="$repo_root/.git/hooks"
    if [[ -d "$hooks_dir" && ! -e "$hooks_dir/pre-commit" ]]; then
      ln -s "$SCRIPT_DIR/tools/git-hooks/pre-commit" "$hooks_dir/pre-commit" 2>/dev/null \
        && log "pre-commit secret scan hook 설치 완료." \
        || warn "pre-commit hook 자동 설치 실패. 수동: ln -sf $SCRIPT_DIR/tools/git-hooks/pre-commit $hooks_dir/pre-commit"
    fi
  fi

  # 모델 워커 포트는 외부에 노출되면 안 됨 (127.0.0.1 listen 강제)
  if ss -ltn 2>/dev/null | awk '{print $4}' | grep -qE '(^0\.0\.0\.0:|^\*:|^\[::\]:)8188$'; then
    warn "ComfyUI(8188)가 외부 인터페이스에 바인딩되어 있습니다. --listen 127.0.0.1 로 다시 띄우세요."
  fi
  if ss -ltn 2>/dev/null | awk '{print $4}' | grep -qE '(^0\.0\.0\.0:|^\*:|^\[::\]:)11434$'; then
    warn "Ollama(11434)가 외부 인터페이스에 바인딩되어 있습니다. OLLAMA_HOST=127.0.0.1:11434 로 systemd 환경변수를 잠그세요."
  fi

  # conda 환경 존재 확인
  if ! conda env list 2>/dev/null | grep -q "^${CONDA_ENV}"; then
    warn "conda 환경 '${CONDA_ENV}'이 없습니다."
    warn "의존성 설치: conda create -n ${CONDA_ENV} python=3.11 && conda run -n ${CONDA_ENV} pip install -r requirements.txt"
    exit 1
  fi

  check_model_workers
}

check_model_workers() {
  local image_backend comfyui_base comfyui_workflow comfyui_stats gpu_worker_mode
  image_backend=$(env_value IMAGE_MODEL_BACKEND "auto")
  comfyui_base=$(env_value COMFYUI_BASE_URL "")
  comfyui_workflow=$(env_value COMFYUI_WORKFLOW_PATH "")
  gpu_worker_mode=$(env_value GPU_WORKER_MODE "always_on")

  if [[ -n "$comfyui_base" || "$image_backend" == "comfyui" ]]; then
    if [[ -n "$comfyui_workflow" && ! -f "$SCRIPT_DIR/$comfyui_workflow" && ! -f "$comfyui_workflow" ]]; then
      warn "COMFYUI_WORKFLOW_PATH 파일을 찾을 수 없습니다: $comfyui_workflow"
    fi

    comfyui_stats="${comfyui_base%/}/system_stats"
    if [[ "$gpu_worker_mode" == "on_demand" || "$gpu_worker_mode" == "exclusive" ]]; then
      # on_demand/exclusive 모드에서는 ComfyUI active 필수 아님 — 요청 시 자동 기동
      if service_active "$COMFYUI_SERVICE" || ( [[ -n "$comfyui_base" && "$comfyui_base" == http* ]] && url_ready "$comfyui_stats" ); then
        log "ComfyUI worker 현재 active (GPU_WORKER_MODE=${gpu_worker_mode}, idle 후 자동 종료됨)."
      else
        log "ComfyUI worker 현재 inactive — GPU_WORKER_MODE=${gpu_worker_mode}: 이미지 요청 시 자동 기동합니다."
        log "  수동 기동: sudo systemctl start ${COMFYUI_SERVICE}"
      fi
    elif service_active "$COMFYUI_SERVICE"; then
      log "ComfyUI systemd 서비스 active (${COMFYUI_SERVICE}.service)."
    elif [[ -n "$comfyui_base" && "$comfyui_base" == http* ]] && url_ready "$comfyui_stats"; then
      warn "ComfyUI endpoint는 응답하지만 ${COMFYUI_SERVICE}.service가 active가 아닙니다. 수동 실행 상태일 수 있습니다."
    else
      warn "ComfyUI worker가 준비되지 않았습니다. 이미지 생성은 fallback으로 동작하거나 실패할 수 있습니다."
      warn "  서비스 등록: sudo install -m 0644 tools/systemd/comfyui.service /etc/systemd/system/comfyui.service && sudo systemctl daemon-reload && sudo systemctl enable --now ${COMFYUI_SERVICE}"
      warn "  상태 확인: journalctl -u ${COMFYUI_SERVICE} -f"
    fi
  fi

  local uses_ollama=false key base
  for key in LOCAL_LLM_BASE_URL KANANA_BASE_URL MIDM_BASE_URL; do
    base=$(env_value "$key" "")
    if [[ "$base" == *":${OLLAMA_PORT}"* ]]; then
      uses_ollama=true
      break
    fi
  done

  if [[ "$uses_ollama" == "true" ]]; then
    if service_active "$OLLAMA_SERVICE"; then
      log "Ollama systemd 서비스 active (${OLLAMA_SERVICE}.service)."
    elif url_ready "http://127.0.0.1:${OLLAMA_PORT}/api/tags"; then
      warn "Ollama endpoint는 응답하지만 ${OLLAMA_SERVICE}.service가 active가 아닙니다. 수동 실행 상태일 수 있습니다."
    else
      warn "Ollama가 준비되지 않았습니다. 로컬 한국어 LLM 슬롯은 fallback으로 동작할 수 있습니다."
      warn "  상태 확인: systemctl status ${OLLAMA_SERVICE}"
    fi
  fi

  local hyperclova_base
  hyperclova_base=$(env_value HYPERCLOVA_BASE_URL "")
  if [[ "$hyperclova_base" == http://127.0.0.1* || "$hyperclova_base" == http://localhost* ]]; then
    if url_ready "${hyperclova_base%/}/models"; then
      log "HyperCLOVA X SEED 로컬 endpoint 준비 완료."
    else
      warn "HyperCLOVA X SEED 로컬 endpoint가 준비되지 않았습니다."
      warn "  실행: conda run -n ${CONDA_ENV} python tools/hyperclova_seed_openai_server.py"
    fi
  fi
}

# ── start backend ─────────────────────────────────────────────────────────────
start_backend() {
  local pid
  pid=$(port_pid "$BACKEND_PORT")
  if [[ -n "$pid" ]]; then
    log "백엔드 이미 실행 중 (pid=$pid, port=$BACKEND_PORT) — 재사용합니다."
    return
  fi

  log "FastAPI 백엔드 시작 (port $BACKEND_PORT)..."
  cd "$SCRIPT_DIR"
  setsid nohup conda run -n "$CONDA_ENV" python -m uvicorn backend.main:app \
    --host 127.0.0.1 --port "$BACKEND_PORT" \
    > fastapi.log 2> fastapi.err.log < /dev/null &
  disown

  # 헬스체크
  local i=0
  while [[ $i -lt 20 ]]; do
    if curl -sf "http://127.0.0.1:${BACKEND_PORT}/health" > /dev/null 2>&1; then
      log "백엔드 준비 완료."
      return
    fi
    sleep 1; ((i++)) || true
  done
  warn "백엔드 헬스체크 실패. fastapi.err.log를 확인하세요."
}

# ── start frontend ────────────────────────────────────────────────────────────
start_frontend() {
  local pid
  pid=$(port_pid "$FRONTEND_PORT")
  if [[ -n "$pid" ]]; then
    log "프론트엔드 이미 실행 중 (pid=$pid, port=$FRONTEND_PORT) — 재사용합니다."
    return
  fi

  log "Streamlit 프론트엔드 시작 (port $FRONTEND_PORT)..."
  cd "$SCRIPT_DIR"
  setsid nohup conda run -n "$CONDA_ENV" python -m streamlit run streamlit_app.py \
    --server.port "$FRONTEND_PORT" \
    --server.address "$FRONTEND_HOST" \
    --server.headless true \
    --server.enableCORS false \
    --server.enableXsrfProtection true \
    > streamlit.log 2> streamlit.err.log < /dev/null &
  disown

  local i=0
  while [[ $i -lt 30 ]]; do
    if curl -sf "http://127.0.0.1:${FRONTEND_PORT}/" > /dev/null 2>&1; then
      log "프론트엔드 준비 완료."
      return
    fi
    sleep 1; ((i++)) || true
  done
  warn "프론트엔드 응답 없음. streamlit.err.log를 확인하세요."
}

# ── main ──────────────────────────────────────────────────────────────────────
for arg in "${@:-}"; do
  case "$arg" in
    --stop)    cmd_stop ;;
    --restart)
      kill_port "$BACKEND_PORT"
      kill_port "$FRONTEND_PORT"
      sleep 1
      ;;
  esac
done

preflight
start_backend
start_frontend

echo ""
echo "======================================================"
echo "  DeskAd AI Studio 실행 중"
echo "  외부 접속  : https://$(curl -sf http://checkip.amazonaws.com 2>/dev/null || echo '<VM_IP>'):8443  (nginx + basic auth)"
echo "  로컬 접속  : http://127.0.0.1:${FRONTEND_PORT}"
echo "  백엔드(내부): http://127.0.0.1:${BACKEND_PORT}"
echo "  Streamlit bind: ${FRONTEND_HOST}:${FRONTEND_PORT}"
echo ""
echo "  로그: fastapi.log / streamlit.log"
echo "  종료: bash start.sh --stop"
echo "======================================================"
