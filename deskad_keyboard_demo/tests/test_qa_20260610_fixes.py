"""2026-06-10 main QA(7c74d06) 지적사항 회귀 가드.

QA 권고 통합 테스트 3종(①구도 payload→flux_img2img 선택 ②캐시 키의 레퍼런스 반응
③denoise 범위 클램프)과 2차 보강 결함(GPT-5 temperature, o-시리즈 prefix 오탐,
구도맵 vision 누수, OpenAI 텍스트 모델 env 우선순위, shot_type 입력 배선)을 잠근다.
"""
import pytest
from pydantic import ValidationError

from backend import ai, llm_adapters
from backend.config import _float_env
from backend.llm_adapters import ChatCompletionAdapter, _is_reasoning_model, _max_tokens_param
from backend.result_cache import make_image_cache_key
from backend.schemas import AdContentRequest


# ── QA #1: 레퍼런스 존재 시 flux_img2img가 txt2img 후보보다 선행 ───────────
def test_composition_reference_routes_to_img2img_workflow():
    payload = {
        "reference_image_b64": "QUJD",
        "reference_is_composition": True,
        "poster_template": "minimal_card",
        "theme": "pastel",
    }
    names = ai._candidate_workflow_names(payload)
    assert "flux_img2img" in names
    # situational(flux_<템플릿/테마>)·default(txt2img)보다 앞에 있어야 한다.
    assert names.index("flux_img2img") < names.index("flux_minimal_card")


def test_reference_asset_only_payload_also_routes_to_img2img(monkeypatch):
    monkeypatch.setattr(ai, "_reference_image_b64", lambda payload: "QUJD")
    names = ai._candidate_workflow_names({"poster_template": "minimal_card"})
    assert names[0] == "flux_img2img"


def test_no_reference_keeps_txt2img_candidates():
    names = ai._candidate_workflow_names({"poster_template": "minimal_card"})
    assert "flux_img2img" not in names


def test_explicit_workflow_still_wins_over_reference_routing():
    payload = {"image_workflow": "flux_custom", "reference_image_b64": "QUJD"}
    names = ai._candidate_workflow_names(payload)
    assert names[0] == "flux_custom"
    assert names[1] == "flux_img2img"


# ── QA #2: 이미지 캐시 키가 레퍼런스·구도 플래그·denoise에 반응 ────────────
def test_image_cache_key_varies_with_reference_image():
    base = {"image_model_backend": "comfyui"}
    key_a = make_image_cache_key("prompt", {**base, "reference_image_b64": "AAAA"}, 1024, 1024)
    key_b = make_image_cache_key("prompt", {**base, "reference_image_b64": "BBBB"}, 1024, 1024)
    key_a2 = make_image_cache_key("prompt", {**base, "reference_image_b64": "AAAA"}, 1024, 1024)
    assert key_a != key_b  # 다른 책상 배치 → 다른 캐시 항목
    assert key_a == key_a2  # 같은 입력은 안정적으로 같은 키


def test_image_cache_key_varies_with_composition_flag_and_denoise(monkeypatch):
    payload = {"reference_image_b64": "AAAA"}
    key_plain = make_image_cache_key("prompt", payload, 1024, 1024)
    key_comp = make_image_cache_key("prompt", {**payload, "reference_is_composition": True}, 1024, 1024)
    assert key_plain != key_comp

    monkeypatch.setenv("COMFYUI_IMG2IMG_DENOISE", "0.42")
    key_denoise = make_image_cache_key("prompt", payload, 1024, 1024)
    assert key_denoise != key_plain


# ── QA #3: denoise [0,1] 클램프 ────────────────────────────────────────────
def test_float_env_clamps_out_of_range_values(monkeypatch):
    monkeypatch.setenv("QA_DENOISE_TEST", "9")
    assert _float_env("QA_DENOISE_TEST", 0.65, lo=0.0, hi=1.0) == 1.0
    monkeypatch.setenv("QA_DENOISE_TEST", "-3")
    assert _float_env("QA_DENOISE_TEST", 0.65, lo=0.0, hi=1.0) == 0.0
    monkeypatch.setenv("QA_DENOISE_TEST", "0.7")
    assert _float_env("QA_DENOISE_TEST", 0.65, lo=0.0, hi=1.0) == 0.7
    monkeypatch.setenv("QA_DENOISE_TEST", "not-a-float")
    assert _float_env("QA_DENOISE_TEST", 0.65, lo=0.0, hi=1.0) == 0.65


