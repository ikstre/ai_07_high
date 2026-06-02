# DeskAd AI Studio 인수인계 문서 - 2026-05-28

작성일: 2026-05-28
프로젝트 경로: `/home/leetaeho/ai_07_high/deskad_keyboard_demo`
현재 작업 브랜치: `taeho`

이 문서는 `docs/project_handoff_2026-05-27.md`의 `§21 ~ §22` 이후에 이어진 작업을 정리한다. 새 대화는 `§9. 최신 새 대화창 시작 프롬프트`부터 읽어도 된다.

## 1. 이번 세션 한 줄 요약

- 로컬 한국어 LLM 서버(Ollama qwen2.5:7b)와 로컬 이미지 워커(ComfyUI + FLUX.1 schnell fp8)를 실제로 연결해 카피/포스터/품질 파이프라인을 처음부터 끝까지 검증했다.
- HyperCLOVA direct API 어댑터, image job jsonl 영속화, 품질 평가 gate skeleton을 새로 넣고 Streamlit UI에도 노출했다.

## 2. 새로 추가/변경된 파일

추가:

- `backend/job_store.py` - 이미지 job 영속화 jsonl store
- `backend/quality_gate.py` - 가벼운 품질 평가 gate skeleton + ImageQualityStore
- `tools/comfyui_workflows/flux_schnell_basic.json` - FLUX.1 schnell API-format workflow
- `docs/project_handoff_2026-05-28.md` (본 문서)

변경:

- `backend/llm_adapters.py` - `HyperClovaDirectAdapter` (Naver Cloud ClovaStudio chat-completions 직접 호출) 추가
- `backend/config.py` - `HYPERCLOVA_USE_DIRECT_API`, `HYPERCLOVA_APIGW_KEY` 환경변수 추가
- `backend/ai.py` - `IMAGE_JOB_STORE` (jsonl 기반)로 전환, hyperclova direct 분기 연결
- `backend/main.py` - `/ai/image/jobs` 목록 API, `/ai/image/jobs/{id}/quality` (POST/GET), `/ai/quality/summary` 추가
- `streamlit_app.py` - "이미지 품질 검사 실행" 버튼과 결과 expander 추가
- `.env.example` - `HYPERCLOVA_USE_DIRECT_API`, `HYPERCLOVA_APIGW_KEY` 항목 추가
- `.gitignore` - `deskad_keyboard_demo/data/runtime/` 무시

## 3. 새 API 표

| Method | Path | 설명 |
|---|---|---|
| GET | `/ai/image/jobs` | 영속 store에 저장된 이미지 job 최신 목록 (limit 파라미터, 기본 20) |
| POST | `/ai/image/jobs/{id}/quality` | 완료된 job에 대해 skeleton 평가기 실행 (해상도/aspect ratio/bytes) |
| GET | `/ai/image/jobs/{id}/quality` | 저장된 품질 리포트 조회 |
| GET | `/ai/quality/summary` | 리포트 개수/평가기 종류/store path |

기존 API 동작 변경:

- `POST /ai/image/jobs`, `GET /ai/image/jobs/{id}`는 jsonl 영속 store를 사용한다. 서버 재시작 후에도 이전 job 조회/포스터 합성이 가능하다.
- `apply_copy_policy`/`generate_copy_experiment`/`/ai/poster` 흐름은 변경 없음 (호환 유지).

## 4. 새 환경변수

```text
# HyperCLOVA direct API (false면 기존 OpenAI-compatible gateway 흐름 유지)
HYPERCLOVA_USE_DIRECT_API=false
HYPERCLOVA_APIGW_KEY=

# image job 영속화 경로 override (기본: deskad_keyboard_demo/data/runtime/image_jobs.jsonl)
IMAGE_JOBS_STORE_PATH=

# 품질 리포트 영속화 경로 override (기본: deskad_keyboard_demo/data/runtime/image_quality.jsonl)
IMAGE_QUALITY_STORE_PATH=
```

세션 검증을 위해 실제 `.env`에는 아래도 추가되어 있다 (gitignored).

