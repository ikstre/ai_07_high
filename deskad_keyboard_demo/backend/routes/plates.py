"""이 파일은 키보드 플레이트 조회 API를 담당한다."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import FileResponse

from ..errors import not_found
from ..plates import get_plate_preview_path, keyboard_layout_repo_path, list_plate_brands, search_plates


router = APIRouter()


@router.get("/plates")
def list_plates(query: str = "", brand: str = "", limit: int = 80):
    """검색어와 브랜드 기준으로 필터링한 키보드 플레이트 카탈로그를 반환한다."""
    return {
        "repo_path": str(keyboard_layout_repo_path()) if keyboard_layout_repo_path() else None,
        "plates": search_plates(query=query, brand=brand, limit=limit),
    }


@router.get("/plates/brands")
def plate_brands():
    """플레이트 카탈로그에서 사용 가능한 브랜드 목록을 반환한다."""
    return {
        "repo_path": str(keyboard_layout_repo_path()) if keyboard_layout_repo_path() else None,
        "brands": list_plate_brands(),
    }


@router.get("/plates/{plate_id}/preview")
def plate_preview(plate_id: str):
    """선택한 플레이트 미리보기 이미지를 정적 파일 응답으로 반환한다."""
    preview_path = get_plate_preview_path(plate_id)
    if preview_path is None or not preview_path.exists():
        raise not_found("Plate preview not found")
    return FileResponse(preview_path)
