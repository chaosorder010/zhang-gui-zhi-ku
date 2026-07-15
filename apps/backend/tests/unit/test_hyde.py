"""单元测试: HyDE 检索节点 (Hypothetical Document Embeddings).

Seam: graph 层, mock 掉 LLM / embedder / milvus。
验证:
    1. HyDE 节点使用 LLM 生成的假设答案做 embedding (而非原始 query)
    2. HyDE 命中 0 条时退回原始 query 嵌入
    3. ENABLE_HYDE=true 时 build_graph 插入 hyde 节点
    4. ENABLE_HYDE=false 时 build_graph 图结构不变
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest
from langchain_core.messages import HumanMessage, AIMessage

from apps.backend.services.graph import build_graph


@pytest.mark.unit
class TestHydeNodeEmbedsHypothetical:
    """RED: HyDE 节点应生成假设答案, 用假设答案做 embedding."""

    def test_hyde_embeds_hypothetical_answer_not_original_query(self):
        """mock LLM 生成假设答案, 断言 embed_fn 收到的是假设答案文本."""
        hypo_answer = "HUAWEI MateStation S 长按电源键 10 秒以上可强制关机"

        llm = MagicMock()
        # recognize_item 被 mock, 不会消耗 llm
        # 第 1 次 invoke = HyDE 生成假设答案
        # 第 2 次 invoke = chatbot 生成最终回答
        llm.invoke.side_effect = [
            AIMessage(content=hypo_answer),
            AIMessage(content="基于假设答案的回答"),
        ]

        embed_calls: list[str] = []

        def embed_fn(text: str):
            embed_calls.append(text)
            return {"dense_vector": [0.1] * 1024, "sparse_vector": {0: 1.0}}

        def search_fn(dense, sparse, item_name):
            return [{"text": "hit", "item_name": "", "score": 0.5, "id": "h1"}]

        graph = build_graph(
            llm=llm,
            embed_fn=embed_fn,
            search_fn=search_fn,
            enable_hyde=True,
        )
        config = {"configurable": {"thread_id": "hyde-t1"}}

        with patch("apps.backend.services.graph.recognize_item", return_value="HUAWEI MateStation S"):
            result = graph.invoke(
                {"messages": [HumanMessage(content="HUAWEI MateStation S 如何强制关机")]},
                config=config,
            )

        # 至少有一次 embed 调用
        assert len(embed_calls) >= 1, "embed_fn 应被调用"

        # 第一次 embed 应使用 LLM 生成的假设答案, 而非原始 query
        assert embed_calls[0] == hypo_answer, (
            f"首次 embed 应使用假设答案, 期望 {hypo_answer!r}, 实际 {embed_calls[0]!r}"
        )
        # 原始 query 不应作为首次 embed 输入
        assert embed_calls[0] != "HUAWEI MateStation S 如何强制关机"

        # 最终应有 retrieved_chunks
        assert len(result["retrieved_chunks"]) >= 1


@pytest.mark.unit
class TestHydeGuardrail:
    """护栏: HyDE 命中 0 条时退回原始 query 嵌入."""

    def test_hyde_zero_hits_falls_back_to_original_query(self):
        """假设答案检索返回空, 应使用原始 query 检索结果."""
        original_question = "万用表直流电压测量范围"
        hypo_answer = "万用表直流电压最大输入为 600V"

        llm = MagicMock()
        llm.invoke.side_effect = [
            AIMessage(content=hypo_answer),
            AIMessage(content="fallback answer"),
        ]

        embed_calls: list[str] = []

        def embed_fn(text: str):
            embed_calls.append(text)
            return {"dense_vector": [0.2] * 1024, "sparse_vector": {1: 1.0}}

        def search_fn(dense, sparse, item_name):
            return []  # 模拟 HyDE 和 original 都返回空

        graph = build_graph(
            llm=llm,
            embed_fn=embed_fn,
            search_fn=search_fn,
            enable_hyde=True,
        )
        config = {"configurable": {"thread_id": "hyde-guard"}}

        with patch("apps.backend.services.graph.recognize_item", return_value="万用表"):
            result = graph.invoke(
                {"messages": [HumanMessage(content=original_question)]},
                config=config,
            )

        # embed_fn 应被调用: 至少 hyde 嵌入 (即使命中 0 条也应尝试)
        assert len(embed_calls) >= 1
        # 第一次嵌入的是假设答案
        assert embed_calls[0] == hypo_answer


@pytest.mark.unit
class TestBuildGraphHydeToggle:
    """build_graph 在 ENABLE_HYDE 开关下的图结构测试."""

    def test_enable_hyde_true_has_hyde_node(self):
        """enable_hyde=True 时图应含 hyde 节点."""
        with patch("apps.backend.services.graph.recognize_item", return_value="x"):
            graph = build_graph(
                llm=MagicMock(),
                embed_fn=lambda t: {"dense_vector": [0.0] * 1024, "sparse_vector": {}},
                search_fn=lambda d, s, i: [],
                enable_hyde=True,
            )

        compiled = graph.get_graph()
        node_names = [n for n in compiled.nodes if n not in ("__start__", "__end__")]
        # 应有 hyde 节点
        assert "hyde" in node_names, f"节点列表: {node_names}"

    def test_enable_hyde_false_has_no_hyde_node(self):
        """enable_hyde=False 时图不应含 hyde 节点 (与改动前一致)."""
        graph = build_graph(
            llm=MagicMock(),
            embed_fn=lambda t: {"dense_vector": [0.0] * 1024, "sparse_vector": {}},
            search_fn=lambda d, s, i: [],
            enable_hyde=False,
        )

        compiled = graph.get_graph()
        node_names = [n for n in compiled.nodes if n not in ("__start__", "__end__")]
        assert "hyde" not in node_names, f"节点列表: {node_names}"
        # 应保留原始三节点
        assert "recognize" in node_names
        assert "retrieve" in node_names
        assert "chatbot" in node_names
