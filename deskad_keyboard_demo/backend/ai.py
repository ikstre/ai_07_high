from __future__ import annotations

import base64
import html
import json
import re
import textwrap
from pathlib import Path
from uuid import uuid4

import requests

from .config import get_settings


STYLE_COPY = {
    "minimal": {
        "mood": "정돈된 데스크 셋업에 어울리는",
        "headline": "작은 책상 위에도 선명한 존재감",
        "cta": "셋업 보기",
    },
    "pastel": {
        "mood": "부드러운 컬러감으로 공간을 환하게 만드는",
        "headline": "책상 위에 얹는 차분한 포인트",
        "cta": "구성 보기",
    },
    "premium": {
        "mood": "고급스러운 작업 공간에 어울리는",
        "headline": "완성도 높은 데스크를 위한 선택",
        "cta": "자세히 보기",
    },
    "gaming": {
        "mood": "몰입감 있는 게임 환경에 맞춘",
        "headline": "플레이와 작업을 모두 잡는 셋업",
        "cta": "지금 구성",
    },
}

TONE_HINTS = {
    "프리미엄형": "차분하고 절제된 문장, 마감과 디테일 강조",
    "감성형": "데스크테리어와 공간 분위기를 중심으로 묘사",
    "할인형": "구매 이유와 가격 메리트를 직접적으로 강조",
    "기능강조형": "스펙, 치수, 구성품, 사용성을 사실 기반으로 설명",
}


def _request_json(url: str, *, headers: dict, payload: dict, timeout: int) -> dict:
    """지정한 JSON API로 POST 요청을 보내고 응답 JSON을 반환한다."""
    response = requests.post(url, headers=headers, json=payload, timeout=timeout)
    response.raise_for_status()
    return response.json()


def _ad_context(payload: dict) -> str:
    """광고 생성에 필요한 상품, 타깃, 렌더링 정보를 프롬프트 문맥으로 정리한다."""
    tone = payload.get("ad_tone", "감성형")
    extras = []
    if payload.get("layout"):
        extras.append(f"키보드 배열: {payload['layout']}")
    if payload.get("case_finish"):
        extras.append(f"케이스 마감: {payload['case_finish']}")
    if payload.get("plate_material"):
        extras.append(f"보강판: {payload['plate_material']}")
    if payload.get("switch_stem"):
        extras.append(f"스위치: {payload['switch_stem']}")
    if payload.get("monitor_size"):
        extras.append(f"모니터: {payload['monitor_size']}인치")

    return "\n".join(
        [
            f"상품명: {payload.get('product_name', '커스텀 키보드 데스크 셋업')}",
            f"상품 유형: {payload.get('product_type', '커스텀 키보드')}",
            f"가격: {payload.get('price', '')}",
            f"판매 채널: {payload.get('target_channel', '인스타그램')}",
            f"타깃 고객: {payload.get('target_customer', '데스크테리어에 관심 있는 사용자')}",
            f"핵심 특징: {payload.get('selling_point', '')}",
            f"광고 톤: {tone} ({TONE_HINTS.get(tone, '')})",
            f"테마: {payload.get('theme', 'minimal')}",
            f"포함 오브젝트: {', '.join(payload.get('assets', []))}",
            f"렌더링 구성: {' / '.join(extras)}" if extras else "",
            f"추가 요청: {payload.get('extra_request', '')}",
            f"3D 모델 URL: {payload.get('model_url') or '아직 없음'}",
        ]
    )


def _extract_json_block(text: str) -> dict | None:
    """모델 응답 텍스트에서 JSON 코드블록이나 중괄호 객체를 찾아 파싱한다."""
    if not text:
        return None
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        try:
            return json.loads(fenced.group(1))
        except json.JSONDecodeError:
            pass
    brace = re.search(r"\{[\s\S]*\}", text)
    if brace:
        try:
            return json.loads(brace.group(0))
        except json.JSONDecodeError:
            return None
    return None


