#!/usr/bin/env python3
"""Serve HyperCLOVA X SEED from Hugging Face behind a small OpenAI-compatible API.

This is intentionally minimal: the DeskAd backend only needs
POST /v1/chat/completions and GET /v1/models for ad-copy generation.
The model is loaded once at process startup and guarded by a generation lock.
"""
from __future__ import annotations

import os
import time
from threading import Lock
from uuid import uuid4

import torch
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from transformers import AutoModelForCausalLM, AutoTokenizer


DEFAULT_MODEL = "naver-hyperclovax/HyperCLOVAX-SEED-Text-Instruct-1.5B"
MODEL_ID = os.getenv("HYPERCLOVA_SEED_MODEL") or os.getenv("HYPERCLOVA_MODEL") or DEFAULT_MODEL
HOST = os.getenv("HYPERCLOVA_SEED_HOST", "127.0.0.1")
PORT = int(os.getenv("HYPERCLOVA_SEED_PORT", "11501"))
MAX_NEW_TOKENS = int(os.getenv("HYPERCLOVA_SEED_MAX_NEW_TOKENS", "1024"))
TOKEN = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACEHUB_API_TOKEN") or None
DEVICE = os.getenv("HYPERCLOVA_SEED_DEVICE", "cuda" if torch.cuda.is_available() else "cpu")
DEVICE_MAP = os.getenv("HYPERCLOVA_SEED_DEVICE_MAP", "")
LOAD_IN_4BIT = os.getenv("HYPERCLOVA_SEED_LOAD_IN_4BIT", "").strip().lower() in {"1", "true", "yes", "on"}
LOAD_IN_8BIT = os.getenv("HYPERCLOVA_SEED_LOAD_IN_8BIT", "").strip().lower() in {"1", "true", "yes", "on"}
TORCH_DTYPE = os.getenv("HYPERCLOVA_SEED_TORCH_DTYPE", "auto").strip().lower()
BNB_4BIT_QUANT_TYPE = os.getenv("HYPERCLOVA_SEED_BNB_4BIT_QUANT_TYPE", "nf4")
BNB_4BIT_USE_DOUBLE_QUANT = os.getenv("HYPERCLOVA_SEED_BNB_4BIT_USE_DOUBLE_QUANT", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
TRUST_REMOTE_CODE = os.getenv("HYPERCLOVA_SEED_TRUST_REMOTE_CODE", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}


class ChatMessage(BaseModel):
    role: str
    # str 또는 OpenAI 멀티모달 part 리스트([{type:text,...},{type:image_url,...}]).
    # 이 서버는 현재 텍스트 전용이라 image_url part는 무시하고 텍스트만 취한다.
    content: str | list


def _content_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            str(part.get("text", ""))
            for part in content
            if isinstance(part, dict) and part.get("type") == "text"
        )
    return ""


class ChatCompletionRequest(BaseModel):
    model: str | None = None
    messages: list[ChatMessage]
    max_tokens: int | None = Field(default=None, ge=1, le=2048)
    max_completion_tokens: int | None = Field(default=None, ge=1, le=2048)
    temperature: float = Field(default=0.5, ge=0.0, le=2.0)
    top_p: float = Field(default=0.9, ge=0.0, le=1.0)
    stop: str | list[str] | None = None


app = FastAPI(title="HyperCLOVA X SEED OpenAI-compatible server")
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
        raise RuntimeError(f"Unsupported HYPERCLOVA_SEED_TORCH_DTYPE: {value}")
    return aliases[value]


