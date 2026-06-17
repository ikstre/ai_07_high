"""Disk-backed result cache for text and image AI requests.

Cache layout:
  data/runtime/cache/text/<sha256>.json   — ad copy results
  data/runtime/cache/image/<sha256>.json  — image job metadata (no binary bytes)

Caching is always active when GPU_WORKER_MODE is configured so that cache hits
avoid GPU work even in always_on mode.

To bound long-term disk growth each write prunes its directory: expired entries
(TTL via GPU_WORKER_CACHE_MAX_AGE_DAYS) are removed first, then the least-
recently-used entries beyond GPU_WORKER_CACHE_MAX_ENTRIES. Reads bump mtime so
recency reflects use, not just creation.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from pathlib import Path


_BACKEND_BASE_DIR = Path(__file__).resolve().parent.parent

# 다중 접속 시 put/put·put/prune이 같은 파일/디렉터리를 두고 경쟁한다(2026-06-11 QA).
# 쓰기·prune은 프로세스 내 락으로 직렬화하고, 파일 자체는 tmp→os.replace 원자 교체로
# 독자가 절대 부분 쓰기를 읽지 않게 한다(읽기는 락 불필요).
_CACHE_WRITE_LOCK = threading.Lock()


def _atomic_write_json(path: Path, obj: dict) -> None:
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.chmod(0o600)
        os.replace(tmp, path)
    except Exception:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def _cache_root() -> Path:
    override = os.getenv("GPU_WORKER_CACHE_DIR", "").strip()
    if override:
        return Path(override).expanduser()
    return _BACKEND_BASE_DIR / "data" / "runtime" / "cache"


def _text_cache_dir() -> Path:
    return _cache_root() / "text"


def _image_cache_dir() -> Path:
    return _cache_root() / "image"


# ── eviction (TTL + LRU by mtime) ──────────────────────────────────────────────

def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _max_entries() -> int:
    """Per-directory cap on cached entries (<=0 disables the count cap)."""
    return _int_env("GPU_WORKER_CACHE_MAX_ENTRIES", 500)


def _max_age_seconds() -> int:
    """Entry TTL in seconds derived from days (<=0 disables expiry)."""
    return max(_int_env("GPU_WORKER_CACHE_MAX_AGE_DAYS", 30), 0) * 86400


def _touch(path: Path) -> None:
    """Bump mtime so cache hits count as recency for LRU eviction."""
    try:
        os.utime(path, None)
    except OSError:
        pass


def _prune_dir(directory: Path, *, max_entries: int, max_age_seconds: int) -> int:
    """Evict expired (TTL) then least-recently-used (.json) entries.

    mtime is the recency signal — reads bump it, writes set it. Returns the
    number of files removed. Best-effort: never raises, skips files that
    vanish under concurrent writers.
    """
    try:
        scan = list(os.scandir(directory))
    except OSError:
        return 0

    entries: list[tuple[str, float]] = []
    for e in scan:
        try:
            if e.is_file() and e.name.endswith(".json"):
                entries.append((e.path, e.stat().st_mtime))
        except OSError:
            continue

    now = time.time()
    removed = 0
    survivors: list[tuple[str, float]] = []
    for path, mtime in entries:
        if max_age_seconds and (now - mtime) > max_age_seconds:
            removed += _safe_unlink(path)
        else:
            survivors.append((path, mtime))

    if max_entries > 0 and len(survivors) > max_entries:
        survivors.sort(key=lambda item: item[1])  # oldest first
        for path, _ in survivors[: len(survivors) - max_entries]:
            removed += _safe_unlink(path)

    return removed


def _safe_unlink(path: str) -> int:
    try:
        os.remove(path)
        return 1
    except OSError:
        return 0


def prune_caches() -> dict:
    """Prune both text and image caches; returns removed counts per directory."""
    max_entries, max_age = _max_entries(), _max_age_seconds()
    with _CACHE_WRITE_LOCK:
        return {
            "text": _prune_dir(_text_cache_dir(), max_entries=max_entries, max_age_seconds=max_age),
            "image": _prune_dir(_image_cache_dir(), max_entries=max_entries, max_age_seconds=max_age),
        }


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
        # 배열·색상은 카피 컨텍스트(build_*_prompt)에 들어가므로 키에 포함해야
        # "배열/색만 바꿔도 옛 카피가 캐시 히트" 회귀를 막는다.
        "layout": payload.get("layout", ""),
        "case_color": payload.get("case_color", ""),
        "keycap_color": payload.get("keycap_color", ""),
        "accent_keycap_color": payload.get("accent_keycap_color", ""),
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

    layout·case/keycap/accent 색상은 build_image_prompt가 image_prompt 문자열에
    그대로 녹여 넣으므로(배열/색이 바뀌면 prompt가 바뀜) 이 키가 이미 그 변화를
    반영한다 — 별도 필드로 중복 추가하지 않는다(make_text_cache_key와 대비).

    img2img 레퍼런스(init latent로 들어가는 실제 픽셀)·denoise는 prompt에 안 녹으므로
    키에 직접 넣는다 — 프롬프트·비율이 같아도 책상 배치가 다르면 다른 캐시 항목이어야
    한다(QA 2026-06-10 #2).
    """
    model_config = json.dumps(
        {
            "backend": payload.get("image_model_backend", ""),
            "flux_variant": os.getenv("FLUX_MODEL_VARIANT", ""),
            "quantization": os.getenv("IMAGE_QUANTIZATION", ""),
            "negative_prompt": os.getenv("COMFYUI_NEGATIVE_PROMPT", ""),
            "lora": os.getenv("COMFYUI_LORA_NAME", ""),
            # ControlNet 모델/강도는 워크플로 placeholder라 workflow_hash로는 안 잡힌다
            # (파일 내용은 동일) → strength 스윕이 캐시에 막히지 않도록 키에 직접 넣는다.
            "controlnet_model": os.getenv("COMFYUI_CONTROLNET_MODEL", ""),
            "controlnet_strength": os.getenv("COMFYUI_CONTROLNET_STRENGTH", ""),
            "controlnet_end_percent": os.getenv("COMFYUI_CONTROLNET_END_PERCENT", ""),
            "best_of_n": os.getenv("COMFYUI_BEST_OF_N", ""),
        },
        sort_keys=True,
    )
    reference_blob = "|".join(
        str(payload.get(key) or "")
        for key in ("reference_image_b64", "reference_image_topdown_b64", "reference_asset_path")
    )
    normalized = {
        "image_prompt": image_prompt,
        "workflow_hash": _workflow_content_hash(workflow_path),
        "width": width,
        "height": height,
        "model_config": model_config,
        "reference_hash": (
            hashlib.sha256(reference_blob.encode("utf-8")).hexdigest()[:16]
            if reference_blob.strip("|")
            else ""
        ),
        "reference_is_composition": bool(payload.get("reference_is_composition")),
        "shot_type": str(payload.get("shot_type") or ""),
        "denoise": [
            os.getenv("COMFYUI_IMG2IMG_DENOISE", ""),
            os.getenv("COMFYUI_COMPOSITION_DENOISE", ""),
        ],
        "steps": [
            os.getenv("COMFYUI_STEPS", ""),
            os.getenv("COMFYUI_COMPOSITION_STEPS", ""),
        ],
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
        _touch(path)
        return data
    except Exception:
        return None


def put_text_cache(cache_key: str, result: dict) -> None:
    """Write ad copy result to disk cache (failures are silently ignored)."""
    with _CACHE_WRITE_LOCK:
        try:
            _text_cache_dir().mkdir(parents=True, exist_ok=True)
            _atomic_write_json(_text_cache_dir() / f"{cache_key}.json", result)
        except Exception:
            pass
        _prune_dir(_text_cache_dir(), max_entries=_max_entries(), max_age_seconds=_max_age_seconds())


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
        _touch(path)
        return data
    except Exception:
        return None


def put_image_cache(cache_key: str, job: dict) -> None:
    """Write image job metadata to disk cache (image_b64 bytes are excluded)."""
    with _CACHE_WRITE_LOCK:
        try:
            _image_cache_dir().mkdir(parents=True, exist_ok=True)
            safe = {k: v for k, v in job.items() if k not in ("image_b64", "image_b64s")}
            _atomic_write_json(_image_cache_dir() / f"{cache_key}.json", safe)
        except Exception:
            pass
        _prune_dir(_image_cache_dir(), max_entries=_max_entries(), max_age_seconds=_max_age_seconds())
