# DeskAd AI Studio - 다음 작업 계획 (2026-06-01 야간 4차 기준)

작성일: 2026-06-01  
기준 브랜치: `main` (로컬 `6f9f6f3` + 미커밋 변경)  
직전 문서: `docs/next_work_2026-06-01-night3.md` (이 문서로 대체)  
설계 레퍼런스: `docs/project_handoff_2026-06-01-night4.md` 6절 (모델/UI/3D)

---

## 0. 직전 완료 작업 (이번 세션)

| 항목 | 상태 |
|---|---|
| 자동 폴링 12개 버그 수정 (fragment 폴링 + None sentinel + 버튼 게이트 + elif) | ✅ 검증 완료 |
| kanana/midm qwen 오염 → 슬롯 비활성화 | ✅ |
| 한국어 프롬프트 인젝션 패턴 5종 | ✅ |
| 텍스트 워커 provider별 라우팅 (`_uses_managed_text_worker`) | ✅ |
| ComfyUI 워커 작업 후 해제 (`IMAGE_WORKER_STOP_AFTER_JOB`) | ✅ |
| NOTION_TOKEN 제외 (미사용) | ✅ |

> **미커밋 상태** — handoff 8절 커밋 가이드 먼저 실행.

---

## 즉시 — 새 세션 시작 전

```bash
cd /home/leetaeho/ai_07_high/deskad_keyboard_demo

# 미커밋 변경 확인 + 커밋 (handoff 8절)
git status --short
git diff --stat

# 서버/라우팅 상태
curl -s http://127.0.0.1:8010/health | python3 -m json.tool --no-indent | head -3
curl -s http://127.0.0.1:8010/ai/providers | python3 -m json.tool | grep -E '"name"|"runtime_name"|"configured"'
```

---

## 1. P0 — 실검증 (이번 주)

### 1-1. 자동 폴링 UI 실검증

코드 수정은 완료, 브라우저 동작 미검증.
1. Streamlit `:8501` → 이미지 작업 제출
2. "자동 갱신 중 · {status} · N초" 캡션 + 3초 간격 갱신 확인 (UI 멈춤 없어야 함)
3. 포스터 버튼 disabled + 안내 캡션 확인
4. completed 시 토스트 + 버튼 자동 활성화 확인
5. **타임아웃(180초)** 동작 확인 — 경고 후 버튼 재활성화(영구 비활성 아님)

### 1-2. OpenAI 이미지 백엔드 실검증

```bash
# .env
OPENAI_API_KEY=<key>
OPENAI_IMAGE_MODEL=dall-e-3
IMAGE_MODEL_BACKEND=auto

bash start.sh --restart
curl -sf -X POST "http://127.0.0.1:8010/ai/image/jobs" \
  -H "Content-Type: application/json" -d '{"product_name":"테스트 키보드"}' \
  | python3 -m json.tool | grep -E '"backend_config"|"openai_image_model"'
```

---

## 2. P1 — 카피 정책 (이번 주, 노션 ⭐⭐)

### 2-1. `copy_policy.py` 금지어 30종 + 채널 3종 (PART 7-Y)

`backend/copy_policy.py` `GLOBAL_REPLACEMENTS` 확장:
- 의약품 표현: "치료", "완치", "효과 입증"
- 비교 광고: "○사보다", "○도 못따라온"
- 과장 부사: "극한", "독보적", "최고의"
- 출처 미상 수치: "○배 더", "N% 효과"

`CHANNEL_POLICY`에 "네이버 검색광고" / "카카오 채널" / "유튜브 쇼츠" 추가.  
금지어 단순 replace → 정규식 경계(`\b1위\b`)로 "국내1위"(공백 없음) 감지.

### 2-2. `ChatCompletionAdapter` retry/백오프 (노션 ⭐⭐)

HCX 5xx 시 즉시 fallback → max_retries=3 + exponential backoff + jitter.

---

## 3. P2 — kanana/midm 실모델 연동 (인프라)

> 현재 슬롯 비활성화 상태. 실제 비교 실험하려면 vLLM 서빙 필요.

### 3-1. Kanana Nano 2.1B

```bash
conda run -n sprint_high pip install vllm
conda run -n sprint_high python -m vllm.entrypoints.openai.api_server \
    --model kakaocorp/kanana-nano-2.1b --port 11502 \
    --gpu-memory-utilization 0.4 --max-model-len 4096
```
```bash
# .env
KANANA_BASE_URL=http://127.0.0.1:11502/v1
KANANA_MODEL=kakaocorp/kanana-nano-2.1b
```

### 3-2. Mi:dm 2.0 Mini

