# DeskAd 배포 가이드 — Docker (Phase 1: 앱 티어)

FastAPI 백엔드 + Streamlit 프론트엔드(앱 티어)를 Docker로 띄우는 절차입니다. 앱 티어는
**CPU-only**(`requirements.txt`에 torch/transformers 없음)이고, GPU 작업(LLM·이미지 생성)은
**외부 GPU 워커를 HTTP로 호출**합니다. 따라서 이 단계에서 GPU 워커는 **호스트에 그대로** 두고
컨테이너는 네트워크로만 연결합니다(GPU 워커 컨테이너화는 Phase 2).

> 인프라 고유값(예: `<VM_IP>`)은 자리표시자입니다. 실제 IP/토큰/비밀번호는 커밋하지 마세요.

---

## 1. 구성 개요

| 서비스 | 내용 | 호스트 바인딩 |
|--------|------|---------------|
| `backend` | uvicorn `backend.main:app` | `127.0.0.1:8010` |
| `frontend` | Streamlit `streamlit_app.py` | `127.0.0.1:8501` |
| (호스트) nginx | basic auth + TLS, `127.0.0.1:8501`로 프록시 | `:8443` (외부) |
| (호스트) GPU 워커 | ComfyUI(8188) · Omni vision(11601) · Omni image(11602) · SEED(11501) · Ollama(11434) | `127.0.0.1` 전용 |

- 두 컨테이너 모두 호스트 `127.0.0.1`에만 바인딩 → 직접 외부 노출 없음(보안 정책 유지, `docs/security.md` §5).
- 단일 호스트라 두 서비스는 `network_mode: host`로 호스트 네트워크를 공유합니다. 프론트엔드는 `http://127.0.0.1:8010`으로 백엔드를, 백엔드는 `.env`의 `127.0.0.1:<port>` 워커 URL을 그대로 호출합니다.

관련 파일: `Dockerfile`, `.dockerignore`, `docker-compose.yml`.

---

## 2. 사전 준비

1. **Docker Engine + Compose 플러그인** 설치(`docker compose version`으로 확인). `sudo` 없이 쓰려면 `sudo usermod -aG docker $USER` 후 재로그인(아니면 `sudo docker …`로 실행).
2. **`.env` 작성** — 이미지에 굽지 않고 런타임 주입합니다.
   ```bash
   cd deskad_keyboard_demo
   cp .env.example .env
   # 로그인/가입코드/엔진 키·워커 URL 등 입력
   ```
3. **GPU 워커는 호스트에서 기동**되어 있어야 GPU 경로(local+ComfyUI)가 동작합니다.
   키·워커가 없어도 앱은 폴백(템플릿 문구 + SVG 일러스트)으로 동작합니다.

---

## 3. 빌드 & 실행

> **컷오버 완료(2026-06-15)**: 이 VM에서 호스트 앱을 내리고 컨테이너로 전환·검증 완료 — backend/frontend 모두 healthy, `/health`·프론트(8501)·**nginx `:8443`** 200, `/ai/providers` 워커 wiring 정상(호스트 네트워크), bind 마운트 쓰기 OK(host UID로 빌드). 이미지 콘텐츠 ~195MB(CPU-only; `docker images`의 DISK USAGE 841MB는 빌드 캐시 포함). `.env`는 이미지에 굽지 않고 `env_file`로 주입한다.
>
> **컷오버 주의**: 호스트에서 `start.sh`로 띄운 기존 앱이 `8010`/`8501`을 점유 중이면 같은 포트를 바인딩하지 못한다. 전환 전 먼저 호스트 앱을 내려라.
> ```bash
> ss -ltnp | grep -E ':8010|:8501'   # 점유 확인
> bash start.sh --stop               # 호스트 앱 중지 후 compose 기동
> ```

```bash
cd deskad_keyboard_demo
# 호스트 계정 UID/GID로 빌드해야 bind 마운트에 쓸 수 있다(§4-1).
DESKAD_UID=$(id -u) DESKAD_GID=$(id -g) docker compose up -d --build

# 상태/로그
docker compose ps
docker compose logs -f backend
```

검증:

```bash
curl -fsS http://127.0.0.1:8010/health        # {"status":"ok"} 류
curl -fsS http://127.0.0.1:8501/ >/dev/null   # 프론트엔드 응답
# 브라우저: https://<VM_IP>:8443  (호스트 nginx 경유)
```

> **되돌리기(호스트 앱으로 복귀)**: `docker compose down` 후 `bash start.sh`.

---

## 4. 호스트 GPU 워커 / UID

