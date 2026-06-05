import json
import struct
from pathlib import Path

from backend.renderer import build_desk_setup_scene_glb


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LAYOUT_65 = PROJECT_ROOT / "data" / "layouts" / "layout_65.json"
GLB_JSON_CHUNK = 0x4E4F534A


def _read_glb_node_names(path: Path) -> set[str]:
    data = path.read_bytes()
    assert data[:4] == b"glTF"
    total = struct.unpack_from("<I", data, 8)[0]
    offset = 12
    while offset + 8 <= min(total, len(data)):
        chunk_len, chunk_type = struct.unpack_from("<II", data, offset)
        offset += 8
        chunk = data[offset:offset + chunk_len]
        if chunk_type == GLB_JSON_CHUNK:
            gltf = json.loads(chunk.decode("utf-8"))
            return {node.get("name", "") for node in gltf.get("nodes", [])}
        offset += chunk_len
    raise AssertionError("GLB JSON chunk not found")


def _build_monitor_arm_scene(tmp_path: Path, style: str) -> set[str]:
    output_path = tmp_path / f"{style}.glb"
    build_desk_setup_scene_glb(
        layout_path=LAYOUT_65,
        output_path=output_path,
        case_color="#c8c1b2",
        keycap_color="#f4ead7",
        accent_keycap_color="#6f8faf",
        deskmat_color="#1f2937",
        desk_color="#d8b892",
        mouse_color="#f7f7f2",
        theme="minimal",
        assets=["monitor", "monitor_arm"],
        monitor_arm_style=style,
    )
    return _read_glb_node_names(output_path)


def test_double_joint_monitor_arm_exports_visible_elbow_nodes(tmp_path):
    names = _build_monitor_arm_scene(tmp_path, "double_joint")

    assert "arm upper boom" in names
    assert "arm elbow upper joint" in names
    assert "arm elbow drop" in names
    assert "arm elbow lower joint" in names
    assert "arm lower boom" in names
    assert "monitor arm boom" not in names


def test_single_monitor_arm_keeps_simple_boom_without_elbow_nodes(tmp_path):
    names = _build_monitor_arm_scene(tmp_path, "single")

    assert "monitor arm boom" in names
    assert "arm elbow upper joint" not in names
    assert "arm elbow lower joint" not in names


def test_desk_setup_uses_only_selected_optional_assets(tmp_path):
    output_path = tmp_path / "selected_assets.glb"
    build_desk_setup_scene_glb(
        layout_path=LAYOUT_65,
        output_path=output_path,
        case_color="#c8c1b2",
        keycap_color="#f4ead7",
        accent_keycap_color="#6f8faf",
        deskmat_color="#1f2937",
        desk_color="#d8b892",
        mouse_color="#f7f7f2",
        theme="minimal",
        assets=["monitor", "mouse"],
    )

    names = _read_glb_node_names(output_path)

    assert "monitor display" in names
    assert "mouse body" in names
    assert "lamp round base" not in names
    assert "plant ceramic pot" not in names
    assert "monitor arm boom" not in names
