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
    assert ai._engine_image_backend({"engine": "hyperclova"}) == "comfyui"
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
