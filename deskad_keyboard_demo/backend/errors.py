"""이 파일은 FastAPI HTTPError helper를 담당한다."""

from __future__ import annotations

from fastapi import HTTPException


def bad_request(detail: str) -> HTTPException:
    return HTTPException(status_code=400, detail=detail)


def not_found(detail: str) -> HTTPException:
    return HTTPException(status_code=404, detail=detail)


def server_error(detail: str) -> HTTPException:
    return HTTPException(status_code=500, detail=detail)
