"""共享 pytest fixture."""
from __future__ import annotations

from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient

from apps.backend.main import create_app


@pytest.fixture
def fake_llm():
    """构造一个可调用的 fake llm, 接受 messages, 返回固定 AIMessage."""
    from langchain_core.messages import AIMessage

    def _make(response: str = "fake response"):
        llm = MagicMock()
        llm.invoke.return_value = AIMessage(content=response)
        return llm

    return _make


@pytest.fixture(autouse=True)
def _force_test_env(monkeypatch):
    """所有测试强制设置 env, 避免真实 key 依赖; 清掉 lru_cache 让 get_settings() 重新读."""
    import apps.backend.core.config as cfg
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.com/v1")
    cfg.get_settings.cache_clear()


@pytest.fixture
def client():
    """FastAPI TestClient, env 已由 _force_test_env 设置."""
    return TestClient(create_app())
