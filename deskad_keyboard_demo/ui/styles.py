"""이 파일은 Streamlit 전역 CSS를 담당한다."""

from __future__ import annotations

import streamlit as st

from .theme import theme_tokens


def render_base_layout_styles() -> None:
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

          .studio-hero {
            display: grid;
            grid-template-columns: minmax(0, 1.4fr) minmax(320px, 0.9fr);
            gap: 18px;
            align-items: stretch;
            margin: 4px 0 18px 0;
            padding: 22px 24px;
            border: 1px solid rgba(15, 23, 42, 0.08);
            border-radius: 14px;
            background:
              radial-gradient(circle at 88% 18%, rgba(14, 165, 233, 0.16), transparent 26%),
              linear-gradient(135deg, #ffffff 0%, #f8fafc 48%, #eef6ff 100%);
            box-shadow: 0 16px 42px rgba(15, 23, 42, 0.08);
          }
          .studio-kicker {
            margin: 0 0 8px 0;
            color: #0f766e;
            font-size: 12px;
            font-weight: 800;
            letter-spacing: 0.08em;
            text-transform: uppercase;
          }
          .studio-hero h1 {
            margin: 0;
            color: #0f172a;
            font-size: 34px;
            line-height: 1.16;
            letter-spacing: 0;
          }
          .studio-hero p {
            max-width: 760px;
            margin: 10px 0 0 0;
            color: #475569;
            font-size: 15px;
            line-height: 1.65;
          }
          .studio-brief-card {
            padding: 16px;
            border: 1px solid rgba(14, 116, 144, 0.18);
            border-radius: 12px;
            background: rgba(255, 255, 255, 0.82);
          }
          .studio-brief-card strong {
            display: block;
            margin-bottom: 8px;
            color: #0f172a;
            font-size: 14px;
          }
          .studio-brief-row {
            display: flex;
            justify-content: space-between;
            gap: 16px;
            padding: 7px 0;
            border-bottom: 1px solid rgba(148, 163, 184, 0.22);
            color: #475569;
            font-size: 13px;
          }
          .studio-brief-row:last-child {
            border-bottom: 0;
          }
          .studio-brief-row span:last-child {
            color: #0f172a;
            font-weight: 700;
            text-align: right;
          }
          .studio-pipeline {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 10px;
            margin: 0 0 16px 0;
          }
          .studio-stage {
            padding: 12px 14px;
            border: 1px solid rgba(148, 163, 184, 0.28);
            border-radius: 12px;
            background: #ffffff;
          }
          .studio-stage .stage-num {
            color: #0f766e;
            font-size: 12px;
            font-weight: 800;
          }
          .studio-stage .stage-title {
            margin-top: 6px;
            color: #0f172a;
            font-size: 14px;
            font-weight: 800;
          }
          .studio-stage .stage-desc {
            margin-top: 4px;
            color: #64748b;
            font-size: 12px;
            line-height: 1.45;
          }
          .studio-stage.active {
            border-color: rgba(14, 165, 233, 0.45);
            background: linear-gradient(180deg, #f0f9ff 0%, #ffffff 100%);
            box-shadow: inset 0 0 0 1px rgba(14, 165, 233, 0.15);
          }
          .creative-strip {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 10px;
            margin: 12px 0;
          }
          .creative-chip {
            padding: 12px;
            border: 1px solid rgba(148, 163, 184, 0.28);
            border-radius: 10px;
            background: #ffffff;
          }
          .creative-chip b {
            display: block;
            margin-bottom: 4px;
            color: #0f172a;
            font-size: 13px;
          }
          .creative-chip span {
            color: #64748b;
            font-size: 12px;
            line-height: 1.45;
          }
          .studio-status-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 10px;
            margin-bottom: 16px;
          }
          .studio-status-card {
            padding: 14px;
            border: 1px solid rgba(148, 163, 184, 0.28);
            border-radius: 12px;
            background: #ffffff;
          }
          .studio-status-card .status-label {
            color: #64748b;
            font-size: 12px;
          }
          .studio-status-card .status-value {
            margin-top: 6px;
            color: #0f172a;
            font-size: 17px;
            font-weight: 800;
          }
          .studio-status-card.ready {
            border-color: rgba(13, 148, 136, 0.36);
            background: #f0fdfa;
          }
          .ad-preview-card {
            min-height: 300px;
            color: #0f172a;
            border: 0;
            border-radius: 14px;
            background:
              linear-gradient(135deg, rgba(15, 23, 42, 0.86), rgba(15, 118, 110, 0.78)),
              linear-gradient(180deg, #ffffff, #e2e8f0);
            box-shadow: 0 18px 46px rgba(15, 23, 42, 0.16);
          }
          .ad-preview-card .template-badge {
            display: inline-flex;
            margin-bottom: 14px;
            padding: 5px 9px;
            border-radius: 999px;
            background: rgba(255, 255, 255, 0.14);
            color: rgba(255, 255, 255, 0.82);
            font-size: 12px;
            font-weight: 700;
          }
          .ad-preview-main {
            display: grid;
            grid-template-columns: minmax(0, 1fr);
            gap: 18px;
          }
          .ad-preview-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 8px;
          }
          .ad-preview-grid span {
            min-height: 58px;
            border-radius: 10px;
            background: rgba(255, 255, 255, 0.22);
          }
          .ad-preview-spec {
            padding: 14px;
            border-radius: 12px;
            background: rgba(255, 255, 255, 0.14);
          }
          .ad-preview-spec strong {
            display: block;
            margin-bottom: 8px;
            color: #bfdbfe;
          }
          .ad-preview-promo {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            padding: 16px;
            border-radius: 12px;
            background: rgba(255, 255, 255, 0.18);
            color: #ffffff;
            font-weight: 800;
          }
          .ad-preview-promo strong {
            font-size: 24px;
          }
          .ad-preview-card--grid_three .ad-preview-main,
          .ad-preview-card--feature_focus .ad-preview-main,
          .ad-preview-card--promo_banner .ad-preview-main {
            grid-template-columns: minmax(0, 1fr) minmax(120px, 0.78fr);
            align-items: start;
          }
          .ad-preview-card--grid_three {
            background:
              linear-gradient(135deg, rgba(15, 23, 42, 0.9), rgba(30, 64, 175, 0.74)),
              linear-gradient(180deg, #ffffff, #dbeafe);
          }
          .ad-preview-card--feature_focus {
            background:
              linear-gradient(135deg, rgba(15, 23, 42, 0.88), rgba(4, 120, 87, 0.72)),
              linear-gradient(180deg, #ffffff, #ccfbf1);
          }
          .ad-preview-card--promo_banner {
            background:
              linear-gradient(135deg, rgba(127, 29, 29, 0.88), rgba(245, 158, 11, 0.78)),
              linear-gradient(180deg, #ffffff, #ffedd5);
          }
          .ad-preview-card h3,
          .ad-preview-card .meta,
          .ad-preview-card li,
          .ad-preview-card .subcopy {
            color: #ffffff;
          }
          .ad-preview-card .meta {
            color: rgba(226, 232, 240, 0.88);
          }
          .ad-preview-card .cta {
            background: #ef4444;
            box-shadow: 0 12px 24px rgba(239, 68, 68, 0.24);
          }
          @media (max-width: 1100px) {
            .studio-hero,
            .studio-pipeline,
            .studio-status-grid {
              grid-template-columns: 1fr;
            }
            .creative-strip {
              grid-template-columns: 1fr;
            }
          }
        </style>
        """,
        unsafe_allow_html=True,
    )

def render_ui_theme_styles(theme_mode: str | None) -> None:
    tokens = theme_tokens(theme_mode)

    st.markdown(
        f"""
        <style>
          .stApp,
          [data-testid="stAppViewContainer"] {{
            background: {tokens["app_bg"]};
            color: {tokens["text"]};
          }}
          [data-testid="stSidebar"],
          [data-testid="stSidebar"] > div {{
            background: {tokens["sidebar_bg"]} !important;
            color: {tokens["sidebar_text"]};
          }}
          [data-testid="stSidebar"] h1,
          [data-testid="stSidebar"] h2,
          [data-testid="stSidebar"] h3,
          [data-testid="stSidebar"] label,
          [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] {{
            color: {tokens["sidebar_text"]} !important;
          }}
          [data-testid="stSidebar"] [data-testid="stCaptionContainer"],
          [data-testid="stSidebar"] small {{
            color: {tokens["sidebar_muted"]} !important;
          }}
          [data-testid="stSidebar"] [data-testid="stExpander"],
          [data-testid="stSidebar"] [data-testid="stExpanderDetails"],
          [data-testid="stSidebar"] [data-testid="stVerticalBlockBorderWrapper"] {{
            background: transparent !important;
            border-color: rgba(248, 251, 255, 0.20) !important;
            color: {tokens["sidebar_text"]} !important;
          }}
          [data-testid="stSidebar"] [data-testid="stExpander"] summary {{
            background: rgba(248, 251, 255, 0.08) !important;
            color: {tokens["sidebar_text"]} !important;
          }}
          [data-testid="stSidebar"] input,
          [data-testid="stSidebar"] textarea,
          [data-testid="stSidebar"] div[data-baseweb="select"] > div {{
            background: rgba(248, 251, 255, 0.10) !important;
            color: {tokens["sidebar_text"]} !important;
            border-color: rgba(248, 251, 255, 0.24) !important;
          }}
          [data-testid="stSidebar"] input,
          [data-testid="stSidebar"] textarea {{
            border: 1.5px solid rgba(248, 251, 255, 0.34) !important;
            caret-color: {tokens["sidebar_text"]} !important;
            box-shadow: inset 0 0 0 1px rgba(0, 0, 0, 0.18) !important;
          }}
          [data-testid="stSidebar"] input:focus,
          [data-testid="stSidebar"] textarea:focus {{
            border-color: #7dd3fc !important;
            box-shadow: 0 0 0 3px rgba(125, 211, 252, 0.20) !important;
          }}
          [data-testid="stSidebar"] span,
          [data-testid="stSidebar"] p {{
            color: {tokens["sidebar_text"]} !important;
          }}
          [data-testid="stHeader"] {{
            background: {tokens["header_bg"]} !important;
            color: {tokens["text"]} !important;
          }}
          [data-testid="stDecoration"] {{
            background: transparent !important;
          }}
          h1, h2, h3, h4, h5, h6,
          label,
          [data-testid="stMarkdownContainer"],
          [data-testid="stText"] {{
            color: {tokens["text"]};
          }}
          [data-testid="stVerticalBlockBorderWrapper"],
          [data-testid="stExpander"],
          [data-testid="stExpanderDetails"] {{
            background: {tokens["surface"]} !important;
            border-color: {tokens["border"]} !important;
            color: {tokens["text"]};
          }}
          [data-testid="stExpander"] summary {{
            background: {tokens["surface_elevated"]} !important;
            color: {tokens["text"]};
          }}
          .stButton > button {{
            border-color: {tokens["border"]};
            background: {tokens["surface"]};
            color: {tokens["text"]};
            border-radius: 8px !important;
            min-width: 100%;
          }}
          .stButton > button p {{
            white-space: normal !important;
            word-break: keep-all !important;
            overflow-wrap: normal !important;
            line-height: 1.35 !important;
            text-align: center;
          }}
          .stButton > button[kind="primary"] {{
            border-color: #ef4444;
            background: #ef4444;
            color: #ffffff;
            border-radius: 8px !important;
          }}
          /* 사이드바 버튼(로그아웃 등): 본문 surface 배경을 그대로 쓰면 사이드바의
             강제 흰 글자와 겹쳐 안 보인다 — 어느 테마 배경에서도 보이는 고스트 버튼. */
          [data-testid="stSidebar"] .stButton > button {{
            background: transparent !important;
            color: {tokens["sidebar_text"]} !important;
            border: 1px solid {tokens["sidebar_muted"]} !important;
          }}
          [data-testid="stSidebar"] .stButton > button:hover {{
            border-color: {tokens["sidebar_text"]} !important;
            background: rgba(127, 127, 127, 0.16) !important;
          }}
          .section-label {{
            color: {tokens["subtle"]};
          }}
          .studio-hero {{
            border-color: {tokens["border"]};
            background: {tokens["hero_bg"]};
            box-shadow: {tokens["hero_shadow"]};
          }}
          .studio-hero h1,
          .studio-brief-card strong,
          .studio-stage .stage-title,
          .creative-chip b,
          .studio-status-card .status-value {{
            color: {tokens["text"]};
          }}
          .studio-hero p,
          .studio-brief-row,
          .studio-stage .stage-desc,
          .creative-chip span,
          .studio-status-card .status-label {{
            color: {tokens["muted"]};
          }}
          .studio-brief-card,
          .studio-stage,
          .creative-chip,
          .studio-status-card,
          .poster-thumb {{
            border-color: {tokens["border"]};
            background: {tokens["surface"]};
          }}
          .studio-brief-row {{
            border-bottom-color: {tokens["border"]};
          }}
          .studio-brief-row span:last-child {{
            color: {tokens["text"]};
          }}
          .studio-stage.active {{
            background: linear-gradient(180deg, {tokens["surface_soft"]} 0%, {tokens["surface"]} 100%);
            border-color: rgba(14, 165, 233, 0.52);
          }}
          .studio-status-card.ready {{
            background: {tokens["ready_bg"]};
          }}
          .step-progress {{
            background: {tokens["surface_soft"]};
            border-color: {tokens["border"]};
          }}
          .metric-chip {{
            color: {tokens["muted"]};
            border-color: {tokens["border"]};
            background: {tokens["surface"]};
          }}
          .ad-preview-card {{
            background: {tokens["preview_bg"]};
          }}
          div[data-baseweb="select"] > div,
          input,
          textarea {{
            background: {tokens["input_bg"]} !important;
            color: {tokens["input_text"]} !important;
            border-color: {tokens["border"]} !important;
          }}
          div[data-baseweb="select"] > div {{
            position: relative !important;
          }}
          div[data-baseweb="select"] input {{
            caret-color: transparent !important;
          }}
          div[data-baseweb="select"] svg {{
            color: {tokens["subtle"]} !important;
            fill: {tokens["subtle"]} !important;
          }}
          [data-testid="stSidebar"] div[data-baseweb="select"] svg {{
            color: {tokens["sidebar_muted"]} !important;
            fill: {tokens["sidebar_muted"]} !important;
          }}
          input,
          textarea {{
            border: 1.5px solid rgba(61, 88, 115, 0.42) !important;
            caret-color: {tokens["input_text"]} !important;
            box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.45);
          }}
          input:focus,
          textarea:focus,
          input:focus-visible,
          textarea:focus-visible {{
            border-color: #0ea5e9 !important;
            box-shadow:
              0 0 0 3px rgba(14, 165, 233, 0.18),
              inset 0 0 0 1px rgba(255, 255, 255, 0.62) !important;
            outline: none !important;
          }}
          div[data-baseweb="select"] input,
          div[data-baseweb="select"] input:focus,
          div[data-baseweb="select"] input:focus-visible {{
            width: 1px !important;
            min-width: 1px !important;
            padding: 0 !important;
            border: 0 !important;
            background: transparent !important;
            color: transparent !important;
            caret-color: transparent !important;
            box-shadow: none !important;
            outline: none !important;
          }}
          textarea::placeholder,
          input::placeholder {{
            color: {tokens["subtle"]} !important;
          }}
          pre,
          code,
          [data-testid="stJson"],
          [data-testid="stJson"] *,
          [data-testid="stCodeBlock"],
          [data-testid="stCodeBlock"] * {{
            background: {tokens["code_bg"]} !important;
            color: {tokens["code_text"]} !important;
            border-color: {tokens["border"]} !important;
          }}
          [data-baseweb="popover"],
          [data-baseweb="popover"] > div,
          [data-baseweb="menu"],
          [role="listbox"] {{
            background: {tokens["menu_bg"]} !important;
            color: {tokens["menu_text"]} !important;
            border-color: {tokens["border"]} !important;
          }}
          [data-baseweb="menu"] li,
          [role="option"] {{
            background: {tokens["menu_bg"]} !important;
            color: {tokens["menu_text"]} !important;
          }}
          [data-baseweb="menu"] li:hover,
          [data-baseweb="menu"] li[aria-selected="true"],
          [role="option"]:hover,
          [role="option"][aria-selected="true"] {{
            background: {tokens["menu_hover"]} !important;
            color: {tokens["menu_text"]} !important;
          }}
        </style>
        """,
        unsafe_allow_html=True,
    )
