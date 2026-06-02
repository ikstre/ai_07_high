# DeskAd AI Studio - 보안 가이드

이 문서는 2026-05-28 보안 강화 작업의 결과를 운영자/개발자가 한눈에 볼 수 있게 정리한다. 코드 변경의 근거(why)와 점검 절차(how to apply) 중심.

> **개정 이력**
> - 2026-05-28: 초판 (secret redaction / 입력검증 / CORS / 파일권한 / pre-commit scan / nginx basic auth)
> - 2026-06-02: 한국어 prompt injection 패턴, GPU 워커 수명주기·리소스 고갈 완화, 결과 캐시 위생, 업로드 GLB 검증, 회귀 테스트 반영. 런타임 상태/캐시/락 파일 0600 일관화(§2-4, §2-7).

## 1. 위협 모델 요약

- 1순위: secret 노출 (PAT, LLM API key) - 화면/로그/git 히스토리로 새는 사고
- 2순위: 외부 노출 인터페이스 (Streamlit 8501) 무인증 접근
- 3순위: LLM/이미지 워커 prompt injection으로 시스템 프롬프트/내부 경로 누설
- 4순위: 업로드 파일/path traversal로 임의 파일 읽기/쓰기
- 5순위: 모델 워커(ComfyUI/Ollama) 포트가 외부에 열려 임의 추론/대량 요청

## 2. 적용된 코드/운영 변경

### 2-1. Secret redaction 단일 출처

- `backend/security.py`
  - `SENSITIVE_ENV_KEYS`: 보호 대상 환경변수 목록 (GITHUB_TOKEN, *_API_KEY, *_TOKEN, *_SECRET, *_PASSWORD 패턴 포함)
  - `_TOKEN_SHAPED_PATTERNS`: 토큰 모양의 문자열(ghp_, github_pat_, sk-, sk-ant-, hf_, Bearer ...) 정규식
  - `mask_value()`: 값 대신 `"set"` / `"missing"`만 반환
  - `redact_mapping()`: dict 안의 sensitive key를 한 번에 마스킹
  - `SecretLogFilter` + `install_secret_log_filter()`: root / uvicorn / httpx / requests / streamlit 로거에 redaction filter 부착. 환경변수 값과 토큰 모양 문자열을 자동으로 `[REDACTED]`로 치환.
- `backend/main.py`가 import 시점에 `install_secret_log_filter()` 호출 → 모든 응답/로그 경로에서 같은 정책.
- `backend/config.py`의 `redacted_settings()`도 `mask_value()`를 통과해 `/health` 응답에 secret 길이/값이 절대 새지 않는다.

### 2-2. 입력 검증 & prompt injection 방어

- `backend/main.py` Pydantic 모델
  - `AdContentRequest`: product_name 80, target_customer 120, selling_point 240, extra_request 400 등 모든 텍스트 필드에 `max_length`
  - `image_ratio`: `^(1:1|4:5|16:9)$` pattern
  - `image_job_id`: `^[A-Za-z0-9_\-]*$` + max_length 64 → path traversal 차단
  - `UploadedModelRequest.filename`: `^[^/\\\x00]+$` + max_length 255 → 슬래시/널바이트 차단
- `backend/ai.py`
  - `sanitize_user_text(value, limit)`: 제어문자 strip + whitespace 정규화 + 길이 trunc
  - `_ad_context()` / `build_image_prompt()` 모든 사용자 값에 사전 적용
  - `_system_prompt()`에 명시적 보안 규칙: 시스템 프롬프트/환경 변수/API 키/토큰/내부 경로 노출 금지, "이전 지시 무시" 같은 우회 요청 거부, JSON 외 출력 금지
  - `_PROMPT_INJECTION_HINTS` (정규식, `re.IGNORECASE`): 영어/한국어 양쪽 jailbreak 표현을 탐지 — `ignore previous instructions`, `system prompt`, `reveal the system/api`, `act as developer/admin`, `jailbreak`, `disregard the rules` + 한국어 `이전 지시 무시` / `시스템 프롬프트 보여` / `개발자 모드` / `관리자 권한`. `_flag_prompt_injection()`이 사용자 입력에서 매칭되면 응답 메타에 플래그를 남겨 모니터링/후속 차단의 근거로 쓴다 (탐지·기록형, 시스템 프롬프트 방어가 1차 차단선).
  - `_safe_workflow_name()`: 요청 필드 `image_workflow`(ComfyUI 워크플로 선택)을 `^[A-Za-z0-9_-]{1,64}$`로 검증 → `COMFYUI_WORKFLOWS_DIR` 밖으로의 경로 탈출(`../`) 차단. 불합격 시 기본 워크플로로 폴백.

