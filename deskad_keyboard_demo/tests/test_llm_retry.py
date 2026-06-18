import pytest
import requests

from backend import llm_adapters


class FakeResponse:
    def __init__(self, status_code: int, *, reason: str = "status", body: dict | None = None):
        self.status_code = status_code
        self.reason = reason
        self.body = body or {"choices": [{"message": {"content": "{}"}}]}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} {self.reason}", response=self)

    def json(self) -> dict:
        return self.body


class FakeSession:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0
        self.trust_env = True
        self.requests = []

    def post(self, *args, **kwargs):
        self.calls += 1
        self.requests.append({"args": args, "kwargs": kwargs})
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def _patch_session(monkeypatch, session: FakeSession) -> FakeSession:
    monkeypatch.setattr(llm_adapters.requests, "Session", lambda: session)
    monkeypatch.setattr(llm_adapters.time, "sleep", lambda delay: None)
    return session


def test_post_with_retry_retries_5xx_then_returns_success(monkeypatch):
    monkeypatch.setenv("LLM_MAX_RETRIES", "2")
    monkeypatch.setenv("LLM_RETRY_BACKOFF_SECONDS", "0")
    session = _patch_session(monkeypatch, FakeSession([FakeResponse(500), FakeResponse(200)]))

    response = llm_adapters._post_with_retry(
        "http://example.test/v1/chat/completions",
        headers={},
        json={},
        timeout=1,
        provider="test",
    )

    assert response.status_code == 200
    assert session.calls == 2
    assert session.trust_env is False


def test_post_with_retry_raises_4xx_without_retry(monkeypatch):
    monkeypatch.setenv("LLM_MAX_RETRIES", "2")
    session = _patch_session(monkeypatch, FakeSession([FakeResponse(400)]))

    with pytest.raises(requests.HTTPError):
        llm_adapters._post_with_retry(
            "http://example.test/v1/chat/completions",
            headers={},
            json={},
            timeout=1,
            provider="test",
        )

    assert session.calls == 1


def test_post_with_retry_exhausts_connection_errors(monkeypatch):
    monkeypatch.setenv("LLM_MAX_RETRIES", "2")
    monkeypatch.setenv("LLM_RETRY_BACKOFF_SECONDS", "0")
    session = _patch_session(
        monkeypatch,
        FakeSession(
            [
                requests.ConnectionError("down 1"),
                requests.ConnectionError("down 2"),
                requests.ConnectionError("down 3"),
            ]
        ),
    )

    with pytest.raises(requests.ConnectionError):
        llm_adapters._post_with_retry(
            "http://example.test/v1/chat/completions",
            headers={},
            json={},
            timeout=1,
            provider="test",
        )

    assert session.calls == 3


def test_post_with_retry_allows_per_request_retry_override(monkeypatch):
    monkeypatch.setenv("LLM_MAX_RETRIES", "2")
    session = _patch_session(monkeypatch, FakeSession([requests.ConnectionError("down")]))

    with pytest.raises(requests.ConnectionError):
        llm_adapters._post_with_retry(
            "http://example.test/v1/chat/completions",
            headers={},
            json={},
            timeout=1,
            provider="test",
            max_retries_override=0,
        )

    assert session.calls == 1


def test_chat_adapter_passes_custom_messages_and_temperature(monkeypatch):
    monkeypatch.setenv("LLM_MAX_TOKENS", "1536")
    session = _patch_session(monkeypatch, FakeSession([FakeResponse(200)]))
    messages = [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "sample"},
        {"role": "assistant", "content": "{}"},
        {"role": "user", "content": "real"},
    ]
    adapter = llm_adapters.ChatCompletionAdapter(name="test", base_url="http://example.test", model="model")

    content = adapter.request(
        system_prompt="fallback system",
        user_prompt="fallback user",
        messages=messages,
        temperature=0.45,
        timeout=1,
    )

    body = session.requests[0]["kwargs"]["json"]
    assert content == "{}"
    assert body["messages"] == messages
    assert body["temperature"] == 0.45
    assert body["max_tokens"] == 1536
