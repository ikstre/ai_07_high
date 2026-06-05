"""키보드 측면 실루엣 회귀 가드.

회귀 맥락(docs/project_handoff_2026-05-29 §7-3, ui_redesign_2026-06-04 §2-3):
- 측면에서 case/plate/switch/keycap 이 '층층이 분리'되어 보이던 회귀.
- clean 뷰(show_internals=False, 셋업 기본값)에서 스위치가 통째로 빠져 keycap 이
  case 위로 떠 보이던 분리.

여기서는 빌더를 계측해 부품별 Y범위로 다음을 잠근다:
  1. clean 뷰에서도 switch housing 이 그려져 keycap 이 case 에 연결된다.
  2. internals 뷰에서 plate/pcb 는 case 상단 아래(=solid case 안)에 묻혀 측면 분리가 없다.
  3. 어떤 switch_family 든 housing 이 case 위로 돌출해 keycap 바닥과 맞닿는다.
추가로 실제 build_desk_setup_scene_glb(기본 show_internals=False) 노드명도 검증한다.
"""
import json
import struct
from pathlib import Path

from backend import renderer as R
from backend.renderer import build_desk_setup_scene_glb

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LAYOUT_65 = PROJECT_ROOT / "data" / "layouts" / "layout_65.json"
GLB_JSON_CHUNK = 0x4E4F534A


def _capture_keyboard(show_internals: bool, switch_family: str = "mx") -> dict[str, tuple[float, float]]:
    """_add_keyboard_detailed 호출을 계측해 {node_name: (ymin, ymax)} 반환."""
    layout = json.loads(LAYOUT_65.read_text(encoding="utf-8"))
    records: dict[str, tuple[float, float]] = {}
    builder = R.GlbBuilder()
    orig_box, orig_cyl = builder.add_box, builder.add_cylinder_y

    def box(name, center, size, material, taper=0.0, rotation_x=0.0):
        records[name] = (center[1] - size[1] / 2, center[1] + size[1] / 2)
        return orig_box(name, center, size, material, taper=taper, rotation_x=rotation_x)

    def cyl(name, center, rx, h, material, **kw):
        records[name] = (center[1] - h / 2, center[1] + h / 2)
        return orig_cyl(name, center, rx, h, material, **kw)

    builder.add_box = box  # type: ignore[method-assign]
    builder.add_cylinder_y = cyl  # type: ignore[method-assign]
    R._add_keyboard_detailed(
        builder, layout_data=layout, center=(0, 0),
        case_color="#c8c1b2", keycap_color="#f4ead7", accent_color="#6f8faf",
        switch_family=switch_family, show_internals=show_internals,
    )
    return records


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


def test_clean_view_draws_switch_housing_so_keycaps_do_not_float():
    rec = _capture_keyboard(show_internals=False)

    assert "switch housing 1" in rec, "clean 뷰에 스위치 하우징이 빠지면 keycap 이 떠 보인다"
    case_top = rec["case top frame"][1]
    housing_top = rec["switch housing 1"][1]
    keycap_bottom = rec["keycap skirt 1"][0]

    # 하우징이 case 위로 돌출해 keycap 바닥과 맞닿아야 분리(공기층)가 없다
    assert housing_top > case_top
    assert keycap_bottom - housing_top <= 0.10

    # clean 뷰는 내부 디테일(스위치 top/stem, pcb, 내부 plate)을 숨긴다
    assert "switch top 1" not in rec
    assert "switch stem 1" not in rec
    assert "pcb board" not in rec
    assert "plate" not in rec


def test_internals_view_keeps_plate_and_pcb_inside_case():
    rec = _capture_keyboard(show_internals=True)
    case_top = rec["case top frame"][1]

    # 내부 부품은 case 상단보다 아래 = solid case 안에 묻혀 측면에서 층 분리가 안 보인다
    assert rec["plate"][1] <= case_top + 1e-6
    assert rec["pcb board"][1] <= case_top + 1e-6

    # 스위치는 case 위로 돌출하고 디테일이 함께 그려진다
    assert rec["switch housing 1"][1] > case_top
    assert "switch stem 1" in rec
    assert "switch top 1" in rec


def test_switch_housing_bridges_case_to_keycap_for_all_families():
    for family in ("mx", "box", "holy_panda", "topre"):
        rec = _capture_keyboard(show_internals=False, switch_family=family)
        assert "switch housing 1" in rec, family
        case_top = rec["case top frame"][1]
        housing_top = rec["switch housing 1"][1]
        keycap_bottom = rec["keycap skirt 1"][0]
        assert housing_top > case_top, family
        assert keycap_bottom - housing_top <= 0.12, family


def test_desk_setup_default_glb_includes_switch_housing_without_internals(tmp_path):
    output_path = tmp_path / "desk_clean.glb"
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
        assets=["monitor"],
        # show_internals 는 desk-setup 기본값(False)을 그대로 사용
    )
    names = _read_glb_node_names(output_path)

    assert "switch housing 1" in names  # clean 뷰에도 하우징이 있어 분리가 없다
    assert "pcb board" not in names     # 내부 디테일은 숨김
    assert "switch stem 1" not in names
