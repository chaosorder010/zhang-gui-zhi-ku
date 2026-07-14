"""上传路由: 接收 PDF → 触发 LangGraph 导入工作流."""
from __future__ import annotations

import logging
import uuid
import time
from typing import Optional

from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks

from apps.backend.core.config import get_settings
from apps.backend.services.milvus_client import delete_by_doc_name
from apps.backend.services.import_workflow import (
    build_import_graph,
    create_initial_import_state,
    ImportState,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["upload"])

# 内存任务状态 (生产应换 Redis/DB)
# 每条记录带 ts, 读取时惰性清理 TTL 过期条目防内存泄漏
_task_status: dict[str, dict] = {}
_TTL_SECONDS = 3600  # 任务状态保留 1 小时


def trigger_import_sync(state: ImportState) -> None:
    """后台同步触发 LangGraph 导入 (供 BackgroundTasks 调用)."""
    task_id = state["task_id"]
    logger.info("[import:%s] workflow started (file=%s)", task_id, state.get("file_name"))
    graph = build_import_graph()
    try:
        final = graph.invoke(state)
        _task_status[task_id] = {
            "task_id": task_id,
            "status": final.get("status", "unknown"),
            "item_name": final.get("item_name"),
            "error": final.get("error"),
            "ts": time.time(),
        }
        log_level = logger.info if final.get("status") == "done" else logger.warning
        log_level("[import:%s] workflow finished status=%s item_name=%s",
                  task_id, final.get("status"), final.get("item_name"))
    except Exception as e:
        logger.error("[import:%s] workflow crashed: %s", task_id, e, exc_info=True)
        _task_status[task_id] = {
            "task_id": task_id,
            "status": "failed",
            "error": str(e),
            "ts": time.time(),
        }


_ALLOWED_SUFFIXES = (".pdf", ".md", ".doc", ".docx", ".ppt", ".pptx")


def _is_allowed_file(filename: Optional[str]) -> bool:
    """校验文件名后缀是否在白名单内."""
    return bool(filename) and filename.lower().endswith(_ALLOWED_SUFFIXES)


@router.post("/upload")
async def upload(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
):
    s = get_settings()
    if not s.mineru_api_key:
        raise HTTPException(400, "MinerU 未配置, 请在 .env 设置 MINERU_API_KEY")

    # Fail-fast: 入口校验所有文件名后缀, 任一非法 → 整批拒绝
    for f in files:
        if not _is_allowed_file(f.filename):
            raise HTTPException(400, "仅支持 PDF/MD/DOC/DOCX/PPT/PPTX 文件")

    # Fail-fast: 校验所有文件非空, 任一为空 → 整批拒绝
    binaries = []
    for f in files:
        binary = await f.read()
        if not binary:
            raise HTTPException(400, "文件为空")
        binaries.append(binary)

    batch_id = str(uuid.uuid4())
    tasks = []
    for f, binary in zip(files, binaries):
        task_id = str(uuid.uuid4())
        state = create_initial_import_state(
            task_id=task_id,
            file_name=f.filename or "unknown",
            file_binary=binary,
            mineru_base_url=s.mineru_base_url,
            mineru_token=s.mineru_api_key,
            openai_api_key=s.openai_api_key,
            openai_base_url=s.openai_base_url,
            openai_model=s.openai_model,
        )
        _task_status[task_id] = {"task_id": task_id, "status": "uploaded", "ts": time.time()}
        # 每文件独立后台触发 (FastAPI BackgroundTasks → 线程池)
        background_tasks.add_task(trigger_import_sync, state)
        tasks.append({"task_id": task_id, "file_name": f.filename, "status": "uploaded"})

    return {"batch_id": batch_id, "tasks": tasks, "count": len(tasks)}


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


@router.delete("/documents/{doc_name}")
def delete_document(doc_name: str):
    """删除文档的所有 chunk, 级联清理 task_status."""
    deleted_chunks = delete_by_doc_name(doc_name)

    if deleted_chunks == 0:
        return {"doc_name": doc_name, "deleted_chunks": 0, "status": "not_found"}

    # 级联清理 _task_status 中 file_name == doc_name 的条目
    to_remove = [
        tid
        for tid, v in _task_status.items()
        if v.get("file_name") == doc_name
    ]
    for tid in to_remove:
        del _task_status[tid]

    return {"doc_name": doc_name, "deleted_chunks": deleted_chunks, "status": "deleted"}
