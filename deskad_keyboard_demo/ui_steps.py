"""DeskAd AI Studio의 단계별 Streamlit 입력 패널을 렌더링한다."""
from __future__ import annotations

import os
from typing import Any

import streamlit as st

from ui.state import PRODUCT_FIELD_ERROR_KEY, missing_product_fields


PRODUCT_TYPE_OPTIONS = ["커스텀 키보드", "키캡", "데스크매트", "데스크 조명", "모니터암", "데스크 소품", "번들 셋업"]
TARGET_CHANNEL_OPTIONS = ["인스타그램", "스마트스토어", "상세페이지", "쿠팡 썸네일", "배너 광고", "네이버 검색광고", "카카오 채널", "유튜브 쇼츠"]
PRODUCT_LIBRARY_OPTIONS = ["keyboard_layout 샘플", "QMK/VIA 샘플", "사용자 업로드"]
DRAWING_UPLOAD_OPTIONS = ["샘플 JSON 사용", "STEP/GLB 파일 업로드"]
THEME_OPTIONS = ["minimal", "pastel", "premium", "gaming"]
AD_TONE_OPTIONS = ["프리미엄형", "감성형", "할인형", "기능강조형"]
IMAGE_RATIO_OPTIONS = ["1:1", "4:5", "16:9"]
ENGINE_OPTIONS = ["hyperclova", "openai", "local"]
ENGINE_LABELS = {
    "hyperclova": "HyperCLOVA · 전용 로컬",
    "openai": "OpenAI API",
    "local": "로컬 텍스트 + ComfyUI",
}
ENGINE_TIER_OPTIONS = ["general", "performance"]
ENGINE_TIER_LABELS = {
    "general": "일반",
    "performance": "고성능",
}
# 이미지 구도(샷 타입). ""(자동)이면 채널별 기본 구도로 결정된다.
# backend/schemas.py AdContentRequest.shot_type 패턴과 키를 맞춘다.
SHOT_TYPE_OPTIONS = ["", "hero", "top_down", "eye_level", "wide_scene", "detail_macro"]
SHOT_TYPE_LABELS = {
    "": "자동 (채널 기본 구도)",
    "hero": "히어로 샷 (사선 위)",
    "top_down": "탑다운 플랫레이",
    "eye_level": "아이레벨 라이프스타일",
    "wide_scene": "와이드 룸 전경",
    "detail_macro": "디테일 매크로 (키캡 클로즈업)",
}
IMAGE_RATIO_LABELS = {
    "1:1": "1:1 정사각",
    "4:5": "4:5 세로",
    "16:9": "16:9 가로",
}
FIXED_SETUP_ITEMS = ["keyboard", "desk"]
SETUP_ITEM_LABELS = {
    "keyboard": "키보드",
    "desk": "책상",
    "deskmat": "데스크매트",
    "monitor": "모니터",
    "monitor_arm": "모니터암",
    "mouse": "마우스",
    "monitor_light_bar": "모니터 라이트 바",
    "desk_lamp": "데스크 조명",
    "plant": "화분",
    "speakers": "스피커",
    "desk_shelf": "모니터 받침대",
    "notebook": "노트",
    "headphone_stand": "헤드폰 스탠드",
    "phone_stand": "스마트폰 스탠드",
    "keycap_tray": "키캡 트레이",
    "coffee_mug": "머그컵",
    "digital_clock": "디지털 시계",
    "aroma_diffuser": "아로마 디퓨저",
    "wireless_charger": "무선 충전 패드",
    "pen_holder": "펜 홀더",
    "book_stack": "책 묶음",
    "humidifier": "가습기",
    "photo_frame": "사진 액자",
    "usb_hub": "USB 허브",
    "mouse_pad_round": "라운드 마우스패드",
}


def _option_index(options: list[str], value: str, default: int = 0) -> int:
    return options.index(value) if value in options else default


