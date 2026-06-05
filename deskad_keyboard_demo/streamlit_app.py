
from __future__ import annotations

import base64
import html
import time
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from ppt_export import build_poster_pptx
from ui_api import (
    api_get,
    api_post,
    fetch_binary_data_url,
    fetch_text_asset,
    poster_preview_height,
    reference_thumbnail_bytes,
    responsive_svg_document,
)
from ui_steps import render_step_input_panel


st.set_page_config(
    page_title="DeskAd AI Studio",
    layout="wide",
    initial_sidebar_state="expanded",
)


st.markdown(
    """
    <style>
      .stApp { background: #f6f8fc; }
      .block-container {
        max-width: min(97vw, 2120px);
        padding-top: 2.5rem;
        padding-bottom: 2.5rem;
        padding-left: 2.75rem;
        padding-right: 2.75rem;
      }

      [data-testid="stSidebar"] {
        width: 280px !important;
        min-width: 280px !important;
      }

      [data-testid="stSidebar"] > div {
        width: 280px !important;
      }

      .section-label {
        font-size: 12px;
        line-height: 1;
        letter-spacing: 0;
        color: #6b7280;
        margin-bottom: 6px;
      }

      .metric-chip {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 6px 10px;
        border: 1px solid rgba(148, 163, 184, 0.28);
        border-radius: 999px;
        font-size: 12px;
        color: #64748b;
        margin-right: 6px;
      }

      iframe {
        border-radius: 8px;
      }

      .step-progress {
        display: flex;
        align-items: center;
        gap: 0;
        margin: 4px 0 12px 0;
        padding: 12px 16px;
        background: linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%);
        border: 1px solid rgba(148, 163, 184, 0.24);
        border-radius: 14px;
      }
      .step-chip {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 6px 14px 6px 6px;
        border-radius: 999px;
        font-size: 13px;
        line-height: 1.1;
        border: 1px solid transparent;
        white-space: nowrap;
      }
      .step-chip .num {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 24px;
        height: 24px;
        border-radius: 999px;
        font-size: 12px;
        font-weight: 600;
        background: #ffffff;
        border: 1px solid currentColor;
      }
      .step-chip.done {
        color: #047857;
        background: rgba(16, 185, 129, 0.10);
        border-color: rgba(16, 185, 129, 0.32);
      }
      .step-chip.done .num {
        background: #047857;
        color: #ffffff;
        border-color: #047857;
      }
      .step-chip.current {
        color: #1d4ed8;
        background: rgba(59, 130, 246, 0.12);
        border-color: rgba(59, 130, 246, 0.42);
        box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.18);
        font-weight: 600;
      }
      .step-chip.current .num {
        background: #1d4ed8;
        color: #ffffff;
        border-color: #1d4ed8;
      }
      .step-chip.pending {
        color: #64748b;
        background: rgba(148, 163, 184, 0.10);
        border-color: rgba(148, 163, 184, 0.28);
      }
      .step-connector {
        flex: 1 1 24px;
        height: 2px;
        margin: 0 8px;
        background: rgba(148, 163, 184, 0.28);
        border-radius: 999px;
      }
      .step-connector.done {
        background: rgba(16, 185, 129, 0.55);
      }

      .poster-thumb-grid {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 8px;
        margin-top: 8px;
      }
      .poster-thumb {
        border: 1px solid rgba(148, 163, 184, 0.32);
        border-radius: 10px;
        padding: 6px 8px 4px 8px;
        background: #ffffff;
        transition: border-color 0.15s ease, box-shadow 0.15s ease;
      }
      .poster-thumb.active {
        border-color: #1d4ed8;
        box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.22);
      }
      .poster-thumb .ptitle {
        font-size: 11px;
        font-weight: 600;
        color: #334155;
        margin-bottom: 2px;
        letter-spacing: -0.1px;
      }
      .poster-thumb.active .ptitle {
        color: #1d4ed8;
      }
      .poster-thumb svg {
        display: block;
        width: 100%;
        height: auto;
      }

      .ad-preview-card {
        min-height: 220px;
        padding: 30px 32px;
        border: 1px solid #e8edf4;
        border-radius: 16px;
        background: linear-gradient(135deg, #ffffff 0%, #dbeafe 160%);
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04), 0 6px 20px rgba(15, 23, 42, 0.06);
        color: #1f2937;
      }
      .ad-preview-card h3 {
        margin: 0 0 14px 0;
        font-size: 26px;
        line-height: 1.25;
        letter-spacing: 0;
      }
      .ad-preview-card .subcopy {
        margin: 0 0 18px 0;
        font-size: 17px;
        line-height: 1.65;
        color: #475569;
      }
      .ad-preview-card ul {
        margin: 0 0 18px 20px;
        padding: 0;
      }
      .ad-preview-card li {
        margin-bottom: 8px;
        line-height: 1.55;
      }
      .ad-preview-card .meta {
        color: #64748b;
        font-size: 14px;
      }
      .ad-preview-card .cta {
        display: inline-block;
        margin-top: 16px;
        padding: 10px 18px;
        border-radius: 999px;
        background: #3b82f6;
        color: #ffffff;
        font-weight: 700;
        font-size: 14px;
        box-shadow: 0 4px 12px rgba(59, 130, 246, 0.30);
      }
      .reference-svg {
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        background: #ffffff;
        padding: 6px;
        height: 150px;
        display: flex;
        align-items: center;
        justify-content: center;
        overflow: hidden;
      }
      .reference-svg svg {
        max-width: 100%;
        max-height: 138px;
        height: auto;
        width: auto;
      }

      /* CTA 강조 (오늘의집 "구매" 자리 → 우리는 "광고 생성") */
      .stButton > button[kind="primary"] {
        border-radius: 999px;
        font-weight: 700;
        box-shadow: 0 4px 14px rgba(59, 130, 246, 0.32);
      }
      .stDownloadButton > button {
        border-radius: 999px;
        font-weight: 700;
      }

      /* 밝은 파스텔 카드 그림자 */
      .step-progress { box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04), 0 6px 18px rgba(15, 23, 42, 0.05); }
      .poster-thumb { box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04); }

      /* 다크모드 적응형 — OS가 다크면 Streamlit 전체(사이드바/헤더/선택창)+카드를 어둡게 */
      @media (prefers-color-scheme: dark) {
        .stApp, [data-testid="stMain"], [data-testid="stAppViewContainer"] { background: #0e1117; }
        [data-testid="stHeader"], [data-testid="stToolbar"] { background: rgba(14, 17, 23, 0.92); }
        [data-testid="stSidebar"] { background: #161b26; border-right: 1px solid #2b3648; }
        .stApp, .stMarkdown, [data-testid="stSidebar"], [data-testid="stWidgetLabel"],
        label, h1, h2, h3, h4, h5, h6, p { color: #e6edf3; }
        /* 입력/선택 위젯 */
        [data-baseweb="select"] > div, [data-baseweb="input"],
        .stTextInput input, .stTextArea textarea, .stNumberInput input,
        [data-baseweb="base-input"] {
          background: #1a2130 !important; color: #e6edf3 !important; border-color: #2b3648 !important;
        }
        [data-baseweb="popover"], [data-baseweb="menu"], [role="listbox"] {
          background: #1a2130 !important; color: #e6edf3 !important;
        }
        [data-testid="stTabs"] button[role="tab"] { color: #cbd5e1; }
        div[data-testid="stExpander"] details { background: #161b26; border-color: #2b3648; }
        [data-testid="stForm"], div[data-testid="stVerticalBlockBorderWrapper"] { border-color: #2b3648; }
        /* 커스텀 카드 */
        .ad-preview-card {
          background: linear-gradient(135deg, #1b2230 0%, #1e3a5f 170%);
          border-color: #2b3648;
          color: #e8edf4;
        }
        .ad-preview-card .subcopy { color: #cbd5e1; }
        .ad-preview-card li { color: #dbe3ee; }
        .ad-preview-card .meta { color: #94a3b8; }
        .metric-chip { background: #161b26; color: #cbd5e1; border-color: #2b3648; }
        .poster-thumb { background: #161b26; border-color: #2b3648; }
        .poster-thumb .ptitle { color: #cbd5e1; }
        .reference-svg { background: #161b26; border-color: #2b3648; }
        .step-progress { background: #161b26; border-color: #2b3648; }
        .step-chip.pending { background: #1e2530; color: #94a3b8; border-color: #2b3648; }
        .section-label { color: #94a3b8 !important; }
        /* 버튼(secondary/download/form) — primary 파랑은 유지 */
        .stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {
          background: #1a2130; color: #e6edf3; border-color: #2b3648;
        }
        .stButton > button[kind="primary"] {
          background: #3b82f6 !important; color: #ffffff !important; border-color: #3b82f6 !important;
        }
        .stButton > button:hover, .stDownloadButton > button:hover {
          border-color: #3b82f6; color: #ffffff;
        }
        /* 드롭다운/셀렉트 펼침(커튼형 메뉴)과 옵션 */
        ul[role="listbox"], [data-baseweb="menu"], [data-baseweb="popover"] > div {
          background: #1a2130 !important;
        }
        ul[role="listbox"] li, li[role="option"], [data-baseweb="menu"] li {
          background: #1a2130 !important; color: #e6edf3 !important;
        }
        li[role="option"]:hover, ul[role="listbox"] li:hover { background: #2b3648 !important; }
        /* expander(접이식) 헤더/본문 */
        [data-testid="stExpander"] summary { background: #161b26 !important; color: #e6edf3 !important; }
        [data-testid="stExpander"] details { background: #161b26 !important; }
        details summary, summary span, summary p { color: #e6edf3 !important; }
        /* multiselect 태그 / radio·checkbox 라벨 */
        span[data-baseweb="tag"] { background: #2b3648 !important; color: #e6edf3 !important; }
        [data-testid="stWidgetLabel"] p, .stRadio label, .stCheckbox label { color: #cbd5e1 !important; }
        /* 3D 셋업 등의 코드/JSON 블록 */
        [data-testid="stJson"], [data-testid="stJson"] > div,
        [data-testid="stCode"], [data-testid="stCodeBlock"], pre, code {
          background: #161b26 !important;
        }
        [data-testid="stJson"] *, [data-testid="stCode"] *, pre, code { color: #e6edf3 !important; }
      }
    </style>
    """,
    unsafe_allow_html=True,
)


