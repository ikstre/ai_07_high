from __future__ import annotations

import logging
import os
import random
import re
import time
from dataclasses import dataclass, field
from urllib.parse import urlparse
from uuid import uuid4

import requests

logger = logging.getLogger(__name__)

# Transient HTTP statuses worth retrying. Non-retryable 4xx (400/401/403/404/422)
# fail fast so the caller can fall back to the next provider immediately.
_RETRYABLE_STATUS = frozenset({408, 409, 425, 429, 500, 502, 503, 504})


def _retry_settings(max_retries_override: int | None = None) -> tuple[int, float, float]:
    if max_retries_override is None:
        max_retries = max(0, int(os.getenv("LLM_MAX_RETRIES", "3")))
    else:
        max_retries = max(0, int(max_retries_override))
    base_backoff = max(0.0, float(os.getenv("LLM_RETRY_BACKOFF_SECONDS", "0.5")))
    max_backoff = max(base_backoff, float(os.getenv("LLM_RETRY_MAX_BACKOFF_SECONDS", "8")))
    return max_retries, base_backoff, max_backoff


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _llm_max_tokens() -> int:
    return max(0, _int_env("LLM_MAX_TOKENS", 1024))


# GPT-5 / o1·o3·o4 계열(reasoning 모델)은 `max_tokens`를 거부하고 `max_completion_tokens`만
# 받으며, 기본값(1.0) 외 `temperature`도 400(unsupported_value)으로 거부한다.
# o-시리즈는 bare prefix로 잡으면 로컬 OpenAI 호환 모델(o3-community-7b 등)을 오탐하므로
# "o1/o3/o4" 단독, 또는 공식 suffix(-mini/-preview/-pro/-deep…)·날짜 suffix만 매칭한다.
_REASONING_MODEL_RE = re.compile(r"^(gpt-5|o[134]($|-(mini|preview|pro|deep|\d)))")


def _is_reasoning_model(model: str) -> bool:
    name = (model or "").strip().lower()
    base = name.rsplit("/", 1)[-1]  # "org/gpt-5.4-mini" 같은 경로형도 처리
    return bool(_REASONING_MODEL_RE.match(base))


def _max_tokens_param(model: str) -> str:
    return "max_completion_tokens" if _is_reasoning_model(model) else "max_tokens"


def _post_with_retry(
    url: str,
    *,
    headers: dict,
    json: dict,
    timeout: int,
    provider: str,
    max_retries_override: int | None = None,
) -> requests.Response:
    """POST with exponential backoff + jitter on transient failures.

    Retries on connection errors, timeouts, and 5xx/429-class statuses; raises
    immediately on non-retryable 4xx so the caller can fall back to the next provider.
    """
    max_retries, base_backoff, max_backoff = _retry_settings(max_retries_override)
    session = requests.Session()
    session.trust_env = False
    last_error: BaseException | None = None
    for attempt in range(max_retries + 1):
        try:
            response = session.post(url, headers=headers, json=json, timeout=timeout)
            if response.status_code in _RETRYABLE_STATUS:
                last_error = requests.HTTPError(
                    f"{response.status_code} {response.reason}", response=response
                )
            else:
                response.raise_for_status()
                return response
        except (requests.ConnectionError, requests.Timeout) as exc:
            last_error = exc
        if attempt >= max_retries:
            break
        delay = min(max_backoff, base_backoff * (2 ** attempt))
        delay += random.uniform(0.0, delay)  # full jitter
        logger.warning(
            "[%s] LLM 요청 실패 — %.2fs 후 재시도 %d/%d (%s)",
            provider, delay, attempt + 1, max_retries, last_error,
        )
        time.sleep(delay)
    if last_error is not None:
        raise last_error
    raise RuntimeError(f"[{provider}] request failed with no response")


def _message_text(content) -> str:
    """OpenAI 멀티모달 content(str 또는 part 리스트)에서 텍스트만 추출한다.

    이미지 part(image_url)는 멀티모달 미지원 경로(single_user flatten 등)에서 버린다.
    """
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        texts = [
            str(part.get("text", "")).strip()
            for part in content
            if isinstance(part, dict) and part.get("type") == "text"
        ]
        return "\n".join(t for t in texts if t)
    return ""


