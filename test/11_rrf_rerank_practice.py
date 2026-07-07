"""
实践 5.4：RRF 融合 + Rerank 重排序 - 多路结果的"裁判"

任务：实现 RRF 融合算法 + 模拟 Rerank 精排 + 断崖检测。
运行命令: uv run python test/11_rrf_rerank_practice.py
"""

import copy


# ============================================================
# 模拟多路搜索结果
# ============================================================

# 三路搜索结果，每路返回 (doc_id, score) 列表
# 注意：不同来源的分数不可直接比较！
vector_results = [
    ("doc_a", 0.92), ("doc_c", 0.85), ("doc_b", 0.78),
    ("doc_d", 0.72), ("doc_e", 0.65),
]

hyde_results = [
    ("doc_b", 0.91), ("doc_a", 0.83), ("doc_f", 0.76),
    ("doc_c", 0.71), ("doc_g", 0.64),
]

web_results = [
    ("doc_h", None), ("doc_b", None), ("doc_i", None),
]  # Web 搜索没有分数！


# ============================================================
# 任务 1：实现 RRF 融合算法
# RRF_score(doc) = Σ 1/(k + rank_i)
# k=60 是平滑参数，rank_i 从 1 开始
# ============================================================

# TODO: 实现 rrf_fuse(result_lists, k=60)
# 输入: 多路搜索结果列表，每路是 [(doc_id, score), ...]
# 输出: 按 RRF 分数降序排列的 [(doc_id, rrf_score), ...]

def rrf_fuse(result_lists: list[list[tuple[str, float | None]]], k: int = 60) -> list[tuple[str, float]]:
    """RRF 融合：用排名而非原始分数来融合多路结果"""
    # TODO: 实现 RRF 算法
    # 提示：
    #   1. 遍历每路结果，记录每个文档在各路中的排名（从 1 开始）
    #   2. 对每个文档，计算 RRF = Σ 1/(k + rank_i)
    #   3. 按 RRF 分数降序返回
    pass
    doc_score = {}
    for result in result_lists:
        for i, item in enumerate(result, 1):
            doc = item[0]
            doc_score[doc] = doc_score.get(doc,0) + 1 / (i + 60)

    return sorted(doc_score.items(),key=lambda x: x[1], reverse=True)

# ============================================================
# 任务 2：模拟 BGE-Reranker 精排
# Reranker 对每个 (query, doc) 对重新打分
# ============================================================

# TODO: 实现模拟的 rerank 函数
# 输入: query 字符串 + RRF 融合后的文档列表 [(doc_id, rrf_score), ...]
# 输出: 精排后的 [(doc_id, rerank_score), ...]，按 rerank_score 降序
# 提示：用 hash(query + doc_id) % 100 / 100 模拟打分（实际是交叉编码器逐对计算）

def simulate_rerank(query: str, docs: list[tuple[str, float]]) -> list[tuple[str, float]]:
    """模拟 Reranker 精排：对每个 query-doc 对重新打分"""
    # TODO: 实现模拟精排
    rerank_doc = {}
    for doc_id, score in docs:
        rerank_doc[doc_id] = hash(query + doc_id) % 100 / 100
    return sorted(rerank_doc.items(), key=lambda x: x[1], reverse=True)


# ============================================================
# 任务 3：断崖检测 + 自动截断
# 相邻文档分差过大时截断，丢弃低质结果
# ============================================================

# TODO: 实现 cliff_detection(docs, threshold=0.2)
# 输入: 精排后的 [(doc_id, score), ...]（已按分数降序）
#       threshold: 相邻分差超过此值视为"断崖"
# 输出: 截断后的列表
# 示例: [(a,0.95), (b,0.91), (c,0.89), (d,0.45), (e,0.12)]
#       c→d 的分差 = 0.89-0.45 = 0.44 > 0.2 → 断崖！截断为 [a, b, c]

def cliff_detection(
    docs: list[tuple[str, float]],
    threshold: float = 0.2
) -> list[tuple[str, float]]:
    """断崖检测：分差过大时自动截断"""
    # TODO: 实现断崖检测
    
    for i in range(1, len(docs)):
        gap = docs[i - 1][1] - docs[i][1]
        if gap >= threshold:
            return docs[:i]
    return docs

