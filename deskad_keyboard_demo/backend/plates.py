from __future__ import annotations

import hashlib
import json
import os
from functools import lru_cache
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_REPO_PATH = Path("C:/tmp/keyboard_layout")


def keyboard_layout_repo_path() -> Path | None:
    """환경 변수에 설정된 keyboard-layout-editor 저장소 경로를 확인한다."""
    raw_path = os.getenv("KEYBOARD_LAYOUT_REPO_PATH")
    path = Path(raw_path) if raw_path else DEFAULT_REPO_PATH
    return path if (path / "keyboard_data.json").exists() else None


def _plate_id(file_path: str) -> str:
    """도면 파일 경로를 URL/JSON에서 쓰기 쉬운 plate id로 변환한다."""
    return hashlib.sha1(file_path.replace("\\", "/").encode("utf-8")).hexdigest()[:16]


def _local_file(repo_path: Path, file_path: str) -> Path:
    """카탈로그의 상대 파일 경로를 로컬 저장소 절대 경로로 변환한다."""
    return repo_path / file_path.replace("\\", "/")


def _preview_path(repo_path: Path, file_path: str) -> Path | None:
    """도면 파일과 같은 이름의 preview 이미지가 있는지 찾아 반환한다."""
    drawing_path = _local_file(repo_path, file_path)
    candidates = [
        drawing_path.with_suffix(".png"),
        drawing_path.with_suffix(".jpg"),
        drawing_path.with_suffix(".webp"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


@lru_cache(maxsize=1)
def load_plate_catalog() -> list[dict]:
    """keyboard-layout-editor 저장소의 plate JSON 파일들을 읽어 카탈로그로 정리한다."""
    repo_path = keyboard_layout_repo_path()
    if repo_path is None:
        return []

    data = json.loads((repo_path / "keyboard_data.json").read_text(encoding="utf-8"))
    catalog: list[dict] = []
    for item in data.get("plates", []):
        file_path = item.get("filePath") or ""
        drawing_path = _local_file(repo_path, file_path)
        preview_path = _preview_path(repo_path, file_path)
        plate_id = _plate_id(file_path)
        catalog.append(
            {
                "id": plate_id,
                "brand": item.get("brandName", ""),
                "keyboard": item.get("keyboardName", ""),
                "file_name": item.get("fileName", ""),
                "file_path": file_path,
                "extension": drawing_path.suffix.lower().lstrip("."),
                "has_local_file": drawing_path.exists(),
                "has_preview": preview_path is not None,
                "preview_url": f"/plates/{plate_id}/preview" if preview_path else None,
                "source_url": item.get("keyboardGithubUrl", ""),
            }
        )
    return catalog


def list_plate_brands() -> list[str]:
    """카탈로그에 존재하는 브랜드명을 중복 없이 정렬해 반환한다."""
    brands = {plate.get("brand", "").strip() for plate in load_plate_catalog()}
    return sorted(brand for brand in brands if brand)


def search_plates(query: str = "", brand: str = "", limit: int = 80) -> list[dict]:
    """검색어, 브랜드, 제한 개수에 맞춰 플레이트 카탈로그를 필터링한다."""
    normalized = query.strip().lower()
    plates = load_plate_catalog()
    normalized_brand = brand.strip().lower()
    if normalized_brand:
        plates = [item for item in plates if item.get("brand", "").strip().lower() == normalized_brand]
    if normalized:
        terms = [term for term in normalized.replace("[", " ").replace("]", " ").split() if term]

        def matches(item: dict) -> bool:
            """search_plates.matches 기능을 처리한다."""
            text = " ".join(
                [
                    item.get("brand", ""),
                    item.get("keyboard", ""),
                    item.get("file_name", ""),
                    item.get("extension", ""),
                ]
            ).lower()
            return all(term in text for term in terms)

        plates = [item for item in plates if matches(item)]
    return plates[: max(1, min(limit, 1000))]


def get_plate(plate_id: str) -> dict | None:
    """plate id와 일치하는 단일 카탈로그 항목을 반환한다."""
    for plate in load_plate_catalog():
        if plate["id"] == plate_id:
            return plate
    return None


def get_plate_preview_path(plate_id: str) -> Path | None:
    """plate id에 해당하는 preview 이미지 경로를 반환한다."""
    repo_path = keyboard_layout_repo_path()
    plate = get_plate(plate_id)
    if repo_path is None or plate is None:
        return None
    return _preview_path(repo_path, plate["file_path"])