STEP_LABELS = {
    1: "상품 정보",
    2: "도면/제품 데이터",
    3: "가상 셋업",
    4: "광고 콘텐츠",
}


DEFAULTS = {
    "step": 1,
    "step_selector": 1,
    "product_name": "크림 베이지 65% 커스텀 키보드",
    "product_type": "커스텀 키보드",
    "price": "189,000원",
    "target_channel": "인스타그램",
    "target_customer": "깔끔한 데스크 셋업을 원하는 직장인",
    "selling_point": "조용한 타건감, 크림 톤 키캡, 작은 책상에도 잘 맞는 65% 배열",
    "layout": "65",
    "product_library": "keyboard_layout 샘플",
    "keyboard_model": "Qwertykeys Neo65",
    "drawing_upload_mode": "샘플 JSON 사용",
    "theme": "minimal",
    "case_color": "#c8c1b2",
    "keycap_color": "#f4ead7",
    "accent_keycap_color": "#6f8faf",
    "deskmat_color": "#1f2937",
    "desk_color": "#d8b892",
    "mouse_color": "#f7f7f2",
    "case_finish": "anodized",
    "plate_material": "aluminum",
    "pcb_color": "black",
    "switch_stem": "red",
    "switch_family": "mx",
    "keycap_profile": "cherry",
    "mount_type": "top_mount",
    "show_internals": False,
    "monitor_arm_style": "single",
    "desk_preset": "120 x 60 cm",
    "desk_width": 120.0,
    "desk_depth": 60.0,
    "monitor_size": "27",
    "asset_selection": ["mouse", "monitor"],
    "selected_setup_item": "keyboard",
    "camera": "perspective",
    "model_url": None,
    "model_meta": None,
    "uploaded_model_url": None,
    "uploaded_model_meta": None,
    "library_model_path": None,
    "library_model_picker_path": None,
    "selected_reference_path": None,
    "selected_history_model_path": None,
    "selected_history_model_url": None,
    "selected_history_model_meta": None,
    "copy_result": None,
    "copy_experiment_result": None,
    "copy_selected_provider": None,
    "poster_result": None,
    "image_job_result": None,
    "image_quality_report": None,
    "image_polling_enabled": False,
    "image_poll_started_at": None,
    "image_poll_timeout_seconds": 180,
    "ad_tone": "감성형",
    "image_ratio": "1:1",
    "extra_request": "깔끔하고 고급스러운 데스크셋업 광고 느낌",
    "poster_template": "minimal_card",
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


def render_poster_template_thumbnails(current_key: str) -> None:
    cards: list[str] = []
    for key, label in POSTER_TEMPLATE_LABELS.items():
        thumb = POSTER_TEMPLATE_THUMBNAILS.get(key, "")
        state = "active" if key == current_key else ""
        cards.append(
            f'<div class="poster-thumb {state}">'
            f'<div class="ptitle">{label}</div>'
            f'{thumb}'
            f'</div>'
        )
    st.markdown(
        '<div class="poster-thumb-grid">' + "".join(cards) + '</div>',
        unsafe_allow_html=True,
    )

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

DEFAULT_LAYOUT_FALLBACK = ["60", "65", "75", "87", "104"]
IMAGE_JOB_TERMINAL_STATUSES = {"completed", "failed", "draft", "not_configured"}

for key, value in DEFAULTS.items():
    st.session_state.setdefault(key, value.copy() if isinstance(value, list) else value)

if st.session_state.step_selector != st.session_state.step:
    st.session_state.step_selector = st.session_state.step


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


FALLBACK_ASSETS = [
    {"id": "mouse", "label": "무선 마우스", "category": "input"},
    {"id": "monitor", "label": "모니터", "category": "display"},
    {"id": "monitor_arm", "label": "VESA 모니터암", "category": "display"},
    {"id": "monitor_light_bar", "label": "모니터 라이트 바", "category": "lighting"},
    {"id": "desk_lamp", "label": "데스크 조명", "category": "lighting"},
    {"id": "plant", "label": "미니 화분", "category": "decor"},
    {"id": "speakers", "label": "북쉘프 스피커", "category": "audio"},
    {"id": "desk_shelf", "label": "모니터 받침대", "category": "furniture"},
    {"id": "notebook", "label": "노트/플래너", "category": "stationery"},
    {"id": "headphone_stand", "label": "헤드폰 스탠드", "category": "audio"},
    {"id": "phone_stand", "label": "스마트폰 스탠드", "category": "accessory"},
    {"id": "keycap_tray", "label": "키캡 진열 트레이", "category": "keyboard"},
    {"id": "coffee_mug", "label": "머그컵", "category": "decor"},
    {"id": "digital_clock", "label": "디지털 시계", "category": "decor"},
    {"id": "aroma_diffuser", "label": "아로마 디퓨저", "category": "decor"},
    {"id": "wireless_charger", "label": "무선 충전 패드", "category": "accessory"},
    {"id": "pen_holder", "label": "펜 홀더", "category": "stationery"},
    {"id": "book_stack", "label": "책 묶음", "category": "decor"},
    {"id": "humidifier", "label": "가습기", "category": "decor"},
    {"id": "photo_frame", "label": "사진 액자", "category": "decor"},
    {"id": "usb_hub", "label": "USB 허브", "category": "accessory"},
    {"id": "mouse_pad_round", "label": "라운드 마우스패드", "category": "input"},
]


def render_reference_grid(references: list[dict], columns: int = 4) -> None:
    """Thumbnail grid of downloaded reference assets. Raster files render via
    st.image (downscaled), SVGs are inlined; layout uses st.columns so it
    renders reliably without HTML-sanitizer / data-URI concerns."""
    cols = st.columns(columns)
    for idx, item in enumerate(references):
        url = item.get("url")
        if not url:
            continue
        ext = str(item.get("extension", "")).lower()
        label = item.get("label") or Path(str(item.get("path", ""))).name or "reference"
        license_text = item.get("license") or "라이선스 확인"
        with cols[idx % columns]:
            try:
                if ext == ".svg":
                    if int(item.get("size_bytes", 0) or 0) <= 400_000:
                        st.markdown(
                            f'<div class="reference-svg">{fetch_text_asset(url)}</div>',
                            unsafe_allow_html=True,
                        )
                    else:
                        st.caption("[SVG · 원본 큼, 드롭다운에서 선택]")
                elif ext in (".png", ".jpg", ".jpeg", ".webp"):
                    st.image(reference_thumbnail_bytes(url), use_container_width=True)
                else:
                    st.caption(f"[{ext.lstrip('.').upper() or 'FILE'}]")
            except Exception:
                st.caption("(미리보기 불가)")
            st.caption(f"{label} · {license_text}")


def format_file_size(size_bytes: int | float | None) -> str:
    size = float(size_bytes or 0)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f}{unit}" if unit == "B" else f"{size:.1f}{unit}"
        size /= 1024
    return "0B"


