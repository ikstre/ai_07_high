"""이 파일은 API 호출과 캐시 helper를 담당한다."""

from __future__ import annotations

import base64
import os
import re
from pathlib import Path

import requests
import streamlit as st


APP_DIR = Path(__file__).resolve().parents[1]


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env_file(APP_DIR / ".env")
API_BASE = os.getenv("DESKAD_API_BASE", "http://127.0.0.1:8010").rstrip("/")
PUBLIC_API_BASE = os.getenv("DESKAD_PUBLIC_API_BASE", API_BASE).rstrip("/")
POSTER_PREVIEW_MAX_WIDTH = 820
_SVG_NUMBER_PATTERN = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"

DEFAULT_LAYOUT_FALLBACK = ["60", "65", "75", "87", "104"]

FALLBACK_ASSETS = [
    {"id": "mouse", "label": "무선 마우스", "category": "input"},
    {"id": "monitor", "label": "모니터", "category": "display"},
    {"id": "monitor_arm", "label": "VESA 모니터암", "category": "display"},
    {"id": "monitor_light_bar", "label": "모니터 라이트 바", "category": "lighting"},
    {"id": "desk_lamp", "label": "데스크 조명", "category": "lighting"},
    {"id": "plant", "label": "미니 화분", "category": "decor"},
    {"id": "speakers", "label": "북쉘프 스피커", "category": "audio"},
    {"id": "desk_shelf", "label": "모니터 받침대", "category": "furniture"},
    {"id": "notebook", "label": "노트/플래너", "category": "stationery"},
    {"id": "headphone_stand", "label": "헤드폰 스탠드", "category": "audio"},
    {"id": "phone_stand", "label": "스마트폰 스탠드", "category": "accessory"},
    {"id": "keycap_tray", "label": "키캡 진열 트레이", "category": "keyboard"},
    {"id": "coffee_mug", "label": "머그컵", "category": "decor"},
    {"id": "digital_clock", "label": "디지털 시계", "category": "decor"},
    {"id": "aroma_diffuser", "label": "아로마 디퓨저", "category": "decor"},
    {"id": "wireless_charger", "label": "무선 충전 패드", "category": "accessory"},
    {"id": "pen_holder", "label": "펜 꽂이", "category": "stationery"},
    {"id": "book_stack", "label": "책 묶음", "category": "decor"},
    {"id": "humidifier", "label": "가습기", "category": "decor"},
    {"id": "photo_frame", "label": "사진 액자", "category": "decor"},
    {"id": "usb_hub", "label": "USB 허브", "category": "accessory"},
    {"id": "mouse_pad_round", "label": "라운드 마우스패드", "category": "input"},
]


def api_get(path: str, timeout: int = 10) -> dict:
    response = requests.get(f"{API_BASE}{path}", timeout=timeout)
    response.raise_for_status()
    return response.json()


def api_post(path: str, payload: dict, timeout: int = 30) -> dict:
    response = requests.post(f"{API_BASE}{path}", json=payload, timeout=timeout)
    response.raise_for_status()
    return response.json()


def activate_engine_track(track: str) -> dict:
    """선택한 생성 엔진(트랙)의 GPU 워커를 백엔드에 미리 워밍업시킨다.

    백엔드가 daemon thread로 처리하므로 빠르게 반환된다. 실패해도 실제 생성
    경로의 ensure_*_worker가 다시 보장하므로 UI에서는 조용히 무시한다.
    """
    try:
        return api_post("/ai/activate_track", {"track": track}, timeout=10)
    except Exception:
        return {}


def to_internal_api_url(url: str) -> str:
    if PUBLIC_API_BASE != API_BASE and url.startswith(PUBLIC_API_BASE):
        return API_BASE + url[len(PUBLIC_API_BASE):]
    return url


@st.cache_data(ttl=300)
def fetch_binary_data_url(url: str, mime_type: str) -> str:
    response = requests.get(to_internal_api_url(url), timeout=30)
    response.raise_for_status()
    encoded = base64.b64encode(response.content).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


@st.cache_data(ttl=300)
def fetch_text_asset(url: str) -> str:
    response = requests.get(to_internal_api_url(url), timeout=30)
    response.raise_for_status()
    return response.text