# ── QA #4: OPENAI_TEXT_MODEL env가 tier 하드코딩보다 우선 ──────────────────
def test_openai_text_model_env_overrides_tier_default(monkeypatch):
    monkeypatch.setenv("OPENAI_TEXT_MODEL", "my-org-model")
    assert ai._openai_text_model({"engine_model_tier": "general"}) == "my-org-model"
    # tier별 env는 공통 env보다도 우선
    monkeypatch.setenv("OPENAI_TEXT_MODEL_GENERAL", "tier-model")
    assert ai._openai_text_model({"engine_model_tier": "general"}) == "tier-model"


# ── QA #5: shot_type 입력 배선 ─────────────────────────────────────────────
def test_ad_content_request_accepts_shot_type():
    request = AdContentRequest(shot_type="detail_macro")
    assert ai._resolve_shot_type(request.model_dump()) == "detail_macro"


def test_ad_content_request_rejects_unknown_shot_type():
    with pytest.raises(ValidationError):
        AdContentRequest(shot_type="dutch_angle")


# ── QA §10: GPT-5/o-시리즈는 temperature 미전송 ────────────────────────────
def _capture_body(monkeypatch):
    seen = {}

    class _Resp:
        @staticmethod
        def json():
            return {"choices": [{"message": {"content": "ok"}}]}

    def fake_post(url, *, headers, json, timeout, provider):
        seen.update(json)
        return _Resp()

    monkeypatch.setattr(llm_adapters, "_post_with_retry", fake_post)
    return seen


def test_gpt5_request_omits_temperature(monkeypatch):
    seen = _capture_body(monkeypatch)
    adapter = ChatCompletionAdapter(name="openai", base_url="https://api.openai.com/v1", model="gpt-5.4-mini")
    adapter.request(system_prompt="s", user_prompt="u", timeout=5, temperature=0.45)
    assert "temperature" not in seen
    assert "max_completion_tokens" in seen and "max_tokens" not in seen


def test_non_reasoning_request_keeps_temperature(monkeypatch):
    seen = _capture_body(monkeypatch)
    adapter = ChatCompletionAdapter(name="local", base_url="http://127.0.0.1:11434/v1", model="qwen2.5:14b")
    adapter.request(system_prompt="s", user_prompt="u", timeout=5, temperature=0.45)
    assert seen["temperature"] == 0.45
    assert "max_tokens" in seen


# ── QA §10: o1/o3/o4 bare prefix 오탐 ──────────────────────────────────────
def test_o_series_prefix_no_longer_matches_lookalike_local_models():
    assert _max_tokens_param("o3-community-7b") == "max_tokens"
    assert _max_tokens_param("o4ka-chat") == "max_tokens"
    # 실제 o-시리즈와 날짜 suffix는 여전히 매칭
    assert _max_tokens_param("o1") == "max_completion_tokens"
    assert _max_tokens_param("o3-mini") == "max_completion_tokens"
    assert _max_tokens_param("o1-2024-12-17") == "max_completion_tokens"
    assert _is_reasoning_model("openai/gpt-5.4")


# ── QA §10: 셋업 구도맵은 카피 vision 경로에 첨부 금지 ─────────────────────
def test_composition_map_excluded_from_vision_copy_path():
    composition_payload = {"reference_image_b64": "QUJD", "reference_is_composition": True}
    assert ai._vision_copy_reference_b64(composition_payload) is None
    # 제품 사진(구도맵 아님)은 그대로 첨부
    assert ai._vision_copy_reference_b64({"reference_image_b64": "QUJD"}) == "QUJD"
    # 멀티모달 content 생성 경로에서도 구도맵은 text-only로 남는다
    content = ai._user_content_with_image("text", composition_payload)
    assert content == "text"
