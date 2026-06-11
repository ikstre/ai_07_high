#!/usr/bin/env python3
"""OpenAI Images-compatible native image-generation server for HyperCLOVA X SEED Omni.

text -> image. The Omni LLM emits a `t2i_model_generation` tool call carrying 729
discrete vision tokens; the vendored OmniServe diffusers decoder
(tools/omni_vision_decoder/pipeline.py) turns them into an RGB image.

Single NVIDIA L4 (22GB) recipe, verified 2026-06-10:
  * 4-bit breaks image-token generation; bf16 (21.5GB) leaves no headroom -> OOM.
    So only the 8B `language_model` (a plain LlamaForCausalLM) is loaded in 8-bit
    (~10GB); the vision/audio encoders are not needed for text->image and are
    excluded via a one-time extraction (see HYPERCLOVA_OMNI_LLM_DIR).
  * Greedy decoding collapses the tokens (few unique -> low detail); temperature
    1.0 breaks the block. temperature=0.7/top_p=0.9 is the sweet spot.
  * Decoder: num_inference_steps=50, guidance_scale=0.75 (transformer2 autoguidance).

Exposes POST /v1/images/generations (and /images/generations) returning
{"data": [{"b64_json": "<png>"}]}, plus GET /health. Mutually exclusive on VRAM
with ComfyUI and the vision-input server (manage via GPU_WORKER_MODE=exclusive).
"""
from __future__ import annotations

import base64
import json
import os
import random
import re
import sys
import time
from io import BytesIO
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4

import numpy as np
import torch
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from transformers import (
    AutoTokenizer,
    BitsAndBytesConfig,
    LlamaForCausalLM,
    StoppingCriteria,
    StoppingCriteriaList,
)

# Vendored OmniServe vision decoder (custom diffusers pipeline). The module must be
# importable as `pipeline` because the decoder components reference library "pipeline".
_DECODER_DIR = str(Path(__file__).resolve().parent / "omni_vision_decoder")
if _DECODER_DIR not in sys.path:
    sys.path.insert(0, _DECODER_DIR)
import pipeline as _vpipe  # noqa: E402  (vendored VisionTokenToImagePipeline)


def _snapshot_dir() -> str:
    override = os.getenv("HYPERCLOVA_OMNI_DECODER_DIR")
    if override:
        return override
    import glob

    roots = [
        "/opt/shared_models/huggingface/hub/models--naver-hyperclovax--HyperCLOVAX-SEED-Omni-8B/snapshots/*",
        os.path.expanduser("~/.cache/huggingface/hub/models--naver-hyperclovax--HyperCLOVAX-SEED-Omni-8B/snapshots/*"),
    ]
    for pat in roots:
        hits = glob.glob(pat)
        if hits:
            return hits[0] + "/decoder/vision"
    raise RuntimeError("Omni decoder/vision weights not found; set HYPERCLOVA_OMNI_DECODER_DIR")


LLM_DIR = os.getenv("HYPERCLOVA_OMNI_LLM_DIR", "/opt/shared_models/omni_language_model")
DECODER_DIR = _snapshot_dir()
HOST = os.getenv("HYPERCLOVA_OMNI_IMAGE_HOST", "127.0.0.1")
PORT = int(os.getenv("HYPERCLOVA_OMNI_IMAGE_PORT", "11602"))
MODEL_ID = os.getenv("HYPERCLOVA_IMAGE_MODEL", "hyperclovax-omni-image")
MAX_NEW_TOKENS = int(os.getenv("HYPERCLOVA_OMNI_IMAGE_MAX_NEW_TOKENS", "900"))
TEMPERATURE = float(os.getenv("HYPERCLOVA_OMNI_IMAGE_TEMPERATURE", "0.7"))
TOP_P = float(os.getenv("HYPERCLOVA_OMNI_IMAGE_TOP_P", "0.9"))
STEPS = int(os.getenv("HYPERCLOVA_OMNI_IMAGE_STEPS", "50"))
GUIDANCE = float(os.getenv("HYPERCLOVA_OMNI_IMAGE_GUIDANCE", "0.75"))
# Sampling is stochastic and occasionally fails to emit the full 729-token block;
# retry with a fresh seed until a valid block appears. Early-aborted attempts cost
# ~10s each, so the count can sit well above the old default of 4; TIME_BUDGET is
# the real cap on wall time.
MAX_ATTEMPTS = int(os.getenv("HYPERCLOVA_OMNI_IMAGE_MAX_ATTEMPTS", "12"))
# No new attempt may START after this much wall time. A successful attempt adds
# ~180s of LLM generation plus ~100s of decoding on the L4, so the client timeout
# (HYPERCLOVA_IMAGE_TIMEOUT_SECONDS, default 420) must cover BUDGET + 280s.
TIME_BUDGET = float(os.getenv("HYPERCLOVA_OMNI_IMAGE_TIME_BUDGET_SECONDS", "140"))
# A failed attempt is sampling going down a plain-text path instead of calling the
# t2i tool; measured cost is 80-180s each. The tool-call header shows up within the
# first few dozen tokens, so abort as soon as it is absent. 0 disables the check.
TOOLCALL_CHECK_TOKENS = int(os.getenv("HYPERCLOVA_OMNI_IMAGE_TOOLCALL_CHECK_TOKENS", "48"))

