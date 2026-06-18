import json
from pathlib import Path

from backend import ai, config
from backend.job_store import ImageJobStore
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
        comfyui_steps=12,
    )
    mapping = ai._workflow_placeholder_mapping(settings, "a keyboard", 1024, 768)

    assert mapping["{negative_prompt}"] == "custom negative"
    assert mapping["{{negative_prompt}}"] == "custom negative"
    assert mapping["{lora_name}"] == "my_lora.safetensors"
    assert mapping["{lora_strength}"] == 0.7
    assert mapping["{controlnet_image}"] == "ref.png"
    assert mapping["{controlnet_strength}"] == 0.5
    assert mapping["{width}"] == 1024 and mapping["{height}"] == 768
    assert mapping["{steps}"] == 12
    assert mapping["{{steps}}"] == 12
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
                "9": {
                    "class_type": "KSampler",
                    "inputs": {"latent_image": ["15", 0], "denoise": "{denoise}", "steps": "{steps}"},
                },
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
    assert workflow["9"]["inputs"]["steps"] == 4
    assert captured["url"].endswith("/upload/image")
    assert captured["files"]["image"][2] == "image/png"


def test_composition_reference_uses_composition_steps(tmp_path, monkeypatch):
    wf_dir = _img2img_dir(tmp_path)
    monkeypatch.setattr(
        ai,
        "get_settings",
        lambda: _settings(
            comfyui_workflows_dir=str(wf_dir),
            comfyui_base_url="http://comfy",
            comfyui_steps=4,
            comfyui_composition_steps=12,
            comfyui_composition_denoise=0.9,
        ),
    )
    monkeypatch.setattr(ai, "_reference_image_b64", lambda payload: "QUJD")
    monkeypatch.setattr(
        ai.requests,
        "post",
        lambda url, **kw: _UploadResp({"name": "deskad_reference.png", "subfolder": ""}),
    )

    workflow = ai._load_comfyui_workflow(
        {"image_workflow": "flux_img2img", "reference_is_composition": True},
        "studio keyboard",
    )

    assert workflow["9"]["inputs"]["denoise"] == 0.9
    assert workflow["9"]["inputs"]["steps"] == 12


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
    assert ks["inputs"]["steps"] == "{steps}"
    # EmptyLatentImage는 도면 latent로 대체되어 없어야 한다.
    assert not any(n.get("class_type") == "EmptyLatentImage" for n in wf.values())


# ── grid_three: ComfyUI 컷별(시점별) 분할 생성 ────────────────────────────────
class _Resp:
    def __init__(self, body=None, content=b""):
        self._body = body
        self.content = content

    def raise_for_status(self):
        pass

    def json(self):
        return self._body


def _grid_settings(tmp_path):
    wf_dir = tmp_path / "workflows"
    wf_dir.mkdir()
    (wf_dir / "flux_schnell_basic.json").write_text(
        json.dumps(
            {
                "6": {"inputs": {"text": "{prompt}", "neg": "{negative_prompt}"}},
                "5": {
                    "class_type": "EmptyLatentImage",
                    "inputs": {"batch_size": "{batch_size}", "width": "{width}", "height": "{height}"},
                },
            }
        ),
        encoding="utf-8",
    )
    return config.Settings(comfyui_workflows_dir=str(wf_dir), comfyui_base_url="http://comfy", comfyui_best_of_n=4)


def test_grid_three_comfyui_submits_first_shot_only_then_pending(tmp_path, monkeypatch):
    # 순차 제출: 제출 시점엔 첫 컷만 ComfyUI에 올라가고 나머지는 pending으로 대기한다
    # (단일 L4에서 3컷을 한꺼번에 큐잉하면 VRAM 피크가 겹쳐 ComfyUI가 죽을 수 있음).
    settings = _grid_settings(tmp_path)
    monkeypatch.setattr(ai, "get_settings", lambda: settings)
    posts: list[dict] = []

    def _fake_post(url, **kw):
        posts.append(kw.get("json", {}))
        return _Resp({"prompt_id": f"pid-{len(posts) - 1}"})

    monkeypatch.setattr(ai.requests, "post", _fake_post)

    job = ai._submit_comfyui_job({"job_id": "JOB"}, {"poster_template": "grid_three", "image_ratio": "1:1"}, "ignored")

    assert job["status"] == "queued"
    shots = job["comfyui_shot_jobs"]
    # 3컷이 서로 다른 shot_type(=다른 카메라/구도)으로 계획된다.
    assert [s["shot_type"] for s in shots] == ["hero", "detail_macro", "eye_level"]
    # 첫 컷만 큐잉(1회 POST), 나머지는 pending(아직 미제출).
    assert len(posts) == 1
    assert shots[0]["status"] == "queued" and shots[0]["comfyui_prompt_id"] == "pid-0"
    assert [s["status"] for s in shots[1:]] == ["pending", "pending"]
    assert all("comfyui_prompt_id" not in s for s in shots[1:])
    # 컷마다 프롬프트가 미리 계산돼 저장되고 실제로 다르다(같은 프롬프트 batch가 아니라 시점 분리).
    assert len({s["prompt"] for s in shots}) == 3
    # 첫 컷은 batch_size=1(best-of-N override) + 컷별 client_id.
    assert posts[0]["prompt"]["5"]["inputs"]["batch_size"] == 1
    assert posts[0]["client_id"] == "JOB:hero"


