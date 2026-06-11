#!/usr/bin/env python3
"""OpenAI-compatible text+image server for HyperCLOVA X SEED Omni.

This is a single-process fallback for hosts where the full OmniServe compose
topology is too large (e.g. a single NVIDIA L4). It serves text+image -> text
only. Image generation still requires OmniServe Track B decoder/S3 or a separate
OpenAI Images-compatible worker.

Runtime notes (verified 2026-06-10 on a single L4, naver-hyperclovax/
HyperCLOVAX-SEED-Omni-8B, transformers 5.9.0, 4-bit):

  * The model ships custom modeling code built for transformers 4.52.4. Four small
    forward-compat shims are applied below so it loads on transformers 5.x.
  * The model is exposed via ``AutoModelForCausalLM`` (its auto_map only registers
    CausalLM / SequenceClassification, not ImageTextToText).
  * The bundled ``HCXVisionV2Processor`` inherits the Qwen2.5-VL default
    ``image_token='<|image_pad|>'`` (id 0). This model's real pad token is
    ``<|IMAGE_PAD|>`` (id 128062); without fixing it the placeholder is never
    expanded and the model silently ignores the image.
  * transformers' ``apply_chat_template`` normalizes ``image_url`` content and the
    shipped jinja template then renders no image block, so we build the prompt
    string manually with the continuous-vision block. The discrete-vision block is
    omitted (the discrete tokenizer needs OmniServe and is unavailable here).
  * ``generation_config.json`` declares ``eos_token_id=0`` which never appears, so
    we stop on ``<|im_end|>`` (128001) / ``<|endofturn|>`` (128003) explicitly.
"""
from __future__ import annotations

import base64
import os
import re
import time
from io import BytesIO
from pathlib import Path
from threading import Lock
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

import requests
import torch
import uvicorn
from fastapi import FastAPI, HTTPException
from PIL import Image
from pydantic import BaseModel, Field

# --- transformers 5.x forward-compat shims for the 4.52.4-era custom modeling ---
import transformers  # noqa: E402
import transformers.modeling_utils as _hcx_mu  # noqa: E402

if not hasattr(_hcx_mu, "no_init_weights"):
    from transformers.initialization import no_init_weights as _hcx_niw

    _hcx_mu.no_init_weights = _hcx_niw
if not hasattr(transformers, "rope_config_validation"):
    try:
        from transformers.modeling_rope_utils import rope_config_validation as _hcx_rcv

        transformers.rope_config_validation = _hcx_rcv
    except Exception:
        pass
# transformers 5.x weight-tying refactor: model lacks this attribute. lm_head.weight
# is materialized in the checkpoint, so an empty default is safe.
if not hasattr(_hcx_mu.PreTrainedModel, "all_tied_weights_keys"):
    _hcx_mu.PreTrainedModel.all_tied_weights_keys = {}
# --------------------------------------------------------------------------------

from transformers import AutoModelForCausalLM, AutoProcessor, BitsAndBytesConfig  # noqa: E402


