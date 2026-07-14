"""RAG 检索评估框架 — 离线计算 hybrid search 的召回指标.

CLI:
    python -m apps.backend.eval.evaluate --limit 30 --output report.json

调用路径与 graph.py retrieve 完全隔离, 直接调 milvus_client.hybrid_search。
embed 走 embedder.embed_chunks, 结果匹配用 substring 近似 chunk 命中。
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import yaml

from apps.backend.services.embedder import embed_chunks
from apps.backend.services import milvus_client

from apps.backend.eval.metrics import recall_at_k, mrr_at_k

# 本模块所在目录, 默认 queries.yaml / README.md 都在这里
EVAL_DIR = Path(__file__).resolve().parent
DEFAULT_QUERIES = EVAL_DIR / "queries.yaml"

# 评估指标 K 值
K_VALUES = (5, 10)


def load_queries(path: Path = DEFAULT_QUERIES) -> list[dict]:
    """加载评估 question 集 (YAML list)."""
    if not path.exists():
        raise FileNotFoundError(f"queries.yaml not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"queries.yaml 顶层应为 list, 得到 {type(data).__name__}")
    return data


def _embed_question(question: str) -> tuple[list[float], dict[int, float]]:
    """把单条 question 文本嵌入为 (dense, sparse)."""
    vectors = embed_chunks([{"text": question}])
    if not vectors:
        return [0.0] * milvus_client.DENSE_DIM, {}
    v = vectors[0]
    dense = v.get("dense_vector", [])
    if hasattr(dense, "tolist"):
        dense = dense.tolist()
    sparse = v.get("sparse_vector", {})
    if hasattr(sparse, "tolist"):
        sparse = {int(k): float(v) for k, v in sparse}
    return list(dense), dict(sparse)


def evaluate_all(
    queries: list[dict],
    milvus_module=milvus_client,
    limit: int = 10,
) -> list[dict]:
    """对每条 query 跑 hybrid search 并计算指标.

    Args:
        queries: load_queries 返回的 query 列表
        milvus_module: 可注入 mock 的 milvus 模块 (真实或 unittest.mock)
        limit: top-K 上限 (至少 max(K_VALUES))
    """
    limit = max(limit, max(K_VALUES))
    results: list[dict] = []

    for q in queries:
        question = q.get("question", "")
        dense, sparse = _embed_question(question)
        hits = milvus_module.hybrid_search(
            query_dense=dense,
            query_sparse=sparse,
            item_name=q.get("item_name"),
            limit=limit,
        )

        relevant = set(q.get("relevant_texts") or [])
        row: dict = {
            "query_id": q.get("query_id", ""),
            "type": q.get("type", ""),
            "question": question,
            "item_name": q.get("item_name"),
        }
        for k in K_VALUES:
            row[f"recall@{k}"] = recall_at_k(hits, relevant, k)
            row[f"mrr@{k}"] = mrr_at_k(hits, relevant, k)
        results.append(row)

    return results


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def group_by_type(results: list[dict]) -> dict[str, dict]:
    """按 query type 分组, 计算各指标均值.

    返回 {type: {count, recall@K, mrr@K, ...}}。
    """
    buckets: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        buckets[r.get("type", "unknown")].append(r)

    metric_keys = [f"recall@{k}" for k in K_VALUES] + [f"mrr@{k}" for k in K_VALUES]
    grouped: dict[str, dict] = {}
    for qtype, rows in buckets.items():
        entry: dict = {"count": len(rows)}
        for key in metric_keys:
            vals = [r.get(key, 0.0) for r in rows]
            entry[key] = round(_mean(vals), 4)
        grouped[qtype] = entry
    return grouped


def build_report(results: list[dict]) -> dict:
    """组装完整报告: overall + by_type + per_query."""
    metric_keys = [f"recall@{k}" for k in K_VALUES] + [f"mrr@{k}" for k in K_VALUES]
    overall: dict = {"count": len(results)}
    for key in metric_keys:
        overall[key] = round(_mean([r.get(key, 0.0) for r in results]), 4)
    return {
        "overall": overall,
        "by_type": group_by_type(results),
        "per_query": results,
    }


# 终端表列顺序 (按 spec 中的分类表)
TYPE_ORDER = ("tech_spec", "error_code", "item_specific", "generic_context")


def render_table(report: dict) -> str:
    """把 report 渲染成终端可读表格."""
    overall = report["overall"]
    by_type = report["by_type"]
    lines: list[str] = []
    lines.append("")
    lines.append("=" * 72)
    lines.append("  RAG 检索评估报告 — Hybrid Search 召回率")
    lines.append("=" * 72)
    header = f"  {'query type':<24} {'N':>4}  " + "  ".join(
        f"{k:>9}" for k in [f"Recall@{K_VALUES[0]}", f"Recall@{K_VALUES[1]}", f"MRR@{K_VALUES[0]}"]
    )
    lines.append(header)
    lines.append("  " + "-" * 68)

    def _row(label: str, entry: dict) -> str:
        return (
            f"  {label:<24} {entry.get('count', 0):>4}  "
            f"{entry.get(f'recall@{K_VALUES[0]}', 0):>9.1%}  "
            f"{entry.get(f'recall@{K_VALUES[1]}', 0):>9.1%}  "
            f"{entry.get(f'mrr@{K_VALUES[0]}', 0):>9.3f}"
        )

    for qtype in TYPE_ORDER:
        if qtype in by_type:
            lines.append(_row(qtype, by_type[qtype]))

    lines.append("  " + "-" * 68)
    lines.append(_row("TOTAL", overall))
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    """CLI 入口."""
    parser = argparse.ArgumentParser(description="RAG 检索评估框架")
    parser.add_argument("--limit", type=int, default=0,
                        help="最多评估多少条 query (默认全部)")
    parser.add_argument("--output", type=str, default=None,
                        help="JSON 报告输出路径, 不传则只打印终端表")
    args = parser.parse_args(argv)

    queries = load_queries()
    if args.limit > 0:
        queries = queries[: args.limit]
    if not queries:
        print("WARNING: no queries to evaluate", file=sys.stderr)
        return

    results = evaluate_all(queries)
    report = build_report(results)
    table = render_table(report)
    print(table)

    if args.output:
        out_path = Path(args.output)
        out_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"report saved → {out_path}")


if __name__ == "__main__":
    main()
