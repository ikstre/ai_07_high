"""이 파일은 Streamlit 앱 진입점을 담당한다."""


from __future__ import annotations

import streamlit as st

from ui.components import render_campaign_studio_header, render_step_progress
from ui.context import build_step_ui_context
from ui.result_panel import render_result_panel
from ui.rendering import render_desk_setup
from ui.sidebar import render_sidebar
from ui.state import (
    go_next_step,
    go_previous_step,
    initialize_session_defaults,
    sync_layout_from_model,
    sync_step_from_sidebar,
)
from ui.styles import render_base_layout_styles, render_ui_theme_styles


st.set_page_config(
    page_title="DeskAd AI Studio",
    layout="wide",
    initial_sidebar_state="expanded",
)


render_base_layout_styles()
initialize_session_defaults()


def go_next() -> None:
    go_next_step(render_desk_setup)


def go_previous() -> None:
    go_previous_step()


render_sidebar(sync_step_from_sidebar)
render_ui_theme_styles(st.session_state.get("ui_theme_mode"))
render_step_progress()
render_campaign_studio_header()

render_result_panel(build_step_ui_context(sync_layout_from_model), go_previous, go_next)
