"""이 파일은 FastAPI 앱 생성과 static mount를 담당한다."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .library import shared_data_dir, shared_model_dir


def ensure_static_dirs(*directories: Path) -> None:
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)


def create_app(static_dir: Path) -> FastAPI:
    app = FastAPI(title="DeskAd AI Studio API")

    cors_origins = get_settings().cors_origins
    if cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST"],
            allow_headers=["Authorization", "Content-Type"],
        )

    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    app.mount("/shared/data", StaticFiles(directory=shared_data_dir(), check_dir=False), name="shared_data")
    app.mount("/shared/models", StaticFiles(directory=shared_model_dir(), check_dir=False), name="shared_models")
    return app
