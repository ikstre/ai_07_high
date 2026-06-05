from __future__ import annotations

from pydantic import BaseModel, Field

from .assets import enabled_asset_ids


class KeyboardRenderRequest(BaseModel):
    """Common keyboard rendering options shared by preview and setup requests."""

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
    """Full desk setup rendering request including desk, monitor, and assets."""

    assets: list[str] = Field(default_factory=enabled_asset_ids)
    desk_width: float = Field(default=120.0, ge=100.0, le=200.0)
    desk_depth: float = Field(default=60.0, ge=50.0, le=90.0)
    monitor_size: str = Field(default="27", pattern=r"^(24|27|32)$")
    monitor_arm_style: str = Field(default="single", pattern=r"^(single|double_joint)$")
    show_internals: bool = Field(default=False)


class SelectedCopy(BaseModel):
    """Ad copy selected in the UI for poster/image generation."""

    provider: str = Field(default="selected", max_length=60)
    headline: str = Field(default="", max_length=80)
    subcopy: str = Field(default="", max_length=160)
    cta: str = Field(default="", max_length=40)
    copies: list[str] = Field(default_factory=list, max_length=5)
    hashtags: list[str] = Field(default_factory=list, max_length=6)
    spec_bullets: list[str] = Field(default_factory=list, max_length=5)


class AdContentRequest(DeskSetupRenderRequest):
    """Product, rendering, and campaign fields needed for ad generation."""

    product_name: str = Field(default="크림 베이지 65% 커스텀 키보드", max_length=80)
    product_type: str = Field(default="커스텀 키보드", max_length=40)
    price: str = Field(default="189,000원", max_length=30)
    target_channel: str = Field(default="인스타그램", max_length=30)
    target_customer: str = Field(default="깔끔한 데스크 셋업을 원하는 직장인", max_length=120)
    selling_point: str = Field(default="조용한 타건감, 크림 톤 키캡, 작은 책상에도 잘 맞는 65% 배열", max_length=240)
    ad_tone: str = Field(default="감성형", max_length=30)
    image_ratio: str = Field(default="1:1", pattern=r"^(1:1|4:5|16:9)$")
    extra_request: str = Field(default="깔끔하고 고급스러운 데스크셋업 광고 자료", max_length=400)
    model_url: str | None = Field(default=None, max_length=400)
    reference_asset_path: str | None = Field(default=None, max_length=400)
    image_job_id: str | None = Field(default=None, max_length=64, pattern=r"^[A-Za-z0-9_\-]*$")
    image_workflow: str | None = Field(default=None, max_length=64, pattern=r"^[A-Za-z0-9_\-]*$")
    poster_template: str = Field(default="minimal_card", pattern=r"^(minimal_card|grid_three|feature_focus|promo_banner)$")
    selected_copy: SelectedCopy | None = None


class UploadedModelRequest(BaseModel):
    """Uploaded model file name and base64 body."""

    filename: str = Field(max_length=255, pattern=r"^[^/\\\x00]+$")
    content_base64: str = Field(max_length=120_000_000)
    product_name: str | None = Field(default=None, max_length=80)


class LibraryModelRequest(BaseModel):
    path: str = Field(
        description="Library path under models/, uploads/reference_drawings/, shared/models/, or shared/data/.",
        max_length=400,
    )
    product_name: str | None = Field(default=None, max_length=80)


class CopyExperimentRequest(AdContentRequest):
    providers: list[str] = Field(default_factory=lambda: ["hyperclova", "kanana", "midm", "local", "fallback"])


class PlateDrawingRenderRequest(BaseModel):
    """Plate id request for converting a keyboard plate drawing to GLB."""

    plate_id: str = Field(max_length=120, pattern=r"^[A-Za-z0-9_\-./]+$")
    product_name: str | None = Field(default=None, max_length=80)
