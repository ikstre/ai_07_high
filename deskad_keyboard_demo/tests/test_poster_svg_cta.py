import re

from backend.ai import create_svg_poster


def _payload(template: str, ratio: str = "1:1") -> dict:
    return {
        "poster_template": template,
        "image_ratio": ratio,
        "theme": "minimal",
        "product_name": "Neo65 커스텀 키보드",
        "price": "189,000원",
        "product_type": "커스텀 키보드",
        "selling_point": "조용한 타건감",
    }


def _copy() -> dict:
    return {
        "headline": "책상이 좋아지는 시간",
        "subcopy": "조용한 타건감과 정돈된 무드",
        "cta": "아주 긴 CTA 버튼 문구 테스트",
        "spec_bullets": ["65% 배열", "조용한 타건", "크림 톤 키캡"],
    }


def test_minimal_card_cta_pill_uses_dynamic_width_and_centered_text():
    svg = create_svg_poster(_payload("minimal_card"), _copy())
    widths = [int(value) for value in re.findall(r'<rect x="86" y="961" width="(\d+)" height="62"', svg)]

    assert widths
    assert max(widths) <= int(1080 * 0.44)
    assert 'text-anchor="middle"' in svg


def test_feature_focus_includes_right_aligned_cta_pill():
    svg = create_svg_poster(_payload("feature_focus", "16:9"), _copy())
    widths = [int(value) for value in re.findall(r'<rect x="\d+" y="\d+" width="(\d+)" height="58" rx="29" fill="#8aa0a8"', svg)]

    assert widths
    assert max(widths) <= int(1600 * 0.34)
    assert "자세히 보기" not in svg