```bash
conda run -n sprint_high python -m vllm.entrypoints.openai.api_server \
    --model K-intelligence/Midm-2.0-Mini-Instruct --port 11503 \
    --quantization awq --gpu-memory-utilization 0.5
```
```bash
# .env
MIDM_BASE_URL=http://127.0.0.1:11503/v1
MIDM_MODEL=K-intelligence/Midm-2.0-Mini-Instruct
```

> **VRAM 제약 (L4 24GB)**: FLUX(14GB)+HyperCLOVA(4GB)+Kanana(6GB) 동시 적재 불가.  
> `exclusive` 모드로 요청 시에만 해당 워커 기동. 텍스트 워커 라우팅(`_uses_managed_text_worker`)은 SEED만 관리하므로, kanana/midm용 워커는 별도 systemd/수동 관리 필요.

### 3-3. 검증

```bash
curl -s http://127.0.0.1:8010/ai/providers | python3 -m json.tool | \
  grep -E '"name"|"runtime_name"|"configured"'
# kanana runtime_name = kanana-nano-2.1b, midm = Midm-2.0-Mini-Instruct (qwen 아님)

curl -sf -X POST "http://127.0.0.1:8010/ai/copy/experiment?force_regen=true" \
  -H "Content-Type: application/json" \
  -d '{"product_name":"버건디 알루미늄 60% 키보드"}' \
  | python3 -m json.tool | grep -E '"provider"|"headline"'
```

---

## 4. P2 — GPU 품질 워커 (다음 주, 노션 ⭐⭐⭐)

`workers/quality_evaluator.py` 신설 — PART 7-U 게이트:
- CLIP-I (CLIPScore vs image_prompt), LPIPS, FID
- OCR (EasyOCR `kor`+`eng`) → 키캡 각인 정확도
- `IMAGE_QUALITY_STORE.save()` 업서트

의존성: `open_clip_torch`, `lpips`, `easyocr`

`backend/quality_gate.py:17` `ImageQualityReport`에 필드 추가: `mos_score` / `accepted` / `clip_score` / `fid_score` / `lpips_score`

교체 트리거 자동화 (`workers/trigger_monitor.py`): OCR<0.85 ×3연속 / MOS<3.5 누적 → 알람.

---

## 5. P3 — 3D 파이프라인 (노션 Part 2/5)

> 상세 설계: handoff 6-3절. 현재 `renderer.py` 절차적 GLB(1cm 기준) + `model-viewer` iframe만 존재.

1. **STEP 변환기 설치** (proxy fallback 해소):
   ```bash
   conda run -n sprint_high pip install "trimesh[all]"
   # .env: STEP_CONVERTER_CMD=python -c "import trimesh,sys; s=trimesh.load(sys.argv[1]); s.export(sys.argv[2])" {input} {output}
   ```
2. **입력 GLB 단위 검증** — `cad.py`에 1cm 기준 스케일 검증 (외부 STEP/GLB 정합)
3. **메시 최적화 파이프라인** — Draco + Meshopt + KTX2 (`gltf-transform optimize`, 셋업 <1MB)
4. **(V1) R3F 프론트** — three.js + R3F + drei, Streamlit iframe + postMessage 양방향
5. **(V1) Blender Eevee Next headless** — 고품질 렌더 옵션

---

## 6. 유보 사항

| 항목 | 상태 |
|---|---|
| HCX-DASH-002 vs HCX-005 디폴트 | 회의 확정 필요 (현재 HCX-005) |
| 노션 reference 다운로드 + grid 미리보기 | `tools/download_notion_references.py` 오류 수정 후 |
| keyboard_layout repo clone | `KEYBOARD_LAYOUT_REPO_PATH` 설정 |
| streamlit_app.py step별 모듈 분리 | 1400줄+ 단일 파일 |
| `docs/security.md` 갱신 | 5/29 이후 캐시/워커 변경 미반영 |
| 테스트/CI 부재 | `tests/` + GitHub Actions (`scan_secrets`+`py_compile`+`ruff`) |

---

## 7. 환경 확인 체크리스트 (새 세션)

```bash
git -C /home/leetaeho/ai_07_high log --oneline -3
curl -s http://localhost:8010/health | python3 -m json.tool --no-indent | head -3

# 모델 라우팅 (kanana/midm runtime_name이 qwen이면 재오염)
curl -s http://localhost:8010/ai/providers | python3 -m json.tool | \
  grep -E '"name"|"runtime_name"|"configured"'

grep -E "GPU_WORKER_MODE|IMAGE_WORKER_STOP_AFTER_JOB" deskad_keyboard_demo/.env
ls deskad_keyboard_demo/data/runtime/cache/{text,image}/ | wc -l

cd /home/leetaeho/ai_07_high/deskad_keyboard_demo && python tools/scan_secrets.py --all
```