def _quantization_config():
    if LOAD_IN_4BIT and LOAD_IN_8BIT:
        raise RuntimeError("Set only one of HYPERCLOVA_SEED_LOAD_IN_4BIT or HYPERCLOVA_SEED_LOAD_IN_8BIT.")
    if not (LOAD_IN_4BIT or LOAD_IN_8BIT):
        return None
    try:
        from transformers import BitsAndBytesConfig
    except ImportError as exc:
        raise RuntimeError(
            "Install bitsandbytes and accelerate to use HyperCLOVA SEED quantized loading."
        ) from exc
    if LOAD_IN_8BIT:
        return BitsAndBytesConfig(load_in_8bit=True)
    compute_dtype = _torch_dtype(TORCH_DTYPE)
    if compute_dtype == "auto":
        compute_dtype = torch.float16
    return BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type=BNB_4BIT_QUANT_TYPE,
        bnb_4bit_compute_dtype=compute_dtype,
        bnb_4bit_use_double_quant=BNB_4BIT_USE_DOUBLE_QUANT,
    )


def _load_model():
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, token=TOKEN, trust_remote_code=TRUST_REMOTE_CODE)
    quantization_config = _quantization_config()
    kwargs: dict = {"token": TOKEN, "trust_remote_code": TRUST_REMOTE_CODE, "torch_dtype": _torch_dtype(TORCH_DTYPE)}
    if quantization_config is not None:
        kwargs["quantization_config"] = quantization_config
        kwargs["device_map"] = DEVICE_MAP or "auto"
    if DEVICE_MAP:
        kwargs["device_map"] = DEVICE_MAP
    model = AutoModelForCausalLM.from_pretrained(MODEL_ID, **kwargs)
    if not DEVICE_MAP and quantization_config is None:
        model = model.to(DEVICE)
    model.eval()
    return tokenizer, model


tokenizer, model = _load_model()


def _model_device() -> torch.device:
    try:
        return next(model.parameters()).device
    except StopIteration:
        return torch.device(DEVICE)


def _stop_strings(stop: str | list[str] | None) -> list[str]:
    values = ["<|endofturn|>", "<|stop|>"]
    if isinstance(stop, str):
        values.append(stop)
    elif isinstance(stop, list):
        values.extend(str(item) for item in stop if item)
    return values


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "model": MODEL_ID,
        "device": str(_model_device()),
        "device_map": DEVICE_MAP or "single",
        "quantization": "4bit" if LOAD_IN_4BIT else "8bit" if LOAD_IN_8BIT else "none",
    }


@app.get("/v1/models")
def models() -> dict:
    return {
        "object": "list",
        "data": [
            {
                "id": MODEL_ID,
                "object": "model",
                "created": 0,
                "owned_by": "naver-hyperclovax",
            }
        ],
    }


@app.post("/v1/chat/completions")
def chat_completions(request: ChatCompletionRequest) -> dict:
    if not request.messages:
        raise HTTPException(status_code=400, detail="messages must not be empty")

    messages = [{"role": m.role, "content": _content_text(m.content)} for m in request.messages]
    max_new_tokens = request.max_completion_tokens or request.max_tokens or MAX_NEW_TOKENS
    inputs = tokenizer.apply_chat_template(
        messages,
        add_generation_prompt=True,
        tokenize=True,
        return_dict=True,
        return_tensors="pt",
    ).to(_model_device())

    generation_kwargs = {
        "max_new_tokens": max_new_tokens,
        "do_sample": request.temperature > 0,
        "temperature": max(request.temperature, 1e-5),
        "top_p": request.top_p,
        "pad_token_id": tokenizer.eos_token_id,
    }
    prompt_len = inputs["input_ids"].shape[-1]

    with _generate_lock:
        try:
            outputs = model.generate(
                **inputs,
                **generation_kwargs,
                stop_strings=_stop_strings(request.stop),
                tokenizer=tokenizer,
            )
        except TypeError:
            outputs = model.generate(**inputs, **generation_kwargs)

    text = tokenizer.decode(outputs[0][prompt_len:], skip_special_tokens=True).strip()
    now = int(time.time())
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
            "prompt_tokens": int(prompt_len),
            "completion_tokens": int(outputs[0].shape[-1] - prompt_len),
            "total_tokens": int(outputs[0].shape[-1]),
        },
    }


if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT)
