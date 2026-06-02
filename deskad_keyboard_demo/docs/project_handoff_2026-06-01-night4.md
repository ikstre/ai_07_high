# DeskAd AI Studio 인수인계 - 2026-06-01 (야간 4차)

작성일: 2026-06-01  
프로젝트 경로: `/home/leetaeho/ai_07_high/deskad_keyboard_demo`  
직전 문서: `docs/project_handoff_2026-06-01-night3.md`  
작업 브랜치: `main` (로컬 커밋 2개가 `origin/main`보다 앞섬 + 미커밋 변경 있음)  
**현재 로컬 main 최신 커밋: `6f9f6f3` (야간 3차 인수인계 문서)**

---

## 1. 이번 세션 한 줄 요약

코드 리뷰(폴링 12개 버그) → **전부 수정 + 검증 완료**.  
노션 피드백(하은) 일부 구현 완료(한국어 프롬프트 인젝션, 텍스트 워커 라우팅, ComfyUI 워커 해제).  
`.env`의 kanana/midm qwen 오염 → **슬롯 비활성화로 해소**.  
노션 설계 레퍼런스(모델/UI/3D)를 6절에 정리 — 차기 코드 추가 기준.

> **주의**: 이번 세션 변경은 **미커밋 상태**. 아래 8절 커밋 가이드 참조.

---

## 2. 자동 폴링 버그 수정 — ✅ 전부 반영 (검증 완료)

`/code-review max`로 직전 커밋(`3640000` 자동 폴링)에서 12개 버그를 발견했고, 이번 세션에 `streamlit_app.py`에서 전부 수정. 실제 코드 라인 검증 완료.

### Critical 5개

| # | 버그 | 수정 내용 | 검증 위치 |
|---|---|---|---|
| 1 | `time.sleep(3)`이 Streamlit 스레드 블로킹 | `@st.fragment(run_every=3)`로 교체, `time.sleep` 제거 | `streamlit_app.py:907` |
| 2 | `0.0`(falsy) sentinel로 타임아웃 미발동 | `DEFAULTS` sentinel `0.0` → `None`, `is None` 체크 | `:292`, `:918-921` |
| 3 | 타임아웃 후 포스터 버튼 영구 비활성 | `poster_waiting_for_image()`가 `image_polling_enabled` 먼저 확인 | `:777-780` |
| 4 | 타임아웃/예외 경로 `st.rerun()` 누락 | 두 경로 모두 `st.rerun()` + `started_at=None` 추가 | `:928`, `:939` |
| 5 | `if … if`(elif 아님) 중복 rerun | `completed` 분기를 `elif`로 변경 | `:942`, `:947` |

### Medium / Low

| # | 버그 | 수정 내용 | 검증 위치 |
|---|---|---|---|
| 6 | `data["copy"]` KeyError | `data.get("copy")` + `isinstance` 가드 | `:875-878` |
| 8 | `refresh_image_job()` 빈 응답 덮어쓰기 | `isinstance` 검증 후 실패 시 기존 job 보존 | `:893-894` |
| 9 | 수동 refresh 시 stale timestamp 재사용 | `previous_polling` 추적 후 전이 시에만 재설정 | `:891`, `:899` |
| 11 | `image_poster_ready` dead state | 세션 키 + 4개 write 전부 제거 | (DEFAULTS에서 삭제) |
| 12 | expander 하드코딩 set 불일치 | `IMAGE_JOB_TERMINAL_STATUSES` 상수 사용 | `:1489` |

> **`@st.fragment(run_every=3)` 동작**: 3초마다 fragment만 자동 재실행(전체 페이지 블로킹 없음).  
> 완료 시 `st.rerun()`(기본 scope=app)으로 전체 갱신 → 포스터 버튼 자동 활성화.

---

## 3. 모델 라우팅 점검 — ✅ 오염 해소

### 문제였던 상태 (수정 전)

```
KANANA_MODEL=qwen2.5:7b   ← 카나나가 아닌 qwen 호출
MIDM_MODEL=qwen2.5:7b     ← Mi:dm이 아닌 qwen 호출
```
→ `/ai/copy/experiment`에서 kanana·midm·local이 전부 동일 qwen 결과 반환, 비교 무의미.