def model_file_summary(item: dict) -> str:
    modified = item.get("modified_at")
    when = ""
    if isinstance(modified, (int, float)):
        when = time.strftime("%Y-%m-%d %H:%M", time.localtime(float(modified)))
    details = [item.get("kind") or "file", format_file_size(item.get("size_bytes"))]
    if when:
        details.append(when)
    return " · ".join(str(part) for part in details if part)


def render_generated_model_gallery(library: dict | None = None, height: int = 420) -> None:
    library = library or fetch_model_library()
    generated = [
        item
        for item in library.get("files", [])
        if item.get("root") == "generated_models" and item.get("extension") in {".glb", ".gltf"}
    ]
    generated.sort(key=lambda item: float(item.get("modified_at") or 0), reverse=True)
    if not generated:
        st.caption("아직 저장된 생성 모델이 없습니다. 3D 셋업을 생성하면 이 영역에 누적됩니다.")
        return

    st.markdown("#### 이전 생성 모델")
    st.caption("최근 생성한 GLB를 골라 미리보고, 아래 '현재 3D 결과로 불러오기'로 다시 가져올 수 있습니다.")
    options = {item["path"]: item for item in generated[:40] if item.get("path")}
    paths = list(options.keys())
    if st.session_state.selected_history_model_path not in options:
        st.session_state.selected_history_model_path = paths[0] if paths else None
    selected_path = st.selectbox(
        "저장된 모델",
        options=paths,
        key="selected_history_model_path",
        format_func=lambda value: f"{options[value].get('name', value)} · {model_file_summary(options[value])}",
    )
    selected = options.get(selected_path)
    if not selected:
        return
    st.session_state.selected_history_model_url = selected.get("url")
    st.session_state.selected_history_model_meta = selected
    meta_a, meta_b, meta_c = st.columns(3)
    meta_a.caption(f"파일: {selected.get('name', '')}")
    meta_b.caption(f"위치: {selected.get('path', '')}")
    meta_c.caption(model_file_summary(selected))
    if selected.get("url"):
        render_model_viewer(selected["url"], height=height)
        if st.button(
            "이 결과를 현재 3D 결과로 불러오기",
            type="primary",
            use_container_width=True,
            key="load_history_model",
        ):
            st.session_state.model_url = selected.get("url")
            st.success(f"'{selected.get('name', '')}'을(를) 현재 3D 결과로 불러왔습니다.")
            st.rerun()