def _render_button_choice(label: str, options: list[str], state_key: str, columns: int = 3) -> None:
    st.caption(label)
    cols = st.columns(columns)
    current = st.session_state.get(state_key, options[0])
    for index, option in enumerate(options):
        button_type = "primary" if option == current else "secondary"
        with cols[index % columns]:
            if st.button(option, type=button_type, use_container_width=True, key=f"{state_key}_{option}"):
                st.session_state[state_key] = option
                st.rerun()


def _render_poster_template_cards(ctx: dict[str, Any]) -> None:
    st.caption("포스터 템플릿")
    labels = ctx["POSTER_TEMPLATE_LABELS"]
    thumbnails = ctx["POSTER_TEMPLATE_THUMBNAILS"]
    cols = st.columns(2)
    for index, (key, label) in enumerate(labels.items()):
        selected = key == st.session_state.poster_template
        with cols[index % 2]:
            with st.container(border=True):
                button_type = "primary" if selected else "secondary"
                if st.button(label, type=button_type, use_container_width=True, key=f"poster_template_{key}"):
                    st.session_state.poster_template = key
                    st.rerun()
                thumb = thumbnails.get(key)
                if thumb:
                    st.markdown(thumb, unsafe_allow_html=True)


def _asset_enabled(asset_id: str) -> bool:
    return asset_id in set(st.session_state.asset_selection)


def _set_asset_enabled(asset_id: str, enabled: bool) -> None:
    selected = list(dict.fromkeys(st.session_state.asset_selection))
    if enabled and asset_id not in selected:
        selected.append(asset_id)
    elif not enabled:
        selected = [item for item in selected if item != asset_id]
    st.session_state.asset_selection = selected


def render_step_input_panel(ctx: dict[str, Any]) -> None:
    """Render the active left-panel step."""
    if st.session_state.step == 1:
        _render_product_info_step()
    elif st.session_state.step == 2:
        _render_drawing_data_step(ctx)
    elif st.session_state.step == 3:
        _render_virtual_setup_step(ctx)
    else:
        _render_ad_content_step(ctx)


def _render_product_info_step() -> None:
    st.markdown("#### 상품 정보")
    if st.session_state.get(PRODUCT_FIELD_ERROR_KEY):
        st.error(st.session_state[PRODUCT_FIELD_ERROR_KEY])
    st.session_state.product_type = st.selectbox(
        "상품 유형",
        PRODUCT_TYPE_OPTIONS,
        index=_option_index(PRODUCT_TYPE_OPTIONS, st.session_state.product_type),
    )
    st.session_state.product_name = st.text_input("상품명", st.session_state.product_name, placeholder="예: 커스텀 키보드")
    st.session_state.price = st.text_input("판매가", st.session_state.price, placeholder="예: 189,000원")
    st.session_state.target_channel = st.selectbox(
        "판매 채널",
        TARGET_CHANNEL_OPTIONS,
        index=_option_index(TARGET_CHANNEL_OPTIONS, st.session_state.target_channel),
    )
    st.session_state.target_customer = st.text_input("타깃 고객", st.session_state.target_customer, placeholder="예: 깔끔한 데스크 셋업을 원하는 직장인")
    st.session_state.selling_point = st.text_area("핵심 특징", st.session_state.selling_point, height=95, placeholder="예: 조용한 타건감, 크림 톤 키캡, 작은 책상에도 잘 맞는 65% 배열")
    missing = missing_product_fields()
    if missing:
        st.caption(f"필수 입력값: {', '.join(missing)}")
    else:
        st.session_state.pop(PRODUCT_FIELD_ERROR_KEY, None)

