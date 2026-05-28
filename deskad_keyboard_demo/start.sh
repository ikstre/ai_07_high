#!/usr/bin/env bash
# DeskAd AI Studio — unified launcher
# Usage: bash start.sh [--restart] [--stop]
set -euo pipefail

CONDA_ENV="sprint_high"
BACKEND_PORT=8010
FRONTEND_PORT=8501
# Bind Streamlit to loopback only. External access goes through nginx (8443) with basic auth.
# To temporarily expose Streamlit directly for local debugging, set DESKAD_STREAMLIT_HOST=0.0.0.0.
FRONTEND_HOST="${DESKAD_STREAMLIT_HOST:-127.0.0.1}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── helpers ──────────────────────────────────────────────────────────────────
log()  { echo "[deskad] $*"; }
warn() { echo "[deskad][WARN] $*" >&2; }

port_pid() { lsof -ti tcp:"$1" 2>/dev/null || true; }

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

  # 런타임 jsonl 권한 잠금 (메모리/디스크 누출 시 secret-인접 데이터가 새지 않게)
  if [[ -d "$SCRIPT_DIR/data/runtime" ]]; then
    find "$SCRIPT_DIR/data/runtime" -type f -name '*.jsonl' -exec chmod 600 {} + 2>/dev/null || true
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