def render_shared_model_picker(height: int = 360) -> None:
    """공용/외부 모델(이전 생성 결과 제외)을 selectbox로 골라 미리보기/사용한다.

    이전 생성 결과는 옆 render_generated_model_gallery 가 담당하므로 여기선 제외한다.
    (도면 단계 입력 패널에서 가상 셋업 결과 영역으로 옮겨온 picker)
    """
    library = fetch_model_library()
    shared_status = library.get("shared", {})
    st.caption(
        f"공용 데이터: {shared_status.get('shared_data_dir', '/opt/shared_data')} "
        f"({'있음' if shared_status.get('shared_data_exists') else '없음'}) · "
        f"공용 모델: {shared_status.get('shared_model_dir', '/opt/shared_model')} "
        f"({'있음' if shared_status.get('shared_model_exists') else '없음'})"
    )
    compatible = {".glb", ".step", ".stp"}
    files = [
        item
        for item in library.get("files", [])
        if item.get("extension") in compatible and item.get("root") != "generated_models"
    ]
    if not files:
        st.caption(
            "공용/외부 모델이 아직 없습니다. /opt/shared_model 또는 static/models에 외부 GLB/STEP/STP를 넣으면 "
            "여기 FastAPI 미리보기에 연결됩니다. (이전 생성 결과는 옆 '이전 생성 모델'에서 불러오세요.)"
        )
        return

    files.sort(key=lambda item: float(item.get("modified_at") or 0), reverse=True)
    file_options = {item["path"]: item for item in files if item.get("path")}
    if st.session_state.library_model_path not in file_options:
        st.session_state.library_model_path = next(iter(file_options), None)
    if st.session_state.get("library_model_picker_path") not in file_options:
        st.session_state.library_model_picker_path = st.session_state.library_model_path

    selected_path = st.selectbox(
        "FastAPI 미리보기 모델",
        options=list(file_options.keys()),
        key="library_model_picker_path",
        format_func=lambda value: f"{file_options[value].get('name', value)} · {file_options[value].get('kind', 'file')}",
    )
    st.session_state.library_model_path = selected_path
    selected_item = file_options.get(selected_path, {})
    st.caption(
        f"선택됨: {selected_item.get('name', '')} · "
        f"{selected_item.get('root', '')} · {format_file_size(selected_item.get('size_bytes'))}"
    )

    ext = (selected_item.get("extension") or "").lower()
    if ext in {".glb", ".gltf"} and selected_item.get("url"):
        render_model_viewer(selected_item["url"], height=height)
    elif ext in {".step", ".stp"}:
        st.caption("STEP/STP는 3D 미리보기 전 GLB 변환이 필요합니다. 아래 버튼으로 변환·로드하세요.")

    if st.button(
        "이 모델 미리보기/사용",
        type="primary",
        use_container_width=True,
        key="use_selected_library_model",
    ):
        try:
            prepare_library_model(selected_path)
            st.success("공용 모델 준비 완료 — 아래 '업로드/공용 모델 미리보기'에 표시됩니다.")
        except Exception as exc:
            st.error(f"공용 모델 처리 실패: {exc}")


def render_model_load_panel() -> None:
    """선택 편집(가상 셋업) 패널용 '기존 모델 불러오기' 묶음.

    이전 생성 모델(불러오기) + 공용/외부 모델 picker + 업로드/공용 모델 미리보기를
    좁은 편집 패널 폭에 맞춰 세로로 쌓아 보여준다.
    """
    library = fetch_model_library()
    render_generated_model_gallery(library, height=260)
    st.divider()
    st.markdown("#### 공용/외부 모델")
    render_shared_model_picker(height=260)
    if st.session_state.uploaded_model_url:
        st.markdown("##### 업로드/공용 모델 미리보기")
        render_model_viewer(st.session_state.uploaded_model_url, height=260)
        if st.session_state.uploaded_model_meta:
            with st.expander("업로드/공용 모델 메타데이터", expanded=False):
                st.json(st.session_state.uploaded_model_meta)


@st.cache_data(ttl=15)
def fetch_security_config() -> dict:
    try:
        return api_get("/security/config")
    except Exception:
        return {
            "openai_api_key": "unknown",
            "local_llm_base_url": "unknown",
            "hyperclova_base_url": "unknown",
            "kanana_base_url": "unknown",
            "midm_base_url": "unknown",
            "local_image_endpoint": "unknown",
            "comfyui_base_url": "unknown",
            "image_model_backend": "unknown",
            "step_converter_cmd": "unknown",
        }


@st.cache_data(ttl=15)
def fetch_ai_providers() -> dict:
    try:
        return api_get("/ai/providers")
    except Exception:
        return {"providers": [], "auto_order": []}


@st.cache_data(ttl=30)
def fetch_desk_assets() -> list[dict]:
    try:
        return api_get("/assets/desk")["assets"]
    except Exception:
        return FALLBACK_ASSETS


@st.cache_data(ttl=60)
def fetch_layout_ids() -> list[str]:
    try:
        payload = api_get("/layouts")
        layouts = payload.get("layouts") or []
        ids = [item["id"] for item in layouts if isinstance(item, dict) and item.get("id")]
        return ids or list(DEFAULT_LAYOUT_FALLBACK)
    except Exception:
        return list(DEFAULT_LAYOUT_FALLBACK)


@st.cache_data(ttl=30)
def fetch_reference_assets() -> list[dict]:
    try:
        return api_get("/assets/references")["references"]
    except Exception:
        return []


@st.cache_data(ttl=30)
def fetch_model_library() -> dict:
    try:
        return api_get("/models/library")
    except Exception:
        return {"files": [], "model_compatible_extensions": []}


def sync_layout_from_model() -> None:
    defaults = KEYBOARD_MODEL_DEFAULTS.get(st.session_state.keyboard_model)
    if defaults:
        st.session_state.layout = defaults["layout"]


def set_step(step: int) -> None:
    step = max(1, min(len(STEP_LABELS), int(step)))
    st.session_state.step = step
    st.session_state.step_selector = step


def sync_step_from_sidebar() -> None:
    set_step(st.session_state.step_selector)


def render_model_viewer(model_url: str, height: int = 720, camera: str | None = None) -> None:
    camera_param = camera or st.session_state.camera
    camera_orbits = {
        "perspective": "32deg 58deg 165m",
        "top": "0deg 0deg 190m",
        "front": "0deg 76deg 150m",
    }
    data_url = fetch_binary_data_url(model_url, "model/gltf-binary")
    components.html(
        f"""
        <!doctype html>
        <html>
          <head>
            <meta charset="utf-8" />
            <script type="module" src="https://unpkg.com/@google/model-viewer@4.0.0/dist/model-viewer.min.js"></script>
            <style>
              html, body {{ margin: 0; width: 100%; height: 100%; background: #f4f1eb; }}
              model-viewer {{
                width: 100%;
                height: {height}px;
                background: radial-gradient(ellipse at center top, #f9f6f0 0%, #e7ecf1 60%, #dfe4eb 100%);
                border-radius: 8px;
              }}
            </style>
          </head>
          <body>
            <model-viewer
              src="{data_url}"
              camera-controls
              auto-rotate
              auto-rotate-delay="6000"
              environment-image="neutral"
              tone-mapping="aces"
              shadow-intensity="1.4"
              shadow-softness="0.85"
              exposure="1.05"
              camera-orbit="{camera_orbits.get(camera_param, camera_orbits['perspective'])}"
              min-camera-orbit="auto auto 70m"
              max-camera-orbit="auto auto 260m"
              interaction-prompt="none">
            </model-viewer>
          </body>
        </html>
        """,
        height=height,
    )


