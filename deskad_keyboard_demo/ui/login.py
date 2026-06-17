"""이 파일은 로그인/회원가입 페이지와 인증 게이트 helper를 담당한다."""

from __future__ import annotations

import re
import time

import streamlit as st
import streamlit.components.v1 as components

from .api_client import (
    api_login,
    api_logout,
    api_signup,
    api_validate_session,
)

USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9]{3,32}$")
PASSWORD_MIN_LENGTH = 8
AUTH_COOKIE_NAME = "deskad_auth"


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


def _auth_cookie_value() -> str | None:
    return st.context.cookies.get(AUTH_COOKIE_NAME)


def _store_login_success(result: dict, fallback_name: str) -> None:
    st.session_state.auth_token = result["token"]
    st.session_state.auth_display_name = result.get("display_name") or fallback_name
    st.session_state.auth_expires_at = result.get("expires_at")
    st.session_state.login_fail_count = 0


def restore_auth_from_cookie() -> bool:
    """새로고침 후 HttpOnly cookie의 세션 토큰을 서버 검증한 뒤 세션 상태로 복원한다."""
    if is_authenticated():
        return True
    token = _auth_cookie_value()
    if not token:
        return False
    result = api_validate_session(token)
    if result.get("ok") and result.get("token"):
        _store_login_success(result, result.get("display_name") or "사용자")
        return True
    return False


# 이전 query param 방식에서 새 cookie 방식으로 이름을 바꿨지만, 기존 import와 테스트가
# 깨지지 않도록 얇은 별칭을 남겨둔다. 실제 동작은 cookie 기반이다.
restore_auth_from_query = restore_auth_from_cookie


def _complete_login(result: dict, fallback_name: str) -> None:
    _store_login_success(result, fallback_name)


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


def _signup_error_message(result: dict) -> str:
    error = result.get("error")
    if error == "signup_disabled":
        return "회원가입이 비활성화되어 있습니다. 관리자에게 문의해주세요."
    if error == "invalid_signup_code":
        return "가입 코드가 올바르지 않습니다."
    if error == "invalid_username":
        return "아이디는 3~32자의 영문과 숫자만 사용할 수 있습니다."
    if error == "weak_password":
        return f"비밀번호는 {PASSWORD_MIN_LENGTH}자 이상이어야 합니다."
    if error == "username_taken":
        return "이미 사용 중인 아이디입니다."
    if error == "request_failed":
        return "서버에 연결할 수 없습니다. 잠시 후 다시 시도해주세요."
    return "회원가입에 실패했습니다. 입력값을 확인해주세요."


def _render_capslock_detector(component_key: str) -> None:
    """비밀번호 입력 중 CapsLock 상태를 브라우저에서 감지해 안내한다."""
    components.html(
        f"""
        <div id="capslock-warning-{component_key}" style="
          display:none;
          margin: -2px 0 8px 0;
          padding: 8px 10px;
          border-radius: 8px;
          background: #fff7ed;
          border: 1px solid #fdba74;
          color: #9a3412;
          font: 13px/1.45 system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        ">
          CapsLock이 켜져 있습니다. 비밀번호 대소문자를 확인해주세요.
        </div>
        <script>
          const warning = document.getElementById("capslock-warning-{component_key}");
          const setWarning = (event) => {{
            if (!event || typeof event.getModifierState !== "function") return;
            warning.style.display = event.getModifierState("CapsLock") ? "block" : "none";
          }};
          const hideWarning = () => {{
            warning.style.display = "none";
          }};
          try {{
            const parentDoc = window.parent.document;
            parentDoc.addEventListener("keydown", (event) => {{
              const target = event.target;
              if (target && target.matches && target.matches('input[type="password"]')) {{
                setWarning(event);
              }}
            }}, true);
            parentDoc.addEventListener("keyup", (event) => {{
              const target = event.target;
              if (target && target.matches && target.matches('input[type="password"]')) {{
                setWarning(event);
              }}
            }}, true);
            parentDoc.addEventListener("focusout", hideWarning, true);
          }} catch (error) {{
            hideWarning();
          }}
        </script>
        """,
        height=44,
    )


def _render_login_form() -> None:
    with st.form("login_form"):
        username = st.text_input("아이디", autocomplete="username", help="3~32자, 영문과 숫자만 입력")
        password = st.text_input("비밀번호", type="password", autocomplete="current-password")
        _render_capslock_detector("login")
        submitted = st.form_submit_button("로그인", use_container_width=True, type="primary")

    if not submitted:
        return
    username = username.strip()
    if not username or not password:
        st.error("아이디와 비밀번호를 모두 입력해주세요.")
        return
    if not USERNAME_PATTERN.fullmatch(username):
        st.error(_signup_error_message({"error": "invalid_username"}))
        return

    result = api_login(username, password)
    if result.get("ok") and result.get("token"):
        _complete_login(result, username)
        st.rerun()
    st.session_state.login_fail_count = int(st.session_state.get("login_fail_count") or 0) + 1
    st.error(_login_error_message(result))


