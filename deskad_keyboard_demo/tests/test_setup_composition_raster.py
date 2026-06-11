"""셋업 구도 맵(composition raster) 회귀 가드.

생성한 데스크 셋업의 실제 배치 좌표만으로 의사 원근 2D 래스터를 그려 img2img
reference로 넣는 경로(handoff 그룹 1-1). 헤드리스 GL 없이 순수 PIL이어야 한다.
"""
import base64
import io
from pathlib import Path

from PIL import Image

from backend import ai
from backend.config import get_settings
from backend.renderer import (
    _comp_canon,
    build_desk_setup_scene_glb,
    build_setup_composition_raster,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LAYOUT_65 = PROJECT_ROOT / "data" / "layouts" / "layout_65.json"


def _build(tmp_path: Path, assets: list[str]) -> dict:
    return build_desk_setup_scene_glb(
        layout_path=LAYOUT_65,
        output_path=tmp_path / "setup.glb",
        case_color="#2b2f36",
        keycap_color="#e8e6e1",
        accent_keycap_color="#d2a24c",
        deskmat_color="#23262b",
        desk_color="#6b4f34",
        mouse_color="#b23b3b",
        theme="minimal",
        assets=assets,
        desk_width=140.0,
        desk_depth=64.0,
        monitor_size="27",
    )


# ── 라벨 정규화 ────────────────────────────────────────────────────────────
def test_comp_canon_normalizes_placer_labels():
    assert _comp_canon("monitor base") == "monitor"
    assert _comp_canon("monitor arm clamp") == "monitor"
    assert _comp_canon("speaker left") == "speaker"
    assert _comp_canon("speaker right") == "speaker"
    assert _comp_canon("mouse_pad_round") == "mouse_pad"
    assert _comp_canon("keyboard") == "keyboard"
    assert _comp_canon("desk_lamp") == "desk_lamp"


# ── build_desk_setup_scene_glb가 구도 맵을 동봉 ────────────────────────────
def test_scene_returns_decodable_composition_png(tmp_path):
    meta = _build(tmp_path, ["monitor", "mouse", "plant"])
    b64 = meta["composition_b64"]
    assert isinstance(b64, str) and b64
    with Image.open(io.BytesIO(base64.b64decode(b64))) as img:
        assert img.format == "PNG"
        assert img.size[0] > 0 and img.size[1] > 0


def test_composition_present_even_without_optional_assets(tmp_path):
    # 키보드만 있어도(부가 에셋 0) 구도 맵은 생성돼야 한다.
    meta = _build(tmp_path, [])
    assert meta["composition_b64"]


def test_scene_returns_both_projections(tmp_path):
    meta = _build(tmp_path, ["monitor", "mouse", "plant"])
    for key in ("composition_b64", "composition_topdown_b64"):
        with Image.open(io.BytesIO(base64.b64decode(meta[key]))) as img:
            assert img.format == "PNG" and img.size[0] > 0


def test_top_down_projection_renders_png():
    raster = build_setup_composition_raster(
        boxes=[(-10.0, 0.0, 10.0, 12.0, "keyboard"), (14.0, 1.0, 20.0, 11.0, "mouse")],
        desk_width=140.0,
        desk_depth=64.0,
        colors={"desk": "#6b4f34", "mouse": "#b23b3b"},
        monitor={"center_x": 0.0, "center_z": -22.0, "panel_w": 60.0, "panel_h": 36.0},
        projection="top_down",
        size=512,
    )
    assert isinstance(raster, bytes) and raster
    with Image.open(io.BytesIO(raster)) as img:
        assert img.size == (512, 512)


def test_top_down_mouse_marker_is_rounded_and_detailed():
    raster = build_setup_composition_raster(
        boxes=[(14.0, 1.0, 20.0, 11.0, "mouse")],
        desk_width=140.0,
        desk_depth=64.0,
        colors={"desk": "#6b4f34", "mouse": "#b23b3b"},
        projection="top_down",
        size=512,
    )
    with Image.open(io.BytesIO(raster)).convert("RGB") as img:
        S = 512
        margin = 0.05 * S
        desk_w_px = S - 2 * margin
        desk_h_px = desk_w_px * (64.0 / 140.0)
        x_off = (S - desk_w_px) / 2
        y_off = (S - desk_h_px) / 2

        def td(x: float, z: float) -> tuple[int, int]:
            return (
                round(x_off + (x + 70.0) / 140.0 * desk_w_px),
                round(y_off + (z + 32.0) / 64.0 * desk_h_px),
            )

        x0, y0 = td(14.0, 1.0)
        x1, y1 = td(20.0, 11.0)
        body = img.getpixel((round(x0 + (x1 - x0) * 0.32), (y0 + y1) // 2))
        corner = img.getpixel((x0 + 1, y0 + 1))
        wheel = img.getpixel(((x0 + x1) // 2, round(y0 + (y1 - y0) * 0.23)))

        assert body[0] > 120 and body[1] < 90 and body[2] < 90
        assert corner[0] < 140  # rounded corner stays desk/outline, not filled mouse red
        assert wheel[0] < body[0] and wheel[1] < body[1]


# ── 채널 → 구도(shot_type) 해석 (투영 선택 근거) ──────────────────────────
def test_resolve_shot_type_by_channel_and_override():
    assert ai._resolve_shot_type({"target_channel": "인스타그램"}) == "top_down"
    assert ai._resolve_shot_type({"target_channel": "스마트스토어"}) == "hero"
    assert ai._resolve_shot_type({"target_channel": "배너 광고"}) == "wide_scene"
    # 명시 shot_type이 채널 기본값보다 우선
    assert ai._resolve_shot_type({"target_channel": "인스타그램", "shot_type": "hero"}) == "hero"
    # 알 수 없는 채널은 hero 폴백
    assert ai._resolve_shot_type({"target_channel": "없는채널"}) == "hero"


# ── 마우스 1개 보장(사용자 핵심 불만: 복제 방지) ──────────────────────────
def test_single_mouse_in_placement(tmp_path):
    meta = _build(tmp_path, ["monitor", "mouse", "plant"])
    mice = [item for item in meta["placed_items"] if _comp_canon(item) == "mouse"]
    assert len(mice) == 1


# ── 래스터 함수 직접 호출(GL 의존성 없이 동작) ─────────────────────────────
def test_raster_helper_returns_png_bytes():
    boxes = [
        (-10.0, 0.0, 10.0, 12.0, "keyboard"),
        (14.0, 1.0, 20.0, 11.0, "mouse"),
        (40.0, -20.0, 54.0, -6.0, "plant"),
    ]
    raster = build_setup_composition_raster(
        boxes=boxes,
        desk_width=140.0,
        desk_depth=64.0,
        colors={"desk": "#6b4f34", "deskmat": "#23262b", "keyboard": "#2b2f36", "mouse": "#b23b3b"},
        theme="minimal",
        monitor={"center_x": 0.0, "center_z": -22.0, "panel_w": 60.0, "panel_h": 36.0},
        size=512,
    )
    assert isinstance(raster, bytes) and raster
    with Image.open(io.BytesIO(raster)) as img:
        assert img.size == (512, 512)


def test_raster_size_param_respected():
    raster = build_setup_composition_raster(
        boxes=[(-5.0, 0.0, 5.0, 10.0, "keyboard")],
        desk_width=120.0,
        desk_depth=60.0,
        colors={"desk": "#6b4f34"},
        size=768,
    )
    with Image.open(io.BytesIO(raster)) as img:
        assert img.size == (768, 768)


# ── 구도 맵 레퍼런스는 더 높은 denoise(평면 색블록 → 사실화) ───────────────
def test_composition_denoise_differs_from_drawing_denoise():
    settings = get_settings()
    # 구도 맵 전용 denoise는 도면 img2img denoise보다 높아야 한다(사실감 확보).
    assert settings.comfyui_composition_denoise > settings.comfyui_img2img_denoise


def test_workflow_mapping_uses_supplied_denoise():
    settings = get_settings()
    base = ai._workflow_placeholder_mapping(settings, "p", 1024, 1024)
    assert base["{denoise}"] == settings.comfyui_img2img_denoise
    override = ai._workflow_placeholder_mapping(settings, "p", 1024, 1024, denoise=0.9)
    assert override["{denoise}"] == 0.9
    assert override["{{denoise}}"] == 0.9