### 현재 상태 (수정 후, `.env`)

```
KANANA_BASE_URL=          # 비움 → configured: false
KANANA_MODEL=
MIDM_BASE_URL=            # 비움 → configured: false
MIDM_MODEL=
LOCAL_LLM_MODEL=qwen2.5:7b   # local 슬롯은 qwen 유지 (정상)
```
→ kanana/midm이 실험에서 제외되어 qwen 결과를 다른 모델로 오인할 위험 제거.

### 텍스트 워커 라우팅 보강 (노션 ⭐⭐⭐, 이번 세션 구현)

`backend/ai.py` — `_uses_managed_text_worker(adapter)` 추가.  
`ensure_text_worker(start_managed_worker=...)`로 변경되어, **HyperCLOVA SEED 관리형 워커(:11501)는 해당 provider를 실제로 쓸 때만 기동**. kanana/midm/local(Ollama :11434) 요청 시에는 SEED 워커를 띄우지 않고, 켜져 있으면 정지.

### kanana/midm 실모델 재연동 시 (P2)

코드 기본값은 이미 올바름 (`backend/ai.py`):
- `kanana` → `kakaocorp/kanana-2-30b-a3b-instruct-2601` (`:271`)
- `midm` → `K-intelligence/Midm-2.0-Mini-Instruct` (`:280`)

vLLM 등으로 별도 포트 서빙 후 `.env`만 채우면 동작:
```bash
KANANA_BASE_URL=http://127.0.0.1:11502/v1
KANANA_MODEL=kakaocorp/kanana-nano-2.1b      # 소형 OSS, L4 적합
MIDM_BASE_URL=http://127.0.0.1:11503/v1
MIDM_MODEL=K-intelligence/Midm-2.0-Mini-Instruct
```
검증: `GET /ai/providers`에서 각 `runtime_name`이 qwen이 아닌 해당 모델명인지 확인.

---

## 4. 노션 피드백(하은) 반영 현황

