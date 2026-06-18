# DeskAd AI Studio — 스키마 구성 (API · 데이터 모델)

FastAPI 백엔드(내부 `:8010`)의 엔드포인트와 요청/응답 스키마를 정리한다. 모든 요청 스키마는 `backend/schemas.py`의 Pydantic 모델로 검증되며, 이 검증 경계가 길이/패턴/범위 제약을 강제한다. 아키텍처는 [architecture.md](./architecture.md) 참고.

> 표기: 타입 뒤 `(기본값)`, 패턴/범위 제약은 비고에 표시. 민감 인프라 값은 마스킹.

---

## 1. 엔드포인트 일람

| 메서드 | 경로 | 용도 |
|--------|------|------|
| GET | `/health` | 헬스체크 + 마스킹된 설정 진단 |
| GET | `/security/config` | 프론트 표시용 마스킹 설정 |
| POST | `/auth/login` `/auth/signup` `/auth/logout` `/auth/session` | 세션 인증(코드형 error 반환) |
| POST | `/auth/cookie-code` · GET `/auth/cookie` `/auth/clear-cookie` | 토큰↔브라우저 쿠키 교환 |
| GET | `/viewer?model_url=&camera=` | model-viewer 4.0 HTML(GLB 3D 뷰어) |
| POST | `/render/keyboard-preview` | 키보드 단품 GLB 생성 |
| POST | `/render/desk-setup` | **데스크 셋업 GLB + 구도 맵** 생성 |
| POST | `/render/uploaded-model` | 업로드 모델(STEP/STP/GLB) 변환·프록시 |
| POST | `/render/plate-drawing` | 플레이트 도면 렌더 |
| POST | `/models/library/prepare` | 모델 라이브러리 파일 준비 |
| GET | `/ai/providers` | 엔진/트랙·provider 가용성 |
| POST | `/ai/activate_track` | 트랙 선택 시 GPU 워커 예열 |
| POST | `/ai/copy` `/ai/copy/variants` `/ai/copy/experiment` | 광고 문구 생성(후보/실험) |
| POST | `/ai/image` | 동기 이미지 레퍼런스 생성 |
| POST | `/ai/image/jobs` | **비동기 이미지 잡 큐잉**(`?force_regen=true`) |
| GET | `/ai/image/jobs/{id}` · `/ai/image/jobs` | 잡 폴링 · 목록 |
| POST/GET | `/ai/image/jobs/{id}/quality` · `/ai/quality/summary` | 품질 평가·요약 |
| POST | `/ai/poster` | 포스터(SVG) 합성 |

---

## 2. 렌더링 스키마

### `KeyboardRenderRequest` (키보드 단품/셋업 공통)

| 필드 | 타입(기본값) | 비고 |
|------|--------------|------|
| `product_name` | str("커스텀 키보드 셋업") | ≤80 |
| `layout` | str("65") | 60/65/75/80/100 등 |
| `case_color` `keycap_color` `accent_keycap_color` | str(hex) | 케이스/키캡/액센트 색 |
| `deskmat_color` `desk_color` `mouse_color` | str(hex) | 데스크 소품 색 |
| `theme` | str("minimal") | minimal/pastel/premium/gaming |
| `case_finish` | str("anodized") | anodized\|matte\|polycarbonate\|wood |
| `plate_material` | str("aluminum") | aluminum\|brass\|pom\|fr4\|carbon\|polycarbonate |
| `pcb_color` | str("black") | black\|red\|blue\|green\|white |
| `switch_stem` | str("red") | red\|yellow\|brown\|blue\|clear\|silent_red\|tactile_purple\|linear_black |
| `switch_family` | str("mx") | mx\|box\|holy_panda\|topre |
| `keycap_profile` | str("cherry") | cherry\|oem\|xda\|sa\|mda |
| `mount_type` | str("top_mount") | top_mount\|tray_mount\|gasket_mount\|o_ring_mount |
| `show_internals` | bool(True) | 내부 구조(플레이트/PCB/스위치) 노출 |

### `DeskSetupRenderRequest` (KeyboardRenderRequest 확장)

| 추가 필드 | 타입(기본값) | 비고 |
|-----------|--------------|------|
| `assets` | list[str] | 활성 데스크 소품 id(monitor/mouse 등) |
| `desk_width` | float(120.0) | 100–200 cm |
| `desk_depth` | float(60.0) | 50–90 cm |
| `monitor_size` | str("27") | 24\|27\|32 인치 |
| `monitor_arm_style` | str("single") | single\|double_joint |
| `show_internals` | bool(False) | 셋업 기본은 클린 뷰 |

