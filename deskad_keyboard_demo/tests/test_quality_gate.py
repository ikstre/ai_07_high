from dataclasses import asdict

from backend import quality_gate


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
