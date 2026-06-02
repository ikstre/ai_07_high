# DeskAd AI Studio 인수인계 문서 - 2026-05-29

작성일: 2026-05-29
프로젝트 경로: `/home/leetaeho/ai_07_high/deskad_keyboard_demo`
현재 작업 브랜치: `taeho` (HEAD: `4b82216 feat(ui): U3 포스터 템플릿 4종 inline SVG 썸네일`)

이 문서는 `docs/project_handoff_2026-05-28.md` 이후의 작업 + 사용자가 직접 테스트하면서 발견한 회귀/누락 이슈를 정리한다. 새 대화창은 §10 "최신 새 대화창 시작 프롬프트" 부터 읽으면 된다.

## 1. 이번 세션 한 줄 요약

- 미커밋 보안/LLM/이미지 작업을 2 commit으로 정리 → `origin/webdemo` 머지 → `taeho` 통합 (PR #4 머지 완료, main = `03a7bbb`).
- M1 (ComfyUI systemd 서비스) + U1 (4단계 stepper) + U3 (포스터 템플릿 SVG 썸네일) + PR 자동화 스크립트 추가 (PR #5 open).
- 사용자가 직접 모델/렌더링 테스트해서 발견한 시각/회귀 이슈 다수. 차기 작업의 우선순위가 "기능 추가"에서 "회귀 픽스 + 데이터 보강" 으로 이동.

## 2. PR 상태

| PR | 상태 | 내용 |
|---|---|---|
| #4 | merged (`03a7bbb`) | M1 ComfyUI systemd + start.sh 워커 의존성 체크 + API 포트 정합 |
| #5 | open | U1 stepper, U3 템플릿 썸네일, tools/push_and_open_pr.sh, 본 핸드오프 문서 |

PR #5 머지 후 main = U1 + U3 까지 반영. 차기 PR 부터는 §7 의 회귀 픽스로 들어간다.

## 3. 추가/변경된 파일 (PR #4 머지 이후)

추가:

- `tools/systemd/comfyui.service` (PR #4) - systemd unit
- `tools/push_and_open_pr.sh` (PR #5) - PR 생성 자동화 (현재는 본문 하드코딩 → §8 리팩터)
- `docs/project_handoff_2026-05-29.md` (본 문서)
- `docs/next_work_2026-05-29.md` (차기 작업 우선순위)

변경:

- `start.sh` (PR #4) - COMFYUI_PORT/SERVICE 상수, env_value/service_active/url_ready 헬퍼, `check_model_workers`
- `streamlit_app.py` (PR #5) - STEP_LABELS 모듈 상수, render_step_progress(), POSTER_TEMPLATE_THUMBNAILS, render_poster_template_thumbnails() + 관련 CSS
- `backend/config.py`, `streamlit_app.py` (PR #4) - 기본 API 포트 8000 → 8010
- `.env.example` (PR #4) - DESKAD_PUBLIC_API_BASE 공인 IP 제거 → loopback
- `README.md` (PR #4) - 모델 워커 systemd 설치 안내
- `docs/next_work_2026-05-28.md` (PR #4) - M1 완료 표기

## 4. 운영 인프라

- ComfyUI: systemd 서비스 `comfyui.service` (active, enabled). 기존 nohup 종료 완료. `journalctl -u comfyui` 로 로그.
- Ollama: 기존 `ollama.service` 그대로.
- `start.sh --restart` 가 두 서비스 active 여부 확인. 미등록/inactive 시 안내 메시지 출력.
- nginx 8443 + basic auth, Streamlit 127.0.0.1:8501 binding 유지.

## 5. 새 API / UI 표

PR #4 ~ #5 까지 사용자 접점 변경 없음. UI 만 시각 개선.

- 사이드바 위 4단계 stepper (chip + progress bar)
- 광고 콘텐츠 단계 selectbox 아래 포스터 템플릿 4종 SVG 미리보기

## 6. 검증 결과

PR #4 와 PR #5 시점 모두 자동 검증 통과:

```text
py_compile                                : OK
tools/scan_secrets.py --all              : clean (100~101 files)
bash start.sh --restart                   : ComfyUI/Ollama 모두 active
/health                                   : 200
/ai/providers                             : 200 (6 providers)
/layouts                                  : 200 (60/65/75/87/104 모두 반환)
/plates                                   : 200 (repo_path=None, graceful)
/render/desk-setup, /render/keyboard-preview : 200
/ai/copy (fallback provider)              : 200
nginx :8443                               : 401 (basic auth)
```

그러나 사용자 직접 테스트에서 시각/렌더링 회귀 다수 발견 → §7.

## 7. 사용자 발견 회귀/누락 이슈 (2026-05-29)

다음 항목은 **사용자가 브라우저에서 직접 모델/렌더링을 실행해 본 결과** 발견한 회귀와 누락이다. 자동 테스트 (py_compile/curl)는 통과해도 시각 결과가 어색한 케이스.

### 7-1. 키보드 레이아웃 5종 중 UI 에 3종만 노출 (P0)

- backend 의 `/layouts` 는 `60/65/75/87/104` 5종 반환
- `streamlit_app.py:818` `layout_options = ["60", "65", "75"]` 가 하드코딩
- `KEYBOARD_SIZE_INFO` (line 398) 도 60/65/75 만 정의 — 87 (TKL) / 104 (풀배열) 라벨 없음
- `KEYBOARD_MODEL_DEFAULTS` (line 411) 의 모든 모델이 60/65/75 만 참조 — TKL/풀배열 모델 없음
- **수정**: `layout_options` 를 `/layouts` API 응답으로 동적 채움, `KEYBOARD_SIZE_INFO` 에 87/104 추가, TKL/풀배열 대표 모델 1-2종 추가
- 사용자 노션에 더 많은 키보드 레이아웃 샘플이 있다고 함 (확인 필요)

### 7-2. PCB / 플레이트가 TKL / 풀배열 지원 안 함 (P0)

- 같은 layout_87 / layout_104 가 frontend 에 안 보이는 문제의 연장.
- `data/drawings/keyboard_layout_plate_{65,75}.json` 만 있고 87/104 도면 없음
- 추가로 `data/assemblies/keyboard_assembly_sample.json` 하나만 있어 다른 사이즈 조립 데이터 없음
- **수정**: drawings/assemblies 에 87/104 도면/조립 데이터 추가, 노션의 keyboard_layout 저장소 참조 확장

### 7-3. 키보드 측면 렌더링 — 이미지를 쌓아 올린 느낌 (P0, 회귀)

- 키보드를 측면(side/front) 카메라로 봤을 때 case/plate/PCB/keycap 이 분리된 층으로 보임
- 정상이라면 case 내부에 plate 가 들어가고, keycap 이 case 위로 살짝 올라온 자연스러운 측면 실루엣
- 회귀 원인 추정: `backend/renderer.py` 의 layer y-offset / case 안쪽 두께 처리. PR #3 ~ taeho 머지 사이에서 case wall, plate inset, keycap base 의 상대 좌표가 어긋났을 가능성
- **수정**: `_add_keyboard_detailed` 의 case wall 두께, plate inset, keycap stem 길이 재검토

### 7-4. 모니터암 double_joint 꺾임 미반영 (P0, 회귀)

- `monitor_arm_style: "double_joint"` 옵션이 UI 에 있고 backend `_add_monitor_arm` 에 `if style == "double_joint":` 분기도 있지만 (`renderer.py:1165`) 실제 렌더에서는 single 과 동일하게 직선 형태로 나옴
- 사용자 증언: 이전 세션에는 동작했음. 최근 수정 (taeho 머지 후) 부터 회귀
- 추정 원인: 머지 시 webdemo 의 모델링 1차 수정을 보류하고 taeho 의 renderer 를 채택했는데, 그 사이에 monitor arm joint 좌표 계산이 틀어짐. 또는 head/screen 위치가 joint endpoint 와 분리되어 있어 화면상 직관적으로 안 보임
- **수정**: webdemo (`a87468d 모델링 1차 수정`) 의 monitor arm 처리 부분만 cherry-pick 또는 재이식

### 7-5. 스위치가 하우징 밖으로 튀어나옴 (P1, 빈도 낮음)

- 가끔 keycap 또는 switch top 이 case 상단보다 더 위에 그려져 "튀어나온" 모양으로 보임
- `case_finish`, `keycap_profile`, `mount_type` 옵션 조합에 따라 발생 빈도가 다를 가능성
- **수정**: 7-3 과 같이 case 두께/keycap base/stem 좌표 일관성 확인

### 7-6. 상품 유형이 키보드 외에는 모두 "테스트 키보드 셋업" 으로 렌더링 (P1)

- `streamlit_app.py:789` 상품 유형 selectbox: `["커스텀 키보드", "키캡", "데스크매트", "데스크 조명", "모니터암", "데스크 소품", "번들 셋업"]`
- 그러나 backend 의 `/render/desk-setup`, `/render/keyboard-preview` 는 항상 키보드 중심 셋업을 렌더
- 다른 상품 유형 선택 시 빌드되는 GLB 가 키보드 데모와 동일
- **수정**: 상품 유형별 분기. 단기적으로는 키보드 외 유형은 "이 상품 유형은 추후 지원" 안내 + 데스크 셋업만 표시. 장기적으로는 유형별 hero 모델 추가
- 또는 상품 유형 옵션을 일단 키보드/번들 셋업 만 노출하도록 축소 (P0 까지 미루기)

### 7-7. 이전 작업 내역 (history) UI 가독성 (P2)

- 사용자가 이전 결과를 다시 보기 어렵다고 함
- 현재는 가장 최근 1건만 미리보기에 노출
- **수정**: U4 (image job history grid) 작업 진행. `/ai/image/jobs?limit=20` 결과를 썸네일 grid 로 표시, 클릭해 포스터 합성 재사용

## 8. 보류 / 차기 작업 (`docs/next_work_2026-05-28.md` 잔여)

§7 의 회귀 픽스가 새 P0 가 되어 우선순위가 재배치되었다. 자세한 표는 `docs/next_work_2026-05-29.md` 참조.

요약:

- **P0 (회귀 픽스, 차기 세션 즉시)**: §7-1 ~ §7-4
- **P1 (UX 보완)**: §7-5, §7-6, §7-7 (= U4)
- **P2 (기능 확장)**: M2 (image batch), M3 (regenerate), U2 (모델 비교 4-card), M4 (모델 hot-swap)
- **보류 (별도 회의)**: M5 ~ M11, U11 ~ U14 (LoRA 학습, multi-GPU 등)

## 9. 보안 / 운영 변동 사항

PR #4 ~ #5 사이에 새 보안 사고/우회 없음. 단:

- `.env` 의 `GITHUB_TOKEN` 으로 `tools/push_and_open_pr.sh` 가 GitHub API 호출. 토큰 scope 는 `repo` 최소 권한 권장. 토큰 회수 / 회전 시 `.env` 의 `GITHUB_TOKEN` 만 교체하면 됨
- `commit Co-Authored-By: Claude` 트레일러는 `2d9f042 → 70a27ca` (M1 commit) amend 로 제거. 이후 commit 부터 `feedback_commit_author_trailer.md` 메모리 규칙으로 자동 생략

## 10. 최신 새 대화창 시작 프롬프트

```text
이 프로젝트는 `/home/leetaeho/ai_07_high/deskad_keyboard_demo` 의 DeskAd AI Studio 입니다.
목표는 커스텀 키보드/데스크테리어 소상공인이 실물 촬영 없이 3D 셋업 미리보기 + 광고 문구/포스터/실사 이미지를 만들 수 있게 하는 서비스입니다.

현재 환경:
- GCP VM + PyCharm Remote/SSH, conda env: `sprint_high`
- FastAPI 8010, Streamlit 8501, Ollama 11434 (systemd), ComfyUI 8188 (systemd, PR #4 머지)
- 외부 접속: https://34.27.86.182:8443 (nginx + basic auth)
- JupyterHub 가 8000 사용 → 앱은 8000 금지

브랜치 / PR:
- main: PR #4 머지된 상태 (`03a7bbb`)
- taeho: PR #5 open (U1 stepper + U3 썸네일 + tools + 본 핸드오프)
- 다음 PR 부터는 §7 회귀 픽스

중요 규칙:
- 실제 `.env` / API 키 / GITHUB 토큰 값 출력/커밋 금지
- 큰 모델 파일은 git 에 넣지 않음
- commit 메시지에 Co-Authored-By 트레일러 생략 (memory `feedback_commit_author_trailer.md`)

직전 완료 작업 (2026-05-29):
1. webdemo 머지 (PR #3 → PR #4) — 보안/LLM/이미지 + 모델링 1차
2. M1 — ComfyUI systemd 등록, start.sh 워커 의존성 체크
3. U1 — 4 단계 진행 stepper 시각화
4. U3 — 포스터 템플릿 4종 inline SVG 썸네일
5. tools/push_and_open_pr.sh — PR 생성 자동화 (현재 하드코딩, §8 일반화 필요)

다음 우선순위 (사용자 직접 테스트에서 발견한 회귀):
1. P0 §7-1: 키보드 레이아웃 60/65/75 만 UI 노출 (87 TKL, 104 풀배열 누락). 노션 에 추가 샘플 있다고 함
2. P0 §7-2: TKL/풀배열 plate / assembly 도면 누락
3. P0 §7-3: 키보드 측면 렌더링이 층층이 쌓인 형태로 보임 (회귀)
4. P0 §7-4: 모니터암 double_joint 꺾임이 실제 렌더에 안 보임 (회귀, 이전엔 동작)
5. P1 §7-6: 상품 유형 selectbox 에 7종 있지만 키보드 외엔 모두 동일 GLB

자세한 진단 / 수정 방향은 docs/project_handoff_2026-05-29.md §7 와 docs/next_work_2026-05-29.md 참조.

검증 명령:

cd /home/leetaeho/ai_07_high/deskad_keyboard_demo
conda run -n sprint_high python -B -m py_compile backend/*.py streamlit_app.py tools/scan_secrets.py
conda run -n sprint_high python tools/scan_secrets.py --all
bash start.sh --restart
curl -s http://127.0.0.1:8010/layouts | python3 -m json.tool
curl -s http://127.0.0.1:8010/health | head -c 400
```

## 11. 종료 절차

```bash
bash /home/leetaeho/ai_07_high/deskad_keyboard_demo/start.sh --stop
# systemd 서비스는 평상시 항상 켜둠. 정말로 꺼야 할 때:
#   sudo systemctl stop comfyui ollama
```