def _render_signup_form() -> None:
    with st.form("signup_form"):
        username = st.text_input("아이디", help="3~32자, 영문과 숫자만 입력")
        password = st.text_input(
            "비밀번호", type="password", help=f"{PASSWORD_MIN_LENGTH}자 이상",
            autocomplete="new-password",
        )
        _render_capslock_detector("signup_password")
        password_confirm = st.text_input("비밀번호 확인", type="password", autocomplete="new-password")
        _render_capslock_detector("signup_confirm")
        signup_code = st.text_input("가입 코드", type="password", help="관리자에게 받은 코드를 입력하세요.")
        submitted = st.form_submit_button("회원가입", use_container_width=True, type="primary")

    if not submitted:
        return
    username = username.strip()
    if not username or not password or not password_confirm or not signup_code.strip():
        st.error("모든 항목을 입력해주세요.")
        return
    if not USERNAME_PATTERN.fullmatch(username):
        st.error(_signup_error_message({"error": "invalid_username"}))
        return
    if len(password) < PASSWORD_MIN_LENGTH:
        st.error(_signup_error_message({"error": "weak_password"}))
        return
    if password != password_confirm:
        st.error("비밀번호 확인이 일치하지 않습니다.")
        return

    result = api_signup(username, password, signup_code.strip())
    if result.get("ok") and result.get("token"):
        # 가입 즉시 자동 로그인.
        _complete_login(result, username)
        st.rerun()
    st.error(_signup_error_message(result))


