# ComfyUI 워크플로 디렉터리

`COMFYUI_WORKFLOWS_DIR`(기본 `tools/comfyui_workflows`)에 **API 포맷** 워크플로 JSON을 모아 둔다.
백엔드(`backend/ai.py`)가 요청마다 알맞은 워크플로를 골라 placeholder를 채운 뒤 ComfyUI `/prompt`로 제출한다.

## 워크플로 선택 순서 (seller/situation selector)

`_select_workflow_path(payload)`가 아래 순서로 첫 번째로 **존재하는** `<name>.json`을 고른다.

1. **명시 선택** — 요청 필드 `image_workflow` (예: `"flux_promo_banner"`)
2. **상황 기반** — `flux_<template>` → `flux_<theme>` (포스터 템플릿 / 테마 키워드)
3. **기본** — `COMFYUI_DEFAULT_WORKFLOW` (기본 `flux_schnell_basic`)

이름은 `^[A-Za-z0-9_-]{1,64}$`만 허용 → 경로 탈출(`../`) 차단. `COMFYUI_WORKFLOWS_DIR`이
없으면 레거시 단일 파일 `COMFYUI_WORKFLOW_PATH`로 폴백한다(기존 설정 호환).

> 새 상황을 추가하려면 코드 수정 없이 `flux_<template>.json`만 이 디렉터리에 떨어뜨리면 된다.

## Placeholder

워크플로 JSON 문자열 안에서 아래 토큰이 치환된다 (`{single}` / `{{double}}` 모두 인식).
문자열 전체가 토큰 하나면 원래 타입(int/float)으로, 부분 문자열이면 텍스트로 치환된다.

| placeholder | 출처 | 비고 |
|---|---|---|
| `{prompt}` | 빌드된 image prompt | |
| `{negative_prompt}` | `COMFYUI_NEGATIVE_PROMPT` | 미설정 시 기본 부정 프롬프트 |
| `{width}` `{height}` | 요청 비율 → 픽셀 | |
| `{seed}` | 요청 시각 기반 | 한 요청 내 동일 seed |
| `{steps}` | `COMFYUI_STEPS` / `COMFYUI_COMPOSITION_STEPS` | int. 셋업 구도 맵 reference는 composition steps 사용 |
| `{flux_model_variant}` | `FLUX_MODEL_VARIANT` | |
| `{image_quantization}` | `IMAGE_QUANTIZATION` | |
| `{lora_name}` | `COMFYUI_LORA_NAME` | 빈 값이면 no-op |
| `{lora_strength}` | `COMFYUI_LORA_STRENGTH` | float (기본 0.0) |
| `{controlnet_image}` | `COMFYUI_CONTROLNET_IMAGE` | 정적 ControlNet 입력 파일명(빈 값이면 no-op) |
| `{controlnet_model}` | `COMFYUI_CONTROLNET_MODEL` | ControlNet 모델 파일명(models/controlnet/ 기준). `flux_controlnet_depth`가 사용 |
| `{controlnet_image_name}` | 셋업 GLB depth 자동 렌더·업로드 | 워크플로에 이 토큰이 있으면 `model_url`의 GLB를 헤드리스(OSMesa) 렌더한 depth PNG를 ComfyUI `/upload/image`에 올려 LoadImage 파일명으로 치환. GLB 미해석/실패 시 워크플로 미구동(draft) |
| `{controlnet_strength}` | `COMFYUI_CONTROLNET_STRENGTH` | float (기본 0.0). depth-ControlNet 충실도 노브 |
| `{denoise}` | `COMFYUI_IMG2IMG_DENOISE` / `COMFYUI_COMPOSITION_DENOISE` | float. 셋업 구도 맵 reference는 composition denoise 사용 |
| `{reference_image_name}` | 선택 도면/셋업 구도 맵 자동 업로드 | 워크플로에 이 토큰이 있으면 `_reference_image_b64`의 래스터를 ComfyUI `/upload/image`에 올려 LoadImage 파일명으로 치환. 레퍼런스 없으면 워크플로 미구동(draft) |

부정 프롬프트, LoRA 이름, denoise, steps는 이미지 캐시 키(`make_image_cache_key`)에도 반영되어,
값이 바뀌면 기존 캐시를 재사용하지 않고 새로 생성한다.

## 포함된 워크플로

