#!/usr/bin/env bash
# taeho 브랜치를 push 하고 main 으로의 PR 을 GitHub API 로 생성한다.
# 사용:
#   bash deskad_keyboard_demo/tools/push_and_open_pr.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_DIR="$(cd "$APP_DIR/.." && pwd)"

# .env 에서 GITHUB_TOKEN 로드
if [[ ! -f "$APP_DIR/.env" ]]; then
  echo "[push_pr] .env 파일이 없습니다: $APP_DIR/.env" >&2
  exit 1
fi
# shellcheck disable=SC1091
source "$APP_DIR/.env"

if [[ -z "${GITHUB_TOKEN:-}" ]]; then
  echo "[push_pr] GITHUB_TOKEN 이 비어 있습니다. .env 를 확인하세요." >&2
  exit 1
fi

REMOTE_URL="https://x-access-token:${GITHUB_TOKEN}@github.com/ikstre/ai_07_high.git"

# taeho push
echo "[push_pr] taeho push 중..."
git -C "$REPO_DIR" push "$REMOTE_URL" taeho

# PR body 를 변수로 정의 (JSON escape 는 jq 가 처리)
PR_TITLE="feat(ops): ComfyUI systemd 서비스 + start.sh 워커 의존성 체크 + API 포트 정합 (M1)"

read -r -d '' PR_BODY <<'MARKDOWN' || true
## Summary
- ComfyUI를 systemd 서비스(`comfyui.service`)로 등록해 재부팅 자동 기동 / `journalctl -u comfyui` 로그 표준화
- `start.sh` preflight에 ComfyUI/Ollama systemd 의존성 체크 + `.env` 의도 기반 fallback 안내 추가
- 앱 기본 API 포트 8000 → 8010 정합 (JupyterHub와 충돌 회피)
- `.env.example`에서 공인 IP 제거 → loopback 통일

## 변경 파일
- `tools/systemd/comfyui.service` (신규)
- `start.sh` (+69줄, env_value/service_active/url_ready 헬퍼 + `check_model_workers`)
- `backend/config.py`, `streamlit_app.py`, `.env.example` (기본 포트 8010)
- `README.md` (systemd 설치 안내 추가)
- `docs/next_work_2026-05-28.md` (M1 완료 기록)

## Test plan
- [x] `py_compile` 통과
- [x] `tools/scan_secrets.py --all` clean (101 files)
- [x] `bash start.sh --restart` 후 ComfyUI/Ollama active 메시지 출력
- [x] `curl :8188/system_stats` 200, `:8010/health` 200, `:8443/` 401
- [x] `systemctl is-enabled comfyui ollama` → 모두 enabled (부팅 시 자동 기동)

## 차기 (`docs/next_work_2026-05-28.md`)
M2 image job 갤러리 / U1 단계 stepper / U3 포스터 템플릿 썸네일 등
MARKDOWN

# JSON payload 작성 (jq 가 있으면 jq 사용, 없으면 python 폴백)
if command -v jq >/dev/null 2>&1; then
  PAYLOAD=$(jq -nc \
    --arg title "$PR_TITLE" \
    --arg head "taeho" \
    --arg base "main" \
    --arg body "$PR_BODY" \
    '{title: $title, head: $head, base: $base, body: $body}')
else
  PAYLOAD=$(python3 -c '
import json, os, sys
print(json.dumps({
  "title": os.environ["PR_TITLE"],
  "head": "taeho",
  "base": "main",
  "body": os.environ["PR_BODY"],
}))
' PR_TITLE="$PR_TITLE" PR_BODY="$PR_BODY" 2>/dev/null || true)

  # 환경변수 export 방식이 일부 환경에서 python -c 에 안 닿을 수 있어 안전 변형
  if [[ -z "$PAYLOAD" ]]; then
    PR_TITLE="$PR_TITLE" PR_BODY="$PR_BODY" PAYLOAD=$(
      python3 - <<'PY'
import json, os
print(json.dumps({
  "title": os.environ["PR_TITLE"],
  "head": "taeho",
  "base": "main",
  "body": os.environ["PR_BODY"],
}))
PY
    )
  fi
fi

echo "[push_pr] PR 생성 중..."
RESPONSE=$(curl -sS -X POST \
  -H "Authorization: bearer $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  -H "Content-Type: application/json" \
  https://api.github.com/repos/ikstre/ai_07_high/pulls \
  -d "$PAYLOAD")

# PR URL 추출
if command -v jq >/dev/null 2>&1; then
  HTML_URL=$(echo "$RESPONSE" | jq -r '.html_url // empty')
  MESSAGE=$(echo "$RESPONSE"   | jq -r '.message // empty')
else
  HTML_URL=$(python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("html_url",""))' <<< "$RESPONSE")
  MESSAGE=$(python3   -c 'import json,sys; d=json.load(sys.stdin); print(d.get("message",""))'   <<< "$RESPONSE")
fi

if [[ -n "$HTML_URL" ]]; then
  echo "[push_pr] PR 생성 완료: $HTML_URL"
else
  echo "[push_pr] PR 생성 실패: ${MESSAGE:-알 수 없는 오류}" >&2
  echo "[push_pr] 응답 본문 일부:" >&2
  echo "$RESPONSE" | head -c 600 >&2
  echo >&2
  exit 1
fi