```text
AI_PROVIDER=auto
KANANA_BASE_URL=http://127.0.0.1:11434/v1
KANANA_MODEL=qwen2.5:7b
MIDM_BASE_URL=http://127.0.0.1:11434/v1
MIDM_MODEL=qwen2.5:7b
LOCAL_LLM_BASE_URL=http://127.0.0.1:11434/v1
LOCAL_LLM_MODEL=qwen2.5:7b

IMAGE_MODEL_BACKEND=auto
COMFYUI_BASE_URL=http://127.0.0.1:8188
COMFYUI_WORKFLOW_PATH=tools/comfyui_workflows/flux_schnell_basic.json
FLUX_MODEL_VARIANT=flux1-schnell-fp8
IMAGE_QUANTIZATION=fp8_e4m3fn
```

## 5. 외부 의존성

신규 설치한 외부 도구:

- Ollama 0.24.0 - systemd 서비스로 활성화 (`systemctl status ollama`)
  - 모델: `qwen2.5:7b` (4.7GB, OpenAI-compatible /v1/chat/completions)
- ComfyUI 0.22.0 - `/opt/shared_model/ComfyUI`에 shallow clone, sprint_high에 requirements 설치
  - 서버: `python main.py --listen 127.0.0.1 --port 8188`
  - 로그: `/opt/shared_model/ComfyUI/comfyui.log`
  - 출력: `/opt/shared_model/ComfyUI/output/`
- FLUX.1 schnell 모델 (Comfy-Org 공개 mirror, /opt/shared_model/ComfyUI/models/)
  - `diffusion_models/flux1-schnell-fp8.safetensors` 17GB
  - `text_encoders/clip_l.safetensors` 235MB
  - `text_encoders/t5xxl_fp8_e4m3fn.safetensors` 4.6GB
  - `vae/ae.safetensors` 320MB
  - 출처: `huggingface.co/Comfy-Org/flux1-schnell`, `huggingface.co/comfyanonymous/flux_text_encoders`, `huggingface.co/Comfy-Org/Lumina_Image_2.0_Repackaged` (FLUX VAE 공개 미러)

## 6. 검증 결과

`py_compile` 통과:

```text
backend/llm_adapters.py backend/job_store.py backend/quality_gate.py
backend/ai.py backend/config.py backend/main.py streamlit_app.py
```

FastAPI TestClient 결과:

```text
/health                       200
/ai/providers                 200  (kanana, midm = configured)
/ai/copy provider=kanana      200  실제 한국어 카피 ("65키 알루미늄 야상 키보드" / "프리미엄 마감, 안정적 사용")
/ai/copy/experiment           200  kanana/midm/fallback 모두 응답
/ai/image/jobs (ComfyUI)      200  status=queued -> 112초 후 completed
/ai/image/jobs/{id}           200  poll 정상
/ai/image/jobs                200  jsonl store에서 2 jobs 로드 (서버 재시작 후 검증)
/ai/image/jobs/{id}/quality   200  1024x1024 / 1.48MB / aspect_ratio_actual=1:1
/ai/poster image_job_id=...   200  ComfyUI PNG가 SVG hero에 embed (image_embedded=true, 1.97MB)
```

서비스 상태:

```text
FastAPI    http://127.0.0.1:8010    200
Streamlit  http://34.27.86.182:8501 200
Ollama     http://127.0.0.1:11434   200 (systemd)
ComfyUI    http://127.0.0.1:8188    200 (수동 nohup)
GPU        L4 24GB                  FLUX fp8 + qwen2.5:7b 동시 가용 (Ollama는 idle 시 swap-out)
```

## 7. 아직 남은 작업

1. ComfyUI를 systemd 서비스로 등록해 재부팅 시 자동 기동. 현재는 `nohup`로 수동 기동.
2. quality gate를 실제 워커로 확장 (OCR 라이브러리 도입, Canny IoU vs reference asset).
3. Streamlit에 "이전 image job 재사용" 카드. 현재는 가장 최근 한 건만 노출.
4. HyperCLOVA direct API에 대한 실 호출 회귀 테스트 (API 키 발급되면 추가).
5. `image_jobs.jsonl` append-only 로그가 커지면 `IMAGE_JOB_STORE.compact()`를 cron으로 실행.

## 8. 보안 강화 작업 (완료, 2026-05-28 저녁)

이번 세션 후반에 보안 6 레이어를 일괄 적용했다. 자세한 운영 가이드는 `docs/security.md`.

### 8-1. Secret 노출 방지

