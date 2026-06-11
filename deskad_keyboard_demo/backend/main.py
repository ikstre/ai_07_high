
from __future__ import annotations

import base64
from html import escape
from pathlib import Path

from fastapi.responses import HTMLResponse

from .ai import (
    IMAGE_JOB_STORE,
    available_text_providers,
    build_image_prompt,
    create_image_job,
    generate_ad_copy,
    generate_copy_experiment,
    generate_copy_variants,
    generate_image_reference as generate_ai_image_reference,
    image_reference_from_job,
    poll_image_job,
    public_image_job,
    safe_image_reference,
    save_poster_svg,
    selected_copy_or_generate,
)
from .quality_gate import (
    evaluate_and_store,
    quality_report_for,
    quality_store_summary,
)
from .security import install_secret_log_filter

install_secret_log_filter()
from .app_factory import create_app, ensure_static_dirs
from .cad import copy_existing_glb, handle_model_upload_bytes
from .config import get_settings, redacted_settings
from .drawing_converter import convert_plate_drawing_to_glb
from .errors import bad_request, not_found, server_error
from .filenames import unique_timestamped_model_path
from .library import (
    resolve_static_library_path,
)
from .plates import get_plate
from .renderer import build_desk_setup_scene_glb, build_keyboard_scene_glb
from .routes import register_routes
from .runtime_workers import activate_track
from .schemas import (
    ActivateTrackRequest,
    AdContentRequest,
    CopyExperimentRequest,
    DeskSetupRenderRequest,
    KeyboardRenderRequest,
    LibraryModelRequest,
    PlateDrawingRenderRequest,
    UploadedModelRequest,
)


BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
MODEL_DIR = STATIC_DIR / "models"
UPLOAD_DIR = STATIC_DIR / "uploads"
POSTER_DIR = STATIC_DIR / "posters"
DATA_DIR = BASE_DIR / "data"

ensure_static_dirs(MODEL_DIR, UPLOAD_DIR, POSTER_DIR)
app = create_app(STATIC_DIR)
register_routes(app)


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
        raise bad_request(f"Plate not found: {plate_id}")
    return plate


@app.get("/health")
def health():
    """서비스 상태와 마스킹된 설정 정보를 반환한다."""
    return {"status": "ok", "config": redacted_settings()}


@app.get("/security/config")
def security_config():
    """프론트엔드 상태 표시용 마스킹 설정 정보를 반환한다."""
    return redacted_settings()


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
    output_path = unique_timestamped_model_path(MODEL_DIR, request.product_name, fallback=f"keyboard_{request.layout}")
    model_name = output_path.name

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
    output_path = unique_timestamped_model_path(MODEL_DIR, request.product_name, fallback=f"desk_setup_{request.layout}")
    model_name = output_path.name

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
            product_name=request.product_name,
        )
    except ValueError as exc:
        raise bad_request(str(exc)) from exc
    except Exception as exc:
        raise server_error(f"Upload failed: {exc}") from exc


@app.post("/render/plate-drawing")
def render_plate_drawing(request: PlateDrawingRenderRequest):
    """선택한 플레이트 도면을 GLB로 변환하고 결과 URL을 반환한다."""
    plate = _selected_plate_or_400(request.plate_id)
    try:
        result = convert_plate_drawing_to_glb(
            plate=plate,
            model_dir=MODEL_DIR,
            public_base_url=_settings_base_url(),
            product_name=request.product_name,
        )
    except ValueError as exc:
        raise bad_request(str(exc)) from exc

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
                product_name=request.product_name,
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
                product_name=request.product_name,
            )
        raise ValueError("Only GLB, STEP, and STP files can be prepared for the 3D viewer.")
    except ValueError as exc:
        raise bad_request(str(exc)) from exc
    except Exception as exc:
        raise server_error(f"Library model preparation failed: {exc}") from exc


@app.get("/ai/providers")
def list_ai_providers():
    return available_text_providers()


@app.post("/ai/activate_track")
def activate_generation_track(request: ActivateTrackRequest):
    """트랙(생성 엔진) 선택 시점에 해당 GPU 워커를 백그라운드로 워밍업한다.

    단일 GPU exclusive 모드에서 트랙 전환 리로드(~75s)를 사용자가 이미지/카피
    생성을 누르기 전에 미리 시작해 체감 대기를 줄인다. 논블로킹으로 즉시 반환.
    """
    return activate_track(request.track)


@app.post("/ai/copy")
def generate_copy(request: AdContentRequest, force_regen: bool = False):
    """광고 문구 생성 요청을 AI 계층으로 전달하고 결과를 반환한다.

    force_regen=true 쿼리 파라미터를 추가하면 디스크 캐시를 무시하고 새 카피를 생성한다.
    """
    return generate_ad_copy(request.model_dump(), force_regen=force_regen)


