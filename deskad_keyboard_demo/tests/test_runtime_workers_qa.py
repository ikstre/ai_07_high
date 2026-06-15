from __future__ import annotations

from backend import ai, result_cache, runtime_workers


def test_track_warm_plan_maps_user_tracks():
    assert runtime_workers.track_warm_plan("openai") == []
    assert runtime_workers.track_warm_plan("hyperclova") == ["hyperclova_image"]
    assert runtime_workers.track_warm_plan("LOCAL") == ["image"]
    assert runtime_workers.track_warm_plan("auto") is None
    assert runtime_workers.track_warm_plan("unknown") is None


def test_hyperclova_image_busy_ignores_stale_and_terminal_jobs(monkeypatch):
    class Store:
        def __init__(self, jobs):
            self._jobs = jobs

        def all(self):
            return self._jobs

    monkeypatch.setattr(runtime_workers.time, "time", lambda: 1000)
    monkeypatch.setattr(
        ai,
        "IMAGE_JOB_STORE",
        Store(
            {
                "old": {
                    "provider": "hyperclova_image",
                    "status": "running",
                    "created_at": 50,
                },
                "done": {
                    "provider": "hyperclova_image",
                    "status": "completed",
                    "created_at": 999,
                },
                "comfy": {
                    "provider": "comfyui",
                    "status": "running",
                    "created_at": 999,
                },
            }
        ),
    )

    assert runtime_workers._hyperclova_image_busy() is False

    monkeypatch.setattr(
        ai,
        "IMAGE_JOB_STORE",
        Store(
            {
                "active": {
                    "provider": "hyperclova_image",
                    "status": "running",
                    "created_at": 999,
                }
            }
        ),
    )

    assert runtime_workers._hyperclova_image_busy() is True


def test_activate_track_always_on_does_not_schedule(monkeypatch):
    monkeypatch.setattr(runtime_workers, "gpu_worker_mode", lambda: "always_on")

    def fail_thread(*args, **kwargs):
        raise AssertionError("activate_track should not create a warmup thread in always_on mode")

    monkeypatch.setattr(runtime_workers.threading, "Thread", fail_thread)

    result = runtime_workers.activate_track("hyperclova")

    assert result == {
        "track": "hyperclova",
        "mode": "always_on",
        "scheduled": False,
        "message": "GPU_WORKER_MODE=always_on — workers are managed externally",
    }


def test_generate_ad_copy_starts_loopback_hyperclova_vision_worker(monkeypatch):
    calls: list[tuple[str, bool | None]] = []

    class Adapter:
        name = "hyperclova_x_vision"
        base_url = "http://127.0.0.1:11601/v1"
        model = "track_b_model"
        default_model = "HCX-005"
        available = True

    monkeypatch.setattr(ai, "_provider_order", lambda provider: ["hyperclova"])
    monkeypatch.setattr(ai, "_copy_adapter", lambda provider, payload: Adapter())
    monkeypatch.setattr(ai, "_chat_copy", lambda payload, adapter: ai._fallback_copy(payload, provider=adapter.name))
    monkeypatch.setattr(
        runtime_workers,
        "ensure_text_worker",
        lambda start_managed_worker=True: calls.append(("text", start_managed_worker)) or True,
    )
    monkeypatch.setattr(
        runtime_workers,
        "ensure_hyperclova_vision_worker",
        lambda: calls.append(("vision", None)) or True,
    )
    monkeypatch.setattr(runtime_workers, "schedule_idle_reap", lambda: None)
    monkeypatch.setattr(result_cache, "make_text_cache_key", lambda *args, **kwargs: "copy-key")
    monkeypatch.setattr(result_cache, "put_text_cache", lambda *args, **kwargs: None)

    result = ai.generate_ad_copy(
        {"product_name": "테스트 키보드", "reference_image_b64": "QUJD"},
        provider_override="hyperclova",
        force_regen=True,
    )

    assert result["provider"] == "hyperclova_x_vision"
    assert calls == [("text", False), ("vision", None)]


