"""이 파일은 FastAPI 요청 스키마를 담당한다."""

from __future__ import annotations

from pydantic import BaseModel, Field

from .assets import enabled_asset_ids


class KeyboardRenderRequest(BaseModel):
    """키보드 단품/셋업 렌더링 공통 옵션을 검증한다."""

    product_name: str = Field(default="커스텀 키보드 셋업", max_length=80)
    layout: str = Field(default="65")
    case_color: str = Field(default="#c8c1b2")
    keycap_color: str = Field(default="#f4ead7")
    accent_keycap_color: str = Field(default="#6f8faf")
    deskmat_color: str = Field(default="#1f2937")
    desk_color: str = Field(default="#d8b892")
    mouse_color: str = Field(default="#f7f7f2")
    theme: str = Field(default="minimal")
    case_finish: str = Field(default="anodized", pattern=r"^(anodized|matte|polycarbonate|wood)$")
    plate_material: str = Field(default="aluminum", pattern=r"^(aluminum|brass|pom|fr4|carbon|polycarbonate)$")
    pcb_color: str = Field(default="black", pattern=r"^(black|red|blue|green|white)$")
    switch_stem: str = Field(default="red", pattern=r"^(red|yellow|brown|blue|clear|silent_red|tactile_purple|linear_black)$")
    switch_family: str = Field(default="mx", pattern=r"^(mx|box|holy_panda|topre)$")
    keycap_profile: str = Field(default="cherry", pattern=r"^(cherry|oem|xda|sa|mda)$")
    mount_type: str = Field(default="top_mount", pattern=r"^(top_mount|tray_mount|gasket_mount|o_ring_mount)$")
    show_internals: bool = Field(default=True)


class DeskSetupRenderRequest(KeyboardRenderRequest):
    """전체 데스크 셋업 렌더링 옵션을 검증한다."""

    assets: list[str] = Field(default_factory=enabled_asset_ids)
    desk_width: float = Field(default=120.0, ge=100.0, le=200.0)
    desk_depth: float = Field(default=60.0, ge=50.0, le=90.0)
    monitor_size: str = Field(default="27", pattern=r"^(24|27|32)$")
    monitor_arm_style: str = Field(default="single", pattern=r"^(single|double_joint)$")
    show_internals: bool = Field(default=False)


class SelectedCopy(BaseModel):
    """UI에서 선택한 광고 문구를 검증한다."""

    provider: str = Field(default="selected", max_length=60)
    headline: str = Field(default="", max_length=80)
    subcopy: str = Field(default="", max_length=160)
    cta: str = Field(default="", max_length=40)
    copies: list[str] = Field(default_factory=list, max_length=5)
    hashtags: list[str] = Field(default_factory=list, max_length=6)
    spec_bullets: list[str] = Field(default_factory=list, max_length=5)


class AdContentRequest(DeskSetupRenderRequest):
    """광고 콘텐츠 생성에 필요한 상품/타깃/렌더링 정보를 검증한다."""

    product_name: str = Field(default="크림 베이지 65% 커스텀 키보드", max_length=80)
    product_type: str = Field(default="커스텀 키보드", max_length=40)
    price: str = Field(default="189,000원", max_length=30)
    target_channel: str = Field(default="인스타그램", max_length=30)
    target_customer: str = Field(default="깔끔한 데스크 셋업을 원하는 직장인", max_length=120)
    selling_point: str = Field(default="조용한 타건감, 크림 톤 키캡, 작은 책상에도 잘 맞는 65% 배열", max_length=240)
    ad_tone: str = Field(default="감성형", max_length=30)
    image_ratio: str = Field(default="1:1", pattern=r"^(1:1|4:5|16:9)$")
    extra_request: str = Field(default="깔끔하고 고급스러운 데스크셋업 광고 느낌", max_length=400)
    model_url: str | None = Field(default=None, max_length=400)
    reference_asset_path: str | None = Field(default=None, max_length=400)
    # 셋업 구도 맵 등 직접 전달하는 img2img 레퍼런스(base64/data URL). 선택 도면보다 우선.
    reference_image_b64: str | None = Field(default=None, max_length=12_000_000)
    # 구도 맵의 top-down(flat-lay) 투영. shot_type이 top_down인 채널에서 위 원근 맵 대신 쓴다.
    reference_image_topdown_b64: str | None = Field(default=None, max_length=12_000_000)
    # 위 레퍼런스가 셋업 구도 맵(평면 색블록)이면 True → 더 높은 denoise로 사실화.
    reference_is_composition: bool = False
    image_job_id: str | None = Field(default=None, max_length=64, pattern=r"^[A-Za-z0-9_\-]*$")
    image_workflow: str | None = Field(default=None, max_length=64, pattern=r"^[A-Za-z0-9_\-]*$")
    poster_template: str = Field(default="minimal_card", pattern=r"^(minimal_card|grid_three|feature_focus|promo_banner)$")
    # 평가 트랙(생성 엔진): openai=OpenAI API, hyperclova=HyperCLOVA, local=로컬 텍스트+ComfyUI.
    # auto는 서버 기본값(AI_PROVIDER/IMAGE_MODEL_BACKEND)을 따른다.
    engine: str = Field(default="auto", pattern=r"^(auto|openai|hyperclova|local)$")
    # OpenAI 엔진의 모델 등급(일반/고성능). 다른 엔진에서는 무시된다.
    engine_model_tier: str = Field(default="general", pattern=r"^(general|performance)$")
    selected_copy: SelectedCopy | None = None


class UploadedModelRequest(BaseModel):
    """업로드 모델 파일명과 base64 본문을 검증한다."""

    filename: str = Field(max_length=255, pattern=r"^[^/\\x00]+$")
    content_base64: str = Field(max_length=120_000_000)
    product_name: str | None = Field(default=None, max_length=80)


class LibraryModelRequest(BaseModel):
    """모델 라이브러리 파일 경로를 검증한다."""

    path: str = Field(
        description="Library path under models/, uploads/reference_drawings/, shared/models/, or shared/data/.",
        max_length=400,
    )
    product_name: str | None = Field(default=None, max_length=80)


class CopyExperimentRequest(AdContentRequest):
    """여러 provider로 광고 문구를 실험할 요청을 검증한다."""

    providers: list[str] = Field(default_factory=lambda: ["openai", "hyperclova", "local", "fallback"])


class PlateDrawingRenderRequest(BaseModel):
    """키보드 플레이트 도면을 GLB로 변환할 요청을 검증한다."""

    plate_id: str = Field(max_length=120, pattern=r"^[A-Za-z0-9_\-./]+$")
    product_name: str | None = Field(default=None, max_length=80)
