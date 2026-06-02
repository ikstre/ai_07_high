import json
import struct

from backend.cad import glb_unit_check


def _json_glb(
    min_xyz=(0.0, 0.0, 0.0),
    max_xyz=(20.0, 5.0, 10.0),
    *,
    root_scale=None,
) -> bytes:
    node = {"mesh": 0}
    if root_scale is not None:
        node["scale"] = list(root_scale)
    gltf = {
        "asset": {"version": "2.0"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [node],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0}}]}],
        "accessors": [{"min": list(min_xyz), "max": list(max_xyz)}],
    }
    payload = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    payload += b" " * ((4 - len(payload) % 4) % 4)
    total_len = 12 + 8 + len(payload)
    return (
        b"glTF"
        + struct.pack("<II", 2, total_len)
        + struct.pack("<II", len(payload), 0x4E4F534A)
        + payload
    )


def test_glb_unit_check_accepts_centimeter_sized_model():
    result = glb_unit_check(_json_glb(max_xyz=(20, 4, 8)))

    assert result["scale_ok"] is True
    assert result["suggested_scale"] is None
    assert result["dimensions_units"]["max_extent"] == 20


def test_glb_unit_check_flags_millimeter_sized_model():
    result = glb_unit_check(_json_glb(max_xyz=(1000, 200, 400)))

    assert result["scale_ok"] is False
    assert result["suggested_scale"] == 0.1


def test_glb_unit_check_flags_meter_sized_model():
    result = glb_unit_check(_json_glb(max_xyz=(0.5, 0.1, 0.2)))

    assert result["scale_ok"] is False
    assert result["suggested_scale"] == 100.0


def test_glb_unit_check_applies_root_scale_before_flagging():
    result = glb_unit_check(_json_glb(max_xyz=(0.8, 0.2, 0.4), root_scale=(100, 100, 100)))

    assert result["scale_ok"] is True
    assert result["suggested_scale"] is None
    assert result["dimensions_units"]["max_extent"] == 80
