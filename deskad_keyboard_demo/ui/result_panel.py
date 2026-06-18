"""DeskAd AI Studio의 단계별 결과/편집 패널을 렌더링한다."""

from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components

from .steps import render_step_input_panel

from .constants import IMAGE_JOB_TERMINAL_STATUSES, KEYBOARD_SIZE_INFO, MONITOR_SIZES, POSTER_TEMPLATE_LABELS, STEP_LABELS


def _render_stage_header(current_step: int) -> None:
    top_a, top_b, top_c = st.columns([0.45, 0.32, 0.23])
    with top_a:
        if current_step < 3:
            st.markdown("### 캠페인 입력 현황")
            st.caption("상품 정보와 도면/제품 데이터를 먼저 정리한 뒤 3D 셋업 단계로 이동합니다.")
        elif current_step == 3:
            st.markdown("### 가상 데스크 셋업 결과")
            st.caption("도면/규격 JSON과 3D 셋업 미리보기를 확인합니다.")
        else:
            st.markdown("### 광고 콘텐츠 미리보기")
            st.caption("선택한 톤, 비율, 템플릿을 기준으로 광고 결과를 확인합니다.")

    if current_step >= 3:
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
                    from .rendering import render_desk_setup

                    render_desk_setup()
                    st.rerun()
                except Exception as exc:
                    st.error(f"실패: {exc}")


def _render_navigation(go_previous, go_next) -> None:
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


def _render_edit_panel(ctx: dict, go_previous, go_next) -> None:
    st.markdown("### 선택 편집")
    with st.container(border=True):
        render_step_input_panel(ctx)
        _render_navigation(go_previous, go_next)


def _render_input_guide(current_step: int) -> None:
    with st.container(border=True):
        st.markdown(f"#### {STEP_LABELS[current_step]} 단계")
        if current_step == 1:
            st.write("상품명, 가격, 판매 채널, 타깃 고객, 핵심 특징만 먼저 정리합니다.")
            st.caption("이 정보는 이후 3D 셋업과 광고 콘텐츠의 기본 브리프로 사용됩니다.")
        else:
            st.write("도면/제품 데이터와 참조 모델을 확인합니다.")
            st.caption("3D 미리보기와 렌더링 액션은 다음 단계인 가상 셋업에서 표시됩니다.")


def _render_setup_preview() -> None:
    st.markdown("### 3D 셋업")
    if st.session_state.model_url:
        from .rendering import render_model_viewer

        render_model_viewer(st.session_state.model_url, height=540)
        if st.session_state.model_meta:
            with st.expander("현재 셋업 메타데이터", expanded=False):
                st.json(st.session_state.model_meta)
    else:
        with st.container(border=True):
            st.markdown("#### 3D 셋업이 아직 없습니다")
            st.write("오른쪽 편집 패널에서 셋업 옵션을 확인한 뒤 3D 결과를 생성하세요.")
            st.caption("생성된 결과는 이 영역에 바로 표시되고, 이후 콘텐츠 제작 단계에 연결됩니다.")


def _poster_status_badge(poster: dict) -> str:
    template_label = POSTER_TEMPLATE_LABELS.get(poster.get("poster_template", ""), poster.get("poster_template", ""))
    image_reference = poster.get("image_reference") or poster.get("local_image_reference") or {}
    badge = f"`{template_label}`"
    if poster.get("image_embedded"):
        badge += " · 이미지 합성"
    elif image_reference.get("error"):
        badge += " · 이미지 생성 오류"
    return badge


def _render_poster_downloads(poster: dict, poster_svg: str) -> None:
    download_a, download_b = st.columns(2)
    download_a.download_button(
        "포스터 다운로드 (SVG)",
        data=poster_svg,
        file_name=f"deskad_poster_{poster.get('poster_template', 'minimal_card')}.svg",
        mime="image/svg+xml",
        use_container_width=True,
    )
    try:
        from .ppt_export import build_poster_pptx
        from .ad_content import current_product_export_payload

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


