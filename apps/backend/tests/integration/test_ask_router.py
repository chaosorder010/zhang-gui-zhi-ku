"""集成测试: /api/ask router.

Seam: 公共 HTTP 接口, mock 掉 graph 层 (外部边界)。
"""
from __future__ import annotations

from unittest.mock import patch, MagicMock
import pytest
from langchain_core.messages import AIMessage


@pytest.mark.integration
class TestAskRouter:
    def test_ask_returns_answer_and_session_id(self, client):
        """mock graph 必须返回真实 AIMessage(content=str), 否则 AskResponse 验证失败."""
        fake_ai = AIMessage(content="this is a test answer")
        fake_result = {"messages": [AIMessage(content="unused"), fake_ai]}

        with patch("apps.backend.routers.ask.app_graph") as mock_graph:
            mock_graph.invoke.return_value = fake_result

            resp = client.post(
                "/api/ask",
                json={"question": "什么是RAG", "session_id": "sess-1"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["answer"] == "this is a test answer"
        assert data["session_id"] == "sess-1"

    def test_ask_passes_thread_id_from_session_id(self, client):
        with patch("apps.backend.routers.ask.app_graph") as mock_graph:
            mock_graph.invoke.return_value = {
                "messages": [AIMessage(content="ok")]
            }

            client.post(
                "/api/ask",
                json={"question": "q", "session_id": "my-thread"},
            )

        call_args = mock_graph.invoke.call_args
        cfg = call_args[1]["config"]
        assert cfg["configurable"]["thread_id"] == "my-thread"

    def test_ask_without_session_id_uses_default(self, client):
        with patch("apps.backend.routers.ask.app_graph") as mock_graph:
            mock_graph.invoke.return_value = {
                "messages": [AIMessage(content="ok")]
            }

            client.post("/api/ask", json={"question": "q"})

        call_args = mock_graph.invoke.call_args
        cfg = call_args[1]["config"]
        assert cfg["configurable"]["thread_id"] == "default"

    def test_ask_rejects_empty_question(self, client):
        with patch("apps.backend.routers.ask.app_graph"):
            resp = client.post(
                "/api/ask",
                json={"question": "", "session_id": "x"},
            )

        assert resp.status_code == 422

    def test_ask_400_when_no_api_key(self, client):
        """LLM 未配置返回 400. 直接 mock get_settings 返回空 key."""
        from apps.backend.core.config import Settings
        fake_s = Settings(openai_api_key="", openai_base_url="https://x")
        with patch("apps.backend.routers.ask.app_graph"), \
             patch("apps.backend.routers.ask.get_settings", return_value=fake_s):
            resp = client.post(
                "/api/ask",
                json={"question": "hi", "session_id": "x"},
            )
        assert resp.status_code == 400
