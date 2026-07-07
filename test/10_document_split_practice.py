"""
实践 3.3：文档切片 - 智能分块策略

任务：模拟文档切分逻辑，理解 chunk_size 和 chunk_overlap 的作用。
运行命令: uv run python test/10_document_split_practice.py
"""


# ============================================================
# 模拟 split_text 函数
# ============================================================

import copy


def split_text(
    text: str,
    chunk_size: int = 2000,
    chunk_overlap: int = 200
) -> list[str]:
    """模拟文档切分：按 chunk_size 切分，相邻块重叠 chunk_overlap"""
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        # 下一块从 (end - overlap) 开始，确保有重叠
        start = end - chunk_overlap

    return chunks


# ============================================================
# 任务 1：理解 chunk_size 的效果
# 用一段短文本测试不同的 chunk_size
# ============================================================

# TODO: 用下面的文本做实验
sample_text = (
    "第一段：Python 的 dataclass 装饰器可以自动生成 __init__ 方法。"
    "第二段：Pydantic 的 BaseModel 提供了运行时数据验证功能。"
    "第三段：LangGraph 使用 StateGraph 来编排工作流节点。"
    "第四段：BGE-M3 模型可以生成稠密向量和稀疏向量。"
    "第五段：Milvus 是一个高性能的向量数据库。"
)

# TODO: 分别用 chunk_size=50 和 chunk_size=100 切分
# 观察不同 chunk_size 对块数量的影响
# chunks_50 = split_text(sample_text, chunk_size=50, chunk_overlap=15)
# chunks_100 = split_text(sample_text, chunk_size=100, chunk_overlap=15)
chunk_50 = split_text(sample_text,chunk_size=50, chunk_overlap=15)
chunk_100 = split_text(sample_text,chunk_size=100, chunk_overlap=15)

# ============================================================
# 任务 2：理解 chunk_overlap 的效果
# 对比有重叠和无重叠的切分结果
# ============================================================

# TODO: 用 chunk_size=100：
#   - 一次 chunk_overlap=30（有重叠）
#   - 一次 chunk_overlap=0（无重叠）
# 观察每块的起始位置差异
chunk_overlay = split_text(sample_text, chunk_size=100, chunk_overlap=30)
chunk_overlay = split_text(sample_text, chunk_size=100, chunk_overlap=0)

# ============================================================
# 任务 3：模拟短内容合并
# 当某些块太短时（< min_length），合并到前一块
# ============================================================

# TODO: 实现 merge_short_chunks(chunks, min_length)
# 输入: ["abc", "defghijklmn", "xyz"]
#        min_length = 10
# 输出: ["abcdefghijklmn", "xyz"]  或 ["abc", "defghijklmnxyz"]
# 注意：合并后不超过 chunk_size


def merge_short_chunks(chunks: list[str], min_length: int) -> list[str]:
    """将太短的 chunk 合并到相邻块"""
    # TODO: 实现合并逻辑
    # 提示：遍历 chunks，长度 < min_length 的合并到前一个
    new_chunks = copy.copy(chunks)
    for i, chunk in enumerate(new_chunks):
        if i == len(new_chunks) - 1:
            return new_chunks
        if len(chunk) < min_length:
            new_chunks[i + 1] = chunk + new_chunks[i + 1]
            del new_chunks[i]
    return new_chunks


# ============================================================
# 测试代码（不要修改）
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("测试 1：chunk_size 的影响")
    print("=" * 60)

    chunks_50 = split_text(sample_text, chunk_size=50, chunk_overlap=15)
    chunks_100 = split_text(sample_text, chunk_size=100, chunk_overlap=15)

    print(f"原文长度: {len(sample_text)} 字符")
    print(f"chunk_size=50 → {len(chunks_50)} 块")
    print(f"chunk_size=100 → {len(chunks_100)} 块")

    # chunk_size 越小，块数应该越多
    assert len(chunks_50) >= len(chunks_100)
    print("✅ chunk_size 测试通过")

    print("\n" + "=" * 60)
    print("测试 2：chunk_overlap 的影响")
    print("=" * 60)

    chunks_with_overlap = split_text(sample_text, chunk_size=100, chunk_overlap=30)
    chunks_no_overlap = split_text(sample_text, chunk_size=100, chunk_overlap=0)

    print(f"chunk_overlap=30 → {len(chunks_with_overlap)} 块")
    print(f"chunk_overlap=0 → {len(chunks_no_overlap)} 块")

    # 有重叠的块数应该 ≥ 无重叠的块数
    assert len(chunks_with_overlap) >= len(chunks_no_overlap)
    print("✅ chunk_overlap 测试通过")

    print("\n" + "=" * 60)
    print("测试 3：短内容合并")
    print("=" * 60)

    test_chunks = ["abc", "defghijklmn", "xyz"]
    merged = merge_short_chunks(test_chunks, min_length=10)
    print(f"合并前: {test_chunks}")
    print(f"合并后: {merged}")
    # 中间那块 >=10，旁边的短块应该被合并
    assert any(len(c) >= 10 for c in merged)
    print("✅ 短内容合并测试通过")

    print("\n🎉 三个测试全部通过！")
