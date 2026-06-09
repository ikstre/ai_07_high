import json
from pathlib import Path

from backend import ai, config
from backend.main import AdContentRequest


def _settings(**overrides) -> config.Settings:
    return config.Settings(**overrides)


def _make_dir(tmp_path, *names: str):
    wf_dir = tmp_path / "workflows"
    wf_dir.mkdir()
    for name in names:
        (wf_dir / f"{name}.json").write_text(
            json.dumps({"6": {"inputs": {"text": "{prompt}", "neg": "{negative_prompt}"}}}),
            encoding="utf-8",
        )
    return wf_dir


def test_safe_workflow_name_rejects_traversal_and_invalid():
    assert ai._safe_workflow_name("flux_promo_banner") == "flux_promo_banner"
    assert ai._safe_workflow_name("flux-2") == "flux-2"
    assert ai._safe_workflow_name("../../etc/passwd") == ""
    assert ai._safe_workflow_name("a/b") == ""
    assert ai._safe_workflow_name("") == ""
    assert ai._safe_workflow_name(None) == ""


def test_select_prefers_explicit_image_workflow(tmp_path, monkeypatch):
    wf_dir = _make_dir(tmp_path, "flux_schnell_basic", "flux_promo")
    monkeypatch.setattr(ai, "get_settings", lambda: _settings(comfyui_workflows_dir=str(wf_dir)))

    selected = ai._select_workflow_path({"image_workflow": "flux_promo"})
    assert selected == wf_dir / "flux_promo.json"


def test_select_uses_situational_template(tmp_path, monkeypatch):
    wf_dir = _make_dir(tmp_path, "flux_schnell_basic", "flux_promo_banner")
    monkeypatch.setattr(ai, "get_settings", lambda: _settings(comfyui_workflows_dir=str(wf_dir)))

    selected = ai._select_workflow_path({"template": "promo_banner"})
    assert selected == wf_dir / "flux_promo_banner.json"


def test_select_uses_poster_template_field_from_api_payload(tmp_path, monkeypatch):
    wf_dir = _make_dir(tmp_path, "flux_schnell_basic", "flux_promo_banner")
    monkeypatch.setattr(ai, "get_settings", lambda: _settings(comfyui_workflows_dir=str(wf_dir)))

    payload = AdContentRequest(poster_template="promo_banner").model_dump()
    selected = ai._select_workflow_path(payload)
    assert selected == wf_dir / "flux_promo_banner.json"


def test_ad_content_request_preserves_explicit_image_workflow():
    payload = AdContentRequest(image_workflow="flux_custom").model_dump()

    assert payload["image_workflow"] == "flux_custom"


def test_select_falls_back_to_default_when_no_match(tmp_path, monkeypatch):
    wf_dir = _make_dir(tmp_path, "flux_schnell_basic")
    monkeypatch.setattr(ai, "get_settings", lambda: _settings(comfyui_workflows_dir=str(wf_dir)))

    # Unknown explicit name + unknown template → default workflow file.
    selected = ai._select_workflow_path({"image_workflow": "does_not_exist", "template": "nope"})
    assert selected == wf_dir / "flux_schnell_basic.json"


def test_select_traversal_name_cannot_escape_dir(tmp_path, monkeypatch):
    wf_dir = _make_dir(tmp_path, "flux_schnell_basic")
    monkeypatch.setattr(ai, "get_settings", lambda: _settings(comfyui_workflows_dir=str(wf_dir)))

    selected = ai._select_workflow_path({"image_workflow": "../../../etc/passwd"})
    assert selected == wf_dir / "flux_schnell_basic.json"  # traversal ignored, default used


def test_select_legacy_single_path_when_dir_unset(tmp_path, monkeypatch):
    legacy = tmp_path / "single.json"
    legacy.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        ai, "get_settings",
        lambda: _settings(comfyui_workflows_dir="", comfyui_workflow_path=str(legacy)),
    )

    selected = ai._select_workflow_path({"image_workflow": "anything"})
    assert selected == legacy


def test_placeholder_mapping_is_configurable_with_both_brace_styles():
    settings = _settings(
        comfyui_negative_prompt="custom negative",
        comfyui_lora_name="my_lora.safetensors",
        comfyui_lora_strength=0.7,
        comfyui_controlnet_image="ref.png",
        comfyui_controlnet_strength=0.5,
    )
    mapping = ai._workflow_placeholder_mapping(settings, "a keyboard", 1024, 768)

    assert mapping["{negative_prompt}"] == "custom negative"
    assert mapping["{{negative_prompt}}"] == "custom negative"
    assert mapping["{lora_name}"] == "my_lora.safetensors"
    assert mapping["{lora_strength}"] == 0.7
    assert mapping["{controlnet_image}"] == "ref.png"
    assert mapping["{controlnet_strength}"] == 0.5
    assert mapping["{width}"] == 1024 and mapping["{height}"] == 768
    # one seed per call, shared by both brace styles
    assert mapping["{seed}"] == mapping["{{seed}}"]


