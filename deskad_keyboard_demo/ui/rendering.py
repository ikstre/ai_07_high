"""이 파일은 3D 렌더링과 모델 준비 UI를 담당한다."""

from __future__ import annotations

import base64

import streamlit as st
import streamlit.components.v1 as components

from .api_client import api_post, fetch_binary_data_url

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
    st.session_state.model_url = data["model_url"]
    st.session_state.model_meta = data