def _fallback_copy(payload: dict, provider: str = "fallback", error: str | None = None) -> dict:
    """외부 모델을 사용할 수 없거나 실패했을 때 기본 광고 문구 응답을 생성한다."""
    style = STYLE_COPY.get(payload.get("theme", "minimal"), STYLE_COPY["minimal"])
    product_name = payload.get("product_name") or "커스텀 키보드 데스크 셋업"
    selling_point = payload.get("selling_point") or "3D 데스크 셋업 미리보기로 제품의 분위기와 구성을 한 번에 보여줍니다."
    target_channel = payload.get("target_channel") or "인스타그램"
    tone = payload.get("ad_tone", "감성형")

    copies = [
        f"{style['mood']} {product_name}",
        f"{selling_point} 실제 촬영 없이도 광고용 비주얼과 문구를 빠르게 준비할 수 있습니다.",
        f"{target_channel}에 바로 올리기 좋은 데스크 셋업 콘텐츠를 만들어보세요.",
        f"{tone} 톤으로 제품의 특징과 공간 분위기를 자연스럽게 전달합니다.",
    ]
    return {
        "provider": provider,
        "copies": copies,
        "headline": style["headline"],
        "subcopy": copies[1],
        "cta": style["cta"],
        "hashtags": ["#커스텀키보드", "#데스크테리어", "#데스크셋업", "#키보드추천"],
        "spec_bullets": [
            payload.get("product_type", "커스텀 키보드"),
            f"가격 {payload.get('price', '')}".strip(),
            payload.get("selling_point", ""),
        ],
        "error": error,
    }


def _merge_structured_response(base: dict, parsed: dict | None) -> dict:
    """fallback 응답에 모델이 반환한 구조화 필드를 병합한다."""
    if not parsed:
        return base
    for key in ("headline", "subcopy", "cta"):
        if parsed.get(key):
            base[key] = str(parsed[key]).strip()
    if parsed.get("copies"):
        copies = [str(c).strip() for c in parsed["copies"] if str(c).strip()]
        if copies:
            base["copies"] = copies[:5]
            if not parsed.get("subcopy"):
                base["subcopy"] = copies[1] if len(copies) > 1 else base.get("subcopy")
    if parsed.get("hashtags"):
        hashtags = [str(h).strip().lstrip("#") for h in parsed["hashtags"] if str(h).strip()]
        base["hashtags"] = ["#" + h for h in hashtags[:6]]
    if parsed.get("spec_bullets") or parsed.get("specs"):
        bullets = parsed.get("spec_bullets") or parsed.get("specs")
        base["spec_bullets"] = [str(b).strip() for b in bullets if str(b).strip()][:5]
    return base


def _system_prompt() -> str:
    """광고 문구 모델에 전달할 역할, 제약, JSON 출력 규칙을 만든다."""
    return (
        "너는 한국어 이커머스 광고 카피라이터다. "
        "커스텀 키보드와 데스크테리어 제품을 판매자가 바로 사용할 수 있는 문구로 정리한다. "
        "과장하지 말고 입력된 사실만 사용한다. 반드시 JSON 객체 하나만 반환한다. "
        "필드는 headline, subcopy, cta, copies, hashtags, spec_bullets를 사용한다. "
        "headline은 22자 이내, subcopy는 45자 이내, cta는 12자 이내로 작성한다. "
        "copies는 4~5개 문장, hashtags는 4~6개, spec_bullets는 3~5개로 작성한다."
    )


def _openai_copy(payload: dict) -> dict:
    """OpenAI 호환 chat completions API로 광고 문구를 생성한다."""
    settings = get_settings()
    url = f"{settings.openai_base_url.rstrip('/')}/chat/completions"
    prompt = _ad_context(payload)
    result = _request_json(
        url,
        headers={"Authorization": f"Bearer {settings.openai_api_key}", "Content-Type": "application/json"},
        payload={
            "model": settings.openai_text_model,
            "temperature": 0.7,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": _system_prompt()},
                {"role": "user", "content": prompt},
            ],
        },
        timeout=settings.request_timeout_seconds,
    )
    content = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
    base = _fallback_copy(payload, provider="openai")
    parsed = _extract_json_block(content)
    if parsed is None and content:
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            parsed = None
    if content:
        base["raw"] = content
    return _merge_structured_response(base, parsed)