### 2-3. CORS / 외부 노출

- `backend/main.py`의 `CORSMiddleware`가 환경변수 화이트리스트(`DESKAD_CORS_ORIGINS`)에서만 동작
  - 기본값(비어 있음) = CORS 미들웨어 자체를 등록하지 않음 → 외부 origin은 차단된다.
  - `allow_methods = ["GET","POST"]`, `allow_headers = ["Authorization","Content-Type"]`로 좁힘
  - wildcard `*` 지원 안 함
- 모델 워커 바인딩(2026-05-28 19:00 기준):
  - FastAPI 8010: `127.0.0.1` ✓
  - ComfyUI 8188: `127.0.0.1` ✓
  - Ollama 11434: `127.0.0.1` ✓
  - Streamlit 8501: `0.0.0.0` → **외부 공개**. GCP firewall로 회사 IP만 허용하거나 nginx basic auth 권장(§5).
- `start.sh`의 preflight가 ComfyUI/Ollama 외부 바인딩을 감지하면 warn 출력.

### 2-4. 파일 권한

런타임에 생성되는 `data/runtime/` 하위 파일은 전부 **0600**으로 통일한다 (소유자만 read/write). 두 겹으로 보장:

- **코드 생성 시점에 즉시 `chmod 0o600`** (런타임에 새로 만들어져도 새지 않게):
  - `backend/job_store.py` — `image_jobs.jsonl` / `image_quality.jsonl`
  - `backend/runtime_workers.py` — `worker_state.json` (워커 PID/last-used 타임스탬프), `gpu_worker.lock` (`_WorkerLock`이 `os.fchmod(.., 0o600)`)
  - `backend/result_cache.py` — `cache/text/*.json`, `cache/image/*.json`
- **`start.sh` preflight 일괄 잠금** (운영 안전망 + 기존 파일 교정):
  - `.env`가 600 이외 권한이면 600으로 잠금
  - `data/runtime` **하위 모든 파일**을 600으로 잠금 (이전엔 `*.jsonl`만 → 이제 `worker_state.json`·`gpu_worker.lock`·캐시 `*.json` 포함)

### 2-5. Pre-commit secret scan

- `tools/scan_secrets.py`: stdlib만 사용. 패턴은 `backend/security.py`와 공유.
  - 인자 없으면 staged 파일만, `--all`이면 tracked 전체
  - `.env*` 파일은 placeholder 값 외 모든 KV에 alert
  - 값을 절대 출력하지 않고 path:line + reason만 표시
- `tools/git-hooks/pre-commit`: scan_secrets.py를 호출, 0이 아니면 commit 차단
- `start.sh` preflight가 `.git/hooks/pre-commit`이 없으면 자동 symlink 설치

### 2-6. .gitignore 강화

```text
.env
.env.*
!.env.example
*.pem *.key *.crt *.p12
*_secret*
*_token*
.netrc .npmrc
*.bak *.swp *.swo *~

deskad_keyboard_demo/data/runtime/
```

### 2-7. 결과 캐시 위생 (`backend/result_cache.py`)

GPU 작업을 줄이려 텍스트/이미지 결과를 디스크에 캐시한다. 보안 관점에서 다음을 지킨다.

