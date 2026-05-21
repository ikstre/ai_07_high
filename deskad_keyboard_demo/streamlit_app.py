from urllib.parse import quote

import requests
import streamlit as st


API_BASE = "http://127.0.0.1:8000"


st.set_page_config(
    page_title="DeskAd AI Studio",
    layout="wide",
    initial_sidebar_state="expanded",
)


st.markdown(
    """
    <style>
      .block-container {
        max-width: 1680px;
        padding-top: 2rem;
        padding-bottom: 2rem;
        padding-left: 3rem;
        padding-right: 3rem;
      }

      [data-testid="stSidebar"] {
        width: 300px !important;
        min-width: 300px !important;
      }

      [data-testid="stSidebar"] > div {
        width: 300px !important;
      }

      .app-shell {
        display: flex;
        gap: 24px;
        align-items: flex-start;
      }

      .section-label {
        font-size: 12px;
        line-height: 1;
        letter-spacing: 0;
        color: #6b7280;
        margin-bottom: 6px;
      }

      .panel-title {
        font-size: 18px;
        font-weight: 700;
        margin: 0 0 12px 0;
      }

      .input-card {
        width: 620px;
        height: 500px;
        overflow-y: auto;
        border: 1px solid rgba(148, 163, 184, 0.28);
        border-radius: 8px;
        padding: 14px 14px 6px 14px;
        background: rgba(255, 255, 255, 0.04);
      }

      .result-frame {
        width: 100%;
        max-width: 1000px;
        min-height: 1000px;
        border: 1px solid rgba(148, 163, 184, 0.3);
        border-radius: 8px;
        padding: 14px;
        background: rgba(255, 255, 255, 0.035);
      }

      .metric-chip {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 6px 10px;
        border: 1px solid rgba(148, 163, 184, 0.28);
        border-radius: 999px;
        font-size: 12px;
        color: #94a3b8;
        margin-right: 6px;
      }

      div[data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 8px;
      }

      iframe {
        border-radius: 8px;
      }
    </style>
    """,
    unsafe_allow_html=True,
)


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
    "model_url": None,
    "model_meta": None,
    "copy_result": None,
}

for key, value in DEFAULTS.items():
    st.session_state.setdefault(key, value)

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
}


def sync_layout_from_model() -> None:
    defaults = KEYBOARD_MODEL_DEFAULTS.get(st.session_state.keyboard_model)
    if defaults:
        st.session_state.layout = defaults["layout"]


def sync_step_from_sidebar() -> None:
    st.session_state.step = st.session_state.step_selector


def render_model_viewer(model_url: str, height: int = 760) -> None:
    viewer_url = f"{API_BASE}/viewer?model_url={quote(model_url, safe='')}"
    st.iframe(viewer_url, height=height)


def build_payload() -> dict:
    return {
        "layout": st.session_state.layout,
        "case_color": st.session_state.case_color,
        "keycap_color": st.session_state.keycap_color,
        "accent_keycap_color": st.session_state.accent_keycap_color,
        "deskmat_color": st.session_state.deskmat_color,
        "desk_color": st.session_state.desk_color,
        "mouse_color": st.session_state.mouse_color,
        "theme": st.session_state.theme,
    }


def render_keyboard_preview() -> None:
    response = requests.post(
        f"{API_BASE}/render/keyboard-preview",
        json=build_payload(),
        timeout=20,
    )
    response.raise_for_status()
    data = response.json()
    st.session_state.model_url = data["model_url"]
    st.session_state.model_meta = data


def generate_copy() -> None:
    response = requests.post(
        f"{API_BASE}/ai/copy",
        json=build_payload(),
        timeout=20,
    )
    response.raise_for_status()
    st.session_state.copy_result = response.json()


def go_next() -> None:
    if st.session_state.step == 2:
        render_keyboard_preview()
    st.session_state.step = min(4, st.session_state.step + 1)


