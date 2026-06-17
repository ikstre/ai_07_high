"""depth-ControlNet 배열 고정 경로 회귀 테스트.

평면 raster img2img로는 "사진+정확 배열"을 동시에 못 얻는다는 2026-06-16 A/B
결론에 따라 추가된 경로: 셋업 GLB를 헤드리스 렌더한 depth를 ControlNet 입력으로
주입해 65% 배열을 denoise와 독립적으로 고정한다(text2img, denoise 1.0). 활성
조건(모델+strength)과 워크플로 선택 게이팅·placeholder 치환을 검증한다.
"""
import json
from pathlib import Path

import pytest

from backend import ai, config, result_cache
from backend.renderer import build_desk_setup_depth_png

WF_DIR = Path(ai.__file__).resolve().parent.parent / "tools" / "comfyui_workflows"


def _settings(**overrides) -> config.Settings:
    return config.Settings(**overrides)


def _payload_with_glb(tmp_path, monkeypatch) -> dict:
    """model_url이 실재 GLB(빈 파일)를 가리키도록 _BACKEND_BASE_DIR을 tmp로 돌린다."""
    models = tmp_path / "static" / "models"
    models.mkdir(parents=True)
    (models / "desk.glb").write_bytes(b"glb")
    monkeypatch.setattr(ai, "_BACKEND_BASE_DIR", tmp_path)
    return {
        "reference_is_composition": True,
        "reference_image_b64": "QUJD",
        "model_url": "http://h/static/models/desk.glb",
    }


# ── ControlNet 활성 판정 ──────────────────────────────────────────────────────
def test_controlnet_enabled_requires_model_and_positive_strength():
    assert ai._controlnet_enabled(
        _settings(comfyui_controlnet_model="m.safetensors", comfyui_controlnet_strength=0.7)
    ) is True
    # 모델 없음 / 강도 0 → 비활성(둘 다 필요)
    assert ai._controlnet_enabled(
        _settings(comfyui_controlnet_model="", comfyui_controlnet_strength=0.7)
    ) is False
    assert ai._controlnet_enabled(
        _settings(comfyui_controlnet_model="m.safetensors", comfyui_controlnet_strength=0.0)
    ) is False


# ── 셋업 GLB 경로 해석(경로 탈출/비-GLB/미존재 차단) ───────────────────────────
def test_setup_glb_path_resolves_existing_and_rejects_others(tmp_path, monkeypatch):
    models = tmp_path / "static" / "models"
    models.mkdir(parents=True)
    glb = models / "desk.glb"
    glb.write_bytes(b"glb")
    monkeypatch.setattr(ai, "_BACKEND_BASE_DIR", tmp_path)

    assert ai._setup_glb_path({"model_url": "http://h/static/models/desk.glb"}) == glb
    # 미존재 / 비-GLB 확장자 / 경로 탈출(basename만 사용) / model_url 없음 → None
    assert ai._setup_glb_path({"model_url": "http://h/static/models/missing.glb"}) is None
    assert ai._setup_glb_path({"model_url": "http://h/static/models/desk.png"}) is None
    assert ai._setup_glb_path({"model_url": "http://h/a/../../etc/passwd"}) is None
    assert ai._setup_glb_path({}) is None


# ── 워크플로 선택 게이팅 ──────────────────────────────────────────────────────
def test_candidate_prefers_controlnet_when_enabled(tmp_path, monkeypatch):
    payload = _payload_with_glb(tmp_path, monkeypatch)
    monkeypatch.setattr(
        ai, "get_settings",
        lambda: _settings(comfyui_controlnet_model="m.safetensors", comfyui_controlnet_strength=0.7),
    )
    names = ai._candidate_workflow_names(payload)
    assert names[0] == "flux_controlnet_depth"
    assert "flux_img2img" in names  # 폴백 후보는 유지


def test_candidate_falls_back_to_img2img_when_disabled(tmp_path, monkeypatch):
    payload = _payload_with_glb(tmp_path, monkeypatch)
    monkeypatch.setattr(
        ai, "get_settings",
        lambda: _settings(comfyui_controlnet_model="", comfyui_controlnet_strength=0.0),
    )
    names = ai._candidate_workflow_names(payload)
    assert "flux_controlnet_depth" not in names
    assert names[0] == "flux_img2img"


def test_candidate_no_controlnet_without_resolvable_glb(monkeypatch):
    # 모델/강도는 켜졌지만 model_url(GLB) 없음 → ControlNet 미선택(img2img 폴백)
    monkeypatch.setattr(
        ai, "get_settings",
        lambda: _settings(comfyui_controlnet_model="m.safetensors", comfyui_controlnet_strength=0.7),
    )
    names = ai._candidate_workflow_names(
        {"reference_is_composition": True, "reference_image_b64": "QUJD"}
    )
    assert "flux_controlnet_depth" not in names


# ── placeholder 매핑 / 캐시 키 ────────────────────────────────────────────────
def test_controlnet_model_in_placeholder_mapping():
    mapping = ai._workflow_placeholder_mapping(
        _settings(comfyui_controlnet_model="m.safetensors"), "kbd", 1024, 1024
    )
    assert mapping["{controlnet_model}"] == "m.safetensors"
    assert mapping["{{controlnet_model}}"] == "m.safetensors"


def test_cache_key_changes_with_controlnet_strength(monkeypatch):
    monkeypatch.setenv("COMFYUI_CONTROLNET_MODEL", "m.safetensors")
    monkeypatch.setenv("COMFYUI_CONTROLNET_STRENGTH", "0.5")
    k1 = result_cache.make_image_cache_key("p", {}, 1024, 1024)
    monkeypatch.setenv("COMFYUI_CONTROLNET_STRENGTH", "0.9")
    k2 = result_cache.make_image_cache_key("p", {}, 1024, 1024)
    assert k1 != k2  # strength 스윕이 캐시에 막히지 않아야 한다


