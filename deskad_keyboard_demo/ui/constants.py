"""이 파일은 UI 선택지와 표시 라벨 상수를 담당한다."""

from __future__ import annotations

STEP_LABELS = {
    1: "상품 정보",
    2: "도면/제품 데이터",
    3: "가상 셋업",
    4: "광고 콘텐츠",
}

CASE_FINISH_LABELS = {
    "anodized": "아노다이징 알루미늄 (반광택)",
    "matte": "무광 페인트",
    "polycarbonate": "폴리카보네이트 (반투명톤)",
    "wood": "원목 마감",
}

PLATE_MATERIAL_LABELS = {
    "aluminum": "알루미늄 (단단·청량한 타건)",
    "brass": "황동 (묵직·차분)",
    "pom": "POM (탄성·부드러움)",
    "fr4": "FR4 글래스 (밸런스)",
    "carbon": "카본 (가벼움·드라이)",
    "polycarbonate": "폴리카보네이트 (탄성·부드러움)",
}

PCB_COLOR_LABELS = {
    "black": "블랙 PCB",
    "red": "레드 PCB",
    "blue": "블루 PCB",
    "green": "그린 PCB",
    "white": "화이트 PCB",
}

SWITCH_STEM_LABELS = {
    "red": "Red (Linear, 가벼움)",
    "yellow": "Yellow (Linear, 부드러움)",
    "brown": "Brown (Tactile, 사무용)",
    "blue": "Blue (Clicky, 또렷)",
    "clear": "Clear (Heavy Tactile)",
    "silent_red": "Silent Red (정음)",
    "tactile_purple": "Holy Panda 계열 (Tactile)",
    "linear_black": "Black (Linear, 무거움)",
}

SWITCH_FAMILY_LABELS = {
    "mx": "MX 호환",
    "box": "BOX 구조",
    "holy_panda": "Holy Panda 계열",
    "topre": "Topre 러버돔",
}

KEYCAP_PROFILE_LABELS = {
    "cherry": "Cherry (낮은 스텝스컬프)",
    "oem": "OEM (기본 높이)",
    "xda": "XDA (균일 저상)",
    "sa": "SA (높은 레트로)",
    "mda": "MDA (둥근 중간 높이)",
}

MOUNT_TYPE_LABELS = {
    "top_mount": "Top mount",
    "tray_mount": "Tray mount",
    "gasket_mount": "Gasket mount",
    "o_ring_mount": "O-ring mount",
}

MONITOR_ARM_LABELS = {
    "single": "싱글 암 (직선)",
    "double_joint": "더블 조인트 (꺾임)",
}

POSTER_TEMPLATE_LABELS = {
    "minimal_card": "Minimal Card (제품 강조)",
    "grid_three": "Grid 3컷 (라이프스타일)",
    "feature_focus": "Feature Focus (스펙 강조)",
    "promo_banner": "Promo Banner (할인/광고)",
}

PROVIDER_LABELS = {
    "openai": "OpenAI",
    "hyperclova": "HyperCLOVA",
    "kanana": "Kanana",
    "midm": "Mi:dm",
    "local": "Local",
    "fallback": "Fallback",
}

