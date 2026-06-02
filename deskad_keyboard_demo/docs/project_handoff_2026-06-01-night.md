# DeskAd AI Studio 인수인계 - 2026-06-01 (야간)

작성일: 2026-06-01  
프로젝트 경로: `/home/leetaeho/ai_07_high/deskad_keyboard_demo`  
직전 문서: `docs/project_handoff_2026-06-01.md`  
기준 브랜치: `taeho` (PR #7 open)

---

## 1. 이번 세션 한 줄 요약

**GPU 런타임 캐시 + on-demand worker unload** 구현 완료.  
text/image 결과를 디스크 캐시로 저장해 재호출 시 GPU 작업을 건너뛰고, `exclusive` 모드에서 VRAM 충돌 없이 워커를 교체한다.

---

## 2. 이번 세션 작업 내용

### 2-1. GPU 런타임 캐시 (`backend/result_cache.py` — 신규)

| 함수 | 역할 |
|---|---|
| `make_text_cache_key(payload, provider_id, model_id)` | 광고 payload + provider/model 기반 SHA256 키 |
| `make_image_cache_key(image_prompt, payload, width, height, workflow_path)` | 이미지 요청 키 (seed 제외, workflow 파일 content hash 포함) |
| `get/put_text_cache(key)` | `data/runtime/cache/text/<sha256>.json` 저장/조회 |
| `get/put_image_cache(key)` | `data/runtime/cache/image/<sha256>.json` 저장/조회 (image_b64 바이트 제외) |

**캐시 키 설계 원칙**:
- **text**: normalized ad payload 전체 + provider + model + policy_version `v1`. 같은 상품 정보면 항상 동일 키.
- **image**: `image_prompt` + workflow 파일 content hash + dimensions + model config. seed를 제외해 "동일 프롬프트 = 동일 키"가 보장됨. `force_regen=true`로만 새 seed 발급.

### 2-2. GPU Worker 생명주기 관리 (`backend/runtime_workers.py` — 신규)

| 함수 | 역할 |
|---|---|
| `ensure_text_worker()` | `GPU_WORKER_MODE`에 따라 text worker 기동 (exclusive면 image worker 먼저 stop) |
| `ensure_image_worker()` | `GPU_WORKER_MODE`에 따라 image worker 기동 (exclusive면 text worker 먼저 stop) |
| `reap_idle_workers()` | idle timeout 경과한 worker를 lock 하에 stop |
| `schedule_idle_reap()` | 마지막 요청 후 idle timeout + 15초에 daemon Timer 등록 (중복 호출 시 타이머 reset) |
| `_WorkerLock` | `data/runtime/gpu_worker.lock` 파일 기반 inter-process exclusive lock |

**`GPU_WORKER_MODE` 값별 동작**:

| 값 | 동작 |
|---|---|
| `always_on` (기본) | worker 시작/종료 없음. 캐시만 활성화. |
| `on_demand` | cache miss 시 필요 worker만 start. idle timeout 후 stop. |
| `exclusive` | cache miss 시 반대 worker stop → 필요 worker start. VRAM 충돌 방지. |

### 2-3. `backend/ai.py` 연동

`generate_ad_copy()`, `generate_copy_experiment()`, `create_image_job()` 각각에:
1. 캐시 조회 → hit이면 즉시 반환 (worker 기동 없음)
2. miss이면 `ensure_text/image_worker()` 호출
3. 결과 캐시 저장 + `schedule_idle_reap()` 예약

`force_regen: bool = False` 파라미터 추가 → `True`면 캐시 건너뜀, 새 seed로 이미지 재생성.

### 2-4. `backend/main.py` — force_regen 쿼리 파라미터

| 엔드포인트 | 변경 |
|---|---|
| `POST /ai/copy` | `?force_regen=true` 추가 |
| `POST /ai/copy/experiment` | `?force_regen=true` 추가 |
| `POST /ai/image/jobs` | `?force_regen=true` 추가 |

### 2-5. `start.sh` 조정

`check_model_workers()` 에서 `GPU_WORKER_MODE=on_demand|exclusive` 일 때 ComfyUI inactive를 경고가 아닌 "요청 시 자동 기동" 안내로 처리.

### 2-6. `.env` — exclusive 모드 기본 활성화

```bash
GPU_WORKER_MODE=exclusive
GPU_WORKER_IDLE_TIMEOUT_SECONDS=600
```

### 2-7. `.env.example` / `.gitignore` 갱신

- `.env.example` — 새 환경변수 8종 문서화
- `.gitignore` — `data/runtime/cache/` 추가

---

## 3. 이전 세션 미커밋 변경사항 (이번 PR에 함께 포함)

| 파일 | 내용 |
|---|---|
| `streamlit_app.py` | 광고 문구 후보 카드 picker UI (`render_copy_experiment_picker`), `copy_selected_provider` 세션, "광고 문구 생성" + "한글 모델 비교" 버튼 통합 |
| `backend/llm_adapters.py` | `is_loopback_base_url()` 추가 (로컬 HyperCLOVA endpoint 무인증 처리) |
| `backend/security.py` | 소규모 패턴 추가 |
| `tools/hyperclova_seed_openai_server.py` | HyperCLOVA X SEED HF 모델을 OpenAI-compatible API로 서빙하는 165줄 스크립트 |
| `README.md` | HyperCLOVA X SEED 로컬 실행 섹션 추가 |
| `docs/*.md` | 인수인계·차기 작업 문서 갱신 |

---

## 4. 검증 결과

| 항목 | 결과 |
|---|---|
| `py_compile` (ai.py, runtime_workers.py, result_cache.py) | ✅ |
| `scan_secrets --all` (110 파일) | ✅ clean |
| `bash -n start.sh` | ✅ |
| `GET /health` | ✅ 200 ok |
| text cache hit — 동일 payload 2회 호출, 2회차 `cache_hit: True` | ✅ |
| image cache hit — 동일 prompt 2회 호출, 2회차 동일 `job_id` 반환 | ✅ |
| `?force_regen=true` — 캐시 무시, 새 job_id 발급 | ✅ |
| `GPU_WORKER_MODE=exclusive` 기본 적용, 서버 재시작 정상 | ✅ |

---

## 5. PR 상태

| PR | 상태 | 내용 |
|---|---|---|
| #4 | merged | M1 ComfyUI systemd + start.sh 워커 의존성 체크 |
| #5 | merged | U1 stepper + U3 썸네일 + PR 자동화 스크립트 |
| #6 | **open** | P0 회귀 픽스 4건 + 이미지 prompt 색상/레이아웃 |
| #7 | **open** | GPU 런타임 캐시 + exclusive worker mode + streamlit copy picker |

---

## 6. 다음 세션 차기 작업

상세 계획: `docs/next_work_2026-06-01-night.md`

### P0 (즉시)

| 번호 | 작업 | 위치 |
|---|---|---|
| #1 | HyperCLOVA X SEED 실제 연결 검증 | `.env HYPERCLOVA_BASE_URL`, `tools/hyperclova_seed_openai_server.py` 실행 후 `/ai/providers` 확인 |

### P1 (UX)

| 번호 | 작업 | 위치 |
|---|---|---|
| #2 | 이미지 작업 자동 폴링 + 포스터 흐름 연결 | `streamlit_app.py` |
| #3 | 노션 reference 다운로드 + grid 미리보기 | `tools/download_notion_references.py` |
| #4 | keyboard_layout repo clone + `.env` 설정 | `KEYBOARD_LAYOUT_REPO_PATH` |

### P2 (인프라)

| 번호 | 작업 | 내용 |
|---|---|---|
| #5 | STEP converter: trimesh 설치 + `.env` 설정 | `conda run -n sprint_high pip install "trimesh[all]"` |
| #6 | exclusive worker 전환 실검증 | ComfyUI active 상태에서 text 요청 → nvidia-smi VRAM 변화 확인 |
| #7 | idle unload 실검증 | `GPU_WORKER_IDLE_TIMEOUT_SECONDS=30`으로 낮춰 30~60초 후 worker stop 확인 |

---

## 7. 환경 메모

| 항목 | 값 |
|---|---|
| conda env | `sprint_high` |
| FastAPI | `:8010` |
| Streamlit | `:8501` |
| Ollama | `:11434` (qwen2.5:7b) |
| ComfyUI | `:8188` (FLUX.1 schnell fp8) |
| HyperCLOVA SEED (선택) | `:11501` (`tools/hyperclova_seed_openai_server.py`) |
| GPU_WORKER_MODE | `exclusive` |
| GPU_WORKER_IDLE_TIMEOUT_SECONDS | `600` |
| 캐시 경로 | `data/runtime/cache/{text,image}/*.json` |
| 외부 접근 | `https://34.27.86.182:8443` (nginx basic auth + TLS) |

---

## 8. 새 대화창 시작 프롬프트

```
docs/project_handoff_2026-06-01-night.md 와 docs/next_work_2026-06-01-night.md 읽고 작업 진행해줘.
```
