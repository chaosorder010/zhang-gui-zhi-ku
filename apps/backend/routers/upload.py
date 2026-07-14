"""上传路由: 接收 PDF → 触发 LangGraph 导入工作流."""
from __future__ import annotations

import uuid
import time
from typing import Optional

from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks

from apps.backend.core.config import get_settings
from apps.backend.services.import_workflow import build_import_graph, ImportState

router = APIRouter(prefix="/api", tags=["upload"])

# 内存任务状态 (生产应换 Redis/DB)
# 每条记录带 ts, 读取时惰性清理 TTL 过期条目防内存泄漏
_task_status: dict[str, dict] = {}
_TTL_SECONDS = 3600  # 任务状态保留 1 小时


def trigger_import_sync(state: ImportState) -> None:
    """后台同步触发 LangGraph 导入 (供 BackgroundTasks 调用)."""
    graph = build_import_graph()
    try:
        final = graph.invoke(state)
        _task_status[state["task_id"]] = {
            "task_id": state["task_id"],
            "status": final.get("status", "unknown"),
            "item_name": final.get("item_name"),
            "error": final.get("error"),
            "ts": time.time(),
        }
    except Exception as e:
        _task_status[state["task_id"]] = {
            "task_id": state["task_id"],
            "status": "failed",
            "error": str(e),
            "ts": time.time(),
        }


@router.post("/upload")
async def upload(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
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

    _task_status[task_id] = {"task_id": task_id, "status": "uploaded", "ts": time.time()}
    # 后台触发 (FastAPI BackgroundTasks → 线程池)
    background_tasks.add_task(trigger_import_sync, state)

    return {"task_id": task_id, "file_name": file.filename, "status": "uploaded"}


@router.get("/documents")
async def list_documents():
    return list(_task_status.values())


def _cleanup_expired() -> None:
    """惰性清理 TTL 过期任务状态."""
    now = time.time()
    expired = [
        tid
        for tid, v in _task_status.items()
        if now - v.get("ts", 0) > _TTL_SECONDS
    ]
    for tid in expired:
        del _task_status[tid]


@router.get("/upload/{task_id}")
async def get_upload_status(task_id: str):
    _cleanup_expired()
    info = _task_status.get(task_id)
    if not info:
        raise HTTPException(404, "任务不存在")
    return info
