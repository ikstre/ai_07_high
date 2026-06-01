from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse
from uuid import uuid4

import requests


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

    @property
    def available(self) -> bool:
        if not self.base_url:
            return False
        if self.require_api_key and not self.api_key:
            return False
        return True

    def request(self, *, system_prompt: str, user_prompt: str, timeout: int) -> str:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        if self.prompt_format == "single_user":
            messages = [{"role": "user", "content": f"{system_prompt}\n\n{user_prompt}"}]

        body: dict = {
            "model": self.model or self.default_model,
            "temperature": 0.7,
            "messages": messages,
        }
        if self.json_response_format:
            body["response_format"] = {"type": "json_object"}

        response = requests.post(
            normalize_chat_completions_url(self.base_url),
            headers=headers,
            json=body,
            timeout=timeout,
        )
        response.raise_for_status()
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
    max_tokens: int = 512
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

    def request(self, *, system_prompt: str, user_prompt: str, timeout: int) -> str:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "X-NCP-CLOVASTUDIO-REQUEST-ID": f"{self.request_id_prefix}-{uuid4().hex[:12]}",
        }
        if self.apigw_key:
            headers["X-NCP-APIGW-API-KEY"] = self.apigw_key

        body = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "maxTokens": self.max_tokens,
            "topP": self.top_p,
            "topK": 0,
            "temperature": self.temperature,
            "repeatPenalty": self.repeat_penalty,
            "stopBefore": [],
            "includeAiFilters": True,
        }

        response = requests.post(self._endpoint(), headers=headers, json=body, timeout=timeout)
        response.raise_for_status()
        result = response.json() or {}
        message = (result.get("result") or {}).get("message") or {}
        content = message.get("content") or ""
        if not content and isinstance(result.get("status"), dict):
            status = result["status"]
            raise RuntimeError(f"hyperclova status {status.get('code')}: {status.get('message')}")
        return content.strip()
