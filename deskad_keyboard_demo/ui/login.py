"""이 파일은 로그인 페이지와 인증 게이트 helper를 담당한다."""

from __future__ import annotations

import time

import streamlit as st

from .api_client import api_login, api_logout


def token_state_is_valid(token: object, expires_at: object, *, now: float | None = None) -> bool:
    """세션 토큰 보유 + 만료 전인지 판정하는 순수 함수(테스트 대상)."""
    if not isinstance(token, str) or not token:
        return False
    if expires_at is None:
        return True
    try:
        expiry = float(expires_at)
    except (TypeError, ValueError):
        return False
    now = time.time() if now is None else now
    return now < expiry


def is_authenticated() -> bool:
    """현재 세션이 로그인 상태인지 반환한다."""
    return token_state_is_valid(
        st.session_state.get("auth_token"),
        st.session_state.get("auth_expires_at"),
    )


def _store_login_success(result: dict, fallback_name: str) -> None:
    st.session_state.auth_token = result["token"]
    st.session_state.auth_display_name = result.get("display_name") or fallback_name
    st.session_state.auth_expires_at = result.get("expires_at")
    st.session_state.login_fail_count = 0


def _login_error_message(result: dict) -> str:
    """실패 사유를 사용자 안내 문구로 바꾼다 — 아이디/비밀번호 구분 노출 금지."""
    error = result.get("error")
    if error == "locked":
        retry_after = result.get("retry_after_seconds") or 60
        return f"로그인 시도가 잠시 제한되었습니다. {retry_after}초 후 다시 시도해주세요."
    if error == "not_configured":
        return "로그인이 아직 설정되지 않았습니다. 관리자에게 문의해주세요."
    if error == "request_failed":
        return "로그인 서버에 연결할 수 없습니다. 잠시 후 다시 시도해주세요."
    return "아이디 또는 비밀번호가 올바르지 않습니다."


def render_login_page() -> None:
    """중앙 카드형 로그인 페이지를 렌더링한다."""
    st.markdown("<div style='height: 14vh'></div>", unsafe_allow_html=True)
    _, center, _ = st.columns([1, 1.1, 1])
    with center:
        st.markdown(
            "<h2 style='text-align:center; margin-bottom: 0.2rem;'>DeskAd AI Studio</h2>"
            "<p style='text-align:center; color: #6b7280; margin-bottom: 1.2rem;'>"
            "로그인 후 스튜디오를 사용할 수 있습니다.</p>",
            unsafe_allow_html=True,
        )
        with st.form("login_form"):
            username = st.text_input("아이디", autocomplete="username")
            password = st.text_input("비밀번호", type="password", autocomplete="current-password")
            submitted = st.form_submit_button("로그인", use_container_width=True, type="primary")

        if not submitted:
            return
        username = username.strip()
        if not username or not password:
            st.error("아이디와 비밀번호를 모두 입력해주세요.")
            return

        result = api_login(username, password)
        if result.get("ok") and result.get("token"):
            _store_login_success(result, username)
            st.rerun()
        st.session_state.login_fail_count = int(st.session_state.get("login_fail_count") or 0) + 1
        st.error(_login_error_message(result))


def logout() -> None:
    """서버 세션 무효화 후 로컬 인증 상태를 비우고 로그인 화면으로 돌아간다."""
    token = st.session_state.get("auth_token")
    if token:
        api_logout(token)
    st.session_state.auth_token = None
    st.session_state.auth_display_name = None
    st.session_state.auth_expires_at = None
    st.rerun()
