#!/usr/bin/env bash
set -euo pipefail

# This is a template for the GPU worker, not a required local dev command.
# Prepare data first with prepare_desk_lora_dataset.py and verify commercial-use rights.

MODEL_NAME="${MODEL_NAME:-black-forest-labs/FLUX.1-schnell}"
DATASET_DIR="${DATASET_DIR:-./training/output/desk_lora_dataset}"
OUTPUT_DIR="${OUTPUT_DIR:-./training/output/desk_lora_flux}"
INSTANCE_PROMPT="${INSTANCE_PROMPT:-deskadkb custom keyboard deskterior product advertising photo}"
RESOLUTION="${RESOLUTION:-768}"
TRAIN_BATCH_SIZE="${TRAIN_BATCH_SIZE:-1}"
GRADIENT_ACCUMULATION_STEPS="${GRADIENT_ACCUMULATION_STEPS:-4}"
MAX_TRAIN_STEPS="${MAX_TRAIN_STEPS:-800}"
LEARNING_RATE="${LEARNING_RATE:-1e-4}"

accelerate launch train_dreambooth_lora_flux.py \
  --pretrained_model_name_or_path "$MODEL_NAME" \
  --instance_data_dir "$DATASET_DIR/images" \
  --caption_column text \
  --instance_prompt "$INSTANCE_PROMPT" \
  --output_dir "$OUTPUT_DIR" \
  --mixed_precision bf16 \
  --resolution "$RESOLUTION" \
  --train_batch_size "$TRAIN_BATCH_SIZE" \
  --gradient_accumulation_steps "$GRADIENT_ACCUMULATION_STEPS" \
  --learning_rate "$LEARNING_RATE" \
  --max_train_steps "$MAX_TRAIN_STEPS" \
  --checkpointing_steps 200
