"""FastAPI factory."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from kernel.api.rutas import router
from kernel.api.ws import ws_router


def create_app() -> FastAPI:
    app = FastAPI(title="RADAR v2.0", version="2.0-corr")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router, prefix="/api")
    app.include_router(ws_router)
    import os
    static_path = os.path.join(os.path.dirname(__file__), "../../frontend/dist")
    if os.path.isdir(static_path):
        app.mount("/", StaticFiles(directory=static_path, html=True), name="static")
    return app
