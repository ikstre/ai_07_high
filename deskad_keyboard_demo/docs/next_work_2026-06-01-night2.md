# DeskAd AI Studio - 다음 작업 계획 (2026-06-01 야간 2차 기준)

작성일: 2026-06-01  
기준 브랜치: `main` (PR #6 + PR #9 모두 merge 완료)  
직전 문서: `docs/next_work_2026-06-01-night.md` (이 문서로 대체)

---

## 0. 직전 완료 작업 요약

| PR | 내용 | 상태 |
|---|---|---|
| #6 | GPU 런타임 캐시 + exclusive worker + picker UI + P0 회귀 픽스 | ✅ merged |
| #9 | OpenAI 이미지 백엔드 + UI 반응형 개선 (PR #8 rebase) | ✅ merged |

**main 현재 커밋**: `4f3226e` (night2 문서 커밋, PR #9 merge commit은 `090df5e`)

---

## 즉시 — 새 세션 시작 전 필수

```bash
cd /home/leetaeho/ai_07_high/deskad_keyboard_demo
git checkout main && git pull origin main
bash start.sh --restart
curl -s http://127.0.0.1:8010/health
```

---

## 1. P0 — 즉시

### 1-1. HyperCLOVA X SEED 실제 연결 검증

**현황**: 2026-06-01 추가 검증 완료. HF gated repo 약관 승인 후 `HyperCLOVAX-SEED-Text-Instruct-1.5B`의 `config.json` 다운로드와 `/ai/copy/experiment?force_regen=true` HyperCLOVA 단독 실호출 모두 성공.

**현재 `.env` 적용값**:
```bash
HF_TOKEN=<set>
HYPERCLOVA_BASE_URL=http://127.0.0.1:11501/v1
HYPERCLOVA_MODEL=naver-hyperclovax/HyperCLOVAX-SEED-Text-Instruct-1.5B
HYPERCLOVA_USE_DIRECT_API=false
TEXT_WORKER_CMD="conda run -n sprint_high python tools/hyperclova_seed_openai_server.py"
```

**검증 결과**:
- HF token user: `ikstre`
- `curl -s http://127.0.0.1:8010/ai/providers`에서 HyperCLOVA model이 1.5B로 표시됨
- `POST /ai/copy/experiment?force_regen=true` + `{"providers":["hyperclova"]}` 응답에서 `provider: hyperclova`, `status: ok`, `copy.provider: hyperclova_x` 확인

**재현/회귀 검증 순서**:
1. 서버 재시작:
   ```bash
   bash start.sh --restart
   ```
2. 확인:
   ```bash
   curl -s http://127.0.0.1:8010/ai/providers | python3 -m json.tool
   curl -sS --max-time 900 -X POST 'http://127.0.0.1:8010/ai/copy/experiment?force_regen=true' \
     -H 'Content-Type: application/json' -d '{"providers":["hyperclova"]}' | python3 -m json.tool
   ```

**남은 점검**: exclusive worker/idle unload 실검증은 3-2, 3-3에서 계속 진행.

<details>
<summary>초기 연결 절차 기록</summary>

**작업 순서**:
1. HF 약관 승인: `https://huggingface.co/naver-hyperclovax/HyperCLOVAX-SEED-Text-Instruct-1.5B`
2. `.env` 추가:
   ```bash
   HF_TOKEN=<token>
   HYPERCLOVA_BASE_URL=http://127.0.0.1:11501/v1
   HYPERCLOVA_MODEL=naver-hyperclovax/HyperCLOVAX-SEED-Text-Instruct-1.5B
   TEXT_WORKER_CMD=conda run -n sprint_high python tools/hyperclova_seed_openai_server.py
   ```
3. 수동 기동 (첫 실행 시 HF 모델 다운로드):
   ```bash
   conda run -n sprint_high python tools/hyperclova_seed_openai_server.py
   ```
4. 확인:
   ```bash
   curl -s http://127.0.0.1:11501/health
   curl -s http://127.0.0.1:8010/ai/providers | python3 -m json.tool
   ```
5. `POST /ai/copy/experiment` 실호출 → HyperCLOVA 카드 `status: ok` 확인

**VRAM**: FLUX ≈ 14GB + HyperCLOVA 1.5B ≈ 4GB = 18GB.  
`GPU_WORKER_MODE=exclusive`이므로 text 요청 시 ComfyUI 자동 stop, 충돌 없음.

</details>

---

### 1-2. OpenAI 이미지 백엔드 실검증

**현황**: `generate_openai_image_reference()` 코드 완성 (PR #9 merge). 실호출 미검증.

**작업**:
1. `.env`에 추가:
   ```bash
   OPENAI_API_KEY=<key>
   OPENAI_IMAGE_MODEL=dall-e-3
   IMAGE_MODEL_BACKEND=auto
   ```
2. `POST /ai/image/jobs` 호출 후 `backend_config.openai_image_model: set` 확인
3. `POST /ai/poster` 응답에 `image_reference` 필드 존재, `local_image_reference` 미존재 확인
4. ComfyUI 없이 OpenAI만으로 포스터 합성 end-to-end 검증

---

## 2. P1 — UX 개선

### 2-1. 이미지 작업 자동 폴링 + 포스터 흐름 연결

**현황**: 이미지 제출 후 결과 확인 수동. 포스터 버튼 활성화 조건 없음.

**2026-06-01 추가 진행**:
- `streamlit_app.py`에 이미지 job 자동 폴링 상태(`image_polling_enabled`, `image_poll_started_at`, timeout) 추가
- 이미지 작업 생성 후 pending 상태면 3초 간격으로 `GET /ai/image/jobs/{job_id}` 자동 갱신
- 이미지 작업 완료 전에는 포스터 생성 버튼 비활성화
- `build_ad_payload()`가 완료된 image job만 `image_job_id`로 넘기도록 변경
- 완료된 ComfyUI job으로 `/ai/poster` 호출 시 `image_embedded: true` 확인

**구현 방향**:
- `streamlit_app.py:refresh_image_job()` 확장
- `st.empty()` 루프로 `GET /ai/image/jobs/{job_id}` 폴링, `status == "completed"` 시 자동 진행
- timeout 처리 (최대 3분), ComfyUI 오류 상태 표시
- cache hit job (`status: queued`)도 폴링 필요

---

### 2-2. 노션 reference 다운로드 + grid 미리보기

```bash
python tools/download_notion_references.py
```
오류 수정 후 `streamlit_app.py` Step 1 또는 사이드바에 grid 미리보기 추가.

---

### 2-3. keyboard_layout repo clone

```bash
git clone https://github.com/naraku010/keyboard_layout /opt/shared_data/keyboard_layout
```
`.env`에 `KEYBOARD_LAYOUT_REPO_PATH=/opt/shared_data/keyboard_layout` 추가.

---

## 3. P2 — 인프라

### 3-1. STEP converter 설치

```bash
conda run -n sprint_high pip install "trimesh[all]"
```
`.env`에 `STEP_CONVERTER_CMD` 추가.

---

### 3-2. exclusive worker 전환 실검증

HyperCLOVA SEED 연결(1-1) 완료 후 가능.

```bash
# ComfyUI active 상태에서 text 요청
nvidia-smi
curl -sf -X POST "http://127.0.0.1:8010/ai/copy?force_regen=true" \
  -H "Content-Type: application/json" -d '{"product_name":"테스트"}'
grep -E "\[exclusive\]|text worker|image worker" fastapi.log | tail -5
nvidia-smi  # VRAM 감소 확인

# 이미지 요청 → text worker stop + ComfyUI start
curl -sf -X POST "http://127.0.0.1:8010/ai/image/jobs?force_regen=true" \
  -H "Content-Type: application/json" -d '{"product_name":"테스트"}'
grep -E "\[exclusive\]|text worker|image worker" fastapi.log | tail -5
nvidia-smi  # VRAM 복귀 확인
```

---

### 3-3. idle unload 실검증

```bash
# 단기 테스트 (30초)
GPU_WORKER_IDLE_TIMEOUT_SECONDS=30 bash start.sh --restart
# 요청 1회 후 40초 대기 → fastapi.log에 "idle ... stopping" 확인
# nvidia-smi에서 VRAM 해제 확인
```

---

## 4. 유보 사항

| 항목 | 상태 |
|---|---|
| 모델 라우팅 실분리 (kanana/midm 독립 슬롯) | HyperCLOVA 연결(1-1) 후 의미 있음 |
| `product_name`에서 한국어 색상 키워드 추출 → `case_color` 기본값 동기화 | 선택 작업 |
| API 응답 캐싱 (`/ai/providers` TTL 60s, `/layouts` TTL 300s) | 낮은 우선순위 |

---

## 5. 환경 확인 체크리스트 (새 세션 시작 시)

```bash
# 브랜치 + 서버 상태
git -C /home/leetaeho/ai_07_high branch --show-current  # main 이어야 함
git -C /home/leetaeho/ai_07_high log --oneline -3
curl -s http://localhost:8010/health | python3 -m json.tool --no-indent | head -3
systemctl is-active comfyui ollama

# GPU worker 모드
grep GPU_WORKER_MODE deskad_keyboard_demo/.env

# 캐시 상태
ls deskad_keyboard_demo/data/runtime/cache/text/ | wc -l
ls deskad_keyboard_demo/data/runtime/cache/image/ | wc -l

# 비밀 스캔
cd /home/leetaeho/ai_07_high/deskad_keyboard_demo && python tools/scan_secrets.py --all
```
