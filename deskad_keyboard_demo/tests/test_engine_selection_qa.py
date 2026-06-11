"""3개 평가 트랙(엔진) 선택 + 구도/CTA/비율 보정 회귀 가드.

키·네트워크 없이 결정적으로 검증 가능한 항목만 (실호출 품질은 별도).
"""
import base64
import io

from PIL import Image

from backend import ai
from backend.llm_adapters import _max_tokens_param


# ── OpenAI GPT-5 계열 토큰 파라미터 ────────────────────────────────────────
def test_gpt5_family_uses_completion_tokens_param():
    # GPT-5/o1·o3·o4 계열은 max_completion_tokens, 그 외는 max_tokens.
    assert _max_tokens_param("gpt-5.4-mini") == "max_completion_tokens"
    assert _max_tokens_param("gpt-5.4") == "max_completion_tokens"
    assert _max_tokens_param("o3-mini") == "max_completion_tokens"
    assert _max_tokens_param("gpt-4o-mini") == "max_tokens"
    assert _max_tokens_param("HCX-005") == "max_tokens"
    # 경로형(org/model)도 처리
    assert _max_tokens_param("openai/gpt-5.4") == "max_completion_tokens"
    assert _max_tokens_param("kakaocorp/kanana-2") == "max_tokens"


# ── 엔진 → provider / backend 매핑 ─────────────────────────────────────────
def test_engine_text_and_image_backend_mapping():
    assert ai._engine_text_provider({"engine": "openai"}) == "openai"
    assert ai._engine_text_provider({"engine": "hyperclova"}) == "hyperclova"
    assert ai._engine_text_provider({"engine": "local"}) == "local"
    # auto/미지정은 None → 서버 기본값(AI_PROVIDER) 사용
    assert ai._engine_text_provider({"engine": "auto"}) is None
    assert ai._engine_text_provider({}) is None

    assert ai._engine_image_backend({"engine": "openai"}) == "openai"
    assert ai._engine_image_backend({"engine": "hyperclova"}) == "hyperclova"
    assert ai._engine_image_backend({"engine": "local"}) == "comfyui"
    assert ai._engine_image_backend({"engine": "auto"}) is None


def test_openai_tier_model_mapping():
    assert ai._openai_text_model({"engine_model_tier": "general"}) == "gpt-5.4-mini"
    assert ai._openai_text_model({"engine_model_tier": "performance"}) == "gpt-5.4"
    assert ai._openai_image_model({"engine_model_tier": "general"}) == "gpt-image-1-mini"
    assert ai._openai_image_model({"engine_model_tier": "performance"}) == "gpt-image-2"
    # 잘못된 등급은 general로 폴백
    assert ai._openai_text_model({"engine_model_tier": "bogus"}) == "gpt-5.4-mini"


# ── 구도 무결성: 셋업 인벤토리 + 강화 네거티브 ────────────────────────────
def test_scene_inventory_lists_selected_assets_once():
    clause = ai._scene_inventory_clause({"assets": ["mouse", "monitor", "plant"]})
    assert "one wireless mouse" in clause
    assert "one computer monitor" in clause
    assert "one small potted plant" in clause
    # 중복/추가 금지 신호
    assert "never duplicate the mouse" in clause


def test_scene_inventory_dedupes_and_ignores_base_items():
    clause = ai._scene_inventory_clause({"assets": ["mouse", "mouse", "keyboard", "desk"]})
    assert clause.count("one wireless mouse") == 1


def test_image_prompt_has_inventory_and_composition_negatives():
    prompt = ai.build_image_prompt(
        {"assets": ["mouse", "monitor", "plant"], "image_ratio": "1:1", "target_channel": "인스타그램"},
        {"headline": "x"},
    )
    assert "[scene inventory]" in prompt
    assert "no two mice" in prompt
    assert "cables plugged into plants" in prompt


def test_macro_shot_skips_inventory():
    # 매크로(키보드 클로즈업)는 셋업 인벤토리를 넣지 않는다.
    prompt = ai.build_image_prompt(
        {"assets": ["mouse"], "image_ratio": "1:1", "shot_type": "detail_macro"},
        {"headline": "x"},
    )
    assert "[scene inventory]" not in prompt