# 각 템플릿의 실제 backend SVG 레이아웃을 단순화한 140x100 미리보기 (선택 전 비교용).
# backend/ai.py 의 _{template}_svg 함수와 시각적으로 일관되게 유지한다.
POSTER_TEMPLATE_THUMBNAILS = {
    "minimal_card": (
        '<svg viewBox="0 0 140 100" xmlns="http://www.w3.org/2000/svg">'
        '<rect width="140" height="100" rx="6" fill="#f8fafc"/>'
        '<rect x="11" y="10" width="60" height="6" rx="2" fill="#1e293b"/>'
        '<rect x="11" y="20" width="44" height="4" rx="2" fill="#64748b"/>'
        '<rect x="18" y="32" width="104" height="38" rx="4" fill="#cbd5e1"/>'
        '<rect x="11" y="76" width="46" height="5" rx="2" fill="#1e293b"/>'
        '<rect x="11" y="84" width="32" height="4" rx="2" fill="#64748b"/>'
        '<rect x="11" y="91" width="36" height="6" rx="3" fill="#3b82f6"/>'
        '</svg>'
    ),
    "grid_three": (
        '<svg viewBox="0 0 140 100" xmlns="http://www.w3.org/2000/svg">'
        '<rect width="140" height="100" rx="6" fill="#f8fafc"/>'
        '<rect x="11" y="8" width="76" height="6" rx="2" fill="#1e293b"/>'
        '<rect x="11" y="20" width="72" height="48" rx="4" fill="#cbd5e1"/>'
        '<rect x="88" y="20" width="40" height="22" rx="4" fill="#3b82f6" opacity="0.55"/>'
        '<rect x="88" y="46" width="40" height="22" rx="4" fill="#a78bfa" opacity="0.75"/>'
        '<rect x="11" y="74" width="54" height="5" rx="2" fill="#1e293b"/>'
        '<rect x="11" y="83" width="80" height="4" rx="2" fill="#64748b"/>'
        '<rect x="11" y="91" width="60" height="4" rx="2" fill="#3b82f6"/>'
        '</svg>'
    ),
    "feature_focus": (
        '<svg viewBox="0 0 140 100" xmlns="http://www.w3.org/2000/svg">'
        '<rect width="140" height="100" rx="6" fill="#f8fafc"/>'
        '<rect x="11" y="10" width="64" height="6" rx="2" fill="#1e293b"/>'
        '<rect x="11" y="24" width="62" height="56" rx="4" fill="#cbd5e1"/>'
        '<rect x="80" y="22" width="50" height="60" rx="6" fill="#3b82f6" opacity="0.10"/>'
        '<text x="85" y="31" font-size="6" font-family="sans-serif" font-weight="700" fill="#1d4ed8">SPECS</text>'
        '<circle cx="86" cy="42" r="1.6" fill="#1d4ed8"/><rect x="90" y="40" width="36" height="3" rx="1" fill="#334155"/>'
        '<circle cx="86" cy="52" r="1.6" fill="#1d4ed8"/><rect x="90" y="50" width="32" height="3" rx="1" fill="#334155"/>'
        '<circle cx="86" cy="62" r="1.6" fill="#1d4ed8"/><rect x="90" y="60" width="34" height="3" rx="1" fill="#334155"/>'
        '<circle cx="86" cy="72" r="1.6" fill="#1d4ed8"/><rect x="90" y="70" width="28" height="3" rx="1" fill="#334155"/>'
        '<rect x="11" y="89" width="40" height="5" rx="2" fill="#1e293b"/>'
        '</svg>'
    ),
    "promo_banner": (
        '<svg viewBox="0 0 140 100" xmlns="http://www.w3.org/2000/svg">'
        '<rect width="140" height="100" rx="6" fill="#f8fafc"/>'
        '<rect x="6" y="14" width="128" height="60" rx="6" fill="#f59e0b"/>'
        '<text x="14" y="38" font-size="14" font-family="sans-serif" font-weight="800" fill="#ffffff">50% OFF</text>'
        '<text x="14" y="56" font-size="9" font-family="sans-serif" font-weight="700" fill="#fff7ed">한정 특가</text>'
        '<rect x="84" y="22" width="44" height="36" rx="4" fill="#ffffff" opacity="0.55"/>'
        '<rect x="14" y="80" width="60" height="4" rx="2" fill="#1e293b"/>'
        '<rect x="14" y="88" width="84" height="4" rx="2" fill="#64748b"/>'
        '<rect x="14" y="94" width="40" height="3" rx="1" fill="#3b82f6"/>'
        '</svg>'
    ),
}

MONITOR_SIZES = {
    "24": "24인치 (56 × 33 cm)",
    "27": "27인치 (62 × 36 cm)",
    "32": "32인치 (74 × 43 cm)",
}

KEYBOARD_SIZE_INFO = {
    "60": "60% (약 28.6 × 9.5 cm, 61키)",
    "65": "65% (약 30.5 × 9.5 cm, 67키)",
    "75": "75% (약 30.5 × 11.4 cm, 84키)",
    "87": "TKL 80% (약 34.8 × 11.4 cm, 87키)",
    "104": "풀배열 100% (약 42.9 × 11.4 cm, 104키)",
}

IMAGE_JOB_TERMINAL_STATUSES = {"completed", "failed", "draft", "not_configured"}

KEYBOARD_MODEL_DEFAULTS = {
    "Qwertykeys Neo65": {
        "layout": "65",
        "description": "65% 컴팩트 커스텀 키보드, 미니멀/프리미엄 광고에 적합",
    },
    "Keychron Q1": {
        "layout": "75",
        "description": "75% 알루미늄 키보드, 사무용/프리미엄 셋업에 적합",
    },
    "Geonworks Frog Mini": {
        "layout": "65",
        "description": "작은 책상에 어울리는 미니 배열 커스텀 키보드",
    },
    "Custom 75": {
        "layout": "75",
        "description": "상세페이지용 제품 시뮬레이션에 적합한 75% 샘플",
    },
    "HHKB Style 60": {
        "layout": "60",
        "description": "60% 배열, 화살표 클러스터 없는 클래식 미니멀 키보드",
    },
    "Keychron Q3 TKL": {
        "layout": "87",
        "description": "87키 텐키리스 알루미늄 키보드, 게이밍/사무용 만능 셋업",
    },
    "Leopold FC750R": {
        "layout": "87",
        "description": "TKL 80% 클래식, PBT 키캡 + 무각 디자인의 사무용 표준",
    },
    "Keychron Q6 Full": {
        "layout": "104",
        "description": "풀배열 100% 알루미늄 케이스, 텐키 필요한 회계/데이터 업무용",
    },
    "Royal Kludge RK104": {
        "layout": "104",
        "description": "풀배열 무선 키보드, 책상이 넓은 스튜디오/홈오피스 셋업",
    },
}