"""单元测试: Graph RAG 三节点编排 (recognize → retrieve → chatbot).

Seam: graph 层, mock 掉 LLM / embedder / milvus (外部边界)。
验证节点顺序、state 传递、条件边路由。
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest
from langchain_core.messages import HumanMessage, AIMessage

from apps.backend.services.graph import build_graph, RagState


@pytest.mark.unit
class TestRagState:
    def test_state_has_expected_keys(self):
        """RagState TypedDict 应包含 messages / item_name / retrieved_chunks."""
        state: RagState = {
            "messages": [HumanMessage(content="q")],
            "item_name": None,
            "retrieved_chunks": [],
        }
        assert "messages" in state
        assert "item_name" in state
        assert "retrieved_chunks" in state


@pytest.mark.unit
class TestGraphRagOrchestration:
    def _make_graph(self, llm_response: str = "answer"):
        """构造 graph 并注入 mock embed_fn / search_fn."""
        llm = MagicMock()
        llm.invoke.return_value = AIMessage(content=llm_response)

        def embed_fn(query: str):
            return {
                "dense_vector": [0.1] * 1024,
                "sparse_vector": {0: 1.0},
            }

        def search_fn(dense, sparse, item_name):
            return [
                {"text": "chunk-1", "item_name": "iPhone 16 Pro", "score": 0.9},
                {"text": "chunk-2", "item_name": "iPhone 16 Pro", "score": 0.8},
            ]

        return build_graph(llm=llm, embed_fn=embed_fn, search_fn=search_fn), llm

    def test_full_pipeline_with_results(self, fake_llm):
        """正常流程: recognize → retrieve → chatbot, 返回带上下文的回答."""
        graph, llm = self._make_graph("iPhone 16 Pro 支持 USB-C 充电.")
        config = {"configurable": {"thread_id": "rag-t1"}}

        # mock recognize_item 返回已知产品名
        with patch("apps.backend.services.graph.recognize_item", return_value="iPhone 16 Pro"):
            result = graph.invoke(
                {"messages": [HumanMessage(content="iPhone 16 Pro 充电口是什么?")]},
                config=config,
            )

        assert result["item_name"] == "iPhone 16 Pro"
        assert len(result["retrieved_chunks"]) == 2
        assert result["messages"][-1].content == "iPhone 16 Pro 支持 USB-C 充电."
        # chatbot 的 prompt 应包含检索到的 chunk
        called_messages = llm.invoke.call_args[0][0]
        prompt_text = " ".join(
            getattr(m, "content", "") for m in called_messages
        )
        assert "chunk-1" in prompt_text
        assert "chunk-2" in prompt_text

    def test_empty_results_returns_no_info_message(self):
        """retrieve 返回空 → 条件边走 END, 返回无信息消息."""
        llm = MagicMock()
        llm.invoke.return_value = AIMessage(content="should not reach")

        def embed_fn(query: str):
            return {"dense_vector": [0.0] * 1024, "sparse_vector": {}}

        def search_fn(dense, sparse, item_name):
            return []  # 空结果

        graph = build_graph(llm=llm, embed_fn=embed_fn, search_fn=search_fn)
        config = {"configurable": {"thread_id": "rag-empty"}}

        with patch("apps.backend.services.graph.recognize_item", return_value="Unknown Device"):
            result = graph.invoke(
                {"messages": [HumanMessage(content="不存在的设备")]},
                config=config,
            )

        assert result["retrieved_chunks"] == []
        # 最终答案应包含"知识库"提示无信息
        assert "知识库" in result["messages"][-1].content
        # LLM 不应被调用 (走的是条件边, 不是 chatbot 节点)
        llm.invoke.assert_not_called()

    def test_recognize_failure_falls_back_to_no_filter(self):
        """recognize 失败 (返回 '未知') → 全量检索 (item_name=None)."""
        llm = MagicMock()
        llm.invoke.return_value = AIMessage(content="generic answer")

        search_calls = []

        def embed_fn(query: str):
            return {"dense_vector": [0.1] * 1024, "sparse_vector": {0: 1.0}}

        def search_fn(dense, sparse, item_name):
            search_calls.append(item_name)
            return [{"text": "generic", "item_name": "", "score": 0.5}]

        graph = build_graph(llm=llm, embed_fn=embed_fn, search_fn=search_fn)
        config = {"configurable": {"thread_id": "rag-fallback"}}

        with patch("apps.backend.services.graph.recognize_item", return_value="未知"):
            result = graph.invoke(
                {"messages": [HumanMessage(content="something")]},
                config=config,
            )

        # "未知" 被转换为 None, 表示全量检索
        assert result["item_name"] is None
        # search_fn 应以 item_name=None 调用 (全量检索)
        assert search_calls == [None]
        assert len(result["retrieved_chunks"]) == 1

    def test_retrieved_chunks_are_passed_to_chatbot_prompt(self):
        """验证 chatbot 节点收到的 prompt 包含所有 chunk 的编号列表."""
        graph, llm = self._make_graph("answer")
        config = {"configurable": {"thread_id": "rag-prompt"}}

        with patch("apps.backend.services.graph.recognize_item", return_value="DeviceX"):
            graph.invoke(
                {"messages": [HumanMessage(content="what is it?")]},
                config=config,
            )

        called_messages = llm.invoke.call_args[0][0]
        prompt = " ".join(getattr(m, "content", "") for m in called_messages)
        # prompt 应包含编号 (1) (2)
        assert "1" in prompt
        assert "2" in prompt
        # 应包含用户问题
        assert "what is it?" in prompt


@pytest.mark.unit
class TestGraphRagEndpoint:
    """集成测试: /api/ask 端到端走真实 graph (mock embed + search + LLM)."""

    def _build_test_graph(self, llm_response="answer", chunks=None):
        """构造使用 mock 依赖的 graph."""
        llm = MagicMock()
        llm.invoke.return_value = AIMessage(content=llm_response)

        def embed_fn(query: str):
            return {"dense_vector": [0.1] * 1024, "sparse_vector": {0: 1.0}}

        def search_fn(dense, sparse, item_name):
            return chunks or []

        return llm, build_graph(llm=llm, embed_fn=embed_fn, search_fn=search_fn)

    def test_ask_endpoint_returns_answer(self, client):
        """POST /api/ask 应返回 RAG graph 生成的 answer."""
        chunks = [{"text": "iPhone 16 Pro 重量 199 克", "item_name": "iPhone 16 Pro", "score": 0.95}]
        llm, test_graph = self._build_test_graph("根据知识库, iPhone 16 Pro 重量 199 克.", chunks)

        # patch app_graph 在 router 模块的引用 (ask.py 里 from ... import app_graph 已绑定)
        with patch("apps.backend.routers.ask.app_graph", test_graph), patch(
            "apps.backend.services.graph.recognize_item", return_value="iPhone 16 Pro"
        ):
            resp = client.post(
                "/api/ask",
                json={"question": "iPhone 16 Pro 多重?", "session_id": "sess-1"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["answer"] == "根据知识库, iPhone 16 Pro 重量 199 克."
        assert data["session_id"] == "sess-1"

    def test_ask_endpoint_no_results(self, client):
        """知识库无匹配 → 返回 '知识库' 提示无信息."""
        llm, test_graph = self._build_test_graph(chunks=[])

        with patch("apps.backend.routers.ask.app_graph", test_graph), patch(
            "apps.backend.services.graph.recognize_item", return_value="未知"
        ):
            resp = client.post(
                "/api/ask",
                json={"question": "完全不相关的问题", "session_id": "sess-2"},
            )

        assert resp.status_code == 200
        assert "知识库" in resp.json()["answer"]
        # LLM 不应被调用
        llm.invoke.assert_not_called()
