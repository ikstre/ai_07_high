
from __future__ import annotations

import base64
from html import escape
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .ai import (
    IMAGE_JOB_STORE,
    available_text_providers,
    build_image_prompt,
    create_image_job,
    generate_ad_copy,
    generate_copy_experiment,
    generate_local_image_reference,
    image_reference_from_job,
    poll_image_job,
    safe_image_reference,
    save_poster_svg,
)
from .quality_gate import (
    evaluate_and_store,
    quality_report_for,
    quality_store_summary,
)
from .security import install_secret_log_filter

install_secret_log_filter()
from .assets import enabled_asset_ids, load_desk_assets
from .cad import copy_existing_glb, handle_model_upload_bytes
from .config import get_settings, redacted_settings
from .drawing_converter import convert_plate_drawing_to_glb
from .library import (
    load_reference_manifest,
    list_library_files,
    model_compatible_extensions,
    resolve_static_library_path,
    shared_data_dir,
    shared_library_status,
    shared_model_dir,
)
from .plates import get_plate, get_plate_preview_path, keyboard_layout_repo_path, list_plate_brands, search_plates
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

_cors_origins = get_settings().cors_origins
if _cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
    )

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/shared/data", StaticFiles(directory=shared_data_dir(), check_dir=False), name="shared_data")
app.mount("/shared/models", StaticFiles(directory=shared_model_dir(), check_dir=False), name="shared_models")


class KeyboardRenderRequest(BaseModel):
    """키보드 단품 렌더링 요청에서 공통 색상, 레이아웃, 내부 옵션을 검증한다."""
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
    """전체 데스크 셋업 렌더링 요청에서 책상, 모니터, 액세서리 옵션을 검증한다."""
    assets: list[str] = Field(default_factory=enabled_asset_ids)
    desk_width: float = Field(default=120.0, ge=100.0, le=200.0)
    desk_depth: float = Field(default=60.0, ge=50.0, le=90.0)
    monitor_size: str = Field(default="27", pattern=r"^(24|27|32)$")
    monitor_arm_style: str = Field(default="single", pattern=r"^(single|double_joint)$")
    show_internals: bool = Field(default=False)


class AdContentRequest(DeskSetupRenderRequest):
    """광고 문구와 포스터 생성을 위한 상품/타깃/렌더링 정보를 검증한다."""
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
    image_job_id: str | None = Field(default=None, max_length=64, pattern=r"^[A-Za-z0-9_\-]*$")
    poster_template: str = Field(default="minimal_card", pattern=r"^(minimal_card|grid_three|feature_focus|promo_banner)$")


class UploadedModelRequest(BaseModel):
    """업로드 모델 파일명과 base64 본문을 검증한다."""
    filename: str = Field(max_length=255, pattern=r"^[^/\\\x00]+$")
    content_base64: str = Field(max_length=120_000_000)


class LibraryModelRequest(BaseModel):
    path: str = Field(
        description="Library path under models/, uploads/reference_drawings/, shared/models/, or shared/data/.",
        max_length=400,
    )


class CopyExperimentRequest(AdContentRequest):
    providers: list[str] = Field(default_factory=lambda: ["kanana", "midm", "local", "fallback"])


class PlateDrawingRenderRequest(BaseModel):
    """키보드 플레이트 도면을 GLB로 변환하기 위한 plate id를 검증한다."""
    plate_id: str = Field(max_length=120, pattern=r"^[A-Za-z0-9_\-./]+$")


def _settings_base_url() -> str:
    """설정된 public API base URL을 정규화해 static URL 생성에 사용한다."""
    return get_settings().public_api_base_url.rstrip("/")


def _layout_path(layout: str) -> Path:
    """요청한 레이아웃 JSON 파일을 찾고 없으면 기본 65 배열로 대체한다."""
    path = DATA_DIR / "layouts" / f"layout_{layout}.json"
    if not path.exists():
        return DATA_DIR / "layouts" / "layout_65.json"
    return path


def _selected_plate_or_400(plate_id: str) -> dict:
    """plate id로 카탈로그 항목을 찾고 없으면 400 오류를 발생시킨다."""
    plate = get_plate(plate_id)
    if plate is None:
        raise HTTPException(status_code=400, detail=f"Plate not found: {plate_id}")
    return plate


