"""检索融合算法: RRF 倒数排名融合 + 辅助工具."""
from __future__ import annotations

from typing import Any


def rrf_fuse(
    lists: list[list[dict[str, Any]]],
    k: int = 60,
    top_k: int | None = None,
) -> list[dict[str, Any]]:
    """RRF 倒数排名融合.

    Args:
        lists: 多个有序列表, 每个元素是 dict 且至少含 "id" 字段
        k: RRF 常数, 越小高分越极化 (常用 60)
        top_k: 返回前 K 个

    Returns:
        合并后的列表, 按 rrf_score 降序, 每个元素新增 "rrf_score" 字段
    """
    if not lists:
        return []

    scores: dict[str, float] = {}
    data: dict[str, dict[str, Any]] = {}

    for lst in lists:
        for rank, doc in enumerate(lst):
            doc_id = doc.get("id")
            if doc_id is None:
                continue
            # RRF: score = Σ 1/(k + rank), rank 0-indexed
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
            data[doc_id] = doc

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    if top_k:
        ranked = ranked[:top_k]

    result: list[dict[str, Any]] = []
    for doc_id, score in ranked:
        item = dict(data[doc_id])
        item["rrf_score"] = score
        result.append(item)
    return result
