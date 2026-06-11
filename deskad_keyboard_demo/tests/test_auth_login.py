"""deskad 로그인(스키마 / /auth/* 엔드포인트 / 잠금 / UI 게이트) 테스트."""
from __future__ import annotations

import hashlib

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend import auth
from backend.main import app
from backend.schemas import LoginRequest

PASSWORD = "correct-horse-battery"
PASSWORD_SHA256 = hashlib.sha256(PASSWORD.encode("utf-8")).hexdigest()


@pytest.fixture(autouse=True)
def _clean_auth_state(monkeypatch):
    auth.reset_state()
    monkeypatch.setenv("DESKAD_LOGIN_ID", "deskad")
    monkeypatch.setenv("DESKAD_LOGIN_PASSWORD_SHA256", PASSWORD_SHA256)
    yield
    auth.reset_state()


@pytest.fixture()
def client():
    return TestClient(app)


# --- 스키마 ---

def test_login_request_rejects_empty_fields():
    with pytest.raises(ValidationError):
        LoginRequest(username="", password=PASSWORD)
    with pytest.raises(ValidationError):
        LoginRequest(username="deskad", password="")


def test_login_request_rejects_oversized_fields():
    with pytest.raises(ValidationError):
        LoginRequest(username="a" * 65, password=PASSWORD)
    with pytest.raises(ValidationError):
        LoginRequest(username="deskad", password="a" * 129)


# --- /auth/login ---

def test_login_success_returns_token(client):
    response = client.post("/auth/login", json={"username": "deskad", "password": PASSWORD})
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["token"]
    assert body["display_name"] == "deskad"
    assert auth.is_token_valid(body["token"])


def test_login_wrong_password_fails_without_token(client):
    response = client.post("/auth/login", json={"username": "deskad", "password": "wrong"})
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["token"] is None
    assert body["error"] == "invalid_credentials"


def test_login_wrong_username_uses_same_error_code(client):
    body = client.post("/auth/login", json={"username": "intruder", "password": PASSWORD}).json()
    assert body["ok"] is False
    # 아이디/비밀번호 어느 쪽이 틀렸는지 구분 노출 금지.
    assert body["error"] == "invalid_credentials"


def test_login_not_configured(client, monkeypatch):
    monkeypatch.delenv("DESKAD_LOGIN_ID")
    monkeypatch.delenv("DESKAD_LOGIN_PASSWORD_SHA256")
    body = client.post("/auth/login", json={"username": "deskad", "password": PASSWORD}).json()
    assert body == {
        "ok": False,
        "token": None,
        "display_name": None,
        "expires_at": None,
        "error": "not_configured",
        "retry_after_seconds": None,
    }


def test_login_rejects_blank_payload_with_422(client):
    response = client.post("/auth/login", json={"username": "", "password": ""})
    assert response.status_code == 422


# --- 잠금 ---

def test_lockout_after_five_failures_blocks_correct_password():
    now = 1_000.0
    for _ in range(4):
        result = auth.login("deskad", "wrong", now=now)
        assert result["error"] == "invalid_credentials"
    result = auth.login("deskad", "wrong", now=now)
    assert result["error"] == "locked"

    locked = auth.login("deskad", PASSWORD, now=now + 1)
    assert locked["ok"] is False
    assert locked["error"] == "locked"
    assert locked["retry_after_seconds"] >= 1


def test_lockout_expires_after_window():
    now = 1_000.0
    for _ in range(5):
        auth.login("deskad", "wrong", now=now)

    after = auth.login("deskad", PASSWORD, now=now + auth.LOCKOUT_SECONDS + 1)
    assert after["ok"] is True
    assert after["token"]


# --- 로그아웃 / 토큰 수명 ---

def test_logout_invalidates_token(client):
    token = client.post("/auth/login", json={"username": "deskad", "password": PASSWORD}).json()["token"]
    assert auth.is_token_valid(token)

    response = client.post("/auth/logout", json={"token": token})
    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert not auth.is_token_valid(token)

    # 이미 무효화된 토큰은 ok=false지만 200 유지.
    assert client.post("/auth/logout", json={"token": token}).json()["ok"] is False


def test_token_expires_after_ttl():
    issued = auth.login("deskad", PASSWORD, now=1_000.0)
    token = issued["token"]
    assert auth.is_token_valid(token, now=1_000.0 + auth.SESSION_TTL_SECONDS - 1)
    assert not auth.is_token_valid(token, now=1_000.0 + auth.SESSION_TTL_SECONDS + 1)


# --- UI 게이트(순수 함수) ---

def test_token_state_is_valid_gate_logic():
    from ui.login import token_state_is_valid

    assert not token_state_is_valid(None, None)
    assert not token_state_is_valid("", None)
    assert token_state_is_valid("tok", None)
    assert token_state_is_valid("tok", 2_000.0, now=1_999.0)
    assert not token_state_is_valid("tok", 2_000.0, now=2_000.0)
    assert not token_state_is_valid("tok", "not-a-number")
