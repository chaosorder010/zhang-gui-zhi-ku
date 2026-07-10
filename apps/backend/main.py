from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from apps.backend.core.config import get_settings
from apps.backend.routers import ask as ask_router
from apps.backend.routers import upload as upload_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup: 触发 settings 加载
    get_settings()
    yield


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(title=s.app_name, debug=s.app_debug, lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(ask_router.router)
    app.include_router(upload_router.router)

    # Static frontend
    frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
    if frontend_dir.exists():
        app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")

        @app.get("/")
        async def root():
            return FileResponse(str(frontend_dir / "index.html"))

    return app


app = create_app()
