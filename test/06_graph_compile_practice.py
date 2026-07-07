"""
实践 2.3：LangGraph 工作流编译 - 从节点到有向图

任务：模拟 StateGraph 的构建流程，理解 add_node / add_edge / add_conditional_edges。
运行命令: uv run python test/06_graph_compile_practice.py
"""

from typing import Dict, Callable, Any
from enum import Enum


# ============================================================
# 简化版 LangGraph 核心（模拟项目结构）
# ============================================================

class END:
    """特殊的结束标记"""
    def __repr__(self):
        return "END"


class StateGraph:
    """简化版 StateGraph"""

    def __init__(self, state_type):
        self.state_type = state_type
        self.nodes: Dict[str, Callable] = {}
        self.edges: list = []           # 顺序边
        self.conditional_edges: list = []  # 条件边
        self.entry_point: str = None

    def add_node(self, name: str, node: Callable):
        """注册节点"""
        self.nodes[name] = node

    def set_entry_point(self, name: str):
        """设置入口"""
        self.entry_point = name

    def add_edge(self, from_node: str, to_node):
        """添加顺序边"""
        self.edges.append((from_node, to_node))

    def add_conditional_edges(self, from_node: str, route_fn: Callable, mapping: Dict):
        """添加条件边"""
        self.conditional_edges.append((from_node, route_fn, mapping))

    def compile(self):
        """编译：返回CompiledGraph"""
        return CompiledGraph(self)


class CompiledGraph:
    """编译后的图"""

    def __init__(self, graph: StateGraph):
        self._graph = graph

    def invoke(self, state: dict) -> dict:
        """执行图"""
        current = self._graph.entry_point
        state = dict(state)  # 复制

        while current != END:
            if current not in self._graph.nodes:
                raise ValueError(f"节点 {current} 不存在")

            # 执行当前节点
            node = self._graph.nodes[current]
            state = node(state)

            # 查找下一个节点
            next_node = self._find_next(current, state)
            current = next_node

        return state

    def _find_next(self, current: str, state: dict):
        """查找下一个节点"""
        # 先检查条件边
        for from_node, route_fn, mapping in self._graph.conditional_edges:
            if from_node == current:
                key = route_fn(state)
                return mapping.get(key, END)

        # 再检查顺序边
        for from_node, to_node in self._graph.edges:
            if from_node == current:
                return to_node

        return END

    def print_ascii(self):
        """打印图结构"""
        print("┌─ 入口:", self._graph.entry_point)
        print("├─ 节点:", list(self._graph.nodes.keys()))
        print("├─ 顺序边:")
        for f, t in self._graph.edges:
            print(f"   {f} → {t}")
        print("├─ 条件边:")
        for f, fn, mapping in self._graph.conditional_edges:
            targets = list(mapping.keys())
            print(f"   {f} → {targets}")
        print("└─ 结束: END")


# ============================================================
# 任务 1：定义节点函数
# 定义 4 个节点函数（模拟导入流程）：
#   - node_entry: 检测文件类型，设置 state["file_type"]
#   - node_pdf: 处理 PDF，设置 state["content"] = "PDF内容"
#   - node_md: 处理 MD，设置 state["content"] = "MD内容"
#   - node_end: 结束节点，设置 state["done"] = True
# ============================================================

# TODO: 定义 node_entry(state) -> state
#   检测 state["file_path"] 的扩展名：
#     - .pdf → state["file_type"] = "pdf"
#     - .md  → state["file_type"] = "md"
#     - 其他  → state["file_type"] = "unknown"

def node_entry(state):
    path = state["file_path"]
    if path.endswith(".pdf"):
        state["file_type"] = "pdf"
    elif path.endswith(".md"):
        state["file_type"] = "md"
    else:
        state["file_type"] = "unknown"
    return state

# TODO: 定义 node_pdf(state) -> state
def node_pdf(state):
    state["content"] = "PDF内容"
    return state
# TODO: 定义 node_md(state) -> state
def node_md(state):
    state["content"] = "MD内容"
    return state
# TODO: 定义 node_end(state) -> state
def node_end(state):
    state["done"] = True
    return state



# ============================================================
# 任务 2：定义路由函数
# 定义 route_after_entry(state) -> str：
#   - file_type == "pdf" → 返回 "node_pdf"
#   - file_type == "md"  → 返回 "node_md"
#   - 其他               → 返回 END
# ============================================================

# TODO: 定义 route_after_entry(state)
def route_after_enty(state):
    if state["file_type"] == "pdf":
        return "node_pdf"
    elif state["file_type"] == "md":
        return "node_md"
    return END



# ============================================================
# 任务 3：构建图
# 创建 StateGraph，注册节点，设置入口，添加边，编译
# ============================================================

# TODO:
#   graph = StateGraph(dict)
#   注册 4 个节点
#   设置入口为 "node_entry"
#   添加条件边（从 node_entry 出发，用 route_after_entry）
#   添加顺序边：node_pdf → node_end, node_md → node_end
#   编译
graph = StateGraph(dict)
graph.add_node("node_entry", node_entry)
graph.add_node("node_pdf",node_pdf)
graph.add_node("node_md",node_md)
graph.add_node("node_end",node_end)
graph.set_entry_point("node_entry")
graph.add_conditional_edges("node_entry", route_after_enty, {
    "node_pdf": "node_pdf",
    "node_md": "node_md",
    END: END
})
graph.add_edge("node_pdf", "node_end")
graph.add_edge("node_md", "node_end")
compiled = graph.compile()

# ============================================================
# 任务 4：执行图 + 打印结构
# 用 print_ascii() 查看图结构，用 invoke() 执行
# ============================================================

# TODO:
#   compiled = graph.compile()
#   compiled.print_ascii()
#   用不同文件路径测试 invoke()
compiled.print_ascii()

# ============================================================
# 测试代码（不要修改）
# ============================================================

if __name__ == "__main__":
    print("=== 测试 1：PDF 流程 ===")
    result = compiled.invoke({"file_path": "test.pdf"})
    print(f"结果: {result}")
    assert result["file_type"] == "pdf"
    assert result["content"] == "PDF内容"
    assert result["done"] is True
    print("✅ PDF 流程正确")

    print("\n=== 测试 2：MD 流程 ===")
    result = compiled.invoke({"file_path": "test.md"})
    print(f"结果: {result}")
    assert result["file_type"] == "md"
    assert result["content"] == "MD内容"
    print("✅ MD 流程正确")

    print("\n=== 测试 3：未知类型 → 直接结束 ===")
    result = compiled.invoke({"file_path": "test.txt"})
    print(f"结果: {result}")
    assert result["file_type"] == "unknown"
    assert "content" not in result  # 应该直接结束，不处理
    print("✅ 未知类型正确处理")

    print("\n🎉 三个测试全部通过！")
