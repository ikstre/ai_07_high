from __future__ import annotations

import re


GLOBAL_REPLACEMENTS = {
    "최저가": "합리적인 가격",
    "국내 1위": "많이 찾는",
    "업계 1위": "많이 찾는",
    "1위": "인기",
    "완벽한": "완성도 높은",
    "완벽하게": "완성도 있게",
    "무조건": "쉽게",
    "100%": "",
    "절대": "",
}

CHANNEL_POLICY = {
    "인스타그램": {"headline_max": 22, "subcopy_max": 42, "cta_max": 12, "hashtag_limit": 6},
    "스마트스토어": {"headline_max": 24, "subcopy_max": 45, "cta_max": 12, "hashtag_limit": 4},
    "상세페이지": {"headline_max": 28, "subcopy_max": 55, "cta_max": 14, "hashtag_limit": 3},
    "쿠팡 썸네일": {"headline_max": 18, "subcopy_max": 32, "cta_max": 10, "hashtag_limit": 0},
    "배너 광고": {"headline_max": 16, "subcopy_max": 30, "cta_max": 8, "hashtag_limit": 0},
}

DEFAULT_POLICY = {"headline_max": 22, "subcopy_max": 42, "cta_max": 12, "hashtag_limit": 5}


def _compact_spaces(text: str) -> str:
    return re.sub(r"\s{2,}", " ", text).strip()


def _sanitize_text(text: object, flagged_terms: set[str]) -> str:
    value = str(text or "")
    for term, replacement in GLOBAL_REPLACEMENTS.items():
        if term in value:
            flagged_terms.add(term)
            value = value.replace(term, replacement)
    return _compact_spaces(value)


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 1)].rstrip() + "…"


def _sanitize_hashtag(value: object) -> str:
    tag = str(value or "").strip()
    if not tag:
        return ""
    tag = "#" + tag.lstrip("#")
    return re.sub(r"\s+", "", tag)


def apply_copy_policy(payload: dict, result: dict) -> dict:
    channel = payload.get("target_channel") or "인스타그램"
    policy = CHANNEL_POLICY.get(channel, DEFAULT_POLICY)
    flagged_terms: set[str] = set()
    output = dict(result)

    output["headline"] = _truncate(_sanitize_text(output.get("headline", ""), flagged_terms), policy["headline_max"])
    output["subcopy"] = _truncate(_sanitize_text(output.get("subcopy", ""), flagged_terms), policy["subcopy_max"])
    output["cta"] = _truncate(_sanitize_text(output.get("cta", ""), flagged_terms), policy["cta_max"])

    copies = [_sanitize_text(copy, flagged_terms) for copy in output.get("copies", [])]
    output["copies"] = [copy for copy in copies if copy][:5]

    spec_bullets = [_sanitize_text(bullet, flagged_terms) for bullet in output.get("spec_bullets", [])]
    output["spec_bullets"] = [bullet for bullet in spec_bullets if bullet][:5]

    hashtag_limit = int(policy["hashtag_limit"])
    hashtags = [_sanitize_hashtag(tag) for tag in output.get("hashtags", [])]
    output["hashtags"] = [tag for tag in hashtags if tag][:hashtag_limit]

    output["policy"] = {
        "channel": channel,
        "headline_max": policy["headline_max"],
        "subcopy_max": policy["subcopy_max"],
        "cta_max": policy["cta_max"],
        "hashtag_limit": hashtag_limit,
        "flagged_terms": sorted(flagged_terms),
    }
    return output
