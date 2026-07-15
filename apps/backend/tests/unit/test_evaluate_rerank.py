"""单元测试: evaluate.py 的 rerank_fn 注入扩展.

Seam: evaluate_all 的 rerank_fn 参数, mock milvus + rerank_fn.
验证: 传入 rerank_fn 时, 计算指标前会用它重排 hits.
"""
from __future__ import annotations

from unittest.mock import MagicMock
import pytest

from apps.backend.eval.evaluate import evaluate_all


@pytest.mark.unit
class TestEvaluateRerankFn:
    def _mock_milvus(self, hits):
        m = MagicMock()
        m.hybrid_search.return_value = hits
        return m

    def test_rerank_fn_reorders_hits_before_scoring(self):
        """rerank_fn 把 relevant 文本从 rank2 提到 rank1 → MRR@5 应提升."""
        hits = [
            {"text": "unused-chunk-about-cats", "item_name": "", "score": 0.9},
            {"text": "EXACT answer to question", "item_name": "", "score": 0.8},
            {"text": "another-off-topic", "item_name": "", "score": 0.7},
        ]
        milvus = self._mock_milvus(hits)

        # rerank_fn: 把含 "EXACT" 的文本提到最前
        def rerank_fn(hits, question):
            return sorted(hits, key=lambda h: "EXACT" not in h.get("text", ""))

        queries = [{
            "query_id": "q1",
            "type": "tech_spec",
            "question": "test",
            "item_name": None,
            "relevant_texts": ["EXACT answer to question"],
        }]

        # baseline (无 rerank)
        baseline = evaluate_all(queries, milvus_module=milvus)
        # with rerank
        reranked = evaluate_all(queries, milvus_module=milvus, rerank_fn=rerank_fn)

        # baseline: relevant 在 rank2 → MRR@5 = 0.5
        assert baseline[0]["mrr@5"] == 0.5
        # rerank 后 relevant 提到 rank1 → MRR@5 = 1.0
        assert reranked[0]["mrr@5"] == 1.0
        # recall@5 不变 (都在 top5)
        assert baseline[0]["recall@5"] == reranked[0]["recall@5"] == 1.0

    def test_no_rerank_fn_keeps_original_order(self):
        """不传 rerank_fn 时, 行为与改动前一致."""
        hits = [
            {"text": "a", "item_name": "", "score": 0.9},
            {"text": "b", "item_name": "", "score": 0.8},
        ]
        milvus = self._mock_milvus(hits)
        queries = [{
            "query_id": "q1",
            "type": "tech_spec",
            "question": "test",
            "item_name": None,
            "relevant_texts": ["b"],
        }]

        results = evaluate_all(queries, milvus_module=milvus)
        # relevant "b" 在 rank2 → MRR@5 = 0.5
        assert results[0]["mrr@5"] == 0.5

    def test_rerank_fn_exception_does_not_crash_evaluate(self):
        """rerank_fn 抛异常时, evaluate_all 应传播异常 (由 rerank_chunks 内部兜底).

        这里验证: 如果 rerank_fn 本身抛异常, evaluate_all 不吞掉.
        """
        hits = [{"text": "a", "item_name": "", "score": 0.9}]
        milvus = self._mock_milvus(hits)

        def bad_rerank_fn(hits, question):
            raise RuntimeError("LLM down")

        queries = [{
            "query_id": "q1",
            "type": "tech_spec",
            "question": "test",
            "item_name": None,
            "relevant_texts": ["a"],
        }]

        with pytest.raises(RuntimeError, match="LLM down"):
            evaluate_all(queries, milvus_module=milvus, rerank_fn=bad_rerank_fn)
