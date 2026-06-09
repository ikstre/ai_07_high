"""이 파일은 광고 콘텐츠 생성 UI를 담당한다."""

from __future__ import annotations

import html
import time

import streamlit as st

from .api_client import api_get, api_post
from .constants import IMAGE_JOB_TERMINAL_STATUSES, PROVIDER_LABELS
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
        "image_workflow": st.session_state.image_workflow,
        "poster_template": st.session_state.poster_template,
        "engine": st.session_state.get("engine", "hyperclova"),
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

def generate_copy() -> None:
    st.session_state.copy_result = api_post("/ai/copy", build_ad_payload(), timeout=180)
    st.session_state.copy_selected_provider = st.session_state.copy_result.get("provider")

def generate_copy_experiment() -> None:
    # 3개 평가 트랙(엔진)을 항상 같은 입력으로 나란히 비교한다. 미설정 엔진은
    # not_configured로 표시돼 어떤 트랙이 활성인지 한눈에 보인다.
    payload = {**build_ad_payload(), "providers": ["openai", "hyperclova", "local", "fallback"]}
    st.session_state.copy_experiment_result = api_post("/ai/copy/experiment", payload, timeout=300)
    st.session_state.copy_result = None
    st.session_state.copy_selected_provider = None

def generate_poster() -> None:
    data = api_post("/ai/poster", build_ad_payload(), timeout=300)
    st.session_state.poster_result = data
    st.session_state.copy_result = data["copy"]
    st.session_state.copy_selected_provider = data["copy"].get("provider")

def generate_image_job() -> None:
    data = api_post("/ai/image/jobs", build_ad_payload(), timeout=180)
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

def render_ad_card_preview_section() -> None:
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
            st.caption(f"선택 provider: {provider_label(st.session_state.get('copy_selected_provider') or result.get('provider'))}")
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
