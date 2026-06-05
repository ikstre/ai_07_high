from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path


_SLUG_PART_RE = re.compile(r"[A-Za-z0-9]+")


def product_slug(value: str | None, *, fallback: str = "model") -> str:
    """Return a filesystem/URL-safe ASCII slug for generated model files."""
    parts = _SLUG_PART_RE.findall(str(value or "").lower())
    slug = "_".join(parts)[:80].strip("_")
    return slug or fallback


def timestamped_model_filename(product_name: str | None, *, fallback: str = "model", suffix: str = ".glb") -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    clean_suffix = suffix if suffix.startswith(".") else f".{suffix}"
    return f"{stamp}_{product_slug(product_name, fallback=fallback)}{clean_suffix.lower()}"


def unique_timestamped_model_path(
    directory: Path,
    product_name: str | None,
    *,
    fallback: str = "model",
    suffix: str = ".glb",
) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    filename = timestamped_model_filename(product_name, fallback=fallback, suffix=suffix)
    candidate = directory / filename
    if not candidate.exists():
        return candidate

    stem = candidate.stem
    clean_suffix = candidate.suffix
    for counter in range(2, 1000):
        numbered = directory / f"{stem}_{counter}{clean_suffix}"
        if not numbered.exists():
            return numbered
    raise FileExistsError(f"Could not allocate a unique generated model filename for {filename}")
