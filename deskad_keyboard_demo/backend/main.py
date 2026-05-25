
from __future__ import annotations

import base64
from html import escape
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .ai import build_image_prompt, generate_ad_copy, generate_local_image_reference, save_poster_svg
from .assets import enabled_asset_ids, load_desk_assets
from .cad import handle_model_upload_bytes
from .config import get_settings, redacted_settings
from .renderer import build_desk_setup_scene_glb, build_keyboard_scene_glb


BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
MODEL_DIR = STATIC_DIR / "models"
UPLOAD_DIR = STATIC_DIR / "uploads"
POSTER_DIR = STATIC_DIR / "posters"
DATA_DIR = BASE_DIR / "data"

for directory in (MODEL_DIR, UPLOAD_DIR, POSTER_DIR):
    directory.mkdir(parents=True, exist_ok=True)


app = FastAPI(title="DeskAd AI Studio API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class KeyboardRenderRequest(BaseModel):
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
    show_internals: bool = Field(default=True)


class DeskSetupRenderRequest(KeyboardRenderRequest):
    assets: list[str] = Field(default_factory=enabled_asset_ids)
    desk_width: float = Field(default=120.0, ge=100.0, le=200.0)
    desk_depth: float = Field(default=60.0, ge=50.0, le=90.0)
    monitor_size: str = Field(default="27", pattern=r"^(24|27|32)$")
    monitor_arm_style: str = Field(default="single", pattern=r"^(single|double_joint)$")
    show_internals: bool = Field(default=False)


class AdContentRequest(DeskSetupRenderRequest):
    product_name: str = Field(default="크림 베이지 65% 커스텀 키보드")
    product_type: str = Field(default="커스텀 키보드")
    price: str = Field(default="189,000원")
    target_channel: str = Field(default="인스타그램")
    target_customer: str = Field(default="깔끔한 데스크 셋업을 원하는 직장인")
    selling_point: str = Field(default="조용한 타건감, 크림 톤 키캡, 작은 책상에도 잘 맞는 65% 배열")
    ad_tone: str = Field(default="감성형")
    image_ratio: str = Field(default="1:1")
    extra_request: str = Field(default="깔끔하고 고급스러운 데스크셋업 광고 느낌")
    model_url: str | None = Field(default=None)
    poster_template: str = Field(default="minimal_card", pattern=r"^(minimal_card|grid_three|feature_focus|promo_banner)$")


class UploadedModelRequest(BaseModel):
    filename: str
    content_base64: str


def _settings_base_url() -> str:
    return get_settings().public_api_base_url.rstrip("/")


def _layout_path(layout: str) -> Path:
    path = DATA_DIR / "layouts" / f"layout_{layout}.json"
    if not path.exists():
        return DATA_DIR / "layouts" / "layout_65.json"
    return path


@app.get("/health")
def health():
    return {"status": "ok", "config": redacted_settings()}


@app.get("/security/config")
def security_config():
    return redacted_settings()


@app.get("/assets/desk")
def list_desk_assets():
    return {"assets": load_desk_assets(), "default_asset_ids": enabled_asset_ids()}


@app.get("/layouts")
def list_layouts():
    layouts = []
    for path in sorted((DATA_DIR / "layouts").glob("layout_*.json")):
        layout_id = path.stem.replace("layout_", "")
        layouts.append({"id": layout_id, "name": f"{layout_id.upper()} Layout"})
    return {"layouts": layouts}


@app.get("/viewer", response_class=HTMLResponse)
def model_viewer(model_url: str, camera: str = "perspective"):
    camera_orbits = {
        "perspective": "32deg 58deg 165m",
        "top": "0deg 0deg 190m",
        "front": "0deg 76deg 150m",
    }
    orbit = camera_orbits.get(camera, camera_orbits["perspective"])
    return f"""
    <!doctype html>
    <html>
      <head>
        <meta charset="utf-8" />
        <script type="module" src="https://unpkg.com/@google/model-viewer@4.0.0/dist/model-viewer.min.js"></script>
        <style>
          html, body {{
            margin: 0;
            width: 100%;
            height: 100%;
            background: #f4f1eb;
          }}
          model-viewer {{
            width: 100%;
            height: 100vh;
            background: radial-gradient(ellipse at center top, #f9f6f0 0%, #e7ecf1 60%, #dfe4eb 100%);
          }}
        </style>
      </head>
      <body>
        <model-viewer
          src="{escape(model_url)}"
          camera-controls
          auto-rotate
          auto-rotate-delay="6000"
          environment-image="neutral"
          tone-mapping="aces"
          shadow-intensity="1.4"
          shadow-softness="0.85"
          exposure="1.05"
          camera-orbit="{orbit}"
          min-camera-orbit="auto auto 70m"
          max-camera-orbit="auto auto 260m"
          interaction-prompt="none">
        </model-viewer>
      </body>
    </html>
    """


@app.post("/render/keyboard-preview")
def render_keyboard_preview(request: KeyboardRenderRequest):
    model_name = f"keyboard_{request.layout}_{uuid4().hex[:8]}.glb"
    output_path = MODEL_DIR / model_name

    metadata = build_keyboard_scene_glb(
        layout_path=_layout_path(request.layout),
        output_path=output_path,
        case_color=request.case_color,
        keycap_color=request.keycap_color,
        accent_keycap_color=request.accent_keycap_color,
        deskmat_color=request.deskmat_color,
        desk_color=request.desk_color,
        mouse_color=request.mouse_color,
        case_finish=request.case_finish,
        plate_material=request.plate_material,
        pcb_color=request.pcb_color,
        switch_stem=request.switch_stem,
        show_internals=request.show_internals,
    )

    return {
        "model_url": f"{_settings_base_url()}/static/models/{model_name}",
        "layout": request.layout,
        "theme": request.theme,
        **metadata,
    }


@app.post("/render/desk-setup")
def render_desk_setup(request: DeskSetupRenderRequest):
    model_name = f"desk_setup_{request.layout}_{uuid4().hex[:8]}.glb"
    output_path = MODEL_DIR / model_name

    metadata = build_desk_setup_scene_glb(
        layout_path=_layout_path(request.layout),
        output_path=output_path,
        case_color=request.case_color,
        keycap_color=request.keycap_color,
        accent_keycap_color=request.accent_keycap_color,
        deskmat_color=request.deskmat_color,
        desk_color=request.desk_color,
        mouse_color=request.mouse_color,
        theme=request.theme,
        assets=request.assets,
        desk_width=request.desk_width,
        desk_depth=request.desk_depth,
        monitor_size=request.monitor_size,
        case_finish=request.case_finish,
        plate_material=request.plate_material,
        pcb_color=request.pcb_color,
        switch_stem=request.switch_stem,
        show_internals=request.show_internals,
        monitor_arm_style=request.monitor_arm_style,
    )

    return {
        "model_url": f"{_settings_base_url()}/static/models/{model_name}",
        "layout": request.layout,
        "theme": request.theme,
        **metadata,
    }


@app.post("/render/uploaded-model")
def render_uploaded_model(request: UploadedModelRequest):
    try:
        data = base64.b64decode(request.content_base64, validate=True)
        return handle_model_upload_bytes(
            filename=request.filename,
            data=data,
            upload_dir=UPLOAD_DIR,
            model_dir=MODEL_DIR,
            public_base_url=_settings_base_url(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Upload failed: {exc}") from exc


@app.post("/ai/copy")
def generate_copy(request: AdContentRequest):
    return generate_ad_copy(request.model_dump())


@app.post("/ai/poster")
def generate_poster(request: AdContentRequest):
    payload = request.model_dump()
    copy_result = generate_ad_copy(payload)
    image_prompt = build_image_prompt(payload, copy_result)
    image_reference = generate_local_image_reference(payload, image_prompt)
    image_b64 = None
    if isinstance(image_reference, dict) and image_reference.get("has_image"):
        image_b64 = image_reference.get("image_b64")
    poster_meta = save_poster_svg(
        payload=payload,
        copy_result=copy_result,
        poster_dir=POSTER_DIR,
        image_b64=image_b64,
    )

    safe_reference = None
    if isinstance(image_reference, dict):
        safe_reference = {k: v for k, v in image_reference.items() if k != "image_b64"}

    return {
        "copy": copy_result,
        "image_prompt": image_prompt,
        "poster_url": f"{_settings_base_url()}/static/posters/{poster_meta['poster_file']}",
        "poster_file": poster_meta["poster_file"],
        "poster_template": payload.get("poster_template", "minimal_card"),
        "local_image_reference": safe_reference,
        "image_embedded": bool(image_b64),
    }
