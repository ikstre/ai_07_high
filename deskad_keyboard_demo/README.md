# DeskAd AI Studio

소상공인 커스텀 키보드 / 데스크테리어 판매자를 위한 **3D 셋업 미리보기 + 광고 콘텐츠 생성** 프로토타입입니다.

## 기능 요약

| 단계 | 기능 |
|------|------|
| ① 상품 정보 | 키보드 모델명·레이아웃 입력, STEP/STP/GLB 업로드 |
| ② 도면 미리보기 | 레이아웃 JSON → SVG 탑뷰 도면 생성 |
| ③ 3D 셋업 구성 | 책상 크기·모니터 크기·데스크테리어 선택 후 GLB 생성 |
| ④ 광고 생성 | 광고 문구(AI/폴백 템플릿) + 광고 이미지 생성(엔진 선택) + SVG/PPTX 포스터 다운로드 |

---

## 이미지 생성 엔진

광고 문구·이미지는 **엔진**을 골라 생성합니다(`engine` = `auto`/`local`/`hyperclova`/`openai`). 사용 가능 여부는 `GET /ai/providers`로 조회합니다.

| 엔진 | 광고 문구 | 광고 이미지 | 비고 |
|------|-----------|-------------|------|
| `local` | 로컬 LLM(Ollama) | ComfyUI/FLUX img2img | 키 불필요, 도면/셋업 픽셀 참조로 정확도 우선 |
| `hyperclova` | HyperCLOVA X SEED | HyperCLOVA Omni 네이티브 text→image | 설정값을 텍스트로 그라운딩 |
| `openai` | OpenAI 호환 API | OpenAI 이미지 | `OPENAI_API_KEY` 필요 |

- **비동기 이미지 잡**: `POST /ai/image/jobs`로 큐에 넣고 `GET /ai/image/jobs/{id}`로 폴링합니다. 동기 `POST /ai/image`도 유지됩니다.
- **best-of-N 구도 선별**: 여러 후보를 만든 뒤 `quality_gate`가 구도 기준으로 가장 좋은 컷을 고릅니다(`/ai/image/jobs/{id}/quality`).
- 엔진/워커/키가 없으면 폴백: 문구는 템플릿, 이미지는 SVG 일러스트(모니터+키보드 실루엣).

GPU 워커(ComfyUI/Omni/SEED)는 단일 L4 VRAM을 공유합니다. `GPU_WORKER_MODE`로 워커 수명주기를 제어합니다 — `always_on`(기본, 외부에서 관리)·`exclusive`(켜기 전 경쟁 워커 종료)·`on_demand`.

---

## 빠른 시작

### 1. 환경 준비

```bash
# 의존성 설치 (최초 1회)
conda run -n sprint_high pip install -r deskad_keyboard_demo/requirements.txt

# 환경 변수 설정
cp deskad_keyboard_demo/.env.example deskad_keyboard_demo/.env
# .env에서 OPENAI_API_KEY 등 필요한 항목 입력
# API 키 없이도 GLB 렌더 + 템플릿 광고 문구는 동작합니다
```

### 2. 통합 실행 (권장)

```bash
bash deskad_keyboard_demo/start.sh
```

옵션:

```bash
bash deskad_keyboard_demo/start.sh --restart   # 실행 중인 서버 재시작
bash deskad_keyboard_demo/start.sh --stop      # 서버 종료
```

### 2-1. Docker로 실행 (선택)

앱 티어(FastAPI+Streamlit)는 CPU-only라 컨테이너로도 띄울 수 있습니다. GPU 워커는 호스트(systemd/Popen)에 그대로 두고 `GPU_WORKER_MODE=always_on`으로 HTTP 호출만 합니다.

```bash
cd deskad_keyboard_demo
cp .env.example .env            # 값 입력. 워커 *_BASE_URL은 host.docker.internal 권장
docker compose up -d --build
curl -fsS http://127.0.0.1:8010/health
```

두 서비스 모두 호스트 `127.0.0.1`에만 바인딩되며, 외부 접속은 기존처럼 호스트 nginx `:8443`이 담당합니다. 자세한 배포 절차·주의사항은 [docs/deploy.md](docs/deploy.md)를 참고하세요.

### 3. 모델 워커(systemd, 선택)

로컬 이미지 생성을 쓸 때는 ComfyUI를 systemd 서비스로 등록합니다. Ollama는 패키지 설치 시 생성되는 `ollama.service`를 사용하며, `start.sh`가 두 워커 상태를 점검합니다.

```bash
sudo install -m 0644 deskad_keyboard_demo/tools/systemd/comfyui.service /etc/systemd/system/comfyui.service
sudo systemctl daemon-reload
sudo systemctl enable --now comfyui
systemctl status comfyui --no-pager
```

로그 확인:

```bash
journalctl -u comfyui -f
```

### 3-1. HyperCLOVA X SEED 로컬 실행(Hugging Face, 선택)

