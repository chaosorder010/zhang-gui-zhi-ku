"""集成测试: 真实 PDF 数据端到端导入.

验证修复后的 chunker (level-1 fallback) + milvus_client (sparse vector 格式)
能正确处理 temp_data 的真实 MinerU markdown.

使用真实 Milvus 实例 (需本地运行), 不做 mock.
运行前确保 Milvus 可连接: localhost:19530
"""
from __future__ import annotations

import os
import pytest

from apps.backend.services.chunker import chunk_by_section
from apps.backend.services.embedder import embed_chunks
from apps.backend.services import milvus_client

# 真实 markdown 文件 (MinerU 提取)
REAL_MD = "/home/leon/projects/-RAG-/knowledge/temp_data/20260608/6bcaf5f5/HUAWEI MateStation S 12代酷睿版 用户指南-(PUC,Windows11_02,zh-cn).md"

# 跳过条件: 文件不存在 or Milvus 不可达
@pytest.mark.integration
class TestRealPdfDataImport:
    """验证真实 PDF 数据的 chunk → embed → store 链路."""

    @pytest.fixture(autouse=True)
    def _check_prerequisites(self):
        """前提条件: 文件存在 + Milvus 可连接."""
        if not os.path.exists(REAL_MD):
            pytest.skip(f"测试数据不存在: {REAL_MD}")
        try:
            client = milvus_client._get_client()
            # 简单 ping - 确认连接
            assert client is not None
        except Exception as e:
            pytest.skip(f"Milvus 不可达: {e}")
        yield

    def test_real_markdown_chunks_correctly(self):
        """MinerU markdown (全 # 标题) 修复后应产出多块, 非单块."""
        md = open(REAL_MD, encoding="utf-8").read()
        chunks = chunk_by_section(md, item_name="HUAWEI MateStation S", max_chars=800)

        # 修复前: 1 chunk (退化解), 修复后: 30+ chunks
        assert len(chunks) >= 10, f"应产出多块, 实际 {len(chunks)}"
        # 每块应有 item_name tag
        for c in chunks:
            assert c["text"].startswith("[HUAWEI MateStation S]")
            assert len(c["text"]) <= 900  # max_chars + tag 容忍
        # chunk_id 应递增
        ids = [c["chunk_id"] for c in chunks]
        assert ids == list(range(len(ids)))

    def test_real_markdown_embed_and_store(self):
        """完整链路: chunk → embed → Milvus, 验证 flush 后可检索."""
        md = open(REAL_MD, encoding="utf-8").read()
        chunks = chunk_by_section(md, item_name="HUAWEI MateStation S", max_chars=800)
        vectors = embed_chunks(chunks)
        enriched = [{**v, "doc_name": "test_e2e_huawei.pdf"} for v in vectors]

        # 存储
        milvus_client.bulk_upsert(enriched)
        milvus_client._get_client().flush(milvus_client._collection_name())

        # 验证: 按 item_name 检索
        client = milvus_client._get_client()
        name = milvus_client._collection_name()
        results = client.query(
            name,
            filter='item_name == "HUAWEI MateStation S" && doc_name == "test_e2e_huawei.pdf"',
            limit=5,
            output_fields=["text", "item_name"],
        )
        assert len(results) >= 1, "应能从 Milvus 检索到导入的数据"
        assert "HUAWEI MateStation S" in results[0].get("text", "")

    def test_hybrid_search_on_real_data(self):
        """hybrid_search 在真实导入数据上应返回结果."""
        md = open(REAL_MD, encoding="utf-8").read()
        chunks = chunk_by_section(md, item_name="HUAWEI MateStation S", max_chars=800)
        vectors = embed_chunks(chunks)
        enriched = [{**v, "doc_name": "test_e2e_search.pdf"} for v in vectors]
        milvus_client.bulk_upsert(enriched)
        milvus_client._get_client().flush(milvus_client._collection_name())

        # 嵌入一个查询
        q_vectors = embed_chunks([{"text": "如何开启和关闭计算机"}])
        dense = q_vectors[0]["dense_vector"]
        sparse = q_vectors[0]["sparse_vector"]

        results = milvus_client.hybrid_search(
            query_dense=dense,
            query_sparse=sparse,
            item_name="HUAWEI MateStation S",
            limit=3,
        )
        # mock embedder 下分数相同, 但应返回结果
        assert len(results) >= 1, "hybrid_search 应返回至少 1 条结果"