### 4-1. 빌드 UID (bind 마운트 쓰기)
컨테이너 `appuser`는 빌드 인자 `UID`/`GID`로 만들어집니다(기본 1000). 호스트 계정 UID가 다르면
bind 마운트(`./data/runtime`, `./static`)에 쓰지 못하므로 **호스트 UID로 빌드**해야 합니다:
```bash
DESKAD_UID=$(id -u) DESKAD_GID=$(id -g) docker compose up -d --build
```

### 4-2. 워커 연결 (host 네트워크)
`docker-compose.yml`은 `network_mode: host`라 컨테이너가 호스트 네트워크를 공유합니다. 따라서
`.env`의 `*_BASE_URL`(`http://127.0.0.1:<port>`)이 **그대로** 호스트 워커(ComfyUI 8188 · Ollama 11434 ·
SEED 11501 · Omni 11601/11602)에 닿습니다 — URL을 바꿀 필요가 없습니다.

- 워커가 떠 있지 않은 엔진은 실패합니다. **컨테이너는 `always_on`이라 Omni 워커(11601/11602)를 자동 기동하지 않으므로** 호스트에서 직접 관리하세요(ComfyUI·Ollama는 systemd):
  ```bash
  tools/omni_workers.sh start image    # Omni 이미지 워커(:11602). vision은 start vision (둘은 VRAM 경합 → 상호배타)
  tools/omni_workers.sh status         # 워커 가동 상태 + GPU 여유
  ```
- 앱·워커를 **다른 호스트로 분리**한다면 host 네트워크 대신 bridge + `host.docker.internal`(또는 실제 워커 호스트 URL)로 `.env`를 조정하세요.

---

## 5. 볼륨 & 영속성

| 마운트 | 용도 |
|--------|------|
| `./data/runtime:/app/data/runtime` | 세션·비동기 이미지 잡(jsonl)·`users.json` 등 쓰기 상태 |
| `./static:/app/static` | 업로드/생성 GLB·포스터 (프론트가 model-viewer로 읽음) |
| `/opt/shared_data`, `/opt/shared_model` | (선택) 공유 라이브러리 기능 사용 시. 모델 weight는 굽지 말고 마운트 |

- 생성물(`static/`)과 런타임(`data/runtime/`)은 `.dockerignore`로 이미지에서 제외됩니다.
- 보안: `data/runtime`의 비밀 파일은 호스트에서 `0600` 권한을 유지하세요(`docs/security.md`).

---

## 6. 비밀 주입

- 실제 `.env`는 추적/커밋하지 않습니다. compose `env_file: .env`로 **런타임 주입**.
- `.dockerignore`가 `.env`/`.env.*`를 제외하므로 이미지에 비밀이 들어가지 않습니다(`.env.example`만 포함).
- `/security/config`는 키의 설정/미설정 상태만 반환하고 값은 노출하지 않습니다.

---

## 7. 외부 노출 (nginx)

기존 호스트 nginx(`:8443`, basic auth + self-signed TLS)를 그대로 사용합니다. 업스트림이
`127.0.0.1:8501`(프론트엔드 컨테이너 게시 포트)이므로 설정 변경이 거의 없습니다. WebSocket
경로(`/_stcore/stream`) 프록시는 `docs/security.md` §5 설정을 따릅니다.

---

## 8. 운영

```bash
docker compose restart backend     # 백엔드만 재시작 (start.sh --restart 대응)
docker compose down                # 종료 (볼륨은 보존)
docker compose up -d --build       # 코드 변경 반영 후 재기동
```

- 백엔드 코드를 고쳤다면 라이브 검증 전 `docker compose up -d --build`로 이미지를 갱신해야
  새 코드로 검증됩니다(uvicorn은 기동 시점 코드를 고정).

---

## 9. `GPU_WORKER_MODE` 주의

- 컨테이너 기본값은 **`always_on`**: 앱이 워커를 직접 띄우지 않고 base URL로 호출만 합니다.
- 호스트 단일 실행에서 쓰던 `exclusive`(켜기 전 경쟁 워커 종료)는 **앱이 워커 수명주기를 직접
  관리**하는 전제라, 컨테이너(`systemctl`/`Popen` 불가)에서는 적합하지 않습니다. 컨테이너에서는
  `always_on`을 유지하고 워커 기동/VRAM 조정은 호스트에서 관리하세요.

---

## 10. Phase 2 (예고) — GPU 워커 컨테이너화

`nvidia-container-toolkit` + `--gpus`/compose `deploy.resources`로 워커를 컨테이너화할 수
있으나, 단일 L4(24GB) VRAM 경합과 Omni 이미지 서버의 vendored diffusers/transformers shim
패키징 난도 때문에 별도 작업으로 분리합니다. 모델 weight는 항상 **볼륨 마운트**(이미지에 굽지 않음).