DEFAULT_MODEL = "naver-hyperclovax/HyperCLOVAX-SEED-Omni-8B"
MODEL_ID = os.getenv("HYPERCLOVA_OMNI_MODEL") or os.getenv("HYPERCLOVA_VISION_MODEL") or DEFAULT_MODEL
HOST = os.getenv("HYPERCLOVA_OMNI_HOST", "127.0.0.1")
PORT = int(os.getenv("HYPERCLOVA_OMNI_PORT", "11601"))
MAX_NEW_TOKENS = int(os.getenv("HYPERCLOVA_OMNI_MAX_NEW_TOKENS", "512"))
TOKEN = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACEHUB_API_TOKEN") or None
DEVICE = os.getenv("HYPERCLOVA_OMNI_DEVICE", "cuda" if torch.cuda.is_available() else "cpu")
DEVICE_MAP = os.getenv("HYPERCLOVA_OMNI_DEVICE_MAP", "")
# Default to 4-bit: the full bf16 weights are ~43GB and only fit a 24GB L4 quantized.
LOAD_IN_4BIT = os.getenv("HYPERCLOVA_OMNI_LOAD_IN_4BIT", "true").strip().lower() in {"1", "true", "yes", "on"}
LOAD_IN_8BIT = os.getenv("HYPERCLOVA_OMNI_LOAD_IN_8BIT", "").strip().lower() in {"1", "true", "yes", "on"}
TORCH_DTYPE = os.getenv("HYPERCLOVA_OMNI_TORCH_DTYPE", "auto").strip().lower()
TRUST_REMOTE_CODE = os.getenv("HYPERCLOVA_OMNI_TRUST_REMOTE_CODE", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
ALLOW_LOCAL_FILES = os.getenv("HYPERCLOVA_OMNI_ALLOW_LOCAL_FILES", "").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
IMAGE_FETCH_TIMEOUT = int(os.getenv("HYPERCLOVA_OMNI_IMAGE_FETCH_TIMEOUT_SECONDS", "15"))
DATA_URL_RE = re.compile(r"^data:image/[^;]+;base64,(?P<data>.+)$", re.IGNORECASE | re.DOTALL)

# Model-specific special tokens (HyperCLOVAX-SEED-Omni-8B tokenizer).
IMAGE_PAD = "<|IMAGE_PAD|>"
IMAGE_PAD_ID = 128062
IMAGE_BLOCK = "<|image_start|><|IMAGE_PAD|><|image_end|>"
IM_END_ID = 128001  # <|im_end|>
ENDOFTURN_ID = 128003  # <|endofturn|>
STOP_TOKEN_IDS = [IM_END_ID, ENDOFTURN_ID]
# Trailing-turn leakage guard: trim anything from a fresh role header onward.
_TRAILING_ROLE_RE = re.compile(r"\n(?:assistant|user|system|tool|google_search|tool_call)\b")


class ChatMessage(BaseModel):
    role: str
    content: str | list[Any]


class ChatCompletionRequest(BaseModel):
    model: str | None = None
    messages: list[ChatMessage]
    max_tokens: int | None = Field(default=None, ge=1, le=4096)
    max_completion_tokens: int | None = Field(default=None, ge=1, le=4096)
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    top_p: float = Field(default=0.9, ge=0.0, le=1.0)


app = FastAPI(title="HyperCLOVA X SEED Omni OpenAI-compatible vision server")
_generate_lock = Lock()


def _torch_dtype(value: str):
    if value in {"", "auto"}:
        return "auto"
    aliases = {
        "fp16": torch.float16,
        "float16": torch.float16,
        "half": torch.float16,
        "bf16": torch.bfloat16,
        "bfloat16": torch.bfloat16,
        "fp32": torch.float32,
        "float32": torch.float32,
    }
    if value not in aliases:
        raise RuntimeError(f"Unsupported HYPERCLOVA_OMNI_TORCH_DTYPE: {value}")
    return aliases[value]


def _quantization_config():
    if LOAD_IN_4BIT and LOAD_IN_8BIT:
        raise RuntimeError("Set only one of HYPERCLOVA_OMNI_LOAD_IN_4BIT or HYPERCLOVA_OMNI_LOAD_IN_8BIT.")
    if not (LOAD_IN_4BIT or LOAD_IN_8BIT):
        return None
    if LOAD_IN_8BIT:
        return BitsAndBytesConfig(load_in_8bit=True)
    compute_dtype = _torch_dtype(TORCH_DTYPE)
    if compute_dtype == "auto":
        compute_dtype = torch.float16
    return BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type=os.getenv("HYPERCLOVA_OMNI_BNB_4BIT_QUANT_TYPE", "nf4"),
        bnb_4bit_compute_dtype=compute_dtype,
        bnb_4bit_use_double_quant=os.getenv("HYPERCLOVA_OMNI_BNB_4BIT_USE_DOUBLE_QUANT", "true").strip().lower()
        in {"1", "true", "yes", "on"},
    )