def build_render_payload() -> dict:
    return {
        "product_name": st.session_state.product_name,
        "layout": st.session_state.layout,
        "case_color": st.session_state.case_color,
        "keycap_color": st.session_state.keycap_color,
        "accent_keycap_color": st.session_state.accent_keycap_color,
        "deskmat_color": st.session_state.deskmat_color,
        "desk_color": st.session_state.desk_color,
        "mouse_color": st.session_state.mouse_color,
        "theme": st.session_state.theme,
        "assets": st.session_state.asset_selection,
        "desk_width": st.session_state.desk_width,
        "desk_depth": st.session_state.desk_depth,
        "monitor_size": st.session_state.monitor_size,
        "case_finish": st.session_state.case_finish,
        "plate_material": st.session_state.plate_material,
        "pcb_color": st.session_state.pcb_color,
        "switch_stem": st.session_state.switch_stem,
        "switch_family": st.session_state.switch_family,
        "keycap_profile": st.session_state.keycap_profile,
        "mount_type": st.session_state.mount_type,
        "show_internals": st.session_state.show_internals,
        "monitor_arm_style": st.session_state.monitor_arm_style,
    }


def current_image_job_id() -> str | None:
    current = st.session_state.image_job_result or {}
    job = current.get("job") or {}
    if job.get("status") != "completed":
        return None
    return job.get("job_id")


def image_job_status() -> str:
    current = st.session_state.image_job_result or {}
    return str((current.get("job") or {}).get("status") or "")


def image_job_is_pending(job: dict | None = None) -> bool:
    if job is None:
        current = st.session_state.image_job_result or {}
        job = current.get("job") or {}
    return bool(job.get("job_id")) and job.get("status") not in IMAGE_JOB_TERMINAL_STATUSES


def poster_waiting_for_image() -> bool:
    if not st.session_state.image_polling_enabled:
        return False
    return bool(st.session_state.image_job_result) and image_job_is_pending()


def build_ad_payload() -> dict:
    payload = {
        **build_render_payload(),
        "product_name": st.session_state.product_name,
        "product_type": st.session_state.product_type,
        "price": st.session_state.price,
        "target_channel": st.session_state.target_channel,
        "target_customer": st.session_state.target_customer,
        "selling_point": st.session_state.selling_point,
        "ad_tone": st.session_state.ad_tone,
        "image_ratio": st.session_state.image_ratio,
        "extra_request": st.session_state.extra_request,
        "model_url": st.session_state.model_url,
        "reference_asset_path": st.session_state.selected_reference_path,
        "image_job_id": current_image_job_id(),
        "poster_template": st.session_state.poster_template,
    }
    selected_copy = selected_copy_payload(st.session_state.copy_result)
    if selected_copy:
        payload["selected_copy"] = selected_copy
    return payload


def selected_copy_payload(copy_result: dict | None) -> dict | None:
    if not isinstance(copy_result, dict):
        return None
    selected = {
        "provider": copy_result.get("provider") or st.session_state.get("copy_selected_provider") or "selected",
        "headline": copy_result.get("headline") or "",
        "subcopy": copy_result.get("subcopy") or "",
        "cta": copy_result.get("cta") or "",
        "copies": list(copy_result.get("copies") or [])[:5],
        "hashtags": list(copy_result.get("hashtags") or [])[:6],
        "spec_bullets": list(copy_result.get("spec_bullets") or [])[:5],
    }
    if not selected["headline"] and not selected["copies"]:
        return None
    return selected


def _copy_editor_signature(copy_result: dict | None) -> tuple[str, str, str, str]:
    if not isinstance(copy_result, dict):
        return ("", "", "", "")
    return (
        str(copy_result.get("provider") or st.session_state.get("copy_selected_provider") or ""),
        str(copy_result.get("headline") or ""),
        str(copy_result.get("subcopy") or ""),
        str(copy_result.get("cta") or ""),
    )


def sync_copy_editor_state(copy_result: dict | None) -> None:
    signature = _copy_editor_signature(copy_result)
    if st.session_state.get("copy_editor_signature") == signature:
        return
    st.session_state.copy_editor_signature = signature
    st.session_state.copy_editor_headline = signature[1]
    st.session_state.copy_editor_subcopy = signature[2]
    st.session_state.copy_editor_cta = signature[3]


def apply_copy_editor_changes() -> None:
    result = dict(st.session_state.copy_result or {})
    result["provider"] = result.get("provider") or st.session_state.get("copy_selected_provider") or "edited"
    result["headline"] = str(st.session_state.get("copy_editor_headline") or "").strip()
    result["subcopy"] = str(st.session_state.get("copy_editor_subcopy") or "").strip()
    result["cta"] = str(st.session_state.get("copy_editor_cta") or "").strip()
    selected = selected_copy_payload(result)
    st.session_state.copy_result = selected or result
    st.session_state.copy_selected_provider = st.session_state.copy_result.get("provider")
    st.session_state.copy_editor_signature = _copy_editor_signature(st.session_state.copy_result)


def render_copy_inline_editor(copy_result: dict | None) -> None:
    if not copy_result:
        return
    sync_copy_editor_state(copy_result)
    with st.form("copy_inline_editor", border=True):
        st.text_input("헤드라인", key="copy_editor_headline", max_chars=80)
        st.text_area("서브카피", key="copy_editor_subcopy", height=88, max_chars=160)
        st.text_input("CTA", key="copy_editor_cta", max_chars=40)
        submitted = st.form_submit_button("문구 업데이트", use_container_width=True)
    if submitted:
        apply_copy_editor_changes()
        st.rerun()


def current_product_export_payload() -> dict:
    return {
        "product_name": st.session_state.product_name,
        "price": st.session_state.price,
        "target_channel": st.session_state.target_channel,
        "selling_point": st.session_state.selling_point,
    }


def render_desk_setup() -> None:
    data = api_post("/render/desk-setup", build_render_payload(), timeout=30)
    st.session_state.model_url = data["model_url"]
    st.session_state.model_meta = data


def upload_reference_model(uploaded_file) -> None:
    raw = uploaded_file.getvalue()
    payload = {
        "filename": uploaded_file.name,
        "content_base64": base64.b64encode(raw).decode("ascii"),
        "product_name": st.session_state.product_name,
    }
    data = api_post("/render/uploaded-model", payload, timeout=45)
    st.session_state.uploaded_model_url = data["model_url"]
    st.session_state.uploaded_model_meta = data


def prepare_library_model(path: str) -> None:
    data = api_post("/models/library/prepare", {"path": path, "product_name": st.session_state.product_name}, timeout=45)
    st.session_state.uploaded_model_url = data["model_url"]
    st.session_state.uploaded_model_meta = data


def generate_copy() -> None:
    st.session_state.copy_result = api_post("/ai/copy", build_ad_payload(), timeout=45)
    st.session_state.copy_selected_provider = st.session_state.copy_result.get("provider")