import logging  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("omni_image")

IM_END_ID, ENDOFTURN_ID = 128001, 128003
_VISION_RE = re.compile(r"<\|vision(\d+)\|>")
_RATIO_RE = re.compile(r"<\|vision_ratio_(\d+):(\d+)\|>")
_DENSITY, _FACTOR = 768 ** 2, 16

SYSTEM_PROMPT = (
    "You are an AI assistant that generates images. When asked to draw or create an image, "
    "you MUST use the t2i_model_generation tool to generate the image. Always respond by calling the tool."
)
_TOOL_JSON = json.dumps({
    "type": "function",
    "function": {
        "name": "t2i_model_generation",
        "description": "Generates an RGB image based on the provided discrete image representation.",
        "parameters": {
            "type": "object",
            "required": ["discrete_image_token"],
            "properties": {
                "discrete_image_token": {
                    "type": "string",
                    "description": "A serialized string of discrete vision tokens.",
                    "minLength": 1,
                }
            },
        },
    },
})


class ImageRequest(BaseModel):
    prompt: str
    model: str | None = None
    n: int = Field(default=1, ge=1, le=4)
    size: str | None = None
    response_format: str | None = "b64_json"
    seed: int | None = Field(default=None, ge=0)


app = FastAPI(title="HyperCLOVA X SEED Omni native image server")
_lock = Lock()


def _load():
    bnb = BitsAndBytesConfig(load_in_8bit=True)
    lm = LlamaForCausalLM.from_pretrained(
        LLM_DIR, quantization_config=bnb, device_map={"": 0}, torch_dtype=torch.float16
    ).eval()
    tok = AutoTokenizer.from_pretrained(LLM_DIR, trust_remote_code=True)
    pipe = _vpipe.VisionTokenToImagePipeline.from_pretrained(
        DECODER_DIR, torch_dtype=torch.bfloat16
    ).to("cuda")
    return lm, tok, pipe


lm, tokenizer, decoder = _load()


def _build_prompt(user_prompt: str) -> str:
    return (
        "<|im_start|>system\n" + SYSTEM_PROMPT + "\n\n# Tools\n\n"
        "You may call one or more functions to assist with the user query.\n\n"
        "You are provided with function signatures within <tools></tools> XML tags:\n<tools>\n"
        + _TOOL_JSON + "\n</tools>\n\n"
        "For each function call, output the function name and arguments within the following XML format:\n"
        "<tool_call>{function-name}\n<arg_key>{arg-key-1}</arg_key>\n<arg_value>{arg-value-1}</arg_value>\n"
        "...\n</tool_call><|im_end|>\n"
        "<|im_start|>user\n" + user_prompt + "<|im_end|>\n"
        "<|im_start|>assistant\n<think>\n\n</think>\n\n"
    )