def normalize_chat_completions_url(base_url: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    if base.endswith("/v1"):
        return f"{base}/chat/completions"
    if "/v1/" in base:
        return f"{base}/chat/completions"
    return f"{base}/v1/chat/completions"


def is_loopback_base_url(base_url: str) -> bool:
    parsed = urlparse(base_url or "")
    return parsed.hostname in {"127.0.0.1", "localhost", "::1"}


@dataclass(frozen=True)
class ChatCompletionAdapter:
    """OpenAI-compatible /v1/chat/completions adapter (works with Ollama, vLLM, SGLang, LM Studio, OpenAI)."""

    name: str
    base_url: str
    model: str
    api_key: str = ""
    default_model: str = "local-model"
    require_api_key: bool = False
    json_response_format: bool = False
    prompt_format: str = "chat"
    supports_vision: bool = False

    @property
    def available(self) -> bool:
        if not self.base_url:
            return False
        if self.require_api_key and not self.api_key:
            return False
        return True

    def request(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        timeout: int,
        messages: list[dict] | None = None,
        temperature: float | None = None,
        max_retries: int | None = None,
    ) -> str:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        request_messages = messages or [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        if self.prompt_format == "single_user":
            flattened = "\n\n".join(
                text for message in request_messages if (text := _message_text(message.get("content")))
            )
            request_messages = [{"role": "user", "content": flattened}]

        model_name = self.model or self.default_model
        body: dict = {
            "model": model_name,
            "messages": request_messages,
        }
        # reasoning 모델(GPT-5/o-시리즈)에는 temperature를 아예 보내지 않는다(서버 기본 1.0).
        # 비기본 temperature를 넣으면 400으로 거부돼 카피 생성이 조용히 규칙기반 폴백으로
        # 추락한다(QA 2026-06-10 §10 — PR #27의 max_tokens 수정과 동일한 실패 모드).
        if not _is_reasoning_model(model_name):
            body["temperature"] = 0.7 if temperature is None else temperature
        max_tokens = _llm_max_tokens()
        if max_tokens:
            body[_max_tokens_param(model_name)] = max_tokens
        if self.json_response_format:
            body["response_format"] = {"type": "json_object"}

        post_kwargs = {
            "headers": headers,
            "json": body,
            "timeout": timeout,
            "provider": self.name,
        }
        if max_retries is not None:
            post_kwargs["max_retries_override"] = max_retries
        response = _post_with_retry(normalize_chat_completions_url(self.base_url), **post_kwargs)
        result = response.json()
        return result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()


@dataclass(frozen=True)
class HyperClovaDirectAdapter:
    """Naver Cloud HyperCLOVA X direct ClovaStudio chat-completions API.

    Distinct from the OpenAI-compatible gateway path: uses a different request schema
    (maxTokens, topP, repeatPenalty, etc.) and Naver Cloud-specific headers.
    Endpoint pattern: {base_url}/v1/chat-completions/{model}
    or app-prefixed:  {base_url}/{testapp|serviceapp}/v1/chat-completions/{model}
    """

    name: str
    base_url: str
    model: str
    api_key: str = ""
    apigw_key: str = ""
    request_id_prefix: str = "deskad"
    default_model: str = "HCX-005"
    max_tokens: int = field(default_factory=lambda: _int_env("HYPERCLOVA_DIRECT_MAX_TOKENS", _llm_max_tokens()))
    temperature: float = 0.5
    top_p: float = 0.8
    repeat_penalty: float = 1.2
    legacy_path: bool = False
    require_api_key: bool = True
    prompt_format: str = "chat"
    json_response_format: bool = False

    @property
    def available(self) -> bool:
        return bool(self.base_url and self.api_key)

    def _endpoint(self) -> str:
        base = self.base_url.rstrip("/")
        model = self.model or self.default_model
        if "/chat-completions/" in base:
            return base
        if base.endswith("/v1") or base.endswith("/v3"):
            return f"{base}/chat-completions/{model}"
        if base.endswith("/testapp") or base.endswith("/serviceapp"):
            return f"{base}/v1/chat-completions/{model}"
        if self.legacy_path:
            return f"{base}/testapp/v1/chat-completions/{model}"
        return f"{base}/v1/chat-completions/{model}"

    def request(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        timeout: int,
        messages: list[dict] | None = None,
        temperature: float | None = None,
        max_retries: int | None = None,
    ) -> str:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "X-NCP-CLOVASTUDIO-REQUEST-ID": f"{self.request_id_prefix}-{uuid4().hex[:12]}",
        }
        if self.apigw_key:
            headers["X-NCP-APIGW-API-KEY"] = self.apigw_key

        body = {
            "messages": messages or [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "maxTokens": self.max_tokens,
            "topP": self.top_p,
            "topK": 0,
            "temperature": self.temperature if temperature is None else temperature,
            "repeatPenalty": self.repeat_penalty,
            "stopBefore": [],
            "includeAiFilters": True,
        }

        post_kwargs = {
            "headers": headers,
            "json": body,
            "timeout": timeout,
            "provider": self.name,
        }
        if max_retries is not None:
            post_kwargs["max_retries_override"] = max_retries
        response = _post_with_retry(self._endpoint(), **post_kwargs)
        result = response.json() or {}
        message = (result.get("result") or {}).get("message") or {}
        content = message.get("content") or ""
        if not content and isinstance(result.get("status"), dict):
            status = result["status"]
            raise RuntimeError(f"hyperclova status {status.get('code')}: {status.get('message')}")
        return content.strip()