- `backend/security.py` 신설
  - `SENSITIVE_ENV_KEYS`, 토큰 모양(`ghp_`, `github_pat_`, `sk-`, `sk-ant-`, `hf_`, `Bearer ...`) 정규식
  - `mask_value()`, `redact_mapping()`
  - `SecretLogFilter` + `install_secret_log_filter()` — root / uvicorn / httpx / requests / streamlit 로거에 부착해 환경변수 값과 토큰 모양 문자열을 `[REDACTED]`로 치환
- `backend/main.py` import 시점에 `install_secret_log_filter()` 호출
- `backend/config.py`의 `redacted_settings()`가 동일 마스킹 헬퍼 사용
- 결과: `/health` 응답, uvicorn access/error 로그, FastAPI 내부 로그 모두 secret 값 누설 0

### 8-2. Pre-commit secret scan

- `tools/scan_secrets.py` (stdlib only)
  - placeholder 외의 env value, 토큰 모양 substring 탐지
  - 발견 시 path:line + reason만 표시, 값은 절대 출력하지 않음
- `tools/git-hooks/pre-commit` — 커밋 차단 hook
- `start.sh` preflight가 `.git/hooks/pre-commit` 심볼릭 링크 자동 설치
- `.gitignore` 강화: `*.pem`, `*.key`, `*.bak`, `data/runtime/`, `_secret*`, `_token*` 등 추가

### 8-3. 입력 검증 & prompt injection 방어

- `backend/main.py` Pydantic 필드에 `max_length`, `pattern` 적용
  - `product_name` 80, `target_customer` 120, `selling_point` 240, `extra_request` 400
  - `image_ratio` `^(1:1|4:5|16:9)$`
  - `image_job_id` `^[A-Za-z0-9_\-]*$` + max 64 → path traversal 차단
  - `UploadedModelRequest.filename` `^[^/\\\x00]+$` + max 255
- `backend/ai.py`에 `sanitize_user_text()` — 제어문자 strip, 길이 trunc. `_ad_context()` / `build_image_prompt()` 모든 사용자 값에 적용
- `_system_prompt()`에 명시적 보안 규칙 추가: API 키/토큰/내부 경로 노출 금지, "이전 지시 무시" 같은 우회 요청 거부

### 8-4. CORS 및 외부 노출 정리

- `CORSMiddleware`가 환경변수 `DESKAD_CORS_ORIGINS` 화이트리스트에서만 동작
- 미설정 시 미들웨어 자체 미등록 → 외부 origin 차단
- `allow_methods=["GET","POST"]`, `allow_headers=["Authorization","Content-Type"]`, wildcard `*` 미지원
- `start.sh` preflight가 ComfyUI/Ollama 외부 바인딩 감지 시 경고

### 8-5. 파일 권한 / 운영 안전망

- `start.sh` preflight가 `.env`, `data/runtime/*.jsonl`을 자동으로 0600 잠금
- `backend/job_store.py`가 jsonl을 처음 생성할 때부터 chmod 0o600
- nginx 인증 파일 `/etc/nginx/.deskad_htpasswd` 0640 root:www-data

### 8-6. 외부 노출 Streamlit 8501 → nginx 8443으로 이중 잠금

- **Layer 1 (VM 안)**: nginx 1.24 + apache2-utils
  - self-signed cert `/etc/nginx/ssl/deskad.{crt,key}` (CN=34.27.86.182, 2036-05-25 까지)
  - basic auth `/etc/nginx/.deskad_htpasswd` (bcrypt $2y$, user=`deskad`)
  - TLSv1.2+1.3, HSTS, X-Frame-Options DENY, X-Content-Type-Options nosniff, Referrer-Policy
  - WebSocket proxy → `127.0.0.1:8501`
- **Streamlit listen**: `127.0.0.1:8501` (start.sh `FRONTEND_HOST`, 평상시 0.0.0.0 사용 금지)
- Streamlit 옵션: `--server.enableCORS false --server.enableXsrfProtection true`
- **Layer 2 (GCP)**: 본인 계정으로 `deskad-https-allow` 규칙 생성, 8443/tcp만 내부 진행자 IP에 허용. 8501은 외부 공개 규칙 없음.

### 8-7. 토큰 사고 대응 (이번 세션 발생)

세션 초반에 `.env`의 GITHUB_TOKEN이 한 번 화면에 노출됐다. 사용자가 즉시 GitHub에서 revoke + 새 PAT 발급 + `.env` 교체 완료.

이후 재발 방지로 위의 6 레이어 적용. 비슷한 사고 발생 시 절차는 `docs/security.md §4`.