def _render_drawing_data_step(ctx: dict[str, Any]) -> None:
    st.markdown("#### 도면/제품 데이터")
    keyboard_model_defaults = ctx["KEYBOARD_MODEL_DEFAULTS"]
    keyboard_size_info = ctx["KEYBOARD_SIZE_INFO"]

    st.session_state.product_library = st.selectbox(
        "제품 라이브러리",
        PRODUCT_LIBRARY_OPTIONS,
        index=_option_index(PRODUCT_LIBRARY_OPTIONS, st.session_state.product_library),
    )
    st.selectbox(
        "키보드 모델",
        list(keyboard_model_defaults.keys()),
        key="keyboard_model",
        on_change=ctx["sync_layout_from_model"],
    )
    layout_options = ctx["fetch_layout_ids"]()
    st.session_state.layout = st.selectbox(
        "배열",
        layout_options,
        index=layout_options.index(st.session_state.layout) if st.session_state.layout in layout_options else min(1, len(layout_options) - 1),
        format_func=lambda k: keyboard_size_info.get(k, k + "%"),
    )
    st.session_state.drawing_upload_mode = st.radio(
        "도면 입력 방식",
        DRAWING_UPLOAD_OPTIONS,
        horizontal=True,
        index=_option_index(DRAWING_UPLOAD_OPTIONS, st.session_state.drawing_upload_mode),
    )
    if st.session_state.drawing_upload_mode == "STEP/GLB 파일 업로드":
        uploaded = st.file_uploader("STEP/STP/GLB 업로드", type=["step", "stp", "glb"])
        if uploaded and st.button("업로드 모델 미리보기", type="primary", use_container_width=True):
            try:
                ctx["upload_reference_model"](uploaded)
                st.success("업로드 모델 준비 완료")
            except Exception as exc:
                st.error(f"업로드 처리 실패: {exc}")

    _render_drawing_references(ctx)
    model_info = keyboard_model_defaults[st.session_state.keyboard_model]
    st.info(f"기본값: {st.session_state.keyboard_model} / {model_info['layout']} 배열\n\n{model_info['description']}")

    _render_keyboard_detail_controls(ctx)
    _render_asset_selection(ctx)


def _render_drawing_references(ctx: dict[str, Any]) -> None:
    st.markdown("##### 공용 도면/레퍼런스 라이브러리")
    references = ctx["fetch_reference_assets"]()
    # 노션에 올라온 도면/레퍼런스는 모두 공용으로 사용한다(shared/data 에서 서빙).
    shared_refs = [item for item in references if item.get("downloaded")]
    st.caption(f"공용 도면/레퍼런스 {len(shared_refs)}개 (노션 리서치 기반, 전체 공용 사용)")
    if shared_refs:
        ref_options = {item["path"]: item for item in shared_refs if item.get("path")}
        if st.session_state.selected_reference_path not in ref_options:
            st.session_state.selected_reference_path = next(iter(ref_options), None)
        selected_ref = st.selectbox(
            "공용 도면/레퍼런스",
            options=list(ref_options.keys()),
            key="selected_reference_path",
            format_func=lambda value: f"{ref_options[value].get('label', value)} · {ref_options[value].get('license', 'license check')}",
        )
        ref_item = ref_options.get(selected_ref, {})
        st.caption(f"출처: {ref_item.get('source_url', '')}")
        if ref_item.get("url"):
            ctx["render_reference_grid"]([ref_item], columns=1)
    else:
        st.caption("아직 공용 도면/레퍼런스가 없습니다. 노션 도면 다운로드 스크립트 실행 후 표시됩니다.")

    # 이전 생성·공용/외부 모델 '불러오기'는 가상 셋업 단계의 '선택 편집' 패널로 옮겼다.
    st.caption("이전 생성·공용/외부 모델 불러오기는 가상 셋업 단계의 '기존 모델 불러오기'에 있습니다.")


