"""이 파일은 Streamlit 앱 진입점을 담당한다."""


from __future__ import annotations

import streamlit as st

from ui.components import render_campaign_studio_header
from ui.context import build_step_ui_context
from ui.login import is_authenticated, render_login_page
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
# 테마 CSS는 사이드바/본문(가변 요소)보다 먼저, 고정된 위치에서 주입한다. 위젯이 바뀌면
# 새 값이 rerun 시작 시점에 session_state에 이미 반영되므로 여기서 읽어도 최신이며,
# 주입 위치가 안정되어 첫 상호작용 후 테마가 바뀐 채 유지되던 현상을 막는다(2026-06-13 QA #2).
render_ui_theme_styles(st.session_state.get("ui_theme_mode"))

if not is_authenticated():
    render_login_page()
    st.stop()


def go_next() -> None:
    go_next_step(render_desk_setup)


def go_previous() -> None:
    go_previous_step()


render_sidebar(sync_step_from_sidebar)
render_campaign_studio_header()

render_result_panel(build_step_ui_context(sync_layout_from_model), go_previous, go_next)
