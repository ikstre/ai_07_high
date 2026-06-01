
from __future__ import annotations

import base64
import html
import os
from pathlib import Path

import requests
import streamlit as st
import streamlit.components.v1 as components


APP_DIR = Path(__file__).resolve().parent


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env_file(APP_DIR / ".env")
API_BASE = os.getenv("DESKAD_API_BASE", "http://127.0.0.1:8010").rstrip("/")
PUBLIC_API_BASE = os.getenv("DESKAD_PUBLIC_API_BASE", API_BASE).rstrip("/")


st.set_page_config(
    page_title="DeskAd AI Studio",
    layout="wide",
    initial_sidebar_state="expanded",
)


st.markdown(
    """
    <style>
      .block-container {
        max-width: min(96vw, 1920px);
        padding-top: 2rem;
        padding-bottom: 2rem;
        padding-left: 2rem;
        padding-right: 2rem;
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
        padding: 28px 30px;
        border: 1px solid rgba(148, 163, 184, 0.28);
        border-radius: 10px;
        background: linear-gradient(135deg, rgba(248, 250, 252, 0.05), rgba(148, 163, 184, 0.08));
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
        color: rgba(229, 231, 235, 0.86);
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
        color: rgba(156, 163, 175, 0.92);
        font-size: 14px;
      }
      .ad-preview-card .cta {
        display: inline-block;
        margin-top: 16px;
        padding: 9px 14px;
        border-radius: 8px;
        background: #2563eb;
        color: #ffffff;
        font-weight: 700;
        font-size: 14px;
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
    "asset_selection": ["mouse", "monitor", "monitor_arm", "desk_lamp", "plant"],
    "camera": "perspective",
    "model_url": None,
    "model_meta": None,
    "uploaded_model_url": None,
    "uploaded_model_meta": None,
    "library_model_path": None,
    "selected_reference_path": None,
    "copy_result": None,
    "copy_experiment_result": None,
    "poster_result": None,
    "image_job_result": None,
    "image_quality_report": None,
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
}

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


def api_get(path: str, timeout: int = 10) -> dict:
    response = requests.get(f"{API_BASE}{path}", timeout=timeout)
    response.raise_for_status()
    return response.json()


def api_post(path: str, payload: dict, timeout: int = 30) -> dict:
    response = requests.post(f"{API_BASE}{path}", json=payload, timeout=timeout)
    response.raise_for_status()
    return response.json()


def to_internal_api_url(url: str) -> str:
    if PUBLIC_API_BASE != API_BASE and url.startswith(PUBLIC_API_BASE):
        return API_BASE + url[len(PUBLIC_API_BASE):]
    return url


@st.cache_data(ttl=300)
def fetch_binary_data_url(url: str, mime_type: str) -> str:
    response = requests.get(to_internal_api_url(url), timeout=30)
    response.raise_for_status()
    encoded = base64.b64encode(response.content).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


@st.cache_data(ttl=300)
def fetch_text_asset(url: str) -> str:
    response = requests.get(to_internal_api_url(url), timeout=30)
    response.raise_for_status()
    return response.text


def responsive_svg_document(svg: str) -> str:
    return f"""
    <!doctype html>
    <html>
      <head>
        <meta charset="utf-8" />
        <style>
          html, body {{
            margin: 0;
            width: 100%;
            min-height: 100%;
            background: transparent;
            overflow: hidden;
          }}
          .poster-frame {{
            width: 100%;
            box-sizing: border-box;
            padding: 0;
          }}
          .poster-frame svg {{
            display: block;
            width: 100%;
            height: auto;
            max-width: 100%;
          }}
        </style>
      </head>
      <body>
        <div class="poster-frame">{svg}</div>
      </body>
    </html>
    """


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
    return (current.get("job") or {}).get("job_id")


def build_ad_payload() -> dict:
    return {
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


def render_desk_setup() -> None:
    data = api_post("/render/desk-setup", build_render_payload(), timeout=30)
    st.session_state.model_url = data["model_url"]
    st.session_state.model_meta = data


def upload_reference_model(uploaded_file) -> None:
    raw = uploaded_file.getvalue()
    payload = {
        "filename": uploaded_file.name,
        "content_base64": base64.b64encode(raw).decode("ascii"),
    }
    data = api_post("/render/uploaded-model", payload, timeout=45)
    st.session_state.uploaded_model_url = data["model_url"]
    st.session_state.uploaded_model_meta = data


def prepare_library_model(path: str) -> None:
    data = api_post("/models/library/prepare", {"path": path}, timeout=45)
    st.session_state.uploaded_model_url = data["model_url"]
    st.session_state.uploaded_model_meta = data


def generate_copy() -> None:
    st.session_state.copy_result = api_post("/ai/copy", build_ad_payload(), timeout=45)


def generate_copy_experiment() -> None:
    payload = {**build_ad_payload(), "providers": ["kanana", "midm", "local", "fallback"]}
    st.session_state.copy_experiment_result = api_post("/ai/copy/experiment", payload, timeout=90)


def generate_poster() -> None:
    data = api_post("/ai/poster", build_ad_payload(), timeout=60)
    st.session_state.poster_result = data
    st.session_state.copy_result = data["copy"]


def generate_image_job() -> None:
    data = api_post("/ai/image/jobs", build_ad_payload(), timeout=60)
    st.session_state.image_job_result = data
    st.session_state.copy_result = data["copy"]


def refresh_image_job() -> None:
    current = st.session_state.image_job_result or {}
    job_id = (current.get("job") or {}).get("job_id")
    if job_id:
        st.session_state.image_job_result = api_get(f"/ai/image/jobs/{job_id}", timeout=30)


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

left_col, result_col = st.columns([0.72, 1.85], gap="large")

with left_col:
    st.markdown('<div class="section-label">INPUT PANEL / responsive</div>', unsafe_allow_html=True)
    with st.container(border=True, height=500):
        if st.session_state.step == 1:
            st.markdown("#### 상품 정보")
            st.session_state.product_type = st.selectbox(
                "상품 유형",
                ["커스텀 키보드", "키캡", "데스크매트", "데스크 조명", "모니터암", "데스크 소품", "번들 셋업"],
                index=["커스텀 키보드", "키캡", "데스크매트", "데스크 조명", "모니터암", "데스크 소품", "번들 셋업"].index(st.session_state.product_type)
                if st.session_state.product_type in ["커스텀 키보드", "키캡", "데스크매트", "데스크 조명", "모니터암", "데스크 소품", "번들 셋업"]
                else 0,
            )
            st.session_state.product_name = st.text_input("상품명", st.session_state.product_name)
            st.session_state.price = st.text_input("판매가", st.session_state.price)
            st.session_state.target_channel = st.selectbox(
                "판매 채널",
                ["인스타그램", "스마트스토어", "상세페이지", "쿠팡 썸네일", "배너 광고"],
            )
            st.session_state.target_customer = st.text_input("타깃 고객", st.session_state.target_customer)
            st.session_state.selling_point = st.text_area("핵심 특징", st.session_state.selling_point, height=95)

        elif st.session_state.step == 2:
            st.markdown("#### 도면/제품 데이터")
            st.session_state.product_library = st.selectbox(
                "제품 라이브러리",
                ["keyboard_layout 샘플", "QMK/VIA 샘플", "사용자 업로드"],
                index=["keyboard_layout 샘플", "QMK/VIA 샘플", "사용자 업로드"].index(st.session_state.product_library),
            )
            st.selectbox(
                "키보드 모델",
                list(KEYBOARD_MODEL_DEFAULTS.keys()),
                key="keyboard_model",
                on_change=sync_layout_from_model,
            )
            layout_options = ["60", "65", "75"]
            st.session_state.layout = st.selectbox(
                "배열",
                layout_options,
                index=layout_options.index(st.session_state.layout) if st.session_state.layout in layout_options else 1,
                format_func=lambda k: KEYBOARD_SIZE_INFO.get(k, k + "%"),
            )
            st.session_state.drawing_upload_mode = st.radio(
                "도면 입력 방식",
                ["샘플 JSON 사용", "STEP/GLB 파일 업로드"],
                horizontal=True,
                index=["샘플 JSON 사용", "STEP/GLB 파일 업로드"].index(st.session_state.drawing_upload_mode)
                if st.session_state.drawing_upload_mode in ["샘플 JSON 사용", "STEP/GLB 파일 업로드"]
                else 0,
            )
            if st.session_state.drawing_upload_mode == "STEP/GLB 파일 업로드":
                uploaded = st.file_uploader("STEP/STP/GLB 업로드", type=["step", "stp", "glb"])
                if uploaded and st.button("업로드 모델 미리보기", type="primary", use_container_width=True):
                    try:
                        upload_reference_model(uploaded)
                        st.success("업로드 모델 준비 완료")
                    except Exception as exc:
                        st.error(f"업로드 처리 실패: {exc}")

            with st.expander("공용 모델/도면 라이브러리", expanded=True):
                references = fetch_reference_assets()
                downloaded_refs = [item for item in references if item.get("downloaded")]
                st.caption(f"노션 리서치 기반 레퍼런스 {len(references)}개 · 다운로드 완료 {len(downloaded_refs)}개")
                if downloaded_refs:
                    ref_options = {item["path"]: item for item in downloaded_refs if item.get("path")}
                    if st.session_state.selected_reference_path not in ref_options:
                        st.session_state.selected_reference_path = next(iter(ref_options), None)
                    selected_ref = st.selectbox(
                        "다운로드된 도면/레퍼런스",
                        options=list(ref_options.keys()),
                        key="selected_reference_path",
                        format_func=lambda value: f"{ref_options[value].get('label', value)} · {ref_options[value].get('license', 'license check')}",
                    )
                    ref_item = ref_options.get(selected_ref, {})
                    st.caption(f"출처: {ref_item.get('source_url', '')}")
                else:
                    st.caption("아직 다운로드된 노션 레퍼런스가 없습니다. 다운로드 스크립트 실행 후 표시됩니다.")

                library = fetch_model_library()
                shared_status = library.get("shared", {})
                st.caption(
                    f"공용 데이터: {shared_status.get('shared_data_dir', '/opt/shared_data')} "
                    f"({'있음' if shared_status.get('shared_data_exists') else '없음'}) · "
                    f"공용 모델: {shared_status.get('shared_model_dir', '/opt/shared_model')} "
                    f"({'있음' if shared_status.get('shared_model_exists') else '없음'})"
                )
                compatible = {".glb", ".step", ".stp"}
                files = [item for item in library.get("files", []) if item.get("extension") in compatible]
                if files:
                    file_options = {item["path"]: item for item in files}
                    if st.session_state.library_model_path not in file_options:
                        st.session_state.library_model_path = next(iter(file_options), None)
                    selected_file = st.selectbox(
                        "FastAPI 미리보기 모델",
                        options=list(file_options.keys()),
                        key="library_model_path",
                        format_func=lambda value: f"{file_options[value].get('name', value)} · {file_options[value].get('kind', 'file')}",
                    )
                    if st.button("공용 모델 미리보기", use_container_width=True):
                        try:
                            prepare_library_model(selected_file)
                            st.success("공용 모델 준비 완료")
                        except Exception as exc:
                            st.error(f"공용 모델 처리 실패: {exc}")
                else:
                    st.caption("/opt/shared_model 또는 static/models에 GLB/STEP/STP 파일을 넣으면 여기서 바로 FastAPI 미리보기에 연결됩니다.")
            model_info = KEYBOARD_MODEL_DEFAULTS[st.session_state.keyboard_model]
            st.info(f"기본값: {st.session_state.keyboard_model} / {model_info['layout']} 배열\n\n{model_info['description']}")

            with st.expander("키보드 상세 커스텀 (케이스/보강판/PCB/스위치)", expanded=True):
                custom_a, custom_b = st.columns(2)
                with custom_a:
                    st.session_state.case_finish = st.selectbox(
                        "케이스 마감",
                        list(CASE_FINISH_LABELS.keys()),
                        index=list(CASE_FINISH_LABELS.keys()).index(st.session_state.case_finish),
                        format_func=lambda k: CASE_FINISH_LABELS[k],
                    )
                    st.session_state.plate_material = st.selectbox(
                        "보강판(plate) 재질",
                        list(PLATE_MATERIAL_LABELS.keys()),
                        index=list(PLATE_MATERIAL_LABELS.keys()).index(st.session_state.plate_material),
                        format_func=lambda k: PLATE_MATERIAL_LABELS[k],
                    )
                with custom_b:
                    st.session_state.pcb_color = st.selectbox(
                        "PCB 색상",
                        list(PCB_COLOR_LABELS.keys()),
                        index=list(PCB_COLOR_LABELS.keys()).index(st.session_state.pcb_color),
                        format_func=lambda k: PCB_COLOR_LABELS[k],
                    )
                    st.session_state.switch_stem = st.selectbox(
                        "스위치 stem",
                        list(SWITCH_STEM_LABELS.keys()),
                        index=list(SWITCH_STEM_LABELS.keys()).index(st.session_state.switch_stem),
                        format_func=lambda k: SWITCH_STEM_LABELS[k],
                    )
                detail_a, detail_b, detail_c = st.columns(3)
                with detail_a:
                    st.session_state.switch_family = st.selectbox(
                        "스위치 구조",
                        list(SWITCH_FAMILY_LABELS.keys()),
                        index=list(SWITCH_FAMILY_LABELS.keys()).index(st.session_state.switch_family),
                        format_func=lambda k: SWITCH_FAMILY_LABELS[k],
                    )
                with detail_b:
                    st.session_state.keycap_profile = st.selectbox(
                        "키캡 프로파일",
                        list(KEYCAP_PROFILE_LABELS.keys()),
                        index=list(KEYCAP_PROFILE_LABELS.keys()).index(st.session_state.keycap_profile),
                        format_func=lambda k: KEYCAP_PROFILE_LABELS[k],
                    )
                with detail_c:
                    st.session_state.mount_type = st.selectbox(
                        "마운트 방식",
                        list(MOUNT_TYPE_LABELS.keys()),
                        index=list(MOUNT_TYPE_LABELS.keys()).index(st.session_state.mount_type),
                        format_func=lambda k: MOUNT_TYPE_LABELS[k],
                    )
                st.session_state.show_internals = st.checkbox(
                    "내부 구조(보강판/PCB/스위치) 렌더 노출",
                    value=st.session_state.show_internals,
                    help="체크하면 키보드 측면에서 내부 적층 구조가 보이도록 두께를 살짝 분리합니다. 포스터 컷에서 분해도처럼 보이게 할 때 유용합니다.",
                )

            st.markdown("##### 데스크테리어 항목")
            assets = fetch_desk_assets()
            asset_labels = {asset["id"]: f"{asset['label']} · {asset.get('category', 'asset')}" for asset in assets}
            categories: dict[str, list[str]] = {}
            for asset in assets:
                categories.setdefault(asset.get("category", "etc"), []).append(asset["id"])
            asset_caption = " / ".join(f"{cat}({len(items)})" for cat, items in sorted(categories.items()))
            st.caption(f"전체 {len(assets)}개 에셋 · {asset_caption}")
            st.session_state.asset_selection = st.multiselect(
                "렌더링에 포함할 판매/연출 물품",
                options=[asset["id"] for asset in assets],
                default=[item for item in st.session_state.asset_selection if item in asset_labels],
                format_func=lambda item: asset_labels.get(item, item),
            )

        elif st.session_state.step == 3:
            st.markdown("#### 가상 셋업")
            st.session_state.theme = st.selectbox(
                "광고 스타일",
                ["minimal", "pastel", "premium", "gaming"],
                index=["minimal", "pastel", "premium", "gaming"].index(st.session_state.theme),
            )
            desk_presets = {
                "120 x 60 cm": (120.0, 60.0),
                "120 x 80 cm": (120.0, 80.0),
                "140 x 70 cm": (140.0, 70.0),
                "160 x 80 cm": (160.0, 80.0),
                "180 x 80 cm": (180.0, 80.0),
                "직접 입력": (float(st.session_state.desk_width), float(st.session_state.desk_depth)),
            }
            previous_preset = st.session_state.get("desk_preset", "120 x 60 cm")
            st.session_state.desk_preset = st.selectbox(
                "책상 크기 프리셋",
                list(desk_presets.keys()),
                index=list(desk_presets.keys()).index(previous_preset) if previous_preset in desk_presets else 0,
            )
            if st.session_state.desk_preset != "직접 입력" and st.session_state.desk_preset != previous_preset:
                st.session_state.desk_width, st.session_state.desk_depth = desk_presets[st.session_state.desk_preset]

            dim_a, dim_b = st.columns(2)
            with dim_a:
                st.session_state.desk_width = st.slider("책상 폭(cm)", 100.0, 200.0, float(st.session_state.desk_width), 5.0)
            with dim_b:
                st.session_state.desk_depth = st.slider("책상 깊이(cm)", 50.0, 90.0, float(st.session_state.desk_depth), 5.0)

            mon_a, mon_b = st.columns(2)
            with mon_a:
                st.session_state.monitor_size = st.selectbox(
                    "모니터 크기",
                    options=list(MONITOR_SIZES.keys()),
                    index=list(MONITOR_SIZES.keys()).index(st.session_state.monitor_size),
                    format_func=lambda k: MONITOR_SIZES[k],
                )
                st.session_state.monitor_arm_style = st.selectbox(
                    "모니터암 스타일",
                    options=list(MONITOR_ARM_LABELS.keys()),
                    index=list(MONITOR_ARM_LABELS.keys()).index(st.session_state.monitor_arm_style),
                    format_func=lambda k: MONITOR_ARM_LABELS[k],
                )
            with mon_b:
                kb_layout = st.session_state.layout
                st.caption(f"키보드: {KEYBOARD_SIZE_INFO.get(kb_layout, kb_layout + '% 배열')}")
                st.caption("렌더 단위: 1 GLB unit = 1 cm  |  1u = 1.905 cm")
                st.caption(f"케이스: {CASE_FINISH_LABELS[st.session_state.case_finish]}")
                st.caption(f"보강판: {PLATE_MATERIAL_LABELS[st.session_state.plate_material]}")
                st.caption(f"스위치: {SWITCH_STEM_LABELS[st.session_state.switch_stem]} · {SWITCH_FAMILY_LABELS[st.session_state.switch_family]}")
                st.caption(f"키캡: {KEYCAP_PROFILE_LABELS[st.session_state.keycap_profile]}")
                st.caption(f"마운트: {MOUNT_TYPE_LABELS[st.session_state.mount_type]}")
            color_a, color_b = st.columns(2)
            with color_a:
                st.session_state.case_color = st.color_picker("하우징", st.session_state.case_color)
                st.session_state.keycap_color = st.color_picker("키캡", st.session_state.keycap_color)
                st.session_state.accent_keycap_color = st.color_picker("포인트 키", st.session_state.accent_keycap_color)
            with color_b:
                st.session_state.deskmat_color = st.color_picker("데스크매트", st.session_state.deskmat_color)
                st.session_state.desk_color = st.color_picker("책상", st.session_state.desk_color)
                st.session_state.mouse_color = st.color_picker("마우스", st.session_state.mouse_color)

            if st.button("3D 데스크 셋업 생성", type="primary", use_container_width=True):
                try:
                    render_desk_setup()
                    st.success("3D GLB 생성 완료")
                except Exception as exc:
                    st.error(f"렌더링 실패: {exc}")

        else:
            st.markdown("#### 광고 콘텐츠")
            ad_a, ad_b = st.columns(2)
            with ad_a:
                st.session_state.ad_tone = st.selectbox("광고 톤", ["프리미엄형", "감성형", "할인형", "기능강조형"])
                st.session_state.image_ratio = st.selectbox("이미지 비율", ["1:1", "4:5", "16:9"])
            with ad_b:
                st.session_state.poster_template = st.selectbox(
                    "포스터 템플릿",
                    options=list(POSTER_TEMPLATE_LABELS.keys()),
                    index=list(POSTER_TEMPLATE_LABELS.keys()).index(st.session_state.poster_template),
                    format_func=lambda k: POSTER_TEMPLATE_LABELS[k],
                )
                render_poster_template_thumbnails(st.session_state.poster_template)
                config_now = fetch_security_config()
                local_llm_status = "on" if config_now.get("local_llm_base_url") == "set" else "off"
                hyperclova_status = "on" if config_now.get("hyperclova_base_url") == "set" else "off"
                kanana_status = "on" if config_now.get("kanana_base_url") == "set" else "off"
                midm_status = "on" if config_now.get("midm_base_url") == "set" else "off"
                openai_status = "on" if config_now.get("openai_api_key") == "set" else "off"
                local_img_status = "on" if config_now.get("local_image_endpoint") == "set" else "off"
                comfyui_status = "on" if config_now.get("comfyui_base_url") == "set" else "off"
                st.caption(
                    f"AI: OpenAI {openai_status} · Local {local_llm_status} · HyperCLOVA {hyperclova_status} · "
                    f"Kanana {kanana_status} · Mi:dm {midm_status}"
                )
                st.caption(f"Image {config_now.get('image_model_backend', 'auto')} / local {local_img_status} / ComfyUI {comfyui_status}")
            st.session_state.extra_request = st.text_area("추가 요청", st.session_state.extra_request, height=110)

            col_copy, col_exp, col_image, col_poster = st.columns(4)
            if col_copy.button("광고 문구 생성", type="secondary", use_container_width=True):
                try:
                    generate_copy()
                    st.success("광고 문구 생성 완료")
                except Exception as exc:
                    st.error(f"문구 생성 실패: {exc}")
            if col_exp.button("한글 모델 비교", type="secondary", use_container_width=True):
                try:
                    generate_copy_experiment()
                    st.success("모델 비교 완료")
                except Exception as exc:
                    st.error(f"모델 비교 실패: {exc}")
            if col_image.button("실사 이미지 작업", type="secondary", use_container_width=True):
                try:
                    generate_image_job()
                    st.success("이미지 작업 생성 완료")
                except Exception as exc:
                    st.error(f"이미지 작업 실패: {exc}")
            if col_poster.button("포스터 생성", type="primary", use_container_width=True):
                try:
                    generate_poster()
                    st.success("포스터 생성 완료")
                except Exception as exc:
                    st.error(f"포스터 생성 실패: {exc}")

            providers = fetch_ai_providers().get("providers", [])
            if providers:
                configured = [item["id"] for item in providers if item.get("configured") and item.get("id") != "fallback"]
                st.caption(f"사용 가능 provider: {', '.join(configured) if configured else 'fallback only'}")

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


with result_col:
    st.markdown('<div class="section-label">RESULT CANVAS / responsive</div>', unsafe_allow_html=True)
    with st.container(border=True, height=1000):
        top_a, top_b, top_c = st.columns([0.45, 0.3, 0.25])
        with top_a:
            st.markdown("### 가상 데스크 셋업 결과")
            st.caption("도면/규격 JSON과 데스크테리어 항목을 기반으로 생성된 3D 미리보기와 광고 결과물")
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

        setup_tab, upload_tab, poster_tab = st.tabs(["3D 셋업", "업로드 모델", "광고 포스터"])

        with setup_tab:
            if st.session_state.model_url:
                render_model_viewer(st.session_state.model_url, height=600)
            else:
                st.markdown("#### 아직 생성된 3D 결과가 없습니다.")
                st.write("왼쪽 입력 패널에서 `가상 셋업` 단계로 이동한 뒤 `3D 데스크 셋업 생성`을 누르면 이 영역에 결과가 표시됩니다.")
                st.json(build_render_payload())

        with upload_tab:
            if st.session_state.uploaded_model_url:
                render_model_viewer(st.session_state.uploaded_model_url, height=600)
                if st.session_state.uploaded_model_meta:
                    st.json(st.session_state.uploaded_model_meta)
            else:
                st.write("STEP/STP/GLB 파일을 업로드하면 이 탭에서 별도로 확인할 수 있습니다.")
                st.caption("현재 VM에 STEP 변환 CLI가 없으면 프록시 GLB로 미리보기를 제공합니다. `.env`의 STEP_CONVERTER_CMD를 설정하면 실제 변환으로 전환됩니다.")

        with poster_tab:
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
                components.html(responsive_svg_document(fetch_text_asset(poster["poster_url"])), height=760, scrolling=False)
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
                with st.expander("실사 이미지 작업 상태", expanded=job.get("status") not in {"completed", "not_configured"}):
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

        st.divider()

        ad_left, ad_right = st.columns([0.66, 0.34])
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
            st.markdown("#### 생성 문구")
            result = st.session_state.copy_result
            if result:
                st.write(f"**{result.get('headline', '')}**")
                if result.get("subcopy"):
                    st.caption(result["subcopy"])
                for copy in result.get("copies", [])[:3]:
                    st.write(f"- {copy}")
                if result.get("cta"):
                    st.write(f"CTA: `{result['cta']}`")
                st.caption(" ".join(result.get("hashtags", [])))
                if result.get("error"):
                    st.caption(f"fallback note: {result['error']}")
            else:
                st.caption("광고 콘텐츠 단계에서 문구를 생성하면 여기에 표시됩니다.")

            experiment = st.session_state.copy_experiment_result
            if experiment:
                with st.expander("한글 모델 비교 결과", expanded=False):
                    for item in experiment.get("results", []):
                        st.markdown(f"**{item.get('provider')}** · {item.get('status')}")
                        copy = item.get("copy") or {}
                        if copy:
                            st.write(copy.get("headline", ""))
                            st.caption(" / ".join(copy.get("copies", [])[:2]))
                        elif item.get("error"):
                            st.caption(item["error"])
                        else:
                            st.caption(item.get("model", "not configured"))
