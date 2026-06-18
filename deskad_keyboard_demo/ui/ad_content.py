"""이 파일은 광고 콘텐츠 생성 UI를 담당한다."""

from __future__ import annotations

import html
import time

import streamlit as st

from .api_client import api_get, api_post
from .constants import IMAGE_JOB_TERMINAL_STATUSES, POSTER_TEMPLATE_LABELS, PROVIDER_LABELS
from .formatting import format_price_display
from .progress import run_with_live_progress
from .rendering import build_render_payload

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

def has_completed_image_job() -> bool:
    """완료된 실사 이미지 작업이 있는지 — 포스터 생성 순서 강제(2026-06-12 QA)에 사용."""
    return current_image_job_id() is not None

def build_ad_payload() -> dict:
    payload = {
        **build_render_payload(),
        "product_name": st.session_state.product_name,
        "product_type": st.session_state.product_type,
        "price": st.session_state.price,
        "target_channel": st.session_state.target_channel,
        "target_customer": st.session_state.target_customer,
        "selling_point": st.session_state.selling_point,
        "product_detail": st.session_state.get("product_detail", ""),
        "ad_tone": st.session_state.ad_tone,
        "shot_type": st.session_state.get("shot_type", ""),
        "image_ratio": st.session_state.image_ratio,
        "extra_request": st.session_state.extra_request,
        "model_url": st.session_state.model_url,
        "reference_asset_path": st.session_state.selected_reference_path,
        "image_job_id": current_image_job_id(),
        "image_workflow": st.session_state.image_workflow,
        "poster_template": st.session_state.poster_template,
        "engine": st.session_state.get("engine", "local"),
        "engine_model_tier": st.session_state.get("engine_model_tier", "general"),
    }
    # 셋업 구도 맵을 img2img 기준으로 주입(reference_image_b64는 선택 도면보다 우선).
    # 토글이 켜져 있고 셋업이 렌더된 경우에만 → 실제 배치 구도가 결과에 반영된다.
    if st.session_state.get("use_setup_composition", True):
        composition = st.session_state.get("setup_composition_b64")
        if composition:
            payload["reference_image_b64"] = composition
            payload["reference_image_topdown_b64"] = st.session_state.get("setup_composition_topdown_b64")
            payload["reference_is_composition"] = True
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
        "copies": list(copy_result.get("copies") or []),
        "hashtags": list(copy_result.get("hashtags") or []),
        "spec_bullets": list(copy_result.get("spec_bullets") or []),
    }
    if not selected["headline"] and not selected["copies"]:
        return None
    return selected

def first_successful_copy(experiment_result: dict | None) -> tuple[str | None, dict | None]:
    if not isinstance(experiment_result, dict):
        return None, None
    for item in experiment_result.get("results") or []:
        if item.get("status") != "ok":
            continue
        copy = item.get("copy")
        if not isinstance(copy, dict):
            continue
        provider = item.get("provider") or copy.get("provider")
        selected = selected_copy_payload({**copy, "provider": provider})
        if selected:
            return provider, selected
    return None, None

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
        st.text_area("헤드라인", key="copy_editor_headline", height=68)
        st.text_area("서브카피", key="copy_editor_subcopy", height=120)
        st.text_input("CTA", key="copy_editor_cta")
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

def generate_copy() -> None:
    st.session_state.copy_result = api_post("/ai/copy", build_ad_payload(), timeout=180)
    st.session_state.copy_selected_provider = st.session_state.copy_result.get("provider")

def generate_copy_experiment() -> None:
    # 텍스트 provider를 같은 입력으로 나란히 비교한다. 미설정 provider는
    # not_configured로 표시돼 어떤 모델이 활성인지 한눈에 보인다.
    payload = {**build_ad_payload(), "providers": ["openai", "hyperclova", "local", "kanana", "midm", "fallback"]}
    st.session_state.copy_experiment_result = api_post("/ai/copy/experiment", payload, timeout=300)
    provider, selected = first_successful_copy(st.session_state.copy_experiment_result)
    st.session_state.copy_result = selected
    st.session_state.copy_selected_provider = provider


def _apply_copy_variants_result(data: dict) -> None:
    st.session_state.copy_experiment_result = data
    provider, selected = first_successful_copy(data)
    st.session_state.copy_result = selected
    st.session_state.copy_selected_provider = provider


