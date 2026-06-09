"""이 파일은 Streamlit 사이드바 렌더링을 담당한다."""

from __future__ import annotations

import os
from collections.abc import Callable

import streamlit as st

from .api_client import fetch_security_config
from .constants import STEP_LABELS
from .theme import THEME_LABELS, THEME_OPTIONS

# 카메라 각도 한국어 라벨 — 사이드바에서 기술 용어(perspective 등)를 그대로 노출하지 않는다.
_CAMERA_LABELS = {
    "perspective": "입체 (3/4 뷰)",
    "top": "위에서 (탑뷰)",
    "front": "정면",
}

# 단계별 한 줄 안내 — 처음 쓰는 사용자가 다음에 뭘 할지 바로 알 수 있게 한다.
_STEP_HINTS = {
    1: "상품명·가격·타깃을 입력하세요.",
    2: "키보드 모델/배열과 도면·레퍼런스를 고르세요.",
    3: "셋업 구성품을 배치하고 3D 셋업을 생성하세요.",
    4: "엔진을 고르고 문구·실사 이미지·포스터를 생성하세요.",
}


def _operator_mode() -> bool:
    """운영자 진단(API/키 상태) 노출 여부. 기본 숨김 — 소비자 화면에는 기술 정보를 보이지 않는다."""
    return os.getenv("DESKAD_OPERATOR_MODE", "").strip().lower() in ("1", "true", "yes", "on")


def render_sidebar(on_step_change: Callable[[], None]) -> None:
    with st.sidebar:
        st.markdown("## 🖥️ DeskAd AI Studio")
        st.caption("도면 기반 3D 셋업으로 광고 콘텐츠를 만드는 스튜디오")

        st.divider()

        st.markdown("### 진행 단계")
        st.radio(
            "현재 단계",
            options=list(STEP_LABELS.keys()),
            format_func=lambda value: f"{value}. {STEP_LABELS[value]}",
            label_visibility="collapsed",
            key="step_selector",
            on_change=on_step_change,
        )
        current_step = st.session_state.get("step_selector", 1)
        if current_step in _STEP_HINTS:
            st.info(_STEP_HINTS[current_step], icon="👉")

        st.divider()

        st.markdown("### 화면 설정")
        st.radio(
            "화면 모드",
            options=THEME_OPTIONS,
            format_func=lambda value: THEME_LABELS[value],
            key="ui_theme_mode",
        )
        st.selectbox(
            "3D 미리보기 각도",
            ["perspective", "top", "front"],
            format_func=lambda value: _CAMERA_LABELS.get(value, value),
            key="camera",
        )

        # 운영자 모드에서만 기술 진단을 노출(소비자 화면 단순화).
        if _operator_mode():
            st.divider()
            config = fetch_security_config()
            with st.expander("운영자 진단 (API / 보안)", expanded=False):
                st.caption(f"OpenAI Key: {config.get('openai_api_key', 'unknown')}")
                st.caption(f"Local LLM: {config.get('local_llm_base_url', 'unknown')}")
                st.caption(f"ComfyUI: {config.get('comfyui_base_url', 'unknown')}")
                st.caption(f"STEP Converter: {config.get('step_converter_cmd', 'unknown')}")
                st.caption("실제 키 값은 화면과 API 응답에 노출하지 않습니다.")