def _local_copy(payload: dict) -> dict:
    """로컬 OpenAI 호환 LLM 엔드포인트로 광고 문구를 생성한다."""
    settings = get_settings()
    base_url = settings.local_llm_base_url.rstrip("/")
    if base_url.endswith("/v1"):
        url = f"{base_url}/chat/completions"
    elif "/v1/" in base_url or base_url.endswith("/chat/completions"):
        url = base_url if base_url.endswith("/chat/completions") else f"{base_url}/chat/completions"
    else:
        url = f"{base_url}/v1/chat/completions"

    body = {
        "model": settings.local_llm_model or "local-model",
        "temperature": 0.7,
        "messages": [
            {"role": "system", "content": _system_prompt()},
            {"role": "user", "content": _ad_context(payload)},
        ],
    }
    result = _request_json(url, headers={"Content-Type": "application/json"}, payload=body, timeout=settings.request_timeout_seconds)
    content = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
    base = _fallback_copy(payload, provider="local_llm")
    parsed = _extract_json_block(content)
    if parsed is None and content:
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            parsed = None
    if content:
        base["raw"] = content
    return _merge_structured_response(base, parsed)


def generate_ad_copy(payload: dict) -> dict:
    """설정된 provider 순서에 따라 OpenAI, 로컬 LLM, fallback 중 하나로 광고 문구를 생성한다."""
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
    """포스터 이미지 생성 모델에 전달할 상품/셋업 설명 프롬프트를 만든다."""
    assets = ", ".join(payload.get("assets", [])) or "keyboard, deskmat, monitor"
    style = payload.get("theme", "minimal")
    product = payload.get("product_name", "custom keyboard desk setup")
    monitor_size = payload.get("monitor_size", "27")
    desk_w = payload.get("desk_width", 120)
    desk_d = payload.get("desk_depth", 60)
    case_finish = payload.get("case_finish", "anodized")
    plate = payload.get("plate_material", "aluminum")
    switch = payload.get("switch_stem", "red")
    return (
        f"Korean e-commerce poster image for {product}. "
        f"Desk setup with {assets}, {style} styling, {monitor_size}-inch monitor, {desk_w:.0f}x{desk_d:.0f}cm desk. "
        f"Keyboard with {case_finish} case, {plate} plate, {switch} switches. "
        "Clean three-quarter product composition, realistic PBR materials, soft daylight, no brand logos, no copyrighted imagery. "
        f"Leave negative space for Korean headline: {copy_result.get('headline', '')}"
    )


def _wrap(text: str, width: int, max_lines: int = 3) -> list[str]:
    """SVG 텍스트 배치를 위해 긴 문자열을 지정 폭과 최대 줄 수에 맞춰 나눈다."""
    text = str(text or "")
    if len(text) <= width:
        return [text]
    return textwrap.wrap(text, width=width, break_long_words=False, replace_whitespace=False)[:max_lines]


PALETTES = {
    "minimal": ("#f5f2ea", "#2f3438", "#8aa0a8", "#d8b892"),
    "pastel": ("#f8f0f3", "#334155", "#9bbbd4", "#e8c7b8"),
    "premium": ("#eef0ec", "#15181d", "#b08d57", "#4b5563"),
    "gaming": ("#10131a", "#f8fafc", "#7c3aed", "#0ea5e9"),
}


def _ratio_size(ratio: str) -> tuple[int, int]:
    """포스터 비율 문자열을 실제 SVG 캔버스 크기로 변환한다."""
    return {"1:1": (1080, 1080), "4:5": (1080, 1350), "16:9": (1600, 900)}.get(ratio, (1080, 1080))


def _safe_inline_image(image_b64: str | None) -> str:
    """SVG에 인라인 삽입할 base64 이미지 문자열을 안전하게 정리한다."""
    if not image_b64:
        return ""
    return image_b64.strip()