def generate_copy_variants() -> None:
    # 선택한 엔진에서 문구 후보를 뽑아 나란히 비교/선택한다.
    # Local+ComfyUI는 HyperCLOVA/base/Kanana/Mi:dm provider별 후보를 반환한다.
    _apply_copy_variants_result(api_post("/ai/copy/variants", build_ad_payload(), timeout=900))


def generate_copy_variants_live(slot) -> None:
    """버튼 슬롯을 실시간 게이지로 바꿔가며 문구 변형을 생성한다."""
    payload = build_ad_payload()
    expected = {"local": 180, "openai": 30}.get(
        str(st.session_state.get("engine") or ""), 90
    )
    data = run_with_live_progress(
        slot,
        lambda: api_post("/ai/copy/variants", payload, timeout=900),
        label="광고 문구 생성 중",
        expected_seconds=expected,
    )
    _apply_copy_variants_result(data)


def _apply_poster_result(data: dict) -> None:
    st.session_state.poster_result = data
    st.session_state.copy_result = data["copy"]
    st.session_state.copy_selected_provider = data["copy"].get("provider")


def generate_poster(include_completed_image: bool = True) -> None:
    payload = build_ad_payload()
    if not include_completed_image:
        payload["image_job_id"] = None
    _apply_poster_result(api_post("/ai/poster", payload, timeout=300))


def generate_poster_live(slot, include_completed_image: bool = True) -> None:
    """버튼 슬롯을 실시간 게이지로 바꿔가며 포스터를 생성한다."""
    payload = build_ad_payload()
    if not include_completed_image:
        payload["image_job_id"] = None
    # 문구가 이미 선택돼 있으면 SVG 합성 위주(빠름), 아니면 copy 생성이 포함된다.
    expected = 20 if payload.get("selected_copy") else 90
    data = run_with_live_progress(
        slot,
        lambda: api_post("/ai/poster", payload, timeout=300),
        label="포스터 생성 중",
        expected_seconds=expected,
    )
    _apply_poster_result(data)