def _render_keyboard_detail_controls(ctx: dict[str, Any]) -> None:
    case_finish_labels = ctx["CASE_FINISH_LABELS"]
    plate_material_labels = ctx["PLATE_MATERIAL_LABELS"]
    pcb_color_labels = ctx["PCB_COLOR_LABELS"]
    switch_stem_labels = ctx["SWITCH_STEM_LABELS"]
    switch_family_labels = ctx["SWITCH_FAMILY_LABELS"]
    keycap_profile_labels = ctx["KEYCAP_PROFILE_LABELS"]
    mount_type_labels = ctx["MOUNT_TYPE_LABELS"]

    with st.expander("키보드 상세 커스텀 (케이스/보강판/PCB/스위치)", expanded=True):
        custom_a, custom_b = st.columns(2)
        with custom_a:
            st.session_state.case_finish = st.selectbox(
                "케이스 마감",
                list(case_finish_labels.keys()),
                index=list(case_finish_labels.keys()).index(st.session_state.case_finish),
                format_func=lambda k: case_finish_labels[k],
            )
            st.session_state.plate_material = st.selectbox(
                "보강판(plate) 재질",
                list(plate_material_labels.keys()),
                index=list(plate_material_labels.keys()).index(st.session_state.plate_material),
                format_func=lambda k: plate_material_labels[k],
            )
        with custom_b:
            st.session_state.pcb_color = st.selectbox(
                "PCB 색상",
                list(pcb_color_labels.keys()),
                index=list(pcb_color_labels.keys()).index(st.session_state.pcb_color),
                format_func=lambda k: pcb_color_labels[k],
            )
            st.session_state.switch_stem = st.selectbox(
                "스위치 stem",
                list(switch_stem_labels.keys()),
                index=list(switch_stem_labels.keys()).index(st.session_state.switch_stem),
                format_func=lambda k: switch_stem_labels[k],
            )
        detail_a, detail_b, detail_c = st.columns(3)
        with detail_a:
            st.session_state.switch_family = st.selectbox(
                "스위치 구조",
                list(switch_family_labels.keys()),
                index=list(switch_family_labels.keys()).index(st.session_state.switch_family),
                format_func=lambda k: switch_family_labels[k],
            )
        with detail_b:
            st.session_state.keycap_profile = st.selectbox(
                "키캡 프로파일",
                list(keycap_profile_labels.keys()),
                index=list(keycap_profile_labels.keys()).index(st.session_state.keycap_profile),
                format_func=lambda k: keycap_profile_labels[k],
            )
        with detail_c:
            st.session_state.mount_type = st.selectbox(
                "마운트 방식",
                list(mount_type_labels.keys()),
                index=list(mount_type_labels.keys()).index(st.session_state.mount_type),
                format_func=lambda k: mount_type_labels[k],
            )
        st.session_state.show_internals = st.checkbox(
            "내부 구조(보강판/PCB/스위치) 렌더 노출",
            value=st.session_state.show_internals,
            help="체크하면 키보드 측면에서 내부 적층 구조가 보이도록 두께를 살짝 분리합니다. 포스터 컷에서 분해도처럼 보이게 할 때 유용합니다.",
        )


def _render_asset_selection(ctx: dict[str, Any]) -> None:
    st.markdown("##### 데스크테리어 항목")
    assets = ctx["fetch_desk_assets"]()
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


