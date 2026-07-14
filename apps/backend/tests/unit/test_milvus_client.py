"""单元测试: Milvus 客户端 (pymilvus 3.0 MilvusClient API).

Seam: milvus_client 模块, mock 掉 pymilvus.MilvusClient。
覆盖: ensure_collection schema、bulk_upsert 参数构造、hybrid_search 带/不带 item_name 过滤、空输入处理。
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest


@pytest.fixture
def mock_client():
    """构造 mock MilvusClient, 所有方法返回自身或可控值."""
    client = MagicMock()
    client.has_collection.return_value = False
    return client


@pytest.fixture(autouse=True)
def patch_client(mock_client):
    """patch milvus_client 模块的 _client 实例."""
    with patch("apps.backend.services.milvus_client._client", mock_client):
        yield mock_client


@pytest.mark.unit
class TestEnsureCollection:
    def test_creates_schema_when_not_exists(self, mock_client):
        """collection 不存在时应创建 schema + 索引."""
        from apps.backend.services import milvus_client as mod

        mod._client = mock_client
        mock_client.has_collection.return_value = False

        mod.ensure_collection()

        mock_client.create_collection.assert_called_once()
        mock_client.create_index.assert_called()

    def test_skips_when_exists(self, mock_client):
        """collection 已存在时跳过创建."""
        from apps.backend.services import milvus_client as mod

        mod._client = mock_client
        mock_client.has_collection.return_value = True

        mod.ensure_collection()

        mock_client.create_collection.assert_not_called()

    def test_loads_collection_after_create(self, mock_client):
        """创建 collection 后应 load 到内存, 否则 search 报 not loaded."""
        from apps.backend.services import milvus_client as mod

        mod._client = mock_client
        mock_client.has_collection.return_value = False

        mod.ensure_collection()

        mock_client.create_collection.assert_called_once()
        mock_client.create_index.assert_called()
        mock_client.load_collection.assert_called_once()


@pytest.mark.unit
class TestBulkUpsert:
    def test_inserts_rows(self, mock_client):
        """bulk_upsert 应调用 insert 并传入行数据."""
        from apps.backend.services import milvus_client as mod

        mod._client = mock_client
        vectors = [
            {
                "text": "chunk1",
                "item_name": "iPhone16",
                "doc_name": "iphone.pdf",
                "chunk_id": 0,
                "dense_vector": [0.1] * 1024,
                "sparse_vector": {1: 0.5, 2: 0.3},
            },
            {
                "text": "chunk2",
                "item_name": "iPhone16",
                "doc_name": "iphone.pdf",
                "chunk_id": 1,
                "dense_vector": [0.2] * 1024,
                "sparse_vector": {3: 0.7},
            },
        ]

        mod.bulk_upsert(vectors)

        mock_client.insert.assert_called_once()
        call_args = mock_client.insert.call_args
        assert call_args[0][0] == "zgzk"  # collection name
        rows = call_args[0][1]
        assert len(rows) == 2
        assert rows[0]["text"] == "chunk1"
        assert rows[0]["item_name"] == "iPhone16"
        assert len(rows[0]["dense_vector"]) == 1024

    def test_empty_list_noop(self, mock_client):
        """空列表不调用 insert."""
        from apps.backend.services import milvus_client as mod

        mod._client = mock_client

        mod.bulk_upsert([])

        mock_client.insert.assert_not_called()

    def test_sparse_vector_not_wrapped_in_list(self, mock_client):
        """sparse_vector 应为 {idx: val} dict, 不是 [{idx: val}] 列表.

        Bug: _to_sparse_payload 之前错误地将 dict 包装成 list,
        导致 Milvus insert() 报 'invalid input for sparse float vector'.
        """
        from apps.backend.services import milvus_client as mod

        mod._client = mock_client
        vectors = [
            {
                "text": "chunk1",
                "item_name": "Device",
                "doc_name": "doc.pdf",
                "chunk_id": 0,
                "dense_vector": [0.1] * 1024,
                "sparse_vector": {1: 0.5, 99: 0.3},
            },
        ]

        mod.bulk_upsert(vectors)

        mock_client.insert.assert_called_once()
        rows = mock_client.insert.call_args[0][1]
        sparse = rows[0]["sparse_vector"]
        # 必须是 dict, 不能是 list
        assert isinstance(sparse, dict), f"sparse_vector 应为 dict, 得到 {type(sparse).__name__}"
        assert sparse == {1: 0.5, 99: 0.3}
        # 确认 key 是 int, value 是 float
        for k, v in sparse.items():
            assert isinstance(k, int)
            assert isinstance(v, float)


@pytest.mark.unit
class TestHybridSearch:
    def test_hybrid_search_with_item_name_filter(self, mock_client):
        """带 item_name 过滤时应传 filter expression."""
        from apps.backend.services import milvus_client as mod

        mod._client = mock_client
        mock_client.hybrid_search.return_value = [[]]

        query_dense = [0.1] * 1024
        query_sparse = {1: 0.5}

        results = mod.hybrid_search(
            query_dense=query_dense,
            query_sparse=query_sparse,
            item_name="iPhone16",
            limit=5,
        )

        mock_client.hybrid_search.assert_called_once()
        call_args = mock_client.hybrid_search.call_args
        # collection_name 为第一位置参数
        assert call_args[0][0] == "zgzk"
        reqs = call_args[1]["reqs"]
        assert len(reqs) == 2  # dense + sparse
        # 验证 filter (AnnSearchRequest.filter 是 expr 的 alias)
        dense_req = reqs[0]
        assert dense_req.filter == 'item_name == "iPhone16"'

    def test_hybrid_search_without_filter(self, mock_client):
        """无 item_name 时不传 filter."""
        from apps.backend.services import milvus_client as mod

        mod._client = mock_client
        mock_client.hybrid_search.return_value = [[]]

        mod.hybrid_search(
            query_dense=[0.1] * 1024,
            query_sparse={1: 0.5},
            limit=10,
        )

        call_args = mock_client.hybrid_search.call_args
        reqs = call_args[1]["reqs"]
        dense_req = reqs[0]
        assert dense_req.filter == ""

    def test_hybrid_search_returns_results(self, mock_client):
        """返回结果应解析为 list[dict]."""
        from apps.backend.services import milvus_client as mod

        mock_client.hybrid_search.return_value = [
            [
                {
                    "id": 1,
                    "distance": 0.95,
                    "entity": {"text": "chunk1", "item_name": "iPhone16"},
                },
                {
                    "id": 2,
                    "distance": 0.80,
                    "entity": {"text": "chunk2", "item_name": "iPhone16"},
                },
            ]
        ]
        mod._client = mock_client

        results = mod.hybrid_search(
            query_dense=[0.1] * 1024,
            query_sparse={1: 0.5},
            limit=10,
        )

        assert len(results) == 2
        assert results[0]["text"] == "chunk1"
        assert results[0]["score"] == 0.95
        assert results[0]["item_name"] == "iPhone16"


@pytest.mark.unit
class TestDeleteByDocName:
    def test_delete_calls_milvus_with_correct_filter(self, mock_client):
        """delete_by_doc_name 应使用 doc_name == \"...\" filter."""
        from apps.backend.services import milvus_client as mod

        mod._client = mock_client
        mock_client.delete.return_value = {"delete_count": 42}

        count = mod.delete_by_doc_name("test.pdf")

        mock_client.delete.assert_called_once()
        call_args = mock_client.delete.call_args
        assert call_args[0][0] == "zgzk"  # collection name
        assert call_args[1]["filter"] == 'doc_name == "test.pdf"'
        assert count == 42

    def test_delete_returns_zero_when_no_match(self, mock_client):
        """Milvus 返回 delete_count=0 时应返回 0."""
        from apps.backend.services import milvus_client as mod

        mod._client = mock_client
        mock_client.delete.return_value = {"delete_count": 0}

        count = mod.delete_by_doc_name("nonexistent.pdf")

        assert count == 0