def generate_image_job(force_regen: bool = False) -> dict:
    # force_regen=True는 캐시를 건너뛰고 같은 조건으로 새로 생성한다(결과 불만족 시
    # 재시도 UX — 2026-06-11 이미지 QA). 서버/워커가 seed를 랜덤화하므로 새 결과가 나온다.
    path = "/ai/image/jobs?force_regen=true" if force_regen else "/ai/image/jobs"
    payload = build_ad_payload()
    data = api_post(path, payload, timeout=180)
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
    return data

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
    # grid 3컷처럼 여러 장을 순차 생성하는 job은 장수만큼 대기 예산을 늘린다
    # (backend stale 판정과 같은 산식 — 기본 600s로는 3컷 ~840s+를 못 기다린다).
    try:
        image_count = max(1, int(job.get("requested_image_count") or 1))
    except (TypeError, ValueError):
        image_count = 1
    timeout = int(st.session_state.image_poll_timeout_seconds) * image_count
    if elapsed > timeout:
        st.session_state.image_polling_enabled = False
        st.session_state.image_poll_started_at = None
        st.warning(f"이미지 작업 자동 갱신이 {timeout}초를 초과해 중단되었습니다.")
        st.rerun()
        return

    # 엔진별 통상 소요(초). 정확한 ETA가 아니라 "얼마나 기다리는 게 정상인지"의
    # 기준선 — 게이지는 97%에서 멈춰 완료를 단정하지 않는다(2026-06-11 이미지 QA).
    expected = {"hyperclova_image": 300, "comfyui": 120, "openai_image": 90}.get(
        str(job.get("provider") or ""), 180
    ) * image_count
    status_slot = st.empty()
    with status_slot.container(border=True):
        shot_jobs = job.get("comfyui_shot_jobs") or []
        if shot_jobs:
            # 작업 기반 진행: 시점별 컷이 몇 개 끝났는지(시간 추정이 아니라 실제 진척).
            total = len(shot_jobs)
            done = sum(1 for s in shot_jobs if s.get("status") == "completed")
            running = sum(1 for s in shot_jobs if s.get("status") == "running")
            frac = min((done + 0.5 * running) / max(total, 1), 0.97)
            st.progress(frac, text=f"이미지 생성 · 시점별 {done}/{total}컷 완료 ({int(elapsed)}초 경과)")
            icon = {"completed": "✅", "running": "🟢", "queued": "⏳", "pending": "·", "error": "⚠️"}
            st.caption(
                " · ".join(
                    f"{icon.get(s.get('status'), '·')} {s.get('label') or s.get('shot_type')}"
                    for s in shot_jobs
                )
            )
        else:
            # 단일 이미지는 작업 단위 신호가 없어 시간 추정 게이지(명시적으로 '추정'이라 표기).
            stage = {"created": "준비 중", "queued": "큐 대기 중", "running": "생성 중"}.get(
                str(job.get("status")), str(job.get("status", "진행 중"))
            )
            st.progress(
                min(elapsed / expected, 0.97),
                text=f"이미지 {stage} · {int(elapsed)}초 경과 (시간 추정 · 보통 ~{expected}초)",
            )
            if job.get("message"):
                st.caption(str(job["message"]))
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
        if st.session_state.get("auto_poster_after_image"):
            # 포스터 버튼이 이미지보다 먼저 눌린 경우의 예약 — 이미지 완료 즉시 포스터까지 이어서 생성(2026-06-12 QA).
            st.session_state.auto_poster_after_image = False
            try:
                generate_poster()
                st.success("이미지 완료 — 포스터까지 자동 생성했습니다.")
            except Exception as exc:
                st.error(f"포스터 자동 생성 실패: {exc} — '포스터 생성' 버튼으로 다시 시도하세요.")
        else:
            st.success("이미지 작업 완료. '포스터 생성'을 누르면 이미지가 합성됩니다.")
        st.rerun()
    elif updated.get("status") in IMAGE_JOB_TERMINAL_STATUSES:
        st.session_state.image_polling_enabled = False
        st.session_state.image_poll_started_at = None
        if st.session_state.get("auto_poster_after_image"):
            st.session_state.auto_poster_after_image = False
            st.error("이미지 작업이 실패해 포스터 자동 생성을 취소했습니다. 이미지 재생성 후 다시 시도하세요.")
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
        # 변형 모드(같은 엔진의 여러 후보)면 "변형 N"으로, 비교 모드면 엔진명으로 라벨링한다.
        if item.get("variant") is not None:
            label = f"변형 {int(item['variant']) + 1} · {provider_label(provider)}"
        else:
            label = provider_label(provider)
        model_name = item.get("model") or item.get("runtime_name")
        if model_name:
            label += f" · {model_name}"
        status = item.get("status", "unknown")
        elapsed_ms = item.get("elapsed_ms")
        # 응답 속도는 평가 기준(응답 속도/부하)이므로 후보 카드에 함께 노출한다.
        speed_note = ""
        if isinstance(elapsed_ms, (int, float)) and status == "ok":
            speed_note = " · 캐시" if item.get("cache_hit") else f" · {elapsed_ms/1000:.1f}s"
        copy = item.get("copy") or {}
        with st.container(border=True):
            head_col, action_col = st.columns([0.78, 0.22])
            with head_col:
                st.caption(f"{label} · {status}{speed_note}")
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


def render_compact_copy_candidates(limit: int = 4) -> None:
    experiment = st.session_state.copy_experiment_result
    if not experiment:
        st.caption("광고 문구를 생성하면 후보가 여기에 표시됩니다.")
        return

    results = experiment.get("results") or []
    if not results:
        st.caption("생성 후보가 없습니다.")
        return

    selected_provider = st.session_state.get("copy_selected_provider")
    current = st.session_state.copy_result or {}
    shown = 0
    for index, item in enumerate(results):
        copy = item.get("copy") or {}
        if not copy:
            continue
        provider = item.get("provider", "unknown")
        label = provider_label(provider)
        is_selected = (
            selected_provider == provider
            and current.get("headline") == copy.get("headline")
            and current.get("subcopy") == copy.get("subcopy")
        )
        shown += 1
        with st.container(border=True):
            st.caption(f"{label} · {item.get('status', 'unknown')}")
            st.markdown(f"**{copy.get('headline') or '제목 없음'}**")
            subcopy = str(copy.get("subcopy") or "")
            if subcopy:
                st.caption(subcopy[:90] + ("..." if len(subcopy) > 90 else ""))
            button_label = "선택됨" if is_selected else "이 문구 사용"
            if st.button(
                button_label,
                key=f"use_compact_copy_{index}_{provider}",
                type="primary" if is_selected else "secondary",
                use_container_width=True,
                disabled=is_selected,
            ):
                selected = selected_copy_payload({**copy, "provider": copy.get("provider") or provider})
                if selected:
                    st.session_state.copy_result = selected
                    st.session_state.copy_selected_provider = provider
                    st.rerun()
        if shown >= limit:
            break

    if shown == 0:
        st.caption("사용 가능한 문구 후보가 없습니다.")


