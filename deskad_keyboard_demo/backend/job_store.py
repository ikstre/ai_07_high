from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path


class ImageJobStore:
    """Append-only jsonl image-job store with an in-memory snapshot.

    File format: each line is a complete JSON job record. Later lines for the same
    job_id supersede earlier ones (write-once-per-update). On load we replay the file
    in order to rebuild the latest snapshot per job_id.
    """

    def __init__(self, path: Path):
        self._path = path
        self._lock = threading.RLock()
        self._cache: dict[str, dict] = {}
        self._loaded = False

    @property
    def path(self) -> Path:
        return self._path

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        with self._lock:
            if self._loaded:
                return
            self._cache = self._read_snapshot()
            self._loaded = True

    def _read_snapshot(self) -> dict[str, dict]:
        if not self._path.exists():
            return {}
        snapshot: dict[str, dict] = {}
        try:
            with self._path.open("r", encoding="utf-8") as handle:
                for raw in handle:
                    line = raw.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    job_id = record.get("job_id")
                    if isinstance(job_id, str):
                        snapshot[job_id] = record
        except OSError:
            return {}
        return snapshot

    def _append_record(self, record: dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        first_write = not self._path.exists()
        line = json.dumps(record, ensure_ascii=False, default=str)
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
        if first_write:
            try:
                os.chmod(self._path, 0o600)
            except OSError:
                pass

    def all(self) -> dict[str, dict]:
        self._ensure_loaded()
        with self._lock:
            return dict(self._cache)

    def get(self, job_id: str) -> dict | None:
        self._ensure_loaded()
        with self._lock:
            record = self._cache.get(job_id)
            return dict(record) if record else None

    def save(self, job: dict) -> dict:
        if not isinstance(job, dict):
            raise TypeError("job must be a dict")
        job_id = job.get("job_id")
        if not isinstance(job_id, str) or not job_id:
            raise ValueError("job is missing a non-empty 'job_id'")
        self._ensure_loaded()
        with self._lock:
            self._cache[job_id] = dict(job)
            self._append_record(self._cache[job_id])
            return dict(self._cache[job_id])

    def compact(self) -> None:
        """Rewrite the jsonl to contain only the latest snapshot per job_id."""
        self._ensure_loaded()
        with self._lock:
            if not self._cache:
                return
            self._path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_path = tempfile.mkstemp(
                prefix=".image_jobs_", suffix=".jsonl.tmp", dir=str(self._path.parent)
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    for record in self._cache.values():
                        handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
                os.replace(tmp_path, self._path)
            except Exception:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
