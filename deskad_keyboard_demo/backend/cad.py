
from __future__ import annotations

import hashlib
import shlex
import shutil
import subprocess
from pathlib import Path
from uuid import uuid4

from .config import get_settings
from .renderer import build_uploaded_step_proxy_glb


ALLOWED_MODEL_EXTENSIONS = {".step", ".stp", ".glb"}


def _safe_suffix(filename: str) -> str:
    suffix = Path(filename or "").suffix.lower()
    if suffix not in ALLOWED_MODEL_EXTENSIONS:
        raise ValueError("Only STEP, STP, and GLB files are supported.")
    return suffix


def _assert_upload_size(data: bytes) -> None:
    settings = get_settings()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(data) > max_bytes:
        raise ValueError(f"Uploaded file is too large. Limit: {settings.max_upload_mb}MB")


def _run_step_converter(input_path: Path, output_path: Path) -> tuple[bool, str]:
    settings = get_settings()
    if not settings.step_converter_cmd:
        return False, "STEP_CONVERTER_CMD is not configured."

    command = [part.format(input=str(input_path), output=str(output_path)) for part in shlex.split(settings.step_converter_cmd)]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=settings.step_converter_timeout_seconds,
            check=False,
        )
    except Exception as exc:
        return False, f"STEP converter failed to start: {exc}"

    if result.returncode != 0 or not output_path.exists():
        stderr = (result.stderr or result.stdout or "").strip()[-500:]
        return False, f"STEP converter returned {result.returncode}: {stderr}"
    return True, "STEP converted to GLB."


def handle_model_upload_bytes(*, filename: str, data: bytes, upload_dir: Path, model_dir: Path, public_base_url: str) -> dict:
    suffix = _safe_suffix(filename or "uploaded.step")
    _assert_upload_size(data)

    digest = hashlib.sha256(data).hexdigest()[:12]
    upload_dir.mkdir(parents=True, exist_ok=True)
    model_dir.mkdir(parents=True, exist_ok=True)

    if suffix == ".glb":
        if not data.startswith(b"glTF"):
            raise ValueError("The uploaded GLB header is invalid.")
        model_name = f"uploaded_{digest}.glb"
        output_path = model_dir / model_name
        output_path.write_bytes(data)
        return {
            "model_url": f"{public_base_url}/static/models/{model_name}",
            "source_file": filename,
            "source_size": len(data),
            "sha256": digest,
            "conversion": "glb_passthrough",
            "message": "Uploaded GLB is ready for the 3D viewer.",
            "model_file": model_name,
        }

    source_name = f"uploaded_{digest}{suffix}"
    source_path = upload_dir / source_name
    source_path.write_bytes(data)
    model_name = f"uploaded_{digest}.glb"
    output_path = model_dir / model_name

    converted, message = _run_step_converter(source_path, output_path)
    if converted:
        return {
            "model_url": f"{public_base_url}/static/models/{model_name}",
            "source_file": filename,
            "source_size": len(data),
            "sha256": digest,
            "conversion": "step_to_glb",
            "message": message,
            "model_file": model_name,
        }

    proxy_meta = build_uploaded_step_proxy_glb(
        output_path=output_path,
        source_name=filename or source_name,
        source_size=len(data),
    )
    proxy_meta.update(
        {
            "model_url": f"{public_base_url}/static/models/{model_name}",
            "sha256": digest,
            "converter_note": message,
        }
    )
    return proxy_meta


def copy_existing_glb(*, source_path: Path, model_dir: Path, public_base_url: str) -> dict:
    digest = hashlib.sha256(source_path.read_bytes()).hexdigest()[:12]
    model_name = f"library_{digest}.glb"
    output_path = model_dir / model_name
    if not output_path.exists():
        shutil.copyfile(source_path, output_path)
    return {"model_url": f"{public_base_url}/static/models/{model_name}", "model_file": model_name}
