"""Milvus 操作 wrapper (pymilvus 3.0.0 MilvusClient 新 API)."""
from __future__ import annotations

import logging

from pymilvus import MilvusClient, DataType, AnnSearchRequest, WeightedRanker
from apps.backend.core.config import get_settings

logger = logging.getLogger(__name__)

DENSE_DIM = 1024

_client: MilvusClient | None = None


def _get_client() -> MilvusClient:
    """懒加载 MilvusClient, 基于 Settings 中的 host/port."""
    global _client
    if _client is None:
        settings = get_settings()
        uri = f"http://{settings.milvus_host}:{settings.milvus_port}"
        _client = MilvusClient(uri=uri)
    return _client


def _collection_name() -> str:
    return get_settings().milvus_collection


def ensure_collection() -> None:
    """创建 collection (含 schema + 索引), 已存在则跳过. 创建后 load 到内存."""
    client = _get_client()
    name = _collection_name()
    if not client.has_collection(name):
        schema = MilvusClient.create_schema(auto_id=True, enable_dynamic_field=False)
        schema.add_field("id", DataType.INT64, is_primary=True, auto_id=True)
        schema.add_field("dense_vector", DataType.FLOAT_VECTOR, dim=DENSE_DIM)
        schema.add_field("sparse_vector", DataType.SPARSE_FLOAT_VECTOR)
        schema.add_field("text", DataType.VARCHAR, max_length=65535)
        schema.add_field("item_name", DataType.VARCHAR, max_length=256)
        schema.add_field("doc_name", DataType.VARCHAR, max_length=1024)
        schema.add_field("chunk_id", DataType.INT64)

        client.create_collection(name, schema=schema)

        index_params = MilvusClient.prepare_index_params()
        index_params.add_index("dense_vector", index_type="IVF_FLAT", metric_type="L2", params={"nlist": 128})
        index_params.add_index("sparse_vector", index_type="SPARSE_INVERTED_INDEX", metric_type="IP", params={"drop_ratio_build": 0.2})
        client.create_index(name, index_params=index_params)

    # 确保集合加载到内存 (搜索前必须)
    client.load_collection(name)

    # 创建后 load 到内存, 否则 hybrid_search 报 collection not loaded
    client.load_collection(name)


def bulk_upsert(vectors: list[dict]) -> None:
    """批量写入 Milvus.

    vectors 格式: [{text, item_name, doc_name, chunk_id, dense_vector, sparse_vector}, ...]
    sparse_vector 接受 dict[int, float], 内部转成 list[dict] 格式。
    空列表不调用 insert。
    """
    if not vectors:
        return

    client = _get_client()
    ensure_collection()

    rows = [_normalize_row(v) for v in vectors]
    client.insert(_collection_name(), rows)


def _normalize_row(v: dict) -> dict:
    sparse = v.get("sparse_vector", {})
    # pymilvus 3.0 insert: sparse vector 直接传 {idx: weight}
    return {
        "text": v.get("text", ""),
        "item_name": v.get("item_name", ""),
        "doc_name": v.get("doc_name", ""),
        "chunk_id": v.get("chunk_id", 0),
        "dense_vector": v.get("dense_vector", [0.0] * DENSE_DIM),
        "sparse_vector": sparse if isinstance(sparse, dict) else {},
    }


def delete_by_doc_name(doc_name: str) -> int:
    """按 doc_name 删除该文档所有 chunk.

    Args:
        doc_name: 文档名, 用于 filter expression

    Returns:
        删除的条数 (collection 不存在时返回 0)
    """
    try:
        client = _get_client()
        result = client.delete(_collection_name(), filter=f'doc_name == "{doc_name}"')
        return result.get("delete_count", 0)
    except Exception as e:
        logger.warning("[milvus] delete_by_doc_name failed (collection may not exist): %s", e)
        return 0


def hybrid_search(
    query_dense: list[float],
    query_sparse: dict[int, float],
    item_name: str | None = None,
    limit: int = 10,
) -> list[dict]:
    """Hybrid search: 一次 RPC, 服务端 RRF 融合稠密 + 稀疏结果.

    Args:
        query_dense: 稠密查询向量, 长度 1024
        query_sparse: 稀疏查询向量, {token_id: weight}
        item_name: 可选过滤主体名
        limit: 返回条数上限

    Returns:
        list of {text, item_name, score}
    """
    client = _get_client()
    ensure_collection()
    collection = _collection_name()
    filt = f'item_name == "{item_name}"' if item_name else ""

    dense_req = AnnSearchRequest(
        data=[query_dense],
        anns_field="dense_vector",
        param={"metric_type": "L2", "params": {"nprobe": 10}},
        limit=limit,
        expr=filt,
    )
    sparse_req = AnnSearchRequest(
        # pymilvus 3.0: sparse data 格式为 [{token_id: weight, ...}], 每元素是一个稀疏向量
        data=[query_sparse],
        anns_field="sparse_vector",
        param={"metric_type": "IP", "params": {"drop_ratio_search": 0.2}},
        limit=limit,
        expr=filt,
    )

    ranker = WeightedRanker(0.5, 0.5)
    raw = client.hybrid_search(
        collection,
        reqs=[dense_req, sparse_req],
        ranker=ranker,
        limit=limit,
        output_fields=["text", "item_name"],
    )

    hits = raw[0] if raw else []
    results = []
    for hit in hits:
        ent = hit.get("entity", {}) if isinstance(hit, dict) else {}
        results.append({
            "text": ent.get("text", ""),
            "item_name": ent.get("item_name", ""),
            "score": hit.get("distance", 0.0) if isinstance(hit, dict) else 0.0,
        })
    return results