HyperCLOVA X SEED 공개 weight는 Hugging Face에서 받아 OpenAI-compatible 서버로 띄운 뒤 `hyperclova` provider에 연결할 수 있습니다. 모델 파일 접근에 동의가 필요한 gated repo이므로 Hugging Face에서 조건을 먼저 승인하고, 필요한 경우 `.env`에 `HF_TOKEN`을 넣습니다.

이 VM은 L4 24GB GPU를 쓰며 ComfyUI가 켜져 있으면 VRAM을 함께 사용합니다. 광고 문구 생성에는 우선 `Text-Instruct-1.5B`를 권장하고, VRAM이 부족하면 `0.5B`로 낮춥니다.

```bash
cd deskad_keyboard_demo

# .env 예시
HYPERCLOVA_BASE_URL=http://127.0.0.1:11501/v1
HYPERCLOVA_MODEL=naver-hyperclovax/HyperCLOVAX-SEED-Text-Instruct-1.5B
HYPERCLOVA_USE_DIRECT_API=false
HF_TOKEN=<huggingface-token-if-required>

# 모델은 첫 실행 시 Hugging Face cache로 다운로드됩니다.
conda run -n sprint_high python tools/hyperclova_seed_openai_server.py
```

다른 터미널에서 확인:

```bash
curl -s http://127.0.0.1:11501/health
curl -s http://127.0.0.1:8010/ai/providers
```

### 4. 개별 실행

**백엔드 (FastAPI, 포트 8010)**

```bash
cd deskad_keyboard_demo
conda run -n sprint_high python -m uvicorn backend.main:app --host 127.0.0.1 --port 8010
```

**프론트엔드 (Streamlit, 포트 8501)**

```bash
cd deskad_keyboard_demo
conda run -n sprint_high python -m streamlit run streamlit_app.py \
  --server.port 8501 --server.address 127.0.0.1 --server.headless true \
  --server.enableCORS false --server.enableXsrfProtection true
```

### 5. 접속

```
https://<VM_IP>:8443
```

> **포트 안내**  
> - `8443` — nginx + basic auth 외부 접속  
> - `8501` — Streamlit 프론트엔드, loopback 전용  
> - `8010` — FastAPI 백엔드, loopback 전용  
> - `8188` — ComfyUI 이미지 워커, loopback 전용  
> - `11434` — Ollama 로컬 LLM, loopback 전용  
> - `11501` — HyperCLOVA X SEED 텍스트 워커, loopback 전용  
> - `11601` — HyperCLOVA Omni 비전 워커(4bit), loopback 전용  
> - `11602` — HyperCLOVA Omni 이미지 워커(8bit), loopback 전용  
> - `8000` — JupyterHub 전용, **절대 사용 금지**

---

## 보안 설정

실제 API 키는 커밋하지 않습니다.

- `.gitignore`에 `.env`, `.env.*`, 업로드/포스터/모델 파일 제외 설정 포함
- `/security/config` API 엔드포인트는 키의 "설정됨/미설정" 상태만 반환, 실제 값 미노출

---

## 렌더링 치수 기준

모든 3D 씬은 `1 GLB unit = 1 cm` 기준입니다. 외부 모델 없이 `backend/renderer.py`의 절차적 박스 렌더러로 생성합니다.

### 책상 프리셋

| 이름 | 너비 × 깊이 |
|------|------------|
| 소형 | 120 × 60 cm |
| 중형 | 120 × 80 cm |
| L형 소형 | 140 × 70 cm |
| L형 중형 | 160 × 80 cm |
| 와이드 | 180 × 80 cm |

### 모니터 크기 프리셋

| 선택 | 패널 크기 |
|------|----------|
| 24인치 | 56 × 33 cm |
| 27인치 | 62 × 36 cm |
| 32인치 | 74 × 43 cm |

모니터암은 VESA MIS-D 100×100mm 기준입니다.

### 키보드 레이아웃 프리셋

| 레이아웃 | 크기 | 키 수 |
|----------|------|-------|
| 60% | 약 28.6 × 9.5 cm | 61키 |
| 65% | 약 30.5 × 9.5 cm | 67키 |
| 75% | 약 30.5 × 11.4 cm | 84키 |
| 87% (TKL) | 약 34.8 × 11.4 cm | 87키 |
| 104% (풀배열) | 약 42.9 × 11.4 cm | 104키 |

MX 스위치 간격 기준 `1u = 19.05 mm`.

---

## 파일 구조

