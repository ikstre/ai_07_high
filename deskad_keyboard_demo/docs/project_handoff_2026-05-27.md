# DeskAd AI Studio 인수인계 문서

작성일: 2026-05-27
프로젝트 경로: `/home/leetaeho/ai_07_high/deskad_keyboard_demo`
현재 작업 브랜치: `taeho`

## 1. 새 대화창 시작 프롬프트

새 대화창에서 이어서 작업할 때 아래 내용을 먼저 전달하면 된다.

```text
이 프로젝트는 `/home/leetaeho/ai_07_high/deskad_keyboard_demo`에 있는 DeskAd AI Studio입니다.
목표는 커스텀 키보드/데스크테리어 소상공인이 실물 촬영 없이 3D 셋업 미리보기와 광고 문구/포스터를 만들 수 있는 서비스입니다.

현재 환경:
- GCP VM + PyCharm Remote/SSH
- conda env: sprint_high
- FastAPI port: 8010
- Streamlit port: 8501
- 외부 접속: http://34.27.86.182:8501
- JupyterHub가 8000 포트를 사용하므로 앱은 8000을 쓰면 안 됩니다.

중요 규칙:
- 실제 `.env`와 API/GitHub 토큰 값을 출력하거나 커밋하지 마세요.
- GitHub push/PR 작업은 `deskad_keyboard_demo/.env`의 `GITHUB_TOKEN`을 값 출력 없이 사용하세요.
- `.env.example`에는 빈 템플릿만 유지하세요.
- 사용자나 팀원이 만든 변경을 임의로 되돌리지 마세요.

Git 상태:
- `main`에는 PR #2가 merge되어 있습니다.
- PR #3이 열려 있습니다: https://github.com/ikstre/ai_07_high/pull/3
- PR #3은 `main` merge 과정에서 재삽입된 중복 코드/깨진 JSON을 제거하는 cleanup PR입니다.
- 현재 `taeho` 브랜치 최신 커밋은 `7c2487b fix: remove duplicated merge artifacts`입니다.

우선 해야 할 일:
1. `git status --short --branch`로 현재 브랜치와 워킹트리를 확인하세요.
2. PR #3이 merge되었는지 확인하세요.
3. PR #3이 merge되지 않았다면 코드 변경보다 먼저 PR #3 리뷰/merge 상태를 기준으로 진행하세요.
4. 작업 전에는 `origin/main`과 `origin/taeho`를 fetch해서 최신 상태를 확인하세요.
5. 중복 정의, 깨진 JSON, 렌더링/포스터 API가 정상인지 검증한 뒤 다음 기능 개발을 이어가세요.

최근 검증:
- Python scoped duplicate check: 중복 함수/클래스 정의 없음
- `desk_assets.json`: 22개 에셋, 중복 id 없음, 중복 JSON key 없음
- `py_compile`: backend/main.py, renderer.py, ai.py, assets.py, cad.py, config.py, streamlit_app.py 통과
- FastAPI TestClient: /health, /assets/desk, /viewer, /render/desk-setup, /ai/poster 통과
- `git diff --check` 통과
```

## 2. 프로젝트 개요

DeskAd AI Studio는 생성형 AI를 활용해 소상공인이 광고 콘텐츠를 손쉽게 제작하도록 돕는 서비스다.

1차 타깃:

- 커스텀 키보드 샵 운영자
- 데스크테리어 / 데스크셋업 용품 판매자
- 가구·소품 판매 소상공인
- 디자인/마케팅 인력과 예산이 부족한 1인 사업자

핵심 컨셉:

- 점주가 키보드와 데스크테리어 제품을 가상 책상 위에 배치한다.
- 3D 셋업 미리보기로 제품 조합과 배치를 확인한다.
- 셋업 정보를 바탕으로 광고 문구와 SVG 포스터를 자동 생성한다.
- 향후 FLUX/SDXL/ControlNet/LoRA 기반 이미지 생성으로 고도화한다.

## 3. 현재 구현 기능

Streamlit 앱은 4단계 흐름이다.

1. 상품 정보 입력
   - 상품명, 유형, 가격, 판매 채널, 타깃 고객, 핵심 특징 입력

2. 도면/제품 데이터
   - 60% / 65% / 75% 키보드 배열 선택
   - STEP/STP/GLB 업로드
   - 데스크테리어 에셋 선택
   - 키보드 케이스, PCB, 보강판, 스위치, 키캡 관련 커스텀 옵션 선택

3. 가상 셋업
   - 책상 크기 선택
   - 모니터 크기 24/27/32인치 선택
   - 모니터암 스타일 선택
   - 색상/테마 선택
   - 3D 데스크 셋업 GLB 생성 및 model-viewer iframe 표시

4. 광고 콘텐츠
   - 광고 톤 선택
   - 이미지 비율 선택
   - 추가 요청 입력
   - 광고 카피 생성
   - SVG 포스터 템플릿 생성

## 4. 기술 스택과 실행 환경

환경:

- GCP VM
- conda env: `sprint_high`
- backend: FastAPI
- frontend: Streamlit
- viewer: `@google/model-viewer@4.0.0`
- 3D output: GLB
- config: `.env` + `.env.example`

포트:

- `8010`: FastAPI
- `8501`: Streamlit
- `8000`: JupyterHub 전용, 앱에서 사용 금지

실행:

```bash
cd /home/leetaeho/ai_07_high/deskad_keyboard_demo
bash start.sh --restart
```

수동 실행:

```bash
conda run -n sprint_high python -m uvicorn backend.main:app --host 0.0.0.0 --port 8010
conda run -n sprint_high python -m streamlit run streamlit_app.py --server.port 8501 --server.address 0.0.0.0
```

## 5. 주요 파일

