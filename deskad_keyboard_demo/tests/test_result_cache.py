import os
import time

from backend import result_cache


def _age(path, seconds_ago: float) -> None:
    """Set a file's mtime to `seconds_ago` in the past for deterministic LRU/TTL."""
    when = time.time() - seconds_ago
    os.utime(path, (when, when))


def test_prune_evicts_least_recently_used_beyond_cap(tmp_path, monkeypatch):
    monkeypatch.setenv("GPU_WORKER_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("GPU_WORKER_CACHE_MAX_AGE_DAYS", "0")  # TTL off, isolate LRU
    monkeypatch.setenv("GPU_WORKER_CACHE_MAX_ENTRIES", "1000")  # no eviction during writes

    text_dir = tmp_path / "text"
    for i in range(5):
        result_cache.put_text_cache(f"key{i}", {"i": i})
    # key0 oldest … key4 newest
    for i in range(5):
        _age(text_dir / f"key{i}.json", (5 - i) * 10)

    monkeypatch.setenv("GPU_WORKER_CACHE_MAX_ENTRIES", "2")
    removed = result_cache.prune_caches()

    survivors = sorted(p.stem for p in text_dir.glob("*.json"))
    assert removed["text"] == 3
    assert survivors == ["key3", "key4"]  # only the 2 most-recent remain


def test_prune_expires_entries_older_than_ttl(tmp_path, monkeypatch):
    monkeypatch.setenv("GPU_WORKER_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("GPU_WORKER_CACHE_MAX_ENTRIES", "1000")  # count cap off, isolate TTL
    monkeypatch.setenv("GPU_WORKER_CACHE_MAX_AGE_DAYS", "7")

    text_dir = tmp_path / "text"
    result_cache.put_text_cache("fresh", {"v": 1})
    result_cache.put_text_cache("stale", {"v": 2})
    _age(text_dir / "stale.json", 10 * 86400)  # 10 days old > 7-day TTL

    removed = result_cache.prune_caches()

    survivors = sorted(p.stem for p in text_dir.glob("*.json"))
    assert removed["text"] == 1
    assert survivors == ["fresh"]


def test_cache_hit_bumps_recency_and_survives_lru(tmp_path, monkeypatch):
    monkeypatch.setenv("GPU_WORKER_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("GPU_WORKER_CACHE_MAX_AGE_DAYS", "0")
    monkeypatch.setenv("GPU_WORKER_CACHE_MAX_ENTRIES", "1000")

    text_dir = tmp_path / "text"
    for i in range(3):
        result_cache.put_text_cache(f"key{i}", {"i": i})
    for i in range(3):
        _age(text_dir / f"key{i}.json", (3 - i) * 10)  # key0 oldest

    # Reading the oldest entry must bump its mtime (LRU recency, not creation).
    assert result_cache.get_text_cache("key0")["i"] == 0

    monkeypatch.setenv("GPU_WORKER_CACHE_MAX_ENTRIES", "1")
    result_cache.prune_caches()

    survivors = [p.stem for p in text_dir.glob("*.json")]
    assert survivors == ["key0"]  # just-read entry survived despite being created first


def test_image_cache_excludes_binary_bytes(tmp_path, monkeypatch):
    monkeypatch.setenv("GPU_WORKER_CACHE_DIR", str(tmp_path))
    result_cache.put_image_cache("job1", {"status": "done", "image_b64": "AAAA", "seed": 7})

    cached = result_cache.get_image_cache("job1")
    assert cached["status"] == "done"
    assert cached["seed"] == 7
    assert "image_b64" not in cached  # heavy bytes never persisted to disk
