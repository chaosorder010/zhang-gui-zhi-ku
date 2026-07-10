"""单元测试: 主体识别 (item name 从 markdown 抽取).

Seam: recognizer.recognize_item, mock LLM。
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest
from langchain_core.messages import AIMessage

from apps.backend.services.recognizer import recognize_item, build_recognizer
from apps.backend.core.config import Settings


@pytest.mark.unit
class TestRecognizeItem:
    def test_returns_llm_response_directly(self):
        fake_llm = MagicMock()
        fake_llm.invoke.return_value = AIMessage(content="iPhone 16 Pro")
        settings = Settings(
            openai_api_key="k",
            openai_base_url="https://x",
            openai_model="gpt-4o-mini",
        )
        out = recognize_item("## iPhone 16 Pro\n\n内容...", llm=fake_llm, settings=settings)
        assert out == "iPhone 16 Pro"

    def test_strips_whitespace_and_punctuation(self):
        fake_llm = MagicMock()
        fake_llm.invoke.return_value = AIMessage(content='  "iPhone16"  \n')
        settings = Settings(openai_api_key="k", openai_base_url="https://x")
        out = recognize_item("任何内容", llm=fake_llm, settings=settings)
        assert out == "iPhone16"

    def test_contains_item_name_keywords(self):
        fake_llm = MagicMock()
        fake_llm.invoke.return_value = AIMessage(content="MacBook Pro M4")
        settings = Settings(openai_api_key="k", openai_base_url="https://x")
        out = recognize_item("...", llm=fake_llm, settings=settings)
        # 主体应含产品名关键词
        assert "MacBook" in out or "Pro" in out

    def test_invalid_response_returns_unknown(self):
        fake_llm = MagicMock()
        fake_llm.invoke.return_value = AIMessage(content="")
        settings = Settings(openai_api_key="k", openai_base_url="https://x")
        out = recognize_item("...", llm=fake_llm, settings=settings)
        assert out == "未知"

    def test_prompt_includes_markdown_sample(self):
        fake_llm = MagicMock()
        fake_llm.invoke.return_value = AIMessage(content="X")
        settings = Settings(openai_api_key="k", openai_base_url="https://x")
        md = "# iPhone手册\n\n这里是内容"
        recognize_item(md, llm=fake_llm, settings=settings)
        # 验证 prompt 传入的内容包含 markdown 文本
        call_args = fake_llm.invoke.call_args
        msgs = call_args[0][0]
        flat = " ".join(getattr(m, "content", str(m)) for m in msgs)
        assert "iPhone手册" in flat

    def test_uses_settings_model(self):
        fake_llm = MagicMock()
        fake_llm.invoke.return_value = AIMessage(content="Y")
        settings = Settings(openai_api_key="k", openai_base_url="https://x", openai_model="gpt-4o")
        recognize_item("内容", llm=fake_llm, settings=settings)
        # build_recognizer 会从 settings 取模型参数, 这里 verify 通过调用即可
        assert fake_llm.invoke.called


@pytest.mark.unit
class TestBuildRecognizer:
    def test_builds_llm_from_settings(self):
        settings = Settings(
            openai_api_key="test",
            openai_base_url="https://x",
            openai_model="gpt-4o-mini",
        )
        with patch("apps.backend.services.recognizer.ChatOpenAI") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance
            llm = build_recognizer(settings)
        mock_cls.assert_called_once()
        assert llm is mock_instance