def _hero_image_svg(payload: dict, image_b64: str | None, x: int, y: int, w: int, h: int, accent: str, ink: str) -> str:
    """생성 이미지가 있으면 SVG image 태그를 만들고, 없으면 기본 데스크 일러스트를 만든다."""
    if image_b64:
        return (
            f'<image href="data:image/png;base64,{html.escape(_safe_inline_image(image_b64))}" '
            f'x="{x}" y="{y}" width="{w}" height="{h}" preserveAspectRatio="xMidYMid slice" />'
        )
    kb_x = x + int(w * 0.16)
    kb_y = y + int(h * 0.62)
    kb_w = int(w * 0.55)
    kb_h = int(h * 0.13)
    mon_x = x + int(w * 0.18)
    mon_y = y + int(h * 0.18)
    mon_w = int(w * 0.6)
    mon_h = int(h * 0.35)
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="32" fill="{accent}" opacity="0.92"/>'
        f'<rect x="{mon_x}" y="{mon_y}" width="{mon_w}" height="{mon_h}" rx="14" fill="{ink}" opacity="0.86"/>'
        f'<rect x="{mon_x + 16}" y="{mon_y + 16}" width="{mon_w - 32}" height="{mon_h - 60}" rx="8" fill="{accent}" opacity="0.55"/>'
        f'<rect x="{mon_x + mon_w // 2 - 30}" y="{mon_y + mon_h - 6}" width="60" height="18" rx="6" fill="{ink}" opacity="0.7"/>'
        f'<rect x="{kb_x}" y="{kb_y}" width="{kb_w}" height="{kb_h}" rx="10" fill="{ink}" opacity="0.85"/>'
    )


def _minimal_card_svg(payload: dict, copy_result: dict, image_b64: str | None) -> str:
    """상품 강조형 minimal card 포스터 SVG를 생성한다."""
    width, height = _ratio_size(payload.get("image_ratio", "1:1"))
    theme = payload.get("theme", "minimal")
    bg, ink, accent, wood = PALETTES.get(theme, PALETTES["minimal"])
    product = html.escape(payload.get("product_name", "DeskAd Setup"))
    price = html.escape(payload.get("price", ""))
    headline = html.escape(copy_result.get("headline") or copy_result.get("copies", [product])[0])
    subcopy = html.escape(copy_result.get("subcopy") or "3D 셋업 미리보기 기반 광고 콘텐츠")
    cta = html.escape(copy_result.get("cta") or "자세히 보기")

    headline_svg = "".join(
        f'<text x="{int(width*0.08)}" y="{int(height*0.13) + i*58}" font-size="48" font-weight="800" fill="{ink}">{line}</text>'
        for i, line in enumerate(_wrap(headline, 18))
    )
    subcopy_svg = "".join(
        f'<text x="{int(width*0.08)}" y="{int(height*0.27) + i*34}" font-size="25" fill="{ink}" opacity="0.78">{line}</text>'
        for i, line in enumerate(_wrap(subcopy, 28))
    )
    hero_svg = _hero_image_svg(payload, image_b64, int(width * 0.13), int(height * 0.40), int(width * 0.74), int(height * 0.36), wood, ink)

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="{width}" height="{height}" fill="{bg}"/>
  {hero_svg}
  {headline_svg}
  {subcopy_svg}
  <text x="{int(width*0.08)}" y="{int(height*0.82)}" font-size="31" font-weight="700" fill="{ink}">{product}</text>
  <text x="{int(width*0.08)}" y="{int(height*0.86)}" font-size="25" fill="{ink}" opacity="0.72">{price}</text>
  <rect x="{int(width*0.08)}" y="{int(height*0.89)}" width="{int(width*0.25)}" height="62" rx="31" fill="{accent}"/>
  <text x="{int(width*0.105)}" y="{int(height*0.89)+40}" font-size="24" font-weight="800" fill="{bg}">{cta}</text>