with st.sidebar:
    st.markdown("## DeskAd AI")
    st.caption("도면 기반 3D 셋업 + 광고 콘텐츠 생성")

    st.divider()

    st.markdown("### 작업 단계")
    step_labels = {
        1: "상품 정보",
        2: "도면/제품 데이터",
        3: "가상 셋업",
        4: "광고 콘텐츠",
    }
    st.session_state.step = st.radio(
        "현재 단계",
        options=list(step_labels.keys()),
        format_func=lambda value: f"{value}. {step_labels[value]}",
        label_visibility="collapsed",
        key="step_selector",
        on_change=sync_step_from_sidebar,
    )

    st.divider()

    with st.expander("도면 데이터", expanded=True):
        st.checkbox("키보드 하우징", value=True)
        st.checkbox("KiSwitch 스위치 footprint", value=True)
        st.checkbox("Tsuki 60% PCB", value=True)
        st.checkbox("키캡/플레이트", value=True)
        st.checkbox("데스크매트", value=True)
        st.checkbox("마우스", value=True)
        st.checkbox("모니터/조명/소품", value=False)

    with st.expander("렌더링 설정", expanded=True):
        st.selectbox("렌더 모드", ["preview", "final"], index=0)
        st.selectbox("카메라", ["three_quarter_top", "top_view", "front"], index=0)
        st.checkbox("scene_hash 캐시 사용", value=True)

    with st.expander("광고 산출물", expanded=False):
        st.checkbox("SNS 카드", value=True)
        st.checkbox("상세페이지 배너", value=True)
        st.checkbox("광고 문구", value=True)
        st.checkbox("PPT 자료", value=False)

    st.divider()
    st.caption("사이드바는 Streamlit 기본 화살표 버튼으로 접고 펼칠 수 있습니다.")


left_col, result_col = st.columns([0.62, 1.35], gap="large")