```text
deskad_keyboard_demo/
  streamlit_app.py
  start.sh
  .env.example
  backend/
    main.py
    renderer.py
    ai.py
    assets.py
    cad.py
    config.py
  data/
    desk_assets.json
    layouts/
      layout_60.json
      layout_65.json
      layout_75.json
  training/
    README.md
    prepare_desk_lora_dataset.py
    train_flux_lora.sh
  docs/
    changes_2026-05-25.md
    project_handoff_2026-05-25.md
    project_handoff_2026-05-27.md
```

파일별 역할:

- `streamlit_app.py`: 전체 UI, 단계별 입력, 3D iframe, 광고 결과 표시
- `backend/main.py`: FastAPI 엔드포인트와 요청 스키마
- `backend/renderer.py`: 절차적 GLB 렌더러
- `backend/ai.py`: 광고 카피 생성, 로컬 이미지 참조, SVG 포스터 저장
- `backend/assets.py`: 데스크 에셋 로드
- `backend/cad.py`: STEP/STP/GLB 업로드 처리
- `backend/config.py`: `.env` 로딩과 설정 마스킹
- `data/desk_assets.json`: 데스크테리어 에셋 카탈로그
- `training/`: 향후 FLUX/LoRA 학습 데이터셋 준비용

## 6. 렌더링 기준

현재 렌더링은 실제 외부 GLB 에셋 병합이 아니라 `renderer.py`의 절차적 GLB 생성 방식이다.

기준:

- `1 GLB unit = 1 cm`
- MX 키보드 `1u = 1.905 cm`
- 책상/모니터/키보드 크기는 실측 기준에 맞춰 조정

키보드:

- 60%: 약 `28.6 x 9.5 cm`, 61키
- 65%: 약 `30.5 x 9.5 cm`, 67키
- 75%: 약 `30.5 x 11.4 cm`, 84키

모니터:

- 24인치: `56 x 33 cm`
- 27인치: `62 x 36 cm`
- 32인치: `74 x 43 cm`

책상:

- 기본: `120 x 60 cm`
- 프리셋: `120x60`, `120x80`, `140x70`, `160x80`, `180x80`
- 직접 입력: 폭 `100~200 cm`, 깊이 `50~90 cm`

## 7. 데스크테리어 에셋

현재 `data/desk_assets.json` 기준 에셋은 22개다.

- mouse
- monitor
- monitor_arm
- monitor_light_bar
- desk_lamp
- plant
- speakers
- desk_shelf
- notebook
- headphone_stand
- phone_stand
- keycap_tray
- coffee_mug
- digital_clock
- aroma_diffuser
- wireless_charger
- pen_holder
- book_stack
- humidifier
- photo_frame
- usb_hub
- mouse_pad_round

각 에셋에는 가능한 경우 아래 필드를 둔다.

- `id`
- `label`
- `category`
- `enabled_by_default`
- `rendering`
- `source`
- `license`
- `notes`
- `dimensions_cm`
- `external_candidates`

주의:

- `external_candidates`는 후보 링크일 뿐 실제 번들링된 에셋이 아니다.
- 외부 GLB를 포함하기 전에는 CC0/CC-BY/상업 사용 여부와 출처 표기를 반드시 확인해야 한다.

## 8. AI/광고 생성 흐름

카피 생성:

- `AI_PROVIDER=auto`
- `OPENAI_API_KEY`가 있으면 OpenAI-compatible chat completions 사용
- `LOCAL_LLM_BASE_URL`이 있으면 로컬 OpenAI-compatible LLM 사용
- 둘 다 없으면 fallback copy 사용

포스터 생성:

- SVG 템플릿 기반
- 템플릿:
  - `minimal_card`
  - `grid_three`
  - `feature_focus`
  - `promo_banner`
- `LOCAL_IMAGE_ENDPOINT`가 있으면 로컬 이미지 모델 결과를 포스터에 합성 가능
- 현재 기본 상태에서는 SVG fallback 일러스트 기반으로 동작

## 9. 환경변수와 보안

실제 `.env`는 커밋 금지다.

`.env.example`에는 빈 템플릿만 둔다.

주요 환경변수:

```text
DESKAD_API_BASE
DESKAD_PUBLIC_API_BASE
AI_PROVIDER
OPENAI_API_KEY
OPENAI_BASE_URL
OPENAI_TEXT_MODEL
OPENAI_IMAGE_MODEL
LOCAL_LLM_BASE_URL
LOCAL_LLM_MODEL
LOCAL_IMAGE_ENDPOINT
AI_REQUEST_TIMEOUT_SECONDS
MAX_UPLOAD_MB
STEP_CONVERTER_CMD
STEP_CONVERTER_TIMEOUT_SECONDS
GITHUB_TOKEN
```

GitHub 작업:

- `.env`의 `GITHUB_TOKEN`을 사용한다.
- 토큰 값은 출력하지 않는다.
- `gh` CLI가 없어도 Python `urllib` 또는 git askpass 방식으로 push/PR 생성이 가능하다.
- 이전에 remote URL에 토큰이 포함된 적이 있어, 현재는 `https://github.com/ikstre/ai_07_high.git` 형태로 정리했다.

## 10. Git / PR 상태

현재 로컬 상태 확인 기준:

```text
branch: taeho
HEAD: 7c2487b fix: remove duplicated merge artifacts
origin/taeho: 7c2487b
origin/main: b178ced Merge pull request #2 from ikstre/taeho
```

중요 PR:

- PR #2: `DeskAd 렌더링 워크플로우 및 광고 생성 기능 개선`
  - URL: `https://github.com/ikstre/ai_07_high/pull/2`
  - 상태: main에 merge됨

- PR #3: `중복 merge 산출물 제거 및 최신 main 정리`
  - URL: `https://github.com/ikstre/ai_07_high/pull/3`
  - 상태: 2026-05-27 기준 생성 완료. merge 여부는 새 대화에서 다시 확인 필요
  - 목적: PR #2 merge 이후 main에 남은 중복 코드/깨진 JSON 제거

PR #3 cleanup 내용:

- `backend/main.py`: 중복 `DeskSetupRenderRequest`, `AdContentRequest`, `UploadedModelRequest`, helper 정의 제거
- `backend/renderer.py`: merge 과정에서 섞인 중복 렌더링 블록 제거
- `data/desk_assets.json`: 깨진/중복 monitor 항목 제거
- `backend/ai.py`: 재삽입된 중복 블록 제거
- `streamlit_app.py`: 재삽입된 중복 블록 제거

PR #3 diff:

```text
5 files changed, 524 deletions
```

## 11. 최근 검증 결과

PR #3 작성 전후로 확인한 내용:

- Python AST scoped duplicate check: 중복 함수/클래스 정의 없음
- `desk_assets.json`: JSON 유효
- `desk_assets.json`: 22개 에셋
- `desk_assets.json`: 중복 id 없음
- `desk_assets.json`: 중복 JSON key 없음
- `git diff --check`: 통과
- `py_compile`: 통과
- FastAPI TestClient:
  - `/health`: OK
  - `/assets/desk`: 22 assets, default 5
  - `/viewer`: model-viewer 4.0.0 / ACES tone mapping 확인
  - `/render/desk-setup`: 160x80 desk, 32인치 모니터, brass plate, silent_red switch 반영
  - `/ai/poster`: `feature_focus`, `spec_bullets` 3개 반환

검증 명령 예시:

```bash
cd /home/leetaeho/ai_07_high/deskad_keyboard_demo

conda run -n sprint_high python -B -m py_compile \
  backend/main.py backend/renderer.py backend/ai.py \
  backend/assets.py backend/cad.py backend/config.py streamlit_app.py
```

## 12. Notion에서 확인한 프로젝트 관리 정보

노션 상위 페이지:

- `코드잇 모델 배포 프로젝트 - 1팀`
- URL: `https://www.notion.so/3027356fc5cb83678f02814f16fa9479`

확인한 하위 페이지:

- 프로젝트 개요
- 역할 분담
- Daily 회의록
- Day 1~3 회의록
- 리서치 자료실
- 벤치마킹 리서치
- 산출물 / 결과물

노션 기준 핵심 의사결정:

- 3D 포맷은 STEP 중심으로 통일
- 실측 단위는 cm 기준으로 통일
- GCP VM + L4 GPU 1장 환경
- Streamlit 기반 MVP, 필요 시 대안 프레임워크 검토
- 모델은 경량화와 상업 사용 가능성을 우선 고려
- 도면/3D 자료는 라이선스 검토가 필수
- 벤치마킹 핵심:
  - 오늘의집/Houzz: 2D/3D 셋업 빌더 UX
  - InteriorAI/Collov: 구조 보존형 AI 리렌더링
  - Photoroom: 결과 5종 변주
  - Canva Magic Switch: 규격 자동 변환
  - 카페24 에디봇: 한국형 상세페이지 레이아웃

## 13. 현재 한계

- 현재 3D는 절차적 primitive 기반이다.
- 외부 GLB 에셋 병합은 아직 미구현이다.
- STEP 변환기는 `STEP_CONVERTER_CMD`가 없으면 프록시 GLB fallback으로 동작한다.
- 실제 FLUX/SDXL/ControlNet 이미지 worker는 완전 연결 전이다.
- Playwright/Chromium이 VM에 설치되어 있지 않아 브라우저 자동 회귀 테스트는 미수행이다.
- main에는 PR #3 merge 전까지 중복 merge 산출물 문제가 남아 있을 수 있다.

## 14. 다음 작업 제안

우선순위:

1. PR #3 merge 여부 확인
2. merge 후 `origin/main` 기준으로 로컬 `main`, `taeho` 정리
3. 앱 재실행 및 HTTP 200 확인
4. 데스크테리어 에셋 실제 GLB 후보 선정
5. 라이선스 manifest 작성
6. STEP -> GLB 변환기 연결
7. 로컬 이미지 모델 endpoint 연결
8. PPT/보고서용 스크린샷과 데모 시나리오 정리

추천 다음 검증:

```bash
git status --short --branch
git fetch --prune origin
git log -4 --oneline --decorate
git diff --stat origin/main..origin/taeho
```

앱 실행:

```bash
cd /home/leetaeho/ai_07_high/deskad_keyboard_demo
bash start.sh --restart
```

접속:

```text
http://34.27.86.182:8501
```

## 15. 발표/PPT 작성 참고

PPT에 반드시 들어갈 흐름:

1. 문제 정의: 소상공인의 촬영/디자인/마케팅 비용 부담
2. 타깃: 커스텀 키보드/데스크테리어 판매자
3. 서비스 컨셉: 3D 셋업 -> 광고 문구/포스터 생성
4. 기술 구조: Streamlit + FastAPI + 절차적 GLB + AI copy/poster
5. 실측 렌더링: cm 기준, 키보드/모니터/책상 비율 보정
6. 에셋 카탈로그: 22개 데스크테리어 에셋
7. 보안: `.env` 기반 키 관리, 키 노출 방지
8. 검증 결과: API/컴파일/JSON/중복 검사
9. 협업: Notion 회의록, GitHub PR #2/#3
10. 한계와 고도화: 실제 GLB, STEP 변환, FLUX/ControlNet, Magic Switch

## 16. 2026-05-27 추가 작업 기록

이 섹션은 `docs/project_handoff_2026-05-27.md` 최초 작성 이후 같은 날 이어서 반영한 변경사항이다.

### 16-1. FastAPI 공용 모델/도면 라이브러리 연결

추가/변경 파일:

- `backend/library.py`
- `backend/main.py`
- `backend/config.py`
- `streamlit_app.py`
- `.env.example`
- `data/reference_assets.json`
- `tools/download_notion_references.py`

추가 API:

- `GET /assets/references`
  - `data/reference_assets.json` 기준 노션 도면/레퍼런스 manifest를 반환한다.
  - 현재 12개 레퍼런스가 등록되어 있고 `/opt/shared_data/reference_drawings`에 다운로드되어 있다.
- `GET /models/library`
  - 아래 폴더를 함께 스캔한다.
    - `static/models`
    - legacy `static/uploads/reference_drawings`
    - `/opt/shared_model`
    - `/opt/shared_data`
  - 응답에 `shared_data_dir`, `shared_model_dir`, 각 폴더 존재 여부를 포함한다.
- `POST /models/library/prepare`
  - `models/...`, `shared/models/...`, `shared/data/...` 경로의 GLB/STEP/STP 파일을 model-viewer용 모델로 준비한다.
  - GLB는 copy/pass-through, STEP/STP는 `STEP_CONVERTER_CMD`가 있으면 변환하고 없으면 proxy GLB fallback을 만든다.
- `POST /ai/image`
  - 이미지 모델 endpoint 연결 상태와 이미지 프롬프트 확인용 API다.
  - 실제 이미지 워커가 없으면 prompt/fallback 응답만 반환한다.

Streamlit 변경:

- 2단계 `도면/제품 데이터` 영역에 `공용 모델/도면 라이브러리` expander를 추가했다.
- 다운로드된 노션 레퍼런스와 FastAPI 미리보기 가능한 GLB/STEP/STP 공용 모델을 선택할 수 있다.
- `/opt/shared_data`, `/opt/shared_model` 존재 여부를 UI caption으로 보여준다.

### 16-2. 공용 저장소 규칙

앞으로 큰 모델/데이터 파일은 git workspace 안이 아니라 `/opt` 아래 공용 폴더에 둔다.

```text
공용 데이터/도면/레퍼런스: /opt/shared_data
공용 모델/가중치/GLB 후보: /opt/shared_model
노션 레퍼런스 기본 위치: /opt/shared_data/reference_drawings
FastAPI static mount: /shared/data/*, /shared/models/*
```

환경변수:

```text
DESKAD_SHARED_DATA_DIR=/opt/shared_data
DESKAD_SHARED_MODEL_DIR=/opt/shared_model
```

현재 상태:

- `/opt/shared_data/reference_drawings` 생성 완료
- `/opt/shared_model` 생성 완료
- 기존 노션 레퍼런스 12개를 `/opt/shared_data/reference_drawings`로 복사 완료
- `data/reference_assets.json`의 `download_root`를 `/opt/shared_data/reference_drawings`로 변경
- `tools/download_notion_references.py`는 manifest의 `storage` 값을 보고 `/opt/shared_data` 또는 `/opt/shared_model`에 저장한다.

주의:

- `/opt/shared_data`, `/opt/shared_model`의 실제 파일은 git 커밋 대상이 아니다.
- 커밋 대상은 manifest, 다운로드 스크립트, 코드 변경만 포함한다.
- legacy로 남아 있는 `static/uploads/reference_drawings`도 `/models/library`에서 읽지만, 신규 기본 저장 위치는 `/opt/shared_data/reference_drawings`다.

### 16-3. 노션 레퍼런스 다운로드

추가 manifest:

- `data/reference_assets.json`

추가 다운로드 스크립트:

- `tools/download_notion_references.py`

다운로드된 12개 레퍼런스:

- `vesa_mount_adapter.svg`
- `vesa_mounts_size_e.svg`
- `lcd_monitor.svg`
- `desk_top_view.jpg`
- `overhead_desktop_workspace.jpg`
- `clean_desk_setup.jpg`
- `minimalist_office_desk.jpg`
- `tsuki_top_render.png`
- `tsuki_kle_layout.png`
- `arcticpcb_top_render.png`
- `arcticpcb_kle_layout.png`
- `austin_kle_layout.png`

Wikimedia 일부 원본 대용량 이미지는 429가 발생해 manifest에서 1280px thumbnail URL로 조정했다.

### 16-4. 렌더링 현실감 개선

`backend/renderer.py`에 아래 디테일을 추가했다.

키보드:

- 하우징 bevel highlight/shadow
- side seam
- screw recess
- USB-C rear cutout
- wood finish grain
- plate rim visible between keycaps
- show internals일 때 plate switch cutout shadow
- keycap skirt / satin top / top highlight 분리

데스크/데스크테리어:

- desk wood grain
- cable grommet
- desk legs
- deskmat stitched edge / weave thread
- monitor glass reflection
- monitor desktop UI band / lower panel
- webcam dot
- keyboard / mouse / accessory contact shadow

AI 프롬프트:

- `backend/ai.py`의 `build_image_prompt()`를 실사형/PBR 광고 이미지에 맞게 강화했다.
- selected reference asset path를 프롬프트에 포함한다.
- 키보드 하우징 bevel, plate visibility, satin PBT keycaps, woven deskmat, monitor reflections, soft contact shadows를 명시한다.

### 16-5. 실행 안정화

`start.sh` 변경:

- FastAPI/Streamlit 백그라운드 실행을 `setsid nohup ... < /dev/null &` 방식으로 보강했다.
- 툴 세션 종료 후에도 서버 프로세스가 유지되도록 했다.

## 17. 최신 검증 결과

2026-05-27 추가 작업 후 확인한 내용:

```text
py_compile: 통과
git diff --check: 통과
FastAPI TestClient:
  /health: 200
  /assets/references: 12개 중 12개 downloaded
  /models/library: /opt/shared_data, /opt/shared_model 존재 확인
  /render/desk-setup: 200
  /models/library/prepare: 200
  /ai/image: 200
HTTP:
  /shared/data/reference_drawings/vesa_mount_adapter.svg: 200
  Streamlit: 200
```

실행 상태:

```text
FastAPI: http://127.0.0.1:8010
Streamlit: http://127.0.0.1:8501
외부 접속: http://34.27.86.182:8501
```

검증 명령 예시:

```bash
cd /home/leetaeho/ai_07_high/deskad_keyboard_demo

conda run -n sprint_high python -B -m py_compile \
  backend/main.py backend/renderer.py backend/ai.py \
  backend/assets.py backend/cad.py backend/config.py \
  backend/library.py streamlit_app.py tools/download_notion_references.py

conda run -n sprint_high python -c "from fastapi.testclient import TestClient; from backend.main import app; c=TestClient(app); print(c.get('/health').status_code); print(len(c.get('/assets/references').json()['references'])); print(c.get('/models/library').json()['shared'])"

git diff --check
```

## 18. 참고해야 할 노션 링크

프로젝트 관리:

- 코드잇 모델 배포 프로젝트 - 1팀
  - `https://www.notion.so/3027356fc5cb83678f02814f16fa9479`
- 프로젝트 개요
  - `https://www.notion.so/2e97356fc5cb8382902d816a508834a0`
- 역할 분담
  - `https://www.notion.so/4377356fc5cb83a496fb81d51c1ca028`
- Daily 회의록
  - `https://www.notion.so/cdb7356fc5cb837fb54b011dcffec45d`
- 리서치 자료실
  - `https://www.notion.so/1417356fc5cb82f98f62012a2647d44f`
- 산출물 / 결과물
  - `https://www.notion.so/0717356fc5cb82c39aaa8100d76eb07b`
- 벤치마킹 리서치
  - `https://www.notion.so/0297356fc5cb82faa40d01ba757f0aea`

특히 다음 작업에서는 `벤치마킹 리서치`를 우선 참고한다.

핵심 내용:

- 메인 이미지 모델 후보: `FLUX.1 schnell`
  - Apache 2.0
  - L4 24GB에서 FP8/GGUF Q8 후보
  - 빠른 4-step 추론
- 한국어 카피 모델 후보:
  - HyperCLOVA X 주력 후보
  - wrtn 보조 후보
  - 현재 앱은 OpenAI-compatible `LOCAL_LLM_BASE_URL` 구조를 우선 지원
- 제품 보존/실사화:
  - Canny + Depth multi ControlNet
  - 점주별 LoRA
  - BrushNet/PowerPaint 인페인팅
  - IC-Light 라이팅 변주
  - Tile ControlNet 업스케일
- 배포:
  - ComfyUI worker + FastAPI gateway
  - GPU worker와 API gateway 분리
  - 모델 가중치는 이미지에 포함하지 않고 HF cache/볼륨 사용
- 최적화:
  - GGUF Q8_0 또는 FP8
  - VAE tiling
  - xFormers
  - OOM fallback/queue 재시도
- 키보드 상세:
  - switch stem/housing visual cues
  - gasket/o-ring/top/tray mount 시각 단서
  - keycap profile, legend, material fidelity
  - Canny IoU, OCR confidence, CLIP-I 등 자동 평가 gate

## 19. 최신 다음 작업 제안

우선순위:

1. 현재 워킹트리 정리
   - `git status --short --branch`
   - 기존 변경을 되돌리지 말고 현재 변경 위에서 이어간다.
   - `docs/project_handoff_2026-05-27.md`, `docs/next_work_prompt_2026-05-27.md`는 untracked일 수 있다.

2. 로컬 언어모델 연결 확장
   - 현재 `LOCAL_LLM_BASE_URL` OpenAI-compatible chat completions는 지원한다.
   - provider adapter를 분리해 OpenAI-compatible local model, HyperCLOVA X 후보, fallback copy를 관리한다.
   - 채널별 카피 검수 사전/금칙어 정책을 추가한다.

3. 이미지 모델/ComfyUI worker 연결
   - 현재 `LOCAL_IMAGE_ENDPOINT`는 단일 JSON endpoint다.
   - ComfyUI workflow JSON 생성기와 queue/poll adapter를 추가한다.
   - 가능하면 job 기반 API를 설계한다.
     - `POST /ai/image/jobs`
     - `GET /ai/image/jobs/{job_id}`

4. 양자화/VRAM 최적화 설정
   - `.env.example`에 빈 설정을 추가한다.
     - `IMAGE_MODEL_BACKEND`
     - `COMFYUI_BASE_URL`
     - `FLUX_MODEL_VARIANT`
     - `IMAGE_QUANTIZATION`
     - `ENABLE_VAE_TILING`
     - `ENABLE_XFORMERS`
   - 실제 모델명/라이선스/설치법은 작업 시점에 공식 문서 또는 Hugging Face model card로 재확인한다.

5. 키보드 상세 렌더링 확장
   - mount type:
     - `top_mount`
     - `tray_mount`
     - `gasket_mount`
     - `o_ring_mount`
   - keycap profile:
     - `cherry`
     - `oem`
     - `xda`
     - `sa`
     - `mda`
   - switch family:
     - `mx`
     - `box`
     - `holy_panda`
     - `topre`
   - FastAPI schema, Streamlit UI, renderer metadata, image prompt를 함께 연결한다.

6. 자동 품질 평가 gate 초안
   - image endpoint 결과가 있을 때 해상도, OCR, Canny IoU, 워터마크 여부를 저장할 schema부터 만든다.
   - CLIP/LPIPS/FID는 dependency와 GPU 비용을 확인한 뒤 별도 worker로 분리한다.

## 20. 최신 새 대화창 시작 프롬프트

새 대화창에서 이어서 작업할 때 아래 내용을 전달하면 된다.

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
- 공용 모델은 `/opt/shared_model`, 공용 데이터/도면/이미지는 `/opt/shared_data` 아래에 둡니다.
- FastAPI는 `/shared/models/*`, `/shared/data/*`로 공용 폴더를 서빙합니다.
- 모델/라이브러리 버전, 라이선스, 설치 방법은 작업 시점에 공식 문서 또는 모델 카드로 반드시 재확인하세요.