</svg>'''


def _grid_three_svg(payload: dict, copy_result: dict, image_b64: str | None) -> str:
    """큰 이미지와 작은 패널 두 개로 구성된 grid형 포스터 SVG를 생성한다."""
    width, height = _ratio_size(payload.get("image_ratio", "1:1"))
    theme = payload.get("theme", "minimal")
    bg, ink, accent, wood = PALETTES.get(theme, PALETTES["minimal"])
    product = html.escape(payload.get("product_name", "DeskAd Setup"))
    headline = html.escape(copy_result.get("headline") or product)
    subcopy = html.escape(copy_result.get("subcopy") or "")
    hashtags = " ".join(html.escape(h) for h in (copy_result.get("hashtags") or [])[:4])
    pad = int(width * 0.06)
    big_x, big_y = pad, int(height * 0.18)
    big_w, big_h = int(width * 0.55), int(height * 0.55)
    small_x = big_x + big_w + pad // 2
    small_w = int(width * 0.31)
    small_h = (big_h - pad) // 2
    small_y_bot = big_y + small_h + pad // 2
    small_inner_pad = max(10, int(width * 0.018))
    headline_svg = "".join(
        f'<text x="{pad}" y="{int(height*0.10) + i*40}" font-size="34" font-weight="800" fill="{ink}">{line}</text>'
        for i, line in enumerate(_wrap(headline, 16, 2))
    )
    small_top_visual = _hero_image_svg(
        payload,
        image_b64,
        small_x + small_inner_pad,
        big_y + small_inner_pad,
        small_w - small_inner_pad * 2,
        small_h - small_inner_pad * 3,
        wood,
        ink,
    )
    small_bottom_visual = _hero_image_svg(
        payload,
        image_b64,
        small_x + small_inner_pad,
        small_y_bot + small_inner_pad,
        small_w - small_inner_pad * 2,
        small_h - small_inner_pad * 3,
        accent,
        ink,
    )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="{width}" height="{height}" fill="{bg}"/>
  {headline_svg}
  {_hero_image_svg(payload, image_b64, big_x, big_y, big_w, big_h, wood, ink)}
  <rect x="{small_x}" y="{big_y}" width="{small_w}" height="{small_h}" rx="20" fill="{accent}" opacity="0.85"/>
  {small_top_visual}
  <text x="{small_x + 24}" y="{big_y + small_h - 28}" font-size="20" font-weight="700" fill="{bg}">데스크 셋업 #1</text>
  <rect x="{small_x}" y="{small_y_bot}" width="{small_w}" height="{small_h}" rx="20" fill="{wood}" opacity="0.92"/>
  {small_bottom_visual}
  <text x="{small_x + 24}" y="{small_y_bot + small_h - 28}" font-size="20" font-weight="700" fill="{bg}">3D 미리보기 #2</text>
  <text x="{pad}" y="{int(height*0.84)}" font-size="26" font-weight="700" fill="{ink}">{product}</text>
  <text x="{pad}" y="{int(height*0.88)}" font-size="20" fill="{ink}" opacity="0.78">{subcopy}</text>
  <text x="{pad}" y="{int(height*0.93)}" font-size="18" fill="{accent}">{hashtags}</text>
</svg>'''


def _feature_focus_svg(payload: dict, copy_result: dict, image_b64: str | None) -> str:
    """제품 이미지와 스펙 bullet을 함께 보여주는 feature focus 포스터 SVG를 생성한다."""
    width, height = _ratio_size(payload.get("image_ratio", "1:1"))
    theme = payload.get("theme", "minimal")
    bg, ink, accent, wood = PALETTES.get(theme, PALETTES["minimal"])
    product = html.escape(payload.get("product_name", "DeskAd Setup"))
    headline = html.escape(copy_result.get("headline") or product)
    spec_bullets = copy_result.get("spec_bullets") or [
        payload.get("product_type", "커스텀 키보드"),
        payload.get("selling_point", ""),
        f"가격 {payload.get('price', '')}".strip(),
    ]
    spec_bullets = [html.escape(str(b)) for b in spec_bullets if b][:4]
    pad = int(width * 0.06)
    hero_x, hero_y = pad, int(height * 0.20)
    hero_w, hero_h = int(width * 0.55), int(height * 0.62)
    spec_x = hero_x + hero_w + pad
    headline_svg = "".join(
        f'<text x="{pad}" y="{int(height*0.13) + i*42}" font-size="36" font-weight="800" fill="{ink}">{line}</text>'
        for i, line in enumerate(_wrap(headline, 14, 2))
    )
    bullets_svg = "".join(
        f'<circle cx="{spec_x + 10}" cy="{hero_y + 40 + i*60 - 8}" r="6" fill="{accent}"/>'
        f'<text x="{spec_x + 28}" y="{hero_y + 40 + i*60}" font-size="22" fill="{ink}">{bullet}</text>'
        for i, bullet in enumerate(spec_bullets)
    )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="{width}" height="{height}" fill="{bg}"/>
  {headline_svg}
  {_hero_image_svg(payload, image_b64, hero_x, hero_y, hero_w, hero_h, wood, ink)}
  <text x="{spec_x}" y="{hero_y + 4}" font-size="20" font-weight="700" fill="{accent}">SPECS</text>
  {bullets_svg}
  <text x="{pad}" y="{int(height*0.92)}" font-size="26" font-weight="700" fill="{ink}">{product}</text>
