# DeskAd AI Studio 인수인계 - 2026-05-29 야간 세션

작성일: 2026-05-29 (야간)
프로젝트 경로: `/home/leetaeho/ai_07_high/deskad_keyboard_demo`
직전 문서: `docs/project_handoff_2026-05-29.md` (오전) + `docs/next_work_2026-05-29.md`

이 문서는 오전 핸드오프 이후 **P0 회귀 픽스 4건 PR #6 생성** 까지의 결과 + 사용자 직접 테스트에서 추가 발견된 **9건의 신규 이슈** 와 **모델 라우팅 진단 결과**, 그리고 다음 세션에서 진행할 **HyperCLOVA X Seed 통합 계획** 을 정리한다.

새 대화창은 §10 "최신 새 대화창 시작 프롬프트" 부터 읽으면 된다.

## 1. 이번 세션 한 줄 요약

- 오전 P0 회귀 픽스 4건 (layout 5종 UI / 87·104 plate / 측면 렌더링 / monitor_arm double_joint) → **PR #6 open** (https://github.com/ikstre/ai_07_high/pull/6)
- 사용자가 추가로 9건의 신규 이슈 보고 → 모델 라우팅 진단 (kanana/midm 모두 qwen2.5:7b 로 라우팅됨을 확인) 후 토큰 한도 고려해 차기 세션으로 이월

## 2. PR 상태

| PR | 상태 | 내용 |
|---|---|---|
| #4 | merged (`03a7bbb`) | M1 ComfyUI systemd + start.sh 워커 의존성 체크 |
| #5 | merged (`e3259b1`) | U1 stepper + U3 썸네일 + PR 자동화 스크립트 |
| #6 | **open** (taeho `efc8328`) | P0 회귀 픽스 4건 + 오전/야간 핸드오프 문서 |

PR #6 머지 후 main 에 모든 P0 회귀 픽스 반영.

## 3. PR #6 변경 요약 (오전 세션 결과)

| 항목 | 파일 | 변경 |
|---|---|---|
| §0-1 layout 5종 UI 노출 | `streamlit_app.py` | `layout_options` 하드코딩 제거 → `/layouts` API 동적 채움. `KEYBOARD_SIZE_INFO` 에 87(TKL)/104(풀배열) 추가. `KEYBOARD_MODEL_DEFAULTS` 에 Keychron Q3 TKL / Leopold FC750R / Keychron Q6 Full / Royal Kludge RK104 추가 |
| §0-2 plate/assembly 데이터 | `data/drawings/keyboard_layout_plate_{87,104}.json` (신규), `data/assemblies/keyboard_assembly_sample.json` | TKL 18.25×6 / 풀배열 22.5×6 plate spec + `plate_sources_by_layout` 매핑 |
| §0-3 측면 렌더링 회귀 | `backend/renderer.py:_add_keyboard_detailed` | case_outer_h 2.4→2.1, case_bottom_h 1.1→0.95, switch_housing_h 1.20→0.65 (topre 1.12→0.58). `plate_y` 를 `show_internals` 분기 밖으로 빼서 case 상단 근처에 재배치. `switch_base_y` 를 plate top 기준으로 변경 → case·plate·switch·keycap 통합 측면 실루엣 |
| §0-4 monitor arm double_joint 회귀 | `backend/renderer.py:_add_monitor_arm` | upper_y(33.0) / lower_y(28.5) 분리 + 수직 elbow drop + 상하 accent 조인트 2종 + VESA bracket |

자동 검증 통과: py_compile, scan_secrets (104 files clean), /health 200, /layouts 5종, /render/desk-setup layout=87+double_joint 200, layout=104 200. **브라우저 측면 카메라 시각 검수는 사용자 검증 대기**.

## 4. 사용자 신규 보고 (2026-05-29 야간)

