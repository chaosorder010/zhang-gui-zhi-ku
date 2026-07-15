"""单元测试: LLM-based Rerank 精排.

Seam: reranker.rerank_chunks, mock LLM 返回 JSON 分数。
验证: 按分数降序重排, 异常时退回原始 Milvus 顺序。
"""
from __future__ import annotations

from unittest.mock import MagicMock
import pytest
from langchain_core.messages import AIMessage

from apps.backend.services.reranker import rerank_chunks


@pytest.mark.unit
class TestRerankReorder:
    """RED → GIVEN: mock LLM 返回分数, 断言输出顺序按分数降序."""

    def test_reorders_chunks_by_score_descending(self):
        """LLM 给 chunk-2 最高分, chunk-1 最低分 → 输出顺序应反转."""
        chunks = [
            {"text": "chunk-A-about-cats", "item_name": "", "score": 0.9},
            {"text": "chunk-B-about-dogs", "item_name": "", "score": 0.8},
            {"text": "chunk-C-about-birds", "item_name": "", "score": 0.7},
        ]

        # Mock LLM: 按 idx 给分 (chunk-1=2, chunk-2=5, chunk-3=3)
        llm = MagicMock()
        llm.invoke.return_value = AIMessage(
            content='[{"idx":1,"score":2,"reason":"low"},'
                    '{"idx":2,"score":5,"reason":"high"},'
                    '{"idx":3,"score":3,"reason":"mid"}]'
        )

        out = rerank_chunks(chunks, "用户问题", llm)

        # 按分数降序: chunk-2 (5) → chunk-3 (3) → chunk-1 (2)
        assert [c["text"] for c in out] == [
            "chunk-B-about-dogs",
            "chunk-C-about-birds",
            "chunk-A-about-cats",
        ]

    def test_output_length_equals_input(self):
        """重排后不丢 chunk."""
        chunks = [
            {"text": "a", "item_name": "", "score": 0.5},
            {"text": "b", "item_name": "", "score": 0.4},
        ]
        llm = MagicMock()
        llm.invoke.return_value = AIMessage(
            content='[{"idx":1,"score":1,"reason":"x"},{"idx":2,"score":4,"reason":"y"}]'
        )

        out = rerank_chunks(chunks, "q", llm)

        assert len(out) == 2
        assert {c["text"] for c in out} == {"a", "b"}

    def test_empty_chunks_returns_empty(self):
        llm = MagicMock()
        out = rerank_chunks([], "q", llm)
        assert out == []
        llm.invoke.assert_not_called()


@pytest.mark.unit
class TestRerankGuardrail:
    """护栏: LLM 抛异常/超时 → 退回原始 Milvus 顺序, 不丢 chunk."""

    def test_llm_exception_falls_back_to_original_order(self):
        """LLM 抛异常 → 输出与输入顺序一致."""
        chunks = [
            {"text": "first", "item_name": "", "score": 0.9},
            {"text": "second", "item_name": "", "score": 0.8},
            {"text": "third", "item_name": "", "score": 0.7},
        ]
        llm = MagicMock()
        llm.invoke.side_effect = RuntimeError("LLM unavailable")

        out = rerank_chunks(chunks, "user q", llm)

        assert [c["text"] for c in out] == ["first", "second", "third"]
        assert len(out) == 3

    def test_llm_unparseable_response_falls_back(self):
        """LLM 返回非 JSON → 退回原始顺序."""
        chunks = [
            {"text": "x", "item_name": "", "score": 0.5},
            {"text": "y", "item_name": "", "score": 0.4},
        ]
        llm = MagicMock()
        llm.invoke.return_value = AIMessage(content="not-json-at-all")

        out = rerank_chunks(chunks, "q", llm)
        assert [c["text"] for c in out] == ["x", "y"]

    def test_returns_new_list_not_mutating_input(self):
        """不修改原始列表."""
        chunks = [
            {"text": "a", "item_name": "", "score": 0.5},
            {"text": "b", "item_name": "", "score": 0.4},
        ]
        llm = MagicMock()
        llm.invoke.side_effect = RuntimeError("fail")

        out = rerank_chunks(chunks, "q", llm)

        assert out is not chunks  # new list
        assert chunks[0]["text"] == "a"  # original intact
