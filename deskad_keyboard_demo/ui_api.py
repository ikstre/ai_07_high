"""이 파일은 기존 ui_api import 호환을 담당한다."""

from ui.api_client import (
    API_BASE,
    PUBLIC_API_BASE,
    api_get,
    api_post,
    fetch_binary_data_url,
    fetch_text_asset,
    poster_preview_height,
    reference_thumbnail_bytes,
    responsive_svg_document,
    svg_aspect_ratio,
    to_internal_api_url,
)

__all__ = [
    "API_BASE",
    "PUBLIC_API_BASE",
    "api_get",
    "api_post",
    "fetch_binary_data_url",
    "fetch_text_asset",
    "poster_preview_height",
    "reference_thumbnail_bytes",
    "responsive_svg_document",
    "svg_aspect_ratio",
    "to_internal_api_url",
]
