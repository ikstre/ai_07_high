
from __future__ import annotations

import html
import textwrap
from pathlib import Path
from uuid import uuid4

import requests

from .config import get_settings


STYLE_COPY = {
    "minimal": {
        "mood": "정돈된 데스크 셋업을 완성하는",
        "headline": "작은 책상에도 선명한 존재감",
        "cta": "오늘 셋업에 바로 더해보세요",
    },
    "pastel": {
        "mood": "부드러운 컬러감으로 공간을 환하게 만드는",
        "headline": "책상 위에 남는 은은한 포인트",
        "cta": "감성 셋업을 지금 구성해보세요",
    },
    "premium": {
        "mood": "고급스러운 작업 공간에 어울리는",
        "headline": "완성도 높은 데스크를 위한 선택",
        "cta": "프리미엄 구성을 확인하세요",
    },
    "gaming": {
        "mood": "RGB 무드와 몰입감을 살린",
        "headline": "플레이와 작업을 모두 잡는 셋업",
        "cta": "나만의 배틀스테이션을 완성하세요",
    },
}


def _request_json(url: str, *, headers: dict, payload: dict, timeout: int) -> dict:
    response = requests.post(url, headers=headers, json=payload, timeout=timeout)
    response.raise_for_status()
    return response.json()


def _ad_context(payload: dict) -> str:
    return "\n".join(
        [
            f"상품명: {payload.get('product_name', '커스텀 키보드 셋업')}",
            f"상품 유형: {payload.get('product_type', '커스텀 키보드')}",
            f"판매가: {payload.get('price', '')}",
            f"채널: {payload.get('target_channel', '인스타그램')}",
            f"타깃: {payload.get('target_customer', '데스크테리어에 관심 있는 고객')}",
            f"소구점: {payload.get('selling_point', '')}",
            f"광고 톤: {payload.get('ad_tone', '감성형')}",
            f"스타일: {payload.get('theme', 'minimal')}",
            f"포함 물품: {', '.join(payload.get('assets', []))}",
            f"추가 요청: {payload.get('extra_request', '')}",
        ]
    )


def _fallback_copy(payload: dict, provider: str = "fallback", error: str | None = None) -> dict:
    style = STYLE_COPY.get(payload.get("theme", "minimal"), STYLE_COPY["minimal"])
    product_name = payload.get("product_name") or "커스텀 키보드 셋업"
    selling_point = payload.get("selling_point") or "키보드와 데스크테리어 제품을 한 번에 보여주는 3D 셋업"
    target_channel = payload.get("target_channel") or "인스타그램"

    copies = [
        f"{style['mood']} {product_name}",
        f"{selling_point}을 실제 촬영 없이 광고 이미지로 준비하세요.",
        f"{target_channel}에 바로 올리기 좋은 데스크 셋업 콘텐츠를 생성합니다.",
    ]
    return {
        "provider": provider,
        "copies": copies,
        "headline": style["headline"],
        "subcopy": copies[1],
        "cta": style["cta"],
        "hashtags": ["#커스텀키보드", "#데스크테리어", "#데스크셋업", "#소상공인광고"],
        "error": error,
    }


def _openai_copy(payload: dict) -> dict:
    settings = get_settings()
    url = f"{settings.openai_base_url.rstrip('/')}/chat/completions"
    prompt = (
        "너는 한국 소상공인 쇼핑몰 광고 카피라이터다. "
        "커스텀 키보드와 데스크테리어 판매자가 바로 쓸 수 있게 과장 없이 짧은 한국어 광고 문구를 만든다. "
        "반드시 JSON 형태로 headline, subcopy, cta, copies, hashtags를 반환한다.\n\n"
        + _ad_context(payload)
    )
    result = _request_json(
        url,
        headers={"Authorization": f"Bearer {settings.openai_api_key}", "Content-Type": "application/json"},
        payload={
            "model": settings.openai_text_model,
            "temperature": 0.7,
            "messages": [
                {"role": "system", "content": "Return concise Korean ad copy. Do not include secrets or API keys."},
                {"role": "user", "content": prompt},
            ],
        },
        timeout=settings.request_timeout_seconds,
    )
    content = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
    fallback = _fallback_copy(payload, provider="openai")
    if content:
        lines = [line.strip(" -") for line in content.splitlines() if line.strip()]
        fallback["copies"] = lines[:4] or fallback["copies"]
        fallback["subcopy"] = fallback["copies"][1] if len(fallback["copies"]) > 1 else fallback["subcopy"]
        fallback["raw"] = content
    return fallback


