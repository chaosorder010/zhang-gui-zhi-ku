"""导入工作流: LangGraph 编排 PDF → Milvus 入库.

节点:
  1. extract         — 调 MinerU 申请URL→上传→轮询→下载→解压→读 full.md
  2. recognize_item  — LLM 抽主体名
  3. chunk            — 按标题分块 + item_name 拼头
  4. embed            — BGE-M3 生成稠密+稀疏向量
  5. store            — Milvus 入库 + MongoDB 元数据
"""
from __future__ import annotations

import functools
import logging
from typing import Optional, TypedDict

from langgraph.graph import StateGraph, START, END

from apps.backend.services.mineru_client import extract_markdown
from apps.backend.services.recognizer import recognize_item, build_recognizer
from apps.backend.services.chunker import chunk_by_section
from apps.backend.services.embedder import embed_chunks
from apps.backend.services.milvus_client import bulk_upsert
from apps.backend.core.config import Settings

logger = logging.getLogger(__name__)


def node_handler(
    on_success_status: str,
    error_prefix: str,
):
    """节点装饰器: 统一错误处理 + fail-fast 守卫.

    消除各节点重复的::

        if state.get("status") == "failed":
            return state
        try:
            ...
        except Exception as e:
            return {**state, "status": "failed", "error": f"X: {e}"}

    用法::

        @node_handler(on_success_status="extracting", error_prefix="extract")
        def _node_extract(state: ImportState) -> dict:
            md = extract_markdown(...)
            if not md:
                raise ValueError("MinerU 返回空内容")
            return {"markdown": md}

    Args:
        on_success_status: 节点成功时写入 state["status"] 的值
        error_prefix: 失败时 error 字段前缀, 用于区分失败来源
    """
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(state: ImportState) -> ImportState:
            task_id = state.get("task_id", "?")
            if state.get("status") == "failed":
                logger.warning("[import:%s] skip %s (already failed: %s)",
                              task_id, fn.__name__, state.get("error"))
                return state
            logger.info("[import:%s] enter %s", task_id, fn.__name__)
            try:
                updates = fn(state) or {}
                result = {**state, **updates, "status": on_success_status}
                logger.info("[import:%s] exit %s → status=%s", task_id, fn.__name__, on_success_status)
                return result
            except Exception as e:
                logger.error("[import:%s] %s failed: %s", task_id, fn.__name__, e)
                return {**state, "status": "failed", "error": f"{error_prefix}: {e}"}
        return wrapper
    return decorator


class ImportState(TypedDict):
    task_id: str                 # 本地任务 id
    file_name: str               # 原始文件名 (例: "iPhone16.pdf")
    file_binary: bytes           # 文件 binary
    item_name: Optional[str]     # 识别出的主体名
    markdown: str                # MinerU 解析的 full.md
    chunks: list[dict]           # chunker 产出
    vectors: list[dict]          # embedder 产出
    status: str                  # uploaded/extracting/recognizing/chunking/embedding/storing/done/failed
    error: Optional[str]         # 失败原因
    # 配置透传
    mineru_base_url: str
    mineru_token: str
    openai_api_key: str
    openai_base_url: str
    openai_model: str


def create_initial_import_state(
    task_id: str,
    file_name: str,
    file_binary: bytes,
    mineru_base_url: str,
    mineru_token: str,
    openai_api_key: str,
    openai_base_url: str,
    openai_model: str,
) -> ImportState:
    """构造初始 ImportState (所有产出字段置空, status=uploaded).

    集中 state schema 知识于 services 层, 避免 router 感知字段细节.
    """
    return {
        "task_id": task_id,
        "file_name": file_name,
        "file_binary": file_binary,
        "item_name": None,
        "markdown": "",
        "chunks": [],
        "vectors": [],
        "status": "uploaded",
        "error": None,
        "mineru_base_url": mineru_base_url,
        "mineru_token": mineru_token,
        "openai_api_key": openai_api_key,
        "openai_base_url": openai_base_url,
        "openai_model": openai_model,
    }


def _fail_fast_edge(next_node: str):
    """构造条件边路由函数: 失败 → END, 否则 → next_node.

    每个节点出边复用此函数, 以 next_node 闭包区分后继.
    节点内仍保留 status=="failed" 守卫作为防御性深度 (直接测节点/异常路径).
    """
    def _route(state: ImportState):
        if state.get("status") == "failed":
            return END
        return next_node
    return _route


def build_import_graph():
    """构造 LangGraph 状态机 (条件边 fail-fast)."""
    graph = StateGraph(ImportState)
    graph.add_node("extract", _node_extract)
    graph.add_node("recognize_item", _node_recognize)
    graph.add_node("chunk", _node_chunk)
    graph.add_node("embed", _node_embed)
    graph.add_node("store", _node_store)

    graph.add_edge(START, "extract")
    graph.add_conditional_edges(
        "extract",
        _fail_fast_edge("recognize_item"),
        {"recognize_item": "recognize_item", END: END},
    )
    graph.add_conditional_edges(
        "recognize_item",
        _fail_fast_edge("chunk"),
        {"chunk": "chunk", END: END},
    )
    graph.add_conditional_edges(
        "chunk",
        _fail_fast_edge("embed"),
        {"embed": "embed", END: END},
    )
    graph.add_conditional_edges(
        "embed",
        _fail_fast_edge("store"),
        {"store": "store", END: END},
    )
    graph.add_edge("store", END)
    return graph.compile()


@node_handler(on_success_status="extracting", error_prefix="extract")
def _node_extract(state: ImportState) -> dict:
    md = extract_markdown(
        base_url=state["mineru_base_url"],
        token=state["mineru_token"],
        file_name=state["file_name"],
        file_binary=state["file_binary"],
    )
    # 校验 MinerU 输出质量
    if not md or not md.strip():
        raise ValueError("MinerU 返回空内容")
    return {"markdown": md}


@node_handler(on_success_status="recognizing", error_prefix="recognize")
def _node_recognize(state: ImportState) -> dict:
    settings = Settings(
        openai_api_key=state["openai_api_key"],
        openai_base_url=state["openai_base_url"],
        openai_model=state["openai_model"],
    )
    llm = build_recognizer(settings)
    item = recognize_item(state.get("markdown", ""), llm=llm, settings=settings)
    return {"item_name": item}


@node_handler(on_success_status="chunking", error_prefix="chunk")
def _node_chunk(state: ImportState) -> dict:
    chunks = chunk_by_section(
        state.get("markdown", ""),
        item_name=state.get("item_name"),
    )
    return {"chunks": chunks}


@node_handler(on_success_status="embedding", error_prefix="embed")
def _node_embed(state: ImportState) -> dict:
    vectors = embed_chunks(state.get("chunks", []))
    return {"vectors": vectors}


@node_handler(on_success_status="done", error_prefix="store")
def _node_store(state: ImportState) -> dict:
    vectors = state.get("vectors", [])
    # 透传 file_name 作为 doc_name
    doc_name = state.get("file_name", "")
    enriched = [{**v, "doc_name": doc_name} for v in vectors]
    bulk_upsert(enriched)
    return {}
