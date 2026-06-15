"""hyperclova 이미지 job 직렬화 (구도 변경 후 재생성 실패, 2026-06-12 QA).

이미지 서버(:11602)는 요청을 내부 lock으로 직렬 처리하므로, 앞 job이 생성 중일 때
새 job이 바로 HTTP를 보내면 큐 대기 시간이 클라이언트 타임아웃(420s×n)을 잠식해
두 번째 job이 구조적으로 실패했다. 백엔드에서 job을 queued로 줄 세우고, 차례가
오면 created_at을 리셋해 stale 예산이 실제 생성 시간만 재는지 검증한다.
"""
from __future__ import annotations

import threading
import time

from backend import ai


class _Store:
    def __init__(self, records: dict[str, dict]):
        self.records = records
        self._lock = threading.Lock()

    def get(self, job_id):
        with self._lock:
            record = self.records.get(job_id)
            return dict(record) if record else None

    def save(self, job):
        with self._lock:
            self.records[job["job_id"]] = dict(job)
            return dict(job)

    def all(self):
        with self._lock:
            return {key: dict(value) for key, value in self.records.items()}


def _running_job(job_id: str) -> dict:
    return {
        "job_id": job_id,
        "provider": "hyperclova_image",
        "status": "running",
        "created_at": int(time.time()),
        "requested_image_count": 1,
    }


def test_second_job_queues_until_first_finishes(monkeypatch):
    import backend.runtime_workers as runtime_workers

    store = _Store({"jobA": _running_job("jobA"), "jobB": _running_job("jobB")})
    monkeypatch.setattr(ai, "IMAGE_JOB_STORE", store)
    monkeypatch.setattr(runtime_workers, "ensure_hyperclova_image_worker", lambda: None)

    first_started = threading.Event()
    release_first = threading.Event()

    def fake_reference(payload, image_prompt, *, on_progress=None):
        if payload["tag"] == "A":
            first_started.set()
            assert release_first.wait(timeout=10)
        return {"has_image": True, "image_b64": payload["tag"]}

    monkeypatch.setattr(ai, "generate_hyperclova_image_reference", fake_reference)

    thread_a = threading.Thread(target=ai._run_hyperclova_image_job, args=("jobA", {"tag": "A"}, "p"))
    thread_a.start()
    assert first_started.wait(timeout=5)

    thread_b = threading.Thread(target=ai._run_hyperclova_image_job, args=("jobB", {"tag": "B"}, "p"))
    thread_b.start()

    # B는 서버로 요청을 보내지 않고 백엔드에서 queued로 대기해야 한다.
    deadline = time.time() + 5
    while time.time() < deadline and (store.get("jobB") or {}).get("status") != "queued":
        time.sleep(0.05)
    job_b = store.get("jobB")
    assert job_b["status"] == "queued"
    assert job_b.get("queued_heartbeat")
    assert (store.get("jobA") or {})["status"] == "running"

    release_first.set()
    thread_a.join(timeout=10)
    thread_b.join(timeout=20)
    assert not thread_a.is_alive() and not thread_b.is_alive()

    job_a = store.get("jobA")
    job_b = store.get("jobB")
    assert job_a["status"] == "completed"
    assert job_b["status"] == "completed"
    # 큐 대기 흔적은 종결 시 정리된다.
    assert "queued_heartbeat" not in job_b
    assert "message" not in job_b


def test_stale_queued_job_fails_when_heartbeat_lost(monkeypatch):
    records = {
        "lost": {
            "job_id": "lost",
            "provider": "hyperclova_image",
            "status": "queued",
            "created_at": 0,
            "queued_heartbeat": 0,
        },
        "waiting": {
            "job_id": "waiting",
            "provider": "hyperclova_image",
            "status": "queued",
            "created_at": 0,
            "queued_heartbeat": 950,
        },
    }
    monkeypatch.setattr(ai, "IMAGE_JOB_STORE", _Store(records))
    monkeypatch.setattr(ai.time, "time", lambda: 1000)

    # heartbeat가 끊긴 queued job(백엔드 재시작 등)은 poll 시점에 failed로 종결.
    lost = ai.poll_image_job("lost")
    assert lost["status"] == "failed"
    assert "queued" in lost["error"]

    # heartbeat가 살아 있는 queued job은 그대로 대기.
    waiting = ai.poll_image_job("waiting")
    assert waiting["status"] == "queued"
