"""Disk-backed result cache for text and image AI requests.

Cache layout:
  data/runtime/cache/text/<sha256>.json   — ad copy results
  data/runtime/cache/image/<sha256>.json  — image job metadata (no binary bytes)

Caching is always active when GPU_WORKER_MODE is configured so that cache hits
avoid GPU work even in always_on mode.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


_BACKEND_BASE_DIR = Path(__file__).resolve().parent.parent


def _cache_root() -> Path:
    override = os.getenv("GPU_WORKER_CACHE_DIR", "").strip()
    if override:
        return Path(override).expanduser()
    return _BACKEND_BASE_DIR / "data" / "runtime" / "cache"


def _text_cache_dir() -> Path:
    return _cache_root() / "text"


def _image_cache_dir() -> Path:
    return _cache_root() / "image"


def _workflow_content_hash(workflow_path_value: str) -> str:
    """Hash workflow JSON file content for image cache key stability."""
    if not workflow_path_value:
        return "no_workflow"
    p = Path(workflow_path_value).expanduser()
    if not p.is_absolute():
        p = _BACKEND_BASE_DIR / p
    if not p.exists():
        return f"missing:{workflow_path_value}"
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16]


def make_text_cache_key(payload: dict, provider_id: str, model_id: str, policy_version: str = "v1") -> str:
    """Stable SHA256 key for a text copy request.

    Includes all ad-content fields that affect the LLM output.
    provider + model + policy_version ensure separate cache entries per backend.
    """
    normalized = {
        "product_name": payload.get("product_name", ""),
        "product_type": payload.get("product_type", ""),
        "price": payload.get("price", ""),
        "target_channel": payload.get("target_channel", ""),
        "target_customer": payload.get("target_customer", ""),
        "selling_point": payload.get("selling_point", ""),
        "ad_tone": payload.get("ad_tone", ""),
        "theme": payload.get("theme", ""),
        "assets": sorted(str(a) for a in payload.get("assets", [])),
        "extra_request": payload.get("extra_request", ""),
        "case_finish": payload.get("case_finish", ""),
        "plate_material": payload.get("plate_material", ""),
        "switch_stem": payload.get("switch_stem", ""),
        "switch_family": payload.get("switch_family", ""),
        "keycap_profile": payload.get("keycap_profile", ""),
        "mount_type": payload.get("mount_type", ""),
        "pcb_color": payload.get("pcb_color", ""),
        "monitor_size": payload.get("monitor_size", ""),
        "provider": provider_id,
        "model": model_id,
        "policy": policy_version,
    }
    blob = json.dumps(normalized, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def make_image_cache_key(
    image_prompt: str,
    payload: dict,
    width: int,
    height: int,
    workflow_path: str = "",
) -> str:
    """Stable SHA256 key for an image generation request.

    Seed is intentionally excluded — the same prompt+workflow always returns
    the cached image. Callers pass force_regen=True to bypass the cache.
    """
    model_config = json.dumps(
        {
            "backend": payload.get("image_model_backend", ""),
            "flux_variant": os.getenv("FLUX_MODEL_VARIANT", ""),
            "quantization": os.getenv("IMAGE_QUANTIZATION", ""),
        },
        sort_keys=True,
    )
    normalized = {
        "image_prompt": image_prompt,
        "workflow_hash": _workflow_content_hash(workflow_path),
        "width": width,
        "height": height,
        "model_config": model_config,
    }
    blob = json.dumps(normalized, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def get_text_cache(cache_key: str) -> dict | None:
    """Return cached ad copy result dict or None on miss."""
    path = _text_cache_dir() / f"{cache_key}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return None
        data["cache_hit"] = True
        data["cache_key"] = cache_key
        return data
    except Exception:
        return None


def put_text_cache(cache_key: str, result: dict) -> None:
    """Write ad copy result to disk cache (failures are silently ignored)."""
    try:
        _text_cache_dir().mkdir(parents=True, exist_ok=True)
        path = _text_cache_dir() / f"{cache_key}.json"
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        path.chmod(0o600)
    except Exception:
        pass


def get_image_cache(cache_key: str) -> dict | None:
    """Return cached image job metadata dict or None on miss."""
    path = _image_cache_dir() / f"{cache_key}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return None
        data["cache_hit"] = True
        data["cache_key"] = cache_key
        return data
    except Exception:
        return None


def put_image_cache(cache_key: str, job: dict) -> None:
    """Write image job metadata to disk cache (image_b64 bytes are excluded)."""
    try:
        _image_cache_dir().mkdir(parents=True, exist_ok=True)
        path = _image_cache_dir() / f"{cache_key}.json"
        safe = {k: v for k, v in job.items() if k not in ("image_b64",)}
        path.write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")
        path.chmod(0o600)
    except Exception:
        pass
