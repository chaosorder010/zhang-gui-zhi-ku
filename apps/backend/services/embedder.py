"""嵌入生成: BGE-M3 稠密+稀疏向量."""
from __future__ import annotations


def embed_chunks(chunks: list[dict]) -> list[dict]:
    """给每个 chunk 生成 dense + sparse 向量, 返回 vectors dict.

    现在占位实现, 返回空 vector; 后续替换为 BGE-M3 推理。
    """
    return [
        {**c, "dense_vector": [], "sparse_vector": {}}
        for c in chunks
    ]
