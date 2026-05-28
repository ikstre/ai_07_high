from __future__ import annotations

import base64
import io
import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import requests

from .job_store import ImageJobStore


@dataclass
class ImageQualityReport:
    """Lightweight quality gate snapshot for one image job.

    Heavy metrics (CLIP-I, LPIPS, FID, full OCR) intentionally live in separate
    workers. This schema captures only fast, dependency-light signals so the
    gate API can be exercised end-to-end without a GPU/ML stack present.
    """

    job_id: str
    status: str = "pending"
    width: int | None = None
    height: int | None = None
    bytes: int | None = None
    aspect_ratio_requested: str | None = None
    aspect_ratio_actual: str | None = None
    aspect_ratio_match: bool | None = None
    has_watermark: bool | None = None
    ocr_text_excerpt: str = ""
    canny_edge_iou_vs_reference: float | None = None
    notes: list[str] = field(default_factory=list)
    evaluator: str = "skeleton"
    evaluated_at: int = field(default_factory=lambda: int(time.time()))
    raw: dict[str, Any] = field(default_factory=dict)


def _quality_store_path() -> Path:
    override = os.getenv("IMAGE_QUALITY_STORE_PATH")
    if override:
        return Path(override).expanduser()
    base = Path(__file__).resolve().parent.parent
    return base / "data" / "runtime" / "image_quality.jsonl"


class ImageQualityStore:
    """Thin wrapper around ImageJobStore for quality reports keyed by job_id."""

    def __init__(self, path: Path):
        self._inner = ImageJobStore(path)

    @property
    def path(self) -> Path:
        return self._inner.path

    def get(self, job_id: str) -> dict | None:
        return self._inner.get(job_id)

    def save(self, report: ImageQualityReport) -> dict:
        record = asdict(report)
        return self._inner.save(record)

    def all(self) -> dict[str, dict]:
        return self._inner.all()


IMAGE_QUALITY_STORE = ImageQualityStore(_quality_store_path())


def _parse_ratio(label: str | None) -> tuple[int, int] | None:
    if not label:
        return None
    parts = str(label).split(":")
    if len(parts) != 2:
        return None
    try:
        a = int(parts[0])
        b = int(parts[1])
    except ValueError:
        return None
    if a <= 0 or b <= 0:
        return None
    return a, b


def _ratio_label(width: int, height: int) -> str | None:
    if width <= 0 or height <= 0:
        return None
    ratio = width / height
    candidates = [("1:1", 1.0), ("4:5", 4 / 5), ("16:9", 16 / 9), ("9:16", 9 / 16), ("3:2", 3 / 2)]
    closest = min(candidates, key=lambda item: abs(item[1] - ratio))
    return closest[0]


def _decode_image_b64_to_bytes(image_b64: str) -> bytes | None:
    if not isinstance(image_b64, str) or not image_b64:
        return None
    payload = image_b64.split(",", 1)[-1] if image_b64.startswith("data:") else image_b64
    try:
        return base64.b64decode(payload, validate=True)
    except Exception:
        return None


def _png_dimensions(data: bytes) -> tuple[int, int] | None:
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    try:
        width = int.from_bytes(data[16:20], "big")
        height = int.from_bytes(data[20:24], "big")
    except Exception:
        return None
    if width <= 0 or height <= 0:
        return None
    return width, height


def _jpeg_dimensions(data: bytes) -> tuple[int, int] | None:
    if len(data) < 4 or data[:2] != b"\xff\xd8":
        return None
    i = 2
    n = len(data)
    while i < n - 9:
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        i += 2
        if marker in (0xD8, 0xD9):
            continue
        if 0xD0 <= marker <= 0xD7:
            continue
        if i + 2 > n:
            break
        segment_len = int.from_bytes(data[i : i + 2], "big")
        if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
            if i + 7 > n:
                return None
            height = int.from_bytes(data[i + 3 : i + 5], "big")
            width = int.from_bytes(data[i + 5 : i + 7], "big")
            return width, height
        i += segment_len
    return None


def _image_dimensions_from_bytes(data: bytes) -> tuple[int, int] | None:
    return _png_dimensions(data) or _jpeg_dimensions(data)


def _fetch_first_image_bytes(job: dict) -> tuple[bytes | None, str]:
    """Return (image_bytes, source_label). Skeleton: no ML stack required."""

    local_reference = job.get("local_image_reference")
    if isinstance(local_reference, dict):
        candidate = _decode_image_b64_to_bytes(local_reference.get("image_b64", ""))
        if candidate:
            return candidate, "local_image_b64"

    images = job.get("images") or []
    if images:
        url = images[0].get("url") if isinstance(images[0], dict) else None
        if url:
            try:
                response = requests.get(url, timeout=20)
                response.raise_for_status()
                return response.content, "comfyui_url"
            except Exception:
                return None, f"comfyui_url_unreachable:{url}"
    return None, "no_image_available"


def evaluate_image_job(job: dict, *, requested_ratio: str | None = None) -> ImageQualityReport:
    """Skeleton evaluator. Fills only dependency-light fields.

    Heavier checks (OCR-based watermark detection, Canny IoU vs reference) are
    left as None so the worker can backfill them later without changing the API.
    """

    job_id = job.get("job_id") or ""
    report = ImageQualityReport(job_id=job_id, status="evaluated")
    report.aspect_ratio_requested = requested_ratio or job.get("aspect_ratio") or None

    data, source = _fetch_first_image_bytes(job)
    report.notes.append(f"source={source}")
    if not data:
        report.status = "no_image"
        return report

    report.bytes = len(data)
    dims = _image_dimensions_from_bytes(data)
    if dims:
        report.width, report.height = dims
        report.aspect_ratio_actual = _ratio_label(*dims)
        if report.aspect_ratio_requested:
            report.aspect_ratio_match = report.aspect_ratio_actual == report.aspect_ratio_requested
    else:
        report.notes.append("unknown_format_or_corrupt_header")

    # Placeholders for downstream workers.
    report.has_watermark = None
    report.ocr_text_excerpt = ""
    report.canny_edge_iou_vs_reference = None
    return report


def evaluate_and_store(job: dict, *, requested_ratio: str | None = None) -> dict:
    report = evaluate_image_job(job, requested_ratio=requested_ratio)
    return IMAGE_QUALITY_STORE.save(report)


def quality_report_for(job_id: str) -> dict | None:
    return IMAGE_QUALITY_STORE.get(job_id)


def quality_store_summary() -> dict:
    records = IMAGE_QUALITY_STORE.all()
    return {
        "store_path": str(IMAGE_QUALITY_STORE.path),
        "count": len(records),
        "evaluators": sorted({rec.get("evaluator", "unknown") for rec in records.values()}),
    }


def export_jsonl_summary() -> str:
    records = IMAGE_QUALITY_STORE.all()
    return "\n".join(json.dumps(record, ensure_ascii=False, default=str) for record in records.values())
