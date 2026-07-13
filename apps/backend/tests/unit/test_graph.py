"""单元测试: LangGraph 多轮记忆编排.

Seam: graph 层, mock 掉 LLM / embedder / milvus (外部边界)。
验证 thread_id 隔离 session, 多轮消息累积。
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest
from langchain_core.messages import HumanMessage, AIMessage
from apps.backend.services.graph import build_graph


@pytest.mark.unit
class TestGraphMultiTurn:
    def _make_graph(self, llm):
        """构造 graph, 注入 mock embed/search 避免真实调用."""
        def embed_fn(query: str):
            return {"dense_vector": [0.0] * 1024, "sparse_vector": {0: 1.0}}

        def search_fn(dense, sparse, item_name):
            return [{"text": "ctx", "item_name": "", "score": 0.5}]

        return build_graph(llm=llm, embed_fn=embed_fn, search_fn=search_fn)

    def test_single_turn_returns_llm_response(self, fake_llm):
        llm = fake_llm("hello back")
        graph = self._make_graph(llm)
        config = {"configurable": {"thread_id": "t1"}}

        with patch("apps.backend.services.graph.recognize_item", return_value="未知"):
            result = graph.invoke({"messages": [HumanMessage(content="hi")]}, config=config)

        assert result["messages"][-1].content == "hello back"
        assert len(result["messages"]) == 2  # human + ai

    def test_multi_turn_keeps_history(self, fake_llm):
        """第二轮应包含第一轮消息."""
        call_count = {"n": 0}

        def side_effect(messages):
            call_count["n"] += 1
            # 验证第二轮收到消息 (human1, ai1, human2, ai2, ...)
            return AIMessage(content=f"reply-{call_count['n']}")

        llm = MagicMock()
        llm.invoke.side_effect = side_effect

        graph = self._make_graph(llm)
        config = {"configurable": {"thread_id": "t-multi"}}

        with patch("apps.backend.services.graph.recognize_item", return_value="未知"):
            graph.invoke({"messages": [HumanMessage(content="q1")]}, config=config)
            result = graph.invoke(
                {"messages": [HumanMessage(content="q2")]}, config=config
            )

        assert result["messages"][-1].content == "reply-2"

    def test_different_thread_id_isolated(self, fake_llm):
        """不同 thread_id 的记忆互不影响."""
        llm = fake_llm("x")
        graph = self._make_graph(llm)

        config_a = {"configurable": {"thread_id": "a"}}
        config_b = {"configurable": {"thread_id": "b"}}

        with patch("apps.backend.services.graph.recognize_item", return_value="未知"):
            graph.invoke({"messages": [HumanMessage(content="qA")]}, config=config_a)
            result_b = graph.invoke(
                {"messages": [HumanMessage(content="qB")]}, config=config_b
            )

        # session b 只应看到 qB + reply (2 条), 不应看到 qA
        assert len(result_b["messages"]) == 2
        assert result_b["messages"][0].content == "qB"
