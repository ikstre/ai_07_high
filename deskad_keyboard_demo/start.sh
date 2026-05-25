#!/usr/bin/env bash
# DeskAd AI Studio — unified launcher
# Usage: bash start.sh [--restart] [--stop]
set -euo pipefail

CONDA_ENV="sprint_high"
BACKEND_PORT=8010
FRONTEND_PORT=8501
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

  # .env 확인
  if [[ ! -f "$SCRIPT_DIR/.env" ]]; then
    warn ".env 파일이 없습니다. .env.example을 복사해 설정하세요:"
    warn "  cp $SCRIPT_DIR/.env.example $SCRIPT_DIR/.env"
    warn "API 키 없이도 기본 기능(GLB 렌더, 템플릿 광고문구)은 동작합니다."
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
  nohup conda run -n "$CONDA_ENV" python -m uvicorn backend.main:app \
    --host 127.0.0.1 --port "$BACKEND_PORT" \
    > fastapi.log 2> fastapi.err.log &
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
  nohup conda run -n "$CONDA_ENV" python -m streamlit run streamlit_app.py \
    --server.port "$FRONTEND_PORT" \
    --server.address 0.0.0.0 \
    --server.headless true \
    > streamlit.log 2> streamlit.err.log &
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
echo "  프론트엔드 : http://$(curl -sf http://checkip.amazonaws.com 2>/dev/null || echo '<VM_IP>'):${FRONTEND_PORT}"
echo "  로컬 접속  : http://127.0.0.1:${FRONTEND_PORT}"
echo "  백엔드(내부): http://127.0.0.1:${BACKEND_PORT}"
echo ""
echo "  로그: fastapi.log / streamlit.log"
echo "  종료: bash start.sh --stop"
echo "======================================================"
