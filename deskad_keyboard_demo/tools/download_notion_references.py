from __future__ import annotations

import json
import sys
from pathlib import Path
from time import sleep
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))

from backend.config import get_settings  # noqa: E402


MANIFEST_PATH = APP_DIR / "data" / "reference_assets.json"


def download(url: str, target: Path) -> tuple[bool, str]:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.stat().st_size > 0:
        return True, f"already exists, {target.stat().st_size} bytes"

    request = Request(url, headers={"User-Agent": "Mozilla/5.0 DeskAdAIStudio/1.0"})
    last_error = "unknown error"
    for attempt in range(4):
        try:
            with urlopen(request, timeout=45) as response:
                data = response.read()
        except HTTPError as exc:
            last_error = str(exc)
            if exc.code == 429 and attempt < 3:
                sleep(3 * (attempt + 1))
                continue
            return False, last_error
        except (URLError, TimeoutError) as exc:
            last_error = str(exc)
            if attempt < 3:
                sleep(2 * (attempt + 1))
                continue
            return False, last_error
        if not data:
            last_error = "empty response"
            sleep(1)
            continue
        target.write_bytes(data)
        return True, f"{len(data)} bytes"
    return False, last_error


def _target_root(storage: str) -> Path:
    settings = get_settings()
    if storage == "shared_model":
        return Path(settings.shared_model_dir).expanduser()
    if storage == "static":
        return APP_DIR / "static"
    return Path(settings.shared_data_dir).expanduser()


def main() -> int:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    references = manifest.get("references", [])
    ok = 0
    failed: list[tuple[str, str]] = []

    for item in references:
        local_path = item.get("local_path")
        source_url = item.get("source_url")
        if not local_path or not source_url:
            continue
        target = _target_root(item.get("storage", manifest.get("storage", "shared_data"))) / local_path
        success, message = download(source_url, target)
        label = item.get("id", local_path)
        if success:
            ok += 1
            print(f"OK {label}: {message}")
        else:
            failed.append((label, message))
            print(f"FAIL {label}: {message}", file=sys.stderr)

    settings = get_settings()
    print(f"Downloaded {ok}/{len(references)} reference files into {Path(settings.shared_data_dir).expanduser() / 'reference_drawings'}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
