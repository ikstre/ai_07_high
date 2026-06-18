from __future__ import annotations

import base64
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
    # Dependency-light composition signal for best-of-N selection (PIL+numpy, no GPU/ML).
    # Higher = subject fills frame with detail; low/None = sparse or front-elevation/empty-zoom.
    composition_score: float | None = None
    # Heavy metrics — populated by the separate GPU quality worker
    # (workers/quality_evaluator.py). None until that worker backfills them.
    clip_score: float | None = None  # CLIP-I / CLIPScore vs image_prompt
    fid_score: float | None = None
    lpips_score: float | None = None
    mos_score: float | None = None  # 점주 패널 5점 평균 (수기/외부 입력)
    accepted: bool | None = None  # 교체 트리거 게이트 통과 여부
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


# PIL+numpy는 GPU/ML 스택이 아니라 가벼운 의존이지만(이미 렌더러 등에서 사용), 없는 환경에서도
# 게이트 API가 죽지 않게 가드한다(스켈레톤 설계 철학 유지). 없으면 구도 분석만 None으로 스킵.
try:  # pragma: no cover - 환경별 가용성
    import io as _io

    import numpy as _np
    from PIL import Image as _PILImage

    _HAS_COMPOSITION_DEPS = True
except Exception:  # pragma: no cover
    _HAS_COMPOSITION_DEPS = False


def analyze_composition(data: bytes, *, _im=None) -> dict | None:
    """best-of-N용 의존성-가벼운 구도 신호(엣지 맵 기반, GPU/ML 불필요).

    Omni의 지배적 실패인 '정면입면/빈공간/줌아웃'(보드가 하단 얇은 밴드 + 상단 텅 빔)을 잡는다.
    **레이아웃 정확도(넘패드 오검출)나 왜곡/melt는 판정하지 못한다** — 그건 CLIP/VLM 의미 점수의 몫.
    PIL/numpy가 없거나 디코드 실패면 None.

    반환: subject_fill(엣지 밀도), frame_fill(피사체 bbox 면적비), vertical_center,
    bands(상/중/하 엣지 비중), composition_score(클수록 프레임 채움+디테일), sparse/front_elevation 플래그.
    """
    if not _HAS_COMPOSITION_DEPS or not data:
        return None
    try:
        im = (_im if _im is not None else _PILImage.open(_io.BytesIO(data))).convert("L")
        height = 200
        width = max(1, round(im.width * height / im.height))
        arr = _np.asarray(im.resize((width, height)), dtype=_np.float32) / 255.0
        gy, gx = _np.gradient(arr)
        grad = _np.hypot(gx, gy)
        # 적응형 임계(평균+0.8σ) — 스튜디오/데스크 등 배경 톤 차이에 강건.
        edge = grad > float(grad.mean() + 0.8 * grad.std())
        subject_fill = float(edge.mean())
        third = height // 3
        bands = (
            float(edge[:third].mean()),
            float(edge[third : 2 * third].mean()),
            float(edge[2 * third :].mean()),
        )
        ys = _np.nonzero(edge)[0]
        vertical_center = float(ys.mean() / height) if ys.size else 0.0
        cols = _np.nonzero(edge.any(axis=0))[0]
        rows = _np.nonzero(edge.any(axis=1))[0]
        frame_w = float((cols[-1] - cols[0] + 1) / width) if cols.size else 0.0
        frame_h = float((rows[-1] - rows[0] + 1) / height) if rows.size else 0.0
        frame_fill = frame_w * frame_h
        composition_score = round(frame_fill + subject_fill, 4)
        sparse = subject_fill < 0.07  # 피사체 디테일이 거의 없음(텅 빈/희박 프레임)
        # 정면입면/줌아웃: 상단 비고 + 피사체가 하단으로 쏠리고 + 세로로 얇게 깔림.
        front_elevation = bands[0] < 0.02 and vertical_center > 0.70 and frame_h < 0.30
        return {
            "subject_fill": round(subject_fill, 4),
            "frame_fill": round(frame_fill, 4),
            "frame_w": round(frame_w, 3),
            "frame_h": round(frame_h, 3),
            "vertical_center": round(vertical_center, 3),
            "bands": [round(b, 4) for b in bands],
            "composition_score": composition_score,
            "sparse": sparse,
            "front_elevation": front_elevation,
        }
    except Exception:
        return None


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

    # 구도 신호(best-of-N): 정면입면/희박 컷을 가려낸다. layout/왜곡은 CLIP/VLM 몫(아래 note).
    composition = analyze_composition(data)
    if composition is not None:
        report.composition_score = composition["composition_score"]
        report.raw["composition"] = composition
        if composition["sparse"]:
            report.accepted = False
            report.notes.append("rejected: sparse/empty frame (subject_fill<0.07)")
        elif composition["front_elevation"]:
            report.notes.append("flag: front-elevation/empty-zoom composition")

    # Placeholders for downstream workers.
    report.has_watermark = None
    report.ocr_text_excerpt = ""
    report.canny_edge_iou_vs_reference = None
    return report