def test_grid_three_submits_sequentially_one_cut_at_a_time(tmp_path, monkeypatch):
    # 폴링이 현재 컷 완료를 확인할 때마다 다음 컷 1개만 추가 제출 → ComfyUI 큐엔 항상 1개.
    settings = _grid_settings(tmp_path)
    monkeypatch.setattr(ai, "get_settings", lambda: settings)
    monkeypatch.setattr(ai, "IMAGE_JOB_STORE", ImageJobStore(tmp_path / "jobs.jsonl"))
    monkeypatch.setattr(ai, "_maybe_release_comfyui_worker", lambda job: None)
    monkeypatch.setattr(ai, "_cache_completed_image_job", lambda job: None)

    posts: list[dict] = []

    def _fake_post(url, **kw):
        posts.append(kw.get("json", {}))
        return _Resp({"prompt_id": f"pid-{len(posts) - 1}"})

    def _fake_get(url, **kw):
        if "/history/" in url:
            pid = url.rsplit("/", 1)[-1]
            return _Resp(
                {pid: {"status": {"status_str": "success"},
                       "outputs": {"9": {"images": [{"filename": f"{pid}.png", "subfolder": "", "type": "output"}]}}}}
            )
        return _Resp(content=b"IMG-" + url.encode())

    monkeypatch.setattr(ai.requests, "post", _fake_post)
    monkeypatch.setattr(ai.requests, "get", _fake_get)

    job = ai._submit_comfyui_job({"job_id": "SEQ"}, {"poster_template": "grid_three", "image_ratio": "1:1"}, "ignored")
    ai.IMAGE_JOB_STORE.save(job)
    assert len(posts) == 1  # 첫 컷만

    ai.poll_image_job("SEQ")  # 첫 컷 완료 → 두 번째 제출
    assert len(posts) == 2
    ai.poll_image_job("SEQ")  # 두 번째 완료 → 세 번째 제출
    assert len(posts) == 3

    public = ai.poll_image_job("SEQ")  # 세 번째 완료 → 집계
    assert public["status"] == "completed"
    # 컷별 client_id로 정확히 3컷이 순서대로 제출됐다.
    assert [p["client_id"] for p in posts] == ["SEQ:hero", "SEQ:detail", "SEQ:lifestyle"]
    ref = ai.IMAGE_JOB_STORE.get("SEQ")["local_image_reference"]
    assert ref["image_count"] == 3 and len(set(ref["image_b64s"])) == 3
    # 보관 payload는 완료 후 비워지고 공개 응답에도 노출되지 않는다.
    assert "_grid_payload" not in ai.IMAGE_JOB_STORE.get("SEQ")
    assert "_grid_payload" not in public


def test_grid_three_comfyui_poll_aggregates_three_cuts(tmp_path, monkeypatch):
    settings = _grid_settings(tmp_path)
    monkeypatch.setattr(ai, "get_settings", lambda: settings)
    monkeypatch.setattr(ai, "IMAGE_JOB_STORE", ImageJobStore(tmp_path / "jobs.jsonl"))
    monkeypatch.setattr(ai, "_maybe_release_comfyui_worker", lambda job: None)
    monkeypatch.setattr(ai, "_cache_completed_image_job", lambda job: None)

    job = {
        "job_id": "JOB2",
        "provider": "comfyui",
        "status": "queued",
        "comfyui_shot_jobs": [
            {"id": "hero", "shot_type": "hero", "status": "queued", "comfyui_prompt_id": "p0"},
            {"id": "detail", "shot_type": "detail_macro", "status": "queued", "comfyui_prompt_id": "p1"},
            {"id": "lifestyle", "shot_type": "eye_level", "status": "queued", "comfyui_prompt_id": "p2"},
        ],
    }
    ai.IMAGE_JOB_STORE.save(job)

    def _fake_get(url, **kw):
        if "/history/" in url:
            pid = url.rsplit("/", 1)[-1]
            return _Resp(
                {pid: {"status": {"status_str": "success"},
                       "outputs": {"9": {"images": [{"filename": f"{pid}.png", "subfolder": "", "type": "output"}]}}}}
            )
        return _Resp(content=b"IMG-" + url.encode())  # filename별로 distinct content

    monkeypatch.setattr(ai.requests, "get", _fake_get)

    public = ai.poll_image_job("JOB2")
    assert public["status"] == "completed"
    ref = ai.IMAGE_JOB_STORE.get("JOB2")["local_image_reference"]
    # 컷당 1장씩 shot 순서대로 3장 집계 → poster의 메인/디테일/무드 패널로 쓰인다.
    assert ref["image_count"] == 3
    assert len(ref["image_b64s"]) == 3
    assert len(set(ref["image_b64s"])) == 3
