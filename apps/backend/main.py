import logging
import os

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from pymilvus import MilvusClient

from apps.backend.core.config import get_settings
from apps.backend.routers import ask as ask_router
from apps.backend.routers import upload as upload_router

logger = logging.getLogger(__name__)


def _check_milvus_readiness():
    """启动时检查 Milvus 是否可达, 不可达则抛出明确错误.

    检查方式: 创建临时连接 + 调用 list_collections (轻量级 RPC)。
    失败时抛出 ConnectionError, 信息包含 host:port 便于定位。
    """
    s = get_settings()
    uri = f"http://{s.milvus_host}:{s.milvus_port}"
    try:
        client = MilvusClient(uri=uri)
        client.list_collections()
        logger.info("Milvus connected: %s", uri)
    except Exception as exc:
        raise ConnectionError(
            f"Milvus 无法连接: {uri}. "
            f"请检查: 1) docker compose up 是否包含 Milvus 服务 "
            f"2) MILVUS_HOST/MILVUS_PORT 是否正确 "
            f"3) 网络是否通畅. 原始错误: {exc}"
        ) from exc


@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup: 触发 settings 加载 + Milvus 就绪检查
    get_settings()
    _check_milvus_readiness()
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