@st.cache_data(ttl=600)
def reference_thumbnail_bytes(url: str) -> bytes:
    """Return a downscaled PNG thumbnail for a raster reference asset."""
    from io import BytesIO

    from PIL import Image

    response = requests.get(to_internal_api_url(url), timeout=30)
    response.raise_for_status()
    image = Image.open(BytesIO(response.content))
    image.thumbnail((320, 320))
    if image.mode not in ("RGB", "RGBA", "L"):
        image = image.convert("RGB")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def svg_aspect_ratio(svg: str) -> float:
    """Return SVG height/width ratio from viewBox or explicit dimensions."""
    match = re.search(
        rf'viewBox=["\']\s*{_SVG_NUMBER_PATTERN}[\s,]+{_SVG_NUMBER_PATTERN}[\s,]+'
        rf'({_SVG_NUMBER_PATTERN})[\s,]+({_SVG_NUMBER_PATTERN})',
        svg,
    )
    if match:
        width, height = float(match.group(1)), float(match.group(2))
        if width > 0:
            return height / width
    width_match = re.search(r'<svg[^>]*\bwidth=["\']([\d.]+)', svg)
    height_match = re.search(r'<svg[^>]*\bheight=["\']([\d.]+)', svg)
    if width_match and height_match and float(width_match.group(1)) > 0:
        return float(height_match.group(1)) / float(width_match.group(1))
    return 1.0


def poster_preview_height(svg: str, max_width: int = POSTER_PREVIEW_MAX_WIDTH) -> int:
    """Return iframe height that fits the whole poster SVG without clipping."""
    return round(max_width * svg_aspect_ratio(svg)) + 16


def responsive_svg_document(svg: str, max_width: int = POSTER_PREVIEW_MAX_WIDTH) -> str:
    return f"""
    <!doctype html>
    <html>
      <head>
        <meta charset="utf-8" />
        <style>
          html, body {{
            margin: 0;
            width: 100%;
            min-height: 100%;
            background: transparent;
            overflow: hidden;
          }}
          .poster-frame {{
            width: 100%;
            max-width: {max_width}px;
            margin: 0 auto;
            box-sizing: border-box;
            padding: 0;
          }}
          .poster-frame svg {{
            display: block;
            width: 100%;
            height: auto;
            max-width: 100%;
          }}
        </style>
      </head>
      <body>
        <div class="poster-frame">{svg}</div>
      </body>
    </html>
    """


@st.cache_data(ttl=15)
def fetch_security_config() -> dict:
    try:
        return api_get("/security/config")
    except Exception:
        return {
            "openai_api_key": "unknown",
            "local_llm_base_url": "unknown",
            "hyperclova_base_url": "unknown",
            "hyperclova_vision_configured": "unknown",
            "hyperclova_image_configured": "unknown",
            "kanana_base_url": "unknown",
            "midm_base_url": "unknown",
            "local_image_endpoint": "unknown",
            "comfyui_base_url": "unknown",
            "image_model_backend": "unknown",
            "step_converter_cmd": "unknown",
        }


@st.cache_data(ttl=15)
def fetch_ai_providers() -> dict:
    try:
        return api_get("/ai/providers")
    except Exception:
        return {"providers": [], "auto_order": []}


@st.cache_data(ttl=30)
def fetch_desk_assets() -> list[dict]:
    try:
        return api_get("/assets/desk")["assets"]
    except Exception:
        return FALLBACK_ASSETS


@st.cache_data(ttl=60)
def fetch_layout_ids() -> list[str]:
    try:
        payload = api_get("/layouts")
        layouts = payload.get("layouts") or []
        ids = [item["id"] for item in layouts if isinstance(item, dict) and item.get("id")]
        return ids or list(DEFAULT_LAYOUT_FALLBACK)
    except Exception:
        return list(DEFAULT_LAYOUT_FALLBACK)


@st.cache_data(ttl=30)
def fetch_reference_assets() -> list[dict]:
    try:
        return api_get("/assets/references")["references"]
    except Exception:
        return []


@st.cache_data(ttl=30)
def fetch_model_library() -> dict:
    try:
        return api_get("/models/library")
    except Exception:
        return {"files": [], "model_compatible_extensions": []}
