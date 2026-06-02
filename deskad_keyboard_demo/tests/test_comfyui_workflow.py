import json

from backend import ai, config


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