# ── CTA/minimal: CTA가 항상 보이고 고대비여야 한다 ────────────────────────
def test_minimal_card_always_renders_cta_text():
    svg = ai._minimal_card_svg(
        {"image_ratio": "1:1", "theme": "minimal", "product_name": "제품", "price": "10000원"},
        {"headline": "헤드라인", "subcopy": "서브", "cta": "지금 구매하기", "copies": ["a"]},
        None,
    )
    assert "지금 구매하기" in svg


def test_minimal_card_caps_headline_to_two_lines():
    long_headline = "아주 긴 헤드라인 문구 한국어로 두 줄을 훌쩍 넘기도록 충분히 길게 작성한 제목"
    svg = ai._minimal_card_svg(
        {"image_ratio": "1:1", "theme": "minimal", "product_name": "제품", "price": "10000원"},
        {"headline": long_headline, "subcopy": "서브", "cta": "구매", "copies": ["a"]},
        None,
    )
    # headline 글자 묶음(font-weight 800, font-size 48)은 최대 2줄
    assert svg.count('font-size="48" font-weight="800"') <= 2


def test_cta_contrast_colors_are_readable():
    # minimal 팔레트: 흐린 accent 위 크림 글자(대비 부족) → 잉크 텍스트로 강제
    text_fill, button_fill = ai._contrast_button_colors("#2f3438", "#8aa0a8", "#f5f2ea")
    assert ai._contrast_ratio(ai._hex_to_rgb(text_fill), ai._hex_to_rgb(button_fill)) >= 3.0
    # gaming 팔레트: 진한 purple accent 위 흰 글자
    text_fill_g, button_fill_g = ai._contrast_button_colors("#f8fafc", "#7c3aed", "#10131a")
    assert ai._contrast_ratio(ai._hex_to_rgb(text_fill_g), ai._hex_to_rgb(button_fill_g)) >= 4.5


# ── img2img 비율 보정 ─────────────────────────────────────────────────────
def _png_bytes(w: int, h: int) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (w, h), (120, 120, 120)).save(out, format="PNG")
    return out.getvalue()


def test_resize_reference_matches_requested_ratio():
    src = _png_bytes(1280, 848)  # 레퍼런스 원본 비율(가로)
    for ratio, expected in [("1:1", (1024, 1024)), ("4:5", (1024, 1280)), ("16:9", (1344, 768))]:
        resized = ai._resize_reference_to_ratio(src, {"image_ratio": ratio})
        with Image.open(io.BytesIO(resized)) as img:
            assert img.size == expected, f"{ratio} → {img.size}"


def test_resize_reference_returns_none_on_bad_bytes():
    assert ai._resize_reference_to_ratio(b"not-an-image", {"image_ratio": "1:1"}) is None


# ── HyperCLOVA 이미지 백엔드 ──────────────────────────────────────────────
class _HyperImageSettings:
    request_timeout_seconds = 1
    openai_api_key = "sk-test"
    openai_base_url = "https://api.openai.com/v1"
    openai_text_model = "gpt-4o-mini"
    openai_image_model = ""
    local_llm_base_url = "http://127.0.0.1:11434/v1"
    local_llm_model = "qwen2.5:14b"
    hyperclova_base_url = ""
    hyperclova_api_key = ""
    hyperclova_model = ""
    hyperclova_use_direct = False
    hyperclova_apigw_key = ""
    hyperclova_vision_base_url = ""
    hyperclova_vision_api_key = ""
    hyperclova_vision_model = ""
    hyperclova_image_base_url = "http://127.0.0.1:8000/b/v1"
    hyperclova_image_api_key = ""
    hyperclova_image_model = "track_b_model"
    hyperclova_image_mode = "omniserve_chat"
    kanana_base_url = ""
    kanana_api_key = ""
    kanana_model = ""
    midm_base_url = ""
    midm_api_key = ""
    midm_model = ""
    comfyui_base_url = "http://127.0.0.1:8188"
    flux_model_variant = "flux1-schnell-fp8"

    @property
    def effective_hyperclova_vision_base_url(self):
        return self.hyperclova_vision_base_url or self.hyperclova_image_base_url

    @property
    def effective_hyperclova_vision_api_key(self):
        return self.hyperclova_vision_api_key or self.hyperclova_image_api_key

    @property
    def effective_hyperclova_vision_model(self):
        return self.hyperclova_vision_model or self.hyperclova_image_model

    @property
    def has_hyperclova_vision(self):
        return bool(self.effective_hyperclova_vision_base_url and self.effective_hyperclova_vision_model)

    @property
    def effective_hyperclova_image_base_url(self):
        return self.hyperclova_image_base_url

    @property
    def effective_hyperclova_image_api_key(self):
        return self.hyperclova_image_api_key

    @property
    def effective_hyperclova_image_model(self):
        return self.hyperclova_image_model

    @property
    def has_hyperclova_image(self):
        return bool(self.effective_hyperclova_image_base_url and self.effective_hyperclova_image_model)

    @property
    def has_comfyui(self):
        return bool(self.comfyui_base_url)