@app.get("/health")
def health():
    """서비스 상태와 마스킹된 설정 정보를 반환한다."""
    return {"status": "ok", "config": redacted_settings()}


@app.get("/security/config")
def security_config():
    """프론트엔드 상태 표시용 마스킹 설정 정보를 반환한다."""
    return redacted_settings()


@app.get("/assets/desk")
def list_desk_assets():
    """사용 가능한 데스크 액세서리 목록과 기본 선택값을 반환한다."""
    return {"assets": load_desk_assets(), "default_asset_ids": enabled_asset_ids()}


@app.get("/assets/references")
def list_reference_assets():
    return {"references": load_reference_manifest(_settings_base_url())}


@app.get("/models/library")
def list_model_library():
    return {
        "files": list_library_files(_settings_base_url()),
        "model_compatible_extensions": model_compatible_extensions(),
        "shared": shared_library_status(),
    }


@app.get("/layouts")
def list_layouts():
    """data/layouts 폴더의 대표 키보드 레이아웃 목록을 반환한다."""
    layouts = []
    for path in sorted((DATA_DIR / "layouts").glob("layout_*.json")):
        layout_id = path.stem.replace("layout_", "")
        layouts.append({"id": layout_id, "name": f"{layout_id.upper()} Layout"})
    return {"layouts": layouts}


@app.get("/plates")
def list_plates(query: str = "", brand: str = "", limit: int = 80):
    """키보드 플레이트 카탈로그를 검색 조건에 맞게 반환한다."""
    return {
        "repo_path": str(keyboard_layout_repo_path()) if keyboard_layout_repo_path() else None,
        "plates": search_plates(query=query, brand=brand, limit=limit),
    }


@app.get("/plates/brands")
def plate_brands():
    """플레이트 카탈로그에서 사용 가능한 브랜드 목록을 반환한다."""
    return {
        "repo_path": str(keyboard_layout_repo_path()) if keyboard_layout_repo_path() else None,
        "brands": list_plate_brands(),
    }


@app.get("/plates/{plate_id}/preview")
def plate_preview(plate_id: str):
    """선택한 플레이트의 preview 이미지를 static 파일로 반환한다."""
    preview_path = get_plate_preview_path(plate_id)
    if preview_path is None or not preview_path.exists():
        raise HTTPException(status_code=404, detail="Plate preview not found")
    return FileResponse(preview_path)


@app.get("/viewer", response_class=HTMLResponse)
def model_viewer(model_url: str, camera: str = "perspective"):
    """model-viewer 4.0을 사용해 GLB URL을 렌더링하는 HTML viewer를 반환한다."""
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
    """키보드 단품 GLB를 생성하고 접근 가능한 model_url과 메타데이터를 반환한다."""
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
        switch_family=request.switch_family,
        keycap_profile=request.keycap_profile,
        mount_type=request.mount_type,
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
    """전체 데스크 셋업 GLB를 생성하고 접근 가능한 model_url과 메타데이터를 반환한다."""
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
        switch_family=request.switch_family,
        keycap_profile=request.keycap_profile,
        mount_type=request.mount_type,
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
    """업로드된 모델 파일을 처리하고 변환 또는 프록시 GLB URL을 반환한다."""
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


