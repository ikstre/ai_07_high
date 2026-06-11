from __future__ import annotations

import re


# 표시광고법·의약품/의료기기 광고 규정 위반 소지가 큰 표현을 완화 표현으로 치환한다.
# 부분 문자열 중복을 안전하게 처리하려 길고 구체적인 키를 먼저 둔다
# (예: "국내 1위"를 "1위"보다, "최고의"를 "최고"보다 먼저).
GLOBAL_REPLACEMENTS = {
    # 가격·순위 과장
    "최저가": "합리적인 가격",
    "초특가": "특가",
    "역대급": "",
    "세계 최초": "새로운",
    "국내 최초": "새로운",
    "국내 1위": "많이 찾는",
    "업계 1위": "많이 찾는",
    "넘버원": "인기",
    "No.1": "인기",
    "1등": "인기",
    "1위": "인기",
    # 최상급·독점 단정
    "최고의": "뛰어난",
    "최상의": "우수한",
    "최강": "강력한",
    "최고": "뛰어난",
    "독보적": "차별화된",
    "유일무이": "특별한",
    "유일한": "특별한",
    # 단정·보장
    "완벽한": "완성도 높은",
    "완벽하게": "완성도 있게",
    "완벽": "완성도 높은",
    "무조건": "쉽게",
    "반드시": "",
    "절대": "",
    "영원히": "",
    "100%": "",
    "보장": "",
    # 효능 단정·공인
    "공인": "",
    "입증된": "",
    "입증": "",
    "검증된": "",
    # 의약품·의학적 표현
    "치료": "관리",
    "완치": "",
    "효능": "",
    "특효": "",
    "의학적": "",
    "임상": "",
}

# subcopy_max는 포스터 가독성과 제품 상세 설명을 함께 맞추기 위해 상향했다.
# 포스터 SVG가 2~3줄로 wrap하므로 제품 마감/색상/타건감이 정책 단계에서 과하게 잘리는 것을 줄인다.
CHANNEL_POLICY = {
    "인스타그램": {"headline_max": 28, "subcopy_max": 84, "cta_max": 16, "hashtag_limit": 6},
    "스마트스토어": {"headline_max": 32, "subcopy_max": 90, "cta_max": 16, "hashtag_limit": 4},
    "상세페이지": {"headline_max": 34, "subcopy_max": 110, "cta_max": 18, "hashtag_limit": 3},
    "쿠팡 썸네일": {"headline_max": 24, "subcopy_max": 62, "cta_max": 14, "hashtag_limit": 0},
    "배너 광고": {"headline_max": 22, "subcopy_max": 58, "cta_max": 12, "hashtag_limit": 0},
    "네이버 검색광고": {"headline_max": 22, "subcopy_max": 72, "cta_max": 12, "hashtag_limit": 0},
    "카카오 채널": {"headline_max": 26, "subcopy_max": 72, "cta_max": 14, "hashtag_limit": 3},
    "유튜브 쇼츠": {"headline_max": 26, "subcopy_max": 64, "cta_max": 14, "hashtag_limit": 3},
}

DEFAULT_POLICY = {"headline_max": 28, "subcopy_max": 84, "cta_max": 16, "hashtag_limit": 5}

# 공백 회피("국내1위", "최 고")까지 잡도록 모든 글자 사이에 \s* 를 넣어 사전 컴파일한다.
# (단어 사이만 \s* 를 넣으면 "최고"처럼 내부 공백 없는 키의 "최 고" 우회를 못 잡는다 —
#  2026-06-11 QA. 기존에도 부분 문자열 치환이라 음절 간 \s* 허용은 의미상 동일 확장이다.)
_REPLACEMENT_PATTERNS = [
    (term, re.compile(r"\s*".join(re.escape(ch) for ch in term if not ch.isspace())), replacement)
    for term, replacement in GLOBAL_REPLACEMENTS.items()
]


def _compact_spaces(text: str) -> str:
    return re.sub(r"\s{2,}", " ", text).strip()


def _sanitize_text(text: object, flagged_terms: set[str]) -> str:
    value = str(text or "")
    for term, pattern, replacement in _REPLACEMENT_PATTERNS:
        value, count = pattern.subn(replacement, value)
        if count:
            flagged_terms.add(term)
    return _compact_spaces(value)


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 1)].rstrip() + "…"


def _sanitize_hashtag(value: object, flagged_terms: set[str]) -> str:
    tag = str(value or "").strip()
    if not tag:
        return ""
    # 해시태그도 본문과 같은 금지어 치환을 거친다 — 문자 필터만 하면 "#최고",
    # "#국내1위키보드" 같은 부당표시가 그대로 통과한다(2026-06-11 QA).
    body = _sanitize_text(tag.lstrip("#"), flagged_terms)
    body = re.sub(r"\s+", "", body)
    body = re.sub(r"[^0-9A-Za-z_가-힣ㄱ-ㅎㅏ-ㅣ]", "", body)
    return f"#{body}" if body else ""


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
    hashtags = [_sanitize_hashtag(tag, flagged_terms) for tag in output.get("hashtags", [])]
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