**응답(`/render/desk-setup`)**: `model_url`(GLB), `layout`, `theme`, `key_count`, `board_width/depth`, `case_outer_*`, `composition_b64`(원근 구도 맵), `composition_topdown_b64`(탑다운), `monitor_panel_cm`, `placed_items`, `scale_notes`(1 unit=1cm) 등.

---

## 3. 광고 콘텐츠 스키마

### `AdContentRequest` (DeskSetupRenderRequest 확장)

상품·타깃·렌더 정보를 모두 포함한다(문구/이미지/포스터 공통 페이로드).

| 필드 | 타입(기본값) | 비고 |
|------|--------------|------|
| `product_name` | str | ≤80 |
| `product_type` | str("커스텀 키보드") | ≤40 |
| `price` | str("189,000원") | ≤30 |
| `target_channel` | str("인스타그램") | 채널별 기본 구도 결정 |
| `target_customer` | str | ≤120 |
| `selling_point` | str | 핵심 특징 요약, ≤240 |
| `product_detail` | str("") | 장문 본문, ≤2000 |
| `ad_tone` | str("감성형") | 감성/프리미엄/할인/기능강조형 |
| `shot_type` | str("") | (빈값=채널 기본) hero\|top_down\|detail_macro\|eye_level\|wide_scene |
| `image_ratio` | str("1:1") | 1:1\|4:5\|16:9 |
| `extra_request` | str | 아트 디렉션, ≤400 |
| `model_url` | str?(null) | 셋업 GLB URL(depth 입력) |
| `reference_image_b64` | str?(null) | 구도 맵/도면 레퍼런스(≤12MB) |
| `reference_image_topdown_b64` | str?(null) | top_down용 구도 맵 |
| `reference_is_composition` | bool(False) | 셋업 구도 맵이면 True(고denoise 사실화) |
| `image_workflow` | str?(null) | 명시 ComfyUI 워크플로명 |
| `poster_template` | str("minimal_card") | minimal_card\|grid_three\|feature_focus\|promo_banner |
| `engine` | str("auto") | auto\|openai\|local |
| `engine_model_tier` | str("general") | general\|performance(OpenAI 한정) |
| `selected_copy` | SelectedCopy?(null) | 사용자 선택 문구(있으면 LLM 우회) |

### `SelectedCopy`

| 필드 | 타입 | 비고 |
|------|------|------|
| `provider` | str("selected") | |
| `headline` `subcopy` `cta` | str | 포스터 표시 문구(길이 제한 없음) |
| `copies` `hashtags` `spec_bullets` | list[str] | 보조 카피·해시태그·스펙 불릿 |

---

## 4. 이미지 잡 응답 모델

`GET /ai/image/jobs/{id}` → `{ "job": {...} }`. 주요 필드:

| 필드 | 의미 |
|------|------|
| `job_id` | 잡 ID |
| `provider` | comfyui\|openai_image\|local_image\|hyperclova_image\|fallback |
| `status` | created\|queued\|running\|completed\|failed\|draft\|not_configured |
| `width` `height` | 출력 해상도 |
| `requested_image_count` | 요청 컷 수(그리드=3) |
| `comfyui_shot_jobs[]` | 그리드 컷별 상태: `{id, label, shot_type, status, comfyui_prompt_id?, image_url?}` |
| `local_image_reference` | 완료 결과(`has_image`, `image_count`, …). **`image_b64`/`image_b64s`는 단건 조회에선 마스킹**(수십 MB 방지) |
| `backend_config` | 사용된 백엔드/노브 진단(마스킹) |

> 그리드 순차 제출용 내부 키 `_grid_payload`는 공개 응답에서 제거된다(용량·민감정보).

---

## 5. 인증 스키마

| 모델 | 필드 |
|------|------|
| `LoginRequest` | `username`(1–64), `password`(1–128) |
| `SignupRequest` | `username`(3–32, 영숫자), `password`(8–128), `signup_code`(.env `DESKAD_SIGNUP_CODE`) |
| `LoginResponse`/`SignupResponse` | `ok`, `token?`, `display_name?`, `expires_at?`, `error?`(invalid_credentials\|locked\|not_configured), `retry_after_seconds?` |
| `LogoutRequest`/`SessionRequest`/`CookieCodeRequest` | `token`(1–128) |

인증·시크릿 위생·CORS·파일 권한 등 보안 설계는 [security.md](./security.md)를 참고한다.