def _local_copy(payload: dict) -> dict:
    settings = get_settings()
    base = settings.local_llm_base_url.rstrip("/")
    url = f"{base}/chat/completions" if base.endswith("/v1") else f"{base}/v1/chat/completions"
    result = _request_json(
        url,
        headers={"Content-Type": "application/json"},
        payload={
            "model": settings.local_llm_model or "local-model",
            "temperature": 0.7,
            "messages": [
                {"role": "system", "content": "한국어 쇼핑몰 광고 문구를 짧게 생성한다."},
                {"role": "user", "content": _ad_context(payload)},
            ],
        },
        timeout=settings.request_timeout_seconds,
    )
    content = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
    fallback = _fallback_copy(payload, provider="local_llm")
    if content:
        fallback["copies"] = [line.strip(" -") for line in content.splitlines() if line.strip()][:4] or fallback["copies"]
        fallback["subcopy"] = fallback["copies"][1] if len(fallback["copies"]) > 1 else fallback["subcopy"]
        fallback["raw"] = content
    return fallback


def generate_ad_copy(payload: dict) -> dict:
    settings = get_settings()
    provider = settings.ai_provider.lower()
    errors: list[str] = []

    if provider in {"auto", "openai"} and settings.has_openai_key:
        try:
            return _openai_copy(payload)
        except Exception as exc:
            errors.append(f"openai: {exc}")
            if provider == "openai":
                return _fallback_copy(payload, provider="fallback_after_openai_error", error="; ".join(errors))

    if provider in {"auto", "local"} and settings.has_local_llm:
        try:
            return _local_copy(payload)
        except Exception as exc:
            errors.append(f"local: {exc}")

    return _fallback_copy(payload, error="; ".join(errors) if errors else None)


def build_image_prompt(payload: dict, copy_result: dict) -> str:
    assets = ", ".join(payload.get("assets", [])) or "keyboard, deskmat, monitor"
    style = payload.get("theme", "minimal")
    product = payload.get("product_name", "custom keyboard desk setup")
    return (
        f"Korean ecommerce poster for {product}, deskterior setup with {assets}, "
        f"style {style}, clean top-view and three-quarter product composition, "
        "clear negative space for Korean headline, realistic lighting, no brand logos. "
        f"Headline idea: {copy_result.get('headline', '')}"
    )


def _wrap(text: str, width: int) -> list[str]:
    text = str(text or "")
    if len(text) <= width:
        return [text]
    return textwrap.wrap(text, width=width, break_long_words=False, replace_whitespace=False)[:3]