def _ratio_to_res(w: int, h: int) -> tuple[int, int]:
    r = h / w
    width = int(((_DENSITY / r) ** 0.5 // _FACTOR) * _FACTOR)
    height = int(((_DENSITY * r) ** 0.5 // _FACTOR) * _FACTOR)
    return width, height


class _AbortIfNoToolCall(StoppingCriteria):
    """Stop generation early when the first tokens are clearly not a tool call."""

    def __init__(self, prompt_len: int):
        self.prompt_len = prompt_len
        self.aborted = False
        self._checked = False

    def __call__(self, input_ids, scores, **kwargs) -> bool:
        if self._checked or TOOLCALL_CHECK_TOKENS <= 0:
            return False
        generated = input_ids[0][self.prompt_len:]
        if generated.shape[-1] < TOOLCALL_CHECK_TOKENS:
            return False
        self._checked = True
        text = tokenizer.decode(generated, skip_special_tokens=False)
        self.aborted = "<tool_call>" not in text
        return self.aborted


def _emit_tokens(user_prompt: str, seed: int) -> tuple[np.ndarray, int, int] | None:
    """Run the LLM once; return (729 tokens, width, height) or None if the block is incomplete."""
    torch.manual_seed(seed)
    enc = tokenizer(_build_prompt(user_prompt), return_tensors="pt").to("cuda")
    abort = _AbortIfNoToolCall(enc["input_ids"].shape[-1])
    with torch.no_grad():
        out = lm.generate(
            **enc, max_new_tokens=MAX_NEW_TOKENS, do_sample=True,
            temperature=TEMPERATURE, top_p=TOP_P,
            eos_token_id=[IM_END_ID, ENDOFTURN_ID], pad_token_id=IM_END_ID,
            stopping_criteria=StoppingCriteriaList([abort]),
        )
    if abort.aborted:
        logger.info("seed=%d -> early abort: no <tool_call> within %d tokens", seed, TOOLCALL_CHECK_TOKENS)
        return None
    text = tokenizer.decode(out[0][enc["input_ids"].shape[-1]:], skip_special_tokens=False)
    vis = [int(x) for x in _VISION_RE.findall(text)]
    logger.info("seed=%d -> vision_tokens=%d uniq=%d", seed, len(vis), len(set(vis)))
    if len(vis) < 600:
        return None
    tokens = np.array(vis[:729], dtype=np.int64)
    if len(tokens) < 729:
        tokens = np.pad(tokens, (0, 729 - len(tokens)))
    m = _RATIO_RE.search(text)
    width, height = _ratio_to_res(int(m.group(1)), int(m.group(2))) if m else (768, 768)
    return tokens, width, height


def _generate_one(user_prompt: str, base_seed: int) -> str | None:
    emitted = None
    started = time.monotonic()
    for attempt in range(MAX_ATTEMPTS):
        emitted = _emit_tokens(user_prompt, seed=base_seed + attempt * 1000)
        elapsed = time.monotonic() - started
        if emitted is not None:
            logger.info("attempt %d/%d ok (%.1fs elapsed)", attempt + 1, MAX_ATTEMPTS, elapsed)
            break
        if elapsed >= TIME_BUDGET:
            logger.warning(
                "attempt %d/%d failed and retry window exhausted (%.1fs >= %.0fs); giving up",
                attempt + 1, MAX_ATTEMPTS, elapsed, TIME_BUDGET,
            )
            return None
        logger.warning(
            "attempt %d/%d produced an incomplete block; retrying (%.1fs elapsed)",
            attempt + 1, MAX_ATTEMPTS, elapsed,
        )
    if emitted is None:
        return None
    tokens, width, height = emitted
    image = decoder(
        vision_tokens=tokens, height=height, width=width,
        num_inference_steps=STEPS, guidance_scale=GUIDANCE, generator=base_seed,
    ).images[0]
    buf = BytesIO()
    image.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "model": MODEL_ID,
        "llm_dir": LLM_DIR,
        "supports": {"text": False, "image_input": False, "image_output": True},
        "params": {"temperature": TEMPERATURE, "top_p": TOP_P, "steps": STEPS, "guidance": GUIDANCE},
    }


@app.post("/v1/images/generations")
@app.post("/images/generations")
def images_generations(req: ImageRequest) -> dict[str, Any]:
    if not req.prompt.strip():
        raise HTTPException(status_code=400, detail="prompt must not be empty")
    # A fixed base seed makes failures deterministic: a prompt that misses the
    # token block on its retry seeds will fail identically on every resubmit.
    # Default to a random seed; accept an explicit one for reproducibility.
    base_seed = req.seed if req.seed is not None else random.randrange(2**31)
    data = []
    with _lock:
        for i in range(req.n):
            b64 = _generate_one(req.prompt, base_seed=base_seed + i)
            if b64:
                data.append({"b64_json": b64})
    logger.info("request done: n=%d ok=%d base_seed=%d", req.n, len(data), base_seed)
    if not data:
        raise HTTPException(status_code=502, detail="model did not emit a valid discrete image token block")
    return {"created": int(time.time()), "data": data}


if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT)