def test_create_image_job_returns_running_for_hyperclova_thread(monkeypatch):
    saved: dict[str, dict] = {}
    started: list[dict] = []

    class Store:
        def get(self, job_id):
            record = saved.get(job_id)
            return dict(record) if record else None

        def save(self, job):
            saved[job["job_id"]] = dict(job)
            return dict(job)

        def all(self):
            return dict(saved)

    class Thread:
        def __init__(self, *, target, args, name, daemon):
            self.target = target
            self.args = args
            self.name = name
            self.daemon = daemon

        def start(self):
            started.append(
                {
                    "target": self.target,
                    "args": self.args,
                    "name": self.name,
                    "daemon": self.daemon,
                }
            )

    monkeypatch.setattr(ai, "IMAGE_JOB_STORE", Store())
    monkeypatch.setattr(ai, "_select_workflow_path", lambda payload: None)
    monkeypatch.setattr(ai, "_image_backend_config", lambda: {})
    monkeypatch.setattr(ai, "_hyperclova_image_not_configured_reason", lambda: None)
    monkeypatch.setattr(ai.threading, "Thread", Thread)
    monkeypatch.setattr(runtime_workers, "schedule_idle_reap", lambda: None)

    result = ai.create_image_job(
        {"engine": "hyperclova", "image_ratio": "1:1"},
        "draw a keyboard",
        force_regen=True,
    )

    assert result["provider"] == "hyperclova_image"
    assert result["status"] == "running"
    assert saved[result["job_id"]]["status"] == "running"
    assert started == [
        {
            "target": ai._run_hyperclova_image_job,
            "args": (result["job_id"], {"engine": "hyperclova", "image_ratio": "1:1"}, "draw a keyboard"),
            "name": f"hyperclova-image-{result['job_id'][:8]}",
            "daemon": True,
        }
    ]


def test_create_image_job_exposes_native_omni_prompt_for_guard(monkeypatch):
    # 응답의 image_prompt는 ComfyUI 브래킷 프롬프트라 그라운딩(_LAYOUT_ROW_SPEC_EN 등)이 안 보인다.
    # job에 실제 전송되는 native 프롬프트를 노출해야 재생성 가드가 폴링 전에 그라운딩 적재를
    # 검증할 수 있다(2026-06-15 라이브 검증: 서버가 구코드면 가드가 ~1초에 차단해야 함).
    saved: dict[str, dict] = {}

    class Store:
        def get(self, job_id):
            record = saved.get(job_id)
            return dict(record) if record else None

        def save(self, job):
            saved[job["job_id"]] = dict(job)
            return dict(job)

        def all(self):
            return dict(saved)

    class Thread:
        def __init__(self, *, target, args, name, daemon):
            pass

        def start(self):
            pass

    monkeypatch.setattr(ai, "IMAGE_JOB_STORE", Store())
    monkeypatch.setattr(ai, "_select_workflow_path", lambda payload: None)
    monkeypatch.setattr(ai, "_image_backend_config", lambda: {})
    monkeypatch.setattr(ai, "_hyperclova_image_not_configured_reason", lambda: None)
    monkeypatch.setattr(ai.threading, "Thread", Thread)
    monkeypatch.setattr(runtime_workers, "schedule_idle_reap", lambda: None)

    result = ai.create_image_job(
        {"engine": "hyperclova", "image_ratio": "1:1", "layout": "65", "keycap_profile": "cherry"},
        "bracketed comfyui prompt without grounding",
        force_regen=True,
    )

    native = result.get("native_image_prompt", "")
    # 가드가 확인할 그라운딩 마커가 노출된 native 프롬프트에 실제로 들어 있어야 한다.
    assert "Build the exact board" in native
    assert "ANSI-staggered rows" in native and "right-side arrow cluster" in native
    assert "sculpted" in native  # Cherry 키캡 높이 그라운딩
    # 응답에 함께 실린 ComfyUI image_prompt와는 다른(=실제 전송) 프롬프트여야 한다.
    assert native != "bracketed comfyui prompt without grounding"


def test_worker_log_path_lives_under_runtime_dir():
    path = runtime_workers._worker_log_path(runtime_workers.HYPERCLOVA_IMAGE_WORKER)
    assert path.name == "hyperclova_image_worker.log"
    assert path.parent == runtime_workers._BACKEND_BASE_DIR / "data" / "runtime"


def test_poll_marks_stale_running_hyperclova_job_failed(monkeypatch):
    saved: dict[str, dict] = {
        "stale": {
            "job_id": "stale",
            "provider": "hyperclova_image",
            "status": "running",
            "created_at": 0,
        },
        "fresh": {
            "job_id": "fresh",
            "provider": "hyperclova_image",
            "status": "running",
            "created_at": 990,
        },
    }

    class Store:
        def get(self, job_id):
            record = saved.get(job_id)
            return dict(record) if record else None

        def save(self, job):
            saved[job["job_id"]] = dict(job)
            return dict(job)

    monkeypatch.setattr(ai, "IMAGE_JOB_STORE", Store())
    monkeypatch.setattr(ai.time, "time", lambda: 1000)
    monkeypatch.setattr(ai, "_hyperclova_image_timeout_seconds", lambda: 420)

    stale = ai.poll_image_job("stale")
    assert stale["status"] == "failed"
    assert "stale" in stale["error"]
    assert saved["stale"]["status"] == "failed"

    fresh = ai.poll_image_job("fresh")
    assert fresh["status"] == "running"
    assert saved["fresh"]["status"] == "running"
