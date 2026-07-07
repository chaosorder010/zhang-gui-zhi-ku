"""
实践 2.4：骨架串联 - 端到端走一遍空节点流程

目标：运行一个模拟的 7 节点导入工作流，观察执行顺序和日志。
运行命令: uv run python test/07_full_pipeline_practice.py
"""

import logging
from typing import TypedDict
from abc import ABC, abstractmethod


# ============================================================
# 配置日志（模拟项目的 colorlog）
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(name)s - %(levelname)s - %(message)s'
)


# ============================================================
# 状态定义（模拟 ImportGraphState）
# ============================================================

class ImportGraphState(TypedDict):
    task_id: str
    is_pdf_read_enabled: bool
    is_md_read_enabled: bool
    import_file_path: str
    file_dir: str
    pdf_path: str
    md_path: str
    file_title: str
    item_name: str
    md_content: str
    chunks: list


def get_default_state() -> ImportGraphState:
    return {
        "task_id": "",
        "is_pdf_read_enabled": False,
        "is_md_read_enabled": False,
        "import_file_path": "",
        "file_dir": "",
        "pdf_path": "",
        "md_path": "",
        "file_title": "",
        "item_name": "",
        "md_content": "",
        "chunks": [],
    }


# ============================================================
# 节点基类（模拟 BaseNode）
# ============================================================

class BaseNode(ABC):
    name: str = "base_node"

    def __init__(self):
        self.logger = logging.getLogger(f"import.{self.name}")

    def __call__(self, state: ImportGraphState) -> ImportGraphState:
        self.logger.info(f"--- {self.name} 开始 ---")
        result = self.process(state)
        self.logger.info(f"--- {self.name} 完成 ---")
        return result

    @abstractmethod
    def process(self, state: ImportGraphState) -> ImportGraphState:
        pass


# ============================================================
# 任务：补全 7 个空节点
# 每个节点只需要：
#   1. 设置 name
#   2. 实现空的 process 方法（pass 即可）
# ============================================================

# TODO: 定义 7 个节点类
# 提示：每个类只需要 3 行代码
#
# class NodeEntry(BaseNode):
#     name = "node_entry"
#     def process(self, state):
#         pass

# class NodePDFToMD(BaseNode):
# class NodeMDImg(BaseNode):
# class NodeDocumentSplit(BaseNode):
# class NodeItemNameRecognition(BaseNode):
# class NodeBGEEmbedding(BaseNode):
# class NodeImportMilvus(BaseNode):

# 你的代码写在这里：
class NodeEntry(BaseNode):
    name = "node_entry"
    def process(self, state):
        return state
    
class NodePDFToMD(BaseNode):
    name = "node_pdf_to_md"
    def process(self, state):
        return state

class NodeMDImg(BaseNode):
    name = "node_md_img"
    def process(self, state):
        return state
    
class NodeDocumentSplit(BaseNode):
    name = "node_document_split"
    def process(self, state):
        return state

class NodeItemNameRecognition(BaseNode):
    name = "node_item_name_recognation"
    def process(self, state):
        return state

class NodeBGEEmbdding(BaseNode):
    name = "node_BGE_embding"
    def process(self, state):
        return state
    
class NodeImportMilvus(BaseNode):
    name = "node_import_milvus"
    def process(self, state):
        return state
    
# ============================================================
# 任务 2：构建工作流
# 创建节点实例，定义路由函数，构建图并执行
# ============================================================

# TODO: 创建节点实例
#   entry = NodeEntry()
#   pdf_to_md = NodePDFToMD()
#   ...
entry = NodeEntry()
pdf_to_md = NodePDFToMD()
md_img = NodeMDImg()
doc_split = NodeDocumentSplit()
item_name = NodeItemNameRecognition()
bge_emb = NodeBGEEmbdding()
import_milvus = NodeImportMilvus()

# TODO: 定义路由函数 route_after_entry(state)
#   如果 state["is_pdf_read_enabled"] → 返回 "node_pdf_to_md"
#   如果 state["is_md_read_enabled"] → 返回 "node_md_img"
#   否则 → 返回 "END"
def route_after_entry(state):
    if state["is_pdf_read_enabled"]:
        return "node_pdf_to_md"
    elif state["is_md_read_enabled"]:
        return "node_md_img"
    return "END"

# TODO: 手动执行流程（模拟 LangGraph 的 invoke）
#   按顺序调用节点，根据路由函数决定路径


# ============================================================
# 测试代码（不要修改）
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("场景 1：PDF 文件导入流程")
    print("=" * 60)

    state = get_default_state()
    state["task_id"] = "task-001"
    state["import_file_path"] = "/data/test.pdf"
    state["is_pdf_read_enabled"] = True

    # 手动执行（模拟 LangGraph）
    state = entry(state)

    # 根据路由决定路径
    if route_after_entry(state) == "node_pdf_to_md":
        state = pdf_to_md(state)
        state = md_img(state)
        state = doc_split(state)
        state = item_name(state)
        state = bge_emb(state)
        state = import_milvus(state)

    print("\n最终 state:")
    for k, v in state.items():
        print(f"  {k}: {v}")

    print("\n" + "=" * 60)
    print("场景 2：Markdown 文件导入流程")
    print("=" * 60)

    state2 = get_default_state()
    state2["task_id"] = "task-002"
    state2["import_file_path"] = "/data/test.md"
    state2["is_md_read_enabled"] = True

    state2 = entry(state2)
    if route_after_entry(state2) == "node_md_img":
        state2 = md_img(state2)
        state2 = doc_split(state2)
        state2 = item_name(state2)
        state2 = bge_emb(state2)
        state2 = import_milvus(state2)

    print("\n最终 state:")
    for k, v in state2.items():
        print(f"  {k}: {v}")

    print("\n🎉 运行成功！观察上面的日志，理解节点执行顺序。")