</svg>'''


def _promo_banner_svg(payload: dict, copy_result: dict, image_b64: str | None) -> str:
    """가로 배너 광고에 맞춘 promo banner 포스터 SVG를 생성한다."""
    width, height = _ratio_size(payload.get("image_ratio", "16:9"))
    theme = payload.get("theme", "minimal")
    bg, ink, accent, wood = PALETTES.get(theme, PALETTES["minimal"])
    product = html.escape(payload.get("product_name", "DeskAd Setup"))
    price = html.escape(payload.get("price", ""))
    headline = html.escape(copy_result.get("headline") or product)
    cta = html.escape(copy_result.get("cta") or "자세히 보기")
    subcopy = html.escape(copy_result.get("subcopy") or "")
    pad = int(width * 0.05)
    headline_svg = "".join(
        f'<text x="{pad}" y="{int(height*0.30) + i*60}" font-size="58" font-weight="900" fill="{ink}">{line}</text>'
        for i, line in enumerate(_wrap(headline, 14, 2))
    )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="{width}" height="{height}" fill="{bg}"/>
  <rect x="0" y="0" width="{int(width*0.5)}" height="{height}" fill="{accent}" opacity="0.10"/>
  <text x="{pad}" y="{int(height*0.18)}" font-size="22" fill="{accent}" font-weight="700">PROMO · 광고 배너</text>
  {headline_svg}
  <text x="{pad}" y="{int(height*0.58)}" font-size="22" fill="{ink}" opacity="0.78">{subcopy}</text>
  <text x="{pad}" y="{int(height*0.66)}" font-size="28" font-weight="700" fill="{ink}">{product}</text>
  <text x="{pad}" y="{int(height*0.72)}" font-size="24" fill="{ink}" opacity="0.78">{price}</text>
  <rect x="{pad}" y="{int(height*0.78)}" width="220" height="60" rx="30" fill="{accent}"/>
  <text x="{pad + 32}" y="{int(height*0.78) + 38}" font-size="22" font-weight="800" fill="{bg}">{cta}</text>
  {_hero_image_svg(payload, image_b64, int(width*0.50), pad, width - int(width*0.50) - pad, height - pad*2, wood, ink)}
</svg>'''


TEMPLATE_BUILDERS = {
    "minimal_card": _minimal_card_svg,
    "grid_three": _grid_three_svg,
    "feature_focus": _feature_focus_svg,
    "promo_banner": _promo_banner_svg,
}


def create_svg_poster(payload: dict, copy_result: dict, *, image_b64: str | None = None) -> str:
    """선택한 포스터 템플릿에 맞는 SVG 문자열을 생성한다."""
    template = payload.get("poster_template", "minimal_card")
    builder = TEMPLATE_BUILDERS.get(template, _minimal_card_svg)
    return builder(payload, copy_result, image_b64)


def save_poster_svg(*, payload: dict, copy_result: dict, poster_dir: Path, image_b64: str | None = None) -> dict:
    """생성된 SVG 포스터를 static/posters 폴더에 저장하고 파일 정보를 반환한다."""
    poster_dir.mkdir(parents=True, exist_ok=True)
    poster_name = f"poster_{uuid4().hex[:10]}.svg"
    poster_path = poster_dir / poster_name
    poster_path.write_text(create_svg_poster(payload, copy_result, image_b64=image_b64), encoding="utf-8")
    return {"poster_file": poster_name, "poster_path": poster_path}


