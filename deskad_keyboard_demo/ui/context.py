"""Streamlit 단계별 입력 UI에서 사용하는 dependency context를 구성한다.

무거운 API/UI helper는 앱 초기 로딩을 늦추지 않도록 필요한 시점에 import한다.
"""

from __future__ import annotations

from collections.abc import Callable

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
    POSTER_TEMPLATE_THUMBNAILS,
    SWITCH_FAMILY_LABELS,
    SWITCH_STEM_LABELS,
)


def _fetch_layout_ids() -> list[str]:
    from .api_client import fetch_layout_ids

    return fetch_layout_ids()


def _upload_reference_model(uploaded) -> None:
    from .rendering import upload_reference_model

    return upload_reference_model(uploaded)


def _fetch_reference_assets() -> list[dict]:
    from .api_client import fetch_reference_assets

    return fetch_reference_assets()


def _render_reference_grid(references: list[dict], columns: int = 4) -> None:
    from .components import render_reference_grid

    render_reference_grid(references, columns=columns)


def _render_model_load_panel() -> None:
    from .model_library import render_model_load_panel

    render_model_load_panel()


def _fetch_model_library() -> dict:
    from .api_client import fetch_model_library

    return fetch_model_library()


def _prepare_library_model(path: str) -> None:
    from .rendering import prepare_library_model

    return prepare_library_model(path)


def _fetch_desk_assets() -> list[dict]:
    from .api_client import fetch_desk_assets

    return fetch_desk_assets()


def _render_desk_setup() -> None:
    from .rendering import render_desk_setup

    render_desk_setup()


def _render_desk_setup_live(slot) -> None:
    from .rendering import render_desk_setup_live

    render_desk_setup_live(slot)


def _render_poster_template_thumbnails(current_key: str) -> None:
    from .components import render_poster_template_thumbnails

    render_poster_template_thumbnails(current_key)


def _fetch_security_config() -> dict:
    from .api_client import fetch_security_config

    return fetch_security_config()


def _generate_copy_experiment() -> None:
    from .ad_content import generate_copy_experiment

    generate_copy_experiment()


def _generate_copy_variants() -> None:
    from .ad_content import generate_copy_variants

    generate_copy_variants()


def _generate_copy_variants_live(slot) -> None:
    from .ad_content import generate_copy_variants_live

    generate_copy_variants_live(slot)


def _generate_image_job(force_regen: bool = False) -> dict:
    from .ad_content import generate_image_job

    return generate_image_job(force_regen=force_regen)


def _poster_waiting_for_image() -> bool:
    from .ad_content import poster_waiting_for_image

    return poster_waiting_for_image()


def _has_completed_image_job() -> bool:
    from .ad_content import has_completed_image_job

    return has_completed_image_job()


def _generate_poster(include_completed_image: bool = True) -> None:
    from .ad_content import generate_poster

    generate_poster(include_completed_image=include_completed_image)


def _generate_poster_live(slot, include_completed_image: bool = True) -> None:
    from .ad_content import generate_poster_live

    generate_poster_live(slot, include_completed_image=include_completed_image)


def _fetch_ai_providers() -> dict:
    from .api_client import fetch_ai_providers

    return fetch_ai_providers()


def _activate_engine_track(engine_id: str) -> dict:
    from .api_client import activate_engine_track

    return activate_engine_track(engine_id)


def _render_copy_experiment_picker() -> None:
    from .ad_content import render_copy_experiment_picker

    render_copy_experiment_picker()


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
        "POSTER_TEMPLATE_THUMBNAILS": POSTER_TEMPLATE_THUMBNAILS,
        "MONITOR_SIZES": MONITOR_SIZES,
        "KEYBOARD_SIZE_INFO": KEYBOARD_SIZE_INFO,
        "KEYBOARD_MODEL_DEFAULTS": KEYBOARD_MODEL_DEFAULTS,
        "sync_layout_from_model": sync_layout_from_model,
        "fetch_layout_ids": _fetch_layout_ids,
        "upload_reference_model": _upload_reference_model,
        "fetch_reference_assets": _fetch_reference_assets,
        "render_reference_grid": _render_reference_grid,
        "render_model_load_panel": _render_model_load_panel,
        "fetch_model_library": _fetch_model_library,
        "prepare_library_model": _prepare_library_model,
        "fetch_desk_assets": _fetch_desk_assets,
        "render_desk_setup": _render_desk_setup,
        "render_desk_setup_live": _render_desk_setup_live,
        "render_poster_template_thumbnails": _render_poster_template_thumbnails,
        "fetch_security_config": _fetch_security_config,
        "generate_copy_experiment": _generate_copy_experiment,
        "generate_copy_variants": _generate_copy_variants,
        "generate_copy_variants_live": _generate_copy_variants_live,
        "generate_image_job": _generate_image_job,
        "poster_waiting_for_image": _poster_waiting_for_image,
        "has_completed_image_job": _has_completed_image_job,
        "generate_poster": _generate_poster,
        "generate_poster_live": _generate_poster_live,
        "fetch_ai_providers": _fetch_ai_providers,
        "activate_engine_track": _activate_engine_track,
        "render_copy_experiment_picker": _render_copy_experiment_picker,
    }