```
deskad_keyboard_demo/
├── start.sh                    # 앱 티어 통합 실행 스크립트
├── streamlit_app.py            # Streamlit 진입점
├── ppt_export.py               # 포스터 PPTX/PIL 렌더
├── requirements.txt            # 앱 티어 의존성 (CPU-only, torch 없음)
├── Dockerfile / .dockerignore  # 앱 컨테이너 이미지
├── docker-compose.yml          # backend + frontend 2서비스
├── .env.example
├── backend/                    # FastAPI
│   ├── main.py                 # 엔드포인트 정의
│   ├── app_factory.py          # 앱 생성 + StaticFiles 마운트
│   ├── routes/                 # assets · layouts · plates 라우터
│   ├── renderer.py             # 절차적 GLB 생성기
│   ├── ai.py                   # 문구/이미지 생성 (엔진 선택·폴백)
│   ├── copy_policy.py          # 문구 품질 정책/재시도
│   ├── quality_gate.py         # 이미지 best-of-N 구도 선별
│   ├── job_store.py            # 비동기 이미지 잡 큐 (jsonl)
│   ├── result_cache.py         # 생성 결과 캐시
│   ├── runtime_workers.py      # GPU 워커 수명주기 (GPU_WORKER_MODE)
│   ├── llm_adapters.py         # OpenAI / HyperCLOVA / 로컬 LLM 어댑터
│   ├── library.py              # 공유 모델/데이터 라이브러리
│   ├── auth.py / user_store.py # 로그인·회원가입·사용자 저장
│   ├── security.py             # 로그 마스킹·입력 검증
│   ├── assets.py / plates.py   # 데스크테리어·플레이트 카탈로그
│   ├── cad.py / drawing_converter.py  # STEP·도면 변환
│   ├── schemas.py / errors.py / filenames.py
│   └── config.py               # 환경 변수 로딩
├── ui/                         # Streamlit UI 모듈 (api_client · sidebar · theme 등)
├── tools/                      # omni/SEED 서버 · ComfyUI 워크플로 · systemd · git-hooks
├── tests/                      # pytest (CI에서 ruff + pytest 실행)
├── data/
│   ├── desk_assets.json        # 데스크테리어 항목 정의
│   ├── layouts/                # layout_60/65/75/87/104.json
│   └── runtime/                # 세션·이미지 잡·users.json (gitignore)
└── training/                   # LoRA 학습 준비 (보류)
```

---

## 주요 API

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/health` | 헬스체크 |
| POST | `/auth/login` · `/auth/signup` · `/auth/logout` | 로그인 · 회원가입(초대코드) · 로그아웃 |
| GET | `/security/config` | API 키 설정/미설정 상태 (값 미노출) |
| GET | `/assets/desk` · `/assets/references` | 데스크테리어 · 참조 자산 카탈로그 |
| GET | `/layouts` | 키보드 레이아웃 목록 (60/65/75/87/104) |
| GET | `/plates` · `/plates/brands` · `/plates/{id}/preview` | 플레이트 검색 · 브랜드 · 미리보기 |
| GET · POST | `/models/library` · `/models/library/prepare` | 공유 모델 라이브러리 조회 · 준비 |
| POST | `/render/keyboard-preview` · `/render/desk-setup` | 키보드 / 데스크 셋업 GLB 생성 |
| POST | `/render/uploaded-model` · `/render/plate-drawing` | 업로드 모델 미리보기 · 플레이트 도면 |
| GET | `/ai/providers` | 사용 가능한 엔진/프로바이더 조회 |
| POST | `/ai/activate_track` | 생성 트랙(GPU 워커) 활성화 |
| POST | `/ai/copy` · `/ai/copy/experiment` · `/ai/copy/variants` | 광고 문구 생성 · 엔진 비교 · N개 변형 |
| POST | `/ai/image` | 광고 이미지 생성 (동기) |
| POST · GET | `/ai/image/jobs` · `/ai/image/jobs/{id}` | 비동기 이미지 잡 생성 · 폴링 · 목록 |
| POST · GET | `/ai/image/jobs/{id}/quality` | best-of-N 구도 평가 · 결과 |
| GET | `/ai/quality/summary` | 품질 게이트 요약 |
| POST | `/ai/poster` | 광고 문구 + 포스터 (SVG/PPTX) |

---

## STEP 파일 변환

`.env`의 `STEP_CONVERTER_CMD`를 설정하면 STEP/STP → GLB 변환을 지원합니다. 미설정 시 프록시 GLB를 자동 생성합니다.

```bash
# 옵션 A: trimesh (pip install trimesh[all])
STEP_CONVERTER_CMD=python -c "import trimesh,sys; s=trimesh.load(sys.argv[1]); s.export(sys.argv[2])" {input} {output}

# 옵션 B: Blender 헤드리스
STEP_CONVERTER_CMD=blender --background --python /opt/deskad/step_to_glb.py -- {input} {output}

# 옵션 C: FreeCADCmd (Ubuntu: sudo apt install freecad)
STEP_CONVERTER_CMD=FreeCADCmd ...
```

---

## LoRA 학습 준비

`training/README.md`를 확인하세요.

```bash
# 의존성 설치 (sprint_high 환경에 미설치 상태)
conda run -n sprint_high pip install diffusers accelerate peft safetensors transformers

# 데이터셋 준비
conda run -n sprint_high python training/prepare_desk_lora_dataset.py \
  --images-dir ./raw_images \
  --output-dir ./training/output/desk_lora \
  --commercial-use-checked
```
