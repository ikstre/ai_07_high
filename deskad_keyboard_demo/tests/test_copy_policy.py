from backend.copy_policy import apply_copy_policy


def _copy_result(**overrides):
    base = {
        "headline": "국내1위 완벽한 키보드",
        "subcopy": "최고의 타건감과 검증된 품질을 보장합니다",
        "cta": "지금 구매",
        "copies": ["초특가 구성", "치료 같은 편안함"],
        "hashtags": ["#Desk Setup", "키보드", "커스텀 키보드", "타건", "할인"],
        "spec_bullets": ["국내 최초 설계"],
    }
    base.update(overrides)
    return base


def test_replaces_forbidden_terms_and_reports_compact_spaced_term():
    output = apply_copy_policy({"target_channel": "인스타그램"}, _copy_result())

    assert "국내1위" not in output["headline"]
    assert "많이 찾는" in output["headline"]
    assert "완성도 높은" in output["headline"]
    assert "국내 1위" in output["policy"]["flagged_terms"]
    assert "완벽한" in output["policy"]["flagged_terms"]


def test_youtube_shorts_policy_limits_lengths_and_hashtags():
    output = apply_copy_policy(
        {"target_channel": "유튜브 쇼츠"},
        _copy_result(
            headline="짧은 영상에서도 바로 보이는 커스텀 키보드 데스크 셋업",
            subcopy="조용한 타건감과 크림 톤 키캡을 한 장면 안에 담은 쇼츠용 설명 문구입니다",
            cta="자세히 보러가기",
        ),
    )

    assert output["policy"]["channel"] == "유튜브 쇼츠"
    assert output["policy"]["headline_max"] == 26
    assert len(output["headline"]) <= 26
    assert len(output["subcopy"]) <= 64
    assert len(output["cta"]) <= 14
    assert output["hashtags"] == ["#DeskSetup", "#키보드", "#커스텀키보드"]


def test_channel_specific_zero_hashtag_limit():
    output = apply_copy_policy({"target_channel": "네이버 검색광고"}, _copy_result())

    assert output["policy"]["hashtag_limit"] == 0
    assert output["hashtags"] == []


def test_hashtags_keep_korean_english_and_numbers_only():
    output = apply_copy_policy(
        {"target_channel": "인스타그램"},
        _copy_result(hashtags=["#Desk Setup", "#키보드65", "#侘寂", "#desk_set"]),
    )

    assert output["hashtags"] == ["#DeskSetup", "#키보드65", "#desk_set"]


# ── 2026-06-11 QA: 광고 규제 우회 2건 ─────────────────────────────────────────
def test_hashtags_pass_through_forbidden_term_replacement():
    output = apply_copy_policy(
        {"target_channel": "인스타그램"},
        _copy_result(hashtags=["#최고", "#국내1위키보드", "#키보드"]),
    )
    assert "#최고" not in output["hashtags"]
    assert "#국내1위키보드" not in output["hashtags"]
    assert "#뛰어난" in output["hashtags"]
    assert "#많이찾는키보드" in output["hashtags"]
    assert "최고" in output["policy"]["flagged_terms"]
    assert "국내 1위" in output["policy"]["flagged_terms"]


def test_single_word_term_with_inner_spaces_is_replaced():
    output = apply_copy_policy(
        {"target_channel": "인스타그램"},
        _copy_result(copies=["최 고 의 타건감", "완 벽 한 마감"]),
    )
    joined = " | ".join(output["copies"])
    assert "최 고" not in joined
    assert "완 벽" not in joined
    assert "뛰어난" in joined
    assert "완성도 높은" in joined