**원문**: [🔬 2026-06-01 코드 검증 종합 + 피드백](https://www.notion.so/da57356fc5cb83cdb54f018c00435e83)

| 항목 | 우선순위 | 상태 |
|---|---|---|
| `_PROMPT_INJECTION_HINTS` 한국어 패턴 5종 | ⭐⭐⭐ | ✅ 완료 (`ai.py` — "이전 지시 무시"/"시스템 프롬프트 보여"/"개발자 모드"/"관리자"/"이 절부터") |
| 텍스트 워커 provider별 라우팅 | ⭐⭐⭐ | ✅ 완료 (`_uses_managed_text_worker`) |
| ComfyUI 워커 작업 후 해제 | ⭐⭐ | ✅ 완료 (`IMAGE_WORKER_STOP_AFTER_JOB=true` + `release_image_worker_after_job` + 완료본 캐시 후 정지) |
| 이미지 자동 폴링 + 포스터 흐름 | ⭐⭐ | ✅ 완료 (버그 수정 포함) |
| ~~`SENSITIVE_ENV_KEYS`에 `NOTION_TOKEN`~~ | — | ❌ 제외 (노션 토큰 미사용. `TOKEN` 부분 문자열 힌트가 이미 자동 redaction) |
| `copy_policy.py` 금지어 30종 추가 | ⭐⭐ | ⬜ 미구현 (5절 차기 작업) |
| GPU 품질 워커 (CLIP-I/FID/LPIPS/OCR) | ⭐⭐⭐ | ⬜ 미구현 (다음 주) |
| `ChatCompletionAdapter` retry/백오프 | ⭐⭐ | ⬜ 미구현 |

---

## 5. 차기 작업 (상세: `next_work_2026-06-01-night4.md`)

### 이번 주
- `copy_policy.py` PART 7-Y 금지어 30종 + 채널 3종
- OpenAI 이미지 백엔드 실검증 (`OPENAI_API_KEY` + `dall-e-3`)
- 자동 폴링 UI 실검증 (브라우저: pending → completed → 버튼 활성)

### 다음 주
- GPU 품질 워커 `workers/quality_evaluator.py`
- `ImageQualityReport` 필드 추가 (`mos_score`/`accepted`/`clip_score`)
- kanana/midm 실모델 vLLM 서빙
- 3D 파이프라인 (6-3절 참조)

---

## 6. 노션 설계 레퍼런스 — 모델 / UI / 3D (코드 추가 기준)

> 두 노션 페이지의 설계 결정을 현재 코드 상태와 대조. 차기 기능 추가 시 이 절을 기준으로.
> - [모델 선정 리서치 — 한국어 카피 LLM & 3D 파이프라인](https://www.notion.so/5d17356fc5cb8260a7d581d018809caa)
> - [2026-06-01 코드 검증 종합](https://www.notion.so/da57356fc5cb83cdb54f018c00435e83)

### 6-1. 모델 선정 (카피 LLM)

**3사 점수 (노션 1-B, 30점 만점)**: HyperCLOVA X **25** (1위) / Kanana 24 / Mi:dm 23

| 모델 | 버전 | 단가(입력/출력 1K) | 컨텍스트 | 포지션 |
|---|---|---|---|---|
| HyperCLOVA X | **HCX-005** | 5원 / 15원 | 32K | 메인 (커머스/스토어 톤 만점) |
| HyperCLOVA X | HCX-DASH-002 | 0.75원 / 1.5원 | 16K | 경량 (단가 1/3) |
| Kanana | Flag 32.5B / Essence 9.8B / **Nano 2.1B** | OSS 자체 호스팅 | 8K~ | Nano는 Apache 2.0, L4 적합 |
| Mi:dm | 2.0 Mini 7B | OSS 자체 호스팅 | 32K | 완전 OSS, 파인튜닝 용이 |

**스테이지별 권장 (노션 1-D)**: MVP=HCX-DASH-002 → V1=DASH+HCX-005(프리미엄 톤) → V2=HCX-005 주 + Kanana Nano 부조

**현재 코드 대조** (`backend/ai.py`):
- provider 6종 분기 (`_copy_adapter`): openai / hyperclova / hyperclova_direct / kanana / midm / local ✅
- 자동 fallback 순서 (`TEXT_PROVIDER_ORDER`): `openai → hyperclova → kanana → midm → local` ✅
- 기본 모델: openai=`gpt-4o-mini`, hyperclova=`HCX-005` ✅ (노션 권장 일치)
- 로컬 SEED: `HyperCLOVAX-SEED-Text-Instruct-1.5B` (:11501, 실호출 검증 완료) ✅
- **결정 보류**: HCX-DASH-002 vs HCX-005 디폴트 — 현재 HCX-005, 회의 확정 필요

### 6-2. UI 구성 (Streamlit 프론트)

**노션 2-11 설계 ↔ 현재 코드** (`streamlit_app.py`):

| 요소 | 설계 | 현재 |
|---|---|---|
| 4단계 step | 1.상품정보 / 2.도면·제품 / 3.가상셋업 / 4.광고콘텐츠 | ✅ `STEP_LABELS` |
| step 동기화 | 단일 출처 전환 + 사이드바 연동 | ✅ `set_step`/`sync_step_from_sidebar` |
| 반응형 | `max-width: min(96vw,1920px)`, 사이드바 280px | ✅ |
| 카피 picker | provider별 카드 + "이 문구 사용" | ✅ `render_copy_experiment_picker` |
| 이미지 자동 폴링 | `st.empty` 루프, completed 자동 진행, timeout | ✅ **이번 세션 완료** (`@st.fragment`) |
| 모델 뷰어 | `model-viewer@4.0.0` 3종 카메라 | ✅ |
| 노션 reference grid | Step 1 갤러리 | ⬜ 미구현 (`tools/download_notion_references.py` 오류 수정 필요) |
| 코드 분리 | step별 모듈 (`streamlit/steps/`) | ⬜ 1400줄+ 단일 파일 |

### 6-3. 3D 모델 구성 (도면 → 렌더 파이프라인)

**노션 Part 2 설계 (5단계)**:
```
① STEP/IGES/STL 업로드
② 변환: FreeCAD CLI(STEP→OBJ, LGPL) → assimp(OBJ→GLB)
③ 에셋 저장 (GCS/S3 .glb + 점주 DB)
④ 프론트: R3F + drei (Streamlit iframe, WebGL2 고정 / WebGPU 자동 감지)
⑤ 고품질 렌더: FLUX+ControlNet(기존) → 옵션 Blender Eevee Next headless(1-3초)
```

**변환기 권장 (노션 2-B)**: FreeCAD CLI(최적) / Blender STEPper / assimp(STL 폴백)  
**메시 최적화 (노션 5-A)**: Draco + Meshopt + Decimation 70% + KTX2 → **전체 셋업 <1MB 목표**  
**PBR 6맵 (5-B)**: Albedo/Normal/Roughness/Metallic/AO/Emissive — 3D는 "구조·형태", LoRA/IC-Light는 "사실성·톤"  
**glTF KHR 확장 7종 (5-C)**: clearcoat(키캡), transmission(아크릴), anisotropy(브러시드 알루미늄) 등 — R3F+drei 자동 지원  
**에셋 라이브러리 (2-F)**: 레디메이드 50개 (하우징 15 / 키캡 6 / 책상 10 / 모니터 8 / 소품 11)

**현재 코드 대조**:
- `backend/renderer.py` (1922줄) — 자체 절차적 GLB 빌더, **1 GLB unit = 1cm** 기준 ✅ (성현님 작업 일치)
- 키보드 5종 레이아웃(60/65/75/87/104) + 액세서리 28종 + `DeskPlacer` 겹침 방지 ✅
- `backend/cad.py` — STEP 업로드 검증 + `STEP_CONVERTER_CMD` 셸 변환
- **갭**: `STEP_CONVERTER_CMD` 미설치 → proxy GLB fallback 중. 노션 권장 `trimesh[all]` 우선 설치
- **갭**: R3F 프론트 미구축 (현재 `model-viewer` iframe만). Blender Eevee Next 미연동
- **갭**: 입력 GLB 단위 검증 없음 — 외부 STEP/GLB가 1cm 기준 아니면 스케일 틀어짐 (`cad.py` 검증 로직 권장)

---

## 7. 현재 환경 상태

| 항목 | 값 |
|---|---|
| conda env | `sprint_high` |
| FastAPI / Streamlit | `:8010` / `:8501` |
| Ollama | `:11434` (qwen2.5:7b — local 슬롯) |
| ComfyUI | `:8188` (FLUX.1 schnell fp8), 작업 후 자동 정지 옵션 ON |
| HyperCLOVA SEED | `:11501` — on-demand, 1.5B 실호출 검증 완료 |
| Kanana / Mi:dm | **슬롯 비활성화** (실모델 미서빙) |
| GPU_WORKER_MODE | `exclusive`, idle 600s |
| 외부 접근 | `https://34.27.86.182:8443` |
| 미커밋 변경 | `streamlit_app.py`, `backend/ai.py`, `backend/security.py`, `backend/runtime_workers.py`, `.env.example`, `tools/hyperclova_seed_openai_server.py`, night2/3 문서 |

---

## 8. 커밋 가이드

```bash
cd /home/leetaeho/ai_07_high/deskad_keyboard_demo

# 컴파일 + 비밀 스캔
conda run -n sprint_high python -m py_compile streamlit_app.py backend/ai.py backend/security.py backend/runtime_workers.py
python tools/scan_secrets.py --all

# 폴링 버그 수정
git add streamlit_app.py
git commit -m "fix: 자동 폴링 12개 버그 수정 (fragment 폴링 + None sentinel + 버튼 게이트)"

# 노션 피드백 (프롬프트 인젝션 + 워커 라우팅 + ComfyUI 해제)
git add backend/ai.py backend/runtime_workers.py backend/security.py .env.example
git commit -m "feat: 한국어 프롬프트 인젝션 패턴 + 텍스트 워커 라우팅 + ComfyUI 작업 후 해제"

# 문서
git add docs/ tools/hyperclova_seed_openai_server.py
git commit -m "docs: 야간 4차 인수인계 + 노션 설계 레퍼런스(모델/UI/3D)"

bash start.sh --restart
curl -s http://127.0.0.1:8010/health
```

---

## 9. 새 대화창 시작 프롬프트

```
docs/project_handoff_2026-06-01-night4.md 와 docs/next_work_2026-06-01-night4.md 읽고 작업 진행해줘.
```