- 경로: `data/runtime/cache/text/<sha256>.json`, `data/runtime/cache/image/<sha256>.json` (`GPU_WORKER_CACHE_DIR`로 재정의 가능)
- **파일명은 SHA256 해시** — 사용자 입력/상품명이 파일명에 노출되지 않는다.
- **이미지 캐시는 `image_b64` 바이너리를 제외**하고 메타데이터만 저장 (`put_image_cache`가 `image_b64` 키 drop) → 대용량 이미지 바이트가 디스크에 중복 적재되지 않음.
- 기록 시 `chmod 0o600` (§2-4) + `.gitignore`의 `data/runtime/` 로 커밋 차단.

> 캐시 디렉터리는 쓰기마다 정리된다: TTL(`GPU_WORKER_CACHE_MAX_AGE_DAYS`, 기본 30일) 만료분을 먼저 제거하고, `GPU_WORKER_CACHE_MAX_ENTRIES`(기본 500) 초과분을 LRU(mtime 기준, 읽기 시 갱신)로 제거 → 장기 운영 시 디스크 무한 누적 방지 (`_prune_dir` / `prune_caches`). 각 값 ≤0이면 해당 차원 비활성화.

### 2-8. GPU 워커 수명주기 & 리소스 고갈 완화 (`backend/runtime_workers.py`)

위협 #5(모델 워커로의 대량 요청 → VRAM 고갈/OOM)에 대한 가용성 방어. 워커 포트는 §2-3대로 전부 127.0.0.1 고정이고, 그 위에 수명주기 제어를 둔다.

- `GPU_WORKER_MODE`:
  - `always_on` — 외부에서 워커를 관리 (start/stop 안 함, 기본값)
  - `on_demand` — 캐시 미스 시 필요한 워커만 기동, idle 타임아웃 후 종료
  - `exclusive` — 한 워커를 켜기 전 **경쟁 워커를 먼저 종료**해 VRAM 확보 → 텍스트/이미지 워커가 동시에 상주하지 않음 (L4 24GB OOM 방지)
- `IMAGE_WORKER_STOP_AFTER_JOB=true` — ComfyUI 이미지 작업 종료 직후 워커를 내려 VRAM 반환 (`release_image_worker_after_job`).
- idle 회수: `GPU_WORKER_IDLE_TIMEOUT_SECONDS`(기본 600초)를 넘긴 워커는 백그라운드 데몬이 자동 종료 (`reap_idle_workers`).
- 동시성: `data/runtime/gpu_worker.lock`에 `fcntl.flock(LOCK_EX)` — 여러 요청이 겹쳐도 start/stop이 직렬화되어 워커 중복 기동/경쟁이 없다. 락 파일도 0600(§2-4).
- 텍스트 워커 종료는 PID 그룹 SIGTERM + 헬스 포트 `fuser -k` 이중 처리, 이미지 워커는 `systemctl stop`.

### 2-9. 업로드 모델 검증 (`backend/cad.py`)

위협 #4(업로드 파일/path traversal) 강화. STEP/GLB 업로드 경로(`handle_model_upload_bytes`)에 적용:

- **확장자 화이트리스트** `ALLOWED_MODEL_EXTENSIONS = {.step, .stp, .glb}` (그 외 거부)
- **크기 한도** `MAX_UPLOAD_MB`(기본 60MB) 초과 시 거부 → 대용량 업로드 디스크/메모리 고갈 차단
- **GLB 매직 헤더** `b"glTF"` 검사 — 헤더 위조 거부
- 파일명은 업로드 데이터의 SHA256(12자)로 재명명 → 클라이언트 제공 경로/이름을 그대로 쓰지 않음 (filename 패턴 검증은 §2-2)
- `glb_unit_check()`: 1 unit=1cm 가정, 바운딩박스 최대 변이 <1cm(m 의심 ×100) / >250cm(mm 의심 ×0.1)면 보정을 권고. **advisory only — 업로드를 차단하지 않고** 응답 `unit_check`/메시지에만 첨부.

### 2-10. 회귀 테스트 (`tests/`)

