"""OpenAI식 text+image 동시 입력(멀티모달) 배관 회귀 테스트.

비전 모델 기동 없이도 메시지 형태/강등 동작을 고정한다.
"""
import base64

import backend.ai as ai
from backend.ai import _copy_messages, _image_data_url, _reference_image_b64
from backend.library import reference_asset_label
from backend.llm_adapters import _message_text


def _payload(**extra):
    base = {
        "product_name": "테스트 65% 커스텀 키보드",
        "product_type": "커스텀 키보드",
        "target_channel": "인스타그램",
        "target_customer": "직장인",
        "selling_point": "알루미늄 하우징, PBT 키캡",
        "ad_tone": "감성형",
    }
    base.update(extra)
    return base


def test_copy_messages_attaches_image_as_openai_multimodal_content():
    payload = _payload(reference_image_b64="QUJD")  # raw base64
    messages = _copy_messages(payload, attach_image=True)
    user = messages[-1]
    assert isinstance(user["content"], list)
    types = [part["type"] for part in user["content"]]
    assert types == ["text", "image_url"]
    assert user["content"][1]["image_url"]["url"] == "data:image/png;base64,QUJD"
    assert user["content"][0]["text"]  # 광고 컨텍스트 텍스트 유지


def test_copy_messages_text_only_when_no_image():
    messages = _copy_messages(_payload(), attach_image=True)
    assert isinstance(messages[-1]["content"], str)


def test_copy_messages_degrades_to_text_when_attach_disabled():
    # 비전 미지원 provider는 attach_image=False로 호출돼 이미지가 있어도 텍스트만 보낸다.
    payload = _payload(reference_image_b64="QUJD")
    messages = _copy_messages(payload, attach_image=False)
    assert isinstance(messages[-1]["content"], str)


def test_image_data_url_wraps_raw_base64_but_keeps_data_url():
    assert _image_data_url("QUJD") == "data:image/png;base64,QUJD"
    assert _image_data_url("data:image/jpeg;base64,XYZ") == "data:image/jpeg;base64,XYZ"


def test_reference_image_b64_ignores_blank():
    assert _reference_image_b64({"reference_image_b64": "  "}) is None
    assert _reference_image_b64({}) is None
    assert _reference_image_b64({"reference_image_b64": "QUJD"}) == "QUJD"


def test_reference_asset_label_humanizes_filename():
    assert reference_asset_label("shared/data/reference_drawings/tsuki_kle_layout.png") == "tsuki kle layout"
    assert reference_asset_label(None) == ""


def test_reference_image_b64_loads_selected_library_drawing(tmp_path, monkeypatch):
    # 직접 b64가 없으면 선택한 공용 도면(래스터)을 읽어 자동 투입한다.
    drawing = tmp_path / "austin_kle_layout.png"
    drawing.write_bytes(b"\x89PNGfake-bytes")
    monkeypatch.setattr(
        ai,
        "reference_asset_descriptor",
        lambda path: {"path": drawing, "label": "austin kle layout", "kind": "reference",
                      "extension": ".png", "is_raster": True},
    )
    result = _reference_image_b64({"reference_asset_path": "shared/data/reference_drawings/austin_kle_layout.png"})
    assert result == base64.b64encode(b"\x89PNGfake-bytes").decode("ascii")


def test_reference_image_b64_skips_non_raster_drawing(monkeypatch):
    # SVG 등 벡터 도면은 vision 경로로 못 보내므로 b64로 자동 투입하지 않는다.
    monkeypatch.setattr(
        ai,
        "reference_asset_descriptor",
        lambda path: {"path": None, "label": "vesa mount adapter", "kind": "reference",
                      "extension": ".svg", "is_raster": False},
    )
    assert _reference_image_b64({"reference_asset_path": "shared/data/reference_drawings/vesa_mount_adapter.svg"}) is None


def test_message_text_extracts_text_and_drops_image_part():
    content = [
        {"type": "text", "text": "광고 컨텍스트"},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,QUJD"}},
    ]
    assert _message_text(content) == "광고 컨텍스트"
    assert _message_text("plain") == "plain"
    assert _message_text(None) == ""