def render_ad_card_preview_section() -> None:
    with st.container():
        st.markdown("#### 광고 카드 미리보기")
        result = st.session_state.copy_result or {}
        product_name = str(st.session_state.get("product_name") or "").strip() or "상품명을 입력해주세요"
        selling_point = str(st.session_state.get("selling_point") or "").strip()
        price = format_price_display(st.session_state.get("price"))
        target_channel = str(st.session_state.get("target_channel") or "").strip() or "채널 미입력"
        headline = result.get("headline") or product_name
        subcopy = result.get("subcopy") or selling_point or "핵심 특징을 입력하면 광고 문구가 표시됩니다."
        cta = result.get("cta") or "자세히 보기"
        copies = result.get("copies") or []
        bullet_html = "".join(f"<li>{html.escape(str(copy))}</li>" for copy in copies[:3] if str(copy).strip())
        if not bullet_html:
            fallback_bullet = selling_point or "상품의 장점을 입력하면 여기에 표시됩니다."
            bullet_html = f"<li>{html.escape(fallback_bullet)}</li>"
        template_key = st.session_state.get("poster_template", "minimal_card")
        template_label = POSTER_TEMPLATE_LABELS.get(template_key, template_key)
        template_note = html.escape(str(template_label).split(" (")[0])
        side_panel = ""
        if template_key == "grid_three":
            product_tile = html.escape(product_name[:22])
            selling_tile = html.escape((selling_point or "핵심 특징 입력 대기")[:28])
            channel_tile = html.escape(target_channel[:18])
            side_panel = f"""
              <div class="ad-preview-grid-panel" aria-label="grid template preview">
                <div class="ad-preview-grid-hero">
                  <span>FEATURED SETUP</span>
                  <strong>{product_tile}</strong>
                </div>
                <div class="ad-preview-grid-shots">
                  <div class="grid-shot grid-shot-product">
                    <b>제품</b>
                    <span>{product_tile}</span>
                  </div>
                  <div class="grid-shot grid-shot-space">
                    <b>공간</b>
                    <span>{channel_tile}</span>
                  </div>
                  <div class="grid-shot grid-shot-point">
                    <b>포인트</b>
                    <span>{selling_tile}</span>
                  </div>
                </div>
                <div class="ad-preview-grid-note">
                  <b>3컷 구성</b>
                  <small>제품, 사용 환경, 핵심 포인트를 각각 분리해 비교합니다.</small>
                </div>
              </div>
            """
        elif template_key == "feature_focus":
            side_panel = f"""
              <aside class="ad-preview-spec">
                <strong>SPECS</strong>
                <ul>{bullet_html}</ul>
              </aside>
            """
        elif template_key == "promo_banner":
            side_panel = f"""
              <div class="ad-preview-promo">
                <strong>{html.escape(price)}</strong>
                <span>{html.escape(target_channel)}</span>
              </div>
            """
        st.markdown(
            f"""
            <div class="ad-preview-card ad-preview-card--{html.escape(str(template_key))}">
              <div class="template-badge">{template_note}</div>
              <div class="ad-preview-main">
                <div>
                  <h3>{html.escape(str(headline))}</h3>
                  <p class="subcopy">{html.escape(str(subcopy))}</p>
                  <ul>{bullet_html}</ul>
                  <div class="meta">{html.escape(price)} · {html.escape(target_channel)}</div>
                  <span class="cta">{html.escape(str(cta))}</span>
                </div>
                {side_panel}
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    if st.session_state.copy_experiment_result:
        render_copy_experiment_picker()
    else:
        st.markdown("#### 문구 후보")
        st.caption("광고 콘텐츠 단계에서 문구를 생성하면 후보가 여기에 표시됩니다.")

    st.markdown("#### 선택 문구")
    result = st.session_state.copy_result
    if result:
        st.caption(f"선택 provider: {provider_label(st.session_state.get('copy_selected_provider') or result.get('provider'))}")
        with st.expander("선택 문구 편집", expanded=False):
            render_copy_inline_editor(result)
        for copy in result.get("copies", [])[:3]:
            st.write(f"- {copy}")
        st.caption(" ".join(result.get("hashtags", [])))
        if result.get("error"):
            st.caption(f"fallback note: {result['error']}")
    else:
        if st.session_state.copy_experiment_result:
            st.caption("광고 콘텐츠 단계의 후보 카드에서 사용할 문구를 선택하세요.")
        else:
            st.caption("광고 콘텐츠 단계에서 문구를 생성하면 여기에 표시됩니다.")