def generate_copy_experiment() -> None:
    providers = [
        item.get("id")
        for item in fetch_ai_providers().get("providers", [])
        if item.get("configured") and item.get("id") and item.get("id") != "fallback"
    ]
    if "fallback" not in providers:
        providers.append("fallback")
    payload = {**build_ad_payload(), "providers": providers or ["fallback"]}
    st.session_state.copy_experiment_result = api_post("/ai/copy/experiment", payload, timeout=90)
    st.session_state.copy_result = None
    st.session_state.copy_selected_provider = None


def generate_poster() -> None:
    data = api_post("/ai/poster", build_ad_payload(), timeout=60)
    st.session_state.poster_result = data
    st.session_state.copy_result = data["copy"]
    st.session_state.copy_selected_provider = data["copy"].get("provider")


def generate_image_job() -> None:
    data = api_post("/ai/image/jobs", build_ad_payload(), timeout=60)
    st.session_state.image_job_result = data
    copy_result = data.get("copy") if isinstance(data, dict) else None
    if isinstance(copy_result, dict):
        st.session_state.copy_result = copy_result
        st.session_state.copy_selected_provider = copy_result.get("provider")
    job = data.get("job") if isinstance(data, dict) else {}
    if not isinstance(job, dict):
        job = {}
    st.session_state.image_quality_report = None
    st.session_state.image_polling_enabled = image_job_is_pending(job)
    st.session_state.image_poll_started_at = time.time() if st.session_state.image_polling_enabled else None


def refresh_image_job() -> dict | None:
    current = st.session_state.image_job_result or {}
    job_id = (current.get("job") or {}).get("job_id")
    if job_id:
        previous_polling = bool(st.session_state.image_polling_enabled)
        updated = api_get(f"/ai/image/jobs/{job_id}", timeout=30)
        if not isinstance(updated, dict) or not isinstance(updated.get("job"), dict):
            return current.get("job") or None
        st.session_state.image_job_result = updated
        job = updated["job"]
        polling_enabled = image_job_is_pending(job)
        st.session_state.image_polling_enabled = polling_enabled
        if polling_enabled and (not previous_polling or st.session_state.image_poll_started_at is None):
            st.session_state.image_poll_started_at = time.time()
        elif not polling_enabled:
            st.session_state.image_poll_started_at = None
        return job
    return None


@st.fragment(run_every=3)
def auto_poll_image_job() -> None:
    if not st.session_state.image_polling_enabled:
        return
    current = st.session_state.image_job_result or {}
    job = current.get("job") or {}
    if not image_job_is_pending(job):
        st.session_state.image_polling_enabled = False
        st.session_state.image_poll_started_at = None
        return

    started_at = st.session_state.image_poll_started_at
    if started_at is None:
        started_at = time.time()
        st.session_state.image_poll_started_at = started_at
    elapsed = time.time() - started_at
    timeout = int(st.session_state.image_poll_timeout_seconds)
    if elapsed > timeout:
        st.session_state.image_polling_enabled = False
        st.session_state.image_poll_started_at = None
        st.warning(f"이미지 작업 자동 갱신이 {timeout}초를 초과해 중단되었습니다.")
        st.rerun()
        return

    status_slot = st.empty()
    status_slot.caption(f"이미지 작업 자동 갱신 중 · {job.get('status', 'unknown')} · {int(elapsed)}초 경과")
    try:
        updated = refresh_image_job() or job
    except Exception as exc:
        st.session_state.image_polling_enabled = False
        st.session_state.image_poll_started_at = None
        st.error(f"이미지 작업 상태 확인 실패: {exc}")
        st.rerun()
        return

    if updated.get("status") == "completed":
        st.session_state.image_polling_enabled = False
        st.session_state.image_poll_started_at = None
        st.success("이미지 작업 완료. 포스터 생성에 자동으로 연결됩니다.")
        st.rerun()
    elif updated.get("status") in IMAGE_JOB_TERMINAL_STATUSES:
        st.session_state.image_polling_enabled = False
        st.session_state.image_poll_started_at = None
        st.rerun()


def provider_label(provider: str | None) -> str:
    provider_id = (provider or "unknown").strip().lower()
    return PROVIDER_LABELS.get(provider_id, provider_id or "unknown")


def render_copy_experiment_picker() -> None:
    experiment = st.session_state.copy_experiment_result
    if not experiment:
        return

    results = experiment.get("results") or []
    if not results:
        st.caption("생성 후보가 없습니다.")
        return

    st.markdown("#### 광고 문구 후보")
    selected_provider = st.session_state.get("copy_selected_provider")
    if st.session_state.copy_result:
        st.success(f"{provider_label(selected_provider)} 문구가 선택되었습니다. 포스터와 이미지 작업에 이 문구가 반영됩니다.")

    for index, item in enumerate(results):
        provider = item.get("provider", "unknown")
        label = provider_label(provider)
        model_name = item.get("model") or item.get("runtime_name")
        if model_name:
            label += f" · {model_name}"
        status = item.get("status", "unknown")
        copy = item.get("copy") or {}
        with st.container(border=True):
            head_col, action_col = st.columns([0.78, 0.22])
            with head_col:
                st.caption(f"{label} · {status}")
                if copy:
                    st.markdown(f"##### {copy.get('headline') or '제목 없음'}")
                    if copy.get("subcopy"):
                        st.write(copy["subcopy"])
                    bullets = list(copy.get("copies") or [])[:4]
                    if bullets:
                        for line in bullets:
                            st.write(f"- {line}")
                    hashtags = " ".join((copy.get("hashtags") or [])[:6])
                    if hashtags:
                        st.caption(hashtags)
                elif status == "not_configured":
                    st.caption("이 provider는 현재 환경 변수 설정이 없어 건너뜁니다.")
                    st.caption(f"model: {item.get('model', 'default')}")
                elif item.get("error"):
                    st.caption(f"오류: {item['error']}")
                else:
                    st.caption("응답 문구가 없습니다.")
            with action_col:
                if copy:
                    current = st.session_state.copy_result or {}
                    is_selected = (
                        selected_provider == provider
                        and current.get("headline") == copy.get("headline")
                        and current.get("subcopy") == copy.get("subcopy")
                    )
                    if is_selected:
                        st.success("선택됨")
                    if st.button(
                        "이 문구 사용",
                        key=f"use_copy_{index}_{provider}",
                        type="primary" if is_selected else "secondary",
                        use_container_width=True,
                    ):
                        selected = selected_copy_payload({**copy, "provider": copy.get("provider") or provider})
                        if selected:
                            st.session_state.copy_result = selected
                            st.session_state.copy_selected_provider = provider
                            st.rerun()


def go_next() -> None:
    if st.session_state.step == 3 and not st.session_state.model_url:
        render_desk_setup()
    set_step(st.session_state.step + 1)


