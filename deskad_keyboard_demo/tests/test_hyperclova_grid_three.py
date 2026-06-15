"""grid_three × hyperclova 분할 생성/타임아웃 예산 (next_work 2026-06-12 0순위).

Omni 네이티브 생성은 장당 ~280s라 n=3 단일 요청은 클라이언트 타임아웃(420s)을
구조적으로 초과했다. 컷별 n=1 분할 요청 + 장수 기반 stale/busy 예산을 검증한다.
"""
from __future__ import annotations

import pytest

from backend import ai, runtime_workers


def _grid_payload() -> dict:
    return {
        "product_name": "QK65 custom keyboard",
        "poster_template": "grid_three",
        "image_ratio": "1:1",
        "engine": "hyperclova",
    }


@pytest.fixture()
def fixed_model(monkeypatch):
    monkeypatch.setattr(ai, "_hyperclova_image_model", lambda: "omni-test")


def test_grid_three_splits_into_three_single_image_requests(monkeypatch, fixed_model):
    captured: list[dict] = []

    def fake_call(request_payload):
        captured.append(dict(request_payload))
        return {"data": [{"b64_json": f"img{len(captured)}"}]}

    monkeypatch.setattr(ai, "_hyperclova_openai_images_call", fake_call)
    progress: list[tuple[int, int, int]] = []

    summary = ai._hyperclova_openai_images_reference(
        _grid_payload(), "base prompt", on_progress=lambda d, t, ok: progress.append((d, t, ok))
    )

    assert len(captured) == 3
    assert all(req["n"] == 1 for req in captured)
    # 컷별 shot_plan 구도가 프롬프트에 반영되어 서로 달라야 한다.
    prompts = [req["prompt"] for req in captured]
    assert len(set(prompts)) == 3
    assert all("Panel focus:" in prompt for prompt in prompts)

    assert summary["has_image"] is True
    assert summary["requested_image_count"] == 3
    assert summary["image_count"] == 3
    assert summary["image_b64s"] == ["img1", "img2", "img3"]
    assert summary["image_b64"] == "img1"
    assert [shot["ok"] for shot in summary["shot_results"]] == [True, True, True]
    assert progress == [(1, 3, 1), (2, 3, 2), (3, 3, 3)]


def test_grid_three_tolerates_partial_shot_failure(monkeypatch, fixed_model):
    calls = {"count": 0}

    def fake_call(request_payload):
        calls["count"] += 1
        if calls["count"] == 2:
            raise RuntimeError("Read timed out. (read timeout=420)")
        return {"data": [{"b64_json": f"img{calls['count']}"}]}

    monkeypatch.setattr(ai, "_hyperclova_openai_images_call", fake_call)

    summary = ai._hyperclova_openai_images_reference(_grid_payload(), "base prompt")

    assert calls["count"] == 3  # 실패한 컷 이후에도 계속 진행
    assert summary["has_image"] is True
    assert summary["image_count"] == 2
    assert [shot["ok"] for shot in summary["shot_results"]] == [True, False, True]
    assert "error" not in summary  # 일부 성공이면 job은 completed로 가야 한다
    assert len(summary["shot_errors"]) == 1


def test_grid_three_all_shots_failed_surfaces_error(monkeypatch, fixed_model):
    def fake_call(request_payload):
        raise RuntimeError("Read timed out. (read timeout=420)")

    monkeypatch.setattr(ai, "_hyperclova_openai_images_call", fake_call)

    summary = ai._hyperclova_openai_images_reference(_grid_payload(), "base prompt")

    assert summary["has_image"] is False
    assert summary["image_count"] == 0
    assert "Read timed out" in summary["error"]
    assert len(summary["shot_errors"]) == 3


def test_single_image_templates_keep_single_request(monkeypatch, fixed_model):
    captured: list[dict] = []

    def fake_call(request_payload):
        captured.append(dict(request_payload))
        return {"data": [{"b64_json": "img1"}]}

    monkeypatch.setattr(ai, "_hyperclova_openai_images_call", fake_call)

    payload = {**_grid_payload(), "poster_template": "minimal_card"}
    summary = ai._hyperclova_openai_images_reference(payload, "base prompt")

    assert len(captured) == 1
    assert summary["has_image"] is True
    assert summary["requested_image_count"] == 1


class _Store:
    def __init__(self, records: dict[str, dict]):
        self.records = records

    def get(self, job_id):
        record = self.records.get(job_id)
        return dict(record) if record else None

    def save(self, job):
        self.records[job["job_id"]] = dict(job)
        return dict(job)

    def all(self):
        return {key: dict(value) for key, value in self.records.items()}


def test_stale_budget_scales_with_requested_image_count(monkeypatch):
    records = {
        "grid_running": {
            "job_id": "grid_running",
            "provider": "hyperclova_image",
            "status": "running",
            "created_at": 0,
            "requested_image_count": 3,
        },
        "grid_stale": {
            "job_id": "grid_stale",
            "provider": "hyperclova_image",
            "status": "running",
            "created_at": 0,
            "requested_image_count": 1,
        },
    }
    monkeypatch.setattr(ai, "IMAGE_JOB_STORE", _Store(records))
    monkeypatch.setattr(ai.time, "time", lambda: 1000)
    monkeypatch.setattr(ai, "_hyperclova_image_timeout_seconds", lambda: 420)

    # 3컷 예산은 3×420+120=1380s — 1000s 경과는 아직 정상 작업.
    grid = ai.poll_image_job("grid_running")
    assert grid["status"] == "running"

    # 1장 예산(420+120=540s)을 넘긴 job은 기존대로 failed.
    stale = ai.poll_image_job("grid_stale")
    assert stale["status"] == "failed"


def test_worker_busy_guard_scales_with_requested_image_count(monkeypatch):
    records = {
        "grid": {
            "job_id": "grid",
            "provider": "hyperclova_image",
            "status": "running",
            "created_at": 0,
            "requested_image_count": 3,
        },
    }

    import backend.ai as ai_module

    monkeypatch.setattr(ai_module, "IMAGE_JOB_STORE", _Store(records))

    # 1000s 경과: 단장 기준(900s)으로는 좀비지만 3컷 예산(2700s) 안 → busy 유지.
    monkeypatch.setattr(runtime_workers.time, "time", lambda: 1000)
    assert runtime_workers._hyperclova_image_busy() is True

    # 3컷 예산도 넘긴 좀비는 busy 해제.
    monkeypatch.setattr(runtime_workers.time, "time", lambda: 3000)
    assert runtime_workers._hyperclova_image_busy() is False
