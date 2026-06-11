"""deskad 단일 운영 계정 로그인과 메모리 세션을 담당한다.

- 자격증명은 .env의 DESKAD_LOGIN_ID / DESKAD_LOGIN_PASSWORD_SHA256 (평문 저장 금지).
- 비교는 secrets.compare_digest 상수시간 비교만 사용한다.
- 세션은 서버 메모리 dict[token, record] + TTL — 단일 인스턴스 운영이라 충분하며,
  job_store와 같은 이유로 Lock으로 보호한다(2026-06-11 QA 동시성 교훈).
- 연속 실패 잠금: LOCKOUT_THRESHOLD회 실패 시 LOCKOUT_SECONDS 동안 정답도 거부.
"""
from __future__ import annotations

import hashlib
import os
import secrets
import threading
import time

SESSION_TTL_SECONDS = 12 * 3600
LOCKOUT_THRESHOLD = 5
LOCKOUT_SECONDS = 60.0

_LOCK = threading.Lock()
# token -> {"username": str, "issued_at": float, "expires_at": float}
_SESSIONS: dict[str, dict] = {}
# 단일 운영 계정이라 전역 카운터 하나로 충분하다.
_FAIL_STATE = {"count": 0, "locked_until": 0.0}


def _configured_credentials() -> tuple[str, str]:
    """환경 변수에서 로그인 아이디와 비밀번호 SHA256 해시를 읽는다.

    Settings는 lru_cache로 고정되므로 거치지 않고 매 호출 os.getenv로 읽는다 —
    테스트(monkeypatch)와 .env 갱신 후 재기동 시점 차이를 줄인다.
    """
    login_id = os.getenv("DESKAD_LOGIN_ID", "").strip()
    password_sha256 = os.getenv("DESKAD_LOGIN_PASSWORD_SHA256", "").strip().lower()
    return login_id, password_sha256


def _prune_expired(now: float) -> None:
    expired = [token for token, record in _SESSIONS.items() if record["expires_at"] <= now]
    for token in expired:
        _SESSIONS.pop(token, None)


def login(username: str, password: str, *, now: float | None = None) -> dict:
    """자격증명을 검증하고 성공 시 세션 토큰을 발급한다.

    반환은 LoginResponse와 같은 형태의 dict:
    성공 {ok, token, display_name, expires_at} / 실패 {ok: False, error[, retry_after_seconds]}.
    """
    now = time.time() if now is None else now
    login_id, password_sha256 = _configured_credentials()
    if not login_id or not password_sha256:
        return {"ok": False, "error": "not_configured"}

    with _LOCK:
        locked_until = _FAIL_STATE["locked_until"]
        if now < locked_until:
            return {
                "ok": False,
                "error": "locked",
                "retry_after_seconds": max(1, int(locked_until - now + 0.999)),
            }

        provided_sha256 = hashlib.sha256(password.encode("utf-8")).hexdigest()
        username_ok = secrets.compare_digest(username.encode("utf-8"), login_id.encode("utf-8"))
        password_ok = secrets.compare_digest(provided_sha256, password_sha256)
        if not (username_ok and password_ok):
            _FAIL_STATE["count"] += 1
            if _FAIL_STATE["count"] >= LOCKOUT_THRESHOLD:
                _FAIL_STATE["count"] = 0
                _FAIL_STATE["locked_until"] = now + LOCKOUT_SECONDS
                return {
                    "ok": False,
                    "error": "locked",
                    "retry_after_seconds": int(LOCKOUT_SECONDS),
                }
            return {"ok": False, "error": "invalid_credentials"}

        _FAIL_STATE["count"] = 0
        _FAIL_STATE["locked_until"] = 0.0
        _prune_expired(now)
        token = secrets.token_urlsafe(32)
        _SESSIONS[token] = {
            "username": login_id,
            "issued_at": now,
            "expires_at": now + SESSION_TTL_SECONDS,
        }
        return {
            "ok": True,
            "token": token,
            "display_name": login_id,
            "expires_at": _SESSIONS[token]["expires_at"],
        }


def logout(token: str) -> bool:
    """세션 토큰을 무효화한다. 존재했던 토큰이면 True."""
    with _LOCK:
        return _SESSIONS.pop(token, None) is not None


def is_token_valid(token: str, *, now: float | None = None) -> bool:
    """토큰이 발급되어 있고 만료 전인지 확인한다."""
    if not token:
        return False
    now = time.time() if now is None else now
    with _LOCK:
        record = _SESSIONS.get(token)
        if record is None:
            return False
        if record["expires_at"] <= now:
            _SESSIONS.pop(token, None)
            return False
        return True


def reset_state() -> None:
    """세션/잠금 상태 초기화 — 테스트 격리 용도."""
    with _LOCK:
        _SESSIONS.clear()
        _FAIL_STATE["count"] = 0
        _FAIL_STATE["locked_until"] = 0.0
