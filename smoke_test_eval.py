"""Smoke test: 验证评估框架在 mock Milvus 下能跑通并产出样例报告。

mock 策略:
  - milvus_client.hybrid_search 由 MagicMock 替换, 按关键词返回预设 golden hit
  - embed_chunks 由 fake 替换, 无需 FlagEmbedding / GPU / 真实 Milvus

运行: python smoke_test_eval.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Fake embedder: 关键词 → dense[slot] 非零 (确定性, 不走 FlagEmbedding)
# ---------------------------------------------------------------------------
def _fake_embed(chunks: list[dict]) -> list[dict]:
    out: list[dict] = []
    for c in chunks:
        text = c.get("text", "")
        dense = [0.0] * 1024
        sparse: dict[int, float] = {}
        # tech_spec 类: 扭矩 → slot 0
        if "扭矩" in text:
            dense[0] = 0.9
            sparse[100] = 1.0
        # error_code 类: E01 → slot 1
        elif "E01" in text:
            dense[1] = 0.8
            sparse[200] = 1.0
        # item_specific 类: 充电口 → slot 2
        elif "充电口" in text:
            dense[2] = 0.85
            sparse[300] = 1.0
        # generic_context 类: USB-C → slot 3
        elif "USB-C" in text:
            dense[3] = 0.75
            sparse[400] = 1.0
        out.append({**c, "dense_vector": dense, "sparse_vector": sparse})
    return out


# ---------------------------------------------------------------------------
# Mock milvus: 按 query_dense 的 slot 返回对应 golden hit
# ---------------------------------------------------------------------------
GOLDEN = {
    "扭矩": {"text": "iPhone 16 Pro 底部螺丝扭矩规格", "item_name": "iPhone16Pro", "score": 0.92},
    "E01": {"text": "故障码 E01: 电源适配器异常, 请更换充电器", "item_name": "iPhone16", "score": 0.88},
    "充电口": {"text": "iPhone 16 Pro 充电口类型 USB-C", "item_name": "iPhone16Pro", "score": 0.85},
    "USB-C": {"text": "USB-C 与 Lightning 接口区别", "item_name": None, "score": 0.80},
}


def _make_mock_milvus() -> MagicMock:
    mock = MagicMock()

    def _hybrid_search(query_dense, query_sparse=None, item_name=None, limit=10):
        if query_dense:
            if query_dense[0] > 0.5:
                return [GOLDEN["扭矩"]] + [{"text": f"noise-{i}", "item_name": "x", "score": 0.1} for i in range(limit - 1)]
            if query_dense[1] > 0.5:
                return [GOLDEN["E01"]]
            if query_dense[2] > 0.5:
                return [GOLDEN["充电口"]]
            if query_dense[3] > 0.5:
                return [GOLDEN["USB-C"]]
        return []

    mock.hybrid_search.side_effect = _hybrid_search
    return mock


# ---------------------------------------------------------------------------
# 4 类 query 各一条 (覆盖全部 type)
# ---------------------------------------------------------------------------
SMOKE_QUERIES: list[dict] = [
    {"query_id": "smoke_ts", "type": "tech_spec", "question": "iPhone 16 Pro 底部螺丝扭矩规格是多少", "item_name": "iPhone16Pro", "relevant_texts": ["iPhone 16 Pro 底部螺丝扭矩规格"]},
    {"query_id": "smoke_ec", "type": "error_code", "question": "故障码 E01 怎么处理", "item_name": "iPhone16", "relevant_texts": ["故障码 E01: 电源适配器异常, 请更换充电器"]},
    {"query_id": "smoke_is", "type": "item_specific", "question": "iPhone 16 Pro 的充电口类型", "item_name": "iPhone16Pro", "relevant_texts": ["iPhone 16 Pro 充电口类型 USB-C"]},
    {"query_id": "smoke_gc", "type": "generic_context", "question": "USB-C 和 Lightning 接口有什么区别", "item_name": None, "relevant_texts": ["USB-C 与 Lightning 接口区别"]},
]


def main() -> None:
    print("=" * 72)
    print("  Smoke Test — RAG 检索评估框架 (mock Milvus)")
    print("=" * 72)
    print()

    mock_milvus = _make_mock_milvus()

    from apps.backend.eval.evaluate import evaluate_all, build_report, render_table

    with patch("apps.backend.eval.evaluate.embed_chunks", side_effect=_fake_embed):
        results = evaluate_all(SMOKE_QUERIES, milvus_module=mock_milvus)

    print(f"evaluate_all → {len(results)} 条结果")
    for r in results:
        print(f"  [{r['query_id']}] recall@5={r['recall@5']:.1f}  mrr@5={r['mrr@5']:.3f}")

    report = build_report(results)
    table = render_table(report)
    print(table)

    # 写出样例报告
    out_path = Path(__file__).resolve().parent / "smoke_report.json"
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"样例报告 → {out_path}")

    # 断言所有 golden 都被召回 (否则 smoke test 失败)
    failures = [r for r in results if r["recall@5"] < 1.0]
    if failures:
        print(f"\n❌ {len(failures)} 条 query 未通过 smoke test:")
        for r in failures:
            print(f"   - {r['query_id']}: recall@5={r['recall@5']}")
        sys.exit(1)

    print("✅ 全部 4 类 query golden hit 在 top-5 召回, smoke test 通过.")
    return None


if __name__ == "__main__":
    main()
