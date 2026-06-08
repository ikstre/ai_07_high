import re

from backend.ai import _wrap, create_svg_poster, safe_image_reference


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


def test_grid_three_single_image_uses_distinct_detail_crops():
    svg = create_svg_poster(_payload("grid_three"), _copy(), image_b64="AAAA")

    assert svg.count("data:image/png;base64,AAAA") == 3
    assert 'preserveAspectRatio="xMidYMid meet"' in svg
    assert 'preserveAspectRatio="xMidYMid slice"' in svg
    assert 'preserveAspectRatio="xMaxYMid slice"' in svg
    assert "제품 메인 컷" in svg
    assert "키캡·스위치 디테일" in svg
    assert "데스크 무드 컷" in svg


def test_grid_three_accepts_three_generated_images():
    svg = create_svg_poster(_payload("grid_three"), _copy(), image_b64s=["AAAA", "BBBB", "CCCC"])

    assert svg.count("data:image/png;base64,AAAA") == 1
    assert svg.count("data:image/png;base64,BBBB") == 1
    assert svg.count("data:image/png;base64,CCCC") == 1
    assert 'preserveAspectRatio="xMaxYMid slice"' not in svg


def test_wrap_force_breaks_spaceless_long_headline_within_width():
    # 공백 없는 긴 한글 headline(A5): break_long_words=False만으론 한 줄로 남아 캔버스
    # 밖으로 넘쳤다. 폭 가드가 글자수 기준으로 강제 분할해 모든 줄이 width 이하여야 한다.
    headline = "책상위에놓는순간모든것이달라지는프리미엄커스텀키보드의완성도높은타건감"
    lines = _wrap(headline, 18)

    assert len(lines) >= 2
    assert all(len(line) <= 18 for line in lines)


def test_wrap_keeps_short_and_word_wraps_spaced_text():
    assert _wrap("짧은 헤드라인", 18) == ["짧은 헤드라인"]
    spaced = _wrap("조용한 타건감과 정돈된 무드 그리고 크림 톤 키캡의 조화", 12)
    assert all(len(line) <= 12 for line in spaced)
    # 공백 있는 텍스트는 단어 중간을 쪼개지 않는다(어절 보존).
    assert all(" " in line or len(line) <= 12 for line in spaced)
    assert "".join(spaced).replace(" ", "") == "조용한타건감과정돈된무드그리고크림톤키캡의조화"


def test_minimal_card_long_spaceless_headline_renders_multiple_lines():
    copy = _copy()
    copy["headline"] = "책상위에놓는순간분위기가완전히달라지는프리미엄커스텀키보드"
    svg = create_svg_poster(_payload("minimal_card"), copy)
    # 강제 줄바꿈으로 headline이 2줄 이상 → 한 줄 오버플로 회귀 방지.
    headline_chunks = [seg for seg in re.findall(r">([^<>]+)<", svg) if "책상위에놓는순간" in seg or "프리미엄커스텀키보드" in seg]
    assert any("책상위에놓는순간" in seg and "프리미엄커스텀키보드" not in seg for seg in headline_chunks)


def test_safe_image_reference_redacts_multiple_images_and_reports_count():
    public = safe_image_reference(
        {
            "provider": "local_image",
            "has_image": True,
            "image_b64": "AAAA",
            "image_b64s": ["AAAA", "BBBB", "CCCC"],
        }
    )

    assert public["image_count"] == 3
    assert "image_b64" not in public
    assert "image_b64s" not in public
