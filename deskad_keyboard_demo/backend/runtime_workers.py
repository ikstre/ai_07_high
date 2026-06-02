"""GPU worker lifecycle management.

GPU_WORKER_MODE environment variable controls behavior:
  always_on   — assume workers are managed externally; never start/stop (default)
  on_demand   — start the needed worker on cache miss; stop it after idle timeout
  exclusive   — before starting one worker, stop the other to free VRAM

Worker types:
  text  — local OpenAI-compatible server (TEXT_WORKER_CMD / TEXT_WORKER_HEALTH_URL)
          default: conda run -n sprint_high python tools/hyperclova_seed_openai_server.py
  image — ComfyUI (IMAGE_WORKER_SERVICE / IMAGE_WORKER_HEALTH_URL)

Idle reaping runs lazily in a background daemon thread after each GPU request.
"""
from __future__ import annotations

import fcntl
import json
import logging
import os
import subprocess
import threading
import time
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

_BACKEND_BASE_DIR = Path(__file__).resolve().parent.parent


# ── env helpers ───────────────────────────────────────────────────────────────

def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def gpu_worker_mode() -> str:
    return _env("GPU_WORKER_MODE", "always_on").lower()


def idle_timeout_seconds() -> int:
    return _int_env("GPU_WORKER_IDLE_TIMEOUT_SECONDS", 600)


def _lock_path() -> Path:
    override = _env("GPU_WORKER_LOCK_PATH")
    if override:
        return Path(override).expanduser()
    return _BACKEND_BASE_DIR / "data" / "runtime" / "gpu_worker.lock"


def _state_path() -> Path:
    return _BACKEND_BASE_DIR / "data" / "runtime" / "worker_state.json"


def _text_worker_cmd() -> str:
    return _env("TEXT_WORKER_CMD", "")


def _text_health_url() -> str:
    return _env("TEXT_WORKER_HEALTH_URL", "http://127.0.0.1:11501/health")


def _image_service() -> str:
    return _env("IMAGE_WORKER_SERVICE", "comfyui")


def _image_health_url() -> str:
    return _env("IMAGE_WORKER_HEALTH_URL", "http://127.0.0.1:8188/system_stats")


def image_worker_stop_after_job() -> bool:
    return _bool_env("IMAGE_WORKER_STOP_AFTER_JOB", True)


# ── persistent state ──────────────────────────────────────────────────────────

def _load_state() -> dict:
    path = _state_path()
    if not path.exists():
        return {"text_last_used": 0, "image_last_used": 0, "text_pid": None, "image_pid": None}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {"text_last_used": 0, "image_last_used": 0, "text_pid": None, "image_pid": None}


def _save_state(state: dict) -> None:
    path = _state_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, indent=2), encoding="utf-8")
        path.chmod(0o600)
    except Exception:
        pass


def _touch_last_used(worker_type: str) -> None:
    state = _load_state()
    state[f"{worker_type}_last_used"] = int(time.time())
    _save_state(state)


# ── health checks ─────────────────────────────────────────────────────────────

def _is_healthy(url: str, timeout: int = 3) -> bool:
    try:
        r = requests.get(url, timeout=timeout)
        return r.status_code < 500
    except Exception:
        return False


def is_text_worker_up() -> bool:
    return _is_healthy(_text_health_url())


def is_image_worker_up() -> bool:
    return _is_healthy(_image_health_url())


# ── file lock ─────────────────────────────────────────────────────────────────

class _WorkerLock:
    """File-based exclusive lock for start/stop operations across processes."""

    def __init__(self) -> None:
        self._path = _lock_path()
        self._fd = None

    def __enter__(self) -> "_WorkerLock":
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._fd = open(self._path, "w")  # noqa: SIM115
        # Keep the lock file at 0600 like the other data/runtime state files
        # (worker_state.json, cache/*.json) so the runtime dir has no
        # group/other-readable outliers.
        try:
            os.fchmod(self._fd.fileno(), 0o600)
        except OSError:
            pass
        fcntl.flock(self._fd, fcntl.LOCK_EX)
        return self

    def __exit__(self, *args) -> None:
        if self._fd:
            fcntl.flock(self._fd, fcntl.LOCK_UN)
            self._fd.close()
            self._fd = None


# ── start / stop internals ────────────────────────────────────────────────────

def _start_text_worker_locked() -> bool:
    """Start the text worker process. Caller must hold _WorkerLock."""
    if is_text_worker_up():
        return True
    cmd = _text_worker_cmd()
    if not cmd:
        logger.warning("TEXT_WORKER_CMD not configured; cannot start text worker")
        return False
    logger.info("Starting text worker: %s", cmd)
    try:
        proc = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        state = _load_state()
        state["text_pid"] = proc.pid
        _save_state(state)
        for _ in range(20):
            time.sleep(3)
            if is_text_worker_up():
                logger.info("Text worker ready")
                return True
        logger.warning("Text worker did not become healthy within 60 s")
        return False
    except Exception as exc:
        logger.error("Failed to start text worker: %s", exc)
        return False


def _stop_text_worker_locked() -> None:
    """Stop the text worker process. Caller must hold _WorkerLock."""
    state = _load_state()
    pid = state.get("text_pid")
    if pid:
        try:
            os.killpg(os.getpgid(int(pid)), 15)
            logger.info("SIGTERM → text worker process group (pid=%s)", pid)
        except (ProcessLookupError, OSError):
            pass
        except Exception as exc:
            logger.warning("Could not SIGTERM text worker pid=%s: %s", pid, exc)
        state["text_pid"] = None
        _save_state(state)
    # belt-and-suspenders: fuser-kill the health port
    try:
        from urllib.parse import urlparse
        port = urlparse(_text_health_url()).port
        if port:
            subprocess.run(
                ["fuser", "-k", f"{port}/tcp"],
                capture_output=True,
                timeout=5,
            )
    except Exception:
        pass


