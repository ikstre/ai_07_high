# DeskAd AI Studio 인수인계 - 2026-06-01 (야간 3차)

작성일: 2026-06-01  
프로젝트 경로: `/home/leetaeho/ai_07_high/deskad_keyboard_demo`  
직전 문서: `docs/project_handoff_2026-06-01-night2.md`  
작업 브랜치: `main` (로컬 커밋 2개가 `origin/main`보다 앞섬)  
**현재 로컬 main 최신 커밋: `6f9f6f3` (야간 3차 인수인계 문서 커밋)**

---

## 1. 이번 세션 한 줄 요약

`streamlit_app.py`에 이미지 작업 자동 폴링 + 포스터 흐름 연결을 구현하고 로컬 커밋 완료.  
추가로 HyperCLOVA X SEED 1.5B gated repo 접근과 실제 `/ai/copy/experiment` 호출까지 검증 완료.

---

## 2. 이번 세션 변경 파일

| 파일 | 변경 유형 | 내용 |
|---|---|---|
| `streamlit_app.py` | 기능 추가 | 이미지 작업 자동 폴링 전체 구현 (`3640000`) |
| `tools/hyperclova_seed_openai_server.py` | 설정 개선 | `HYPERCLOVA_MODEL` 환경변수도 모델 선택에 사용하도록 변경 (미커밋) |
| `docs/project_handoff_2026-06-01-night2.md` | 문서 갱신 | HyperCLOVA 1.5B 검증 결과 반영 (미커밋) |
| `docs/next_work_2026-06-01-night2.md` | 문서 갱신 | HyperCLOVA 작업 상태를 완료/회귀 검증으로 정리 (미커밋) |

---

## 3. 구현 상세 (streamlit_app.py)

### 3-1. 세션 상태 추가

```python
DEFAULTS = {
    ...
    "image_polling_enabled": False,      # 자동 폴링 활성 여부
    "image_poll_started_at": 0.0,        # 폴링 시작 시각 (time.time())
    "image_poll_timeout_seconds": 180,   # 최대 대기 시간 (3분)
    "image_poster_ready": False,         # 포스터 버튼 활성화 플래그
}
```

### 3-2. 상수 추가

```python
IMAGE_JOB_TERMINAL_STATUSES = {"completed", "failed", "draft", "not_configured"}
```
— 이 상태에 도달하면 폴링 중단.

### 3-3. 헬퍼 함수 추가

| 함수 | 역할 |
|---|---|
| `image_job_status()` | 현재 job status 문자열 반환 |
| `image_job_is_pending(job=None)` | job_id 존재 + terminal 아님 → `True` |
| `poster_waiting_for_image()` | 폴링 중인 job 있으면 `True` → 포스터 버튼 disabled 용 |

### 3-4. `current_image_job_id()` 수정

```python
# 변경 전: job_id 무조건 반환
# 변경 후: status == "completed"인 경우만 반환
if job.get("status") != "completed":
    return None
return job.get("job_id")
```
— 포스터 합성 시 완료된 이미지만 참조하도록 안전망 추가.

### 3-5. `generate_image_job()` 수정

이미지 작업 제출 직후 폴링 상태 초기화:

```python
st.session_state.image_quality_report = None
st.session_state.image_poster_ready = job.get("status") == "completed"
st.session_state.image_polling_enabled = image_job_is_pending(job)
st.session_state.image_poll_started_at = time.time() if polling else 0.0
```

### 3-6. `refresh_image_job()` 수정

API 갱신 후 폴링 상태(`image_poster_ready`, `image_polling_enabled`) 업데이트. 반환값을 `dict | None`으로 변경.

### 3-7. `auto_poll_image_job()` 신규 추가 (핵심)

result 영역(`with result_col:`) 내 job 표시 블록 직후 호출.