def create_svg_poster(payload: dict, copy_result: dict, *, ratio: str = "1:1") -> str:
    width, height = {"1:1": (1080, 1080), "4:5": (1080, 1350), "16:9": (1600, 900)}.get(ratio, (1080, 1080))
    theme = payload.get("theme", "minimal")
    palettes = {
        "minimal": ("#f5f2ea", "#2f3438", "#8aa0a8", "#d8b892"),
        "pastel": ("#f8f0f3", "#334155", "#9bbbd4", "#e8c7b8"),
        "premium": ("#eef0ec", "#15181d", "#b08d57", "#4b5563"),
        "gaming": ("#10131a", "#f8fafc", "#7c3aed", "#0ea5e9"),
    }
    bg, ink, accent, wood = palettes.get(theme, palettes["minimal"])
    product = html.escape(payload.get("product_name", "DeskAd Setup"))
    price = html.escape(payload.get("price", ""))
    headline = html.escape(copy_result.get("headline") or copy_result.get("copies", [product])[0])
    subcopy = html.escape(copy_result.get("subcopy") or "3D 셋업 미리보기 기반 광고 콘텐츠")
    cta = html.escape(copy_result.get("cta") or "지금 확인하기")

    desk_x = int(width * 0.13)
    desk_y = int(height * 0.35)
    desk_w = int(width * 0.74)
    desk_h = int(height * 0.36)
    mat_x = int(width * 0.25)
    mat_y = int(height * 0.48)
    mat_w = int(width * 0.5)
    mat_h = int(height * 0.16)

    headline_lines = _wrap(headline, 18)
    subcopy_lines = _wrap(subcopy, 28)
    headline_svg = "".join(
        f'<text x="{int(width*0.08)}" y="{int(height*0.12) + i*58}" font-size="48" font-weight="800" fill="{ink}">{line}</text>'
        for i, line in enumerate(headline_lines)
    )
    subcopy_svg = "".join(
        f'<text x="{int(width*0.08)}" y="{int(height*0.24) + i*34}" font-size="25" fill="{ink}" opacity="0.78">{line}</text>'
        for i, line in enumerate(subcopy_lines)
    )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="{width}" height="{height}" fill="{bg}"/>
  <rect x="{desk_x}" y="{desk_y}" width="{desk_w}" height="{desk_h}" rx="28" fill="{wood}" opacity="0.92"/>
  <rect x="{mat_x}" y="{mat_y}" width="{mat_w}" height="{mat_h}" rx="22" fill="{accent}" opacity="0.72"/>
  <rect x="{int(width*0.34)}" y="{int(height*0.52)}" width="{int(width*0.27)}" height="{int(height*0.075)}" rx="12" fill="{ink}" opacity="0.88"/>
  <g opacity="0.93">
    <rect x="{int(width*0.36)}" y="{int(height*0.535)}" width="{int(width*0.032)}" height="{int(height*0.019)}" rx="4" fill="{bg}"/>
    <rect x="{int(width*0.405)}" y="{int(height*0.535)}" width="{int(width*0.032)}" height="{int(height*0.019)}" rx="4" fill="{bg}"/>
    <rect x="{int(width*0.45)}" y="{int(height*0.535)}" width="{int(width*0.032)}" height="{int(height*0.019)}" rx="4" fill="{bg}"/>
    <rect x="{int(width*0.495)}" y="{int(height*0.535)}" width="{int(width*0.032)}" height="{int(height*0.019)}" rx="4" fill="{bg}"/>
    <rect x="{int(width*0.54)}" y="{int(height*0.535)}" width="{int(width*0.05)}" height="{int(height*0.019)}" rx="4" fill="{bg}"/>
  </g>
  <rect x="{int(width*0.66)}" y="{int(height*0.515)}" width="{int(width*0.07)}" height="{int(height*0.11)}" rx="32" fill="{ink}" opacity="0.72"/>
  <rect x="{int(width*0.39)}" y="{int(height*0.39)}" width="{int(width*0.22)}" height="{int(height*0.075)}" rx="8" fill="{ink}" opacity="0.86"/>
  <rect x="{int(width*0.405)}" y="{int(height*0.4)}" width="{int(width*0.19)}" height="{int(height*0.048)}" rx="4" fill="{accent}" opacity="0.76"/>
  {headline_svg}
  {subcopy_svg}
  <text x="{int(width*0.08)}" y="{int(height*0.82)}" font-size="31" font-weight="700" fill="{ink}">{product}</text>
  <text x="{int(width*0.08)}" y="{int(height*0.86)}" font-size="25" fill="{ink}" opacity="0.72">{price}</text>
  <rect x="{int(width*0.08)}" y="{int(height*0.89)}" width="{int(width*0.25)}" height="62" rx="31" fill="{accent}"/>
  <text x="{int(width*0.105)}" y="{int(height*0.89)+40}" font-size="24" font-weight="800" fill="{bg}">{cta}</text>
</svg>'''


def save_poster_svg(*, payload: dict, copy_result: dict, poster_dir: Path) -> dict:
    poster_dir.mkdir(parents=True, exist_ok=True)
    ratio = payload.get("image_ratio", "1:1")
    poster_name = f"poster_{uuid4().hex[:10]}.svg"
    poster_path = poster_dir / poster_name
    poster_path.write_text(create_svg_poster(payload, copy_result, ratio=ratio), encoding="utf-8")
    return {"poster_file": poster_name, "poster_path": poster_path}


def generate_local_image_reference(payload: dict, image_prompt: str) -> dict | None:
    settings = get_settings()
    if not settings.has_local_image:
        return None
    try:
        result = _request_json(
            settings.local_image_endpoint,
            headers={"Content-Type": "application/json"},
            payload={"prompt": image_prompt, "metadata": payload},
            timeout=settings.request_timeout_seconds,
        )
    except Exception as exc:
        return {"provider": "local_image", "error": str(exc)}
    return {"provider": "local_image", "result": result}