def _render_login_page_styles() -> None:
    """로그인 화면 전용 레이아웃 스타일을 주입한다."""
    st.markdown(
        """
        <style>
          [data-testid="stSidebar"] {
            display: none;
          }

          .block-container {
            max-width: min(1360px, 94vw);
            padding-top: 3.4rem;
            padding-bottom: 3rem;
          }

          .deskad-login-shell {
            min-height: calc(100vh - 8rem);
            display: grid;
            grid-template-columns: minmax(520px, 1.35fr) minmax(380px, 0.65fr);
            gap: 42px;
            align-items: center;
          }

          .deskad-login-brand {
            min-height: 640px;
            border: 1px solid rgba(125, 211, 252, 0.22);
            border-radius: 22px;
            padding: 58px 54px;
            background:
              linear-gradient(90deg, rgba(8, 13, 24, 0.88) 0%, rgba(8, 13, 24, 0.58) 54%, rgba(8, 13, 24, 0.18) 100%),
              radial-gradient(circle at 82% 24%, rgba(56, 189, 248, 0.36), transparent 32%),
              radial-gradient(circle at 18% 78%, rgba(37, 99, 235, 0.26), transparent 34%),
              linear-gradient(135deg, #0b1220 0%, #183552 44%, #2f8398 100%);
            color: #ffffff;
            box-shadow: 0 30px 90px rgba(15, 23, 42, 0.24);
            overflow: hidden;
            position: relative;
          }

          .deskad-login-kicker {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 7px 11px;
            border-radius: 999px;
            border: 1px solid rgba(255, 255, 255, 0.22);
            background: rgba(255, 255, 255, 0.10);
            color: rgba(255, 255, 255, 0.86);
            font-size: 12px;
            font-weight: 700;
            letter-spacing: 0;
          }

          .deskad-login-brand h1 {
            max-width: 620px;
            margin: 32px 0 18px 0;
            font-size: 52px;
            line-height: 1.08;
            letter-spacing: 0;
            word-break: keep-all;
          }

          .deskad-login-brand p {
            max-width: 640px;
            margin: 0;
            color: rgba(255, 255, 255, 0.78);
            font-size: 17px;
            line-height: 1.65;
          }

          .deskad-login-hero-actions {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin-top: 26px;
          }

          .deskad-login-hero-pill {
            display: inline-flex;
            align-items: center;
            min-height: 34px;
            padding: 7px 12px;
            border-radius: 999px;
            border: 1px solid rgba(255, 255, 255, 0.18);
            background: rgba(255, 255, 255, 0.10);
            color: rgba(255, 255, 255, 0.82);
            font-size: 13px;
            font-weight: 700;
          }

          .deskad-login-feature-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 12px;
            margin-top: 42px;
            max-width: 100%;
          }

          .deskad-login-feature {
            min-height: 104px;
            padding: 15px;
            border-radius: 14px;
            border: 1px solid rgba(255, 255, 255, 0.16);
            background: rgba(15, 23, 42, 0.36);
          }

          .deskad-login-feature strong {
            display: block;
            margin-bottom: 8px;
            font-size: 15px;
          }

          .deskad-login-feature span {
            color: rgba(255, 255, 255, 0.68);
            font-size: 13px;
            line-height: 1.5;
          }

          .deskad-login-card {
            border: 1px solid rgba(148, 163, 184, 0.32);
            border-radius: 18px;
            padding: 36px 34px 30px;
            background: rgba(255, 255, 255, 0.88);
            box-shadow: 0 22px 64px rgba(15, 23, 42, 0.12);
          }

          .deskad-login-card h2 {
            margin: 0 0 8px 0;
            font-size: 28px;
            letter-spacing: 0;
          }

          .deskad-login-card-head h2 {
            margin: 0 0 8px 0;
            font-size: 28px;
            letter-spacing: 0;
          }

          .deskad-login-card p {
            margin: 0 0 20px 0;
            color: #64748b;
            line-height: 1.6;
          }

          .deskad-login-card-head p {
            margin: 0 0 20px 0;
            color: #64748b;
            line-height: 1.6;
          }

          .deskad-login-note {
            margin-top: 18px;
            padding: 13px 14px;
            border-radius: 12px;
            background: #eff6ff;
            border: 1px solid #bfdbfe;
            color: #335b7d;
            font-size: 13px;
            line-height: 1.55;
          }

          .deskad-login-card [data-baseweb="tab-list"] {
            gap: 8px;
          }

          .deskad-login-card [data-baseweb="tab"] {
            height: 42px;
            border-radius: 999px;
            padding: 0 18px;
          }

          .deskad-login-card [data-testid="stForm"] {
            border: 0;
            padding: 0;
          }

          .deskad-login-card div[data-testid="stTextInput"] label {
            font-weight: 700;
            color: #0f172a;
          }

          .deskad-login-card div[data-testid="stTextInput"] input {
            border-radius: 10px;
            min-height: 42px;
          }

          @media (max-width: 980px) {
            .block-container {
              padding-top: 2rem;
            }

            .deskad-login-shell {
              grid-template-columns: 1fr;
            }

            .deskad-login-brand {
              min-height: auto;
              padding: 30px;
            }

            .deskad-login-brand h1 {
              font-size: 40px;
            }

            .deskad-login-feature-grid {
              grid-template-columns: 1fr;
              margin-top: 28px;
            }
          }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_login_page() -> None:
    """브랜드 패널과 인증 카드를 나란히 배치한 로그인/회원가입 페이지를 렌더링한다."""
    _render_login_page_styles()
    left, right = st.columns([1.08, 0.92], gap="large")
    with left:
        st.markdown(
            """
            <section class="deskad-login-brand">
              <div class="deskad-login-kicker">Campaign Production Studio</div>
              <h1>키보드 광고 제작을<br>한 화면에서 끝내세요.</h1>
              <p>
                제품 정보, 3D 데스크 셋업, 광고 문구, 이미지 작업, 포스터 제작을
                단계별로 이어서 검수하는 DeskAd AI 제작 스튜디오입니다.
              </p>
              <div class="deskad-login-hero-actions">
                <span class="deskad-login-hero-pill">3D 셋업 기반</span>
                <span class="deskad-login-hero-pill">문구 후보 비교</span>
                <span class="deskad-login-hero-pill">포스터 결과 검수</span>
              </div>
              <div class="deskad-login-feature-grid">
                <div class="deskad-login-feature">
                  <strong>3D 셋업</strong>
                  <span>제품과 데스크 구성요소를 시각화합니다.</span>
                </div>
                <div class="deskad-login-feature">
                  <strong>광고 문구</strong>
                  <span>타깃과 톤에 맞는 문구 후보를 생성합니다.</span>
                </div>
                <div class="deskad-login-feature">
                  <strong>포스터 제작</strong>
                  <span>선택한 템플릿으로 광고 결과물을 만듭니다.</span>
                </div>
              </div>
            </section>
            """,
            unsafe_allow_html=True,
        )
    with right:
        with st.container(border=True):
            st.markdown(
                """
                <div class="deskad-login-card-head">
                  <h2>스튜디오 로그인</h2>
                  <p>계정으로 로그인하거나 관리자에게 받은 가입 코드로 새 계정을 만드세요.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            login_tab, signup_tab = st.tabs(["로그인", "회원가입"])
            with login_tab:
                _render_login_form()
            with signup_tab:
                _render_signup_form()
            st.markdown(
                """
                <div class="deskad-login-note">
                  가입 코드는 내부 사용자 확인용입니다. 로그인 실패 시 아이디와 비밀번호 중 어느 항목이 틀렸는지는 표시하지 않습니다.
                </div>
                """,
                unsafe_allow_html=True,
            )


def logout() -> None:
    """서버 세션 무효화 후 로컬 인증 상태를 비우고 로그인 화면으로 돌아간다."""
    token = st.session_state.get("auth_token")
    if token:
        api_logout(token)
    st.session_state.auth_token = None
    st.session_state.auth_display_name = None
    st.session_state.auth_expires_at = None
    st.rerun()