현재 워킹트리 참고:
- `docs/project_handoff_2026-05-27.md`가 최신 인수인계 문서입니다.
- 추가 이어가기 기록은 `docs/next_work_prompt_2026-05-27.md`에도 있습니다.
- 변경된 주요 파일:
  - `.env.example`
  - `backend/main.py`
  - `backend/library.py`
  - `backend/config.py`
  - `backend/renderer.py`
  - `backend/ai.py`
  - `streamlit_app.py`
  - `start.sh`
  - `data/reference_assets.json`
  - `tools/download_notion_references.py`

직전 완료 작업:
1. FastAPI에 공용 모델/도면 라이브러리 연결 API를 추가했습니다.
   - `GET /assets/references`
   - `GET /models/library`
   - `POST /models/library/prepare`
   - `POST /ai/image`
2. 공용 저장소를 `/opt/shared_data`, `/opt/shared_model`로 반영했습니다.
   - `DESKAD_SHARED_DATA_DIR=/opt/shared_data`
   - `DESKAD_SHARED_MODEL_DIR=/opt/shared_model`
   - `/shared/data/*`, `/shared/models/*` mount
3. 노션 리서치 자료 기반 공개 레퍼런스 12개를 manifest로 정리하고 `/opt/shared_data/reference_drawings`에 다운로드했습니다.
4. 절차적 GLB 렌더러를 개선했습니다.
   - 하우징 bevel/seam/screw/USB cutout
   - plate rim / switch cutout shadow
   - keycap skirt/top/highlight
   - desk wood grain / cable grommet / legs
   - deskmat stitch/weave
   - monitor glass reflection / UI details / contact shadow
5. 이미지 생성 프롬프트를 실사형/PBR/데스크테리어 광고 톤으로 강화했습니다.
6. `start.sh`를 `setsid nohup` 방식으로 보강해 서버 프로세스 유지성을 개선했습니다.

최근 검증:
- `py_compile` 통과
- `git diff --check` 통과
- FastAPI TestClient 통과:
  - `/health`
  - `/assets/references`
  - `/models/library`
  - `/render/desk-setup`
  - `/models/library/prepare`
  - `/ai/image`
- HTTP 확인:
  - `/shared/data/reference_drawings/vesa_mount_adapter.svg`: 200
  - Streamlit: 200

참고 노션:
- 프로젝트 상위: `https://www.notion.so/3027356fc5cb83678f02814f16fa9479`
- 리서치 자료실: `https://www.notion.so/1417356fc5cb82f98f62012a2647d44f`
- 벤치마킹 리서치: `https://www.notion.so/0297356fc5cb82faa40d01ba757f0aea`
- 산출물 / 결과물: `https://www.notion.so/0717356fc5cb82c39aaa8100d76eb07b`

다음 작업을 이어서 해주세요.

우선순위:
1. `git status --short --branch`로 현재 브랜치와 워킹트리를 확인합니다.
2. 기존 변경을 되돌리지 말고 현재 변경 위에 이어서 작업합니다.
3. 로컬 언어모델 연결을 확장합니다.
   - provider adapter를 분리해 OpenAI-compatible local model, HyperCLOVA X 후보, fallback copy를 관리합니다.
   - 채널별 카피 검수 사전/금칙어 정책을 추가합니다.
4. 이미지 모델 연결을 확장합니다.
   - ComfyUI worker adapter를 추가하고 job 기반 API(`/ai/image/jobs`) 구조를 설계/구현합니다.
   - FLUX.1 schnell + ControlNet을 염두에 두되, 실제 모델명/라이선스/설치 방법은 반드시 최신 공식 문서/모델 카드로 확인합니다.
5. 양자화/VRAM 최적화 설정을 추가합니다.
   - `.env.example`에 `IMAGE_MODEL_BACKEND`, `COMFYUI_BASE_URL`, `FLUX_MODEL_VARIANT`, `IMAGE_QUANTIZATION`, `ENABLE_VAE_TILING`, `ENABLE_XFORMERS` 같은 빈 설정을 추가합니다.
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

## 21. 2026-05-28 추가 작업 기록

이 섹션은 2026-05-28에 이어서 반영한 최신 변경사항이다. 새 대화에서는 이 섹션과 아래 `22. 최신 이어가기 프롬프트`를 우선 기준으로 삼는다.

### 21-1. 한국어 LLM provider 확장

추가/변경 파일:

- `backend/llm_adapters.py`
- `backend/copy_policy.py`
- `backend/ai.py`
- `backend/config.py`
- `backend/main.py`
- `streamlit_app.py`
- `.env.example`
- `docs/korean_llm_experiments_2026-05-28.md`

추가 provider:

- `openai`
- `hyperclova`
- `kanana`
- `midm`
- `local`
- `fallback`

`AI_PROVIDER=auto`일 때 순서는 아래와 같다.

```text
openai -> hyperclova -> kanana -> midm -> local -> fallback
```

새 환경변수:

```text
HYPERCLOVA_BASE_URL=
HYPERCLOVA_API_KEY=
HYPERCLOVA_MODEL=
KANANA_BASE_URL=
KANANA_API_KEY=
KANANA_MODEL=
MIDM_BASE_URL=
MIDM_API_KEY=
MIDM_MODEL=
```

연결 방식:

- HyperCLOVA, Kanana, Mi:dm 모두 우선 OpenAI-compatible chat completions gateway를 바라보도록 설계했다.
- Kanana/Mi:dm은 vLLM, SGLang, Ollama, LM Studio 등으로 띄운 `/v1/chat/completions` 엔드포인트를 `KANANA_BASE_URL`, `MIDM_BASE_URL`에 넣으면 된다.
- 실제 모델 가중치와 HF/API 토큰은 repo가 아니라 `/opt/shared_model` 또는 HF cache와 `.env`에 둔다.

새 API:

- `GET /ai/providers`
  - provider 설정 상태, model 이름, auto 순서를 반환한다.
  - secret 값은 `set`/`missing`으로만 표시한다.
