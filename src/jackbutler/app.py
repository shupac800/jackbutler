from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from jackbutler.web.routes import router

STATIC_DIR = Path(__file__).resolve().parent / "static"


def create_app() -> FastAPI:
    application = FastAPI(title="Jack Butler", version="0.1.0")
    application.include_router(router)
    application.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    return application


app = create_app()