def test_hyperclova_openai_images_reference_uses_images_generations(monkeypatch):
    settings = _HyperImageSettings()
    settings.hyperclova_image_mode = "openai_images"
    seen = {}

    def fake_request(url, *, headers, payload, timeout):
        seen.update({"url": url, "headers": headers, "payload": payload, "timeout": timeout})
        return {"data": [{"b64_json": "QUJD"}]}

    monkeypatch.setattr(ai, "get_settings", lambda: settings)
    monkeypatch.setattr(ai, "_request_json", fake_request)

    result = ai.generate_hyperclova_image_reference({"image_ratio": "1:1"}, "desk setup prompt")

    assert result["provider"] == "hyperclova_image"
    assert result["mode"] == "openai_images"
    assert result["has_image"] is True
    assert result["image_b64"] == "QUJD"
    assert seen["url"] == "http://127.0.0.1:8000/b/v1/images/generations"
    assert seen["payload"]["model"] == "track_b_model"
    assert "custom keyboard" in seen["payload"]["prompt"]
    assert seen["payload"]["prompt"] != "desk setup prompt"


def test_hyperclova_omniserve_chat_reference_parses_tool_image(monkeypatch):
    settings = _HyperImageSettings()
    seen = {}

    def fake_request(url, *, headers, payload, timeout):
        seen.update({"url": url, "payload": payload})
        return {
            "choices": [
                {
                    "message": {
                        "tool_calls": [
                            {
                                "function": {
                                    "arguments": '{"discrete_image_token": "data:image/png;base64,QUJD"}'
                                }
                            }
                        ]
                    }
                }
            ]
        }

    monkeypatch.setattr(ai, "get_settings", lambda: settings)
    monkeypatch.setattr(ai, "_request_json", fake_request)

    result = ai.generate_hyperclova_image_reference({"image_ratio": "1:1"}, "draw a keyboard")

    assert result["provider"] == "hyperclova_image"
    assert result["mode"] == "omniserve_chat"
    assert result["has_image"] is True
    assert result["image_b64"] == "QUJD"
    assert seen["url"] == "http://127.0.0.1:8000/b/v1/chat/completions"
    assert seen["payload"]["tools"][0]["function"]["name"] == "t2i_model_generation"
    assert "custom keyboard" in seen["payload"]["messages"][-1]["content"]
    assert seen["payload"]["messages"][-1]["content"] != "draw a keyboard"


def test_hyperclova_image_payload_uses_compact_native_prompt(monkeypatch):
    long_comfyui_prompt = "[subject] " + ("very long structured comfyui control prompt " * 100)

    payload = ai._build_hyperclova_openai_images_payload(
        {
            "product_name": "테스트 키보드",
            "layout": "65",
            "assets": ["mouse", "monitor"],
            "theme": "minimal",
            "ad_tone": "감성형",
            "image_ratio": "1:1",
            "shot_type": "hero",
            "case_color": "#c8c1b2",
            "keycap_color": "#f4ead7",
            "accent_keycap_color": "#6f8faf",
        },
        long_comfyui_prompt,
    )

    assert payload["prompt"] != long_comfyui_prompt
    assert len(payload["prompt"]) <= 1400
    assert "[subject]" not in payload["prompt"]
    assert "테스트 키보드" in payload["prompt"]
    assert "Aspect ratio: 1:1" in payload["prompt"]
    assert "no letters, no numbers" in payload["prompt"]


