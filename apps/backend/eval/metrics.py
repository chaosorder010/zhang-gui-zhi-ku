"""纯指标函数: Recall@K 和 MRR@K.

设计为无副作用纯函数 — 方便独立测试, 不依赖 Milvus / embedder。
输入是 hybrid_search 返回的 hits 列表 (每项至少含 "text" 字段) +
一个 relevant_texts 集合 (ground-truth 全文)。
匹配采用 substring 包含: hit["text"] == relevant 或 relevant in hit["text"]。
"""
from __future__ import annotations


def _is_relevant(hit_text: str, relevant_texts: set[str]) -> bool:
    """判断一条 hit 是否命中 ground-truth."""
    for gold in relevant_texts:
        if gold and (gold == hit_text or gold in hit_text or hit_text in gold):
            return True
    return False


def recall_at_k(hits: list[dict], relevant_texts: set[str], k: int) -> float:
    """Per-query Recall@K: top-K 命中的 ground-truth 比例.

    若 relevant_texts 为空 → 0.0 (无正确答案可召回)。
    单 ground-truth 时退化为二值: 命中 → 1.0, 未命中 → 0.0。
    """
    if not relevant_texts or not hits:
        return 0.0

    top_k = hits[:k]
    hit_texts = {h.get("text", "") for h in top_k}

    matched = 0
    for gold in relevant_texts:
        for ht in hit_texts:
            if gold == ht or gold in ht or ht in gold:
                matched += 1
                break
    return matched / len(relevant_texts)


def mrr_at_k(hits: list[dict], relevant_texts: set[str], k: int) -> float:
    """Per-query MRR@K: top-K 中首个命中倒数的均值.

    仅看 top-K 内第一次命中的排名, 1-indexed。未命中 → 0.0。
    """
    if not relevant_texts or not hits:
        return 0.0

    for rank, hit in enumerate(hits[:k], start=1):
        if _is_relevant(hit.get("text", ""), relevant_texts):
            return 1.0 / rank
    return 0.0