def select_best_of_n(jobs: list[dict], *, requested_ratio: str | None = None) -> dict:
    """여러 이미지 job 중 구도 점수가 가장 좋은 1장을 고른다(Omni 출력 분산 대응 best-of-N).

    프레임을 채우고 균형 잡힌 컷을 선호하고, 정면입면/희박/줌아웃(Omni 지배적 실패)을 강등한다.
    **레이아웃 정확도(넘패드)·왜곡/melt는 판정하지 못한다** — 그 의미적 실패는 CLIP/VLM 점수가 필요
    (`note` 참고). 구도 의존(PIL/numpy)이 없으면 점수가 None이라 입력 순서가 유지된다(원형 폴백).
    """
    scored: list[dict] = []
    for job in jobs:
        data, source = _fetch_first_image_bytes(job)
        composition = analyze_composition(data) if data else None
        scored.append(
            {
                "job_id": job.get("job_id"),
                "score": composition["composition_score"] if composition else None,
                "flags": [k for k in ("sparse", "front_elevation") if composition and composition.get(k)],
                "source": source,
                "composition": composition,
            }
        )
    # 점수 없는 항목(구도 분석 불가)은 맨 뒤로. 동점/전무면 입력 순서 보존.
    ranking = sorted(
        scored,
        key=lambda item: (item["score"] is not None, item["score"] if item["score"] is not None else 0.0),
        reverse=True,
    )
    best = ranking[0] if ranking and ranking[0]["score"] is not None else None
    return {
        "best_job_id": best["job_id"] if best else None,
        "best_score": best["score"] if best else None,
        "ranking": ranking,
        "evaluated": len(scored),
        "scored": sum(1 for item in scored if item["score"] is not None),
        "note": "composition-only (frame-fill/sparse/front-elevation); layout & distortion need CLIP/VLM",
    }


def _hex_to_rgb(value: object) -> tuple[int, int, int] | None:
    """'#rgb' / '#rrggbb' / '#rrggbbaa'(알파 무시) → (r,g,b). 실패하면 None.

    color picker는 보통 #rrggbb지만, 단축형(#abc)·알파 포함(#rrggbbaa)도 받아 두지 않으면
    유효한 색인데도 best-of-N이 조용히 꺼진다(None → 호출부 no-op).
    """
    if not isinstance(value, str):
        return None
    s = value.strip().lstrip("#")
    if len(s) == 3:            # 단축형 #abc → #aabbcc
        s = "".join(ch * 2 for ch in s)
    elif len(s) == 8:          # #rrggbbaa → 알파 채널 무시
        s = s[:6]
    if len(s) != 6:
        return None
    try:
        return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))
    except ValueError:
        return None


def accent_fidelity_score(
    data: bytes,
    accent_rgb: tuple[int, int, int],
    *,
    threshold: float = 64.0,
    region: tuple[float, float, float, float] = (0.34, 0.82, 0.14, 0.86),
    _im=None,
) -> float | None:
    """이미지 중앙(키보드) 밴드에서 스펙 액센트 색에 가까운 픽셀 비중(0~1).

    depth-ControlNet은 grayscale라 색을 못 잠근다 → best-of-N으로 액센트 색이 가장 충실한
    컷을 고를 때 쓰는 의존-가벼운 색 신호(PIL+numpy, GPU/ML 불필요). ``region``은
    (top,bottom,left,right) 비율로 키보드가 놓이는 중앙 밴드만 본다(데스크/배경 간섭 축소).
    액센트 키는 소수라 값 자체는 작지만 후보 간 *상대* 비교로 충실한 컷을 가린다.
    의존성/디코드 실패면 None.
    """
    if not _HAS_COMPOSITION_DEPS or not data:
        return None
    try:
        im = (_im if _im is not None else _PILImage.open(_io.BytesIO(data))).convert("RGB")
        h = 220
        w = max(1, round(im.width * h / im.height))
        arr = _np.asarray(im.resize((w, h)), dtype=_np.float32)
        t, b, left, r = region
        sub = arr[int(t * h) : int(b * h), int(left * w) : int(r * w)]
        if sub.size == 0:
            return None
        target = _np.array(accent_rgb, dtype=_np.float32)
        dist = _np.sqrt(((sub - target) ** 2).sum(axis=2))
        return float((dist < threshold).mean())
    except Exception:
        return None


