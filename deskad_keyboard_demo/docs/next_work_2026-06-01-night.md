# DeskAd AI Studio - 다음 작업 계획 (2026-06-01 야간 기준)

작성일: 2026-06-01  
기준 브랜치: `taeho` (PR #7 open)  
직전 문서: `docs/next_work_2026-06-01.md` (이 문서로 대체)

---

## 0. 직전 완료 작업 요약

| 이슈 | 위치 | 상태 |
|---|---|---|
| GPU 런타임 캐시 + on-demand worker unload | `backend/result_cache.py`, `backend/runtime_workers.py`, `backend/ai.py` | ✅ PR #7 |
| streamlit 광고 문구 picker 카드 UI | `streamlit_app.py` (`render_copy_experiment_picker`) | ✅ PR #7 |
| HyperCLOVA SEED OpenAI 서버 스크립트 | `tools/hyperclova_seed_openai_server.py` | ✅ PR #7 |
| exclusive GPU worker 모드 기본 적용 | `.env GPU_WORKER_MODE=exclusive` | ✅ 적용 중 |

---

## 1. P0 — 즉시

### 1-1. HyperCLOVA X SEED 실제 연결 검증 (이슈 #1)

**현황**: `tools/hyperclova_seed_openai_server.py` 스크립트와 `is_loopback_base_url()` 연동 코드는 완성됨.  
Hugging Face gated repo 약관 승인 + `HF_TOKEN` 설정 후 실제 모델 다운로드/호출이 필요.

**작업 순서**:
1. HF 약관 승인: `https://huggingface.co/naver-hyperclovax/HyperCLOVAX-SEED-Text-Instruct-1.5B`
2. `.env` 업데이트:
   ```bash
   HF_TOKEN=<token>
   HYPERCLOVA_BASE_URL=http://127.0.0.1:11501/v1
   HYPERCLOVA_MODEL=naver-hyperclovax/HyperCLOVAX-SEED-Text-Instruct-1.5B
   ```
3. text worker 수동 기동: `conda run -n sprint_high python tools/hyperclova_seed_openai_server.py`
4. 확인: `curl -s http://127.0.0.1:11501/health && curl -s http://127.0.0.1:8010/ai/providers`
5. `POST /ai/copy/experiment` 실호출 → HyperCLOVA 카드가 `status: ok`로 반환되는지 확인

**VRAM 주의**: ComfyUI(FLUX ≈ 14GB) + HyperCLOVA SEED 1.5B(≈ 4GB) = 18GB. L4 24GB에서 동시 실행 가능하나 `GPU_WORKER_MODE=exclusive`(현재 기본값)이므로 text 요청 시 ComfyUI가 자동 stop됨.

---

## 2. P1 — UX 개선

### 2-1. 이미지 작업 자동 폴링 + 포스터 흐름 연결 (이슈 #2)

**현황**: 이미지 작업 제출 후 결과 확인이 수동. 포스터 생성 버튼이 이미지 완료 여부와 무관하게 활성화.

**구현 방향**:
- `st.empty()` + `time.sleep(3)` 루프 or `st.fragment` + auto-refresh
- `GET /ai/image/jobs/{job_id}` 폴링 → `status == "completed"` 감지 시 이미지 표시 + 포스터 버튼 활성화
- timeout 처리 (최대 3분)
- cache hit job은 상태가 이미 `queued`이므로 ComfyUI 폴링도 필요

**위치**: `streamlit_app.py:refresh_image_job()` 확장, Step 4 결과 표시 영역

---

### 2-2. 노션 reference 다운로드 + grid 미리보기 (이슈 #3)

**현황**: `tools/download_notion_references.py` 존재, 실행 여부 미확인.

**작업**:
1. `python tools/download_notion_references.py` 실행 후 오류 수정
2. `streamlit_app.py` — Step 1 또는 사이드바에 레퍼런스 이미지 grid 미리보기 추가

---

### 2-3. keyboard_layout repo clone (이슈 #4)

```bash
git clone https://github.com/naraku010/keyboard_layout /opt/shared_data/keyboard_layout
```
`.env`에 `KEYBOARD_LAYOUT_REPO_PATH=/opt/shared_data/keyboard_layout` 추가.

---

## 3. P2 — 인프라

### 3-1. STEP converter 설치 (이슈 #5)

```bash
conda run -n sprint_high pip install "trimesh[all]"
```
`.env`에 `STEP_CONVERTER_CMD` 추가.

---

### 3-2. exclusive worker 전환 실검증 (이슈 #6)

현재 `GPU_WORKER_MODE=exclusive`가 `.env`에 적용됐지만, TEXT_WORKER_CMD가 빈 값이므로 text worker start는 no-op. HyperCLOVA SEED 연결(1-1) 후에 실검증 가능.

**검증 시나리오**:
```bash
# 사전: ComfyUI active 상태
nvidia-smi  # FLUX weight VRAM 확인
systemctl is-active comfyui

# text 요청 (cache miss) → ComfyUI stop → text worker start 로그 확인
curl -sf -X POST "http://127.0.0.1:8010/ai/copy?force_regen=true" \
  -H "Content-Type: application/json" \
  -d '{"product_name":"테스트"}'
cat fastapi.log | grep -E "\[exclusive\]|text worker|image worker"
nvidia-smi  # VRAM 감소 확인

# 이미지 요청 (cache miss) → text worker stop → ComfyUI start
curl -sf -X POST "http://127.0.0.1:8010/ai/image/jobs?force_regen=true" \
  -H "Content-Type: application/json" \
  -d '{"product_name":"테스트"}'
cat fastapi.log | grep -E "\[exclusive\]|text worker|image worker"
nvidia-smi  # VRAM 복귀 확인
```

---

### 3-3. idle unload 실검증 (이슈 #7)

```bash
# 단기 테스트용 timeout
GPU_WORKER_IDLE_TIMEOUT_SECONDS=30 bash start.sh --restart

# 요청 1회 후 40~45초 대기
# fastapi.log에서 "idle ... stopping" 로그 확인
# nvidia-smi에서 해당 worker VRAM 해제 확인
```

---

## 4. 유보 사항

| 항목 | 상태 |
|---|---|
| 모델 라우팅 실분리 (kanana/midm 독립 슬롯) | HyperCLOVA 연결(1-1) 완료 후 의미 있음 |
| `product_name` 텍스트에서 한국어 색상 키워드 추출 → `case_color` 기본값 동기화 | 선택 작업 |
| API 응답 캐싱 (`/ai/providers` TTL 60s, `/layouts` TTL 300s) | 이슈 #9. result_cache 완료 후 낮은 우선순위 |

---

## 5. 환경 확인 체크리스트 (새 세션 시작 시)

```bash
# 서버 상태
curl -s http://localhost:8010/health
systemctl is-active comfyui ollama

# GPU worker 모드 확인
grep GPU_WORKER_MODE deskad_keyboard_demo/.env

# 브랜치
git -C /home/leetaeho/ai_07_high branch --show-current  # taeho 여야 함

# 비밀 스캔
cd /home/leetaeho/ai_07_high/deskad_keyboard_demo && python tools/scan_secrets.py --all

# 캐시 상태 확인
ls data/runtime/cache/text/ | wc -l
ls data/runtime/cache/image/ | wc -l
```