## 9. 보안 검증 결과 (2026-05-28 06:30 UTC)

```text
nginx 8443 no-creds            : 401 (Basic realm="DeskAd AI Studio")
nginx 8443 wrong-creds         : 401
Streamlit loopback 8501        : 200
FastAPI / ComfyUI / Ollama 포트: 127.0.0.1만
nginx 8443                     : 0.0.0.0 / [::] (GCP firewall로 IP allowlist)
.env / .key / htpasswd 권한    : 600 / 600 / 640
tools/scan_secrets.py --all    : clean (79 files scanned)
Pydantic 422 차단              : product_name 200자, image_job_id 경로 traversal 모두 차단
LLM 응답 누설 (API_KEY/GITHUB_TOKEN/ghp_/sk-/system prompt) : 0건
```

## 9. 최신 새 대화창 시작 프롬프트

```text
이 프로젝트는 `/home/leetaeho/ai_07_high/deskad_keyboard_demo`에 있는 DeskAd AI Studio입니다.
목표는 커스텀 키보드/데스크테리어 소상공인이 실물 촬영 없이 3D 셋업 미리보기와 광고 문구/포스터/실사 광고 이미지를 만들 수 있게 하는 서비스입니다.

현재 환경:
- GCP VM + PyCharm Remote/SSH
- conda env: `sprint_high`
- FastAPI port: 8010
- Streamlit port: 8501
- Ollama port: 11434 (systemd, qwen2.5:7b 한국어 카피)
- ComfyUI port: 8188 (수동 기동, FLUX.1 schnell fp8)
- 외부 접속: http://34.27.86.182:8501
- JupyterHub가 8000 포트를 사용하므로 앱은 8000을 쓰면 안 됩니다.

중요 규칙:
- 실제 `.env`와 API/GitHub/HF 토큰 값을 출력하거나 커밋하지 마세요.
- `.env.example`에는 빈 템플릿만 유지하세요.
- 공용 모델은 `/opt/shared_model`, 공용 데이터/도면/이미지는 `/opt/shared_data`에 둡니다.
- 큰 모델 파일은 git에 들어가지 않습니다.

직전 완료 작업 (2026-05-28):
1. Ollama + qwen2.5:7b로 KANANA/MIDM/LOCAL_LLM endpoint를 실제 연결, /ai/copy/experiment 통해 실 한국어 카피 생성 확인
2. ComfyUI 0.22 + FLUX.1 schnell fp8을 :8188에 띄우고 /ai/image/jobs queue/poll/포스터 합성까지 끝까지 검증 (1024x1024, 112초 추론)
3. HyperCLOVA direct API adapter (HyperClovaDirectAdapter) 분리
4. image job을 jsonl 영속화 (IMAGE_JOB_STORE)
5. 품질 평가 gate skeleton 추가 (해상도/aspect ratio만 채움)
6. Streamlit에 "이미지 품질 검사 실행" 버튼 + 결과 expander 추가

다음 우선순위:
1. ComfyUI/ollama를 systemd로 영속화하고 start.sh에서 의존성으로 체크.
2. 품질 워커 확장: OCR (paddleocr/easyocr) + Canny IoU vs reference.
3. /ai/image/jobs/{id}/regenerate 또는 변주 (FLUX schnell N장 batch + 자동 큐레이션).
4. Streamlit에 이전 job 갤러리 expand.
5. HyperCLOVA direct API 실 키 확보 시 회귀 테스트 추가.

검증 명령:

```bash
cd /home/leetaeho/ai_07_high/deskad_keyboard_demo

conda run -n sprint_high python -B -m py_compile \
  backend/main.py backend/renderer.py backend/ai.py \
  backend/assets.py backend/cad.py backend/config.py \
  backend/library.py backend/llm_adapters.py backend/copy_policy.py \
  backend/job_store.py backend/quality_gate.py \
  streamlit_app.py tools/download_notion_references.py

bash start.sh --restart
curl -s http://127.0.0.1:8010/health | head -c 400
```
```

## 10. 종료 절차

```bash
bash /home/leetaeho/ai_07_high/deskad_keyboard_demo/start.sh --stop
# Ollama: systemctl stop ollama  (기본은 항상 켜두는 게 안전)
# ComfyUI: pkill -f "ComfyUI.*main.py"  또는 lsof -ti tcp:8188 | xargs -r kill
```
