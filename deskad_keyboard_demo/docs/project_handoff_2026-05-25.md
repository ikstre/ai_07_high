# DeskAd AI Studio 협업 인수인계 정리

작성일: 2026-05-25
프로젝트 경로: `/home/leetaeho/ai_07_high/deskad_keyboard_demo`

## 1. 프로젝트 목표

본 프로젝트의 목표는 생성형 AI 기술을 활용하여 소상공인이 광고 콘텐츠를 쉽게 제작할 수 있는 서비스를 개발하는 것이다.

타깃 사용자는 디자인 인력이나 전문 도구를 갖추기 어려운 소상공인이다. 그중 현재 서비스는 커스텀 키보드 샵과 데스크테리어/데스크셋업 용품 판매자를 1차 타깃으로 한다.

핵심 컨셉은 다음과 같다.

- 점주가 키보드/데스크테리어 제품을 가상 책상 위에 배치한다.
- 3D 셋업 미리보기를 통해 제품 조합과 배치를 확인한다.
- 생성된 셋업 정보를 바탕으로 광고 문구와 포스터를 자동 생성한다.
- 실물 촬영 없이 인스타그램, 스마트스토어, 상세페이지용 광고 소재를 빠르게 만든다.

## 2. 서비스 컨셉

서비스명은 현재 `DeskAd AI Studio`로 사용 중이다.

서비스 방향:

- 커스텀 키보드 / 데스크테리어 가상 시뮬레이터
- 도면 또는 레이아웃 기반 3D 미리보기
- 책상 위 제품 배치 조감도 및 perspective preview
- 광고 카피 생성
- SVG 기반 광고 포스터 생성
- 향후 FLUX/SDXL/ControlNet/LoRA 기반 이미지 고도화 가능

차별점:

- 일반 광고 이미지 생성 서비스는 제품 사진 업로드에서 시작한다.
- 현재 기획은 촬영 단계 자체를 줄이는 방향이다.
- 키보드 배열, 모니터 크기, 책상 크기, 데스크테리어 소품을 실제 치수 기반으로 구성해 광고 소재의 구조를 먼저 만든다.

## 3. 현재 실행 환경

GCP VM에서 실행 중이며, 맥북의 PyCharm Remote/SSH 환경에서 접근한다.

공용 conda 환경:

```bash
sprint_high
```

중요 포트:

- `8000`: JupyterHub 사용 중. 앱에서 사용하지 않는다.
- `8010`: FastAPI 백엔드
- `8501`: Streamlit 프론트엔드

외부 접속 URL:

```text
http://34.27.86.182:8501
```

실행 명령:

```bash
cd /home/leetaeho/ai_07_high/deskad_keyboard_demo

conda run -n sprint_high python -m uvicorn backend.main:app --host 0.0.0.0 --port 8010

conda run -n sprint_high python -m streamlit run streamlit_app.py --server.port 8501 --server.address 0.0.0.0
```

## 4. 주요 파일 구조

```text
deskad_keyboard_demo/
  streamlit_app.py
  README.md
  requirements.txt
  .env.example
  start.sh
  backend/
    main.py
    renderer.py
    ai.py
    cad.py
    config.py
    assets.py
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
```

핵심 역할:

- `streamlit_app.py`: 4단계 UI, 3D preview, 광고 결과 표시
- `backend/main.py`: FastAPI 엔드포인트
- `backend/renderer.py`: 자체 GLB 절차적 렌더러
- `backend/ai.py`: 광고 문구 생성, SVG 포스터 생성
- `backend/cad.py`: STEP/STP/GLB 업로드 처리
- `backend/config.py`: `.env` 로딩, API 키 마스킹
- `data/desk_assets.json`: 데스크테리어 에셋 카탈로그와 치수 기록
- `training/`: LoRA 학습 데이터셋 준비 코드

## 5. 현재 구현된 사용자 흐름

Streamlit 앱은 4단계로 구성된다.

