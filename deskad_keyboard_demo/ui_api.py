"""Backend API client + asset fetch/transform helpers for the Streamlit app.

Extracted from streamlit_app.py (phase 1 of the module split): this is the
self-contained HTTP/asset layer with no dependency on the UI's session state or
step flow. Loads the frontend .env on import so API_BASE is correct regardless
of import order.
"""
from __future__ import annotations

import base64
import os
import re
from pathlib import Path

import requests
import streamlit as st


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env_file(Path(__file__).resolve().parent / ".env")

API_BASE = os.getenv("DESKAD_API_BASE", "http://127.0.0.1:8010").rstrip("/")
PUBLIC_API_BASE = os.getenv("DESKAD_PUBLIC_API_BASE", API_BASE).rstrip("/")

# 포스터 미리보기 표시 폭(px). iframe 높이를 이 폭 × SVG 종횡비로 잡아
# 1:1 포스터 하단이 잘리지 않게 한다(성현 문서 "남은 확인 사항"). 결과 컬럼이
# 더 넓어도 포스터는 이 폭으로 가운데 정렬되어 전체가 보인다.
POSTER_PREVIEW_MAX_WIDTH = 820


def api_get(path: str, timeout: int = 10) -> dict:
    response = requests.get(f"{API_BASE}{path}", timeout=timeout)
    response.raise_for_status()
    return response.json()


def api_post(path: str, payload: dict, timeout: int = 30) -> dict:
    response = requests.post(f"{API_BASE}{path}", json=payload, timeout=timeout)
    response.raise_for_status()
    return response.json()


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
    """Downscaled PNG thumbnail for a raster reference, cached per url so
    Streamlit reruns don't refetch the (sometimes multi-MB) originals."""
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
    """SVG의 height/width 비율. viewBox > width/height 속성 순, 기본 1.0(정사각)."""
    match = re.search(r'viewBox=["\']\s*[\d.]+\s+[\d.]+\s+([\d.]+)\s+([\d.]+)', svg)
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
    """잘림 없이 포스터 전체를 담는 iframe 높이(px)."""
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