보안-인접 동작을 코드로 고정해 회귀를 막는다. 전부 순수 함수 + 모킹이라 네트워크/GPU/외부 키 없이 `pytest tests`로 실행 (`conda run -n sprint_high pytest tests` → 12 passed).

- `test_copy_policy.py` — 금지어 치환, 공백 회피("국내1위") 탐지, 채널별 길이/해시태그 제한
- `test_llm_retry.py` — `_post_with_retry`: 5xx 재시도→성공 / 4xx 즉시 raise / 연결오류 소진 (`Session.post` 모킹)
- `test_cad_glb.py` — `glb_unit_check` cm/mm/m + 루트 scale 오탐 없음 (JSON-only GLB)
- `test_quality_gate.py` — `ImageQualityReport` 직렬화 + summary 집계

## 3. 운영자 체크리스트

매일 또는 새 환경 시작 시:

1. `stat -c '%a' deskad_keyboard_demo/.env` → `600`
2. `find deskad_keyboard_demo/data/runtime -type f -exec stat -c '%n %a' {} +` → 모두 `600` (jsonl 로그 + `worker_state.json` + `gpu_worker.lock` + `cache/*.json`)
3. `ss -ltn | awk '$4 ~ /:(8010|8188|11434)$/'` → 모두 `127.0.0.1`로 시작
4. `python deskad_keyboard_demo/tools/scan_secrets.py --all` → exit 0
5. `git config --get core.hooksPath` 또는 `.git/hooks/pre-commit` 심볼릭 링크 확인

## 4. 사고 대응 - secret 노출 시

1. **즉시 revoke** - 노출된 토큰의 종류별 페이지:
   - GitHub classic PAT: https://github.com/settings/tokens
   - GitHub fine-grained PAT: https://github.com/settings/personal-access-tokens
   - OpenAI: https://platform.openai.com/api-keys
   - HuggingFace: https://huggingface.co/settings/tokens
2. **사용 흔적 점검** - GitHub security log, OpenAI usage dashboard, HF token activity
3. **재발급 + .env 교체** - 값을 화면에 띄우지 않는 방법:
   ```bash
   cd /home/leetaeho/ai_07_high/deskad_keyboard_demo
   read -s -p "New TOKEN: " T && \
     sed -i.bak -E "s|^GITHUB_TOKEN=.*$|GITHUB_TOKEN=${T}|" .env && \
     unset T
   chmod 600 .env
   shred -u .env.bak    # 백업 파일 안전 삭제
   ```
4. **git 히스토리에 새 적이 있는지 검사**:
   ```bash
   python deskad_keyboard_demo/tools/scan_secrets.py --all
   ```
   히트가 나면 해당 커밋이 푸시 전이면 amend 또는 reset --soft. 푸시 후라면 `git filter-repo`로 cleanup + remote 강제 푸시 + 협업자에 알림.

## 5. 외부 공개되는 Streamlit(8501) 보호 - 적용 완료 (2026-05-28)

이중 잠금이 적용된 상태.

### Layer 1: nginx basic auth + self-signed HTTPS (적용 완료)

- 패키지: `nginx 1.24.0`, `apache2-utils`
- 인증서: `/etc/nginx/ssl/deskad.crt` (self-signed, CN=34.27.86.182, 10년 유효)
- 키:    `/etc/nginx/ssl/deskad.key` (root:root 0600)
- htpasswd: `/etc/nginx/.deskad_htpasswd` (root:www-data 0640, bcrypt)
- 설정: `/etc/nginx/sites-enabled/deskad`
  - 8443/tcp HTTPS, TLSv1.2+TLSv1.3, HIGH cipher
  - `Strict-Transport-Security`, `X-Frame-Options DENY`, `X-Content-Type-Options nosniff`, `Referrer-Policy strict-origin-when-cross-origin`
  - basic auth realm "DeskAd AI Studio"
  - `/` 와 `/_stcore/stream` 둘 다 127.0.0.1:8501로 WebSocket upgrade 프록시
