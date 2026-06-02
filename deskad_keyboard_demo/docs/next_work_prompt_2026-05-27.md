# DeskAd AI Studio 이어가기 기록 및 프롬프트

작성일: 2026-05-27  
프로젝트 경로: `/home/leetaeho/ai_07_high/deskad_keyboard_demo`  
참고 노션: `https://www.notion.so/0297356fc5cb82faa40d01ba757f0aea`

## 1. 직전 작업 기록

이 문서는 `docs/project_handoff_2026-05-27.md` 이후 이어진 작업을 다음 대화에서 바로 복구하기 위한 기록이다.

### FastAPI 모델/파일 라이브러리 연결

- `backend/library.py`를 추가했다.
- FastAPI에 아래 엔드포인트를 추가했다.
  - `GET /assets/references`: 노션 기반 도면/레퍼런스 manifest 반환
  - `GET /models/library`: `static/models`, `static/uploads/reference_drawings`의 공용 파일 목록 반환
  - `POST /models/library/prepare`: 공용 GLB/STEP/STP를 model-viewer에서 볼 수 있도록 준비
  - `POST /ai/image`: 이미지 모델 endpoint 연결 상태와 프롬프트 확인용 API
- `streamlit_app.py` 2단계 도면/제품 데이터 영역에 `공용 모델/도면 라이브러리` expander를 추가했다.
- 공용 모델/데이터 기본 폴더는 아래 구조를 기준으로 사용한다.
  - 공용 모델: `/opt/shared_model`
  - 공용 데이터/도면/레퍼런스: `/opt/shared_data`
  - FastAPI mount: `/shared/models/*`, `/shared/data/*`
  - 앱에서 생성한 임시/결과 모델: `static/models`
  - 사용자가 업로드한 임시 파일: `static/uploads`

### 노션 도면/레퍼런스 다운로드

- `data/reference_assets.json` manifest를 추가했다.
- `tools/download_notion_references.py` 다운로드 스크립트를 추가했다.
- 노션 리서치 자료실에서 정리한 공개 자료 12개를 다운로드했다.
- 기본 다운로드 위치: `/opt/shared_data/reference_drawings`
- 저장된 주요 자료:
  - VESA mount SVG 2개
  - LCD monitor SVG
  - desk top-view / overhead workspace / clean desk setup / minimalist office desk 이미지
  - Acheron Tsuki, ArcticPCB, Austin 키보드 렌더/KLE 이미지
- Wikimedia 원본 대용량 이미지 중 일부는 429가 발생해 1280px thumbnail URL로 manifest를 조정했다.

### 키보드/데스크 렌더링 현실감 개선

`backend/renderer.py`에 절차적 GLB 디테일을 보강했다.

- 키보드 하우징:
  - case bevel highlight/shadow
  - side seam
  - screw recess
  - USB-C rear cutout
  - wood finish일 때 wood grain line
- 보강판/스위치:
  - plate rim visible between keycaps
  - show internals일 때 plate switch cutout shadow
  - brass/POM/FR4/carbon/polycarbonate plate material 유지
- 키캡:
  - skirt와 satin top을 분리
  - top highlight 추가
  - legend 유지
- 데스크/데스크테리어:
  - desk wood grain
  - cable grommet
  - desk legs
  - deskmat stitched edge/weave
  - monitor glass reflection, desktop UI band, webcam dot
  - keyboard/mouse/accessory contact shadow

### AI 프롬프트 개선

- `backend/ai.py`의 `build_image_prompt()`를 실사형 광고 이미지 생성에 맞게 강화했다.
- 프롬프트에 아래 요소를 포함하도록 했다.
  - photorealistic Korean e-commerce hero image
  - PBR material
  - woven deskmat, monitor glass reflections, soft contact shadows
  - keyboard housing bevels, plate visible between keycaps, satin PBT keycaps
  - selected reference asset path

### 실행 안정화

- `start.sh`의 백그라운드 실행을 `setsid nohup ... < /dev/null &`로 보강했다.
- 툴 세션 종료 후에도 FastAPI/Streamlit 프로세스가 유지되도록 조정했다.

## 2. 검증 기록

