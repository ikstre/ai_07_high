from backend.ai import (
    _complete_copy_payload,
    _copy_request_timeout,
    _extract_json_block,
    _strip_reasoning,
    generate_ad_copy,
)
from backend.config import get_settings
from backend.llm_adapters import ChatCompletionAdapter


def _payload():
    return {
        "product_name": "테스트 65% 커스텀 키보드",
        "product_type": "커스텀 키보드",
        "layout": "65",
        "case_color": "#c8c1b2",
        "keycap_color": "#f4ead7",
        "accent_keycap_color": "#6f8faf",
        "case_finish": "anodized",
        "switch_stem": "silent_red",
        "switch_family": "mx",
        "keycap_profile": "cherry",
        "mount_type": "gasket_mount",
        "price": "189,000원",
        "target_channel": "인스타그램",
        "target_customer": "조용하고 정돈된 데스크 셋업을 원하는 직장인",
        "selling_point": "알루미늄 하우징, PBT 키캡, 조용한 리니어 스위치, 낮은 전고",
    }


def test_complete_copy_payload_pads_short_model_result():
    result = _complete_copy_payload(
        _payload(),
        {
            "provider": "local_llm",
            "headline": "책상 위 포인트",
            "subcopy": "짧음",
            "cta": "보기",
            "copies": ["PBT 키캡의 차분한 첫인상"],
            "spec_bullets": ["PBT 키캡"],
        },
    )

    assert len(result["copies"]) == 5
    assert len(result["spec_bullets"]) == 5
    assert len(result["subcopy"]) >= 35
    assert "65% 컴팩트 배열" in " ".join(result["copies"] + result["spec_bullets"])
    assert "silent red" in " ".join(result["copies"] + result["spec_bullets"])
    # 색상 hex(#c8c1b2 등)가 사람이 읽는 카피에 새어 들어가면 안 되고,
    # subcopy 폴백은 "…광고 카피" 같은 메타 묘사가 아니라 실제 카피 문장이어야 한다.
    blob = " ".join([result["subcopy"], *result["copies"], *result["spec_bullets"]])
    assert "#" not in blob
    assert "광고 카피" not in blob


def test_fallback_copy_returns_full_copy_set():
    result = generate_ad_copy(_payload(), provider_override="fallback", force_regen=True)

    assert result["provider"] == "fallback"
    assert len(result["copies"]) == 5
    assert len(result["spec_bullets"]) >= 4
    assert len(result["subcopy"]) > 35
    blob = " ".join([result["subcopy"], *result["copies"], *result["spec_bullets"]])
    assert "#" not in blob
    assert "광고 카피" not in blob


def test_strip_reasoning_drops_think_block_with_braces():
    # HyperCLOVA X SEED Think 계열은 <think> 안에서 추론하고 본문(JSON)을 뒤에 낸다.
    raw = '<think>플랜을 세운다 {중괄호 포함}</think>\n{"headline": "본문"}'
    stripped = _strip_reasoning(raw)
    assert "<think>" not in stripped
    assert "중괄호" not in stripped
    assert stripped.lstrip().startswith("{")
    # 닫는 태그 없이 잘린 reasoning도 본문 앞부분을 오염시키지 않게 제거.
    assert _strip_reasoning("<think>미완성 추론").strip() == ""


def test_extract_json_block_salvages_unquoted_hashtags():
    # 모델이 거의 맞는 JSON을 내되 해시태그 따옴표를 빠뜨려도 좋은 문구를 통째로 버리지 않는다.
    raw = (
        '{"headline": "퇴근길의 잔잔한 집중력", "subcopy": "알루미늄과 크림 베이지 키캡", '
        '"cta": "내 책상에 더하기", "copies": ["따뜻한 톤.", "조용한 스위치."], '
        '"hashtags": ["#미니멀데스크", "#조용한집중", #커스텀키캡, #65배열키보드], '
        '"spec_bullets": ["65% 배열", "PBT 키캡"]}'
    )
    parsed = _extract_json_block(raw)
    assert parsed is not None
    assert parsed["headline"] == "퇴근길의 잔잔한 집중력"
    assert parsed["copies"] == ["따뜻한 톤.", "조용한 스위치."]
    assert "#커스텀키캡" in parsed["hashtags"]
    assert "#65배열키보드" in parsed["hashtags"]
    assert parsed["spec_bullets"] == ["65% 배열", "PBT 키캡"]


def test_provider_specific_copy_timeout(monkeypatch):
    monkeypatch.setenv("AI_REQUEST_TIMEOUT_SECONDS", "45")
    monkeypatch.delenv("LLM_REQUEST_TIMEOUT_SECONDS", raising=False)
    monkeypatch.setenv("HYPERCLOVA_REQUEST_TIMEOUT_SECONDS", "900")
    monkeypatch.setenv("LOCAL_LLM_REQUEST_TIMEOUT_SECONDS", "300")
    monkeypatch.setenv("OPENAI_REQUEST_TIMEOUT_SECONDS", "45")
    get_settings.cache_clear()

    try:
        hyperclova = ChatCompletionAdapter(name="hyperclova_x", base_url="http://127.0.0.1:11501/v1", model="model")
        local = ChatCompletionAdapter(name="local_llm", base_url="http://127.0.0.1:11434/v1", model="model")
        openai = ChatCompletionAdapter(name="openai", base_url="http://example.test/v1", model="model")

        assert _copy_request_timeout(hyperclova) == 900
        assert _copy_request_timeout(local) == 300
        assert _copy_request_timeout(openai) == 45
        assert _copy_request_timeout(local, {"_copy_request_timeout_override": 25}) == 25
    finally:
        get_settings.cache_clear()
