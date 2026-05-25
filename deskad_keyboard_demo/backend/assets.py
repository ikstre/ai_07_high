
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
ASSET_CATALOG_PATH = BASE_DIR / "data" / "desk_assets.json"


@lru_cache(maxsize=1)
def load_desk_assets() -> list[dict]:
    if not ASSET_CATALOG_PATH.exists():
        return []
    return json.loads(ASSET_CATALOG_PATH.read_text(encoding="utf-8"))


def enabled_asset_ids(default: bool = True) -> list[str]:
    return [asset["id"] for asset in load_desk_assets() if asset.get("enabled_by_default") is default]