def go_previous() -> None:
    set_step(st.session_state.step - 1)


def render_step_progress() -> None:
    current = int(st.session_state.get("step", 1))
    total = len(STEP_LABELS)
    chips: list[str] = []
    for index, (step_id, label) in enumerate(STEP_LABELS.items()):
        if step_id < current:
            state = "done"
        elif step_id == current:
            state = "current"
        else:
            state = "pending"
        chips.append(
            f'<div class="step-chip {state}">'
            f'<span class="num">{step_id}</span>'
            f'<span class="label">{label}</span>'
            f'</div>'
        )
        if index < total - 1:
            connector_state = "done" if step_id < current else "pending"
            chips.append(f'<div class="step-connector {connector_state}"></div>')

    st.markdown(
        '<div class="step-progress">' + "".join(chips) + "</div>",
        unsafe_allow_html=True,
    )
    st.progress(current / total, text=f"{current} / {total} — {STEP_LABELS[current]}")


with st.sidebar:
    st.markdown("## DeskAd AI")
    st.caption("도면 기반 3D 셋업 + 광고 콘텐츠 생성")

    st.divider()

    st.markdown("### 작업 단계")
    st.radio(
        "현재 단계",
        options=list(STEP_LABELS.keys()),
        format_func=lambda value: f"{value}. {STEP_LABELS[value]}",
        label_visibility="collapsed",
        key="step_selector",
        on_change=sync_step_from_sidebar,
    )

    st.divider()

    config = fetch_security_config()
    with st.expander("API / 보안 상태", expanded=True):
        st.caption(f"OpenAI Key: {config.get('openai_api_key', 'unknown')}")
        st.caption(f"Local LLM: {config.get('local_llm_base_url', 'unknown')}")
        st.caption(f"STEP Converter: {config.get('step_converter_cmd', 'unknown')}")
        st.caption("실제 키 값은 화면과 API 응답에 노출하지 않습니다.")

    with st.expander("도면 데이터", expanded=True):
        st.checkbox("키보드 하우징", value=True)
        st.checkbox("KiSwitch 스위치 footprint", value=True)
        st.checkbox("Acheron 계열 PCB", value=True)
        st.checkbox("STEP/STP 업로드", value=True)
        st.checkbox("데스크테리어 절차적 GLB", value=True)

    with st.expander("렌더링 설정", expanded=True):
        st.selectbox("카메라", ["perspective", "top", "front"], key="camera")
        st.checkbox("scene_hash 캐시 사용", value=True)

    with st.expander("광고 산출물", expanded=False):
        st.checkbox("SNS 카드", value=True)
        st.checkbox("상세페이지 배너", value=True)
        st.checkbox("광고 문구", value=True)
        st.checkbox("PPT 자료", value=False)


render_step_progress()

STEP_UI_CONTEXT = {
    "CASE_FINISH_LABELS": CASE_FINISH_LABELS,
    "PLATE_MATERIAL_LABELS": PLATE_MATERIAL_LABELS,
    "PCB_COLOR_LABELS": PCB_COLOR_LABELS,
    "SWITCH_STEM_LABELS": SWITCH_STEM_LABELS,
    "SWITCH_FAMILY_LABELS": SWITCH_FAMILY_LABELS,
    "KEYCAP_PROFILE_LABELS": KEYCAP_PROFILE_LABELS,
    "MOUNT_TYPE_LABELS": MOUNT_TYPE_LABELS,
    "MONITOR_ARM_LABELS": MONITOR_ARM_LABELS,
    "POSTER_TEMPLATE_LABELS": POSTER_TEMPLATE_LABELS,
    "MONITOR_SIZES": MONITOR_SIZES,
    "KEYBOARD_SIZE_INFO": KEYBOARD_SIZE_INFO,
    "KEYBOARD_MODEL_DEFAULTS": KEYBOARD_MODEL_DEFAULTS,
    "sync_layout_from_model": sync_layout_from_model,
    "fetch_layout_ids": fetch_layout_ids,
    "upload_reference_model": upload_reference_model,
    "fetch_reference_assets": fetch_reference_assets,
    "render_reference_grid": render_reference_grid,
    "render_model_load_panel": render_model_load_panel,
    "fetch_model_library": fetch_model_library,
    "prepare_library_model": prepare_library_model,
    "fetch_desk_assets": fetch_desk_assets,
    "render_desk_setup": render_desk_setup,
    "render_poster_template_thumbnails": render_poster_template_thumbnails,
    "fetch_security_config": fetch_security_config,
    "generate_copy_experiment": generate_copy_experiment,
    "generate_image_job": generate_image_job,
    "poster_waiting_for_image": poster_waiting_for_image,
    "generate_poster": generate_poster,
    "fetch_ai_providers": fetch_ai_providers,
    "render_copy_experiment_picker": render_copy_experiment_picker,
}

