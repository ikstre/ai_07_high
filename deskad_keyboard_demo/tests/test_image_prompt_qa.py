"""PR #11 프롬프트튜닝 QA 배터리 — build_image_prompt 구도/장면/톤/엣지 회귀 가드.

키 없이 결정적으로 검증 가능한 항목 전부. 실호출(ComfyUI/LLM) 생성 품질은 별도(Phase 2).
"""
from backend.ai import (
    build_image_prompt,
    _COMPOSITION_TEMPLATES,
    _DEFAULT_SHOT_BY_CHANNEL,
    _COLOR_TEMP_BY_TONE,
    _IMAGE_DIRECTION_BY_TONE,
)
from ui_steps import TARGET_CHANNEL_OPTIONS, AD_TONE_OPTIONS


_BASE = {
    "product_name": "크림 베이지 65% 키보드",
    "ad_tone": "감성형",
    "layout": "65",
    "assets": ["keyboard", "deskmat", "monitor"],
}


def _prompt(**over):
    payload = dict(_BASE)
    payload.update(over)
    return build_image_prompt(payload, {"headline": "조용한 타건감"})


# ── Fix 1: 채널 기본 구도 매핑 (조용한 폴백 0건) ────────────────────────────
def test_every_ui_channel_has_explicit_default_shot():
    """UI에 노출되는 8개 채널 전부 명시 매핑 — 누락 시 조용히 hero로 빠지는 회귀 차단."""
    missing = [c for c in TARGET_CHANNEL_OPTIONS if c not in _DEFAULT_SHOT_BY_CHANNEL]
    assert missing == [], f"기본 구도 매핑 누락 채널: {missing}"


def test_channel_default_keys_point_to_real_templates():
    for channel, shot in _DEFAULT_SHOT_BY_CHANNEL.items():
        assert shot in _COMPOSITION_TEMPLATES, f"{channel} → 없는 구도 {shot}"


def test_banner_channel_uses_wide_scene():
    """버그였던 '배너 광고' → wide_scene 정상 적용 확인."""
    prompt = _prompt(target_channel="배너 광고", shot_type="")
    assert _COMPOSITION_TEMPLATES["wide_scene"]["angle"] in prompt


def test_instagram_default_uses_top_down():
    prompt = _prompt(target_channel="인스타그램", shot_type="")
    assert _COMPOSITION_TEMPLATES["top_down"]["angle"] in prompt


# ── Fix 2: shot_type 배선 (★ main 회귀 문서화) ─────────────────────────────
def test_detail_macro_only_reachable_via_explicit_shot_type():
    """detail_macro는 어떤 채널 기본값으로도 안 나온다.

    PR #11에서 ui_steps.SHOT_TYPE_OPTIONS + 페이로드로 shot_type을 배선했으나,
    모듈화/UI 재설계 후 main에서 UI 선택이 사라짐 → detail_macro가 다시 죽은 구도.
    이 테스트는 그 회귀의 구체적 결과를 못박는다(백엔드 계약 자체는 온전).
    """
    channel_defaults = set(_DEFAULT_SHOT_BY_CHANNEL.values())
    assert "detail_macro" not in channel_defaults, "채널 기본만으론 detail_macro 도달 불가"
    # 백엔드는 명시 지정 시 여전히 정상 — 즉 빠진 건 UI 배선뿐.
    assert _COMPOSITION_TEMPLATES["detail_macro"]["angle"] in _prompt(shot_type="detail_macro")


def test_explicit_shot_type_overrides_channel_default():
    """인스타그램(기본 top_down)이라도 shot_type 지정 시 그 구도가 우선."""
    prompt = _prompt(target_channel="인스타그램", shot_type="hero")
    assert _COMPOSITION_TEMPLATES["hero"]["angle"] in prompt
    assert _COMPOSITION_TEMPLATES["top_down"]["angle"] not in prompt


def test_all_five_shot_types_reachable():
    for shot, tpl in _COMPOSITION_TEMPLATES.items():
        prompt = _prompt(shot_type=shot)
        assert tpl["angle"] in prompt, f"{shot} 구도 미반영"
        assert tpl["lens"] in prompt, f"{shot} 렌즈 미반영"


# ── 구도-장면 일관성 (모순 제거) ───────────────────────────────────────────
def test_macro_scene_excludes_desk_and_room():
    prompt = _prompt(shot_type="detail_macro")
    assert "no full desk" in prompt
    assert "full deskterior scene" not in prompt


