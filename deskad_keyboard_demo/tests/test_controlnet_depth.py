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
        "shot_type": "hero",  # desk 씬 → ControlNet 적합(flat-lay/macro는 별도 테스트)
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


def test_controlnet_only_for_perspective_desk_shots(tmp_path, monkeypatch):
    """depth는 3D 데스크(세워진 모니터)를 3/4-위에서 렌더 → hero/eye_level/wide_scene(desk·room)엔
    적합, top_down(flat-lay)·detail_macro엔 부적합 → 그 컷은 img2img 폴백."""
    base = _payload_with_glb(tmp_path, monkeypatch)
    monkeypatch.setattr(
        ai, "get_settings",
        lambda: _settings(comfyui_controlnet_model="m.safetensors", comfyui_controlnet_strength=0.7),
    )
    for shot in ("hero", "eye_level", "wide_scene"):
        names = ai._candidate_workflow_names({**base, "shot_type": shot})
        assert "flux_controlnet_depth" in names, shot
    for shot in ("top_down", "detail_macro"):
        names = ai._candidate_workflow_names({**base, "shot_type": shot})
        assert "flux_controlnet_depth" not in names, shot
        assert names[0] == "flux_img2img", shot  # 폴백


def test_candidate_no_controlnet_without_resolvable_glb(monkeypatch):
    # 모델/강도는 켜졌지만 model_url(GLB) 없음 → ControlNet 미선택(img2img 폴백)
    monkeypatch.setattr(
        ai, "get_settings",
        lambda: _settings(comfyui_controlnet_model="m.safetensors", comfyui_controlnet_strength=0.7),
    )
    names = ai._candidate_workflow_names(
        {"reference_is_composition": True, "reference_image_b64": "QUJD", "shot_type": "hero"}
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


# ── best-of-N 액센트 색 선택 ──────────────────────────────────────────────────
def _solid_b64(rgb, *, accent_patch=None):
    """단색 PNG b64. accent_patch=(rgb)면 중앙 키보드 밴드에 액센트 패치를 넣는다."""
    np = pytest.importorskip("numpy")
    pytest.importorskip("PIL")
    import base64
    import io

    from PIL import Image

    arr = np.full((512, 512, 3), rgb, np.uint8)
    if accent_patch is not None:
        arr[230:300, 200:330] = accent_patch  # (0.34~0.82, 0.14~0.86) 중앙 밴드 안
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def test_best_of_n_batch_size_in_controlnet_workflow(tmp_path, monkeypatch):
    payload = _payload_with_glb(tmp_path, monkeypatch)
    monkeypatch.setattr(
        ai, "get_settings",
        lambda: _settings(
            comfyui_workflows_dir=str(WF_DIR), comfyui_base_url="http://comfy",
            comfyui_controlnet_model="m.safetensors", comfyui_controlnet_strength=0.7,
            comfyui_best_of_n=4,
        ),
    )
    monkeypatch.setattr(ai, "_upload_controlnet_depth_to_comfyui", lambda p, s: "d.png")
    wf = ai._load_comfyui_workflow(payload, "kbd")
    assert wf["16"]["inputs"]["batch_size"] == 4  # EmptyLatentImage batch = best_of_n


def test_best_of_n_clamped_in_mapping():
    # 1~8 클램프(0/음수→1, 과대→8)
    assert ai._workflow_placeholder_mapping(_settings(comfyui_best_of_n=0), "p", 8, 8)["{batch_size}"] == 1
    assert ai._workflow_placeholder_mapping(_settings(comfyui_best_of_n=99), "p", 8, 8)["{batch_size}"] == 8


def test_select_best_accent_image_picks_spec_colour():
    from backend.quality_gate import select_best_accent_image

    without = _solid_b64((230, 230, 230))
    with_blue = _solid_b64((230, 230, 230), accent_patch=(111, 143, 175))
    res = select_best_accent_image([without, with_blue], "#6f8faf")
    assert res is not None and res["best_index"] == 1
    # 액센트 색 미설정이면 None(호출부가 첫 컷 유지)
    assert select_best_accent_image([without, with_blue], None) is None
    assert select_best_accent_image([without, with_blue], "") is None


def test_hex_to_rgb_accepts_short_and_alpha_hex():
    # #rrggbb 외에 단축형(#abc)·알파 포함(#rrggbbaa)도 파싱해야 유효 색에서 best-of-N이
    # 조용히 꺼지지 않는다. 잘못된 길이/문자는 None(호출부 no-op).
    from backend.quality_gate import _hex_to_rgb

    assert _hex_to_rgb("#6f8faf") == (111, 143, 175)
    assert _hex_to_rgb("6f8faf") == (111, 143, 175)
    assert _hex_to_rgb("#FFF") == (255, 255, 255)        # 단축형 확장
    assert _hex_to_rgb("#6f8fafcc") == (111, 143, 175)   # 8자리 → 알파 무시
    assert _hex_to_rgb("#xyz") is None
    assert _hex_to_rgb("#12345") is None                 # 길이 불일치
    assert _hex_to_rgb(None) is None


def test_apply_accent_best_of_n_promotes_best():
    without = _solid_b64((230, 230, 230))
    with_blue = _solid_b64((230, 230, 230), accent_patch=(111, 143, 175))
    reference = {
        "image_b64": without, "image_b64s": [without, with_blue],
        "source_url": "u0", "source_urls": ["u0", "u1"],
    }
    ai._apply_accent_best_of_n({"accent_keycap_color": "#6f8faf"}, reference)
    assert reference["image_b64"] == with_blue       # 액센트 충실한 컷으로 승격
    assert reference["source_url"] == "u1"
    assert reference["best_of_n"]["best_index"] == 1 and reference["best_of_n"]["count"] == 2


def test_apply_accent_best_of_n_noop_single_image():
    only = _solid_b64((230, 230, 230))
    reference = {"image_b64": only, "source_url": "u0"}  # image_b64s 없음(batch 1)
    ai._apply_accent_best_of_n({"accent_keycap_color": "#6f8faf"}, reference)
    assert "best_of_n" not in reference and reference["image_b64"] == only


def test_best_of_n_in_cache_key(monkeypatch):
    monkeypatch.setenv("COMFYUI_BEST_OF_N", "1")
    k1 = result_cache.make_image_cache_key("p", {}, 1024, 1024)
    monkeypatch.setenv("COMFYUI_BEST_OF_N", "4")
    k2 = result_cache.make_image_cache_key("p", {}, 1024, 1024)
    assert k1 != k2


# ── end_percent 노브(ControlNet 적용 구간) ───────────────────────────────────
def test_controlnet_end_percent_in_mapping_and_workflow(tmp_path, monkeypatch):
    mapping = ai._workflow_placeholder_mapping(
        _settings(comfyui_controlnet_end_percent=0.6), "kbd", 1024, 1024
    )
    assert mapping["{controlnet_end_percent}"] == 0.6

    payload = _payload_with_glb(tmp_path, monkeypatch)
    monkeypatch.setattr(
        ai, "get_settings",
        lambda: _settings(
            comfyui_workflows_dir=str(WF_DIR), comfyui_base_url="http://comfy",
            comfyui_controlnet_model="m.safetensors", comfyui_controlnet_strength=0.8,
            comfyui_controlnet_end_percent=0.6,
        ),
    )
    monkeypatch.setattr(ai, "_upload_controlnet_depth_to_comfyui", lambda p, s: "d.png")
    wf = ai._load_comfyui_workflow(payload, "kbd")
    assert wf["23"]["inputs"]["end_percent"] == 0.6   # <1.0 → 초기 스텝만
    assert wf["23"]["inputs"]["start_percent"] == 0.0


def test_end_percent_in_cache_key(monkeypatch):
    monkeypatch.setenv("COMFYUI_CONTROLNET_END_PERCENT", "1.0")
    k1 = result_cache.make_image_cache_key("p", {}, 1024, 1024)
    monkeypatch.setenv("COMFYUI_CONTROLNET_END_PERCENT", "0.6")
    k2 = result_cache.make_image_cache_key("p", {}, 1024, 1024)
    assert k1 != k2


# ── batch OOM 시 N 자동 하향 재시도 ───────────────────────────────────────────
def _err_status(msg):
    return {"status_str": "error", "messages": [["execution_error", {"exception_message": msg}]]}


def _record_with_batch(batch):
    wf = {"16": {"class_type": "EmptyLatentImage", "inputs": {"batch_size": batch, "width": 1024, "height": 1024}}}
    return {"prompt": [0, "pid", wf, {}, []]}


class _PromptResp:
    def __init__(self, captured):
        self._captured = captured

    def raise_for_status(self):
        pass

    def json(self):
        return {"prompt_id": "newpid"}


def test_is_oom_error_detects_cuda_oom():
    assert ai._is_oom_error(_err_status("CUDA out of memory. Tried to allocate 2.00 GiB")) is True
    assert ai._is_oom_error(_err_status("torch.cuda.OutOfMemoryError")) is True
    assert ai._is_oom_error(_err_status("some unrelated KeyError")) is False


def test_oom_retry_halves_batch_and_resubmits(monkeypatch):
    captured = {}

    def _fake_post(url, **kwargs):
        captured["batch"] = kwargs["json"]["prompt"]["16"]["inputs"]["batch_size"]
        captured["url"] = url
        return _PromptResp(captured)

    monkeypatch.setattr(ai.requests, "post", _fake_post)
    job = {"job_id": "j1"}
    ok = ai._maybe_retry_oom_lower_batch(
        job, _record_with_batch(4), _err_status("CUDA out of memory"),
        _settings(comfyui_base_url="http://comfy"),
    )
    assert ok is True
    assert captured["batch"] == 2                  # 4 → 2 (반감)
    assert job["status"] == "queued" and job["comfyui_prompt_id"] == "newpid"
    assert job["oom_retries"][-1] == {"from_batch": 4, "to_batch": 2, "at": job["oom_retries"][-1]["at"]}


def test_oom_retry_stops_at_batch_1(monkeypatch):
    monkeypatch.setattr(ai.requests, "post", lambda *a, **k: pytest.fail("should not resubmit at batch 1"))
    job = {"job_id": "j1"}
    ok = ai._maybe_retry_oom_lower_batch(
        job, _record_with_batch(1), _err_status("CUDA out of memory"),
        _settings(comfyui_base_url="http://comfy"),
    )
    assert ok is False  # batch 1 → 더 줄일 수 없음, 진짜 실패


def test_oom_retry_ignores_non_oom_error(monkeypatch):
    monkeypatch.setattr(ai.requests, "post", lambda *a, **k: pytest.fail("non-OOM must not resubmit"))
    job = {"job_id": "j1"}
    assert ai._maybe_retry_oom_lower_batch(
        job, _record_with_batch(4), _err_status("ValueError: bad node"),
        _settings(comfyui_base_url="http://comfy"),
    ) is False


# ── depth 생성기(헤드리스 렌더; OSMesa 없으면 skip) ───────────────────────────
# ── 색/액센트 그라운딩(depth가 grayscale라 색은 프롬프트가 책임) ─────────────
def test_image_prompt_grounds_exact_colours_early():
    payload = {
        "product_name": "Neo65", "layout": "65", "shot_type": "hero",
        "case_color": "#c8c1b2", "keycap_color": "#f4ead7", "accent_keycap_color": "#6f8faf",
    }
    prompt = ai.build_image_prompt(payload, {})
    assert "[exact colours]" in prompt
    # 말미 [color palette]보다 앞(고가중치)에서 정확 색을 단언해야 한다
    assert prompt.index("[exact colours]") < prompt.index("[color palette]")
    assert "accent keycaps" in prompt
    # 색 입력이 없으면 빈 절을 만들지 않는다(color_clause 가드)
    no_color = ai.build_image_prompt({"product_name": "Neo65", "layout": "65", "shot_type": "hero"}, {})
    assert "[exact colours]" not in no_color


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


def test_depth_png_camera_angle_changes_output(tmp_path):
    # 다른 카메라 각도(hero 높은 3/4 vs eye_level 낮은 수평)는 다른 depth를 내야 한다.
    # (단위테스트로 "각도가 맞는지"는 못 잡지만 "각도가 실제로 적용돼 달라지는지"는 잡는다.)
    trimesh = pytest.importorskip("trimesh")
    pytest.importorskip("pyrender")
    box = trimesh.creation.box(extents=[40.0, 10.0, 40.0])
    box.apply_translation([0.0, 5.0, 6.0])  # 카메라 타깃 부근(보이도록)
    glb = tmp_path / "box.glb"
    box.export(str(glb))

    high = build_desk_setup_depth_png(glb, size=256, azimuth_deg=26.0, elevation_deg=36.0, radius=95.0)
    if high is None:
        pytest.skip("headless GL(OSMesa) 미가용 환경")
    low = build_desk_setup_depth_png(glb, size=256, azimuth_deg=12.0, elevation_deg=18.0, radius=100.0)
    assert high[:8] == b"\x89PNG\r\n\x1a\n"
    assert low is not None and low != high          # 각도 분리 → depth 분리(캐시 키도 eye 기준)
    assert build_desk_setup_depth_png(glb, size=256) is not None  # 레거시 기본(각도 미지정)도 동작


def test_depth_upload_uses_per_shot_camera_and_unique_name(tmp_path, monkeypatch):
    # _upload_controlnet_depth_to_comfyui가 (1) shot_type별로 다른 카메라 kwargs를 넘기고
    # (2) 컷별로 유니크한 ComfyUI 파일명으로 올리는지(고정 파일명 overwrite 클로버 방지).
    payload = _payload_with_glb(tmp_path, monkeypatch)
    cam_calls: list[dict] = []
    uploaded_names: list[str] = []

    from backend import renderer

    def _fake_depth(_glb_path, **kwargs):
        cam_calls.append(kwargs)
        return b"depthpng"  # 같은 바이트라도 shot_type이 파일명을 갈라야 한다

    monkeypatch.setattr(renderer, "build_desk_setup_depth_png", _fake_depth)
    monkeypatch.setattr(ai, "_resize_reference_to_ratio", lambda png, p: png)

    class _Resp:
        def __init__(self, name):
            self._name = name

        def raise_for_status(self):
            pass

        def json(self):
            return {"name": self._name}

    def _fake_post(*_a, **kwargs):
        name = kwargs["files"]["image"][0]  # 업로드 파일명(=ComfyUI가 저장하는 이름)
        uploaded_names.append(name)
        return _Resp(name)

    monkeypatch.setattr(ai.requests, "post", _fake_post)
    settings = _settings(comfyui_base_url="http://comfy")

    hero_name = ai._upload_controlnet_depth_to_comfyui({**payload, "shot_type": "hero"}, settings)
    eye_name = ai._upload_controlnet_depth_to_comfyui({**payload, "shot_type": "eye_level"}, settings)

    assert cam_calls[0] == {"azimuth_deg": 26.0, "elevation_deg": 36.0, "radius": 95.0}
    assert cam_calls[1] == {"azimuth_deg": 12.0, "elevation_deg": 18.0, "radius": 100.0}
    assert cam_calls[0] != cam_calls[1]            # hero·eye_level 카메라 분리
    assert "hero" in hero_name and "eye_level" in eye_name
    assert hero_name != eye_name                   # 파일명 분리 → ComfyUI 클로버 방지(회귀 가드)
    assert uploaded_names == [hero_name, eye_name]  # 반환값 = 실제 업로드 파일명
