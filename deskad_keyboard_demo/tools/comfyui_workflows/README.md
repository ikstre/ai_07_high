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
| `{flux_model_variant}` | `FLUX_MODEL_VARIANT` | |
| `{image_quantization}` | `IMAGE_QUANTIZATION` | |
| `{lora_name}` | `COMFYUI_LORA_NAME` | 빈 값이면 no-op |
| `{lora_strength}` | `COMFYUI_LORA_STRENGTH` | float (기본 0.0) |
| `{controlnet_image}` | `COMFYUI_CONTROLNET_IMAGE` | 빈 값이면 no-op |
| `{controlnet_strength}` | `COMFYUI_CONTROLNET_STRENGTH` | float (기본 0.0) |

부정 프롬프트와 LoRA 이름은 이미지 캐시 키(`make_image_cache_key`)에도 반영되어,
값이 바뀌면 기존 캐시를 재사용하지 않고 새로 생성한다.

## 포함된 워크플로

- `flux_schnell_basic.json` — FLUX.1 schnell fp8 기본 텍스트→이미지 (UNETLoader + DualCLIP + KSampler 4 steps). 기본 워크플로.

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