with left_col:
    st.markdown('<div class="section-label">INPUT PANEL / 620 x 500</div>', unsafe_allow_html=True)
    with st.container(border=True, height=500):
        if st.session_state.step == 1:
            st.markdown("#### 상품 정보")
            st.session_state.product_type = st.selectbox(
                "상품 유형",
                ["커스텀 키보드", "키캡", "데스크매트", "데스크 조명", "데스크 소품"],
            )
            st.session_state.product_name = st.text_input("상품명", st.session_state.product_name)
            st.session_state.price = st.text_input("판매가", st.session_state.price)
            st.session_state.target_channel = st.selectbox(
                "판매 채널",
                ["인스타그램", "스마트스토어", "상세페이지", "배너 광고"],
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
            st.session_state.layout = st.selectbox(
                "배열",
                ["65", "75"],
                index=["65", "75"].index(st.session_state.layout),
            )
            st.session_state.drawing_upload_mode = st.radio(
                "도면 입력 방식",
                ["샘플 JSON 사용", "도면 파일 업로드"],
                horizontal=True,
                index=["샘플 JSON 사용", "도면 파일 업로드"].index(st.session_state.drawing_upload_mode),
            )
            if st.session_state.drawing_upload_mode == "도면 파일 업로드":
                st.file_uploader("도면 JSON/SVG/DXF 업로드", type=["json", "svg", "dxf"])
            model_info = KEYBOARD_MODEL_DEFAULTS[st.session_state.keyboard_model]
            st.info(f"기본값: {st.session_state.keyboard_model} / {model_info['layout']} 배열\n\n{model_info['description']}")
            st.markdown("##### 키보드 부품 레퍼런스")
            st.caption("하우징: keyboard_layout 샘플 도면")
            st.caption("스위치: kiswitch/kiswitch KiCad footprint")
            st.caption("PCB: AcheronProject/Tsuki 60% PCB")

        elif st.session_state.step == 3:
            st.markdown("#### 가상 셋업")
            st.session_state.theme = st.selectbox(
                "광고 스타일",
                ["minimal", "pastel", "premium", "gaming"],
                index=["minimal", "pastel", "premium", "gaming"].index(st.session_state.theme),
            )
            st.session_state.case_color = st.color_picker("하우징", st.session_state.case_color)
            st.session_state.keycap_color = st.color_picker("키캡", st.session_state.keycap_color)
            st.session_state.accent_keycap_color = st.color_picker("포인트 키", st.session_state.accent_keycap_color)
            st.session_state.deskmat_color = st.color_picker("데스크매트", st.session_state.deskmat_color)
            st.session_state.desk_color = st.color_picker("책상", st.session_state.desk_color)
            st.session_state.mouse_color = st.color_picker("마우스", st.session_state.mouse_color)

            if st.button("3D 셋업 생성", type="primary", use_container_width=True):
                try:
                    render_keyboard_preview()
                    st.success("3D GLB 생성 완료")
                except Exception as exc:
                    st.error(f"렌더링 실패: {exc}")

        else:
            st.markdown("#### 광고 콘텐츠")
            st.selectbox("광고 톤", ["프리미엄형", "감성형", "할인형", "기능강조형"])
            st.selectbox("이미지 비율", ["1:1", "4:5", "16:9"])
            st.text_area("추가 요청", "깔끔하고 고급스러운 데스크셋업 광고 느낌", height=110)

            if st.button("광고 문구 생성", type="primary", use_container_width=True):
                try:
                    generate_copy()
                    st.success("광고 문구 생성 완료")
                except Exception as exc:
                    st.error(f"문구 생성 실패: {exc}")

    nav_a, nav_b = st.columns(2)
    if nav_a.button("이전", use_container_width=True, disabled=st.session_state.step <= 1):
        st.session_state.step -= 1
        st.rerun()
    if nav_b.button("다음", use_container_width=True, disabled=st.session_state.step >= 4):
        try:
            go_next()
            st.rerun()
        except Exception as exc:
            st.error(f"다음 단계 처리 실패: {exc}")


with result_col:
    st.markdown('<div class="section-label">RESULT CANVAS / 1000 x 1000</div>', unsafe_allow_html=True)
    with st.container(border=True, height=1000):
        top_a, top_b, top_c = st.columns([0.45, 0.3, 0.25])
        with top_a:
            st.markdown("### 가상 데스크 셋업 결과")
            st.caption("도면/규격 JSON을 기반으로 생성된 3D 미리보기와 광고 결과물")
        with top_b:
            meta = st.session_state.model_meta or {}
            st.markdown(
                f"""
                <span class="metric-chip">Layout {st.session_state.layout}</span>
                <span class="metric-chip">Keys {meta.get("key_count", "-")}</span>
                <span class="metric-chip">{st.session_state.theme}</span>
                """,
                unsafe_allow_html=True,
            )
        with top_c:
            if st.button("결과 새로고침", use_container_width=True):
                try:
                    render_keyboard_preview()
                    st.rerun()
                except Exception as exc:
                    st.error(f"실패: {exc}")

        st.divider()

        if st.session_state.model_url:
            render_model_viewer(st.session_state.model_url, height=720)
        else:
            st.markdown("#### 아직 생성된 3D 결과가 없습니다.")
            st.write("왼쪽 입력 패널에서 `가상 셋업` 단계로 이동한 뒤 `3D 셋업 생성`을 누르면 이 영역에 결과가 표시됩니다.")
            st.json(build_payload())

        st.divider()

        ad_left, ad_right = st.columns([0.58, 0.42])
        with ad_left:
            st.markdown("#### 광고 카드 미리보기")
            st.write(f"**{st.session_state.product_name}**")
            st.write(st.session_state.selling_point)
            st.caption(f"{st.session_state.price} · {st.session_state.target_channel}")
        with ad_right:
            st.markdown("#### 생성 문구")
            result = st.session_state.copy_result
            if result:
                for copy in result["copies"][:2]:
                    st.write(f"- {copy}")
                st.caption(" ".join(result["hashtags"]))
            else:
                st.caption("광고 콘텐츠 단계에서 문구를 생성하면 여기에 표시됩니다.")