def _patch_tie_weights(cls) -> None:
    """transformers 5.x calls tie_weights(missing_keys=..., recompute_mapping=...);
    the model's 4.52.4-era override only accepts (self). Swallow the new kwargs."""
    import inspect

    try:
        params = inspect.signature(cls.tie_weights).parameters
    except (TypeError, ValueError):
        return
    if "missing_keys" in params:
        return
    _orig_tie = cls.tie_weights

    def _patched_tie(self, *args, **kwargs):
        try:
            return _orig_tie(self)
        except TypeError:
            return None

    cls.tie_weights = _patched_tie


def _load_model():
    processor = AutoProcessor.from_pretrained(MODEL_ID, token=TOKEN, trust_remote_code=TRUST_REMOTE_CODE)
    # The processor inherits the wrong Qwen2.5-VL image token; point it at this model's.
    processor.image_token = IMAGE_PAD
    processor.image_token_id = IMAGE_PAD_ID

    # Pre-resolve and patch the dynamic model class before from_pretrained runs.
    if TRUST_REMOTE_CODE:
        try:
            from transformers.dynamic_module_utils import get_class_from_dynamic_module

            _cls = get_class_from_dynamic_module(
                "modeling_vlm.HCXVisionForCausalLM", MODEL_ID, token=TOKEN, trust_remote_code=True
            )
            _patch_tie_weights(_cls)
        except Exception:
            pass

    kwargs: dict[str, Any] = {
        "token": TOKEN,
        "trust_remote_code": TRUST_REMOTE_CODE,
        "torch_dtype": _torch_dtype(TORCH_DTYPE),
    }
    quantization_config = _quantization_config()
    if quantization_config is not None:
        kwargs["quantization_config"] = quantization_config
        kwargs["device_map"] = DEVICE_MAP or "auto"
    elif DEVICE_MAP:
        kwargs["device_map"] = DEVICE_MAP
    model = AutoModelForCausalLM.from_pretrained(MODEL_ID, **kwargs)
    if not DEVICE_MAP and quantization_config is None:
        model = model.to(DEVICE)
    model.eval()
    return processor, model


processor, model = _load_model()


def _model_device() -> torch.device:
    try:
        return next(model.parameters()).device
    except StopIteration:
        return torch.device(DEVICE)


def _image_url_value(part: dict[str, Any]) -> str | None:
    image_url = part.get("image_url")
    if isinstance(image_url, str):
        return image_url
    if isinstance(image_url, dict):
        url = image_url.get("url")
        return str(url) if url else None
    return None


def _load_image(url: str) -> Image.Image:
    match = DATA_URL_RE.match(url)
    if match:
        data = base64.b64decode(match.group("data"))
        return Image.open(BytesIO(data)).convert("RGB")

    parsed = urlparse(url)
    if parsed.scheme in {"http", "https"}:
        response = requests.get(url, timeout=IMAGE_FETCH_TIMEOUT)
        response.raise_for_status()
        return Image.open(BytesIO(response.content)).convert("RGB")

    if parsed.scheme == "file":
        path = Path(parsed.path)
    else:
        path = Path(url).expanduser()
    if not ALLOW_LOCAL_FILES:
        raise HTTPException(
            status_code=400,
            detail="Local image files are disabled. Use data URLs/HTTP URLs or set HYPERCLOVA_OMNI_ALLOW_LOCAL_FILES=true.",
        )
    if not path.exists():
        raise HTTPException(status_code=400, detail=f"Image file does not exist: {path}")
    return Image.open(path).convert("RGB")


def _part_text(part: dict[str, Any]) -> str:
    if part.get("type") == "text":
        return str(part.get("text", ""))
    # Some clients send {"type": "input_text", "text": ...} or bare {"text": ...}.
    if "text" in part and part.get("type") not in {"image_url", "image"}:
        return str(part.get("text", ""))
    return ""


