"""이 파일은 Streamlit 공통 UI 컴포넌트를 담당한다."""

from __future__ import annotations

import html
from pathlib import Path

import streamlit as st

from .api_client import fetch_text_asset, reference_thumbnail_bytes
from .constants import POSTER_TEMPLATE_LABELS, POSTER_TEMPLATE_THUMBNAILS, STEP_LABELS

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

def render_reference_grid(references: list[dict], columns: int = 4) -> None:
    """다운로드된 레퍼런스 에셋을 썸네일 grid로 표시한다.

    래스터 이미지는 축소된 `st.image`로 표시하고, 작은 SVG는 직접 삽입한다.
    HTML sanitizer나 data URI 문제를 피하기 위해 `st.columns` 기반으로 배치한다.
    """
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

def render_campaign_studio_header() -> None:
    stage_cards = []
    stage_descriptions = {
        1: "상품명, 가격, 타깃을 정리",
        2: "도면과 키보드 스펙 연결",
        3: "3D 데스크 씬 구성",
        4: "카피, 이미지, 포스터 제작",
    }
    for step_id, label in STEP_LABELS.items():
        active = " active" if step_id == st.session_state.step else ""
        stage_cards.append(
            f'<div class="studio-stage{active}">'
            f'<div class="stage-num">STEP {step_id}</div>'
            f'<div class="stage-title">{html.escape(label)}</div>'
            f'<div class="stage-desc">{html.escape(stage_descriptions[step_id])}</div>'
            f'</div>'
        )

    st.markdown(
        f"""
        <section class="studio-hero">
          <div>
            <div class="studio-kicker">Campaign Production Studio</div>
            <h1>{html.escape(str(st.session_state.product_name))}</h1>
            <p>
              제품 정보와 3D 데스크 씬을 하나의 캠페인 브리프로 묶고,
              광고 문구, 실사 이미지 작업, 포스터 결과물을 같은 화면에서 검수하는 제작형 UI입니다.
            </p>
          </div>
          <div class="studio-brief-card">
            <strong>현재 캠페인 브리프</strong>
            <div class="studio-brief-row"><span>채널</span><span>{html.escape(str(st.session_state.target_channel))}</span></div>
            <div class="studio-brief-row"><span>타깃</span><span>{html.escape(str(st.session_state.target_customer))}</span></div>
            <div class="studio-brief-row"><span>가격</span><span>{html.escape(str(st.session_state.price))}</span></div>
            <div class="studio-brief-row"><span>톤</span><span>{html.escape(str(st.session_state.ad_tone))}</span></div>
          </div>
        </section>
        <div class="studio-pipeline">{''.join(stage_cards)}</div>
        """,
        unsafe_allow_html=True,
    )

def render_studio_status_cards() -> None:
    model_ready = bool(st.session_state.model_url)
    copy_ready = bool(st.session_state.copy_result)
    poster_ready = bool(st.session_state.poster_result)
    image_job = st.session_state.image_job_result or {}
    image_status = (image_job.get("job") or {}).get("status") or "대기"
    cards = [
        ("3D 씬", "생성 완료" if model_ready else "생성 대기", model_ready),
        ("광고 문구", "선택 완료" if copy_ready else "후보 대기", copy_ready),
        ("포스터", "렌더 완료" if poster_ready else f"이미지 {image_status}", poster_ready),
    ]
    st.markdown(
        '<div class="studio-status-grid">'
        + "".join(
            f'<div class="studio-status-card {"ready" if ready else ""}">'
            f'<div class="status-label">{html.escape(label)}</div>'
            f'<div class="status-value">{html.escape(value)}</div>'
            f'</div>'
            for label, value, ready in cards
        )
        + "</div>",
        unsafe_allow_html=True,
    )
