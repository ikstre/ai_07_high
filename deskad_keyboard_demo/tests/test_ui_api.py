from ui.api_client import poster_preview_height, responsive_svg_document, svg_aspect_ratio


def test_svg_aspect_ratio_uses_viewbox_dimensions():
    svg = '<svg viewBox="0 0 1080 1350" xmlns="http://www.w3.org/2000/svg"></svg>'

    assert svg_aspect_ratio(svg) == 1.25
    assert poster_preview_height(svg, max_width=400) == 516


def test_svg_aspect_ratio_accepts_negative_and_comma_viewbox():
    svg = '<svg viewBox="-12,-8,1080,1350" xmlns="http://www.w3.org/2000/svg"></svg>'

    assert svg_aspect_ratio(svg) == 1.25


def test_poster_document_keeps_svg_responsive_without_cutting():
    svg = '<svg viewBox="0 0 820 820"><rect width="820" height="820"/></svg>'
    document = responsive_svg_document(svg, max_width=640)

    assert "max-width: 640px" in document
    assert "height: auto" in document
    assert svg in document
    assert poster_preview_height(svg, max_width=640) == 656