def _decode_image_to_b64(result: dict) -> str | None:
    """OpenAI 또는 로컬 이미지 응답에서 base64 이미지 데이터를 표준 형태로 추출한다."""
    if not isinstance(result, dict):
        return None
    for key in ("image_base64", "image_b64", "image"):
        value = result.get(key)
        if isinstance(value, str) and value:
            return value.split(",", 1)[-1] if value.startswith("data:") else value
    data = result.get("data")
    if isinstance(data, list) and data:
        first = data[0]
        if isinstance(first, dict):
            for key in ("b64_json", "image_base64", "image"):
                value = first.get(key)
                if isinstance(value, str) and value:
                    return value
            url = first.get("url")
            if isinstance(url, str) and url:
                try:
                    response = requests.get(url, timeout=20)
                    response.raise_for_status()
                    return base64.b64encode(response.content).decode("ascii")
                except Exception:
                    return None
    url = result.get("url")
    if isinstance(url, str) and url:
        try:
            response = requests.get(url, timeout=20)
            response.raise_for_status()
            return base64.b64encode(response.content).decode("ascii")
        except Exception:
            return None
    return None


def _openai_image_reference(payload: dict, image_prompt: str) -> dict | None:
    """OpenAI 이미지 생성 API를 호출하고 포스터 합성용 base64 이미지를 정규화한다."""
    settings = get_settings()
    if not settings.has_openai_image:
        return None
    try:
        result = _request_json(
            f"{settings.openai_base_url.rstrip('/')}/images/generations",
            headers={"Authorization": f"Bearer {settings.openai_api_key}", "Content-Type": "application/json"},
            payload={"model": settings.openai_image_model, "prompt": image_prompt, "size": "1024x1024", "n": 1},
            timeout=max(settings.request_timeout_seconds, 120),
        )
    except Exception as exc:
        return {"provider": "openai_image", "model": settings.openai_image_model, "error": str(exc), "has_image": False}

    image_b64 = _decode_image_to_b64(result)
    summary: dict = {"provider": "openai_image", "model": settings.openai_image_model, "has_image": bool(image_b64)}
    if image_b64:
        summary["image_b64"] = image_b64
    else:
        summary["raw_keys"] = list(result.keys()) if isinstance(result, dict) else []
    return summary


def _local_image_reference(payload: dict, image_prompt: str) -> dict | None:
    """로컬 이미지 생성 엔드포인트를 호출하고 포스터 합성용 base64 이미지를 정규화한다."""
    settings = get_settings()
    if not settings.has_local_image:
        return None
    try:
        result = _request_json(
            settings.local_image_endpoint,
            headers={"Content-Type": "application/json"},
            payload={"prompt": image_prompt, "metadata": payload, "width": 1024, "height": 1024},
            timeout=max(settings.request_timeout_seconds, 90),
        )
    except Exception as exc:
        return {"provider": "local_image", "error": str(exc), "has_image": False}

    image_b64 = _decode_image_to_b64(result)
    summary: dict = {"provider": "local_image", "has_image": bool(image_b64)}
    if image_b64:
        summary["image_b64"] = image_b64
    else:
        summary["raw_keys"] = list(result.keys()) if isinstance(result, dict) else []
    return summary


def generate_image_reference(payload: dict, image_prompt: str) -> dict | None:
    """설정에 따라 OpenAI 이미지 모델, 로컬 이미지 모델, fallback 순서로 이미지 참조를 생성한다."""
    settings = get_settings()
    provider = settings.ai_provider.lower()
    errors: list[str] = []

    if provider in {"auto", "openai"} and settings.has_openai_image:
        result = _openai_image_reference(payload, image_prompt)
        if isinstance(result, dict) and result.get("has_image"):
            return result
        if isinstance(result, dict) and result.get("error"):
            errors.append(f"openai_image: {result['error']}")
            if provider == "openai":
                return {**result, "error": "; ".join(errors)}

    if provider in {"auto", "local"} and settings.has_local_image:
        result = _local_image_reference(payload, image_prompt)
        if isinstance(result, dict) and result.get("has_image"):
            return result
        if isinstance(result, dict) and result.get("error"):
            errors.append(f"local_image: {result['error']}")
            return {**result, "error": "; ".join(errors)}
        if result is not None:
            return result

    if errors:
        return {"provider": "image_fallback", "has_image": False, "error": "; ".join(errors)}
    return None


def generate_local_image_reference(payload: dict, image_prompt: str) -> dict | None:
    """기존 호출부 호환을 위해 로컬 이미지 참조 생성 함수를 감싼다."""
    return _local_image_reference(payload, image_prompt)