실행한 검증:

```bash
conda run -n sprint_high python -B -m py_compile \
  backend/main.py backend/renderer.py backend/ai.py \
  backend/assets.py backend/cad.py backend/config.py \
  backend/library.py streamlit_app.py tools/download_notion_references.py
```

FastAPI TestClient 검증:

- `/health`: 200
- `/assets/references`: 12개 중 12개 downloaded
- `/models/library`: OK
- `/render/desk-setup`: 200
- `/models/library/prepare`: 200
- `/ai/image`: 200

HTTP 확인:

- FastAPI local health: 200
- Streamlit local: 200
- 실행 URL: `http://34.27.86.182:8501`

주의:

- `/opt/shared_data`, `/opt/shared_model`은 git workspace 밖의 공용 저장소로 사용한다.
- `static/uploads/`는 legacy/임시 업로드용이며 `.gitignore` 대상이다.
- manifest와 다운로드 스크립트만 repo에 남겨 재현 가능하게 했다.
- `docs/project_handoff_2026-05-27.md`는 현재 untracked 상태로 남아 있다.

## 3. 참고 노션 핵심 요약

노션 벤치마킹 리서치의 다음 개발 방향:

- 메인 이미지 생성 모델: `FLUX.1 schnell`
  - Apache 2.0
  - L4 24GB에서 FP8/GGUF Q8 후보
  - 4-step 빠른 추론
- 한국어 카피 모델:
  - HyperCLOVA X 주력 후보
  - wrtn/뤼튼 보조 후보
  - 현재 앱 구조는 OpenAI-compatible chat completions와 `LOCAL_LLM_BASE_URL`을 우선 지원
- 제품 보존/실사화:
  - Canny + Depth multi ControlNet
  - 점주별 LoRA
  - BrushNet/PowerPaint 인페인팅
  - IC-Light 라이팅 변주
  - Tile ControlNet 업스케일
- 배포 구조:
  - ComfyUI worker + FastAPI gateway
  - GPU worker와 API gateway 분리
  - 모델 가중치는 이미지에 포함하지 않고 HF cache/볼륨 사용
- 최적화:
  - GGUF Q8_0 또는 FP8
  - VAE tiling
  - xFormers
  - OOM 시 fallback/queue 재시도
- 키보드 디테일:
  - switch stem/housing visual cues
  - gasket/o-ring/top/tray mount 시각 단서
  - keycap profile, legend, material fidelity
  - Canny IoU, OCR confidence, CLIP-I 등 자동 평가 게이트

## 4. 다음 작업 우선순위

1. 로컬 언어모델 연결 강화
   - `LOCAL_LLM_BASE_URL` OpenAI-compatible 서버 기준으로 이미 동작한다.
   - 다음 작업은 provider adapter를 분리해 HyperCLOVA X, OpenAI-compatible local model, fallback copy를 명확히 관리한다.
   - 카피 검수 사전과 채널별 금칙어/표현 정책을 `backend/ai.py` 또는 별도 `copy_policy.py`로 분리한다.

2. 이미지 모델/ComfyUI worker 연결
   - 현재 `LOCAL_IMAGE_ENDPOINT`는 단일 JSON endpoint만 가정한다.
   - 다음 작업은 ComfyUI workflow JSON 생성기와 queue/poll API adapter를 추가한다.
   - FastAPI에는 `/ai/image/jobs`, `/ai/image/jobs/{id}` 같은 job 기반 API를 고려한다.

3. 양자화/VRAM 최적화 설정
   - `.env.example`에 이미지 모델 최적화 변수를 추가한다.
   - 예: `IMAGE_MODEL_BACKEND`, `COMFYUI_BASE_URL`, `FLUX_MODEL_VARIANT`, `IMAGE_QUANTIZATION`, `ENABLE_VAE_TILING`, `ENABLE_XFORMERS`.
   - 실제 모델명/라이선스/설치법은 작업 시점에 공식 문서와 Hugging Face card를 반드시 재확인한다.