다음 9건은 사용자가 직접 모델/렌더링을 실행해 본 결과 추가로 발견한 이슈. P0 회귀 픽스 (PR #6) 이후의 차기 작업 큐.

### 4-1. HyperCLOVA X 연동 필요 (#1)

- 현재 `.env` 의 `HYPERCLOVA_BASE_URL` 비어있어 호출 불가
- 코드는 준비됨 (`backend/llm_adapters.py:HyperClovaDirectAdapter`, `backend/ai.py:_copy_adapter`)
- **참고 (사용자 제공)**:
  - Naver tech blog "AI 생태계에 씨앗을 뿌리다: 상업용 오픈소스 AI HyperCLOVA X Seed": https://clova.ai/tech-blog/ai-%EC%83%9D%ED%83%9C%EA%B3%84%EC%97%90-%EC%94%A8%EC%95%97%EC%9D%84-%EB%BF%8C%EB%A6%AC%EB%8B%A4-%EC%83%81%EC%97%85%EC%9A%A9-%EC%98%A4%ED%94%88%EC%86%8C%EC%8A%A4-ai-hyperclova-x-seed
  - 노션 페이지 1: https://www.notion.so/b757356fc5cb831ea366012ba4353f15
  - 노션 페이지 2 (LLM 3D): https://www.notion.so/LLM-3D-5d17356fc5cb8260a7d581d018809caa
- 차기 세션 작업: 위 블로그/노션 페이지 fetch → HyperCLOVA X Seed 모델 (Naver 가 공개한 상업용 오픈소스 weight) 을 로컬 또는 ClovaStudio 게이트웨이로 연결
- 옵션 A (Seed 로컬 호스팅): HF 에서 Naver 공개 weight 다운로드 → vLLM/SGLang/Ollama 로 띄움 → `HYPERCLOVA_BASE_URL=http://127.0.0.1:<port>/v1`
- 옵션 B (Naver ClovaStudio 게이트웨이): 키 발급 후 `HYPERCLOVA_USE_DIRECT_API=true` + `HYPERCLOVA_API_KEY=<X-NCP-CLOVASTUDIO-API-KEY>` + `HYPERCLOVA_BASE_URL=https://clovastudio.stream.ntruss.com`

### 4-2. 광고 문구 + 한글 모델 비교 UI 병합 + 선택 (#2)

- 현재 (`streamlit_app.py:1093-1117`) 4개 버튼 분리: `광고 문구 생성` / `한글 모델 비교` / `실사 이미지 작업` / `포스터 생성`
- `copy_result` 는 단일 결과만 표시 (1257-1264), `copy_experiment_result` 는 별도 expander (1267-1278)
- 사용자 요청:
  1. "광고 문구 생성" 과 "한글 모델 비교" 를 하나의 흐름으로 병합 — 동시에 여러 provider 호출
  2. 결과 N개를 카드/리스트로 보여주고 사용자가 마음에 드는 1개를 **선택** → 이후 단계 (포스터/이미지) 에 그 선택본이 반영되도록
- 백엔드 `/ai/copy/experiment` (`backend/ai.py:run_copy_experiment`) 는 이미 멀티 provider 결과 반환. UI 만 합치면 됨
- 후속: 선택한 copy 의 `headline/copies/hashtags` 가 `copy_result` 로 승격되도록 session_state 흐름 추가

### 4-3. 이미지 작업 워크플로우 명확화 (#3)

- 현재 흐름: `실사 이미지 작업` 클릭 → 즉시 fallback SVG/sample 반환 + ComfyUI 백그라운드 큐잉 → 사용자가 "이미지 작업 상태 갱신" 수동 클릭 → 완료 후 포스터에 합성
- 사용자 요청: "이미지 작업 클릭 → 작업 내역 보고 → 완료 후 포스터/PPT 생성" 흐름으로 정리
- 수정 방향:
  1. 이미지 작업 클릭 시 진행 상태 UI (큐 / running / completed) 를 명확히 표시
  2. 자동 폴링 (Streamlit `st.empty()` + sleep loop 또는 fragment) — 5-10초 간격으로 `/ai/image/jobs/{id}` 호출
  3. 완료 전에는 "포스터 생성" 버튼 비활성화 또는 안내
  4. 완료 후 자동으로 포스터 합성 단계로 진행
  5. PPT 생성도 동일 흐름에 묶기 (현재는 미구현 — 별도 작업)

### 4-4. STEP converter 작업 (#4)

- 현재 `STEP_CONVERTER_CMD` 비어있고 trimesh 미설치 (`backend/cad.py:_run_step_converter` 가 false fallback)
- 옵션 (`backend/config.py:81` 주석):
  - **trimesh (권장)**: `pip install "trimesh[all]"` → `STEP_CONVERTER_CMD=python -c "import trimesh,sys; s=trimesh.load(sys.argv[1]); s.export(sys.argv[2])" {input} {output}`
  - Blender headless: `STEP_CONVERTER_CMD=blender --background --python /opt/deskad/step_to_glb.py -- {input} {output}` (Blender 설치 필요)
  - FreeCAD: `STEP_CONVERTER_CMD=FreeCADCmd -c "..." ` (FreeCAD 설치 필요)
- 차기 세션 작업:
  1. `sprint_high` conda env 에 trimesh 설치
  2. `.env` 에 STEP_CONVERTER_CMD 추가
  3. STEP 업로드 → GLB 변환 시각 검증
  4. `tools/scan_secrets.py` 에 `.stp/.step` 바이너리 제외 확인 (이미 49-50줄 처리)

### 4-5. 상품명 색상 미반영 (#5)

- 현상: 상품명 "크림 베이지 65% 커스텀 키보드" 인데 이미지는 검은색 키보드
- 원인: `backend/ai.py:build_image_prompt` (400-427) 가 `case_color`, `keycap_color`, `accent_keycap_color`, `pcb_color` 의 **HEX 값** 을 prompt 에 안 넣고 `case_finish/plate_material/switch_stem` 등 단어 옵션만 사용
- 키보드 상세 커스텀 (케이스/보강판/PCB/스위치) 만 일부 반영되고 색상 hex 는 빠짐
- 수정 방향:
  1. `build_image_prompt` 에 `case_color`, `keycap_color`, `accent_keycap_color`, `pcb_color` 를 HEX → 한국어 컬러명 (예 "#c8c1b2" → "크림 베이지") 으로 매핑해 추가
  2. `product_name` 안의 색상 키워드 (크림 베이지, 라벤더 등) 를 LLM 이 추출해 case_color 기본값으로 동기화 (Step 1 단계에서 자동 적용)
  3. ComfyUI workflow 의 positive prompt 에도 같은 매핑 전달

### 4-6. 레이아웃 미반영 (65% 선택 → HHKB 이미지) (#6)

- 현상: 65% 선택 후 이미지 생성하면 HHKB (60%) 또는 다른 배열로 그려짐
- 원인: `build_image_prompt` 에 `layout` 필드 **자체가 없음** (#5와 같은 함수, 라인 400-427 에 layout 참조 0건)
- 수정 방향: prompt 에 layout 정보 추가
  - 예: `f"keyboard layout: {layout}% ({KEYBOARD_SIZE_INFO[layout]})"` — 60/65/75 는 컴팩트 배열, 87 TKL, 104 풀배열
  - ComfyUI workflow positive prompt 에도 동일 정보 주입

### 4-7. 노션 샘플 미리보기 가독성 (#7)

- 현상: 모델 미리보기 영역에 어떤 노션 샘플이 있는지 보기 어려움
- 현재 상태:
  - `data/reference_assets.json` 에 12건 등록, **전부 `downloaded: False`** (`tools/download_notion_references.py` 미실행)
  - UI (`streamlit_app.py:842-859`) 가 `downloaded=True` 만 selectbox 에 표시 → 현재 빈 목록
- 수정 방향:
  1. `python tools/download_notion_references.py` 실행해서 12건 다운로드
  2. UI 개선: 다운로드된 파일의 썸네일 grid + label + 라이선스 표시
  3. 도면/이미지 미리보기를 모델 미리보기와 분리된 탭/expander 로 배치
- 노션 추가 샘플 수집 가능성: 사용자 제공 노션 페이지 (4-1 의 b757..., 5d17...) 에 더 많은 자료 있을 수 있음 → fetch 해서 reference_assets.json 확장

### 4-8. 하우징 도면 누락 (#8)

- 현상: "하우징 관련 제품 도면이 더 있는 것 같은데 안 보임"
- 추정 원인:
  - `backend/plates.py:keyboard_layout_repo_path()` 가 `KEYBOARD_LAYOUT_REPO_PATH` 환경변수 또는 `C:/tmp/keyboard_layout` (Windows 경로!) 기본값을 확인
  - 환경변수 미설정 + 경로 미존재 → `load_plate_catalog()` 가 빈 리스트 반환 → `/plates` 응답이 비어 UI 에 안 노출
- 수정 방향:
  1. `naraku010/keyboard_layout` GitHub repo 또는 사용자 노션의 housing 자료를 로컬에 clone
     - 예: `git clone https://github.com/naraku010/keyboard_layout /opt/shared_data/keyboard_layout`
  2. `.env` 에 `KEYBOARD_LAYOUT_REPO_PATH=/opt/shared_data/keyboard_layout` 추가
  3. `/plates` 응답에 카탈로그 반영되는지 확인
  4. 노션 페이지에 housing 추가 자료가 있으면 reference_assets.json 으로 동기화

### 4-9. API 모델 캐싱 (#9)

- 현재 캐싱:
  - `backend/assets.py:lru_cache` (assets 카탈로그)
  - `backend/plates.py:lru_cache` (plate 카탈로그)
  - `backend/config.py:lru_cache` (settings)
- 캐싱 누락 (매번 재계산):
  - `/ai/providers` — provider 메타 정보 (TTL 60s 정도면 충분)
  - `/layouts` — `data/layouts/*.json` glob (TTL 300s)
  - `/render/desk-setup` — 동일 payload 에 대해 동일 GLB 반환 (payload hash 기반 캐싱)
  - `/ai/copy` — 동일 payload 캐싱 (TTL 단기)
- 수정 방향:
  1. `fastapi-cache2` 또는 자체 in-memory `functools.lru_cache` + TTL 데코레이터
  2. ETag / Cache-Control 헤더로 클라이언트 캐싱 유도
  3. Streamlit 측 `@st.cache_data(ttl=...)` 와 정합 (이미 일부 사용)
  4. GLB 캐싱은 payload SHA256 hash → /static/cache/<hash>.glb 패턴

## 5. 모델 라우팅 진단 (2026-05-29 야간 검증)

`/ai/providers` + `/security/config` 응답 분석 결과:

| Provider | base_url | model | 실제 호출 대상 |
|---|---|---|---|
| openai | api.openai.com | gpt-4o-mini | **api_key missing → 호출 불가** |
| **hyperclova** | **missing** | hyperclova-x | **호출 불가 (#1)** |
| **kanana** | Ollama 11434/v1 | **qwen2.5:7b** | **qwen2.5:7b 로 라우팅 (가짜 분리)** |
| **midm** | Ollama 11434/v1 | **qwen2.5:7b** | **qwen2.5:7b 로 라우팅 (가짜 분리)** |
| local | Ollama 11434/v1 | qwen2.5:7b | qwen2.5:7b |
| fallback | n/a | rule-based | 로컬 규칙 |

**핵심 발견**:
- Ollama (`/api/tags`) 에 설치된 모델은 `qwen2.5:7b` **단 1개**
- `.env` 의 `KANANA_BASE_URL` / `MIDM_BASE_URL` / `LOCAL_LLM_BASE_URL` 가 모두 같은 Ollama URL + 같은 모델 (qwen2.5:7b) 로 가리킴
- 결과적으로 `/ai/copy/experiment` 호출 시 kanana / midm / local 3개 응답이 모두 동일한 qwen 응답
- 사용자가 보고한 "kanana 가 qwen 으로 응답" 회귀 사실 확인

**해결책 (차기 세션)**:
- **§5-A**: Ollama 에 한국어 특화 모델 추가 (`ollama pull eeve-korean-instruct` 등) → `.env` 의 KANANA_MODEL 또는 MIDM_MODEL 교체. 단 ~6-12GB 다운로드
- **§5-B**: HyperCLOVA X Seed 를 로컬 (vLLM/Ollama) 또는 ClovaStudio 게이트웨이로 연결 (#1 과 동일 작업). 가장 정공법
- **§5-C**: Kanana/Mi:dm 슬롯을 제거하고 local + hyperclova + fallback 만 노출 (모델 비교가 의미 없으면)

## 6. 작업 우선순위 (차기 세션)

발표/데모 영향 큰 순으로:

```text
P0 (차기 세션 즉시)
 ├─→ #1 HyperCLOVA X Seed 통합 (블로그 + 노션 fetch + vLLM/Ollama 배치 또는 ClovaStudio 키)
 ├─→ #6 image prompt 에 layout 추가 (작은 코드 변경, 큰 시각 영향)
 ├─→ #5 image prompt 에 색상 정보 추가 (#6과 함께 build_image_prompt 1회 수정)
 └─→ #2 UI 광고문구 + 모델비교 병합 + 선택 (HyperCLOVA 연결 후 의미)
P1 (UX)
 ├─→ #3 이미지 작업 자동 폴링 + 완료 후 포스터 흐름 정리
 ├─→ #7 노션 다운로드 실행 + 미리보기 grid (썸네일/라이선스 표시)
 └─→ #8 keyboard_layout repo clone + KEYBOARD_LAYOUT_REPO_PATH 설정
P2 (확장)
 ├─→ #4 STEP converter (trimesh 설치 + .env 등록)
 └─→ #9 API 캐싱 (/ai/providers, /layouts, /render TTL/payload-hash)
```

## 7. 운영 인프라 상태

PR #6 단계에서 변경 없음:
- FastAPI 127.0.0.1:8010 (active)
- Streamlit 127.0.0.1:8501 (active)
- Ollama systemd `ollama.service` (active, qwen2.5:7b 단일)
- ComfyUI systemd `comfyui.service` (active, FLUX.1 schnell fp8)
- nginx :8443 + basic auth + TLS (외부 접속)
- `start.sh --restart` 가 두 systemd 서비스 active 여부 자동 체크

## 8. 보안 / 운영 변동 사항

- 본 야간 세션 추가 변경 없음
- `.env` 의 `KEYBOARD_LAYOUT_REPO_PATH` 추가 시 외부 git 도면 저장소 경로 노출되므로 commit 금지 (`.gitignore` 에 .env 이미 포함)
- HyperCLOVA Naver Cloud 키 도입 시 `tools/scan_secrets.py` 의 패턴 매칭 확인 필요 (X-NCP-* 헤더 키 형식)

## 9. 검증 명령

```bash
cd /home/leetaeho/ai_07_high/deskad_keyboard_demo
conda run -n sprint_high python -B -m py_compile backend/*.py streamlit_app.py tools/scan_secrets.py
conda run -n sprint_high python tools/scan_secrets.py --all
bash start.sh --restart

# 모델 라우팅 확인 (kanana / midm 가 실제 다른 모델인지)
curl -s http://127.0.0.1:8010/ai/providers | python3 -m json.tool
curl -s http://127.0.0.1:11434/api/tags | python3 -c "import sys,json; print([m['name'] for m in json.load(sys.stdin)['models']])"

# 모델 비교 실호출 (4개 응답이 같으면 §5 의 가짜 분리 상태)
curl -s -X POST http://127.0.0.1:8010/ai/copy/experiment -H 'Content-Type: application/json' -d '{"product_name":"테스트 키보드","providers":["kanana","midm","local","fallback"]}' | python3 -m json.tool | head -80

# HyperCLOVA 활성 시 추가
curl -s -X POST http://127.0.0.1:8010/ai/copy -H 'Content-Type: application/json' -d '{"product_name":"테스트","ai_provider":"hyperclova"}' | python3 -m json.tool
```

## 10. 최신 새 대화창 시작 프롬프트

```text
이 프로젝트는 `/home/leetaeho/ai_07_high/deskad_keyboard_demo` 의 DeskAd AI Studio 입니다.
목표는 커스텀 키보드/데스크테리어 소상공인이 실물 촬영 없이 3D 셋업 미리보기 + 광고 문구/포스터/실사 이미지를 만들 수 있게 하는 서비스입니다.

현재 환경:
- GCP VM + conda env `sprint_high`
- FastAPI 8010, Streamlit 8501, Ollama 11434 (systemd, qwen2.5:7b), ComfyUI 8188 (systemd, FLUX.1 schnell fp8)
- 외부 접속: https://34.27.86.182:8443 (nginx + basic auth)
- JupyterHub 가 8000 사용 → 앱은 8000 금지

브랜치 / PR:
- main: PR #4 + #5 머지 완료 (`e3259b1`)
- taeho: PR #6 open — P0 회귀 픽스 4건 (layout/plate/측면렌더링/double_joint) + 본 핸드오프
- 다음 PR 부터는 §6 의 P0 신규 작업 (#1 HyperCLOVA X Seed → #6 layout prompt → #5 색상 prompt → #2 UI 병합)

중요 규칙:
- `.env` / API 키 / GITHUB 토큰 값 출력/커밋 금지
- commit 메시지에 Co-Authored-By 트레일러 생략 (memory `feedback_commit_author_trailer.md`)
- 큰 모델 파일은 git 에 넣지 않음 (Ollama / ComfyUI 가 디스크 직접 관리)

직전 완료 작업 (PR #6):
1. layout 5종 (60/65/75/87/104) UI 전체 노출 + TKL/풀배열 대표 모델 4종 추가
2. 87/104 plate JSON + assembly 매핑
3. 측면 렌더링 회귀 픽스 (case 슬림화, plate/switch 위치 통합)
4. monitor arm double_joint 시각화 (upper/lower y 분리 + elbow drop + accent 조인트)

차기 작업 (사용자 보고 9건, 우선순위 §6 참조):

[P0 즉시]
1. #1 HyperCLOVA X Seed 통합 — 다음 참조를 fetch 해서 진행:
   - https://clova.ai/tech-blog/ai-%EC%83%9D%ED%83%9C%EA%B3%84%EC%97%90-%EC%94%A8%EC%95%97%EC%9D%84-%EB%BF%8C%EB%A6%AC%EB%8B%A4-%EC%83%81%EC%97%85%EC%9A%A9-%EC%98%A4%ED%94%88%EC%86%8C%EC%8A%A4-ai-hyperclova-x-seed
   - https://www.notion.so/b757356fc5cb831ea366012ba4353f15
   - https://www.notion.so/LLM-3D-5d17356fc5cb8260a7d581d018809caa
   옵션 A: Naver 공개 weight 를 HF → vLLM/Ollama 로컬 호스팅
   옵션 B: ClovaStudio 게이트웨이 (사용자 키 필요)
2. #6 image prompt 에 layout 정보 추가 (backend/ai.py:build_image_prompt)
3. #5 image prompt 에 case_color/keycap_color hex 정보 추가 (#6과 동일 함수)
4. #2 UI 광고문구 + 모델비교 병합 + 선택 (streamlit_app.py)

[P1 UX]
5. #3 이미지 작업 자동 폴링 + 완료 후 포스터 흐름
6. #7 노션 reference 다운로드 실행 + 미리보기 grid
7. #8 keyboard_layout repo clone + KEYBOARD_LAYOUT_REPO_PATH 설정

[P2 확장]
8. #4 STEP converter (trimesh 설치 + .env)
9. #9 API 응답 캐싱 (/layouts, /ai/providers, /render payload-hash)

진단 결과 (§5):
- Ollama 에 qwen2.5:7b 단일 모델만 설치
- .env 의 KANANA_BASE_URL / MIDM_BASE_URL / LOCAL_LLM_BASE_URL 모두 같은 Ollama URL + 같은 qwen2.5:7b 모델
- 결과: kanana/midm/local 3개 슬롯이 모두 같은 응답 → 4-card 비교 의미 없음
- 해결: HyperCLOVA X Seed 통합 (#1) 이 핵심, 또는 Ollama 에 EEVE 등 한국어 모델 pull

자세한 진단 / 9건 매핑은 docs/project_handoff_2026-05-29-night.md §4-5 참조.

검증 명령:

cd /home/leetaeho/ai_07_high/deskad_keyboard_demo
curl -s http://127.0.0.1:8010/ai/providers | python3 -m json.tool
curl -s http://127.0.0.1:11434/api/tags | python3 -c "import sys,json; print([m['name'] for m in json.load(sys.stdin)['models']])"
curl -s -X POST http://127.0.0.1:8010/ai/copy/experiment -H 'Content-Type: application/json' -d '{"product_name":"테스트 키보드","providers":["kanana","midm","local","fallback"]}' | python3 -m json.tool | head -80
```

## 11. 종료 절차

```bash
bash /home/leetaeho/ai_07_high/deskad_keyboard_demo/start.sh --stop
# systemd 서비스는 평상시 항상 켜둠
```
