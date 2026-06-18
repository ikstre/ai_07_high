# DeskAd AI Studio — 기술 문서 (아키텍처)

본 문서는 DeskAd AI Studio의 시스템 구조, 데이터 흐름, 핵심 메커니즘을 개발자/운영자 관점에서 정리한다. 사용법은 [README](../README.md), 보안은 [security.md](./security.md), 배포는 [deploy.md](./deploy.md), API 스키마는 [schema.md](./schema.md)를 참고한다.

> 이 문서의 외부 접속 주소·토큰 등 민감 인프라 값은 마스킹(`<서버-IP>` 등)했다. 내부 포트(127.0.0.1 기준)는 동작 이해를 위해 그대로 둔다.

---

## 1. 개요

소상공인 커스텀 키보드 / 데스크테리어 판매자를 위한 **3D 셋업 미리보기 + 광고 콘텐츠 자동 생성** 도구다. 판매자가 상품 스펙(레이아웃·색·재질)과 데스크 환경(책상·모니터·소품)을 입력하면,

1. 3D 데스크 셋업(GLB)을 생성해 미리 보고,
2. 그 셋업을 **구조적 레퍼런스**로 삼아 광고 문구와 **사진 품질의 광고 이미지**를 만들고,
3. SVG/PPTX 포스터로 내보낸다.

핵심 차별점은 **"AI가 그린 이미지가 실제 판매 제품과 다르다"는 문제를 배열 충실도 고정(depth-ControlNet)으로 해결**한 점이다(§4).

---

## 2. 시스템 구성

```
                      사용자(브라우저)
                            │  HTTPS + Basic Auth (nginx, :8443)
                            ▼
            ┌──────────────────────────────┐
            │  Streamlit UI (:8501, 내부)   │   ui/ — 4단계 위저드, 포스터/PPTX
            └──────────────┬───────────────┘
                           │  REST (httpx)
                           ▼
            ┌──────────────────────────────┐
            │  FastAPI 백엔드 (:8010, 내부) │   backend/ — 검증·오케스트레이션
            └───┬───────────┬───────────┬───┘
                │           │           │
       3D 렌더  │   텍스트   │   이미지   │
                ▼           ▼           ▼
      renderer.py    LLM 워커들      이미지 백엔드
      (GLB/depth,   ├ HyperCLOVA X SEED (:11501)   ├ ComfyUI/FLUX (:8188)
       pyrender,    ├ Kanana / Mi:dm (Ollama :11434) │   + depth-ControlNet
       OSMesa CPU)  └ OpenAI 호환 API               └ OpenAI 이미지 API
```

- **UI(Streamlit)** 는 외부에 직접 노출하지 않고 nginx + Basic Auth 뒤에 둔다. 모델 워커 포트(ComfyUI/Ollama)도 외부에 열지 않는다(§보안).
- **백엔드(FastAPI)** 는 모든 입력 검증·프롬프트 구성·잡 큐·캐시·워커 수명주기를 담당하는 단일 오케스트레이터다.
- **GPU 워커**(ComfyUI / HyperCLOVA SEED / Omni)는 단일 NVIDIA L4(24GB)를 공유하며 `GPU_WORKER_MODE`로 수명주기를 제어한다(§5).

### 모듈 맵 (`backend/`)

| 모듈 | 역할 |
|------|------|
| `main.py` / `app_factory.py` | FastAPI 앱·라우트 정의, CORS·미들웨어 |
| `schemas.py` | 요청 Pydantic 모델(입력 검증 경계) |
| `renderer.py` | 절차적 GLB 빌더(키보드/데스크), 구도 맵 래스터, **headless depth 렌더** |
| `ai.py` | 문구/이미지 생성 오케스트레이션, 프롬프트 구성, ComfyUI 잡 제출·폴링, 충실도 로직 |
| `llm_adapters.py` | LLM provider 어댑터(HyperCLOVA/Kanana/Mi:dm/OpenAI), 재시도 |
| `copy_policy.py` | 카피 후처리(금지 표현 치환, 해시태그 수 제한) |
| `quality_gate.py` | 생성 이미지 구도/액센트 색 평가, best-of-N 선별 |
| `runtime_workers.py` | GPU 워커 기동/예열/유휴 회수 |
| `result_cache.py` / `job_store.py` | 결과 캐시·이미지 잡 영속화 |
| `config.py` | `.env` 기반 설정(`Settings`), 마스킹된 진단 |
| `auth.py` / `user_store.py` / `security.py` | 세션·계정·시크릿 위생 |
| `assets.py` `plates.py` `cad.py` `drawing_converter.py` `library.py` | 데스크 소품·플레이트·STEP/도면 변환·모델 라이브러리 |