4. 키보드 상세 렌더링 추가
   - mount type 옵션 추가: `top_mount`, `tray_mount`, `gasket_mount`, `o_ring_mount`
   - keycap profile 옵션 추가: `cherry`, `oem`, `xda`, `sa`, `mda`
   - switch family 옵션 추가: `mx`, `box`, `holy_panda`, `topre`
   - Streamlit UI, Pydantic schema, renderer metadata, prompt 모두 함께 연결한다.

5. 자동 품질 평가 gate 초안
   - 가벼운 MVP부터 시작한다.
   - image endpoint 결과가 있을 때 Canny IoU/OCR/해상도/워터마크 여부를 저장할 수 있는 schema를 먼저 만든다.
   - 무거운 CLIP/LPIPS/FID는 dependency와 GPU 비용을 확인한 뒤 별도 worker로 분리한다.

## 5. 새 대화창 시작 프롬프트

아래 프롬프트를 새 대화창에 그대로 붙여 넣으면 된다.

```text
이 프로젝트는 `/home/leetaeho/ai_07_high/deskad_keyboard_demo`에 있는 DeskAd AI Studio입니다.
목표는 커스텀 키보드/데스크테리어 소상공인이 실물 촬영 없이 3D 셋업 미리보기와 광고 문구/포스터/실사 광고 이미지를 만들 수 있게 하는 서비스입니다.

현재 환경:
- GCP VM + PyCharm Remote/SSH
- conda env: `sprint_high`
- FastAPI port: 8010
- Streamlit port: 8501
- 외부 접속: `http://34.27.86.182:8501`
- JupyterHub가 8000 포트를 사용하므로 앱은 8000을 쓰면 안 됩니다.

중요 규칙:
- 실제 `.env`와 API/GitHub/HF 토큰 값을 출력하거나 커밋하지 마세요.
- `.env.example`에는 빈 템플릿만 유지하세요.
- 사용자나 팀원이 만든 변경을 임의로 되돌리지 마세요.
- 공용 모델은 `/opt/shared_model`, 공용 데이터/도면/이미지는 `/opt/shared_data` 아래에 둡니다. 커밋 대상은 manifest와 스크립트 위주입니다.
- 모델/라이브러리 버전, 라이선스, 설치 방법은 작업 시점에 공식 문서 또는 모델 카드로 반드시 재확인하세요.


공용 저장소 규칙:
- `DESKAD_SHARED_MODEL_DIR=/opt/shared_model`
- `DESKAD_SHARED_DATA_DIR=/opt/shared_data`
- FastAPI는 `/shared/models/*`, `/shared/data/*`로 두 폴더를 서빙합니다.
- `/models/library`는 `static/models`, legacy `static/uploads/reference_drawings`, `/opt/shared_model`, `/opt/shared_data`를 함께 스캔합니다.
- `/models/library/prepare`는 `models/...`, `shared/models/...`, `shared/data/...` 경로를 받을 수 있습니다.

현재 워킹트리 참고:
- `docs/project_handoff_2026-05-27.md`는 이전 대화에서 받은 handoff 문서이며 untracked일 수 있습니다.
- 직전 작업 기록은 `docs/next_work_prompt_2026-05-27.md`에 남아 있습니다.
- 변경된 주요 파일:
  - `backend/main.py`
  - `backend/library.py`
  - `backend/renderer.py`
  - `backend/ai.py`
  - `streamlit_app.py`
  - `start.sh`
  - `data/reference_assets.json`
  - `tools/download_notion_references.py`
  - `.env.example`

직전 완료 작업:
1. FastAPI에 공용 모델/도면 라이브러리 연결 API를 추가했습니다.
   - `GET /assets/references`
   - `GET /models/library`
   - `POST /models/library/prepare`
   - `POST /ai/image`
2. 노션 리서치 자료 기반 공개 레퍼런스 12개를 manifest로 정리하고 다운로드했습니다.
   - manifest: `data/reference_assets.json`
   - download script: `tools/download_notion_references.py`
   - 기본 다운로드 위치: `/opt/shared_data/reference_drawings`
3. 절차적 GLB 렌더러를 개선했습니다.
   - 하우징 bevel/seam/screw/USB cutout
   - plate rim / switch cutout shadow
   - keycap skirt/top/highlight
   - desk wood grain / cable grommet / legs
   - deskmat stitch/weave
   - monitor glass reflection / UI details / contact shadow