def _start_image_worker_locked() -> bool:
    """Start the image worker via systemctl. Caller must hold _WorkerLock."""
    if is_image_worker_up():
        return True
    service = _image_service()
    logger.info("systemctl start %s", service)
    try:
        result = subprocess.run(
            ["systemctl", "start", service],
            capture_output=True,
            timeout=30,
        )
        if result.returncode != 0:
            logger.warning(
                "systemctl start %s returned %d: %s",
                service,
                result.returncode,
                result.stderr.decode(errors="replace"),
            )
        for _ in range(30):
            time.sleep(3)
            if is_image_worker_up():
                logger.info("Image worker ready")
                return True
        logger.warning("Image worker did not become healthy within 90 s")
        return False
    except Exception as exc:
        logger.error("Failed to start image worker: %s", exc)
        return False


def _stop_image_worker_locked() -> None:
    """Stop the image worker via systemctl. Caller must hold _WorkerLock."""
    service = _image_service()
    logger.info("systemctl stop %s", service)
    try:
        subprocess.run(
            ["systemctl", "stop", service],
            capture_output=True,
            timeout=30,
        )
    except Exception as exc:
        logger.warning("Could not stop image worker: %s", exc)


# ── public API ────────────────────────────────────────────────────────────────

def ensure_text_worker(start_managed_worker: bool = True) -> bool:
    """Ensure the text worker is running (respects GPU_WORKER_MODE).

    In always_on mode, just updates the last-used timestamp and returns True.
    In on_demand/exclusive mode, acquires the global file lock, stops the
    competing worker if exclusive, then starts the managed text worker only
    when the selected provider actually needs TEXT_WORKER_CMD.
    Returns True if the worker is (or should be) up.
    """
    mode = gpu_worker_mode()
    if mode == "always_on":
        _touch_last_used("text")
        return True

    with _WorkerLock():
        if mode == "exclusive" and is_image_worker_up():
            logger.info("[exclusive] Stopping image worker before starting text worker")
            _stop_image_worker_locked()
        if not start_managed_worker:
            if is_text_worker_up():
                logger.info("Stopping managed text worker; selected provider does not use TEXT_WORKER_CMD")
                _stop_text_worker_locked()
            return True
        ok = _start_text_worker_locked()
        if ok:
            _touch_last_used("text")
        return ok


def ensure_image_worker() -> bool:
    """Ensure the image worker is running (respects GPU_WORKER_MODE).

    In always_on mode, just updates the last-used timestamp and returns True.
    In on_demand/exclusive mode, acquires the global file lock, stops the
    competing worker if exclusive, then starts the image worker if needed.
    Returns True if the worker is (or should be) up.
    """
    mode = gpu_worker_mode()
    if mode == "always_on":
        _touch_last_used("image")
        return True

    with _WorkerLock():
        if mode == "exclusive" and is_text_worker_up():
            logger.info("[exclusive] Stopping text worker before starting image worker")
            _stop_text_worker_locked()
        ok = _start_image_worker_locked()
        if ok:
            _touch_last_used("image")
        return ok


def release_image_worker_after_job(reason: str = "terminal image job") -> bool:
    """Stop the managed image worker immediately after the last image job.

    always_on keeps the historical externally managed behavior. on_demand and
    exclusive can opt out with IMAGE_WORKER_STOP_AFTER_JOB=false.
    """
    mode = gpu_worker_mode()
    if mode == "always_on" or not image_worker_stop_after_job():
        return False

    with _WorkerLock():
        if not is_image_worker_up():
            return False
        logger.info("Stopping image worker after %s", reason)
        _stop_image_worker_locked()
        state = _load_state()
        state["image_last_used"] = 0
        _save_state(state)
        return True


def reap_idle_workers() -> None:
    """Stop workers that have been idle longer than GPU_WORKER_IDLE_TIMEOUT_SECONDS.

    Skips in always_on mode. Safe to call from a background daemon thread.
    """
    mode = gpu_worker_mode()
    if mode == "always_on":
        return

    timeout = idle_timeout_seconds()
    now = int(time.time())
    state = _load_state()

    with _WorkerLock():
        text_idle = now - int(state.get("text_last_used", 0))
        if text_idle > timeout and is_text_worker_up():
            logger.info("Text worker idle %ds > %ds — stopping", text_idle, timeout)
            _stop_text_worker_locked()

        image_idle = now - int(state.get("image_last_used", 0))
        if image_idle > timeout and is_image_worker_up():
            logger.info("Image worker idle %ds > %ds — stopping", image_idle, timeout)
            _stop_image_worker_locked()


# ── background idle reaper ────────────────────────────────────────────────────

_reap_timer_lock = threading.Lock()
_reap_timer: threading.Timer | None = None


def schedule_idle_reap() -> None:
    """Schedule a single background idle-reap after the idle timeout elapses.

    Each call resets the timer so that back-to-back requests delay the reap
    naturally without spawning many threads.
    Skips in always_on mode.
    """
    if gpu_worker_mode() == "always_on":
        return

    global _reap_timer

    delay = idle_timeout_seconds() + 15

    with _reap_timer_lock:
        if _reap_timer is not None:
            _reap_timer.cancel()

        t = threading.Timer(delay, reap_idle_workers)
        t.daemon = True
        t.start()
        _reap_timer = t
