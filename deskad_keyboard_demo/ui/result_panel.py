"""이 파일은 결과 패널 렌더링 UI를 담당한다."""

from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components

from ppt_export import build_poster_pptx
from ui_steps import render_step_input_panel

from .ad_content import (
    auto_poll_image_job,
    current_product_export_payload,
    refresh_image_job,
    render_ad_card_preview_section,
    render_copy_experiment_picker,
)
from .api_client import api_post, fetch_text_asset, poster_preview_height, responsive_svg_document
from .components import render_studio_status_cards
from .constants import IMAGE_JOB_TERMINAL_STATUSES, KEYBOARD_SIZE_INFO, MONITOR_SIZES, POSTER_TEMPLATE_LABELS
from .rendering import build_render_payload, render_desk_setup, render_model_viewer


def render_result_panel(ctx: dict, go_previous, go_next) -> None:
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
                render_step_input_panel(ctx)
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
                    started_at = job.get("created_at")
                    finished_at = job.get("completed_at")
                    elapsed_note = ""
                    if isinstance(started_at, (int, float)) and isinstance(finished_at, (int, float)) and finished_at >= started_at:
                        elapsed_note = f" · 생성 {int(finished_at - started_at)}초"
                    st.caption(
                        f"{job.get('provider', 'fallback')} · {job.get('status', 'unknown')} · "
                        f"{job.get('width', '')}×{job.get('height', '')}{elapsed_note}"
                    )
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
            render_ad_card_preview_section()
            render_copy_experiment_picker()
