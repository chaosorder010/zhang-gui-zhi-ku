import logging
from typing import Annotated, TypedDict

from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

from apps.backend.core.config import get_settings
from apps.backend.services.llm import build_llm
from apps.backend.services.recognizer import recognize_item
from apps.backend.services.embedder import embed_chunks
from apps.backend.services.milvus_client import hybrid_search
from apps.backend.services.reranker import rerank_chunks
from apps.backend.services.retriever import rrf_fuse

logger = logging.getLogger(__name__)

# 检索无结果时的回退回答
_NO_INFO_MESSAGE = "知识库中暂无相关信息, 请换一个问题或联系客服."


class RagState(TypedDict):
    """RAG graph 的 state schema.

    fields:
        messages: 对话消息列表 (带 add_messages reducer 实现多轮累积)
        item_name: 识别出的产品主体名, None 表示未识别 (全量检索)
        retrieved_chunks: Milvus 检索结果列表
    """
    messages: Annotated[list[BaseMessage], add_messages]
    item_name: str | None
    retrieved_chunks: list[dict]


def build_graph(
    llm=None,
    embed_fn=None,
    search_fn=None,
    enable_hyde: bool | None = None,
    enable_rerank: bool | None = None,
):
    """构造 LangGraph 编排: recognize → [hyde | retrieve] → [rerank] → chatbot.

    两个开关独立控制, 关闭时图结构字节级不变.

    Args:
        llm: LLM 实例, 默认 build_llm(); 可注入 mock 用于测试
        embed_fn: (query_str) -> {dense_vector, sparse_vector}, 默认 embed_chunks
        search_fn: (dense, sparse, item_name) -> list[dict], 默认 hybrid_search
        enable_hyde: 是否启用 HyDE 节点. None 时读取 settings.enable_hyde.
            True 时插入 hyde 节点 (recognize→hyde, 跳过 retrieve);
            False 时走原始 retrieve 路径.
        enable_rerank: 是否启用 rerank 精排, 默认取 settings.enable_rerank.
            True 时在检索后插入 rerank 节点;
            False 时图结构不变.

    Returns:
        编译后的 LangGraph (带 MemorySaver checkpointer)
    """
    if llm is None:
        llm = build_llm()
    if embed_fn is None:
        embed_fn = _default_embed
    if search_fn is None:
        search_fn = hybrid_search
    if enable_hyde is None:
        enable_hyde = get_settings().enable_hyde
    if enable_rerank is None:
        enable_rerank = get_settings().enable_rerank

    memory = MemorySaver()

    # ── Node 1: 主体识别 ──
    def recognize(state: RagState):
        """从用户最新问题识别产品名, 写入 state["item_name"]."""
        last_human = _last_human_message(state["messages"])
        if last_human is None:
            return {"item_name": None}
        item = recognize_item(last_human, llm)
        result_item = item if item != "未知" else None
        logger.info("[rag] recognize item_name=%s", result_item)
        return {"item_name": result_item}

    # ── Node 2: 检索 ──
    def retrieve(state: RagState):
        """对用户问题做 embedding + Milvus hybrid search."""
        last_human = _last_human_message(state["messages"])
        if last_human is None:
            return {"retrieved_chunks": []}
        # embed_fn 接收原始 query text
        vec = embed_fn(last_human)
        # search_fn 接口: (dense, sparse, item_name) -> list[dict]
        # 真实 hybrid_search 使用位置参数, mock 也兼容位置参数调用
        chunks = search_fn(
            vec["dense_vector"],
            vec["sparse_vector"],
            state["item_name"],
        )
        logger.info("[rag] retrieve hits=%d item_name=%s", len(chunks), state["item_name"])
        return {"retrieved_chunks": chunks}

    # ── Node 2b: HyDE 检索 (enable_hyde=True 时启用) ──
    def hyde(state: RagState):
        """HyDE: LLM 生成假设答案 → embed → hybrid_search → RRF 融合."""
        last_q = _last_human_message(state["messages"])
        if last_q is None:
            return {"retrieved_chunks": []}
        # 1. LLM 生成假设答案
        prompt = get_settings().hyde_prompt_template.format(question=last_q)
        hypothetical = llm.invoke(prompt).content.strip()

        # 2. embed 假设答案 + 原始 query
        hyp_vec = embed_fn(hypothetical)
        orig_vec = embed_fn(last_q)

        # 3. 双路 hybrid_search
        hyp_hits = search_fn(
            hyp_vec["dense_vector"], hyp_vec["sparse_vector"], state.get("item_name")
        )
        orig_hits = search_fn(
            orig_vec["dense_vector"], orig_vec["sparse_vector"], state.get("item_name")
        )

        # 4. 护栏: HyDE 命中 0 退回原始
        if not hyp_hits:
            return {"retrieved_chunks": orig_hits}

        # 5. RRF 融合
        fused = rrf_fuse([orig_hits, hyp_hits])
        return {"retrieved_chunks": fused}

    # ── Node 3: 生成回答 ──
    def chatbot(state: RagState):
        """基于检索 chunks 构建 prompt, 调用 LLM 生成回答."""
        context = _format_context(state["retrieved_chunks"])
        user_question = _last_human_message(state["messages"]) or ""

        system_prompt = (
            "你是一个电子产品知识库助手. 请根据以下参考资料回答用户问题.\n"
            "要求:\n"
            "1. 仅基于参考资料回答, 不要编造信息.\n"
            "2. 简洁直接, 不要解释来源.\n\n"
            f"参考资料:\n{context}\n\n"
            f"用户问题: {user_question}"
        )

        # 构建完整消息列表 (system + history)
        messages = [AIMessage(content=system_prompt)] + list(state["messages"])
        response = llm.invoke(messages)
        logger.info("[rag] chatbot generated answer (len=%d)", len(response.content))
        return {"messages": [response]}

    # ── 条件边: 空结果 → 直接返回无信息消息 ──
    def route_after_retrieve(state: RagState):
        if not state["retrieved_chunks"]:
            logger.info("[rag] route → no_results (empty hits)")
            return "no_results"
        if enable_rerank:
            return "rerank"
        return "chatbot"

    # ── 空结果节点 ──
    def no_results(state: RagState):
        return {"messages": [AIMessage(content=_NO_INFO_MESSAGE)]}

    # ── Rerank 节点 (开关行为, enable_rerank=false 时不加入图) ──
    def rerank(state: RagState):
        """LLM 精排: 对 retrieved_chunks 按相关性重排序.

        护栏: rerank_chunks 内部已处理异常, 失败时退回原始 Milvus 顺序.
        """
        last_human = _last_human_message(state["messages"])
        if last_human is None:
            return {}
        reranked = rerank_chunks(state["retrieved_chunks"], last_human, llm)
        logger.info("[rag] rerank reordered %d chunks", len(reranked))
        return {"retrieved_chunks": reranked}

    # ── 构建图 ──
    graph = StateGraph(RagState)
    graph.add_node("recognize", recognize)
    graph.add_node("retrieve", retrieve)
    graph.add_node("chatbot", chatbot)
    graph.add_node("no_results", no_results)

    # 条件节点
    if enable_hyde:
        graph.add_node("hyde", hyde)
    if enable_rerank:
        graph.add_node("rerank", rerank)

    graph.add_edge(START, "recognize")

    # recognize → hyde 或 retrieve
    if enable_hyde:
        graph.add_edge("recognize", "hyde")
    else:
        graph.add_edge("recognize", "retrieve")

    # 检索后路由 (从 hyde 或 retrieve 出发)
    post_retrieve_node = "hyde" if enable_hyde else "retrieve"
    retrieve_paths = {"no_results": "no_results", "chatbot": "chatbot"}
    if enable_rerank:
        retrieve_paths["rerank"] = "rerank"
    graph.add_conditional_edges(
        post_retrieve_node,
        route_after_retrieve,
        retrieve_paths,
    )

    graph.add_edge("no_results", END)
    graph.add_edge("chatbot", END)

    if enable_rerank:
        graph.add_edge("rerank", "chatbot")

    return graph.compile(checkpointer=memory)


# ── helpers ──

def _last_human_message(messages: list[BaseMessage]) -> str | None:
    """取最近一条 HumanMessage 的 content, 用于识别 / 检索."""
    for m in reversed(messages):
        if isinstance(m, HumanMessage):
            return m.content
    return None


def _format_context(chunks: list[dict]) -> str:
    """把 chunk 列表拼成编号上下文文本."""
    if not chunks:
        return "(无参考资料)"
    lines = []
    for i, c in enumerate(chunks, 1):
        text = c.get("text", "").strip()
        if text:
            lines.append(f"[{i}] {text}")
    return "\n".join(lines) if lines else "(无参考资料)"


def _default_embed(query: str) -> dict:
    """默认 embed: 把 query 当单 chunk, 用真实 embedder 生成向量."""
    vec = embed_chunks([{"text": query}])
    return vec[0] if vec else {"dense_vector": [0.0] * 1024, "sparse_vector": {}}


app_graph = build_graph()