def test_room_scene_includes_full_setup():
    prompt = _prompt(shot_type="wide_scene")
    assert "full deskterior scene" in prompt


# ── 톤 조명 ↔ 색온도 모순 0건 ──────────────────────────────────────────────
def test_tone_lighting_and_color_temp_both_applied():
    for tone in AD_TONE_OPTIONS:
        prompt = _prompt(ad_tone=tone)
        assert _IMAGE_DIRECTION_BY_TONE[tone] in prompt, f"{tone} 조명 누락"
        assert _COLOR_TEMP_BY_TONE[tone] in prompt, f"{tone} 색온도 누락"


def test_warm_tone_has_warm_temperature():
    """감성형: 따뜻한 조명 + 따뜻한 색온도 — warm 골든아워에 차가운 색온도 모순 없는지."""
    prompt = _prompt(ad_tone="감성형")
    assert "warm" in _IMAGE_DIRECTION_BY_TONE["감성형"]
    assert "warm 2700K" in prompt


# ── 공통 가드 상시 존재 ────────────────────────────────────────────────────
def test_core_guards_always_present():
    prompt = _prompt(shot_type="hero")
    for tag in ("[keyboard fidelity]", "[text policy]", "[negative]", "white balance", "[format]"):
        assert tag in prompt, f"가드 누락: {tag}"


def test_headline_not_baked_into_image():
    """헤드라인은 포스터 레이어에서 오버레이 — 이미지엔 광고문구를 굽지 않는다."""
    prompt = build_image_prompt(dict(_BASE), {"headline": "단 하나의 타건감"})
    assert "단 하나의 타건감" not in prompt


def test_reference_adherence_branch():
    with_ref = _prompt(reference_asset_path="renders/kbd_65.png")
    assert "reference adherence" in with_ref
    assert "follow the provided 3D reference" in with_ref

    without_ref = _prompt()
    assert "reference adherence" not in without_ref
    assert "[reference]" in without_ref


# ── 엣지 케이스: 예외 0 + 정상 폴백 ────────────────────────────────────────
def test_empty_payload_does_not_crash():
    out = build_image_prompt({}, {})
    assert isinstance(out, str) and len(out) > 0


def test_unknown_tone_falls_back_to_default_color_temp():
    prompt = _prompt(ad_tone="존재하지않는톤")
    assert "standard 5500K daylight white balance" in prompt


def test_invalid_shot_type_falls_back_to_channel_default():
    prompt = _prompt(target_channel="배너 광고", shot_type="bogus")
    assert _COMPOSITION_TEMPLATES["wide_scene"]["angle"] in prompt


def test_unknown_channel_falls_back_to_hero():
    prompt = _prompt(target_channel="틱톡", shot_type="")
    assert _COMPOSITION_TEMPLATES["hero"]["angle"] in prompt


def test_broken_hex_color_does_not_crash():
    out = _prompt(case_color="#ZZZ", keycap_color="not-a-color")
    assert isinstance(out, str) and len(out) > 0


# ── HyperCLOVA native image compact prompt (2026-06-11 텍스트 구워짐 회귀) ─────
def _hyperclova_prompt(**over):
    from backend.ai import _hyperclova_native_image_prompt

    payload = dict(_BASE)
    payload.update(over)
    return _hyperclova_native_image_prompt(payload, "fallback prompt")


def test_hyperclova_prompt_has_no_typography_guard():
    prompt = _hyperclova_prompt()
    assert "no letters" in prompt
    assert "no numbers" in prompt
    assert "no logos" in prompt


def test_hyperclova_prompt_does_not_ask_for_text_anywhere():
    # "readable keycap legends"/"overlay text"는 no-typography 지시와 모순되어
    # 이미지에 글자가 구워지는 원인이 됐다.
    prompt = _hyperclova_prompt().lower()
    assert "legend" not in prompt
    assert "overlay text" not in prompt
    assert "headline" not in prompt


def test_hyperclova_prompt_stays_compact():
    prompt = _hyperclova_prompt(extra_request="따뜻한 분위기로")
    assert len(prompt) <= 1400


def test_hyperclova_prompt_strips_hex_codes_from_colors():
    prompt = _hyperclova_prompt(case_color="#F5F0E6", keycap_color="#EAE3D2")
    assert "#f5f0e6" not in prompt.lower()
    assert "#eae3d2" not in prompt.lower()
    assert "case" in prompt  # 색 이름 자체는 유지