def select_best_accent_image(image_b64s: list[str], accent_color: object) -> dict | None:
    """N개 후보 b64 중 액센트 색이 가장 충실한 1장을 고른다(빈 프레임은 강등).

    accent_color는 '#rrggbb' 스펙 색. 반환:
    {"best_index", "best_accent", "scores":[{index,accent,composition,sparse}], "note"}.
    accent 미설정/의존성 없음/유효 후보 없음이면 None(호출부가 기존 첫 컷 유지).
    """
    accent_rgb = _hex_to_rgb(accent_color)
    if accent_rgb is None or not _HAS_COMPOSITION_DEPS or not image_b64s:
        return None
    scores: list[dict] = []
    for idx, b64 in enumerate(image_b64s):
        data = _decode_image_b64_to_bytes(b64)
        # 후보당 PIL open을 1회로 모아 구도·액센트 두 신호가 공유한다(이중 디코드 제거).
        # 여기까지 왔으면 _HAS_COMPOSITION_DEPS는 보장된다(함수 진입 가드).
        im = None
        if data:
            try:
                im = _PILImage.open(_io.BytesIO(data))
            except Exception:
                im = None
        comp = analyze_composition(data, _im=im) if im is not None else None
        accent = accent_fidelity_score(data, accent_rgb, _im=im) if im is not None else None
        scores.append(
            {
                "index": idx,
                "accent": round(accent, 5) if accent is not None else None,
                "composition": comp["composition_score"] if comp else None,
                "sparse": bool(comp and comp.get("sparse")),
            }
        )
    valid = [s for s in scores if s["accent"] is not None]
    if not valid:
        return None
    # sparse(빈/희박 프레임)는 뒤로 → 액센트 충실도 높은 순 → 동점이면 구도 점수.
    ranking = sorted(
        valid,
        key=lambda s: (not s["sparse"], s["accent"], s["composition"] or 0.0),
        reverse=True,
    )
    best = ranking[0]
    return {
        "best_index": best["index"],
        "best_accent": best["accent"],
        "scores": scores,
        "note": "accent-colour fidelity in central keyboard band; sparse demoted, ties by composition",
    }


def evaluate_and_store(job: dict, *, requested_ratio: str | None = None) -> dict:
    report = evaluate_image_job(job, requested_ratio=requested_ratio)
    return IMAGE_QUALITY_STORE.save(report)


def quality_report_for(job_id: str) -> dict | None:
    return IMAGE_QUALITY_STORE.get(job_id)


def quality_store_summary() -> dict:
    records = IMAGE_QUALITY_STORE.all()
    values = list(records.values())

    def _avg(key: str) -> float | None:
        nums = [rec[key] for rec in values if isinstance(rec.get(key), (int, float))]
        return round(sum(nums) / len(nums), 4) if nums else None

    accepted = [rec.get("accepted") for rec in values]
    return {
        "store_path": str(IMAGE_QUALITY_STORE.path),
        "count": len(values),
        "evaluators": sorted({rec.get("evaluator", "unknown") for rec in values}),
        "accepted": sum(1 for a in accepted if a is True),
        "rejected": sum(1 for a in accepted if a is False),
        "unscored": sum(1 for a in accepted if a is None),
        "mean_mos_score": _avg("mos_score"),
        "mean_clip_score": _avg("clip_score"),
    }


def export_jsonl_summary() -> str:
    records = IMAGE_QUALITY_STORE.all()
    return "\n".join(json.dumps(record, ensure_ascii=False, default=str) for record in records.values())
