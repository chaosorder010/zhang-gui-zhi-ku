"""上传路由: 接收 PDF → 触发 LangGraph 导入工作流."""
from __future__ import annotations

import asyncio
import uuid
from typing import Optional

from fastapi import APIRouter, UploadFile, File, HTTPException

from apps.backend.core.config import get_settings
from apps.backend.services.import_workflow import build_import_graph, ImportState

router = APIRouter(prefix="/api", tags=["upload"])

# 内存任务状态 (生产应换 Redis/DB)
_task_status: dict[str, dict] = {}


def trigger_import(state: ImportState) -> None:
    """后台触发 LangGraph 导入."""
    graph = build_import_graph()

    async def _run():
        try:
            final = await graph.ainvoke(state)
            _task_status[state["task_id"]] = {
                "task_id": state["task_id"],
                "status": final.get("status", "unknown"),
                "item_name": final.get("item_name"),
                "error": final.get("error"),
            }
        except Exception as e:
            _task_status[state["task_id"]] = {
                "task_id": state["task_id"],
                "status": "failed",
                "error": str(e),
            }

    # 尝试获取/创建事件循环
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(_run())
        else:
            loop.run_until_complete(_run())
    except RuntimeError:
        asyncio.run(_run())


@router.post("/upload")
async def upload(file: UploadFile = File(...)):
    s = get_settings()
    if not s.mineru_api_key:
        raise HTTPException(400, "MinerU 未配置, 请在 .env 设置 MINERU_API_KEY")

    # 校验文件类型
    if not file.filename or not file.filename.lower().endswith((".pdf", ".md", ".doc", ".docx", ".ppt", ".pptx")):
        raise HTTPException(400, "仅支持 PDF/MD/DOC/DOCX/PPT/PPTX 文件")

    binary = await file.read()
    if not binary:
        raise HTTPException(400, "文件为空")

    task_id = str(uuid.uuid4())
    state: ImportState = {
        "task_id": task_id,
        "file_name": file.filename or "unknown",
        "file_binary": binary,
        "item_name": None,
        "markdown": "",
        "chunks": [],
        "vectors": [],
        "status": "uploaded",
        "error": None,
        "mineru_base_url": s.mineru_base_url,
        "mineru_token": s.mineru_api_key,
        "openai_api_key": s.openai_api_key,
        "openai_base_url": s.openai_base_url,
        "openai_model": s.openai_model,
    }

    _task_status[task_id] = {"task_id": task_id, "status": "uploaded"}
    # 后台触发
    asyncio.get_event_loop().run_in_executor(None, trigger_import, state)

    return {"task_id": task_id, "file_name": file.filename, "status": "uploaded"}


@router.get("/documents")
async def list_documents():
    return list(_task_status.values())


@router.get("/upload/{task_id}")
async def get_upload_status(task_id: str):
    info = _task_status.get(task_id)
    if not info:
        raise HTTPException(404, "任务不存在")
    return info