def _build_prompt(messages: list[ChatMessage]) -> tuple[str, list[Image.Image]]:
    """Render the chat into the model's raw prompt string and collect images.

    We bypass ``apply_chat_template`` (it drops image_url content) and emit the
    continuous-vision block for each image inline, in order.
    """
    images: list[Image.Image] = []
    chunks: list[str] = []
    for message in messages:
        role = message.role
        content = message.content
        if isinstance(content, str):
            body = content
        else:
            pieces: list[str] = []
            for part in content:
                if not isinstance(part, dict):
                    continue
                part_type = part.get("type")
                if part_type in {"image_url", "image"}:
                    url = _image_url_value(part) or part.get("url")
                    if url:
                        images.append(_load_image(str(url)))
                        pieces.append(IMAGE_BLOCK)
                else:
                    text = _part_text(part)
                    if text:
                        pieces.append(text)
            body = "\n".join(pieces)
        chunks.append(f"<|im_start|>{role}\n{body}<|im_end|>\n")
    # skip_reasoning-style assistant prefix (empty think block -> direct answer).
    chunks.append("<|im_start|>assistant\n<think>\n\n</think>\n\n")
    return "".join(chunks), images


def _prepare_inputs(prompt: str, images: list[Image.Image]):
    kwargs: dict[str, Any] = {"text": [prompt], "return_tensors": "pt"}
    if images:
        kwargs["images"] = images
    inputs = processor(**kwargs)
    # The processor returns mm_token_type_ids which the model.generate rejects.
    if hasattr(inputs, "pop"):
        try:
            inputs.pop("mm_token_type_ids", None)
        except Exception:
            pass
    if hasattr(inputs, "to"):
        return inputs.to(_model_device())
    return {
        key: value.to(_model_device()) if hasattr(value, "to") else value
        for key, value in inputs.items()
        if key != "mm_token_type_ids"
    }


def _clean(text: str) -> str:
    text = text.strip()
    # Trim any leaked next-turn header (the model can ramble past <|im_end|>).
    match = _TRAILING_ROLE_RE.search(text)
    if match:
        text = text[: match.start()]
    return text.strip()


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "model": MODEL_ID,
        "device": str(_model_device()),
        "device_map": DEVICE_MAP or "single",
        "quantization": "4bit" if LOAD_IN_4BIT else "8bit" if LOAD_IN_8BIT else "none",
        "supports": {"text": True, "image_input": True, "image_output": False},
    }


@app.get("/v1/models")
def models() -> dict[str, Any]:
    return {
        "object": "list",
        "data": [{"id": MODEL_ID, "object": "model", "created": 0, "owned_by": "naver-hyperclovax"}],
    }


@app.post("/v1/chat/completions")
def chat_completions(request: ChatCompletionRequest) -> dict[str, Any]:
    if not request.messages:
        raise HTTPException(status_code=400, detail="messages must not be empty")
    prompt, images = _build_prompt(request.messages)
    max_new_tokens = request.max_completion_tokens or request.max_tokens or MAX_NEW_TOKENS
    inputs = _prepare_inputs(prompt, images)
    prompt_len = int(inputs["input_ids"].shape[-1]) if "input_ids" in inputs else 0
    generation_kwargs = {
        "max_new_tokens": max_new_tokens,
        "do_sample": request.temperature > 0,
        "temperature": max(request.temperature, 1e-5),
        "top_p": request.top_p,
        "eos_token_id": STOP_TOKEN_IDS,
        "pad_token_id": IM_END_ID,
    }

    with _generate_lock:
        with torch.no_grad():
            outputs = model.generate(**inputs, **generation_kwargs)

    generated = outputs[0][prompt_len:]
    text = _clean(processor.tokenizer.decode(generated, skip_special_tokens=True))
    now = int(time.time())
    completion_tokens = int(outputs.shape[-1] - prompt_len) if hasattr(outputs, "shape") and prompt_len else 0
    return {
        "id": f"chatcmpl-{uuid4().hex}",
        "object": "chat.completion",
        "created": now,
        "model": request.model or MODEL_ID,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": prompt_len,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_len + completion_tokens,
        },
    }


if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT)
