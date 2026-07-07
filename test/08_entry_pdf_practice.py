"""
实践 3.1：入口分发 + PDF 转 Markdown

任务：模拟 node_entry 和 node_pdf_to_md 的完整数据流。
运行命令: uv run python test/08_entry_pdf_practice.py
"""

from dataclasses import dataclass
from typing import TypedDict, Optional

# ============================================================
# 状态定义
# ============================================================

class ImportState(TypedDict):
    import_file_path: str
    is_pdf_read_enabled: bool
    is_md_read_enabled: bool
    file_type: str              # 新增：检测到的文件类型
    pdf_path: Optional[str]      # PDF 路径（如果是 PDF）
    md_path: Optional[str]       # 转换后的 MD 路径（如果有）
    file_title: str              # 文件名（不含扩展名）


def create_initial_state(file_path: str) -> ImportState:
    """创建初始状态"""
    return {
        "import_file_path": file_path,
        "is_pdf_read_enabled": False,
        "is_md_read_enabled": False,
        "file_type": "unknown",
        "pdf_path": None,
        "md_path": None,
        "file_title": "",
    }


# ============================================================
# 任务 1：实现 node_entry
# 检测文件类型，设置控制标志和元数据
# ============================================================

# TODO: 实现 node_entry(state: ImportState) -> ImportState
# 要求：
#   1. 从 import_file_path 提取文件名（不含扩展名）→ state["file_title"]
#   2. 检测扩展名：
#      - .pdf → state["is_pdf_read_enabled"] = True, state["file_type"] = "pdf"
#      - .md  → state["is_md_read_enabled"] = True, state["file_type"] = "md"
#      - 其他 → state["file_type"] = "unknown"
#   3. 如果是 PDF，设置 state["pdf_path"] = state["import_file_path"]




# ============================================================
# 任务 2：实现 route_after_entry（条件路由）
# ============================================================

# TODO: 实现 route_after_entry(state: ImportState) -> str
# 要求：
#   - is_pdf_read_enabled → 返回 "node_pdf_to_md"
#   - is_md_read_enabled  → 返回 "node_md_img"
#   - 其他                → 返回 "END"




# ============================================================
# 任务 3：实现 node_pdf_to_md（模拟 PDF 转 Markdown）
# ============================================================

# TODO: 实现 node_pdf_to_md(state: ImportState) -> ImportState
# 要求：
#   1. 从 state["pdf_path"] 获取 PDF 路径
#   2. 模拟转换：生成 MD 路径（把 .pdf 替换成 .md）
#   3. 设置 state["md_path"] = 生成的路径
#   4. 模拟提取标题：从文件名提取（去掉 _images 等后缀）




# ============================================================
# 任务 4：端到端测试
# 创建状态 → 入口节点 → 路由 → PDF转MD → 打印结果
# ============================================================

# TODO: 用以下两个文件路径测试：
#   1. "/data/manuals/hak180_product_safety_manual.pdf"
#   2. "/data/notes/already_converted.md"


# ============================================================
# 测试代码（不要修改）
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("测试 1：PDF 文件")
    print("=" * 60)

    state1 = create_initial_state("/data/manuals/hak180_product_safety_manual.pdf")
    state1 = node_entry(state1)

    print(f"文件标题: {state1['file_title']}")
    print(f"文件类型: {state1['file_type']}")
    print(f"PDF标志: {state1['is_pdf_read_enabled']}")
    print(f"路由决策: {route_after_entry(state1)}")

    if route_after_entry(state1) == "node_pdf_to_md":
        state1 = node_pdf_to_md(state1)
        print(f"MD路径: {state1['md_path']}")

    print("\n" + "=" * 60)
    print("测试 2：Markdown 文件")
    print("=" * 60)

    state2 = create_initial_state("/data/notes/already_converted.md")
    state2 = node_entry(state2)

    print(f"文件标题: {state2['file_title']}")
    print(f"文件类型: {state2['file_type']}")
    print(f"MD标志: {state2['is_md_read_enabled']}")
    print(f"路由决策: {route_after_entry(state2)}")

    print("\n" + "=" * 60)
    print("测试 3：未知格式")
    print("=" * 60)

    state3 = create_initial_state("/data/files/readme.txt")
    state3 = node_entry(state3)
    print(f"文件标题: {state3['file_title']}")
    print(f"文件类型: {state3['file_type']}")
    print(f"路由决策: {route_after_entry(state3)}")

    print("\n🎉 三个测试全部通过！")
