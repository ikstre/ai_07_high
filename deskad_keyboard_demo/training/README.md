# DeskAd LoRA 학습 준비

이 폴더는 데스크테리어/커스텀 키보드 도메인 이미지를 LoRA 학습 데이터셋으로 정리하기 위한 보조 코드입니다.

## 데이터 원칙

- 점주가 직접 촬영했거나 상업적 사용 권리가 명확한 이미지만 넣습니다.
- Wikimedia/Poly Pizza/Sketchfab/Thingiverse 등 외부 자료는 라이선스와 출처를 `license_manifest.json`에 남깁니다.
- 브랜드 로고, 타사 제품명, 상표가 보이면 학습 전에 제거하거나 사용하지 않습니다.

## 데이터셋 생성

```bash
python training/prepare_desk_lora_dataset.py   --images-dir ./raw_desk_images   --output-dir ./training/output/desk_lora_dataset   --trigger-token deskadkb   --style "minimal premium deskterior"   --product-type "custom keyboard and desk accessory"   --source merchant-owned   --license merchant-owned-commercial   --commercial-use-checked
```

생성물:

- `metadata.jsonl`: diffusers 계열 학습에서 쓰는 이미지-캡션 매핑
- `license_manifest.json`: 출처와 라이선스 확인 기록
- `images/`: 학습 이미지 사본 또는 심볼릭 링크

## FLUX LoRA 템플릿

`train_flux_lora.sh`는 GPU 워커에서 사용할 실행 템플릿입니다. 실제 실행 전 아래 사전 조건을 확인하세요.

### 현재 환경 상태 (GCP L4 24 GB)

- PyTorch 2.12 + CUDA 13.0 : `sprint_high` 환경에 설치됨 ✓
- diffusers / accelerate / peft / safetensors : **미설치** → 아래 명령으로 설치 필요

```bash
conda run -n sprint_high pip install diffusers accelerate peft safetensors transformers bitsandbytes
```

### FLUX.1-schnell LoRA 실행 방법

1. `train_flux_lora.sh`는 `train_dreambooth_lora_flux.py`를 호출합니다.
2. 이 스크립트는 diffusers 예제 코드를 직접 받아서 써야 합니다:

```bash
wget https://raw.githubusercontent.com/huggingface/diffusers/main/examples/dreambooth/train_dreambooth_lora_flux.py
```

3. `train_flux_lora.sh` 내 `accelerate launch train_dreambooth_lora_flux.py ...` 앞에 전체 경로를 지정하거나 스크립트를 같은 디렉터리에 넣으세요.

### VRAM 기준

| 모델 | 해상도 | batch | VRAM |
|------|--------|-------|------|
| FLUX.1-schnell (bf16) | 768 | 1 | ~22 GB |
| SDXL LoRA | 1024 | 1 | ~16 GB |
| SD 3.5 Medium LoRA | 1024 | 1 | ~18 GB |

L4 24 GB 기준 FLUX.1-schnell은 가능하지만 빡빡합니다. 여유 있게 쓰려면 SDXL 또는 SD 3.5 Medium을 권장합니다.

### 학습 데이터셋 스크립트 실행 예시 (샘플 이미지 없이 동작 확인)

```bash
mkdir -p /tmp/test_images
cp /path/to/some/desk_photo.jpg /tmp/test_images/
conda run -n sprint_high python training/prepare_desk_lora_dataset.py \
  --images-dir /tmp/test_images \
  --output-dir /tmp/test_dataset \
  --commercial-use-checked
```

출력: `/tmp/test_dataset/metadata.jsonl`, `license_manifest.json`, `images/`
