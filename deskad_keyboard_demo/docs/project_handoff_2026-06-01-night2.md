# DeskAd AI Studio 인수인계 - 2026-06-01 (야간 2차)

작성일: 2026-06-01  
프로젝트 경로: `/home/leetaeho/ai_07_high/deskad_keyboard_demo`  
직전 문서: `docs/project_handoff_2026-06-01-night.md`  
작업 브랜치: `feat/pr9-openai-image-ui-merge` (main에 merge 완료)  
**현재 main 최신 커밋: `4f3226e` (night2 문서 커밋, PR #9 merge commit은 `090df5e`)**

---

## 1. 이번 세션 한 줄 요약

PR #6(merged)과 PR #8(openai-image-ui-fix)을 분석해 충돌을 해결한 뒤 **PR #9**로 통합 merge.  
`main` 브랜치에 두 PR의 모든 변경사항이 반영됐고, 미해결 PR은 없는 상태.

---

## 2. PR 이력 최종 정리

| PR | 상태 | 내용 |
|---|---|---|
| #4 | merged | M1 ComfyUI systemd + start.sh 워커 의존성 체크 |
| #5 | merged | U1 stepper + U3 썸네일 + PR 자동화 스크립트 |
| #6 | **merged** | GPU 런타임 캐시 + exclusive worker 전환 + picker UI + P0 회귀 픽스 |
| #7 | closed (미merge) | taeho 브랜치 임시 PR, #6으로 대체됨 |
| #8 | closed (미merge) | OpenAI 이미지 백엔드 + UI 개선, #9에 흡수됨 |
| #9 | **merged** | PR #8 내용을 main 기반으로 rebase해 충돌 해결 후 merge |

---

## 3. main 브랜치 현재 포함 기능 전체 목록

### 3-1. GPU 런타임 캐시 (PR #6)

| 파일 | 역할 |
|---|---|
| `backend/result_cache.py` | text/image 결과를 `data/runtime/cache/{text,image}/<sha256>.json`에 저장 |
| `backend/runtime_workers.py` | GPU_WORKER_MODE별 worker 생명주기 + 파일 lock + idle reaper Timer |
| `backend/ai.py` | `generate_ad_copy`, `generate_copy_experiment`, `create_image_job`에 캐시 + worker 연결 |
| `backend/main.py` | `/ai/copy`, `/ai/copy/experiment`, `/ai/image/jobs`에 `?force_regen` 쿼리 파라미터 |

**캐시 키 설계**:
- text: ad payload 정규화 + provider + model + policy_version `v1`
- image: image_prompt + workflow content hash + dimensions (seed 제외) → `?force_regen=true`만 새 seed

**GPU_WORKER_MODE** (`.env`에 `exclusive` 적용 중):
- `always_on`: worker 시작/종료 없음, 캐시만 활성
- `on_demand`: cache miss 시 필요 worker start, idle timeout 후 stop
- `exclusive`: 반대 worker stop 후 필요 worker start (VRAM 충돌 방지)

---

### 3-2. OpenAI 이미지 백엔드 + UI 반응형 개선 (PR #9 ← PR #8)

**백엔드**:
| 변경 | 내용 |
|---|---|
| `generate_openai_image_reference()` | DALL-E/OpenAI Images API 호출, `response_format` 미지원 모델 자동 재시도 |
| `generate_image_reference()` dispatcher | openai → local → comfyui → fallback 순서로 시도 |
| `create_image_job()` | OpenAI 이미지 백엔드 우선 분기 추가 |
| HTTP Session | 모든 requests 호출에 `Session(trust_env=False)` — 프록시 환경 우회 |
| 포스터 응답 | `local_image_reference` 필드 제거, `image_reference`로 통합 |
| security.py | `_scrub_arg()` — 비문자열 로그 인자 stringify 없이 타입 보존 |

**프론트엔드 (streamlit_app.py)**:
| 변경 | 내용 |
|---|---|
| 반응형 레이아웃 | `max-width: min(96vw, 1920px)`, 컬럼 비율 조정, 사이드바 280px |
| `ad-preview-card` CSS | headline/subcopy/copies/cta를 HTML 카드로 렌더링 |
| `responsive_svg_document()` | SVG 포스터를 100% width HTML로 감싸 반응형 렌더링, 높이 760px |
| `set_step()` / `go_previous()` | 스텝 전환 중앙화, sidebar step_selector 동기화 |
| 이전/다음 버튼 | `on_click` 콜백으로 변경 (불필요한 `st.rerun()` 제거) |
| 포스터 탭 | `image_reference` / `local_image_reference` 모두 지원 |

---

### 3-3. 광고 문구 picker 카드 UI (PR #6)

| 변경 | 내용 |
|---|---|
| `render_copy_experiment_picker()` | provider별 결과를 카드 grid로 표시 |
| "이 문구 사용" 버튼 | 선택 시 `copy_result` 승격, 이후 이미지/포스터에 반영 |
| "광고 문구 생성" 버튼 | "광고 문구 생성" + "한글 모델 비교" 통합, 내부 호출 `/ai/copy/experiment` |
| `provider_label()` | provider id → 표시용 이름 변환 |

---

### 3-4. P0 회귀 픽스 + 이미지 프롬프트 개선 (PR #6)

| 변경 | 내용 |
|---|---|
| `_COLOR_ANCHORS` + `describe_color()` | HEX → 22개 anchor 중 최근접 영문 색상명 매핑 |
| `LAYOUT_PROMPT_LABELS` | 60/65/75/87/104% 레이아웃 상세 레이블 |
| `build_image_prompt()` | `Keyboard format:` + `Color palette:` 절 추가 |

---

### 3-5. HyperCLOVA X SEED 서버 (PR #6)

`tools/hyperclova_seed_openai_server.py` — Hugging Face weight를 OpenAI-compatible API로 서빙 (165줄).  
**2026-06-01 추가 검증 완료** — HF 약관 승인 + `HF_TOKEN` 설정 후 `HyperCLOVAX-SEED-Text-Instruct-1.5B` 실호출 성공. `tools/hyperclova_seed_openai_server.py`는 `HYPERCLOVA_SEED_MODEL` 또는 `HYPERCLOVA_MODEL` 환경변수를 읽어 모델을 선택한다.

---

## 4. 이번 세션 작업 상세 (PR #9 생성 과정)

1. **PR 상태 파악**: PR #6 merged, PR #8 open (`codex/openai-image-ui-fix` 브랜치)
2. **PR #8 diff 분석**: 백엔드 7개 함수 변경 + streamlit 반응형/UX 전면 개선 확인
3. **통합 브랜치 생성**: `feat/pr9-openai-image-ui-merge` — 최신 main 기반
4. **cherry-pick**: PR #8 커밋(`c00cf38`) cherry-pick → `streamlit_app.py` 1곳 충돌 발생
5. **충돌 해결**: "생성 문구" 블록 — PR #6의 `provider 캡션` + PR #8의 `subcopy` 모두 보존
6. **검증**: `py_compile` 6개 파일 + `scan_secrets` (119 파일) 통과
7. **PR #9 생성 + merge**: `feat/pr9-openai-image-ui-merge` → `main`

---

## 5. 현재 환경 상태

| 항목 | 값 |
|---|---|
| conda env | `sprint_high` |
| FastAPI | `:8010` (재시작 필요, 현재 PR #9 코드 미반영 가능성) |
| Streamlit | `:8501` |
| Ollama | `:11434` (qwen2.5:7b) |
| ComfyUI | `:8188` (FLUX.1 schnell fp8) |
| HyperCLOVA SEED | `:11501` — `TEXT_WORKER_CMD`로 on-demand 기동, 1.5B 실호출 검증 완료 |
| GPU_WORKER_MODE | `exclusive` (`.env` 설정 중) |
| GPU_WORKER_IDLE_TIMEOUT_SECONDS | `600` |
| 캐시 경로 | `data/runtime/cache/{text,image}/` |
| 외부 접근 | `https://34.27.86.182:8443` (nginx + TLS) |
| 작업 브랜치 | `feat/pr9-openai-image-ui-merge` (merged, 새 작업은 main pull 후 신규 브랜치) |

> **주의**: PR #9 merge 후 서버를 재시작해야 최신 코드가 반영됩니다.
> ```bash
> cd /home/leetaeho/ai_07_high/deskad_keyboard_demo
> git checkout main && git pull origin main
> bash start.sh --restart
> ```

---

## 6. 검증 결과 (이번 세션)

| 항목 | 결과 |
|---|---|
| `py_compile` (6개 파일) | ✅ |
| `scan_secrets --all` (119 파일) | ✅ clean |
| PR #9 생성 + merge | ✅ `090df5e` |
| 충돌 해결 (streamlit_app.py 1곳) | ✅ 양 PR 의도 보존 |
| HF gated repo 1.5B 접근 | ✅ `config.json` 다운로드 성공 |
| HyperCLOVA 1.5B copy 실호출 | ✅ `/ai/copy/experiment?force_regen=true` 응답 `status: ok` |

---

## 7. 다음 세션 차기 작업

상세 계획: `docs/next_work_2026-06-01-night2.md`

### P0 (즉시)
- **서버 재시작** — main pull 후 `bash start.sh --restart` 실행
- **HyperCLOVA X SEED 실연결** — 완료. 다음에는 회귀 검증만 수행

### P1 (UX)
- 이미지 작업 자동 폴링 + 포스터 흐름 연결
- 노션 reference 다운로드 + grid 미리보기
- keyboard_layout repo clone

### P2 (인프라)
- OpenAI 이미지 백엔드 실검증 (`OPENAI_IMAGE_MODEL=dall-e-3` 설정)
- exclusive worker 전환 실검증 (nvidia-smi VRAM 변화 확인)
- idle unload 실검증 (`GPU_WORKER_IDLE_TIMEOUT_SECONDS=30`)

---

## 8. 새 대화창 시작 프롬프트

```
docs/project_handoff_2026-06-01-night2.md 와 docs/next_work_2026-06-01-night2.md 읽고 작업 진행해줘.
```