def test_hyperclova_image_timeout_ignores_generic_text_timeout(monkeypatch):
    monkeypatch.setenv("AI_REQUEST_TIMEOUT_SECONDS", "900")
    monkeypatch.delenv("HYPERCLOVA_IMAGE_TIMEOUT_SECONDS", raising=False)

    assert ai._hyperclova_image_timeout_seconds() == 420

    monkeypatch.setenv("HYPERCLOVA_IMAGE_TIMEOUT_SECONDS", "300")
    assert ai._hyperclova_image_timeout_seconds() == 300


def test_hyperclova_text_only_model_does_not_fallback_to_image_config(monkeypatch):
    settings = _HyperImageSettings()
    settings.hyperclova_image_base_url = ""
    settings.hyperclova_image_model = ""
    settings.hyperclova_base_url = "http://127.0.0.1:11434/v1"
    settings.hyperclova_model = "hyperclova-omni-8b-text:Q4_K_M"

    monkeypatch.setattr(ai, "get_settings", lambda: settings)

    result = ai.generate_hyperclova_image_reference({"image_ratio": "1:1"}, "draw")

    assert result["provider"] == "hyperclova_image"
    assert result["has_image"] is False
    assert result["not_configured"] is True
    assert "재사용하지 않습니다" in result["error"]


def test_hyperclova_vision_requires_explicit_vision_endpoint(monkeypatch):
    settings = _HyperImageSettings()
    settings.hyperclova_base_url = "http://127.0.0.1:11434/v1"
    settings.hyperclova_model = "hyperclova-omni-8b-text:Q4_K_M"
    settings.hyperclova_image_base_url = ""
    settings.hyperclova_image_model = ""
    settings.hyperclova_vision_base_url = ""
    settings.hyperclova_vision_model = ""
    monkeypatch.setattr(ai, "get_settings", lambda: settings)
    monkeypatch.setenv("HYPERCLOVA_SUPPORTS_VISION", "true")

    adapter = ai._copy_adapter("hyperclova", {"reference_image_b64": "QUJD"})

    assert adapter.name == "hyperclova_x"
    assert adapter.base_url == "http://127.0.0.1:11434/v1"
    assert adapter.supports_vision is False


def test_hyperclova_vision_uses_explicit_vision_endpoint(monkeypatch):
    settings = _HyperImageSettings()
    settings.hyperclova_base_url = "http://127.0.0.1:11434/v1"
    settings.hyperclova_model = "hyperclova-omni-8b-text:Q4_K_M"
    settings.hyperclova_vision_base_url = "http://127.0.0.1:8000/b/v1"
    settings.hyperclova_vision_model = "track_b_model"
    settings.hyperclova_image_base_url = ""
    settings.hyperclova_image_model = ""
    monkeypatch.setattr(ai, "get_settings", lambda: settings)
    monkeypatch.setenv("HYPERCLOVA_SUPPORTS_VISION", "true")

    adapter = ai._copy_adapter("hyperclova", {"reference_image_b64": "QUJD"})

    assert adapter.name == "hyperclova_x_vision"
    assert adapter.base_url == "http://127.0.0.1:8000/b/v1"
    assert adapter.model == "track_b_model"
    assert adapter.supports_vision is True


def test_generation_tracks_expose_three_user_facing_routes(monkeypatch):
    settings = _HyperImageSettings()
    settings.hyperclova_base_url = "http://127.0.0.1:11434/v1"
    settings.hyperclova_model = "hyperclova-omni-8b-text:Q4_K_M"
    settings.hyperclova_image_base_url = ""
    settings.hyperclova_image_model = ""
    monkeypatch.setattr(ai, "get_settings", lambda: settings)

    tracks = {track["id"]: track for track in ai.generation_tracks()}

    assert set(tracks) == {"openai", "hyperclova", "local"}
    assert tracks["openai"]["text_provider"] == "openai"
    assert tracks["openai"]["image_backend"] == "openai"
    assert tracks["hyperclova"]["text_provider"] == "hyperclova"
    assert tracks["hyperclova"]["image_backend"] == "hyperclova"
    assert tracks["hyperclova"]["image_configured"] is False
    assert tracks["local"]["text_provider"] == "local"
    assert tracks["local"]["image_backend"] == "comfyui"
    assert tracks["local"]["image_configured"] is True
    assert [item["id"] for item in tracks["local"]["text_candidates"]] == ["local", "kanana", "midm"]
