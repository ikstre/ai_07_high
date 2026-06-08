from __future__ import annotations

from fastapi import FastAPI

from . import assets, plates


def register_routes(app: FastAPI) -> None:
    app.include_router(assets.router)
    app.include_router(plates.router)
