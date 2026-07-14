"""导入工作流: LangGraph 编排 PDF → Milvus 入库.

节点:
  1. extract         — 调 MinerU 申请URL→上传→轮询→下载→解压→读 full.md
  2. recognize_item  — LLM 抽主体名
  3. chunk            — 按标题分块 + item_name 拼头
  4. embed            — BGE-M3 生成稠密+稀疏向量
  5. store            — Milvus 入库 + MongoDB 元数据
"""
from __future__ import annotations

from typing import Optional, TypedDict

from langgraph.graph import StateGraph, START, END

from apps.backend.services.mineru_client import extract_markdown
from apps.backend.services.recognizer import recognize_item, build_recognizer
from apps.backend.services.chunker import chunk_by_section
from apps.backend.services.embedder import embed_chunks
from apps.backend.services.milvus_client import bulk_upsert
from apps.backend.core.config import Settings


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


def _node_extract(state: ImportState) -> ImportState:
    try:
        md = extract_markdown(
            base_url=state["mineru_base_url"],
            token=state["mineru_token"],
            file_name=state["file_name"],
            file_binary=state["file_binary"],
        )
        # 校验 MinerU 输出质量
        if not md or not md.strip():
            return {**state, "status": "failed", "error": "extract: MinerU 返回空内容"}
        if "##" not in md:
            return {**state, "status": "failed", "error": "extract: 无二级标题，无法分块"}
        return {**state, "markdown": md, "status": "extracting"}
    except Exception as e:
        return {**state, "status": "failed", "error": f"extract: {e}"}


def _node_recognize(state: ImportState) -> ImportState:
    if state.get("status") == "failed":
        return state
    try:
        settings = Settings(
            openai_api_key=state["openai_api_key"],
            openai_base_url=state["openai_base_url"],
            openai_model=state["openai_model"],
        )
        llm = build_recognizer(settings)
        item = recognize_item(state.get("markdown", ""), llm=llm, settings=settings)
        return {**state, "item_name": item, "status": "recognizing"}
    except Exception as e:
        return {**state, "status": "failed", "error": f"recognize: {e}"}


def _node_chunk(state: ImportState) -> ImportState:
    if state.get("status") == "failed":
        return state
    try:
        chunks = chunk_by_section(
            state.get("markdown", ""),
            item_name=state.get("item_name"),
        )
        return {**state, "chunks": chunks, "status": "chunking"}
    except Exception as e:
        return {**state, "status": "failed", "error": f"chunk: {e}"}


def _node_embed(state: ImportState) -> ImportState:
    if state.get("status") == "failed":
        return state
    try:
        vectors = embed_chunks(state.get("chunks", []))
        return {**state, "vectors": vectors, "status": "embedding"}
    except Exception as e:
        return {**state, "status": "failed", "error": f"embed: {e}"}


def _node_store(state: ImportState) -> ImportState:
    if state.get("status") == "failed":
        return state
    try:
        vectors = state.get("vectors", [])
        # 透传 file_name 作为 doc_name
        doc_name = state.get("file_name", "")
        enriched = [{**v, "doc_name": doc_name} for v in vectors]
        bulk_upsert(enriched)
        return {**state, "status": "done"}
    except Exception as e:
        return {**state, "status": "failed", "error": f"store: {e}"}