---

## 3. 4단계 워크플로우

| 단계 | 입력 | 처리 | 산출 |
|------|------|------|------|
| ① 상품 정보 | 모델명·레이아웃, STEP/STP/GLB 업로드 | 업로드 검증·변환(`cad`, `drawing_converter`) | 정규화된 상품 메타 |
| ② 도면 미리보기 | 레이아웃 JSON | 레이아웃 → SVG 탑뷰 도면 | 배열 확인용 도면 |
| ③ 3D 셋업 구성 | 색·재질·책상/모니터/소품 | `renderer.build_desk_setup_scene_glb` 절차적 GLB | `model_url`(GLB) + 구도 맵(원근/탑다운) |
| ④ 광고 생성 | 채널·톤·셀링포인트·셋업 | 문구(LLM/폴백) + 이미지(엔진별) + 포스터 합성 | 카피 후보, 광고 이미지, SVG/PPTX 포스터 |

3D 셋업 빌더는 **GLB 단위 = 1cm** 규약을 지켜 키보드 footprint·키캡 프로파일·책상 치수를 실측 기반으로 생성한다(MX 표준 간격 19.05mm). 이 정확한 3D가 §4 충실도의 기반이 된다.

---

## 4. 배열 충실도 메커니즘 (depth-ControlNet)

### 문제

순수 text2image(또는 평면 도면 img2img)로는 **"사진 품질"과 "정확한 키 배열"을 동시에** 얻기 어렵다. 모델이 65% 배열을 풀사이즈로 그리거나, 행이 물결치거나, 키캡이 녹는(melt) 현상이 분산적으로 발생한다(2026-06 A/B 검증).

### 해법: 구조와 외관의 분리

생성한 3D 셋업 GLB를 **구조 레퍼런스**로 쓴다.

```
셋업 GLB ──(headless 렌더)──▶ depth PNG ──▶ FLUX depth-ControlNet ──▶ 사진 광고
 (정확한 배열)   OSMesa, CPU    (near=밝게)    (denoise 1.0 = 사진 자유)   (배열은 고정)
```

- `renderer.build_desk_setup_depth_png` 가 GLB를 **OSMesa(소프트웨어, CPU)** 로 헤드리스 렌더해 z-buffer를 정규화한 grayscale depth PNG를 만든다. GPU를 쓰지 않아 exclusive GPU 워커와 충돌하지 않는다(VRAM 영향 0).
- ComfyUI의 `flux_controlnet_depth` 워크플로(`ControlNetLoader → SetUnionControlNetType(type=depth) → ControlNetApplyAdvanced`)가 이 depth로 **구조를 denoise와 독립적으로 고정**한다. 그래서 denoise=1.0(완전한 사진 자유도)이어도 배열이 무너지지 않는다.

### 조절 노브 (`.env`)

| 노브 | 의미 |
|------|------|
| `COMFYUI_CONTROLNET_STRENGTH` | 구조 강제 강도. **0.5가 스위트스팟**(사진+배열). 0.7↑은 평면 CG화, 0이면 비활성→img2img 폴백 |
| `COMFYUI_CONTROLNET_END_PERCENT` | ControlNet을 초기 스텝에만 적용(<1.0이면 후반 사진 자유도↑) |
| `COMFYUI_BEST_OF_N` | N장(시드만 다름) 생성 후 `quality_gate`가 **액센트 색** 충실도로 최적 컷 선택(depth는 grayscale라 색을 못 잠금 → 직교 보완). 단일 L4 권장 2~4 |

색은 depth가 grayscale라 고정되지 않으므로 **프롬프트 그라운딩**(`[exact colours]` 절을 피사체 직후 고가중치로 주입)과 **best-of-N** 이 분담한다. 즉 **배열=depth, 주색=프롬프트, 액센트=best-of-N** 의 3단 직교 구성이다.

### 게이팅 / 폴백

depth는 GLB(세워진 모니터 포함)를 데스크 시점으로 렌더하므로 **데스크/룸 구도**(hero·eye_level·wide_scene)에만 적합하다. flat-lay(top_down)·macro 컷은 ControlNet을 끄고 img2img(전용 top_down 구도 맵 보유)로 자연 폴백한다(`_controlnet_appropriate_shot`). ControlNet 모델 미설정/strength=0이면 전 경로 img2img 폴백한다.

---

## 5. 광고 이미지 생성 파이프라인

### 엔진 2트랙