@app.post("/render/plate-drawing")
def render_plate_drawing(request: PlateDrawingRenderRequest):
    """선택한 플레이트 도면을 GLB로 변환하고 결과 URL을 반환한다."""
    plate = _selected_plate_or_400(request.plate_id)
    try:
        result = convert_plate_drawing_to_glb(
            plate=plate,
            model_dir=MODEL_DIR,
            public_base_url=_settings_base_url(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        **result,
        "plate": plate,
        "render_source": "drawing_converted_glb",
        "viewer": "model-viewer@4.0.0",
    }


@app.post("/models/library/prepare")
def prepare_library_model(request: LibraryModelRequest):
    try:
        source_path = resolve_static_library_path(request.path)
        suffix = source_path.suffix.lower()
        if suffix == ".glb":
            result = copy_existing_glb(
                source_path=source_path,
                model_dir=MODEL_DIR,
                public_base_url=_settings_base_url(),
            )
            return {
                **result,
                "source_file": source_path.name,
                "source_path": request.path,
                "conversion": "library_glb_passthrough",
                "message": "Shared GLB file is ready for the 3D viewer.",
            }
        if suffix in {".step", ".stp"}:
            return handle_model_upload_bytes(
                filename=source_path.name,
                data=source_path.read_bytes(),
                upload_dir=UPLOAD_DIR,
                model_dir=MODEL_DIR,
                public_base_url=_settings_base_url(),
            )
        raise ValueError("Only GLB, STEP, and STP files can be prepared for the 3D viewer.")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Library model preparation failed: {exc}") from exc


@app.get("/ai/providers")
def list_ai_providers():
    return available_text_providers()


@app.post("/ai/copy")
def generate_copy(request: AdContentRequest):
    """광고 문구 생성 요청을 AI 계층으로 전달하고 결과를 반환한다."""
    return generate_ad_copy(request.model_dump())


@app.post("/ai/copy/experiment")
def run_copy_experiment(request: CopyExperimentRequest):
    payload = request.model_dump(exclude={"providers"})
    return generate_copy_experiment(payload, request.providers)


@app.post("/ai/image")
def generate_image_reference(request: AdContentRequest):
    payload = request.model_dump()
    copy_result = generate_ad_copy(payload)
    image_prompt = build_image_prompt(payload, copy_result)
    image_reference = generate_local_image_reference(payload, image_prompt)
    safe_reference = safe_image_reference(image_reference)
    return {
        "copy": copy_result,
        "image_prompt": image_prompt,
        "local_image_reference": safe_reference,
        "image_embedded": bool(isinstance(image_reference, dict) and image_reference.get("has_image")),
    }


@app.post("/ai/image/jobs")
def create_image_generation_job(request: AdContentRequest):
    payload = request.model_dump()
    copy_result = generate_ad_copy(payload)
    image_prompt = build_image_prompt(payload, copy_result)
    job = create_image_job(payload, image_prompt)
    return {"copy": copy_result, "image_prompt": image_prompt, "job": job}


@app.get("/ai/image/jobs/{job_id}")
def get_image_generation_job(job_id: str):
    job = poll_image_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Image job not found.")
    return {"job": job}


@app.get("/ai/image/jobs")
def list_image_generation_jobs(limit: int = 20):
    items = list(IMAGE_JOB_STORE.all().values())
    items.sort(key=lambda record: record.get("created_at", 0), reverse=True)
    return {"jobs": items[: max(1, min(limit, 200))], "store_path": str(IMAGE_JOB_STORE.path)}


@app.post("/ai/image/jobs/{job_id}/quality")
def evaluate_image_job_quality(job_id: str):
    job = IMAGE_JOB_STORE.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Image job not found.")
    if job.get("status") not in {"completed"}:
        return {
            "job_id": job_id,
            "status": "skipped",
            "reason": f"Job status '{job.get('status')}' is not 'completed'.",
        }
    requested_ratio = (job.get("backend_config") or {}).get("aspect_ratio")
    report = evaluate_and_store(job, requested_ratio=requested_ratio)
    return {"report": report}


@app.get("/ai/image/jobs/{job_id}/quality")
def get_image_job_quality(job_id: str):
    report = quality_report_for(job_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Quality report not found.")
    return {"report": report}


@app.get("/ai/quality/summary")
def quality_summary():
    return quality_store_summary()


@app.post("/ai/poster")
def generate_poster(request: AdContentRequest):
    """광고 문구, 이미지 프롬프트, 포스터 SVG 생성을 묶어서 처리한다."""
    payload = request.model_dump()
    copy_result = generate_ad_copy(payload)
    image_prompt = build_image_prompt(payload, copy_result)

    image_reference = None
    if request.image_job_id:
        image_reference = image_reference_from_job(request.image_job_id)
    if not (isinstance(image_reference, dict) and image_reference.get("has_image")):
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

    safe_reference = safe_image_reference(image_reference)

    return {
        "copy": copy_result,
        "image_prompt": image_prompt,
        "poster_url": f"{_settings_base_url()}/static/posters/{poster_meta['poster_file']}",
        "poster_file": poster_meta["poster_file"],
        "poster_template": payload.get("poster_template", "minimal_card"),
        "local_image_reference": safe_reference,
        "image_reference": safe_reference,
        "image_job_id": request.image_job_id,
        "image_embedded": bool(image_b64),
    }
