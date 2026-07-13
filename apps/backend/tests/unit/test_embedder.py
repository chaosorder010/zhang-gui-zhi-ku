"""单元测试: embedder BGE-M3 接入 / 维度正确性 / 稀疏向量.

Unit tests mock the external dependency (FlagEmbedding's BGEM3FlagModel),
producing ms-level execution.
"""
from __future__ import annotations

import numpy as np
import pytest

from apps.backend.services import embedder


class _MockBgeM3:
    """Mock BGE-M3-like model returning deterministic vectors."""

    def __init__(self, dense_dim: int = 1024, sparse_size: int = 4):
        self.dense_dim = dense_dim
        self.sparse_size = sparse_size

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
            vecs = np.zeros((n, self.dense_dim), dtype=np.float32)
            for i in range(n):
                vecs[i, i % self.dense_dim] = float(i + 1)
            result["dense_vecs"] = vecs
        if return_sparse:
            result["lexical_weights"] = [
                {
                    (i * 10 + j): float(i + 1) * (j + 1) * 0.1
                    for j in range(self.sparse_size)
                }
                for i in range(n)
            ]
        return result


@pytest.fixture
def mock_m3():
    """构造一个 mock M3 模型实例."""
    return _MockBgeM3()


@pytest.fixture(autouse=True)
def _force_mock_embedder(mock_m3, monkeypatch):
    """所有 embedder 测试强制使用 mock 模型, 不加载 FlagEmbedding."""
    def _load_mock():
        return mock_m3

    monkeypatch.setattr(embedder, "_load_embedder", _load_mock)


@pytest.mark.unit
class TestEmbedChunks:
    """embed_chunks 核心功能."""

    def test_dense_vector_dim_is_1024(self, mock_m3):
        chunks = [{"text": "iPhone 16 发布"}]
        out = embedder.embed_chunks(chunks)
        assert len(out[0]["dense_vector"]) == mock_m3.dense_dim == 1024

    def test_sparse_vector_is_non_empty_dict(self, mock_m3):
        chunks = [{"text": "iPhone 16 摄像头升级"}]
        out = embedder.embed_chunks(chunks)
        sparse = out[0]["sparse_vector"]
        assert isinstance(sparse, dict)
        assert len(sparse) > 0
        # 所有 key 是 int, val 是 float
        for k, v in sparse.items():
            assert isinstance(k, int)
            assert isinstance(v, float)

    def test_preserves_original_fields(self, mock_m3):
        chunks = [{"text": "hello", "item_name": "iPhone", "doc_name": "phone.pdf"}]
        out = embedder.embed_chunks(chunks)
        assert out[0]["text"] == "hello"
        assert out[0]["item_name"] == "iPhone"
        assert out[0]["doc_name"] == "phone.pdf"

    def test_empty_input_returns_empty(self, mock_m3):
        assert embedder.embed_chunks([]) == []

    def test_batch_output_length_matches_input(self, mock_m3):
        texts = [f"chunk-{i}" for i in range(5)]
        chunks = [{"text": t} for t in texts]
        out = embedder.embed_chunks(chunks)
        assert len(out) == 5

    def test_dense_vector_values_are_float(self, mock_m3):
        chunks = [{"text": "test"}]
        out = embedder.embed_chunks(chunks)
        for v in out[0]["dense_vector"]:
            assert isinstance(v, float)

    def test_passes_max_length_to_model(self, mock_m3, monkeypatch):
        """验证 encode 调用时传入 max_length 参数."""
        calls: list[dict] = []
        origin = mock_m3.encode

        def spy_encode(sentences, **kwargs):
            calls.append(kwargs)
            return origin(sentences, **kwargs)

        monkeypatch.setattr(mock_m3, "encode", spy_encode)
        embedder.embed_chunks([{"text": "test"}])
        assert len(calls) == 1
        assert calls[0]["max_length"] == 512

    def test_large_batch_splits_by_batch_size(self, mock_m3, monkeypatch):
        """大量 chunk 时按批次编码，避免一次全量送入 OOM."""
        calls: list[list] = []
        origin = mock_m3.encode

        def spy_encode(sentences, **kwargs):
            calls.append(list(sentences))
            return origin(sentences, **kwargs)

        monkeypatch.setattr(mock_m3, "encode", spy_encode)
        # 10 chunks, batch_size=4 → 应分 3 次调用 (4,4,2)
        chunks = [{"text": f"c{i}"} for i in range(10)]
        out = embedder.embed_chunks(chunks, batch_size=4)
        assert len(calls) == 3
        assert len(calls[0]) == 4
        assert len(calls[1]) == 4
        assert len(calls[2]) == 2
        assert len(out) == 10  # 输出数量不变

    def test_batch_size_default_32(self, mock_m3, monkeypatch):
        """默认 batch_size=32，小批量只调一次 encode."""
        calls: list[list] = []
        origin = mock_m3.encode

        def spy_encode(sentences, **kwargs):
            calls.append(list(sentences))
            return origin(sentences, **kwargs)

        monkeypatch.setattr(mock_m3, "encode", spy_encode)
        chunks = [{"text": f"c{i}"} for i in range(5)]
        embedder.embed_chunks(chunks)  # 5 < 32 → 1 次
        assert len(calls) == 1


@pytest.mark.unit
class TestMockEmbedderFallback:
    """无 FlagEmbedding / GPU 时 fallback 到 mock 模式."""

    def test_mock_embedder_output_dims(self):
        m = embedder._MockEmbedder()
        out = m.encode(["hi", "world"], return_dense=True, return_sparse=True)
        assert out["dense_vecs"].shape == (2, 1024)
        assert len(out["lexical_weights"]) == 2
        assert all(isinstance(d, dict) and len(d) > 0 for d in out["lexical_weights"])

    def test_mock_embedder_returns_float32_dense(self):
        m = embedder._MockEmbedder()
        out = m.encode(["x"])
        assert out["dense_vecs"].dtype == np.float32

    def test_mock_embedder_respects_return_flags(self):
        m = embedder._MockEmbedder()
        out = m.encode(["x"], return_dense=False)
        assert "dense_vecs" not in out
        assert "lexical_weights" in out
