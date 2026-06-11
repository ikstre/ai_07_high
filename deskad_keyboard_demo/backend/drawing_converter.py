from __future__ import annotations

import hashlib
import shlex
import subprocess
from pathlib import Path

from .config import get_settings
from .filenames import unique_timestamped_model_path
from .plates import keyboard_layout_repo_path


SUPPORTED_DRAWING_EXTENSIONS = {".dwg", ".dxf", ".glb"}


def _plate_source_path(plate: dict) -> Path:
    """플레이트 카탈로그 항목에서 실제 도면 파일 경로를 계산한다."""
    repo_path = keyboard_layout_repo_path()
    if repo_path is None:
        raise ValueError("keyboard_layout repo path is not configured.")

    source_path = repo_path / plate["file_path"].replace("\\", "/")
    if not source_path.exists():
        raise ValueError(f"Drawing file does not exist: {source_path}")

    suffix = source_path.suffix.lower()
    if suffix not in SUPPORTED_DRAWING_EXTENSIONS:
        raise ValueError(f"Unsupported drawing extension: {suffix}")

    return source_path


def convert_plate_drawing_to_glb(
    *,
    plate: dict,
    model_dir: Path,
    public_base_url: str,
    product_name: str | None = None,
) -> dict:
    """플레이트 도면 데이터를 렌더러가 표시할 수 있는 GLB 프록시 모델로 변환한다."""
    source_path = _plate_source_path(plate)
    digest = hashlib.sha256(str(source_path).encode("utf-8") + source_path.read_bytes()).hexdigest()[:12]
    output_path = unique_timestamped_model_path(
        model_dir,
        product_name or plate.get("name") or plate.get("id") or source_path.stem,
        fallback=f"plate_{plate.get('id', digest)}",
    )
    model_name = output_path.name

    if source_path.suffix.lower() == ".glb":
        # unique_timestamped_model_path가 빈 파일로 경로를 선점해 두므로 항상 내용을 쓴다.
        output_path.write_bytes(source_path.read_bytes())
        return {
            "model_url": f"{public_base_url}/static/models/{model_name}",
            "model_file": model_name,
            "source_file": str(source_path),
            "conversion": "glb_passthrough",
            "message": "Selected GLB drawing asset is ready for model-viewer.",
        }

    settings = get_settings()
    if not settings.drawing_converter_cmd:
        raise ValueError(
            "DRAWING_CONVERTER_CMD is not configured. "
            "DWG/DXF cannot be rendered as GLB until an external converter is configured."
        )

    model_dir.mkdir(parents=True, exist_ok=True)
    command = [
        part.format(input=str(source_path), output=str(output_path))
        for part in shlex.split(settings.drawing_converter_cmd)
    ]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=settings.drawing_converter_timeout_seconds,
            check=False,
        )
    except Exception as exc:
        raise ValueError(f"Drawing converter failed to start: {exc}") from exc

    # 경로 선점으로 빈 파일이 미리 존재하므로 실제 내용이 쓰였는지(size>0)까지 본다.
    if result.returncode != 0 or not output_path.exists() or output_path.stat().st_size == 0:
        stderr = (result.stderr or result.stdout or "").strip()[-800:]
        raise ValueError(f"Drawing converter returned {result.returncode}: {stderr}")

    return {
        "model_url": f"{public_base_url}/static/models/{model_name}",
        "model_file": model_name,
        "source_file": str(source_path),
        "conversion": f"{source_path.suffix.lower().lstrip('.')}_to_glb",
        "message": "Selected drawing was converted to GLB.",
    }