# ── _load_comfyui_workflow: depth 주입(실제 워크플로 파일 사용, 업로드만 mock) ──
def test_load_controlnet_workflow_injects_depth_and_strength(tmp_path, monkeypatch):
    payload = _payload_with_glb(tmp_path, monkeypatch)
    monkeypatch.setattr(
        ai, "get_settings",
        lambda: _settings(
            comfyui_workflows_dir=str(WF_DIR), comfyui_base_url="http://comfy",
            comfyui_controlnet_model="m.safetensors", comfyui_controlnet_strength=0.7,
            comfyui_composition_steps=8,
        ),
    )
    # depth 렌더는 무겁고 OSMesa 필요 → 업로드 헬퍼 통째로 mock(치환 경로만 검증)
    monkeypatch.setattr(ai, "_upload_controlnet_depth_to_comfyui", lambda p, s: "deskad_controlnet_depth.png")

    wf = ai._load_comfyui_workflow(payload, "studio keyboard photo")
    assert wf is not None
    assert wf["22"]["inputs"]["image"] == "deskad_controlnet_depth.png"
    assert wf["20"]["inputs"]["control_net_name"] == "m.safetensors"
    assert wf["21"]["inputs"]["type"] == "depth"
    assert wf["23"]["inputs"]["strength"] == 0.7
    assert wf["23"]["inputs"]["vae"] == ["5", 0]
    assert wf["9"]["inputs"]["denoise"] == 1.0     # text2img(구조는 ControlNet이 고정)
    assert wf["9"]["inputs"]["steps"] == 8          # 셋업 레퍼런스 → composition steps
    assert not any("{" in str(v) for n in wf.values() for v in n["inputs"].values()
                   if isinstance(v, str))           # placeholder 잔류 없음


def test_load_controlnet_workflow_draft_when_depth_fails(tmp_path, monkeypatch):
    payload = _payload_with_glb(tmp_path, monkeypatch)
    monkeypatch.setattr(
        ai, "get_settings",
        lambda: _settings(
            comfyui_workflows_dir=str(WF_DIR), comfyui_base_url="http://comfy",
            comfyui_controlnet_model="m.safetensors", comfyui_controlnet_strength=0.7,
        ),
    )
    monkeypatch.setattr(ai, "_upload_controlnet_depth_to_comfyui", lambda p, s: None)
    # depth 입력이 없으면 구동 불가 → None(호출부가 draft 처리)
    out = ai._load_comfyui_workflow({**payload, "image_workflow": "flux_controlnet_depth"}, "kbd")
    assert out is None


# ── 배포된 워크플로 JSON 구조(노드 와이어링) ──────────────────────────────────
def test_shipped_controlnet_workflow_wires_depth_to_conditioning():
    wf = json.loads((WF_DIR / "flux_controlnet_depth.json").read_text(encoding="utf-8"))
    loader_id = next(k for k, n in wf.items() if n.get("class_type") == "ControlNetLoader")
    union_id = next(k for k, n in wf.items() if n.get("class_type") == "SetUnionControlNetType")
    apply_id = next(k for k, n in wf.items() if n.get("class_type") == "ControlNetApplyAdvanced")
    loadimg_id = next(k for k, n in wf.items() if n.get("class_type") == "LoadImage")
    ks = next(n for n in wf.values() if n.get("class_type") == "KSampler")

    # ControlNetLoader → SetUnionControlNetType(type=depth) → ControlNetApplyAdvanced
    assert wf[union_id]["inputs"]["control_net"][0] == loader_id
    assert wf[union_id]["inputs"]["type"] == "depth"
    assert wf[apply_id]["inputs"]["control_net"][0] == union_id
    assert wf[apply_id]["inputs"]["image"][0] == loadimg_id
    assert wf[apply_id]["inputs"]["vae"][0] != ""           # InstantX latent_input=True → vae 필수
    assert wf[loader_id]["inputs"]["control_net_name"] == "{controlnet_model}"
    assert wf[apply_id]["inputs"]["strength"] == "{controlnet_strength}"
    assert wf[loadimg_id]["inputs"]["image"] == "{controlnet_image_name}"
    # KSampler positive/negative는 ControlNetApplyAdvanced에서(text2img, EmptyLatentImage)
    assert ks["inputs"]["positive"][0] == apply_id
    assert ks["inputs"]["negative"][0] == apply_id
    assert ks["inputs"]["denoise"] == 1.0
    assert any(n.get("class_type") == "EmptyLatentImage" for n in wf.values())
    assert "{reference_image_name}" not in json.dumps(wf)   # img2img 아님


# ── depth 생성기(헤드리스 렌더; OSMesa 없으면 skip) ───────────────────────────
def test_depth_png_none_for_missing_path():
    # 미존재 경로는 pyrender import 전에 None(빠름)
    assert build_desk_setup_depth_png("/no/such/file.glb") is None


def test_depth_png_renders_small_glb_and_caches(tmp_path):
    trimesh = pytest.importorskip("trimesh")
    pytest.importorskip("pyrender")
    box = trimesh.creation.box(extents=[40.0, 10.0, 40.0])
    box.apply_translation([0.0, 5.0, 6.0])  # 카메라 타깃 부근에 배치(보이도록)
    glb = tmp_path / "box.glb"
    box.export(str(glb))

    png = build_desk_setup_depth_png(glb, size=256)
    if png is None:
        pytest.skip("headless GL(OSMesa) 미가용 환경")
    assert png[:8] == b"\x89PNG\r\n\x1a\n"       # 유효 PNG
    assert build_desk_setup_depth_png(glb, size=256) == png  # 2회차는 캐시(동일 바이트)
