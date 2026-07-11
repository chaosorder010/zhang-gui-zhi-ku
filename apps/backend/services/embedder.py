"""嵌入生成: BGE-M3 稠密+稀疏向量.

公开接口:
    embed_chunks(chunks: list[dict]) -> list[dict]
        — 批量接口, 给每个 chunk 补上 dense_vector + sparse_vector.
    _load_embedder()
        — 单例加载真实模型; 无 GPU/无 FlagEmbedding 时回落 _MockEmbedder.
    _MockEmbedder
        — 无依赖 fallback, 输出 0 稠密 + 单 token 稀疏.
"""
from __future__ import annotations

import logging

import numpy as np

logger = logging.getLogger(__name__)


class _MockEmbedder:
    """无 FlagEmbedding / 无 GPU 时的占位实现.

    输出全 0 稠密向量 (float32, dim=1024) 和单 token 稀疏向量,
    让端到端流程无需 GPU 也能跑通.
    """

    DIM = 1024

    def encode(
        self,
        sentences: list[str],
        *,
        return_dense: bool = True,
        return_sparse: bool = True,
        return_colbert_vecs: bool = False,
        max_length: int | None = None,
        batch_size: int | None = None,
        **kwargs,
    ) -> dict:
        n = len(sentences)
        result: dict = {}
        if return_dense:
            result["dense_vecs"] = np.zeros((n, self.DIM), dtype=np.float32)
        if return_sparse:
            # 至少一个非零 entry 表示稀疏向量 "非空"
            result["lexical_weights"] = [{0: 1.0} for _ in range(n)]
        if return_colbert_vecs:
            result["colbert_vecs"] = []
        return result


def _load_embedder():
    """单例加载 BGEM3FlagModel (真实模型).

    失败回落 _MockEmbedder, 避免 import 期即崩溃.
    真实部署时需 `pip install FlagEmbedding torch`.
    """
    try:
        from FlagEmbedding import BGEM3FlagModel

        use_fp16 = True  # fp16 加速; CPU 上也能工作
        model = BGEM3FlagModel("BAAI/bge-m3", use_fp16=use_fp16)
        logger.info("BGE-M3 model loaded (BAAI/bge-m3, fp16=%s)", use_fp16)
        return model
    except Exception as exc:  # ImportError / RuntimeError / OSError
        logger.warning(
            "BGE-M3 not available (%s); using _MockEmbedder fallback", exc
        )
        return _MockEmbedder()


def embed_chunks(chunks: list[dict]) -> list[dict]:
    """给每个 chunk 生成 dense + sparse 向量, 返回 vectors dict.

    输入 chunk dict 至少需要 ``text`` 字段.
    输出在原有 key 基础上追加:

    - ``dense_vector``  — list[float], len == 1024
    - ``sparse_vector`` — dict[int, float], 非空
    """
    if not chunks:
        return []

    texts = [c["text"] for c in chunks]
    model = _load_embedder()
    output = model.encode(
        texts,
        return_dense=True,
        return_sparse=True,
        return_colbert_vecs=False,
        max_length=512,
    )

    dense = output["dense_vecs"]
    sparse = output["lexical_weights"]
    results: list[dict] = []
    for i, chunk in enumerate(chunks):
        dense_vec = dense[i].tolist() if hasattr(dense[i], "tolist") else list(dense[i])
        sparse_vec = {
            int(k): float(v) for k, v in sparse[i].items()
        }
        results.append({**chunk, "dense_vector": dense_vec, "sparse_vector": sparse_vec})
    return results