4. 이미지 생성 프롬프트를 실사형/PBR/데스크테리어 광고 톤으로 강화했습니다.
5. `start.sh`를 `setsid nohup` 방식으로 보강해 서버 프로세스 유지성을 개선했습니다.

최근 검증:
- `py_compile` 통과
- FastAPI TestClient 통과:
  - `/health`
  - `/assets/references`
  - `/models/library`
  - `/render/desk-setup`
  - `/models/library/prepare`
  - `/ai/image`
- `git diff --check` 통과
- `bash start.sh --restart` 후 FastAPI/Streamlit 200 확인

참고 노션:
- 벤치마킹 리서치: `https://www.notion.so/0297356fc5cb82faa40d01ba757f0aea`
- 노션의 핵심 방향:
  - 메인 이미지 모델: FLUX.1 schnell 후보
  - 한국어 카피 모델: HyperCLOVA X 주력, wrtn 보조 후보
  - 제품 보존: Canny + Depth multi ControlNet + 점주별 LoRA + BrushNet/PowerPaint
  - 배포: ComfyUI worker + FastAPI gateway
  - 최적화: GGUF Q8 또는 FP8, VAE tiling, xFormers
  - 키보드 상세: switch visual cues, mount type, keycap profile, OCR/Canny/CLIP 기반 평가

다음 작업을 이어서 해주세요.

우선순위:
1. 현재 브랜치와 워킹트리를 `git status --short --branch`로 확인합니다.
2. 기존 변경을 되돌리지 말고, 현재 변경 위에 이어서 작업합니다.
3. 로컬 언어모델 연결을 확장합니다.
   - 현재 `LOCAL_LLM_BASE_URL` OpenAI-compatible chat completions는 동작합니다.
   - provider adapter를 분리해 OpenAI-compatible local model, HyperCLOVA X 후보, fallback copy를 관리할 수 있게 합니다.
   - 채널별 카피 검수 사전/금칙어 정책을 추가합니다.
4. 이미지 모델 연결을 확장합니다.
   - 현재 `LOCAL_IMAGE_ENDPOINT`는 단일 JSON endpoint입니다.
   - ComfyUI worker adapter를 추가하고, 가능하면 job 기반 API(`/ai/image/jobs`) 구조를 설계/구현합니다.
   - FLUX.1 schnell + ControlNet을 염두에 두되, 실제 모델명/라이선스/설치 방법은 반드시 최신 공식 문서/모델 카드로 확인합니다.
5. 양자화/VRAM 최적화 설정을 추가합니다.
   - `.env.example`에 `IMAGE_MODEL_BACKEND`, `COMFYUI_BASE_URL`, `FLUX_MODEL_VARIANT`, `IMAGE_QUANTIZATION`, `ENABLE_VAE_TILING`, `ENABLE_XFORMERS` 같은 빈 설정을 추가합니다.
   - 실제 추론 코드는 모델이 없을 때도 fallback으로 깨지지 않아야 합니다.
6. 키보드 상세 렌더링을 더 확장합니다.
   - mount type: `top_mount`, `tray_mount`, `gasket_mount`, `o_ring_mount`
   - keycap profile: `cherry`, `oem`, `xda`, `sa`, `mda`
   - switch family: `mx`, `box`, `holy_panda`, `topre`
   - FastAPI schema, Streamlit UI, renderer metadata, image prompt에 모두 연결합니다.
7. 작업 후 검증합니다.
   - `conda run -n sprint_high python -B -m py_compile ...`
   - FastAPI TestClient로 `/health`, `/assets/references`, `/models/library`, `/render/desk-setup`, `/ai/image` 확인
   - `git diff --check`
   - 필요하면 `bash start.sh --restart` 후 `http://34.27.86.182:8501` 접속 가능 상태 확인

결과 보고 시:
- 변경 파일
- 새 API/환경변수
- 검증 결과
- 아직 실제 모델이 연결되지 않아 fallback으로 남은 부분
을 짧게 정리해 주세요.
```

