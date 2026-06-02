# DeskAd AI Studio - 다음 작업 계획 (2026-05-29 야간 기준)

작성일: 2026-05-29 (야간)
기준 브랜치: `taeho` (PR #6 open)

이 문서는 `docs/next_work_2026-05-29.md` (오전) 를 **확장 대체** 한다. 오전 P0 회귀 픽스 4건 (#0-1 ~ #0-4) 은 PR #6 에 포함되어 있고, 사용자가 야간에 신규 보고한 9건이 새로운 우선순위 큐를 형성한다.

자세한 진단 / 재현 / 추정 원인은 `docs/project_handoff_2026-05-29-night.md §4 ~ §5` 참조.

---

## 0. 직전 완료 작업 요약 (PR #6)

| 회귀 픽스 | 위치 | 상태 |
|---|---|---|
| §0-1 layout 5종 UI 노출 | `streamlit_app.py` | ✅ PR #6 |
| §0-2 87/104 plate/assembly 데이터 | `data/drawings/` + assembly json | ✅ PR #6 |
| §0-3 키보드 측면 렌더링 회귀 | `backend/renderer.py:_add_keyboard_detailed` | ✅ PR #6 (사용자 시각 검수 대기) |
| §0-4 monitor arm double_joint 회귀 | `backend/renderer.py:_add_monitor_arm` | ✅ PR #6 (사용자 시각 검수 대기) |

---

## 1. P0 — 즉시 처리 (사용자 신규 보고)

### 1-1. HyperCLOVA X 연동 (사용자 #1)

| 위치 | 현재 | 수정 |
|---|---|---|
| `.env:HYPERCLOVA_BASE_URL` | 비어있음 | 옵션 A: 로컬 vLLM/Ollama 의 OpenAI 호환 endpoint / 옵션 B: `https://clovastudio.stream.ntruss.com` |
| `.env:HYPERCLOVA_USE_DIRECT_API` | false | 옵션 B 채택 시 true |
| `.env:HYPERCLOVA_API_KEY` | 비어있음 | 옵션 B 채택 시 X-NCP-CLOVASTUDIO-API-KEY |
| `.env:HYPERCLOVA_MODEL` | 비어있음 | 옵션 A: HF 모델 ID / 옵션 B: hyperclova-x 등 ClovaStudio 모델명 |

**참고 자료 (사용자 제공, 차기 세션에서 fetch)**:
- Naver tech blog: https://clova.ai/tech-blog/ai-%EC%83%9D%ED%83%9C%EA%B3%84%EC%97%90-%EC%94%A8%EC%95%97%EC%9D%84-%EB%BF%8C%EB%A6%AC%EB%8B%A4-%EC%83%81%EC%97%85%EC%9A%A9-%EC%98%A4%ED%94%88%EC%86%8C%EC%8A%A4-ai-hyperclova-x-seed
- 노션 1: https://www.notion.so/b757356fc5cb831ea366012ba4353f15
- 노션 2 (LLM 3D): https://www.notion.so/LLM-3D-5d17356fc5cb8260a7d581d018809caa

**작업 순서**:
1. WebFetch 또는 노션 MCP 로 위 3개 자료 읽고 HyperCLOVA X Seed 의 정확한 호스팅 방식 / 라이선스 / 모델 ID 파악
2. 옵션 결정 (Seed 로컬 vs ClovaStudio 게이트웨이)
3. `.env` 업데이트 (`tools/scan_secrets.py` 통과 확인)
4. `/ai/copy` 와 `/ai/copy/experiment` 로 HyperCLOVA 실호출 검증
5. `tools/scan_secrets.py` 패턴에 ClovaStudio 키 형식 추가 검토

### 1-2. image prompt 에 layout 정보 추가 (사용자 #6)

| 위치 | 현재 | 수정 |
|---|---|---|
| `backend/ai.py:build_image_prompt` (400-427) | `layout` 필드 참조 0건 | payload["layout"] 을 prompt 에 명시 |
| ComfyUI workflow positive prompt | 동일 | layout 정보 주입 |

**구체 변경**:
```python
layout = sanitize_user_text(payload.get("layout", "65"), limit=10)
layout_label = {
    "60": "60% compact (61 keys, no F-row no arrows)",
    "65": "65% compact (67 keys, F-row only on layer)",
    "75": "75% compact with F-row + arrows",
    "87": "TKL tenkeyless 87 keys with F-row + arrows + nav cluster",
    "104": "full-size 104 keys with numpad",
}.get(layout, layout + "% custom keyboard")
# build prompt:
#   f"keyboard layout: {layout_label}, ..."
```

### 1-3. image prompt 에 색상/제품명 컬러 단서 추가 (사용자 #5)

| 위치 | 현재 | 수정 |
|---|---|---|
| `backend/ai.py:build_image_prompt` | case/keycap/accent HEX 빠짐 | hex → 한국어 색상명 매핑 추가, prompt 에 명시 |

**구체 변경**:
1. `backend/ai.py` 에 HEX → 색상명 매핑 (예: `#c8c1b2` → "warm cream beige") 추가
2. `build_image_prompt` 에 `case_color`, `keycap_color`, `accent_keycap_color`, `pcb_color` HEX → 색상명 적용 후 prompt 에 포함
3. (선택) Step 1 의 `product_name` 텍스트에서 한국어 색상 키워드를 추출해 case_color 기본값 동기화

**ComfyUI workflow 매핑**:
- `_load_comfyui_workflow` (ai.py:794) 가 워크플로우의 prompt 노드를 치환할 때 색상 정보도 함께 주입

### 1-4. UI 광고문구 + 한글 모델 비교 병합 + 선택 (사용자 #2)

| 위치 | 현재 | 수정 |
|---|---|---|
| `streamlit_app.py:1093-1117` | 4개 버튼 분리 | "광고 문구 생성" 단일 버튼으로 통합 → 내부적으로 `/ai/copy/experiment` 호출 |
| 결과 표시 (1255-1278) | copy_result + 별도 expander | N개 카드 grid + "이 문구 사용" 버튼 |
| 세션 상태 흐름 | copy_result 단일 | 사용자 선택 시 copy_result 로 승격 → 이후 포스터/이미지 단계 반영 |

**HyperCLOVA 연결 후 의미 (1-1 의존)**. HyperCLOVA 연결 전이라도 UI 병합은 진행 가능.

---

## 2. P1 — UX 보완

### 2-1. 이미지 작업 자동 폴링 + 명확한 흐름 (사용자 #3)

| 위치 | 현재 | 수정 |
|---|---|---|
| `streamlit_app.py:1207-1244` | "이미지 작업 상태 갱신" 수동 버튼 | 작업 생성 직후 자동 폴링 (5-10s interval) 시작, 완료 시 자동 알림 |
| 포스터 생성 버튼 (1112) | 항상 활성 | 이미지 작업 큐잉됐다면 완료 전 비활성 또는 안내 |
| PPT 생성 | 미구현 | 별도 작업 (python-pptx, /ai/ppt endpoint) |

**구현 가이드**:
- Streamlit `st.empty()` placeholder + `time.sleep` 루프, 또는 `st.fragment(run_every=10)` (Streamlit 1.33+)
- 완료 후 자동 `generate_poster()` 호출 옵션
- "작업 내역 보기" expander 를 작업 진행 전부터 노출 (queued / running / completed 상태 chip)

### 2-2. 노션 reference 다운로드 + 미리보기 grid (사용자 #7)

| 위치 | 현재 | 수정 |
|---|---|---|
| `data/reference_assets.json` (12건) | 전부 `downloaded: False` | `python tools/download_notion_references.py` 실행 → 로컬 다운로드 |
| `streamlit_app.py:842-859` (다운로드된 도면 selectbox) | path 만 표시 | 썸네일 grid + 라벨 + 라이선스 + 출처 URL |
| 노션 추가 자료 | 미수집 | 사용자 제공 노션 페이지 2개 fetch 해서 reference_assets.json 확장 |

### 2-3. keyboard_layout repo 연결 (사용자 #8)

| 위치 | 현재 | 수정 |
|---|---|---|
| `backend/plates.py:DEFAULT_REPO_PATH` | `C:/tmp/keyboard_layout` (Windows!) | `/opt/shared_data/keyboard_layout` 또는 사용자 지정 |
| `.env:KEYBOARD_LAYOUT_REPO_PATH` | 미설정 | 설정 후 `/plates` 가 카탈로그 반환하는지 확인 |
| 외부 repo | 미clone | `git clone https://github.com/naraku010/keyboard_layout <path>` |

**검증**:
```bash
git clone https://github.com/naraku010/keyboard_layout /opt/shared_data/keyboard_layout
echo "KEYBOARD_LAYOUT_REPO_PATH=/opt/shared_data/keyboard_layout" >> .env
bash start.sh --restart
curl -s 'http://127.0.0.1:8010/plates?limit=10' | python3 -m json.tool
curl -s 'http://127.0.0.1:8010/plates/brands' | python3 -m json.tool
```

기대: `plates` 가 비어있지 않고 brand 목록 노출. UI 의 도면 라이브러리에도 표시되는지 확인.

---

## 3. P2 — 인프라 확장

### 3-1. STEP converter (사용자 #4)

| 위치 | 현재 | 수정 |
|---|---|---|
| `.env:STEP_CONVERTER_CMD` | 비어있음 | trimesh 명령어 1줄 |
| `sprint_high` env | trimesh 미설치 | `conda run -n sprint_high pip install "trimesh[all]"` |
| `backend/cad.py:_run_step_converter` | command 분기 OK | 변경 없음 |

**구체 명령어**:
```bash
conda run -n sprint_high pip install "trimesh[all]"
# .env 에 추가
STEP_CONVERTER_CMD=python -c "import trimesh,sys; s=trimesh.load(sys.argv[1]); s.export(sys.argv[2])" {input} {output}
```

**검증**: 작은 .step 파일 업로드 → /render/uploaded-model 응답에 STEP → GLB 변환 메시지

### 3-2. API 응답 캐싱 (사용자 #9)

| Endpoint | 현재 | 캐싱 전략 |
|---|---|---|
| `/ai/providers` | 매 호출 재계산 | in-memory TTL 60s |
| `/layouts` | 파일 glob 매번 | in-memory TTL 300s |
| `/render/desk-setup` | 매 호출 GLB 재생성 | payload SHA256 hash → `/static/cache/<hash>.glb` 파일 캐싱 |
| `/ai/copy` (deterministic seed) | 매 호출 LLM 재호출 | payload+provider hash → 결과 캐싱 TTL 60s |
| `/plates` | `lru_cache` 있음 | 변경 없음 |

**구현 옵션**:
- `fastapi-cache2` (Redis or in-memory)
- 단순 `functools.lru_cache` + TTL wrapper (TTLCache from cachetools)
- ETag / Cache-Control 헤더 (클라이언트 캐싱 유도)

### 3-3. 모델 라우팅 정리 (next_work_2026-05-29-night §5 진단 결과)

| 슬롯 | 현재 | 옵션 |
|---|---|---|
| kanana | qwen2.5:7b 로 라우팅 | A: Ollama 에 EEVE 등 한국어 모델 pull / B: HyperCLOVA Seed 통합 후 분리 |
| midm | qwen2.5:7b 로 라우팅 | A: 동일 / B: 동일 |
| local | qwen2.5:7b | 변경 없음 (의도된 단일 로컬 모델) |
| hyperclova | 미설정 | 1-1 작업으로 분리 |

UI 측에서도 `/ai/providers` 응답에 "actually serves: qwen2.5:7b" 같은 별칭 정보를 표시하면 명확.

---

## 4. 보류 / 별도 회의

- M5 실 Kanana / Mi:dm 가중치 분리 (HF 다운로드 + GPU 메모리 스케줄)
- M6 ControlNet (canny/depth)
- M7 IP-Adapter / FaceID 스타일
- M8 LoRA 슬롯 + 학습 파이프라인
- M9 FLUX dev / SDXL 추가
- M10 OCR + Canny IoU 품질 워커
- U11 즐겨찾기 / 갤러리 영속화
- U12 다국어 UI (영/일)
- U13 모바일 반응형
- U14 다크 모드

---

## 5. 작업 순서 권장 (차기 세션)

```text
P0 (사용자 신규)
 ├─→ 1-1 HyperCLOVA X Seed (참고 자료 fetch → 옵션 결정 → .env)
 ├─→ 1-2 image prompt 에 layout 추가  (작은 코드 변경, 큰 영향)
 ├─→ 1-3 image prompt 에 색상 추가     (1-2 와 묶음 — 같은 함수)
 └─→ 1-4 UI 광고문구 + 모델비교 병합   (1-1 완료 후 의미)
P1 (UX)
 ├─→ 2-1 이미지 작업 자동 폴링 + 흐름
 ├─→ 2-2 노션 reference 다운로드 + grid
 └─→ 2-3 keyboard_layout repo clone + .env
P2 (인프라)
 ├─→ 3-1 STEP converter (trimesh)
 ├─→ 3-2 API 응답 캐싱
 └─→ 3-3 모델 라우팅 정리 / alias 표시
```

발표/데모 우선이면 **1-2 → 1-3 → 2-3 → 2-2** 까지가 시각 영향 큼.
HyperCLOVA 실연동이 데모 핵심이면 **1-1 → 1-2 → 1-3 → 1-4** 순서.

---

## 6. 검증 명령 한 줄

```bash
cd /home/leetaeho/ai_07_high/deskad_keyboard_demo && \
conda run -n sprint_high python -B -m py_compile backend/*.py streamlit_app.py tools/scan_secrets.py && \
conda run -n sprint_high python tools/scan_secrets.py --all && \
bash start.sh --restart && \
curl -s http://127.0.0.1:8010/health && echo && \
curl -s http://127.0.0.1:8010/ai/providers | python3 -c "import sys,json; d=json.load(sys.stdin); [print(f\"  {p['id']:12} configured={p['configured']:1} model={p['model']}\") for p in d['providers']]" && \
curl -s http://127.0.0.1:11434/api/tags | python3 -c "import sys,json; print('Ollama models:', [m['name'] for m in json.load(sys.stdin)['models']])"
```

기대 출력 (현재):
- `clean`
- providers: openai/hyperclova 미설정, kanana/midm/local 모두 qwen2.5:7b
- Ollama: `['qwen2.5:7b']`

차기 세션 §1-1 완료 후 기대:
- `hyperclova` configured=True, model=HyperCLOVA X Seed 또는 hyperclova-x
- kanana/midm 슬롯은 §3-3 결정에 따라 (분리 시 다른 model, alias 표시 시 동일 model + 안내)