- `POST /ai/copy/experiment`
  - 같은 상품/광고 입력을 여러 provider로 비교한다.
  - 기본 비교 후보는 `kanana`, `midm`, `local`, `fallback`이다.

Streamlit 변경:

- 광고 콘텐츠 단계에 `한글 모델 비교` 버튼을 추가했다.
- OpenAI / Local / HyperCLOVA / Kanana / Mi:dm / 이미지 backend 설정 상태를 UI caption에 표시한다.
- 결과 패널에 `한글 모델 비교 결과` expander를 추가했다.

카피 정책:

- `backend/copy_policy.py`를 추가했다.
- 채널별 headline/subcopy/cta 길이와 hashtag 개수를 제한한다.
- `최저가`, `국내 1위`, `완벽한`, `100%` 같은 과장 가능 표현을 완화하거나 제거한다.

### 21-2. ComfyUI / 이미지 job -> 포스터 합성 연결

추가/변경 파일:

- `backend/ai.py`
- `backend/main.py`
- `streamlit_app.py`
- `.env.example`

이미지 backend 환경변수:

```text
IMAGE_MODEL_BACKEND=auto
LOCAL_IMAGE_ENDPOINT=
COMFYUI_BASE_URL=
COMFYUI_WORKFLOW_PATH=
FLUX_MODEL_VARIANT=
IMAGE_QUANTIZATION=
ENABLE_VAE_TILING=false
ENABLE_XFORMERS=false
```

새 API:

- `POST /ai/image/jobs`
  - 이미지 생성 작업을 만든다.
  - `LOCAL_IMAGE_ENDPOINT`가 있으면 동기 endpoint를 job 형태로 감싼다.
  - `COMFYUI_BASE_URL`과 `COMFYUI_WORKFLOW_PATH`가 있으면 ComfyUI `/prompt`에 queue한다.
  - 설정이 없으면 `not_configured` job으로 안전하게 반환한다.
- `GET /ai/image/jobs/{job_id}`
  - ComfyUI job이면 `/history/{prompt_id}`를 poll하고 완료 이미지 URL을 반환한다.
- `POST /ai/poster`
  - `image_job_id`를 받을 수 있다.
  - 완료된 local image job 또는 ComfyUI job 이미지가 있으면 SVG 포스터 hero 이미지로 합성한다.
  - job 결과가 없으면 기존 SVG fallback 또는 `LOCAL_IMAGE_ENDPOINT` fallback으로 동작한다.

ComfyUI workflow placeholder:

```text
{prompt}
{negative_prompt}
{width}
{height}
{seed}
{flux_model_variant}
{image_quantization}
```

주의:

- `COMFYUI_WORKFLOW_PATH`는 ComfyUI UI JSON이 아니라 API-format workflow JSON이어야 한다.
- 실제 FLUX/ControlNet workflow 파일은 아직 repo에 포함하지 않았다.
- 모델명, 라이선스, 설치법은 실행 시점의 공식 문서와 Hugging Face model card로 다시 확인해야 한다.

### 21-3. 키보드 상세 렌더링 확장 완료

기존 우선순위였던 아래 옵션을 FastAPI schema, Streamlit UI, renderer metadata, image prompt까지 연결했다.

- `mount_type`
  - `top_mount`
  - `tray_mount`
  - `gasket_mount`
  - `o_ring_mount`
- `keycap_profile`
  - `cherry`
  - `oem`
  - `xda`
  - `sa`
  - `mda`
- `switch_family`
  - `mx`
  - `box`
  - `holy_panda`
  - `topre`

렌더러 반영:

- mount cue: gasket strip, tray standoff, o-ring rail, top mount tab
- keycap profile별 높이/간격/top taper/row angle
- switch family별 housing/stem/detail shape

### 21-4. 최신 모델 후보 메모

2026-05-28 기준 확인한 방향:

- Kakao Kanana
  - Kakao는 Kanana 1.5 모델군을 Hugging Face에 공개했고 Apache 2.0 상업 사용 가능성을 공지했다.
  - Hugging Face Kakao org에는 Kanana-2 계열도 올라와 있으므로 실제 실험 전 개별 모델 카드의 license, context length, VRAM 요구량을 다시 확인한다.
- KT Mi:dm
  - `K-intelligence/Midm-2.0-Base-Instruct` 모델 카드는 MIT license와 vLLM/SGLang OpenAI-compatible 호출 예시를 제공한다.
  - L4 24GB 환경에서는 Mini 또는 양자화 변형부터 검토한다.

참고 URL:

```text
https://www.kakaocorp.com/page/detail/11654
https://huggingface.co/kakaocorp
https://huggingface.co/K-intelligence/Midm-2.0-Base-Instruct
```

### 21-5. 최신 검증 결과

검증 명령/결과:

- `py_compile` 통과
  - `backend/main.py`
  - `backend/renderer.py`
  - `backend/ai.py`
  - `backend/assets.py`
  - `backend/cad.py`
  - `backend/config.py`
  - `backend/library.py`
  - `backend/llm_adapters.py`
  - `backend/copy_policy.py`
  - `streamlit_app.py`
  - `tools/download_notion_references.py`
- FastAPI TestClient 통과
  - `/health`
  - `/ai/providers`
  - `/ai/copy/experiment`
  - `/ai/image/jobs`
  - `/ai/poster` with `image_job_id`
- 이전 TestClient 검증도 유지
  - `/assets/references`
  - `/models/library`
  - `/render/desk-setup`
  - `/models/library/prepare`
  - `/ai/image`
- `git diff --check` 통과
- `bash start.sh --restart` 후 HTTP 확인
  - FastAPI `/health`: 200
  - FastAPI `/ai/providers`: 200
  - Streamlit: 200

실행 URL:

```text
http://34.27.86.182:8501
```

### 21-6. 아직 남은 연결 작업

우선순위:

1. 실제 Kanana/Mi:dm 모델 서버 연결
   - vLLM 또는 SGLang으로 OpenAI-compatible endpoint를 띄운다.
   - `.env`에 `KANANA_BASE_URL`, `KANANA_MODEL`, `MIDM_BASE_URL`, `MIDM_MODEL`을 설정한다.
   - L4 24GB에서 full precision이 어려우면 Mini/GGUF/AWQ/GPTQ 등 양자화 후보를 먼저 검토한다.
2. HyperCLOVA 직접 API adapter 여부 결정
   - 현재는 OpenAI-compatible gateway 전제다.
   - Naver Cloud direct API를 쓸 경우 별도 adapter가 필요하다.
3. ComfyUI workflow JSON 작성
   - FLUX.1 schnell + ControlNet/Canny/Depth 후보 workflow를 API-format JSON으로 저장한다.
   - `COMFYUI_WORKFLOW_PATH`에 경로를 넣고 `/ai/image/jobs`로 queue/poll을 확인한다.
4. image job 영속화
   - 현재 `IMAGE_JOBS`는 프로세스 메모리 기반이다.
   - 서버 재시작 후에도 job 조회가 필요하면 sqlite/jsonl 기반 job store로 분리한다.
5. 자동 품질 평가 gate
   - 해상도, 워터마크, OCR, Canny IoU 저장 schema부터 추가한다.
   - CLIP/LPIPS/FID는 GPU 비용을 확인한 뒤 worker로 분리한다.

## 22. 2026-05-28 최신 새 대화창 시작 프롬프트

새 대화창에서 이어서 작업할 때는 아래 내용을 전달하면 된다.

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
- 공용 모델은 `/opt/shared_model`, 공용 데이터/도면/이미지는 `/opt/shared_data` 아래에 둡니다.
- 모델/라이브러리 버전, 라이선스, 설치 방법은 작업 시점에 공식 문서 또는 모델 카드로 반드시 재확인하세요.

현재 브랜치/상태:
- branch: `taeho`
- PR #3은 `origin/main`에 merge됨: merge commit `8c6b394`
- 로컬 `taeho`는 `origin/main` 기준 fast-forward 후 새 작업이 워킹트리에 있습니다.
- `docs/project_handoff_2026-05-27.md`의 `21. 2026-05-28 추가 작업 기록`과 `22. 2026-05-28 최신 새 대화창 시작 프롬프트`가 최신 기준입니다.

최근 완료 작업:
1. 공용 모델/도면 라이브러리 API 연결
   - `GET /assets/references`
   - `GET /models/library`
   - `POST /models/library/prepare`
2. 한국어 LLM provider 확장
   - `openai`, `hyperclova`, `kanana`, `midm`, `local`, `fallback`
   - `GET /ai/providers`
   - `POST /ai/copy/experiment`
   - `backend/llm_adapters.py`, `backend/copy_policy.py` 추가
3. 이미지 job API 추가
   - `POST /ai/image/jobs`
   - `GET /ai/image/jobs/{job_id}`
   - `/ai/poster`가 `image_job_id`를 받아 완료된 이미지 job 결과를 SVG 포스터에 합성 가능
4. 키보드 상세 렌더링 연결 완료
   - mount type: `top_mount`, `tray_mount`, `gasket_mount`, `o_ring_mount`
   - keycap profile: `cherry`, `oem`, `xda`, `sa`, `mda`
   - switch family: `mx`, `box`, `holy_panda`, `topre`
5. Streamlit UI 업데이트
   - `한글 모델 비교` 버튼
   - 실사 이미지 작업 상태 표시
   - 완료된 image job을 다음 포스터 생성에 자동 합성 후보로 사용

새 환경변수:
- `HYPERCLOVA_BASE_URL`, `HYPERCLOVA_API_KEY`, `HYPERCLOVA_MODEL`
- `KANANA_BASE_URL`, `KANANA_API_KEY`, `KANANA_MODEL`
- `MIDM_BASE_URL`, `MIDM_API_KEY`, `MIDM_MODEL`
- `IMAGE_MODEL_BACKEND`, `LOCAL_IMAGE_ENDPOINT`, `COMFYUI_BASE_URL`, `COMFYUI_WORKFLOW_PATH`
- `FLUX_MODEL_VARIANT`, `IMAGE_QUANTIZATION`, `ENABLE_VAE_TILING`, `ENABLE_XFORMERS`

최근 검증:
- `py_compile` 통과
- FastAPI TestClient 통과:
  - `/health`
  - `/ai/providers`
  - `/ai/copy/experiment`
  - `/ai/image/jobs`
  - `/ai/poster` with `image_job_id`
  - `/assets/references`
  - `/models/library`
  - `/render/desk-setup`
  - `/models/library/prepare`
  - `/ai/image`
- `git diff --check` 통과
- `bash start.sh --restart` 후 FastAPI `/health` 200, `/ai/providers` 200, Streamlit 200

다음 우선순위:
1. 실제 Kanana/Mi:dm 모델 서버를 vLLM/SGLang/Ollama/LM Studio 중 하나로 띄우고 OpenAI-compatible endpoint 연결
2. HyperCLOVA direct API를 쓸지, OpenAI-compatible gateway만 유지할지 결정
3. FLUX.1 schnell + ControlNet 기반 ComfyUI API-format workflow JSON 작성
4. `COMFYUI_WORKFLOW_PATH` 연결 후 `/ai/image/jobs` queue/poll과 `/ai/poster` 합성 검증
5. image job을 메모리 기반에서 sqlite/jsonl 기반으로 영속화
6. OCR/Canny/해상도/워터마크 중심의 가벼운 품질 평가 gate 초안 작성

결과 보고 시:
- 변경 파일
- 새 API/환경변수
- 검증 결과
- 아직 실제 모델 서버 또는 ComfyUI workflow가 없어 fallback으로 남은 부분
을 짧게 정리하세요.
```