@app.post("/ai/copy/experiment")
def run_copy_experiment(request: CopyExperimentRequest, force_regen: bool = False):
    payload = request.model_dump(exclude={"providers"})
    return generate_copy_experiment(payload, request.providers, force_regen=force_regen)


@app.post("/ai/copy/variants")
def run_copy_variants(request: AdContentRequest, n: int = 4, force_regen: bool = False):
    """Generate N copy variants from the selected engine (payload.engine) for selection."""
    return generate_copy_variants(request.model_dump(), n=n, force_regen=force_regen)


@app.post("/ai/image")
def generate_image_reference(request: AdContentRequest):
    payload = request.model_dump()
    copy_result = selected_copy_or_generate(payload)
    image_prompt = build_image_prompt(payload, copy_result)
    image_reference = generate_ai_image_reference(payload, image_prompt)
    safe_reference = safe_image_reference(image_reference)
    return {
        "copy": copy_result,
        "image_prompt": image_prompt,
        "image_reference": safe_reference,
        "image_embedded": bool(isinstance(image_reference, dict) and image_reference.get("has_image")),
    }


@app.post("/ai/image/jobs")
def create_image_generation_job(request: AdContentRequest, force_regen: bool = False):
    """이미지 생성 작업을 큐에 넣고 job 메타데이터를 반환한다.

    force_regen=true 쿼리 파라미터를 추가하면 캐시를 무시하고 새 seed로 이미지를 생성한다.
    """
    payload = request.model_dump()
    copy_result = selected_copy_or_generate(payload)
    image_prompt = build_image_prompt(payload, copy_result)
    job = create_image_job(payload, image_prompt, force_regen=force_regen)
    return {"copy": copy_result, "image_prompt": image_prompt, "job": job}


@app.get("/ai/image/jobs/{job_id}")
def get_image_generation_job(job_id: str):
    job = poll_image_job(job_id)
    if job is None:
        raise not_found("Image job not found.")
    return {"job": job}


@app.get("/ai/image/jobs")
def list_image_generation_jobs(limit: int = 20):
    items = list(IMAGE_JOB_STORE.all().values())
    items.sort(key=lambda record: record.get("created_at", 0), reverse=True)
    capped = items[: max(1, min(limit, 200))]
    # 목록에선 이미지 바이트(local_image_reference.image_b64/_b64s) 제외 — 수십 MB 응답 방지.
    # 실제 바이트는 단건 조회(/ai/image/jobs/{id})에서만 내려간다.
    jobs = [public_image_job(job) for job in capped]
    return {"jobs": jobs, "store_path": str(IMAGE_JOB_STORE.path)}


@app.post("/ai/image/jobs/{job_id}/quality")
def evaluate_image_job_quality(job_id: str):
    job = IMAGE_JOB_STORE.get(job_id)
    if not job:
        raise not_found("Image job not found.")
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
        raise not_found("Quality report not found.")
    return {"report": report}


@app.get("/ai/quality/summary")
def quality_summary():
    return quality_store_summary()


@app.post("/ai/poster")
def generate_poster(request: AdContentRequest):
    """광고 문구, 이미지 프롬프트, 포스터 SVG 생성을 묶어서 처리한다."""
    payload = request.model_dump()
    copy_result = selected_copy_or_generate(payload)
    image_prompt = build_image_prompt(payload, copy_result)

    image_reference = None
    if request.image_job_id:
        image_reference = image_reference_from_job(request.image_job_id)
    if not (isinstance(image_reference, dict) and image_reference.get("has_image")):
        image_reference = generate_ai_image_reference(payload, image_prompt)

    image_b64 = None
    image_b64s = None
    if isinstance(image_reference, dict) and image_reference.get("has_image"):
        image_b64 = image_reference.get("image_b64")
        raw_image_b64s = image_reference.get("image_b64s")
        if isinstance(raw_image_b64s, list):
            image_b64s = [item for item in raw_image_b64s if isinstance(item, str) and item][:3]
    poster_meta = save_poster_svg(
        payload=payload,
        copy_result=copy_result,
        poster_dir=POSTER_DIR,
        image_b64=image_b64,
        image_b64s=image_b64s,
    )

    safe_reference = safe_image_reference(image_reference)

    return {
        "copy": copy_result,
        "image_prompt": image_prompt,
        "poster_url": f"{_settings_base_url()}/static/posters/{poster_meta['poster_file']}",
        "poster_file": poster_meta["poster_file"],
        "poster_template": payload.get("poster_template", "minimal_card"),
        "image_reference": safe_reference,
        "image_job_id": request.image_job_id,
        "image_embedded": bool(image_b64 or image_b64s),
        "image_count": len(image_b64s) if image_b64s else (1 if image_b64 else 0),
    }