1. 상품 정보
   - 상품 유형
   - 상품명
   - 가격
   - 판매 채널
   - 타깃 고객
   - 핵심 특징

2. 도면/제품 데이터
   - 키보드 모델 선택
   - 키보드 배열 선택
   - STEP/STP/GLB 업로드
   - 데스크테리어 물품 선택

3. 가상 셋업
   - 광고 스타일 선택
   - 책상 크기 프리셋 선택
   - 모니터 크기 선택
   - 색상 선택
   - 3D 데스크 셋업 생성

4. 광고 콘텐츠
   - 광고 톤 선택
   - 이미지 비율 선택
   - 추가 요청 입력
   - 광고 문구 생성
   - SVG 포스터 생성

## 6. 현재 렌더링 방식

현재 3D 렌더링은 외부 3D 모델이나 이미지 생성 AI 모델이 아니라, `backend/renderer.py`의 자체 GLB 생성기로 동작한다.

즉, `GlbBuilder`가 키보드, 모니터, 책상, 소품을 절차적으로 생성해 GLB 파일을 만든다.

중요 기준:

- `1 GLB unit = 1 cm`
- 키보드 레이아웃 JSON은 MX key unit 기준
- MX `1u = 19.05 mm = 1.905 cm`

현재 지원 키보드 배열:

- 60%: 약 `28.6 x 9.5 cm`, 61키
- 65%: 약 `30.5 x 9.5 cm`, 67키
- 75%: 약 `30.5 x 11.4 cm`, 84키

현재 지원 모니터 크기:

- 24인치: 약 `56 x 33 cm`
- 27인치: 약 `62 x 36 cm`
- 32인치: 약 `74 x 43 cm`

현재 지원 책상 크기:

- `120 x 60 cm`
- `120 x 80 cm`
- `140 x 70 cm`
- `160 x 80 cm`
- `180 x 80 cm`
- 직접 입력: 폭 `100~200 cm`, 깊이 `50~90 cm`

## 7. 데스크테리어 에셋

현재 `data/desk_assets.json`에는 12개 에셋이 등록되어 있다.

기본/기존 에셋:

- 무선 마우스
- 24/27/32인치 모니터
- VESA 모니터암
- 데스크 조명
- 미니 화분
- 북쉘프 스피커
- 모니터 받침대
- 노트/플래너
- 헤드폰 스탠드

추가된 에셋:

- 스마트폰 스탠드
- 키캡 진열 트레이
- 머그컵

각 에셋에는 다음 정보가 기록되어 있다.

- `id`
- `label`
- `category`
- `enabled_by_default`
- `rendering`
- `source`
- `license`
- `dimensions_cm`
- `external_candidates`
- `notes`

외부 GLB 후보는 `external_candidates`에 기록되어 있으나, 실제 다운로드/번들링은 아직 하지 않았다. 외부 파일을 프로젝트에 포함하기 전에는 반드시 상업 사용 가능 여부와 출처 표기 조건을 개별 확인해야 한다.

## 8. 최근 수정/검증된 내용

최근 검증 항목:

- 페이지 로드 정상
- 타이틀 `DeskAd AI Studio`
- API 상태에서 OpenAI Key, Local LLM, STEP Converter는 `missing`으로 표시
- 실제 키 값은 노출되지 않음
- 60/65/75 배열 드롭다운 표시
- 24/27/32인치 모니터 선택 표시
- 결과 패널에 실측 치수 칩 표시
- 3D GLB iframe 로드 정상
- 32인치 top view에서 책상 범위 밖으로 나가지 않음
- 60% 배열 렌더 시 65%보다 작게 표시
- 모니터암 선택 시 기본 스탠드 없이 arm upright 컬럼만 표시

추가 수정:

- 모니터 크기 선택 시 외곽 프레임뿐 아니라 display 면도 24/27/32 크기에 맞게 변경
- 램프를 후면 모니터 뒤쪽에서 좌측 전면 쪽으로 이동해 top/perspective view에서 더 잘 보이게 수정
- 원통형 primitive를 추가해 소품이 덜 박스처럼 보이게 개선
- 램프 베이스/갓, 화분, 스피커 유닛, 머그컵을 원통 기반 형태로 개선
- 스마트폰 스탠드, 키캡 진열 트레이, 머그컵 추가

검증 결과:

```text
py_compile 통과
/assets/desk: 12개 에셋 로드
/render/desk-setup: 200
60% + 32인치 + 추가 소품 조합 생성 성공
asset_count: 9
monitor_panel_cm: 74.0 x 43.0
board_width: 28.6
http://34.27.86.182:8501: 200
```

## 9. API 구조

주요 엔드포인트:

- `GET /health`
- `GET /security/config`
- `GET /layouts`
- `GET /assets/desk`
- `GET /viewer`
- `POST /render/keyboard-preview`
- `POST /render/desk-setup`
- `POST /render/uploaded-model`
- `POST /ai/copy`
- `POST /ai/poster`

중요 사항:

- 브라우저가 8010 포트에 직접 접근하지 못할 수 있다.
- 그래서 Streamlit이 내부 `127.0.0.1:8010`에서 GLB/SVG를 받아와 인라인으로 렌더링하도록 구성되어 있다.
- 외부 사용자에게는 기본적으로 `8501`만 안내한다.

## 10. 보안 설정

실제 API 키는 `.env`에만 둔다.

`.env.example`은 공유 가능하지만, `.env`는 커밋하지 않는다.

예시:

```env
DESKAD_API_BASE=http://127.0.0.1:8010
DESKAD_PUBLIC_API_BASE=http://34.27.86.182:8010
AI_PROVIDER=auto
OPENAI_API_KEY=
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_TEXT_MODEL=gpt-4o-mini
LOCAL_LLM_BASE_URL=
LOCAL_LLM_MODEL=
LOCAL_IMAGE_ENDPOINT=
STEP_CONVERTER_CMD=
```

주의:

- API 키 값을 로그, 화면, API 응답에 노출하지 않는다.
- `/security/config`는 키 존재 여부만 `set/missing`으로 보여준다.
- `.gitignore`에는 `.env`, `.env.*`, 업로드 파일, 생성 포스터, 대형 모델 파일을 제외하도록 설정한다.

## 11. STEP/GLB 업로드

현재 지원:

- `.glb` 업로드: 그대로 viewer에 사용
- `.step`, `.stp` 업로드: 변환기가 있으면 GLB 변환
- 변환기가 없으면 프록시 GLB 생성

변환기 설정:

```env
STEP_CONVERTER_CMD=python /opt/deskad/convert_step_to_glb.py {input} {output}
```

현재 VM에는 FreeCADCmd, Blender, assimp 기반 변환기가 기본 구성되어 있지 않았다. 실제 STEP 변환을 붙이려면 별도 설치와 검증이 필요하다.

## 12. AI / 광고 생성

현재 구현:

- OpenAI 호환 API 기반 광고 문구 생성
- 로컬 LLM endpoint 기반 광고 문구 생성 가능
- 둘 다 없으면 fallback 템플릿 사용
- SVG 포스터 생성

현재 이미지 생성 모델이 직접 광고 이미지를 생성하는 구조는 아니다. 포스터는 SVG 기반 템플릿이며, 추후 FLUX/SDXL/ControlNet과 연결 가능하다.

향후 후보:

- FLUX.1 schnell
- SDXL Turbo
- SD3.5 Medium
- ControlNet Canny/Depth
- BrushNet/PowerPaint
- LoRA 또는 IP-Adapter

## 13. 학습 파이프라인

`training/prepare_desk_lora_dataset.py`는 LoRA 학습용 데이터셋 준비 스크립트다.

기능:

- 이미지 폴더 입력
- 이미지 복사 또는 symlink
- caption 자동 생성
- `metadata.jsonl` 생성
- `license_manifest.json` 생성

