import base64
import io
from dataclasses import asdict

import pytest

from backend import quality_gate


def _synthetic_pngs() -> tuple[bytes, bytes]:
    """(frame-filling 텍스처, 정면입면/희박) 합성 PNG — docs 아티팩트 비의존, 결정적(seed 고정)."""
    np = pytest.importorskip("numpy")
    pil_image = pytest.importorskip("PIL.Image")
    rng = np.random.default_rng(0)
    full = rng.integers(0, 256, size=(256, 256), dtype=np.uint8)  # 프레임 전체 텍스처
    sparse = np.full((256, 256), 180, dtype=np.uint8)  # 균일 배경
    sparse[224:248, 40:216] = rng.integers(0, 256, size=(24, 176), dtype=np.uint8)  # 하단 얇은 밴드만

    def to_png(arr) -> bytes:
        buf = io.BytesIO()
        pil_image.fromarray(arr, mode="L").save(buf, format="PNG")
        return buf.getvalue()

    return to_png(full), to_png(sparse)


def _job(job_id: str, png: bytes) -> dict:
    return {"job_id": job_id, "local_image_reference": {"image_b64": base64.b64encode(png).decode()}}


def test_image_quality_report_serializes_heavy_metric_fields():
    report = quality_gate.ImageQualityReport(
        job_id="job-1",
        clip_score=0.82,
        fid_score=12.5,
        lpips_score=0.21,
        mos_score=4.2,
        accepted=True,
    )
    data = asdict(report)

    assert data["clip_score"] == 0.82
    assert data["fid_score"] == 12.5
    assert data["lpips_score"] == 0.21
    assert data["mos_score"] == 4.2
    assert data["accepted"] is True


def test_quality_store_summary_counts_and_averages(tmp_path, monkeypatch):
    store = quality_gate.ImageQualityStore(tmp_path / "quality.jsonl")
    monkeypatch.setattr(quality_gate, "IMAGE_QUALITY_STORE", store)

    store.save(quality_gate.ImageQualityReport(job_id="accepted", clip_score=0.8, mos_score=4.0, accepted=True))
    store.save(quality_gate.ImageQualityReport(job_id="rejected", clip_score=0.4, mos_score=2.0, accepted=False))
    store.save(quality_gate.ImageQualityReport(job_id="unscored"))

    summary = quality_gate.quality_store_summary()

    assert summary["count"] == 3
    assert summary["accepted"] == 1
    assert summary["rejected"] == 1
    assert summary["unscored"] == 1
    assert summary["mean_clip_score"] == 0.6
    assert summary["mean_mos_score"] == 3.0


# ── best-of-N 구도 선별(2026-06-15): 정면입면/희박 컷 강등, 프레임 채운 컷 선택 ──
def test_analyze_composition_separates_frame_filling_from_sparse():
    full_png, sparse_png = _synthetic_pngs()
    full = quality_gate.analyze_composition(full_png)
    sparse = quality_gate.analyze_composition(sparse_png)
    assert full is not None and sparse is not None
    assert full["composition_score"] > sparse["composition_score"]
    assert sparse["sparse"] is True and full["sparse"] is False
    # 하단 밴드 + 상단 텅 빔 → 정면입면/줌아웃 플래그
    assert sparse["front_elevation"] is True


def test_select_best_of_n_picks_frame_filling_over_sparse():
    full_png, sparse_png = _synthetic_pngs()
    result = quality_gate.select_best_of_n([_job("sparse", sparse_png), _job("full", full_png)])
    assert result["best_job_id"] == "full"
    assert result["scored"] == 2
    assert result["ranking"][0]["job_id"] == "full"
    assert "sparse" in result["ranking"][-1]["flags"]


def test_select_best_of_n_handles_jobs_without_images():
    result = quality_gate.select_best_of_n([{"job_id": "a"}, {"job_id": "b"}])
    assert result["best_job_id"] is None
    assert result["evaluated"] == 2 and result["scored"] == 0


def test_evaluate_image_job_rejects_sparse_via_composition():
    _, sparse_png = _synthetic_pngs()
    report = quality_gate.evaluate_image_job(_job("sparse", sparse_png), requested_ratio="1:1")
    assert report.composition_score is not None
    assert report.accepted is False
    assert any("sparse" in note for note in report.notes)