def _render_poster_result(poster: dict) -> None:
    from .api_client import fetch_text_asset, poster_preview_height, responsive_svg_document

    st.success("포스터 생성 완료")
    st.markdown("#### 포스터 미리보기")
    st.caption(_poster_status_badge(poster))
    poster_svg = fetch_text_asset(poster["poster_url"])
    components.html(
        responsive_svg_document(poster_svg),
        height=poster_preview_height(poster_svg),
        scrolling=False,
    )
    _render_poster_downloads(poster, poster_svg)


def _render_ad_preview() -> None:
    from .ad_content import auto_poll_image_job, render_ad_card_preview_section
    from .components import render_studio_status_cards

    st.markdown("### 광고 미리보기")
    # 이미지 생성 진행 게이지는 접힌 '작업 상세' expander가 아니라 결과를 기다리며
    # 보고 있는 미리보기 상단에 표시한다(2026-06-12 QA: 로딩바 가시성).
    auto_poll_image_job()
    render_studio_status_cards()

    poster = st.session_state.poster_result
    if poster:
        _render_poster_result(poster)
        with st.expander("광고 카드 / 문구 미리보기", expanded=False):
            render_ad_card_preview_section()
    else:
        render_ad_card_preview_section()
        st.caption("포스터를 생성하면 이 영역에 결과가 표시됩니다.")


def _render_step_content(ctx: dict, go_previous, go_next) -> None:
    current_step = int(st.session_state.step)

    if current_step < 3:
        _render_edit_panel(ctx, go_previous, go_next)
        return

    if current_step == 3:
        preview_col, edit_col = st.columns([0.68, 0.32], gap="large")
        with preview_col:
            _render_setup_preview()
        with edit_col:
            _render_edit_panel(ctx, go_previous, go_next)
        return

    preview_col, edit_col = st.columns([0.52, 0.48], gap="large")
    with preview_col:
        _render_ad_preview()
    with edit_col:
        _render_edit_panel(ctx, go_previous, go_next)


def _render_poster_details() -> None:
    from .ad_content import generate_image_job, refresh_image_job
    from .api_client import api_post

    with st.expander("포스터 / 이미지 작업 상세", expanded=False):
        st.markdown("### 포스터 작업 상세")
        poster = st.session_state.poster_result
        if poster:
            image_reference = poster.get("image_reference") or poster.get("local_image_reference") or {}
            st.caption(_poster_status_badge(poster))

            with st.expander("이미지 생성 프롬프트", expanded=False):
                st.write(poster["image_prompt"])
            if image_reference:
                with st.expander("이미지 모델 응답", expanded=False):
                    st.json(image_reference)
        else:
            st.caption("포스터 생성 후 프롬프트와 이미지 상세 정보가 표시됩니다.")

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
                col_refresh, col_regen, col_quality = st.columns(3)
                if col_refresh.button("이미지 작업 상태 갱신", use_container_width=True):
                    try:
                        refresh_image_job()
                        st.rerun()
                    except Exception as exc:
                        st.error(f"상태 확인 실패: {exc}")
                if col_regen.button(
                    "같은 조건으로 다시 생성",
                    use_container_width=True,
                    disabled=job.get("status") not in IMAGE_JOB_TERMINAL_STATUSES,
                ):
                    try:
                        generate_image_job(force_regen=True)
                        st.rerun()
                    except Exception as exc:
                        st.error(f"재생성 실패: {exc}")
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
                st.caption(
                    "완료된 이미지 작업은 다음 포스터 생성 시 자동 합성 후보로 사용됩니다. "
                    "결과가 마음에 들지 않으면 '같은 조건으로 다시 생성'(새 seed) 또는 포스터 템플릿 변경 후 재생성을 사용하세요."
                )
            elif job.get("status") == "failed":
                st.warning(
                    "이미지 생성에 실패했습니다. '같은 조건으로 다시 생성'을 누르면 새로운 seed로 재시도합니다."
                )
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


def render_result_panel(ctx: dict, go_previous, go_next) -> None:
    st.markdown('<div class="section-label">RESULT CANVAS / primary</div>', unsafe_allow_html=True)
    with st.container(border=True):
        current_step = int(st.session_state.step)
        _render_stage_header(current_step)
        st.divider()
        _render_step_content(ctx, go_previous, go_next)
        if current_step >= 4:
            st.divider()
            _render_poster_details()
