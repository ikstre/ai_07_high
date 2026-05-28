from __future__ import annotations

import json
import mimetypes
from pathlib import Path

from .config import get_settings


BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
MODEL_DIR = STATIC_DIR / "models"
REFERENCE_DIR = STATIC_DIR / "uploads" / "reference_drawings"
REFERENCE_MANIFEST_PATH = BASE_DIR / "data" / "reference_assets.json"

MODEL_EXTENSIONS = {".glb", ".gltf", ".step", ".stp", ".stl", ".obj", ".fbx"}
DRAWING_EXTENSIONS = {".svg", ".dxf", ".dwg", ".pdf", ".png", ".jpg", ".jpeg", ".kicad_pcb", ".wrl"}
ALLOWED_LIBRARY_EXTENSIONS = MODEL_EXTENSIONS | DRAWING_EXTENSIONS | {".json"}


def shared_data_dir() -> Path:
    return Path(get_settings().shared_data_dir).expanduser()


def shared_model_dir() -> Path:
    return Path(get_settings().shared_model_dir).expanduser()


def library_roots() -> list[dict]:
    return [
        {
            "id": "generated_models",
            "label": "Generated/static models",
            "root": MODEL_DIR,
            "path_prefix": "models",
            "url_prefix": "static/models",
            "storage": "static",
        },
        {
            "id": "static_reference_drawings",
            "label": "Legacy static reference drawings",
            "root": REFERENCE_DIR,
            "path_prefix": "uploads/reference_drawings",
            "url_prefix": "static/uploads/reference_drawings",
            "storage": "static",
        },
        {
            "id": "shared_model",
            "label": "Shared model folder",
            "root": shared_model_dir(),
            "path_prefix": "shared/models",
            "url_prefix": "shared/models",
            "storage": "shared_model",
        },
        {
            "id": "shared_data",
            "label": "Shared data folder",
            "root": shared_data_dir(),
            "path_prefix": "shared/data",
            "url_prefix": "shared/data",
            "storage": "shared_data",
        },
    ]


def _url_for_path(path: Path, *, public_base_url: str, root: Path, url_prefix: str) -> str:
    relative_path = path.relative_to(root).as_posix()
    return f"{public_base_url.rstrip('/')}/{url_prefix}/{relative_path}"


def _library_path(path: Path, *, root: Path, path_prefix: str) -> str:
    relative_path = path.relative_to(root).as_posix()
    return f"{path_prefix}/{relative_path}"


def _file_kind(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".glb", ".gltf", ".stl", ".obj", ".fbx"}:
        return "model"
    if suffix in {".step", ".stp", ".dxf", ".dwg", ".kicad_pcb", ".wrl"}:
        return "cad"
    if suffix in {".svg", ".pdf", ".png", ".jpg", ".jpeg"}:
        return "reference"
    return "file"


def _file_record(path: Path, *, public_base_url: str, root_config: dict) -> dict:
    root = root_config["root"]
    mime_type, _encoding = mimetypes.guess_type(path.name)
    return {
        "name": path.name,
        "path": _library_path(path, root=root, path_prefix=root_config["path_prefix"]),
        "root": root_config["id"],
        "root_path": str(root),
        "storage": root_config["storage"],
        "url": _url_for_path(path, public_base_url=public_base_url, root=root, url_prefix=root_config["url_prefix"]),
        "kind": _file_kind(path),
        "extension": path.suffix.lower(),
        "size_bytes": path.stat().st_size,
        "mime_type": mime_type or "application/octet-stream",
    }


def iter_library_files() -> list[tuple[Path, dict]]:
    files: list[tuple[Path, dict]] = []
    for root_config in library_roots():
        root = root_config["root"]
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if path.is_file() and path.suffix.lower() in ALLOWED_LIBRARY_EXTENSIONS:
                files.append((path, root_config))
    return files


def list_library_files(public_base_url: str) -> list[dict]:
    return [
        _file_record(path, public_base_url=public_base_url, root_config=root_config)
        for path, root_config in iter_library_files()
    ]


def _reference_target_path(item: dict) -> tuple[Path, str]:
    storage = item.get("storage", "shared_data")
    local_path = item.get("local_path", "")
    if storage == "shared_data":
        return shared_data_dir() / local_path, f"shared/data/{local_path}"
    if storage == "shared_model":
        return shared_model_dir() / local_path, f"shared/models/{local_path}"
    return STATIC_DIR / local_path, local_path


def _reference_url(path: Path, *, public_base_url: str, storage: str, local_path: str) -> str:
    base = public_base_url.rstrip("/")
    if storage == "shared_data":
        return f"{base}/shared/data/{local_path}"
    if storage == "shared_model":
        return f"{base}/shared/models/{local_path}"
    return f"{base}/static/{local_path}"


def load_reference_manifest(public_base_url: str) -> list[dict]:
    if not REFERENCE_MANIFEST_PATH.exists():
        return []
    data = json.loads(REFERENCE_MANIFEST_PATH.read_text(encoding="utf-8"))
    records = data if isinstance(data, list) else data.get("references", [])
    enriched: list[dict] = []
    for record in records:
        item = dict(record)
        local_path = item.get("local_path")
        storage = item.get("storage", "shared_data")
        if local_path:
            path, library_path = _reference_target_path(item)
            item["downloaded"] = path.exists()
            item["path"] = library_path
            item["storage"] = storage
            item["root_path"] = str(path.parent if path.name else path)
            if path.exists():
                item["url"] = _reference_url(path, public_base_url=public_base_url, storage=storage, local_path=local_path)
                item["size_bytes"] = path.stat().st_size
                item["extension"] = path.suffix.lower()
        else:
            item["downloaded"] = False
        enriched.append(item)
    return enriched


def resolve_static_library_path(relative_path: str) -> Path:
    if not relative_path or relative_path.startswith("/"):
        raise ValueError("Library path must be relative to a shared/static library root.")

    for root_config in library_roots():
        prefix = root_config["path_prefix"].rstrip("/") + "/"
        if not relative_path.startswith(prefix):
            continue
        inner_path = relative_path[len(prefix):]
        candidate = (root_config["root"] / inner_path).resolve()
        root = root_config["root"].resolve()
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise ValueError("Library path escapes the configured library directory.") from exc
        if not candidate.exists() or not candidate.is_file():
            raise ValueError("Library file does not exist.")
        if candidate.suffix.lower() not in ALLOWED_LIBRARY_EXTENSIONS:
            raise ValueError("This file type is not supported by the shared library.")
        return candidate

    raise ValueError("Library path must start with models/, uploads/reference_drawings/, shared/models/, or shared/data/.")


def model_compatible_extensions() -> list[str]:
    return sorted(MODEL_EXTENSIONS)


def shared_library_status() -> dict:
    data_dir = shared_data_dir()
    model_dir = shared_model_dir()
    return {
        "shared_data_dir": str(data_dir),
        "shared_model_dir": str(model_dir),
        "shared_data_exists": data_dir.exists(),
        "shared_model_exists": model_dir.exists(),
    }