def _render_virtual_setup_step(ctx: dict[str, Any]) -> None:
    st.markdown("#### 가상 셋업")
    _render_setup_composition(ctx)

    active_items = _active_setup_items(ctx)
    if st.session_state.selected_setup_item not in active_items:
        st.session_state.selected_setup_item = active_items[0]
    st.radio(
        "편집할 제품",
        active_items,
        key="selected_setup_item",
        horizontal=True,
        format_func=lambda item: SETUP_ITEM_LABELS.get(item, item),
    )

    selected = st.session_state.selected_setup_item
    if selected == "keyboard":
        _render_keyboard_setup_controls(ctx)
    elif selected == "desk":
        _render_desk_setup_controls()
    elif selected == "monitor":
        _render_monitor_setup_controls(ctx)
    elif selected == "mouse":
        _render_mouse_setup_controls()
    elif selected == "deskmat":
        _render_deskmat_setup_controls()
    elif selected == "monitor_arm":
        _render_monitor_arm_setup_controls(ctx)
    else:
        _render_generic_asset_controls(selected, ctx)

    st.session_state.theme = st.selectbox(
        "광고 스타일",
        THEME_OPTIONS,
        index=_option_index(THEME_OPTIONS, st.session_state.theme),
    )

    if st.button("3D 데스크 셋업 생성", type="primary", use_container_width=True):
        progress = st.progress(0, text="3D 셋업 생성 준비 중")
        status = st.empty()
        try:
            status.info("25% · 셋업 옵션과 배치 구성을 정리하는 중")
            progress.progress(25, text="셋업 옵션 정리 중")
            status.info("60% · GLB 모델과 이미지 구도 데이터를 생성하는 중")
            progress.progress(60, text="GLB 모델 생성 중")
            ctx["render_desk_setup"]()
            status.success("100% · 3D GLB 생성 완료")
            progress.progress(100, text="3D GLB 생성 완료")
            st.success("3D GLB 생성 완료")
            st.rerun()
        except Exception as exc:
            progress.empty()
            status.empty()
            st.error(f"렌더링 실패: {exc}")

    # 새로 생성하는 대신 이전 생성 결과나 공용/외부 모델을 불러올 수 있게 한다.
    with st.expander("기존 모델 불러오기 (이전 생성 / 공용·외부)", expanded=False):
        ctx["render_model_load_panel"]()


def _render_setup_composition(ctx: dict[str, Any]) -> None:
    assets = ctx["fetch_desk_assets"]()
    asset_labels = {asset["id"]: SETUP_ITEM_LABELS.get(asset["id"], asset["label"]) for asset in assets}
    st.caption("기본 구성: 키보드 · 책상")
    st.session_state.asset_selection = st.multiselect(
        "셋업 구성품",
        options=[asset["id"] for asset in assets],
        default=[item for item in st.session_state.asset_selection if item in asset_labels],
        format_func=lambda item: asset_labels.get(item, item),
    )


def _active_setup_items(ctx: dict[str, Any]) -> list[str]:
    available_assets = {asset["id"] for asset in ctx["fetch_desk_assets"]()}
    selected_assets = [item for item in st.session_state.asset_selection if item in available_assets]
    return FIXED_SETUP_ITEMS + [item for item in selected_assets if item not in FIXED_SETUP_ITEMS]


