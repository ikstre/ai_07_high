"""이미지 job 목록/품질게이트 회귀 테스트.

B3: 목록 응답에 base64 이미지 바이트가 실리지 않는지(수십 MB 누출 방지).
B4: 요청 비율(aspect_ratio)이 job에 실려 quality_gate가 실제 비율을 검증하는지.
"""
import backend.main as main
from backend import quality_gate


def _fake_png(width: int, height: int) -> bytes:
    """_png_dimensions가 읽는 IHDR width/height만 채운 최소 PNG 바이트."""
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = b"\x00\x00\x00\rIHDR" + width.to_bytes(4, "big") + height.to_bytes(4, "big")
    return sig + ihdr + b"\x00" * 8


class _FakeStore:
    def __init__(self, jobs):
        self._jobs = jobs
        self.path = "/tmp/fake_jobs.json"

    def all(self):
        return self._jobs


def test_list_jobs_excludes_image_bytes(monkeypatch):
    heavy = "A" * 100_000
    jobs = {
        "j1": {
            "job_id": "j1",
            "created_at": 1,
            "status": "completed",
            "local_image_reference": {"has_image": True, "image_b64": heavy, "image_b64s": [heavy]},
        }
    }
    monkeypatch.setattr(main, "IMAGE_JOB_STORE", _FakeStore(jobs))

    result = main.list_image_generation_jobs(limit=20)

    blob = repr(result)
    assert heavy not in blob, "목록 응답에 base64 이미지 바이트가 실렸다"
    ref = result["jobs"][0]["local_image_reference"]
    assert "image_b64" not in ref and "image_b64s" not in ref
    assert ref["image_count"] == 1  # 메타(개수)는 보존


def test_quality_gate_reads_requested_ratio_from_backend_config():
    """요청 비율과 결과 해상도가 일치/불일치를 정확히 판정."""
    import base64

    job_45 = {
        "job_id": "ratio-ok",
        "backend_config": {"aspect_ratio": "4:5"},
        "local_image_reference": {"image_b64": base64.b64encode(_fake_png(1024, 1280)).decode()},
    }
    requested = (job_45.get("backend_config") or {}).get("aspect_ratio")
    report = quality_gate.evaluate_image_job(job_45, requested_ratio=requested)
    assert report.aspect_ratio_requested == "4:5"
    assert report.aspect_ratio_actual == "4:5"
    assert report.aspect_ratio_match is True

    job_mismatch = {
        "job_id": "ratio-bad",
        "backend_config": {"aspect_ratio": "1:1"},
        "local_image_reference": {"image_b64": base64.b64encode(_fake_png(1024, 1280)).decode()},
    }
    requested = (job_mismatch.get("backend_config") or {}).get("aspect_ratio")
    report = quality_gate.evaluate_image_job(job_mismatch, requested_ratio=requested)
    assert report.aspect_ratio_requested == "1:1"
    assert report.aspect_ratio_match is False
