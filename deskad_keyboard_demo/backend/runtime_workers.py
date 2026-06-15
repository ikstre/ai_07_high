"""GPU worker lifecycle management.

GPU_WORKER_MODE environment variable controls behavior:
  always_on   — assume workers are managed externally; never start/stop (default)
  on_demand   — start the needed worker on cache miss; stop it after idle timeout
  exclusive   — before starting one worker, stop the others to free VRAM

Worker types:
  text             — local OpenAI-compatible server (TEXT_WORKER_CMD / TEXT_WORKER_HEALTH_URL)
  image            — ComfyUI (IMAGE_WORKER_SERVICE / IMAGE_WORKER_HEALTH_URL, systemctl)
  hyperclova_vision— HyperCLOVA Omni 이미지 입력 thin server (:11601, 4bit ~11GB)
  hyperclova_image — HyperCLOVA Omni 네이티브 이미지 생성 server (:11602, 8bit ~15GB)

단일 L4(22GB)에서는 위 워커들이 VRAM을 두고 경합하므로 exclusive 모드에서
서로 배타적으로 관리한다(전환마다 ~75s 모델 리로드). 트랙(생성 엔진) 선택 시
activate_track이 해당 워커를 백그라운드로 미리 워밍업한다.

Idle reaping runs lazily in a background daemon thread after each GPU request.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import requests

try:
    import fcntl
except ImportError:  # Windows does not provide fcntl; always_on mode never needs it.
    fcntl = None

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


# ── process worker specs ──────────────────────────────────────────────────────
# subprocess.Popen으로 직접 띄우는 GPU 워커들. ComfyUI(image)는 systemctl 관리라 별도.

@dataclass(frozen=True)
class ProcessWorkerSpec:
    name: str                 # worker_state.json의 "<name>_pid"/"<name>_last_used" 키
    cmd_env: str
    default_cmd: str
    health_env: str
    default_health: str
    startup_timeout_env: str
    startup_timeout_default: int


TEXT_WORKER = ProcessWorkerSpec(
    name="text",
    cmd_env="TEXT_WORKER_CMD",
    default_cmd="",
    health_env="TEXT_WORKER_HEALTH_URL",
    default_health="http://127.0.0.1:11501/health",
    startup_timeout_env="TEXT_WORKER_STARTUP_TIMEOUT_SECONDS",
    startup_timeout_default=60,
)

# 검증된 기동 레시피는 docs/hyperclova_omni_vision_input_2026-06-10.md 참고.
HYPERCLOVA_VISION_WORKER = ProcessWorkerSpec(
    name="hyperclova_vision",
    cmd_env="HYPERCLOVA_VISION_WORKER_CMD",
    default_cmd=(
        "HYPERCLOVA_OMNI_PORT=11601 HYPERCLOVA_OMNI_LOAD_IN_4BIT=true "
        "conda run --no-capture-output -n sprint_high python tools/hyperclova_omni_openai_vision_server.py"
    ),
    health_env="HYPERCLOVA_VISION_WORKER_HEALTH_URL",
    default_health="http://127.0.0.1:11601/health",
    startup_timeout_env="HYPERCLOVA_VISION_WORKER_STARTUP_TIMEOUT_SECONDS",
    startup_timeout_default=240,  # 4bit 모델 로드 ~75s+ — 여유를 둔다
)

HYPERCLOVA_IMAGE_WORKER = ProcessWorkerSpec(
    name="hyperclova_image",
    cmd_env="HYPERCLOVA_IMAGE_WORKER_CMD",
    default_cmd=(
        "PYTHONUNBUFFERED=1 "
        "conda run --no-capture-output -n sprint_high python tools/hyperclova_omni_image_server.py"
    ),
    health_env="HYPERCLOVA_IMAGE_WORKER_HEALTH_URL",
    default_health="http://127.0.0.1:11602/health",
    startup_timeout_env="HYPERCLOVA_IMAGE_WORKER_STARTUP_TIMEOUT_SECONDS",
    startup_timeout_default=240,  # 8bit LLM + 디코더 로드 ~75s+
)

_PROCESS_WORKERS: dict[str, ProcessWorkerSpec] = {
    spec.name: spec for spec in (TEXT_WORKER, HYPERCLOVA_VISION_WORKER, HYPERCLOVA_IMAGE_WORKER)
}


def _worker_cmd(spec: ProcessWorkerSpec) -> str:
    return _env(spec.cmd_env, spec.default_cmd)


def _worker_log_path(spec: ProcessWorkerSpec) -> Path:
    # stdout/stderr를 버리면 token-block 실패 같은 워커측 원인을 추적할 수 없다.
    return _BACKEND_BASE_DIR / "data" / "runtime" / f"{spec.name}_worker.log"


def _worker_health_url(spec: ProcessWorkerSpec) -> str:
    return _env(spec.health_env, spec.default_health)


def _worker_startup_timeout(spec: ProcessWorkerSpec) -> int:
    return _int_env(spec.startup_timeout_env, spec.startup_timeout_default)


def _text_worker_cmd() -> str:
    return _worker_cmd(TEXT_WORKER)


def _text_health_url() -> str:
    return _worker_health_url(TEXT_WORKER)


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


def is_process_worker_up(spec: ProcessWorkerSpec) -> bool:
    return _is_healthy(_worker_health_url(spec))


def is_text_worker_up() -> bool:
    return is_process_worker_up(TEXT_WORKER)


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
        if fcntl is None:
            return self
        fcntl.flock(self._fd, fcntl.LOCK_EX)
        return self

    def __exit__(self, *args) -> None:
        if self._fd:
            if fcntl is not None:
                fcntl.flock(self._fd, fcntl.LOCK_UN)
            self._fd.close()
            self._fd = None


# ── start / stop internals ────────────────────────────────────────────────────

def _start_process_worker_locked(spec: ProcessWorkerSpec) -> bool:
    """Start a managed process worker. Caller must hold _WorkerLock."""
    if is_process_worker_up(spec):
        return True
    cmd = _worker_cmd(spec)
    if not cmd:
        logger.warning("%s not configured; cannot start %s worker", spec.cmd_env, spec.name)
        return False
    logger.info("Starting %s worker: %s", spec.name, cmd)
    try:
        log_path = _worker_log_path(spec)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "ab") as log_fd:
            proc = subprocess.Popen(
                cmd,
                shell=True,
                cwd=str(_BACKEND_BASE_DIR),  # 기본 cmd가 tools/ 상대 경로를 쓴다
                stdout=log_fd,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        state = _load_state()
        state[f"{spec.name}_pid"] = proc.pid
        _save_state(state)
        poll_interval = 3
        attempts = max(1, _worker_startup_timeout(spec) // poll_interval)
        for _ in range(attempts):
            time.sleep(poll_interval)
            if is_process_worker_up(spec):
                logger.info("%s worker ready", spec.name)
                return True
        logger.warning("%s worker did not become healthy within %s s", spec.name, attempts * poll_interval)
        return False
    except Exception as exc:
        logger.error("Failed to start %s worker: %s", spec.name, exc)
        return False


def _stop_process_worker_locked(spec: ProcessWorkerSpec) -> None:
    """Stop a managed process worker. Caller must hold _WorkerLock."""
    state = _load_state()
    pid = state.get(f"{spec.name}_pid")
    if pid:
        try:
            os.killpg(os.getpgid(int(pid)), 15)
            logger.info("SIGTERM → %s worker process group (pid=%s)", spec.name, pid)
        except (ProcessLookupError, OSError):
            pass
        except Exception as exc:
            logger.warning("Could not SIGTERM %s worker pid=%s: %s", spec.name, pid, exc)
        state[f"{spec.name}_pid"] = None
        _save_state(state)
    # belt-and-suspenders: fuser-kill the health port
    try:
        port = urlparse(_worker_health_url(spec)).port
        if port:
            subprocess.run(
                ["fuser", "-k", f"{port}/tcp"],
                capture_output=True,
                timeout=5,
            )
    except Exception:
        pass


def _start_text_worker_locked() -> bool:
    return _start_process_worker_locked(TEXT_WORKER)


def _stop_text_worker_locked() -> None:
    _stop_process_worker_locked(TEXT_WORKER)


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


def _comfyui_base_url() -> str:
    """ComfyUI base (scheme://host:port) derived from the image health URL."""
    parsed = urlparse(_image_health_url())
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return "http://127.0.0.1:8188"


def _free_image_worker_vram() -> None:
    """Unload models and free VRAM via ComfyUI's /free API.

    Privilege-free, unlike ``systemctl stop`` (blocked by polkit for a non-root
    user). This is what actually reclaims VRAM between exclusive text/image
    turns; the systemctl stop below stays best-effort for setups that grant it.
    """
    if _image_service() != "comfyui":
        return
    try:
        requests.post(
            f"{_comfyui_base_url()}/free",
            json={"unload_models": True, "free_memory": True},
            timeout=10,
        )
        logger.info("ComfyUI /free: models unloaded, VRAM freed")
    except Exception as exc:
        logger.warning("ComfyUI /free failed: %s", exc)


def _stop_image_worker_locked() -> None:
    """Reclaim image-worker VRAM. Caller must hold _WorkerLock.

    Frees VRAM via ComfyUI /free first (works without privilege), then attempts
    systemctl stop as best-effort (ignored when polkit denies a non-root user).
    """
    _free_image_worker_vram()
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


# ── exclusive 상호배타 ────────────────────────────────────────────────────────

def _hyperclova_image_busy() -> bool:
    """생성 중(running)인 hyperclova 이미지 job이 있으면 True — 워커 stop을 미룬다."""
    try:
        from .ai import IMAGE_JOB_STORE
    except Exception:
        return False
    now = int(time.time())
    for record in IMAGE_JOB_STORE.all().values():
        if record.get("provider") != "hyperclova_image":
            continue
        if record.get("status") not in {"created", "queued", "running"}:
            continue
        # grid 3컷은 컷별 순차 생성이라 정상 작업이 900s를 넘는다 — 장수만큼 예산 확대.
        try:
            image_count = max(1, int(record.get("requested_image_count") or 1))
        except (TypeError, ValueError):
            image_count = 1
        if now - int(record.get("created_at") or 0) > 900 * image_count:
            continue  # stale 좀비 — 죽은 job으로 간주
        return True
    return False


def _comfyui_busy() -> bool:
    try:
        from .ai import _has_active_comfyui_jobs

        return _has_active_comfyui_jobs()
    except Exception:
        return False


def _stop_other_gpu_workers_locked(active: str) -> None:
    """[exclusive] active 외 GPU 워커를 모두 내려 단일 L4 VRAM을 비운다.

    실행 중인 이미지 job(ComfyUI·hyperclova)이 있는 워커는 건너뛰어 job을 죽이지
    않는다 — 그 경우 VRAM 확보는 job 종료 후 release 경로가 처리한다.
    Caller must hold _WorkerLock.
    """
    if active != "image" and is_image_worker_up() and not _comfyui_busy():
        logger.info("[exclusive] Stopping image worker before starting %s", active or "nothing")
        _stop_image_worker_locked()
    for spec in _PROCESS_WORKERS.values():
        if spec.name == active:
            continue
        if spec.name == "hyperclova_image" and _hyperclova_image_busy():
            continue
        if is_process_worker_up(spec):
            logger.info("[exclusive] Stopping %s worker before starting %s", spec.name, active or "nothing")
            _stop_process_worker_locked(spec)


# ── public API ────────────────────────────────────────────────────────────────

def ensure_text_worker(start_managed_worker: bool = True) -> bool:
    """Ensure the text worker is running (respects GPU_WORKER_MODE).

    In always_on mode, just updates the last-used timestamp and returns True.
    In on_demand/exclusive mode, acquires the global file lock, stops the
    competing workers if exclusive, then starts the managed text worker only
    when the selected provider actually needs TEXT_WORKER_CMD.
    Returns True if the worker is (or should be) up.
    """
    mode = gpu_worker_mode()
    if mode == "always_on":
        _touch_last_used("text")
        return True

    with _WorkerLock():
        if mode == "exclusive":
            _stop_other_gpu_workers_locked("text")
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
    competing workers if exclusive, then starts the image worker if needed.
    Returns True if the worker is (or should be) up.
    """
    mode = gpu_worker_mode()
    if mode == "always_on":
        _touch_last_used("image")
        return True

    with _WorkerLock():
        if mode == "exclusive":
            _stop_other_gpu_workers_locked("image")
        ok = _start_image_worker_locked()
        if ok:
            _touch_last_used("image")
        return ok


def ensure_process_worker(spec: ProcessWorkerSpec) -> bool:
    """Ensure a managed process worker is running (respects GPU_WORKER_MODE)."""
    mode = gpu_worker_mode()
    if mode == "always_on":
        _touch_last_used(spec.name)
        return True

    with _WorkerLock():
        if mode == "exclusive":
            _stop_other_gpu_workers_locked(spec.name)
        ok = _start_process_worker_locked(spec)
        if ok:
            _touch_last_used(spec.name)
        return ok


def ensure_hyperclova_vision_worker() -> bool:
    return ensure_process_worker(HYPERCLOVA_VISION_WORKER)


def ensure_hyperclova_image_worker() -> bool:
    return ensure_process_worker(HYPERCLOVA_IMAGE_WORKER)


# ── 트랙(생성 엔진) 선택 기점 워밍업 ──────────────────────────────────────────

# 트랙 → 미리 워밍업할 워커. openai는 API만 쓰므로 로컬 GPU를 전부 비운다.
# hyperclova의 vision(:11601)은 image(:11602)와 단일 L4에 동시 적재 불가(11+15GB>22GB)
# → 무거운 이미지 생성 서버를 기본 워밍업하고, vision은 입력 단계에서 on-demand 기동.
_TRACK_WARM_WORKERS = {
    "openai": [],
    "hyperclova": ["hyperclova_image"],
    "local": ["image"],
}


def track_warm_plan(track: str) -> list[str] | None:
    """트랙이 워밍업할 워커 이름 목록. 알 수 없는/auto 트랙은 None(워밍업 없음)."""
    return _TRACK_WARM_WORKERS.get((track or "").strip().lower())


def activate_track(track: str) -> dict:
    """3트랙(생성 엔진) 선택 시점에 해당 GPU 워커를 백그라운드로 워밍업한다.

    모델 리로드가 ~75s라 호출자는 블로킹하지 않고 daemon thread로 진행한다.
    여기 실패해도 실제 job 경로의 ensure_*_worker가 다시 보장하므로 치명적이지 않다.
    """
    plan = track_warm_plan(track)
    mode = gpu_worker_mode()
    result = {"track": (track or "").strip().lower(), "mode": mode, "scheduled": False}
    if plan is None:
        result["message"] = "auto/unknown track — no warmup"
        return result
    if mode == "always_on":
        result["message"] = "GPU_WORKER_MODE=always_on — workers are managed externally"
        return result

    def _warm() -> None:
        try:
            with _WorkerLock():
                if mode == "exclusive":
                    _stop_other_gpu_workers_locked(plan[0] if plan else "")
                for name in plan:
                    ok = (
                        _start_image_worker_locked()
                        if name == "image"
                        else _start_process_worker_locked(_PROCESS_WORKERS[name])
                    )
                    if ok:
                        _touch_last_used(name)
        except Exception as exc:
            logger.warning("activate_track(%s) warmup failed: %s", track, exc)

    threading.Thread(target=_warm, name=f"activate-track-{result['track']}", daemon=True).start()
    result.update({"scheduled": True, "warm_workers": plan})
    return result


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

    # idle 판정~stop을 모두 락 안에서 수행한다. state를 락 밖에서 읽으면, 읽은 시점과
    # 락 획득 사이에 ensure_*_worker가 작업 시작과 함께 *_last_used를 갱신(이 갱신도
    # 락 안에서 일어남)해도 그 갱신을 못 보고 stale 스냅샷으로 idle 판정 → 막 작업을
    # 시작한 워커에 SIGTERM을 보내는 race가 생긴다. 락 안에서 읽으면 가장 최신
    # last_used를 보게 되어 그 race가 사라진다.
    with _WorkerLock():
        state = _load_state()
        now = int(time.time())
        for spec in _PROCESS_WORKERS.values():
            idle = now - int(state.get(f"{spec.name}_last_used", 0))
            if idle <= timeout or not is_process_worker_up(spec):
                continue
            if spec.name == "hyperclova_image" and _hyperclova_image_busy():
                continue
            logger.info("%s worker idle %ds > %ds — stopping", spec.name, idle, timeout)
            _stop_process_worker_locked(spec)

        image_idle = now - int(state.get("image_last_used", 0))
        if image_idle > timeout and is_image_worker_up() and not _comfyui_busy():
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