def _render_keyboard_setup_controls(ctx: dict[str, Any]) -> None:
    keyboard_model_defaults = ctx["KEYBOARD_MODEL_DEFAULTS"]
    keyboard_size_info = ctx["KEYBOARD_SIZE_INFO"]
    st.selectbox(
        "키보드 모델",
        list(keyboard_model_defaults.keys()),
        key="keyboard_model",
        on_change=ctx["sync_layout_from_model"],
    )
    layout_options = ctx["fetch_layout_ids"]()
    st.session_state.layout = st.selectbox(
        "배열",
        layout_options,
        index=layout_options.index(st.session_state.layout) if st.session_state.layout in layout_options else min(1, len(layout_options) - 1),
        format_func=lambda k: keyboard_size_info.get(k, k + "%"),
    )
    color_a, color_b, color_c = st.columns(3)
    with color_a:
        st.session_state.case_color = st.color_picker("하우징", st.session_state.case_color)
    with color_b:
        st.session_state.keycap_color = st.color_picker("키캡", st.session_state.keycap_color)
    with color_c:
        st.session_state.accent_keycap_color = st.color_picker("포인트 키", st.session_state.accent_keycap_color)
    with st.expander("고급 키보드 옵션", expanded=False):
        detail_a, detail_b = st.columns(2)
        with detail_a:
            st.session_state.case_finish = st.selectbox(
                "케이스 마감",
                list(ctx["CASE_FINISH_LABELS"].keys()),
                index=list(ctx["CASE_FINISH_LABELS"].keys()).index(st.session_state.case_finish),
                format_func=lambda k: ctx["CASE_FINISH_LABELS"][k],
            )
            st.session_state.switch_family = st.selectbox(
                "스위치 구조",
                list(ctx["SWITCH_FAMILY_LABELS"].keys()),
                index=list(ctx["SWITCH_FAMILY_LABELS"].keys()).index(st.session_state.switch_family),
                format_func=lambda k: ctx["SWITCH_FAMILY_LABELS"][k],
            )
            st.session_state.keycap_profile = st.selectbox(
                "키캡 프로파일",
                list(ctx["KEYCAP_PROFILE_LABELS"].keys()),
                index=list(ctx["KEYCAP_PROFILE_LABELS"].keys()).index(st.session_state.keycap_profile),
                format_func=lambda k: ctx["KEYCAP_PROFILE_LABELS"][k],
            )
        with detail_b:
            st.session_state.plate_material = st.selectbox(
                "보강판 재질",
                list(ctx["PLATE_MATERIAL_LABELS"].keys()),
                index=list(ctx["PLATE_MATERIAL_LABELS"].keys()).index(st.session_state.plate_material),
                format_func=lambda k: ctx["PLATE_MATERIAL_LABELS"][k],
            )
            st.session_state.switch_stem = st.selectbox(
                "스위치 stem",
                list(ctx["SWITCH_STEM_LABELS"].keys()),
                index=list(ctx["SWITCH_STEM_LABELS"].keys()).index(st.session_state.switch_stem),
                format_func=lambda k: ctx["SWITCH_STEM_LABELS"][k],
            )
            st.session_state.mount_type = st.selectbox(
                "마운트 방식",
                list(ctx["MOUNT_TYPE_LABELS"].keys()),
                index=list(ctx["MOUNT_TYPE_LABELS"].keys()).index(st.session_state.mount_type),
                format_func=lambda k: ctx["MOUNT_TYPE_LABELS"][k],
            )
        st.session_state.show_internals = st.checkbox("내부 구조 렌더 노출", value=st.session_state.show_internals)


def _render_desk_setup_controls() -> None:
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
    st.session_state.desk_color = st.color_picker("책상", st.session_state.desk_color)


def _render_monitor_setup_controls(ctx: dict[str, Any]) -> None:
    monitor_sizes = ctx["MONITOR_SIZES"]
    st.session_state.monitor_size = st.selectbox(
        "모니터 크기",
        options=list(monitor_sizes.keys()),
        index=list(monitor_sizes.keys()).index(st.session_state.monitor_size),
        format_func=lambda k: monitor_sizes[k],
    )
    include_arm = st.checkbox("모니터암 포함", value=_asset_enabled("monitor_arm"))
    _set_asset_enabled("monitor_arm", include_arm)
    if include_arm:
        _render_monitor_arm_setup_controls(ctx)


def _render_monitor_arm_setup_controls(ctx: dict[str, Any]) -> None:
    monitor_arm_labels = ctx["MONITOR_ARM_LABELS"]
    st.session_state.monitor_arm_style = st.selectbox(
        "모니터암 스타일",
        options=list(monitor_arm_labels.keys()),
        index=list(monitor_arm_labels.keys()).index(st.session_state.monitor_arm_style),
        format_func=lambda k: monitor_arm_labels[k],
    )


def _render_mouse_setup_controls() -> None:
    st.session_state.mouse_color = st.color_picker("마우스", st.session_state.mouse_color)


def _render_deskmat_setup_controls() -> None:
    st.session_state.deskmat_color = st.color_picker("데스크매트", st.session_state.deskmat_color)