# ============================================================
# 任务 4：端到端流程
# 三路结果 → RRF 融合 → Rerank 精排 → 断崖截断 → 最终结果
# ============================================================

# TODO: 串联完整流程
query = "产品安全规范有哪些要求？"
fused = rrf_fuse([vector_results, hyde_results, web_results])
reranked =  simulate_rerank(query, fused)
cliff_detection(reranked)
# 1. rrf_fuse([vector_results, hyde_results, web_results])
# 2. simulate_rerank(query, fused)
# 3. cliff_detection(reranked)
# 4. 打印每一步的中间结果


# ============================================================
# 测试代码（不要修改）
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("测试 1：RRF 融合")
    print("=" * 60)

    fused = rrf_fuse([vector_results, hyde_results, web_results])
    print("RRF 融合结果（Top-5）:")
    for doc_id, score in fused[:5]:
        print(f"  {doc_id}: {score:.6f}")

    # 多路都出现的文档应该排更前
    # doc_b 在三路中都出现了，应该排名靠前
    assert len(fused) > 0, "融合结果不应为空"
    # doc_a 在两路中出现（vector #1, hyde #2），应该比只在一路的高
    a_scores = [s for d, s in fused if d == "doc_a"]
    f_scores = [s for d, s in fused if d == "doc_f"]
    if a_scores and f_scores:
        # doc_a 在两路中出现，RRF 分数应该比只在一路的 doc_f 高
        assert a_scores[0] > f_scores[0], \
            f"多路出现的 doc_a({a_scores[0]:.6f}) 应比单路的 doc_f({f_scores[0]:.6f}) 排名更高"
    print("✅ RRF 融合测试通过")

    print("\n" + "=" * 60)
    print("测试 2：Rerank 精排")
    print("=" * 60)

    query = "产品安全规范有哪些要求？"
    # 先用 RRF 结果做输入
    fused = rrf_fuse([vector_results, hyde_results, web_results])
    reranked = simulate_rerank(query, fused)

    print("精排结果（Top-5）:")
    for doc_id, score in reranked[:5]:
        print(f"  {doc_id}: {score:.4f}")

    # 分数应该在 0~1 之间
    assert all(0 <= s <= 1 for _, s in reranked), "Rerank 分数应在 0~1 之间"
    # 应该按降序排列
    for i in range(len(reranked) - 1):
        assert reranked[i][1] >= reranked[i+1][1], "应严格按分数降序"
    print("✅ Rerank 精排测试通过")

    print("\n" + "=" * 60)
    print("测试 3：断崖检测")
    print("=" * 60)

    # 构造有明显断崖的数据
    test_docs = [
        ("doc_a", 0.95),
        ("doc_b", 0.91),
        ("doc_c", 0.89),
        ("doc_d", 0.45),  # ← 断崖！（0.89→0.45，差 0.44）
        ("doc_e", 0.12),
    ]
    truncated = cliff_detection(test_docs, threshold=0.2)
    print(f"截断前: {len(test_docs)} 条")
    print(f"截断后: {len(truncated)} 条")
    for doc_id, score in truncated:
        print(f"  {doc_id}: {score:.2f}")

    assert len(truncated) == 3, f"应该截断为 3 条，实际 {len(truncated)}"
    assert truncated[-1][0] == "doc_c", "doc_c 应该是最后一条"
    print("✅ 断崖检测测试通过")

    print("\n" + "=" * 60)
    print("测试 4：端到端流程")
    print("=" * 60)

    query = "产品安全规范有哪些要求？"

    # Step 1: RRF 融合
    fused = rrf_fuse([vector_results, hyde_results, web_results])
    print(f"[RRF 融合] {len(fused)} 条结果")

    # Step 2: Rerank 精排
    reranked = simulate_rerank(query, fused)
    print(f"[Rerank 精排] {len(reranked)} 条结果")

    # Step 3: 断崖截断
    final = cliff_detection(reranked)
    print(f"[断崖截断] 最终 {len(final)} 条结果")
    print()
    print("最终返回给 LLM 的上下文:")
    for i, (doc_id, score) in enumerate(final, 1):
        print(f"  {i}. [{doc_id}] (相关性: {score:.4f})")

    print("\n🎉 四个测试全部通过！")
