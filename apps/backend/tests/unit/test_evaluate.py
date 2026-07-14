"""元测试: RAG 检索评估框架.

Seam 列表 (与用户约定, 与 spec 一致):
  1. metrics.recall_at_k / mrr_at_k — 纯函数, 已知答案独立计算
  2. evaluate_all — 直接调用 milvus_client.hybrid_search (不在 graph.py retrieve 内)
  3. group_by_type / build_report / render_table — 聚合与输出

mock 策略:
  - milvus_client.hybrid_search 由 mock_milvus 替换, 完全隔离真实 Milvus
  - embed_chunks 由 fake 替换, 无需 FlagEmbedding / GPU
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from apps.backend.tests.conftest import _force_test_env  # noqa: F401  (确保 env)

import pytest


# ---------------------------------------------------------------------------
# 先验常量 (来自 spec, 独立于被测代码)
# ---------------------------------------------------------------------------
GOLDEN_TEXTS = {"iPhone 16 Pro 底部螺丝扭矩规格"}


# ===========================================================================
# Cycle 1: 纯指标公式 (Recall@K / MRR@K)
# ===========================================================================
@pytest.fixture
def five_hits():
    """5 个结果的 fixture: golden text 在第 3 位 (rank=3)."""
    return [
        {"text": "无关 chunk A", "item_name": "iPhone16", "score": 0.9},
        {"text": "无关 chunk B", "item_name": "iPhone16", "score": 0.85},
        {"text": "iPhone 16 Pro 底部螺丝扭矩规格", "item_name": "iPhone16", "score": 0.8},
        {"text": "无关 chunk C", "item_name": "iPhone16", "score": 0.7},
        {"text": "无关 chunk D", "item_name": "iPhone16", "score": 0.6},
    ]


@pytest.mark.unit
class TestRecallAtK:
    def test_recall_at_5_hit(self, five_hits):
        """golden 在 rank 3 ≤ 5 → Recall@5 = 1.0."""
        from apps.backend.eval.metrics import recall_at_k

        assert recall_at_k(five_hits, GOLDEN_TEXTS, 5) == 1.0

    def test_recall_at_2_miss(self, five_hits):
        """golden 在 rank 3 > 2 → Recall@2 = 0.0."""
        from apps.backend.eval.metrics import recall_at_k

        assert recall_at_k(five_hits, GOLDEN_TEXTS, 2) == 0.0

    def test_recall_empty_results(self):
        """空结果集 → 0.0."""
        from apps.backend.eval.metrics import recall_at_k

        assert recall_at_k([], {"anything"}, 5) == 0.0

    def test_recall_empty_relevant(self):
        """relevant 集为空 → 0.0 (无正确答案可召回)."""
        from apps.backend.eval.metrics import recall_at_k

        assert recall_at_k([{"text": "x"}], set(), 5) == 0.0

    def test_recall_exact_boundary_at_k(self):
        """golden 恰好在第 k 位 → 命中 (rank == k)."""
        from apps.backend.eval.metrics import recall_at_k

        hits = [{"text": f"c{i}"} for i in range(5)]
        hits[4] = {"text": "gold"}  # rank 5
        assert recall_at_k(hits, {"gold"}, 5) == 1.0


@pytest.mark.unit
class TestMrrAtK:
    def test_mrr_rank_1(self):
        """golden 在 rank 1 → MRR@5 = 1.0."""
        from apps.backend.eval.metrics import mrr_at_k

        hits = [
            {"text": "iPhone 16 Pro 底部螺丝扭矩规格"},
            {"text": "other"},
        ]
        assert mrr_at_k(hits, GOLDEN_TEXTS, 5) == 1.0

    def test_mrr_rank_3(self, five_hits):
        """golden 在 rank 3 → MRR@5 = 1/3."""
        from apps.backend.eval.metrics import mrr_at_k

        assert mrr_at_k(five_hits, GOLDEN_TEXTS, 5) == pytest.approx(1 / 3)

    def test_mrr_miss(self, five_hits):
        """top-5 无 golden → MRR@5 = 0.0."""
        from apps.backend.eval.metrics import mrr_at_k

        assert mrr_at_k(five_hits, {"不存在的文本"}, 5) == 0.0

    def test_mrr_beyond_k(self, five_hits):
        """golden 在 rank 3, 仅看 top-2 → MRR@2 = 0.0."""
        from apps.backend.eval.metrics import mrr_at_k

        assert mrr_at_k(five_hits, GOLDEN_TEXTS, 2) == 0.0

    def test_mrr_empty(self):
        """空结果 → 0.0."""
        from apps.backend.eval.metrics import mrr_at_k

        assert mrr_at_k([], {"x"}, 5) == 0.0


# ===========================================================================
# Cycle 2: eval pipeline — mock milvus_client.hybrid_search
# ===========================================================================
def _fake_embed(chunks: list[dict]) -> list[dict]:
    """确定性 fake embedding: 匹配 embed_chunks 真实签名 (list[dict] -> list[dict]).

    关键词 → dense[slot] 非零, 使 mock_milvus 能路由到 golden hit。
    """
    out: list[dict] = []
    for c in chunks:
        text = c.get("text", "")
        dense = [0.0] * 1024
        sparse: dict[int, float] = {}
        if "扭矩" in text:
            dense[0] = 0.9
            sparse[100] = 1.0
        elif "E01" in text:
            dense[1] = 0.8
            sparse[200] = 1.0
        out.append({**c, "dense_vector": dense, "sparse_vector": sparse})
    return out


def _make_mock_milvus(golden_map: dict[str, dict]) -> MagicMock:
    """构造 mock milvus 模块.

    golden_map: {keyword: hit_dict}
    hybrid_search 根据 query_dense 决定返回 golden 还是 []。
    """
    mock = MagicMock()

    def _hybrid_search(query_dense, query_sparse, item_name=None, limit=10):
        if query_dense and query_dense[0] > 0.5:
            return [golden_map["扭矩"]] + [
                {"text": f"noise-{i}", "item_name": "x", "score": 0.1} for i in range(limit - 1)
            ]
        if query_dense and query_dense[1] > 0.5:
            return [golden_map["E01"]]
        return []

    mock.hybrid_search.side_effect = _hybrid_search
    return mock


SAMPLE_QUERIES: list[dict] = [
    {
        "query_id": "q001",
        "type": "tech_spec",
        "question": "iPhone 16 Pro 螺丝扭矩是多少",
        "item_name": "iPhone16",
        "relevant_texts": ["iPhone 16 Pro 底部螺丝扭矩规格"],
    },
    {
        "query_id": "q002",
        "type": "error_code",
        "question": "故障码 E01 怎么处理",
        "item_name": "iPhone16",
        "relevant_texts": ["故障码 E01: 电源适配器异常, 请更换充电器"],
    },
]


@pytest.fixture
def mock_milvus():
    golden = {
        "扭矩": {"text": "iPhone 16 Pro 底部螺丝扭矩规格", "item_name": "iPhone16", "score": 0.8},
        "E01": {"text": "故障码 E01: 电源适配器异常, 请更换充电器", "item_name": "iPhone16", "score": 0.9},
    }
    return _make_mock_milvus(golden)


@pytest.mark.unit
class TestEvaluatePipeline:
    def test_evaluate_all_returns_metrics_per_query(self, mock_milvus):
        """evaluate_all 对每条 query 返回 recall 与 mrr."""
        from apps.backend.eval.evaluate import evaluate_all

        with patch("apps.backend.eval.evaluate.embed_chunks", side_effect=_fake_embed):
            results = evaluate_all(SAMPLE_QUERIES, milvus_module=mock_milvus)

        assert len(results) == 2
        assert results[0]["query_id"] == "q001"
        assert "recall@5" in results[0]
        assert "recall@10" in results[0]
        assert "mrr@5" in results[0]

    def test_all_queries_recalled_when_mock_returns_golden(self, mock_milvus):
        """mock 将 golden 排在 rank 1 → Recall@5 / MRR@5 全为 1.0."""
        from apps.backend.eval.evaluate import evaluate_all

        with patch("apps.backend.eval.evaluate.embed_chunks", side_effect=_fake_embed):
            results = evaluate_all(SAMPLE_QUERIES, milvus_module=mock_milvus)

        for r in results:
            assert r["recall@5"] == 1.0, f"{r['query_id']} recall@5 should be 1.0"
            assert r["mrr@5"] == 1.0, f"{r['query_id']} mrr@5 should be 1.0"

    def test_group_by_type_averages(self, mock_milvus):
        """group_by_type 按 query type 分桶并计算均值."""
        from apps.backend.eval.evaluate import evaluate_all, group_by_type

        with patch("apps.backend.eval.evaluate.embed_chunks", side_effect=_fake_embed):
            results = evaluate_all(SAMPLE_QUERIES, milvus_module=mock_milvus)
            grouped = group_by_type(results)

        assert "tech_spec" in grouped
        assert "error_code" in grouped
        assert grouped["tech_spec"]["count"] == 1
        assert grouped["tech_spec"]["recall@5"] == 1.0

    def test_build_report_has_overall_and_by_type(self, mock_milvus):
        """report 同时包含 overall 汇总与 by_type 分组."""
        from apps.backend.eval.evaluate import evaluate_all, build_report

        with patch("apps.backend.eval.evaluate.embed_chunks", side_effect=_fake_embed):
            results = evaluate_all(SAMPLE_QUERIES, milvus_module=mock_milvus)
            report = build_report(results)

        assert "overall" in report
        assert "by_type" in report
        assert "per_query" in report
        assert report["overall"]["recall@5"] == 1.0

    def test_render_table_contains_types(self, mock_milvus):
        """render_table 终端输出中出现 query type 名称."""
        from apps.backend.eval.evaluate import evaluate_all, build_report, render_table

        with patch("apps.backend.eval.evaluate.embed_chunks", side_effect=_fake_embed):
            results = evaluate_all(SAMPLE_QUERIES, milvus_module=mock_milvus)
            report = build_report(results)
            table = render_table(report)

        assert "tech_spec" in table
        assert "error_code" in table


@pytest.mark.unit
class TestCLI:
    def test_main_runs_pipeline_when_evaluate_all_mocked(self, tmp_path, capsys):
        """main(): mock 底层 → 打印表 + 写 JSON."""
        from apps.backend.eval import evaluate as evaluate_mod

        report_path = tmp_path / "report.json"
        # 直接 mock evaluate_all 解析结果, 隔离 milvus/embed
        fake_results = [
            {"query_id": "q001", "type": "tech_spec", "question": "扭矩",
             "recall@5": 1.0, "recall@10": 1.0, "mrr@5": 1.0},
            {"query_id": "q002", "type": "error_code", "question": "E01",
             "recall@5": 0.0, "recall@10": 1.0, "mrr@5": 0.0},
        ]
        with patch.object(evaluate_mod, "load_queries", return_value=SAMPLE_QUERIES), \
             patch.object(evaluate_mod, "evaluate_all", return_value=fake_results):
            evaluate_mod.main(["--output", str(report_path)])

        out = capsys.readouterr().out
        assert "tech_spec" in out
        assert report_path.exists()
        data = json.loads(report_path.read_text(encoding="utf-8"))
        assert data["overall"]["recall@5"] == pytest.approx(0.5)
