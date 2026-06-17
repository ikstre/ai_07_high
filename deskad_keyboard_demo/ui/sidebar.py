"""DeskAd AI Studio의 사용자용 사이드바를 렌더링한다."""

from __future__ import annotations

from collections.abc import Callable

import streamlit as st

from .constants import STEP_LABELS
from .login import logout
from .theme import DEFAULT_THEME_MODE, THEME_LABELS, THEME_OPTIONS


def _step_state_label(step_id: int, current_step: int) -> str:
    if step_id < current_step:
        return "완료"
    if step_id == current_step:
        return "진행 중"
    return "대기"


def _bind_theme_widget_state() -> None:
    current = st.session_state.get("ui_theme_mode", DEFAULT_THEME_MODE)
    if current not in THEME_OPTIONS:
        current = DEFAULT_THEME_MODE
    st.session_state["_ui_theme_mode_input"] = current


def _sync_theme_mode() -> None:
    selected = st.session_state.get("_ui_theme_mode_input", DEFAULT_THEME_MODE)
    st.session_state.ui_theme_mode = selected if selected in THEME_OPTIONS else DEFAULT_THEME_MODE


def render_sidebar(on_step_change: Callable[[], None]) -> None:
    with st.sidebar:
        current_step = int(st.session_state.get("step", 1))

        st.markdown("## DeskAd AI")
        st.caption("3D 셋업부터 광고 콘텐츠까지 단계별로 제작합니다.")

        display_name = st.session_state.get("auth_display_name")
        if display_name:
            user_col, logout_col = st.columns([1.6, 1])
            with user_col:
                st.caption(f"{display_name} 님")
            with logout_col:
                if st.button("로그아웃", key="logout_button", use_container_width=True):
                    logout()

        st.divider()

        st.markdown("### 진행 요약")
        st.caption(f"현재 단계: {current_step}. {STEP_LABELS[current_step]}")
        st.progress(current_step / len(STEP_LABELS))

        for step_id, label in STEP_LABELS.items():
            state = _step_state_label(step_id, current_step)
            st.caption(f"{step_id}. {label} · {state}")

        st.divider()

        st.markdown("### 단계 이동")
        st.radio(
            "현재 단계",
            options=list(STEP_LABELS.keys()),
            format_func=lambda value: f"{value}. {STEP_LABELS[value]}",
            label_visibility="collapsed",
            key="step_selector",
            on_change=on_step_change,
        )

        st.divider()

        st.markdown("### 화면 모드")
        _bind_theme_widget_state()
        st.radio(
            "UI 테마",
            options=THEME_OPTIONS,
            format_func=lambda value: THEME_LABELS[value],
            label_visibility="collapsed",
            key="_ui_theme_mode_input",
            on_change=_sync_theme_mode,
        )

        st.divider()

        with st.expander("고급 설정 / 진단", expanded=False):
            st.caption("일반 제작 과정에서는 열어보지 않아도 되는 운영 정보입니다.")
            load_diagnostics = st.button("진단 정보 불러오기", use_container_width=True, key="load_diagnostics")

            with st.expander("API / 보안 상태", expanded=False):
                if load_diagnostics:
                    from .api_client import fetch_security_config

                    config = fetch_security_config()
                    st.caption(f"OpenAI Key: {config.get('openai_api_key', 'unknown')}")
                    st.caption(
                        "Tracks: "
                        f"OpenAI {config.get('openai_api_key', 'unknown')} · "
                        f"HyperCLOVA text {config.get('hyperclova_base_url', 'unknown')} / "
                        f"vision {config.get('hyperclova_vision_configured', 'unknown')} / "
                        f"image {config.get('hyperclova_image_configured', 'unknown')} · "
                        f"Local text {config.get('local_llm_base_url', 'unknown')} / "
                        f"ComfyUI {config.get('comfyui_base_url', 'unknown')}"
                    )
                    st.caption(f"STEP Converter: {config.get('step_converter_cmd', 'unknown')}")
                    st.caption("실제 키 값은 화면과 API 응답에 노출하지 않습니다.")
                else:
                    st.caption("필요할 때만 진단 정보를 불러옵니다.")

            with st.expander("도면 데이터", expanded=False):
                st.checkbox("키보드 하우징", value=True)
                st.checkbox("KiSwitch 스위치 footprint", value=True)
                st.checkbox("Acheron 계열 PCB", value=True)
                st.checkbox("STEP/STP 업로드", value=True)
                st.checkbox("데스크테리어 절차적 GLB", value=True)

            with st.expander("렌더링 설정", expanded=False):
                st.selectbox("카메라", ["perspective", "top", "front"], key="camera")
                st.checkbox("scene_hash 캐시 사용", value=True)

            with st.expander("광고 산출물", expanded=False):
                st.checkbox("SNS 카드", value=True)
                st.checkbox("상세페이지 배너", value=True)
                st.checkbox("광고 문구", value=True)
                st.checkbox("PPT 자료", value=False)