def test_load_workflow_injects_configured_negative_prompt(tmp_path, monkeypatch):
    wf_dir = _make_dir(tmp_path, "flux_schnell_basic")
    monkeypatch.setattr(
        ai, "get_settings",
        lambda: _settings(comfyui_workflows_dir=str(wf_dir), comfyui_negative_prompt="no logos here"),
    )

    workflow = ai._load_comfyui_workflow({}, "studio keyboard photo")
    node = workflow["6"]["inputs"]
    assert node["text"] == "studio keyboard photo"
    assert node["neg"] == "no logos here"


# ── img2img(선택 도면 강제) 스파이크 ──────────────────────────────────────────

def test_denoise_placeholder_in_mapping():
    mapping = ai._workflow_placeholder_mapping(_settings(comfyui_img2img_denoise=0.6), "kbd", 1024, 1024)
    assert mapping["{denoise}"] == 0.6
    assert mapping["{{denoise}}"] == 0.6


class _UploadResp:
    def __init__(self, body):
        self._body = body

    def raise_for_status(self):
        pass

    def json(self):
        return self._body


def _img2img_dir(tmp_path):
    wf_dir = tmp_path / "workflows"
    wf_dir.mkdir()
    (wf_dir / "flux_img2img.json").write_text(
        json.dumps(
            {
                "14": {"class_type": "LoadImage", "inputs": {"image": "{reference_image_name}"}},
                "9": {"class_type": "KSampler", "inputs": {"latent_image": ["15", 0], "denoise": "{denoise}"}},
            }
        ),
        encoding="utf-8",
    )
    return wf_dir


def test_img2img_uploads_reference_and_substitutes_name(tmp_path, monkeypatch):
    wf_dir = _img2img_dir(tmp_path)
    monkeypatch.setattr(
        ai, "get_settings",
        lambda: _settings(comfyui_workflows_dir=str(wf_dir), comfyui_base_url="http://comfy", comfyui_img2img_denoise=0.6),
    )
    monkeypatch.setattr(ai, "_reference_image_b64", lambda payload: "QUJD")  # base64("ABC")
    captured = {}

    def _fake_post(url, **kwargs):
        captured["url"] = url
        captured["files"] = kwargs.get("files")
        return _UploadResp({"name": "deskad_reference.png", "subfolder": ""})

    monkeypatch.setattr(ai.requests, "post", _fake_post)

    workflow = ai._load_comfyui_workflow({"image_workflow": "flux_img2img"}, "studio keyboard")
    assert workflow["14"]["inputs"]["image"] == "deskad_reference.png"
    assert workflow["9"]["inputs"]["denoise"] == 0.6
    assert captured["url"].endswith("/upload/image")
    assert captured["files"]["image"][2] == "image/png"


def test_img2img_subfolder_prefixes_filename(tmp_path, monkeypatch):
    wf_dir = _img2img_dir(tmp_path)
    monkeypatch.setattr(
        ai, "get_settings",
        lambda: _settings(comfyui_workflows_dir=str(wf_dir), comfyui_base_url="http://comfy"),
    )
    monkeypatch.setattr(ai, "_reference_image_b64", lambda payload: "QUJD")
    monkeypatch.setattr(ai.requests, "post", lambda url, **kw: _UploadResp({"name": "ref.png", "subfolder": "deskad"}))

    workflow = ai._load_comfyui_workflow({"image_workflow": "flux_img2img"}, "kbd")
    assert workflow["14"]["inputs"]["image"] == "deskad/ref.png"


def test_img2img_draft_when_no_reference(tmp_path, monkeypatch):
    wf_dir = _img2img_dir(tmp_path)
    monkeypatch.setattr(
        ai, "get_settings",
        lambda: _settings(comfyui_workflows_dir=str(wf_dir), comfyui_base_url="http://comfy"),
    )
    monkeypatch.setattr(ai, "_reference_image_b64", lambda payload: None)

    # 레퍼런스 없으면 업로드할 입력이 없으므로 워크플로 미구동(None → 호출부가 draft).
    assert ai._load_comfyui_workflow({"image_workflow": "flux_img2img"}, "kbd") is None


def test_shipped_img2img_workflow_wires_loadimage_vaeencode_to_ksampler():
    wf_path = Path(ai.__file__).resolve().parent.parent / "tools" / "comfyui_workflows" / "flux_img2img.json"
    wf = json.loads(wf_path.read_text(encoding="utf-8"))

    load_id = next(k for k, n in wf.items() if n.get("class_type") == "LoadImage")
    enc_id = next(k for k, n in wf.items() if n.get("class_type") == "VAEEncode")
    ks = next(n for n in wf.values() if n.get("class_type") == "KSampler")

    assert wf[load_id]["inputs"]["image"] == "{reference_image_name}"
    assert wf[enc_id]["inputs"]["pixels"][0] == load_id      # VAEEncode ← LoadImage
    assert ks["inputs"]["latent_image"][0] == enc_id          # KSampler ← VAEEncode
    assert ks["inputs"]["denoise"] == "{denoise}"
    # EmptyLatentImage는 도면 latent로 대체되어 없어야 한다.
    assert not any(n.get("class_type") == "EmptyLatentImage" for n in wf.values())