def _render_generic_asset_controls(asset_id: str, ctx: dict[str, Any]) -> None:
    assets = {asset["id"]: asset for asset in ctx["fetch_desk_assets"]()}
    item = assets.get(asset_id, {})
    st.caption(f"{item.get('category', 'asset')} · {SETUP_ITEM_LABELS.get(asset_id, item.get('label', asset_id))}")
    if st.button("셋업에서 제거", use_container_width=True):
        _set_asset_enabled(asset_id, False)
        st.session_state.selected_setup_item = "keyboard"
        st.rerun()


def _render_ad_content_step(ctx: dict[str, Any]) -> None:
    st.markdown("#### 광고 콘텐츠")

    def _on_engine_change() -> None:
        # 트랙 전환 시 해당 GPU 워커를 백엔드가 미리 워밍업(논블로킹, 단일 GPU exclusive).
        ctx["activate_engine_track"](st.session_state.engine)

    st.selectbox(
        "생성 엔진",
        ENGINE_OPTIONS,
        key="engine",
        format_func=lambda key: ENGINE_LABELS.get(key, key),
        help="광고 문구와 실사 이미지 생성에 사용할 엔진 묶음입니다.",
        on_change=_on_engine_change,
    )
    if st.session_state.engine == "openai":
        st.session_state.engine_model_tier = st.radio(
            "OpenAI 모델 등급",
            ENGINE_TIER_OPTIONS,
            index=_option_index(ENGINE_TIER_OPTIONS, st.session_state.get("engine_model_tier", "general")),
            format_func=lambda key: ENGINE_TIER_LABELS.get(key, key),
            horizontal=True,
        )

    ad_a, ad_b = st.columns([0.30, 0.70])
    with ad_a:
        _render_button_choice("광고 톤", AD_TONE_OPTIONS, "ad_tone", columns=2)
        _render_button_choice("이미지 비율", IMAGE_RATIO_OPTIONS, "image_ratio", columns=3)
        st.session_state.shot_type = st.selectbox(
            "이미지 구도",
            SHOT_TYPE_OPTIONS,
            index=_option_index(SHOT_TYPE_OPTIONS, st.session_state.get("shot_type", "")),
            format_func=lambda key: SHOT_TYPE_LABELS.get(key, key),
            help="실사 이미지의 카메라 구도입니다. 자동이면 타깃 채널에 맞는 구도를 사용합니다.",
        )
    with ad_b:
        _render_poster_template_cards(ctx)
        if _operator_mode():
            _render_ai_status(ctx["fetch_security_config"]())
    st.session_state.extra_request = st.text_area("추가 요청", st.session_state.extra_request, height=110)

    if st.session_state.get("setup_composition_b64"):
        st.session_state.use_setup_composition = st.checkbox(
            "3D 셋업 구도를 이미지 기준으로 사용",
            value=st.session_state.get("use_setup_composition", True),
            help="Step 3에서 만든 데스크 셋업 구도를 실사 이미지 생성의 구도 기준으로 전달합니다.",
        )
        if st.session_state.use_setup_composition:
            with st.expander("셋업 구도 미리보기", expanded=False):
                import base64 as _b64

                st.image(
                    _b64.b64decode(st.session_state.setup_composition_b64),
                    caption="img2img 구도 기준",
                    use_container_width=True,
                )

    col_copy, col_image, col_poster = st.columns(3)
    if col_copy.button("광고 문구 생성", type="secondary", use_container_width=True):
        progress = st.progress(0, text="광고 문구 생성 준비 중")
        try:
            engine_label = ENGINE_LABELS.get(st.session_state.get("engine", "hyperclova"), "선택 엔진")
            progress.progress(30, text=f"{engine_label} 문구 변형 생성 중")
            ctx["generate_copy_variants"]()
            progress.progress(100, text="광고 문구 생성 완료")
            st.success("광고 문구 변형 생성 완료 — 마음에 드는 후보를 선택하세요")
            st.rerun()
        except Exception as exc:
            progress.empty()
            st.error(f"문구 생성 실패: {exc}")
    if col_image.button("실사 이미지 작업", type="secondary", use_container_width=True):
        progress = st.progress(0, text="이미지 작업 요청 준비 중")
        try:
            progress.progress(35, text="이미지 생성 작업 등록 중")
            ctx["generate_image_job"]()
            progress.progress(100, text="이미지 작업 등록 완료")
            st.success("이미지 작업 생성 완료")
            st.rerun()
        except Exception as exc:
            progress.empty()
            st.error(f"이미지 작업 실패: {exc}")
    poster_disabled = ctx["poster_waiting_for_image"]()
    if col_poster.button("포스터 생성", type="primary", use_container_width=True, disabled=poster_disabled):
        progress = st.progress(0, text="포스터 생성 준비 중")
        status = st.empty()
        try:
            status.info("15% · 선택한 템플릿과 문구를 정리하는 중")
            progress.progress(15, text="선택한 템플릿과 문구 정리 중")
            status.info("45% · 광고 이미지와 SVG 포스터를 생성하는 중")
            progress.progress(45, text="광고 이미지와 SVG 포스터 생성 중")
            ctx["generate_poster"]()
            status.success("100% · 포스터 생성 완료")
            progress.progress(100, text="포스터 생성 완료")
            st.success("포스터 생성 완료")
            st.rerun()
        except Exception as exc:
            progress.empty()
            status.empty()
            st.error(f"포스터 생성 실패: {exc}")
    if poster_disabled:
        st.caption("이미지 작업이 완료되면 포스터 생성이 활성화됩니다.")

    if _operator_mode():
        providers = ctx["fetch_ai_providers"]().get("providers", [])
        if providers:
            configured = [item["id"] for item in providers if item.get("configured") and item.get("id") != "fallback"]
            st.caption(f"사용 가능 provider: {', '.join(configured) if configured else 'fallback only'}")
    if st.session_state.copy_experiment_result:
        st.caption("생성된 문구 후보는 아래 결과 캔버스의 광고 카드 영역에서 크게 비교할 수 있습니다.")