이미지 요청 payload에 실제로 실리는 situational 키는 `poster_template`과
`theme`(minimal/pastel/premium/gaming)이다. 템플릿 전용 워크플로가 있으면
`flux_<poster_template>.json`이 먼저 선택되고, 없으면 아래 `flux_<theme>.json`으로 자동 라우팅된다.

- `flux_schnell_basic.json` — FLUX.1 schnell fp8 기본 텍스트→이미지 (UNETLoader + DualCLIP + KSampler `{steps}`). 기본 워크플로이자 `theme=minimal` 및 매칭 없는 모든 요청의 폴백.
- `flux_pastel.json` — `theme=pastel`. negative에 `harsh shadow / overexposed / dark mood` 보강(밝고 부드러운 톤 유도).
- `flux_premium.json` — `theme=premium`. **hires 2-pass**: 1차 KSampler → `LatentUpscaleBy ×1.5` → 2차 KSampler(denoise 0.5)로 디테일/해상감↑. 배율 노드라 종횡비 유지. 추론 시간이 더 길다.
- `flux_gaming.json` — `theme=gaming`. negative에 `washed out / flat lighting / low contrast` 보강(어둡고 또렷한 무드 유도).
- `flux_controlnet_depth.json` — **depth-ControlNet으로 배열 고정**. 셋업 구도 레퍼런스 요청에서 `COMFYUI_CONTROLNET_MODEL`(union 또는 단일 depth)과 `COMFYUI_CONTROLNET_STRENGTH>0`가 설정되면 `flux_img2img`보다 우선 선택된다. text2img(EmptyLatentImage, denoise 1.0)로 사진 품질을 내면서, 셋업 GLB를 헤드리스 렌더한 depth(`{controlnet_image_name}`)를 `ControlNetLoader → SetUnionControlNetType(type=depth) → ControlNetApplyAdvanced(strength=`{controlnet_strength}`, vae 연결)`로 주입해 65% 배열을 denoise와 독립적으로 고정한다. 평면 raster img2img로는 "사진+정확 배열"을 동시에 못 얻는다는 2026-06-16 A/B 결론에 따른 경로. union이 아닌 단일 depth 모델을 쓰면 `SetUnionControlNetType` 노드를 빼면 된다.
- `flux_img2img.json` — **레퍼런스 강제(img2img)**. `EmptyLatentImage` 대신 `LoadImage({reference_image_name})→VAEEncode`로 선택 도면/셋업 구도 맵을 latent화해 `KSampler.latent_image`에 연결(steps `{steps}`, denoise `{denoise}`). 출력이 레퍼런스 구조를 닮게 한다. 셋업 구도 맵은 `COMFYUI_COMPOSITION_STEPS`(기본 8)와 `COMFYUI_COMPOSITION_DENOISE`(기본 0.90)를 사용하고, 선택 도면은 `COMFYUI_STEPS`(기본 4)와 `COMFYUI_IMG2IMG_DENOISE`(기본 0.65)를 사용한다.

> theme별 "분위기"는 이미 `build_image_prompt`가 positive 프롬프트에 반영한다. schnell은 `cfg=1.0`이라
> negative 차등 효과는 제한적이므로, pastel/gaming은 구조·미세조정용이고 실질 화질차는 premium의 hires가 담당한다.
> `theme=minimal`은 별도 파일 없이 `flux_schnell_basic`으로 폴백한다(중복 회피).

## LoRA / ControlNet 추가 예시

기본 워크플로를 복사해 노드를 추가하고 placeholder를 참조하면 된다 (LoRA 예).

```jsonc
// "3"(UNETLoader)과 KSampler 사이에 LoraLoaderModelOnly 삽입
"12": {
  "class_type": "LoraLoaderModelOnly",
  "inputs": {
    "lora_name": "{lora_name}",
    "strength_model": "{lora_strength}",
    "model": ["3", 0]
  }
}
// 그리고 KSampler("9")의 "model" 입력을 ["3", 0] → ["12", 0] 으로 교체
```

LoRA/ControlNet 워크플로는 해당 모델 파일이 ComfyUI에 설치되어 있어야 하며,
`COMFYUI_LORA_NAME` 등을 설정하지 않으면 제출 시 실패하므로 **명시 선택(`image_workflow`)** 으로만 쓰는 것을 권장한다.
