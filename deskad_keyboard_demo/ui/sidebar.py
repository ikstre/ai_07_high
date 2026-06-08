"""이 파일은 Streamlit 사이드바 렌더링을 담당한다."""

from __future__ import annotations

from collections.abc import Callable

import streamlit as st

from .api_client import fetch_security_config
from .constants import STEP_LABELS
from .theme import THEME_LABELS, THEME_OPTIONS


def render_sidebar(on_step_change: Callable[[], None]) -> None:
    with st.sidebar:
        st.markdown("## DeskAd AI")
        st.caption("도면 기반 3D 셋업 + 광고 콘텐츠 생성")

        st.divider()

        st.markdown("### 화면 모드")
        st.radio(
            "UI 테마",
            options=THEME_OPTIONS,
            format_func=lambda value: THEME_LABELS[value],
            label_visibility="collapsed",
            key="ui_theme_mode",
        )

        st.divider()

        st.markdown("### 작업 단계")
        st.radio(
            "현재 단계",
            options=list(STEP_LABELS.keys()),
            format_func=lambda value: f"{value}. {STEP_LABELS[value]}",
            label_visibility="collapsed",
            key="step_selector",
            on_change=on_step_change,
        )

        st.divider()

        config = fetch_security_config()
        with st.expander("API / 보안 상태", expanded=True):
            st.caption(f"OpenAI Key: {config.get('openai_api_key', 'unknown')}")
            st.caption(f"Local LLM: {config.get('local_llm_base_url', 'unknown')}")
            st.caption(f"STEP Converter: {config.get('step_converter_cmd', 'unknown')}")
            st.caption("실제 키 값은 화면과 API 응답에 노출하지 않습니다.")

        with st.expander("도면 데이터", expanded=True):
            st.checkbox("키보드 하우징", value=True)
            st.checkbox("KiSwitch 스위치 footprint", value=True)
            st.checkbox("Acheron 계열 PCB", value=True)
            st.checkbox("STEP/STP 업로드", value=True)
            st.checkbox("데스크테리어 절차적 GLB", value=True)

        with st.expander("렌더링 설정", expanded=True):
            st.selectbox("카메라", ["perspective", "top", "front"], key="camera")
            st.checkbox("scene_hash 캐시 사용", value=True)

        with st.expander("광고 산출물", expanded=False):
            st.checkbox("SNS 카드", value=True)
            st.checkbox("상세페이지 배너", value=True)
            st.checkbox("광고 문구", value=True)
            st.checkbox("PPT 자료", value=False)
