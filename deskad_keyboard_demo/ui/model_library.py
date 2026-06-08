"""이 파일은 모델 라이브러리 UI를 담당한다."""

from __future__ import annotations

import time

import streamlit as st

from .api_client import fetch_model_library
from .rendering import prepare_library_model, render_model_viewer

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