- `local` — 로컬 LLM 문구(HyperCLOVA X SEED 등) + **ComfyUI/FLUX 이미지**(depth-ControlNet/img2img). 키 불필요, 정확도 우선.
- `openai` — OpenAI 호환 텍스트 + OpenAI 이미지. `OPENAI_API_KEY` 필요.
- `auto` — 서버 기본값(`AI_PROVIDER`/`IMAGE_MODEL_BACKEND`)을 따름.

### 비동기 잡 모델

이미지 생성은 수십 초~분이 걸리므로 동기 호출(`POST /ai/image`)과 별도로 **비동기 잡**을 둔다.

```
POST /ai/image/jobs ──▶ job(queued) ──▶ (UI 폴링) GET /ai/image/jobs/{id} ──▶ completed
```

`job_store` 가 잡을 영속화하고, `result_cache` 가 동일 입력 결과를 캐시한다(`force_regen=true`로 무시).

### grid_three 포스터 — 컷별 순차 생성

`grid_three` 포스터는 hero(메인)·detail_macro(키캡 디테일)·eye_level(데스크 무드) **3컷을 각자 다른 시점**으로 만든다.

- 컷마다 `shot_type`을 바꿔 프롬프트·카메라·워크플로(매크로는 depth 제외)를 분리하고 `batch_size=1`로 한 장씩 생성한다.
- **depth 컷의 카메라 각도 분리**: depth 컷(hero·eye_level)은 GLB를 컷별 카메라 각도(구면좌표 프리셋: hero=높은 3/4, eye_level=낮은 수평, wide=멀리 광각)로 렌더해 시점이 실제로 갈린다. 컷별 depth는 ComfyUI에 **유니크 파일명**으로 올린다(고정 파일명+overwrite는 LoadImage가 실행 시점에 읽는 탓에 서로 덮어써 시점이 겹침).
- **순차 제출**: 첫 컷만 ComfyUI에 올리고, 폴링이 현재 컷 완료를 확인한 뒤에야 다음 컷을 올린다. 단일 L4에서 FLUX+ControlNet 컷을 한꺼번에 큐잉하면 VRAM 피크가 겹쳐 위험하므로, **ComfyUI 큐에 우리 컷이 항상 1개만** 존재하도록 한다.

### 폴백 사다리

엔진/워커/키가 없으면 안전하게 내려간다: 문구는 템플릿, 이미지는 SVG 일러스트(모니터+키보드 실루엣). 평가 트랙 무결성을 위해 **엔진을 명시(openai/local)하면 다른 엔진으로 조용히 우회하지 않는다**.

---

## 6. GPU 워커 수명주기

단일 L4 VRAM(24GB)을 ComfyUI(FLUX ~12GB + ControlNet 4.3GB)와 HyperCLOVA SEED/Omni가 공유한다. `GPU_WORKER_MODE`:

| 모드 | 동작 |
|------|------|
| `always_on` | 외부에서 워커를 상시 관리(기본 가정) |
| `exclusive` | 새 워커 기동 전 경쟁 워커를 종료(텍스트↔이미지 전환). 안전하지만 콜드스타트 비용 |
| `on_demand` | 요청 시 기동, 유휴 시 회수 |

`runtime_workers` 가 기동/예열/유휴 회수를 담당한다. exclusive에서는 잡마다 콜드스타트가 생길 수 있어, 재시작 직후 첫 폴링이 `/history` 레이스를 만날 수 있다(재시도로 회복).

---

## 7. 데이터·캐시·영속화

- `data/runtime/` — 워커 상태·로그(text_worker.log 등), 0600 권한.
- 이미지 잡 스토어(`job_store`) — 잡 메타·결과 참조 영속화. 그리드 순차 제출을 위해 원 payload를 잡에 **비공개(`_grid_payload`)** 로 보관하고 공개 응답에선 제거한다.
- 결과 캐시(`result_cache`) — 동일 (프롬프트, payload, 크기, 워크플로) 키로 완료 잡 재사용.
- 정적 모델(`static/models/`) — 생성된 GLB. `model_url`의 basename만 신뢰해 경로 탈출을 차단한다.

---

## 8. 품질 보증

- 회귀 테스트 **263개**(`tests/`), `conda run -n sprint_high pytest`.
- 충실도·구도 변경은 단위 테스트로 동작을 고정하되, **각도/사진 품질 같은 시각 품질은 라이브 ComfyUI 실생성으로 눈 검증**한다(단위 테스트로는 시점 차이를 못 잡음).
- 백엔드 코드 변경은 uvicorn이 기동 시점 코드를 고정하므로 **라이브 검증 전 `bash start.sh --restart` 필수**.
