"""이 파일은 Streamlit 세션 상태와 단계 이동 helper를 담당한다."""

from __future__ import annotations

from collections.abc import Callable

import streamlit as st

from .constants import KEYBOARD_MODEL_DEFAULTS, STEP_LABELS
from .defaults import DEFAULTS


def initialize_session_defaults(defaults: dict = DEFAULTS) -> None:
    """앱 최초 진입 시 필요한 session_state 기본값을 채운다."""
    for key, value in defaults.items():
        if isinstance(value, list):
            value = value.copy()
        elif isinstance(value, dict):
            value = value.copy()
        st.session_state.setdefault(key, value)

    if st.session_state.step_selector != st.session_state.step:
        st.session_state.step_selector = st.session_state.step


def sync_layout_from_model() -> None:
    defaults = KEYBOARD_MODEL_DEFAULTS.get(st.session_state.keyboard_model)
    if defaults:
        st.session_state.layout = defaults["layout"]


def set_step(step: int) -> None:
    step = max(1, min(len(STEP_LABELS), int(step)))
    st.session_state.step = step
    st.session_state.step_selector = step


def sync_step_from_sidebar() -> None:
    set_step(st.session_state.step_selector)


def invalidate_generated_ad_outputs() -> None:
    """상품 입력 변경 시 기존 광고 생성 결과를 비운다."""
    st.session_state.copy_result = None
    st.session_state.copy_selected_provider = None
    st.session_state.copy_experiment_result = None
    st.session_state.poster_result = None
    st.session_state.image_job_result = None
    st.session_state.image_quality_report = None


def go_next_step(render_before_next: Callable[[], None]) -> None:
    if st.session_state.step == 3 and not st.session_state.model_url:
        render_before_next()
    set_step(st.session_state.step + 1)


def go_previous_step() -> None:
    set_step(st.session_state.step - 1)
