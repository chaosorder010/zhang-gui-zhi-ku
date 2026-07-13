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
import os

# 必须在导入 transformers/FlagEmbedding 之前设置离线模式
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

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

    优先级:
    1. 本地路径 /models/bge-m3 (Docker 挂载或开发环境)
    2. HuggingFace BAAI/bge-m3 (自动下载)
    3. 失败回落 _MockEmbedder, 避免 import 期即崩溃.
    """
    try:
        from FlagEmbedding import BGEM3FlagModel

        # 优先使用本地挂载的模型
        local_path = os.environ.get("BGE_MODEL_PATH", "/models/bge-m3")
        if os.path.isdir(local_path) and os.path.exists(os.path.join(local_path, "config.json")):
            model = BGEM3FlagModel(local_path, use_fp16=False)
            logger.info("BGE-M3 model loaded from local path: %s", local_path)
        else:
            use_fp16 = True  # fp16 加速; CPU 上也能工作
            model = BGEM3FlagModel("BAAI/bge-m3", use_fp16=use_fp16)
            logger.info("BGE-M3 model loaded (BAAI/bge-m3, fp16=%s)", use_fp16)
        return model
    except Exception as exc:  # ImportError / RuntimeError / OSError
        logger.warning(
            "BGE-M3 not available (%s); using _MockEmbedder fallback", exc
        )
        return _MockEmbedder()


def embed_chunks(chunks: list[dict], batch_size: int = 32) -> list[dict]:
    """给每个 chunk 生成 dense + sparse 向量, 返回 vectors dict.

    输入 chunk dict 至少需要 ``text`` 字段.
    输出在原有 key 基础上追加:

    - ``dense_vector``  — list[float], len == 1024
    - ``sparse_vector`` — dict[int, float], 非空

    batch_size 控制一次送入模型的 chunk 数, 避免大文件 OOM.
    """
    if not chunks:
        return []

    model = _load_embedder()
    results: list[dict] = []

    # 分批编码, 避免一次全量送入 OOM
    for batch_start in range(0, len(chunks), batch_size):
        batch = chunks[batch_start : batch_start + batch_size]
        texts = [c["text"] for c in batch]
        output = model.encode(
            texts,
            return_dense=True,
            return_sparse=True,
            return_colbert_vecs=False,
            max_length=512,
        )

        dense = output["dense_vecs"]
        sparse = output["lexical_weights"]
        for i, chunk in enumerate(batch):
            dense_vec = dense[i].tolist() if hasattr(dense[i], "tolist") else list(dense[i])
            sparse_vec = {
                int(k): float(v) for k, v in sparse[i].items()
            }
            results.append({**chunk, "dense_vector": dense_vec, "sparse_vector": sparse_vec})

    return results