def _operator_mode() -> bool:
    """운영자 진단 정보(AI provider 상태 등) 노출 여부. 기본 숨김 — 소비자 화면에는
    어떤 모델/키가 켜져 있는지 등 기술 정보를 보이지 않는다. DESKAD_OPERATOR_MODE로만 노출."""
    return os.getenv("DESKAD_OPERATOR_MODE", "").strip().lower() in ("1", "true", "yes", "on")


def _render_ai_status(config_now: dict) -> None:
    local_text_status = "on" if any(
        config_now.get(key) == "set" for key in ("local_llm_base_url", "kanana_base_url", "midm_base_url")
    ) else "off"
    hyperclova_text_status = "on" if config_now.get("hyperclova_base_url") == "set" else "off"
    hyperclova_image_status = "on" if config_now.get("hyperclova_image_configured") else "off"
    kanana_status = "on" if config_now.get("kanana_base_url") == "set" else "off"
    midm_status = "on" if config_now.get("midm_base_url") == "set" else "off"
    openai_text_status = "on" if config_now.get("openai_api_key") == "set" else "off"
    openai_image_status = "on" if config_now.get("openai_api_key") == "set" else "off"
    comfyui_status = "on" if config_now.get("comfyui_base_url") == "set" else "off"
    st.caption(
        f"Tracks: OpenAI text/img {openai_text_status}/{openai_image_status} · "
        f"HyperCLOVA text/img {hyperclova_text_status}/{hyperclova_image_status} · "
        f"Local text/img {local_text_status}/{comfyui_status}"
    )
    st.caption(
        f"Local text candidates: base {local_text_status} · Kanana {kanana_status} · Mi:dm {midm_status}"
    )
    st.caption(
        f"AI providers: OpenAI {openai_text_status} · HyperCLOVA {hyperclova_text_status} · "
        f"Kanana {kanana_status} · Mi:dm {midm_status}"
    )
