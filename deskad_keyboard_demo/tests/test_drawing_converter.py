"""도면 변환기 QA 배터리 — convert_plate_drawing_to_glb 회귀 가드.

`drawing_converter.py`엔 테스트가 0개였다. 실제 외부 변환기(DRAWING_CONVERTER_CMD)·
KEYBOARD_LAYOUT_REPO_PATH 없이도 결정적으로 검증 가능한 항목을 깐다:
- GLB 패스스루(외부 도구 0)
- DWG/DXF 분기는 '가짜 변환기 커맨드'로 계약(성공/실패/미설정)만 검증

실제 DWG/DXF→GLB 변환 품질은 변환기 설치 후 별도(Phase 3). 여기선 배선·계약·엣지만.
"""
import json
import struct
import sys
import types

import pytest

from backend import drawing_converter


def _minimal_glb() -> bytes:
    """model-viewer가 읽을 수 있는 최소 유효 GLB(JSON 청크만)."""
    gltf = {
        "asset": {"version": "2.0"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0}],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0}}]}],
        "accessors": [{"min": [0.0, 0.0, 0.0], "max": [10.0, 5.0, 8.0]}],
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


def _fake_settings(cmd: str = "", timeout: int = 60):
    return types.SimpleNamespace(
        drawing_converter_cmd=cmd,
        drawing_converter_timeout_seconds=timeout,
    )


def _converter_cmd(python_code: str) -> str:
    """{input}/{output} 플레이스홀더를 가진 가짜 변환기 커맨드 문자열."""
    return f'{sys.executable} -c "{python_code}" {{input}} {{output}}'


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """plate 카탈로그가 가리키는 가짜 keyboard_layout 저장소."""
    root = tmp_path / "kbd_repo"
    (root / "plates").mkdir(parents=True)
    # keyboard_layout_repo_path()는 keyboard_data.json 존재로 저장소를 인정한다.
    (root / "keyboard_data.json").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("KEYBOARD_LAYOUT_REPO_PATH", str(root))
    return root


# ── GLB 패스스루 (외부 도구 불필요) ────────────────────────────────────────
def test_glb_passthrough_copies_bytes_and_builds_url(repo, tmp_path):
    glb = _minimal_glb()
    (repo / "plates" / "sample.glb").write_bytes(glb)
    models = tmp_path / "models"
    plate = {"file_path": "plates/sample.glb", "name": "샘플 플레이트", "id": "p1"}

    result = drawing_converter.convert_plate_drawing_to_glb(
        plate=plate, model_dir=models, public_base_url="http://host"
    )

    assert result["conversion"] == "glb_passthrough"
    out = models / result["model_file"]
    assert out.exists() and out.read_bytes() == glb  # 바이트 무손실
    assert result["model_url"] == f"http://host/static/models/{result['model_file']}"
    assert result["model_file"].endswith(".glb")


def test_korean_plate_name_preserved_in_slug(repo, tmp_path):
    """한글 제품명이 파일명에 보존된다(QA 06-05 지적 → product_slug가 한글 허용)."""
    (repo / "plates" / "k.glb").write_bytes(_minimal_glb())
    plate = {"file_path": "plates/k.glb", "name": "한글 플레이트", "id": "abc123"}

    result = drawing_converter.convert_plate_drawing_to_glb(
        plate=plate, model_dir=tmp_path / "m", public_base_url="http://h"
    )
    assert "한글_플레이트" in result["model_file"]


# ── 입력 검증 / 엣지 ────────────────────────────────────────────────────────
def test_unsupported_extension_rejected(repo, tmp_path):
    (repo / "plates" / "bad.pdf").write_bytes(b"%PDF-1.4")
    plate = {"file_path": "plates/bad.pdf", "id": "p2"}
    with pytest.raises(ValueError, match="Unsupported drawing extension"):
        drawing_converter.convert_plate_drawing_to_glb(
            plate=plate, model_dir=tmp_path / "m", public_base_url="http://h"
        )


def test_missing_source_file_rejected(repo, tmp_path):
    plate = {"file_path": "plates/nope.glb", "id": "p3"}
    with pytest.raises(ValueError, match="does not exist"):
        drawing_converter.convert_plate_drawing_to_glb(
            plate=plate, model_dir=tmp_path / "m", public_base_url="http://h"
        )


def test_repo_not_configured_rejected(monkeypatch, tmp_path):
    # 저장소 미설정 → DEFAULT 경로엔 keyboard_data.json이 없어 None.
    monkeypatch.delenv("KEYBOARD_LAYOUT_REPO_PATH", raising=False)
    plate = {"file_path": "plates/x.glb", "id": "p4"}
    with pytest.raises(ValueError, match="repo path is not configured"):
        drawing_converter.convert_plate_drawing_to_glb(
            plate=plate, model_dir=tmp_path / "m", public_base_url="http://h"
        )


# ── DWG/DXF 분기 (가짜 변환기로 계약만 검증) ────────────────────────────────
def test_dxf_without_converter_cmd_gives_clear_error(repo, tmp_path, monkeypatch):
    (repo / "plates" / "p.dxf").write_text("0\nSECTION", encoding="utf-8")
    monkeypatch.setattr(drawing_converter, "get_settings", lambda: _fake_settings(cmd=""))
    plate = {"file_path": "plates/p.dxf", "id": "p5"}
    with pytest.raises(ValueError, match="DRAWING_CONVERTER_CMD is not configured"):
        drawing_converter.convert_plate_drawing_to_glb(
            plate=plate, model_dir=tmp_path / "m", public_base_url="http://h"
        )


def test_dxf_with_converter_produces_glb_and_labels_conversion(repo, tmp_path, monkeypatch):
    (repo / "plates" / "p.dxf").write_text("0\nSECTION", encoding="utf-8")
    code = "import sys,pathlib; pathlib.Path(sys.argv[2]).write_bytes(b'converted-glb')"
    monkeypatch.setattr(
        drawing_converter, "get_settings", lambda: _fake_settings(cmd=_converter_cmd(code))
    )
    plate = {"file_path": "plates/p.dxf", "name": "plate", "id": "p6"}

    result = drawing_converter.convert_plate_drawing_to_glb(
        plate=plate, model_dir=tmp_path / "m", public_base_url="http://h"
    )

    assert result["conversion"] == "dxf_to_glb"
    out = (tmp_path / "m") / result["model_file"]
    assert out.exists() and out.read_bytes() == b"converted-glb"


def test_converter_nonzero_exit_surfaces_returncode(repo, tmp_path, monkeypatch):
    (repo / "plates" / "p.dwg").write_bytes(b"DWG-binary")
    code = "import sys; sys.stderr.write('boom'); sys.exit(3)"
    monkeypatch.setattr(
        drawing_converter, "get_settings", lambda: _fake_settings(cmd=_converter_cmd(code))
    )
    plate = {"file_path": "plates/p.dwg", "id": "p7"}
    with pytest.raises(ValueError, match="returned 3"):
        drawing_converter.convert_plate_drawing_to_glb(
            plate=plate, model_dir=tmp_path / "m", public_base_url="http://h"
        )
