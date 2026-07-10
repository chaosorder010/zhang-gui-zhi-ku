"""单元测试: RRF 倒数排名融合.

Seam: retriever.rrf_fuse, 纯函数。
"""
from __future__ import annotations

import pytest
from apps.backend.services.retriever import rrf_fuse


@pytest.mark.unit
class TestRRFFuse:
    def test_single_list_returns_sorted(self):
        lst = [{"id": "a", "text": "x"}, {"id": "b", "text": "y"}]
        out = rrf_fuse([lst])
        assert [d["id"] for d in out] == ["a", "b"]

    def test_union_of_multiple_lists(self):
        # b 在两个列表都出现, a 只在一个列表出现 → b 分数最高
        l1 = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
        l2 = [{"id": "b"}, {"id": "d"}]
        out = rrf_fuse([l1, l2])
        ids = [d["id"] for d in out]
        assert set(ids) == {"a", "b", "c", "d"}
        assert ids[0] == "b"
        # a/c/d 只在一列表出现, 分数低于 b
        assert out[0]["rrf_score"] > out[1]["rrf_score"]

    def test_k_parameter_controls_score_decay(self):
        # a 在 l1 排 rank0, b 在 l1 排 rank10 (高分 vs 低分)
        l1 = [{"id": "a"}] + [{"id": f"x{i}"} for i in range(10)] + [{"id": "b"}]
        out_low_k = rrf_fuse([l1], k=1)
        out_high_k = rrf_fuse([l1], k=100)
        # 低 k 时, 第一名与第十一名的分数差更大
        a_low = next(d["rrf_score"] for d in out_low_k if d["id"] == "a")
        b_low = next(d["rrf_score"] for d in out_low_k if d["id"] == "b")
        diff_low = a_low - b_low
        a_high = next(d["rrf_score"] for d in out_high_k if d["id"] == "a")
        b_high = next(d["rrf_score"] for d in out_high_k if d["id"] == "b")
        diff_high = a_high - b_high
        assert diff_low > diff_high > 0

    def test_empty_input_returns_empty(self):
        assert rrf_fuse([]) == []
        assert rrf_fuse([[]]) == []

    def test_preserves_data_fields(self):
        l1 = [{"id": "x", "text": "hello"}]
        out = rrf_fuse([l1])
        assert out[0]["text"] == "hello"
        assert out[0]["id"] == "x"
        assert "rrf_score" in out[0]

    def test_top_k_limits_output(self):
        l1 = [{"id": str(i)} for i in range(10)]
        out = rrf_fuse([l1], top_k=3)
        assert len(out) == 3
