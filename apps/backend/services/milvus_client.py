"""Milvus 操作 wrapper."""
from __future__ import annotations


def bulk_upsert(vectors: list[dict]) -> None:
    """批量写入 Milvus.

    现在占位实现; 后续替换为 pymilvus。
    """
    if not vectors:
        return
    # TODO: pymilvus 实现