- Streamlit listen: `127.0.0.1:8501` (start.sh의 `FRONTEND_HOST`로 잠금. `DESKAD_STREAMLIT_HOST=0.0.0.0` 환경변수로 임시 해제 가능, 평소엔 사용 금지)
- Streamlit 추가 옵션: `--server.enableCORS false --server.enableXsrfProtection true`

비밀번호 갱신 (echo OFF, 한 줄):

```bash
sudo htpasswd -B /etc/nginx/.deskad_htpasswd deskad
# 추가 사용자 만들기:  sudo htpasswd -B /etc/nginx/.deskad_htpasswd <new_user>
# 사용자 삭제:        sudo htpasswd -D /etc/nginx/.deskad_htpasswd <user>
# 변경 후 reload 필요 없음 (nginx가 매 요청마다 파일 읽음)
```

### Layer 2: GCP firewall IP allowlist (사용자가 직접 적용)

VM 안의 서비스 계정은 compute scope가 없어 자동화 불가. 본인 PC/Cloud Shell에서 본인 계정 인증 후 실행:

```bash
# 1) 프로젝트 선택
gcloud config set project sprint-ai-chunk3-01

# 2) 본인 노트북/공유기 외부 IP 확인 (현재 SSH 세션에서 잡힌 IP: 112.162.29.176)
MY_IP=$(curl -s ifconfig.me)
echo "$MY_IP"

# 3) 8443 (HTTPS) 만 본인 IP에서 허용
gcloud compute firewall-rules create deskad-https-allow \
  --direction=INGRESS --action=ALLOW \
  --rules=tcp:8443 \
  --source-ranges="${MY_IP}/32" \
  --priority=900

# 4) 기존 8501 외부 공개 규칙 정리 (있다면)
gcloud compute firewall-rules list --filter="allowed.ports~8501" --format="value(name)" \
  | while read rule; do
      [ -n "$rule" ] && gcloud compute firewall-rules delete "$rule" --quiet
    done
```

또는 GCP Console:
- VPC 네트워크 > 방화벽 > 규칙 만들기
- 이름 `deskad-https-allow` / 방향 `수신` / 대상 `모든 인스턴스`
- 소스 IPv4: 본인 IP/32 (예: 112.162.29.176/32)
- 프로토콜/포트: `tcp:8443`

IP가 바뀌면 (KT 망 등) 위 명령의 `--source-ranges` 만 다시 update:
```bash
gcloud compute firewall-rules update deskad-https-allow --source-ranges=<new-ip>/32
```

### 접속 URL

- 외부: `https://34.27.86.182:8443` (브라우저가 self-signed cert 경고 → "고급 → 진행" 한 번 확인)
- 로컬: `http://127.0.0.1:8501` (VM 내부 SSH에서만)

### 운영 점검

```bash
# nginx 상태
sudo systemctl status nginx

# 잘못된 자격증명으로 접근 - 401 받아야 정상
curl -sk -o /dev/null -w "%{http_code}\n" https://127.0.0.1:8443/

# 올바른 자격증명 - 200
curl -sk -u deskad:<password> -o /dev/null -w "%{http_code}\n" https://127.0.0.1:8443/

# 인증서 만료일
echo | openssl s_client -connect 127.0.0.1:8443 2>/dev/null | openssl x509 -noout -dates
```

## 6. 자동 점검 명령

```bash
# 한 줄로 모든 점검:
( cd /home/leetaeho/ai_07_high/deskad_keyboard_demo && \
  python tools/scan_secrets.py --all && \
  stat -c '%n %a' .env 2>/dev/null && \
  find data/runtime -type f -exec stat -c '%n %a' {} + 2>/dev/null && \
  ss -ltn | awk '$4 ~ /:(8010|8188|11434|8501)$/' )
```

기대 출력:
- scan_secrets: `clean (N file(s) scanned).`
- .env: 600
- `data/runtime` 하위 전부 (jsonl·`worker_state.json`·`gpu_worker.lock`·`cache/*.json`): 모두 600
- 8010 / 8188 / 11434: 127.0.0.1
- 8501: 0.0.0.0 → nginx로 보호한 경우 127.0.0.1