로직 흐름:
1. `image_polling_enabled` 아니면 즉시 반환
2. terminal status 확인 → 폴링 중단
3. 경과 시간 > `image_poll_timeout_seconds` → 경고 후 중단
4. `st.empty().caption()` 으로 상태 표시 ("자동 갱신 중 · {status} · {elapsed}초")
5. `refresh_image_job()` 호출
6. `completed` → `st.success()` + `st.rerun()`
7. 다른 terminal 상태 → `st.rerun()`
8. pending 유지 → `time.sleep(3)` + `st.rerun()` (3초 간격 폴링)

### 3-8. 포스터 버튼 disabled 처리

```python
poster_disabled = poster_waiting_for_image()
col_poster.button("포스터 생성", ..., disabled=poster_disabled)
if poster_disabled:
    st.caption("이미지 작업이 완료되면 포스터 생성이 활성화됩니다.")
```

---

## 4. 현재 환경 상태

| 항목 | 값 |
|---|---|
| conda env | `sprint_high` |
| FastAPI | `:8010` (재시작 완료) |
| Streamlit | `:8501` (재시작 완료) |
| Ollama | `:11434` (qwen2.5:7b) |
| ComfyUI | `:8188` (FLUX.1 schnell fp8) |
| HyperCLOVA SEED | `:11501` — `TEXT_WORKER_CMD`로 on-demand 기동, 1.5B 실호출 검증 완료 |
| GPU_WORKER_MODE | `exclusive` |
| GPU_WORKER_IDLE_TIMEOUT_SECONDS | `600` |
| 캐시 경로 | `data/runtime/cache/{text,image}/` |
| 외부 접근 | `https://34.27.86.182:8443` |
| 루트 파일시스템 | 약 `290G` total / `234G` available (`df -h /` 기준) |
| 미커밋 변경 | `tools/hyperclova_seed_openai_server.py`, night2/night3 문서 갱신 |

> **주의**: 자동 폴링 구현은 이미 로컬 커밋(`3640000`)됐지만 아직 `origin/main`에는 push되지 않은 상태입니다. 현재 추가 변경(`tools/hyperclova_seed_openai_server.py`, 문서)은 미커밋입니다.
> ```bash
> cd /home/leetaeho/ai_07_high/deskad_keyboard_demo
> git status --short --branch
> git diff --stat
> ```

---

## 5. 검증 결과 (이번 세션)

| 항목 | 결과 |
|---|---|
| `py_compile tools/hyperclova_seed_openai_server.py streamlit_app.py backend/ai.py backend/main.py` | ✅ |
| `scan_secrets --all` | ✅ clean (121 files) |
| 폴링 로직 구현 완료 | ✅ |
| 포스터 버튼 disabled 처리 | ✅ |
| `current_image_job_id()` 안전망 | ✅ |
| HF gated repo 1.5B 접근 | ✅ `config.json` 다운로드 성공 |
| HyperCLOVA 1.5B copy 실호출 | ✅ `/ai/copy/experiment?force_regen=true` 응답 `status: ok` |
| 서버 재시작 | ✅ `bash start.sh --restart` 완료 |

---

## 6. 다음 세션 차기 작업

상세 계획: `docs/next_work_2026-06-01-night3.md`

### P0 (즉시)
- **현재 미커밋 변경 정리** — `tools/hyperclova_seed_openai_server.py` + 문서 변경 커밋 여부 결정
- **자동 폴링 UI 실검증** — 브라우저에서 pending → completed → 포스터 버튼 활성화 확인
- **OpenAI 이미지 백엔드 실검증** — `OPENAI_API_KEY` 설정 후 실제 이미지 생성 확인

### P1 (UX)
- 노션 reference 다운로드 + grid 미리보기
- keyboard_layout repo clone

### P2 (인프라)
- OpenAI 이미지 백엔드 실검증
- exclusive worker 전환 실검증
- idle unload 실검증

---

## 7. 새 대화창 시작 프롬프트

```
docs/project_handoff_2026-06-01-night3.md 와 docs/next_work_2026-06-01-night3.md 읽고 작업 진행해줘.
```
