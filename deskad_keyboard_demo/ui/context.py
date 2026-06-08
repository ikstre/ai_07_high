"""이 파일은 단계별 입력 UI에 넘길 dependency context를 담당한다."""

from __future__ import annotations

from collections.abc import Callable

from .ad_content import (
    generate_copy_experiment,
    generate_image_job,
    generate_poster,
    poster_waiting_for_image,
    render_copy_experiment_picker,
)
from .api_client import (
    fetch_ai_providers,
    fetch_desk_assets,
    fetch_layout_ids,
    fetch_model_library,
    fetch_reference_assets,
    fetch_security_config,
)
from .components import render_poster_template_thumbnails, render_reference_grid
from .constants import (
    CASE_FINISH_LABELS,
    KEYBOARD_MODEL_DEFAULTS,
    KEYBOARD_SIZE_INFO,
    KEYCAP_PROFILE_LABELS,
    MONITOR_ARM_LABELS,
    MONITOR_SIZES,
    MOUNT_TYPE_LABELS,
    PCB_COLOR_LABELS,
    PLATE_MATERIAL_LABELS,
    POSTER_TEMPLATE_LABELS,
    SWITCH_FAMILY_LABELS,
    SWITCH_STEM_LABELS,
)
from .model_library import render_model_load_panel
from .rendering import prepare_library_model, render_desk_setup, upload_reference_model


def build_step_ui_context(sync_layout_from_model: Callable[[], None]) -> dict:
    return {
        "CASE_FINISH_LABELS": CASE_FINISH_LABELS,
        "PLATE_MATERIAL_LABELS": PLATE_MATERIAL_LABELS,
        "PCB_COLOR_LABELS": PCB_COLOR_LABELS,
        "SWITCH_STEM_LABELS": SWITCH_STEM_LABELS,
        "SWITCH_FAMILY_LABELS": SWITCH_FAMILY_LABELS,
        "KEYCAP_PROFILE_LABELS": KEYCAP_PROFILE_LABELS,
        "MOUNT_TYPE_LABELS": MOUNT_TYPE_LABELS,
        "MONITOR_ARM_LABELS": MONITOR_ARM_LABELS,
        "POSTER_TEMPLATE_LABELS": POSTER_TEMPLATE_LABELS,
        "MONITOR_SIZES": MONITOR_SIZES,
        "KEYBOARD_SIZE_INFO": KEYBOARD_SIZE_INFO,
        "KEYBOARD_MODEL_DEFAULTS": KEYBOARD_MODEL_DEFAULTS,
        "sync_layout_from_model": sync_layout_from_model,
        "fetch_layout_ids": fetch_layout_ids,
        "upload_reference_model": upload_reference_model,
        "fetch_reference_assets": fetch_reference_assets,
        "render_reference_grid": render_reference_grid,
        "render_model_load_panel": render_model_load_panel,
        "fetch_model_library": fetch_model_library,
        "prepare_library_model": prepare_library_model,
        "fetch_desk_assets": fetch_desk_assets,
        "render_desk_setup": render_desk_setup,
        "render_poster_template_thumbnails": render_poster_template_thumbnails,
        "fetch_security_config": fetch_security_config,
        "generate_copy_experiment": generate_copy_experiment,
        "generate_image_job": generate_image_job,
        "poster_waiting_for_image": poster_waiting_for_image,
        "generate_poster": generate_poster,
        "fetch_ai_providers": fetch_ai_providers,
        "render_copy_experiment_picker": render_copy_experiment_picker,
    }
