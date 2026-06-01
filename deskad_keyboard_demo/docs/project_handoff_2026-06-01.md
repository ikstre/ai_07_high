# DeskAd AI Studio 인수인계 - 2026-06-01

작성일: 2026-06-01  
프로젝트 경로: `/home/leetaeho/ai_07_high/deskad_keyboard_demo`  
직전 문서: `docs/project_handoff_2026-05-29-night.md` + `docs/next_work_2026-05-29-night.md`  
기준 브랜치: `taeho` (PR #6 open, 자동 갱신됨)  

---

## 1. 이번 세션 한 줄 요약

야간 핸드오프 문서의 **P0 이슈 #5 + #6** (이미지 프롬프트 색상/레이아웃 누락) 을 `backend/ai.py` 에 반영.  
커밋 `d38a067` 이 taeho 브랜치에 push 되어 PR #6 에 자동 포함됨.

---

## 2. 이번 세션 작업 내용

### 2-1. 이슈 #6: image prompt에 layout 정보 추가

**문제**: `build_image_prompt()` 가 `payload["layout"]` 을 전혀 참조하지 않아, 60%~104% 레이아웃 차이가 생성 이미지에 반영되지 않음.

**수정 위치**: `backend/ai.py:400-410`, `462-500`

**추가된 코드**:
```python
LAYOUT_PROMPT_LABELS = {
    "60": "60% compact layout (61 keys, no function row, no dedicated arrow cluster, smallest footprint)",
    "65": "65% compact layout (67 keys, no function row but with right-side arrow cluster)",
    "75": "75% compact layout (84 keys, function row plus arrow cluster, gapless tight layout)",
    "87": "TKL tenkeyless layout (87 keys, full function row plus arrow cluster, no numpad)",
    "104": "full-size 100% layout (104 keys, function row plus arrow cluster plus right-side numpad)",
}
```

`build_image_prompt()` 내에 `f"Keyboard format: {layout_label}."` 절 추가.

---

### 2-2. 이슈 #5: image prompt에 색상 정보 추가

**문제**: case/keycap/accent HEX 값이 prompt에서 완전히 누락 → "크림 베이지" 상품명에도 검은 키보드가 생성됨.

**수정 위치**: `backend/ai.py:408-500`

**추가된 코드**:
- `_COLOR_ANCHORS`: 22개 RGB anchor + 영어 색상명 (`black`, `charcoal dark gray`, `warm cream beige`, `vivid crimson red` 등)
- `_hex_to_rgb(hex_value)`: HEX string → RGB tuple
- `describe_color(value)`: HEX → 가장 가까운 anchor 색상명. 저채도(max-min ≤ 12) 입력은 grayscale anchor(max-min ≤ 10)만 후보로 한정해 갈색 계열로 잘못 스냅되는 문제 방지.

`build_image_prompt()` 내에 `f"Color palette: {color_clause}."` 절 추가. `color_clause` 에는 case/primary keycaps/accent keycaps/PCB 색상이 포함됨.

---

### 2-3. ComfyUI 자동 반영 확인

`_load_comfyui_workflow()` 는 워크플로우 JSON의 `{prompt}` placeholder 를 `image_prompt` 로 치환하므로, `build_image_prompt()` 수정만으로 FLUX positive prompt 에도 자동 반영됨. ComfyUI 코드 별도 수정 불필요.

---

### 2-4. 커밋 정보

| 커밋 | 메시지 |
|---|---|
| `d38a067` | `fix(p0): 이미지 프롬프트에 layout + 색상 hex→이름 매핑 (#5 #6)` |

---

## 3. 검증 결과

### 자동 검증 (이번 세션 완료)

| 항목 | 결과 |
|---|---|
| `python -m py_compile backend/ai.py` | ✅ 통과 |
| `tools/scan_secrets.py --all` | ✅ 108 files clean |
| `bash start.sh --restart` | ✅ FastAPI(:8010) + Streamlit(:8501) 재시작 성공, ComfyUI/Ollama systemd active 유지 |
| `GET /health` | ✅ 200 |

### 응답 내용 검증 (이번 세션 완료)

| 테스트 케이스 | 확인 내용 | 결과 |
|---|---|---|
| layout=65, case=#c8c1b2, keycap=#f4ead7, accent=#6f8faf | "65% compact layout (67 keys...)", "case/housing warm cream beige (#c8c1b2), primary keycaps ivory off-white (#f4ead7), accent keycaps muted slate blue (#6f8faf)" | ✅ |
| layout=104, case=#1a1a1a, keycap=#ffffff, accent=#ff0000 | "full-size 100% layout (104 keys...)", "case/housing charcoal dark gray (#1a1a1a), primary keycaps pure white (#ffffff), accent keycaps vivid crimson red (#ff0000)" | ✅ |

### 사용자 검증 필요 (차기 세션)

| 항목 | 확인 방법 |
|---|---|
| 실제 ComfyUI 이미지 생성 결과에 레이아웃이 시각적으로 반영되는지 | UI에서 60% / 104% 각각 이미지 생성 후 육안 비교 |
| 색상 palette가 생성 이미지에 실제로 반영되는지 | 고대비 색상 조합(흰 케이스+빨간 악센트 등)으로 이미지 생성 후 확인 |
| 회귀 없음: layout 미선택 시(기본값 "65") 정상 동작 | layout 드롭다운 기본값으로 이미지 생성 |

---

## 4. PR 상태

| PR | 상태 | 내용 |
|---|---|---|
| #4 | merged | M1 ComfyUI systemd + start.sh 워커 의존성 체크 |
| #5 | merged | U1 stepper + U3 썸네일 + PR 자동화 스크립트 |
| #6 | **open** (`d38a067`) | P0 회귀 픽스 4건 + 이미지 prompt 색상/레이아웃 (#5 #6) + 인수인계 문서 |

PR #6 은 taeho 브랜치의 모든 현행 커밋을 포함. 머지 시 main 에 즉시 반영.

---

## 5. 다음 세션 차기 작업

상세 계획: `docs/next_work_2026-06-01.md`

### P0 (즉시)

| 번호 | 작업 | 위치 |
|---|---|---|
| #1 | HyperCLOVA X Seed 통합 | `.env` + `backend/llm_adapters.py` |
| #2 | 광고 문구 UI 병합 + 선택 | `streamlit_app.py:1093-1117`, `1257-1278` |

### P1 (UX)

| 번호 | 작업 | 위치 |
|---|---|---|
| #3 | 이미지 작업 자동 폴링 + 포스터 흐름 연결 | `streamlit_app.py` |
| #7 | 노션 reference 다운로드 실행 + grid 미리보기 | `tools/download_notion_references.py` |
| #8 | keyboard_layout repo clone + `.env` 설정 | `KEYBOARD_LAYOUT_REPO_PATH` |

### P2 (인프라)

| 번호 | 작업 | 내용 |
|---|---|---|
| #4 | STEP converter: trimesh 설치 + `.env` 설정 | `conda run -n sprint_high pip install "trimesh[all]"` |
| #9 | API 응답 캐싱 | `/ai/providers`(TTL 60s), `/layouts`(TTL 300s), `/render/desk-setup`(GLB 캐시) |

---

## 6. 환경 메모

| 항목 | 값 |
|---|---|
| conda env | `sprint_high` |
| FastAPI | `:8010` |
| Streamlit | `:8501` |
| Ollama | `:11434` (qwen2.5:7b — kanana/midm/local 슬롯 모두 동일 모델로 라우팅) |
| ComfyUI | `:8188` (FLUX.1 schnell fp8) |
| 외부 접근 | `https://34.27.86.182:8443` (nginx basic auth + TLS) |
| GITHUB_TOKEN | `.env` 에서만 로드, 출력/커밋 절대 금지 |

---

## 7. 새 대화창 시작 프롬프트

```
docs/project_handoff_2026-06-01.md 와 docs/next_work_2026-06-01.md 읽고 작업 진행해줘.
```
