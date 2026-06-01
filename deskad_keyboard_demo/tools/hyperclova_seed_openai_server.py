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
MAX_NEW_TOKENS = int(os.getenv("HYPERCLOVA_SEED_MAX_NEW_TOKENS", "512"))
TOKEN = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACEHUB_API_TOKEN") or None
DEVICE = os.getenv("HYPERCLOVA_SEED_DEVICE", "cuda" if torch.cuda.is_available() else "cpu")
DEVICE_MAP = os.getenv("HYPERCLOVA_SEED_DEVICE_MAP", "")


class ChatMessage(BaseModel):
    role: str
    content: str


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


def _load_model():
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, token=TOKEN)
    kwargs: dict = {"token": TOKEN, "torch_dtype": "auto"}
    if DEVICE_MAP:
        kwargs["device_map"] = DEVICE_MAP
    model = AutoModelForCausalLM.from_pretrained(MODEL_ID, **kwargs)
    if not DEVICE_MAP:
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

    messages = [message.model_dump() for message in request.messages]
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