예시:

```bash
python training/prepare_desk_lora_dataset.py \
  --images-dir ./raw_desk_images \
  --output-dir ./training/output/desk_lora_dataset \
  --trigger-token deskadkb \
  --style "minimal premium deskterior" \
  --product-type "custom keyboard and desk accessory" \
  --source merchant-owned \
  --license merchant-owned-commercial \
  --commercial-use-checked
```

중요:

- 점주 직접 촬영 이미지 우선
- 외부 자료는 상업 사용 가능 여부 확인 필수
- 브랜드 로고, 상표, 타사 제품명은 학습 전 제거 또는 제외

## 14. 벤치마킹/기획 참고

주요 벤치마크:

- 오늘의집 3D 인테리어
- Houzz Floor Planner
- IKEA Kreativ
- Threekit
- Nike By You
- Keyboard Layout Editor
- InteriorAI
- RoomGPT
- Photoroom
- Canva Magic Switch
- 카페24 에디봇
- 미리캔버스

차용한 UX 패턴:

- 2D/3D 또는 camera view 전환
- 좌측 제품/데이터 선택
- 중앙 3D preview
- 우측 또는 하단 결과 패널
- 결과 치수 칩 표시
- 광고 생성 CTA
- Magic Switch 스타일의 산출물 전환 가능성
- 5종 변주 그리드 가능성

## 15. 남은 작업

우선순위가 높은 작업:

1. 실제 GLB 에셋 병합 파이프라인
   - Poly Pizza, Sketchfab CC0, Pixabay 등에서 상업 사용 가능한 GLB 선별
   - 라이선스 manifest 기록
   - glTF/GLB 병합 또는 참조 로딩 구조 구현

2. 렌더링 품질 개선
   - 박스/원통 primitive를 더 자연스럽게 개선
   - monitor arm, lamp, speaker, plant 위치 세밀 조정
   - 책상 크기별 충돌/겹침 방지

3. STEP 변환
   - FreeCADCmd 또는 Blender 기반 변환기 검토
   - `.env`의 `STEP_CONVERTER_CMD`로 연결
   - 업로드 STEP 파일 실제 렌더링 검증

4. AI 이미지 생성 연결
   - 현재는 SVG 포스터
   - 다음 단계에서 FLUX/SDXL/ControlNet worker 연결
   - 생성 결과 4~5종 변주 UI 추가

5. 광고 상세페이지 자동 레이아웃
   - 헤드라인
   - 스펙
   - 감성 컷
   - 제품 디테일
   - CTA

6. 테스트/검증 자동화
   - Playwright headless Chromium으로 UI regression 체크
   - 60/65/75 배열별 GLB 생성 테스트
   - 24/27/32 모니터별 bbox 테스트
   - 120x60/160x80 책상별 소품 위치 테스트

## 16. 협업 시 주의사항

- `8000` 포트는 JupyterHub가 사용 중이므로 앱에 사용하지 않는다.
- 외부 접속은 `8501` 기준으로 안내한다.
- 실제 키가 들어 있는 `.env`는 커밋하지 않는다.
- 기존 절차적 렌더러를 수정할 때는 `1 unit = 1cm` 기준을 유지한다.
- 외부 3D 모델을 추가할 때는 라이선스와 출처를 `data/desk_assets.json` 또는 별도 manifest에 남긴다.
- 사용자/다른 팀원이 수정한 파일을 임의로 되돌리지 않는다.

## 17. 현재 확인된 한계

- 실제 GLB 에셋을 외부에서 다운로드해 병합하는 단계는 아직 미구현
- 현재 3D 모델은 절차적 primitive 기반이라 고품질 CAD/실사 수준은 아님
- STEP 파일은 변환기가 없으면 프록시 GLB만 생성
- 광고 포스터는 SVG 템플릿 기반이며 이미지 생성 모델 결과물은 아님
- 모니터/램프/소품 위치는 계속 미세 조정 필요
