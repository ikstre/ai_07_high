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


def _hero_box(svg: str) -> tuple[int, int]:
    """meet로 배치된 히어로 <image>의 (width, height)를 반환."""
    m = re.search(
        r'<image href="data:image/png[^"]*" x="\d+" y="\d+" width="(\d+)" height="(\d+)" '
        r'preserveAspectRatio="xMidYMid meet"',
        svg,
    )
    assert m, "히어로 image 태그를 찾지 못함"
    return int(m.group(1)), int(m.group(2))


def test_minimal_card_hero_frame_matches_square_image_no_band():
    # 1:1 이미지는 정사각 프레임(width==height) → meet 레터박스(좌우 베이지 띠) 없음.
    svg = create_svg_poster(_payload("minimal_card", "1:1"), _copy(), image_b64="AAAA")
    w, h = _hero_box(svg)
    assert w == h, f"정사각이어야 하는데 {w}x{h} (좌우 여백 띠 발생)"


def test_minimal_card_hero_frame_matches_wide_ratio():
    # 16:9 이미지는 프레임도 16:9(가로>세로) → 비율 불일치로 인한 띠 없음.
    svg = create_svg_poster(_payload("minimal_card", "16:9"), _copy(), image_b64="AAAA")
    w, h = _hero_box(svg)
    assert abs(w / h - 16 / 9) < 0.02, f"16:9 프레임이어야 하는데 {w}x{h}"


def test_promo_banner_hero_frame_matches_wide_ratio_no_band():
    svg = create_svg_poster(_payload("promo_banner", "16:9"), _copy(), image_b64="AAAA")
    w, h = _hero_box(svg)
    assert abs(w / h - 16 / 9) < 0.02, f"16:9 프레임이어야 하는데 {w}x{h}"


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


# ── 2026-06-11 이미지 QA(1.md): SPEC 카드 줄바꿈/폰트 축소 ─────────────────────
def _spec_card_lines(svg: str) -> list[tuple[int, int, str]]:
    """(x, font_size, text)를 SPEC 카드 영역 bullet 라인만 추려 반환."""
    from backend.ai import _ratio_size

    lines = []
    for m in re.finditer(r'<text x="(\d+)" y="\d+" font-size="(\d+)" fill="[^"]+">([^<]*)</text>', svg):
        lines.append((int(m.group(1)), int(m.group(2)), m.group(3)))
    # spec 텍스트 x는 카드 내부(이미지 우측)에 있음 — 가장 큰 x 그룹이 카드
    if not lines:
        return []
    spec_x = max(x for x, _, _ in lines)
    return [item for item in lines if item[0] == spec_x]


def test_feature_focus_long_spec_bullet_wraps_within_card():
    from backend.ai import _estimate_svg_text_width

    copy_result = _copy()
    copy_result["spec_bullets"] = ["저소음 리니어 스위치와 흡음 폼 구성으로 사무실에서도 조용한 타건감"]
    svg = create_svg_poster(_payload("feature_focus"), copy_result)

    spec_lines = _spec_card_lines(svg)
    assert len(spec_lines) >= 2, "긴 bullet은 여러 줄로 wrap되어야 한다"
    # 1:1 기준 카드 텍스트 폭 = spec_w - 44
    width = 1080
    pad = int(width * 0.06)
    spec_w = width - (pad + int(width * 0.55) + pad) - pad
    for _, font, text in spec_lines:
        assert _estimate_svg_text_width(text, font) <= spec_w - 44


def test_feature_focus_many_long_bullets_shrink_font_not_overflow():
    copy_result = _copy()
    copy_result["spec_bullets"] = [
        "저소음 리니어 스위치와 흡음 폼 구성으로 조용한 타건감 제공",
        "알루미늄 CNC 가공 케이스와 가스켓 마운트 구조 적용",
        "PBT 이중사출 키캡과 체리 프로파일 구성으로 내구성 확보",
        "남거리 무선 연결과 유선 연결을 모두 지원하는 멀티 페어링",
    ]
    svg = create_svg_poster(_payload("feature_focus"), copy_result)
    spec_lines = _spec_card_lines(svg)
    fonts = {font for _, font, _ in spec_lines}
    assert fonts and max(fonts) <= 22
    # 모든 라인의 y가 카드 안(hero_y ~ hero_y+hero_h)에 있어야 한다
    height = 1080
    hero_y, hero_h = int(height * 0.20), int(height * 0.62)
    ys = [int(m.group(1)) for m in re.finditer(r'<text x="\d+" y="(\d+)" font-size="(?:1[0-9]|2[0-2])" fill', svg)]
    spec_ys = [y for y in ys if y >= hero_y]
    assert spec_ys and max(spec_ys) <= hero_y + hero_h + 16


def test_wrap_px_splits_spaceless_korean_token():
    from backend.ai import _wrap_px

    lines = _wrap_px("띄어쓰기없이아주길게이어지는한글스펙문구입니다", font_size=22, max_px=200, max_lines=3)
    assert len(lines) >= 2
    assert all(lines)