st.markdown('<div class="section-label">RESULT CANVAS / primary</div>', unsafe_allow_html=True)
with st.container(border=True):
    top_a, top_b, top_c = st.columns([0.45, 0.32, 0.23])
    with top_a:
        st.markdown("### 가상 데스크 셋업 결과")
        st.caption("도면/규격 JSON, 셋업 미리보기, 광고 포스터와 문구를 한 화면에 누적 표시합니다.")
    with top_b:
        meta = st.session_state.model_meta or {}
        kb_info = KEYBOARD_SIZE_INFO.get(st.session_state.layout, st.session_state.layout + "%")
        mon_info = MONITOR_SIZES.get(st.session_state.monitor_size, st.session_state.monitor_size + '"')
        desk_w = meta.get("desk_width", st.session_state.desk_width)
        desk_d = meta.get("desk_depth", st.session_state.desk_depth)
        st.markdown(
            f"""
            <span class="metric-chip">KB {kb_info}</span>
            <span class="metric-chip">Mon {mon_info}</span>
            <span class="metric-chip">Desk {desk_w:.0f}×{desk_d:.0f} cm</span>
            <span class="metric-chip">{st.session_state.theme}</span>
            """,
            unsafe_allow_html=True,
        )
    with top_c:
        if st.button("결과 새로고침", use_container_width=True):
            try:
                render_desk_setup()
                st.rerun()
            except Exception as exc:
                st.error(f"실패: {exc}")

    st.divider()

    preview_col, edit_col = st.columns([0.68, 0.32], gap="large")
    with preview_col:
        st.markdown("### 3D 셋업")
        if st.session_state.model_url:
            render_model_viewer(st.session_state.model_url, height=650)
            if st.session_state.model_meta:
                with st.expander("현재 셋업 메타데이터", expanded=False):
                    st.json(st.session_state.model_meta)
        else:
            st.markdown("#### 아직 생성된 3D 결과가 없습니다.")
            st.write("오른쪽 편집 패널에서 셋업 구성을 정한 뒤 `3D 데스크 셋업 생성`을 누르면 이 영역에 결과가 표시됩니다.")
            with st.expander("현재 렌더링 payload", expanded=False):
                st.json(build_render_payload())
    with edit_col:
        st.markdown("### 선택 편집")
        with st.container(border=True):
            render_step_input_panel(STEP_UI_CONTEXT)
            st.divider()
            nav_a, nav_b = st.columns(2)
            nav_a.button(
                "이전",
                use_container_width=True,
                disabled=st.session_state.step <= 1,
                on_click=go_previous,
            )
            nav_b.button(
                "다음",
                use_container_width=True,
                disabled=st.session_state.step >= 4,
                on_click=go_next,
            )

    st.divider()

    with st.expander("광고 포스터 / 이미지 작업", expanded=bool(st.session_state.poster_result)):
        st.markdown("### 광고 포스터")
        poster = st.session_state.poster_result
        if poster:
            template_label = POSTER_TEMPLATE_LABELS.get(poster.get("poster_template", ""), poster.get("poster_template", ""))
            image_reference = poster.get("image_reference") or poster.get("local_image_reference") or {}
            badge = f"`{template_label}`"
            if poster.get("image_embedded"):
                badge += "  ·  이미지 합성"
            elif image_reference.get("error"):
                badge += "  ·  이미지 생성 오류"
            st.caption(badge)
            poster_svg = fetch_text_asset(poster["poster_url"])
            components.html(
                responsive_svg_document(poster_svg),
                height=poster_preview_height(poster_svg),
                scrolling=False,
            )
            download_a, download_b = st.columns(2)
            download_a.download_button(
                "포스터 다운로드 (SVG · 이미지 합성 포함)",
                data=poster_svg,
                file_name=f"deskad_poster_{poster.get('poster_template', 'minimal_card')}.svg",
                mime="image/svg+xml",
                use_container_width=True,
            )
            try:
                pptx_data = build_poster_pptx(
                    poster_svg=poster_svg,
                    copy_result=st.session_state.copy_result or poster.get("copy") or {},
                    poster=poster,
                    product=current_product_export_payload(),
                )
                download_b.download_button(
                    "포스터 다운로드 (PPTX)",
                    data=pptx_data,
                    file_name=f"deskad_poster_{poster.get('poster_template', 'minimal_card')}.pptx",
                    mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    use_container_width=True,
                )
            except Exception as exc:
                download_b.caption(f"PPT 생성 실패: {exc}")
            with st.expander("이미지 생성 프롬프트", expanded=False):
                st.write(poster["image_prompt"])
            if image_reference:
                with st.expander("이미지 모델 응답", expanded=False):
                    st.json(image_reference)
        else:
            st.write("광고 콘텐츠 단계에서 `포스터 생성`을 누르면 SVG 포스터와 생성 프롬프트가 표시됩니다.")
            st.caption("로컬 이미지 모델 (LOCAL_IMAGE_ENDPOINT) 이 설정되어 있으면 생성된 이미지가 포스터에 직접 합성됩니다.")

        image_job_result = st.session_state.image_job_result
        if image_job_result:
            job = image_job_result.get("job", {})
            job_id = job.get("job_id")
            with st.expander("실사 이미지 작업 상태", expanded=job.get("status") not in IMAGE_JOB_TERMINAL_STATUSES):
                st.caption(f"{job.get('provider', 'fallback')} · {job.get('status', 'unknown')} · {job.get('width', '')}×{job.get('height', '')}")
                col_refresh, col_quality = st.columns(2)
                if col_refresh.button("이미지 작업 상태 갱신", use_container_width=True):
                    try:
                        refresh_image_job()
                        st.rerun()
                    except Exception as exc:
                        st.error(f"상태 확인 실패: {exc}")
                if col_quality.button(
                    "이미지 품질 검사 실행",
                    use_container_width=True,
                    disabled=job.get("status") != "completed" or not job_id,
                ):
                    try:
                        st.session_state.image_quality_report = api_post(
                            f"/ai/image/jobs/{job_id}/quality", {}, timeout=30
                        )
                    except Exception as exc:
                        st.error(f"품질 검사 실패: {exc}")
                st.json(job)
            if job.get("status") == "completed":
                st.caption("완료된 이미지 작업은 다음 포스터 생성 시 자동 합성 후보로 사용됩니다.")
            auto_poll_image_job()
            quality = st.session_state.get("image_quality_report")
            if quality and quality.get("report"):
                report = quality["report"]
                with st.expander("이미지 품질 검사 결과", expanded=False):
                    st.caption(
                        f"{report.get('evaluator', 'skeleton')} · "
                        f"{report.get('width', '')}×{report.get('height', '')} · "
                        f"{report.get('aspect_ratio_actual', 'unknown')} · "
                        f"{(report.get('bytes') or 0) // 1024}KB"
                    )
                    st.json(report)

    with st.expander("광고 카드 / 문구 후보", expanded=bool(st.session_state.copy_experiment_result or st.session_state.copy_result)):
        st.markdown("### 광고 카드와 문구")
        ad_left, ad_right = st.columns([0.62, 0.38], gap="large")
        with ad_left:
            st.markdown("#### 광고 카드 미리보기")
            result = st.session_state.copy_result or {}
            headline = result.get("headline") or st.session_state.product_name
            subcopy = result.get("subcopy") or st.session_state.selling_point
            cta = result.get("cta") or "자세히 보기"
            copies = result.get("copies") or []
            bullet_html = "".join(f"<li>{html.escape(str(copy))}</li>" for copy in copies[:3])
            if not bullet_html:
                bullet_html = f"<li>{html.escape(st.session_state.selling_point)}</li>"
            st.markdown(
                f"""
                <div class="ad-preview-card">
                  <h3>{html.escape(str(headline))}</h3>
                  <p class="subcopy">{html.escape(str(subcopy))}</p>
                  <ul>{bullet_html}</ul>
                  <div class="meta">{html.escape(str(st.session_state.price))} · {html.escape(str(st.session_state.target_channel))}</div>
                  <span class="cta">{html.escape(str(cta))}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with ad_right:
            st.markdown("#### 선택 문구 편집")
            result = st.session_state.copy_result
            if result:
                st.caption(f"선택 provider: {provider_label(st.session_state.get('copy_selected_provider') or result.get('provider'))}")
                render_copy_inline_editor(result)
                for copy in result.get("copies", [])[:3]:
                    st.write(f"- {copy}")
                st.caption(" ".join(result.get("hashtags", [])))
                if result.get("error"):
                    st.caption(f"fallback note: {result['error']}")
            else:
                if st.session_state.copy_experiment_result:
                    st.caption("아래 후보 카드에서 사용할 문구를 선택하세요.")
                else:
                    st.caption("광고 콘텐츠 단계에서 문구를 생성하면 여기에 표시됩니다.")

        render_copy_experiment_picker()
