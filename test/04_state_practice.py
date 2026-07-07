"""
实践 2.1：状态设计 - ImportGraphState 数据契约

任务：体验 TypedDict 状态定义、工厂函数和深拷贝。
运行命令: uv run python test/04_state_practice.py
"""

from typing import TypedDict, List
import copy


# ============================================================
# 任务 1：定义 TypedDict 状态
# 定义 GraphState，包含以下字段：
#   - task_id: str
#   - status: str = "pending"（用这个默认值）
#   - results: List[str]
#   - error: str = ""
# ============================================================

# TODO: 定义 GraphState(TypedDict)
class GraphState(TypedDict):
    task_id: str
    status: str = "pending"
    results: List[str]
    error: str = ""



# ============================================================
# 任务 2：定义默认状态 + 工厂函数
# 创建 DEFAULT_STATE 字典和 get_default_state() 函数
# 要求用 copy.deepcopy 避免共享
# ============================================================

# TODO: DEFAULT_STATE: GraphState = { ... }
DEFAULT_STATE: GraphState = {
    "task_id": "",
    "status": "pending",
    "results": [],
    "error": ""
}
# TODO: def get_default_state() -> GraphState: ...
def get_default_state() -> GraphState:
    return copy.deepcopy(DEFAULT_STATE)



# ============================================================
# 任务 3：模拟节点更新状态
# 模拟一个"处理节点"：
#   - 接收 state
#   - 更新 status 为 "completed"
#   - 添加一条 result
#   - 返回更新后的 state
# ============================================================

# TODO: def process_node(state: GraphState) -> GraphState: ...
def process_node(state: GraphState) -> GraphState:
    state["status"] = "completed"
    state["results"].append("processed")
    return state



# ============================================================
# 任务 4：验证深拷贝隔离性
# 创建两个独立任务，验证修改一个不影响另一个
# ============================================================

# TODO:
#   task1 = get_default_state()
#   task2 = get_default_state()
#   task1["task_id"] = "task-001"
#   task2["task_id"] = "task-002"
#   验证 task1 和 task2 互不干扰
task1 = get_default_state()
task2 = get_default_state()
task1["task_id"] = "task-001"
task2["task_id"] = "task-002"

# ============================================================
# 测试代码（不要修改）
# ============================================================

if __name__ == "__main__":
    print("=== 测试 1：默认状态 ===")
    state = get_default_state()
    print(f"task_id: '{state['task_id']}'")
    print(f"status: '{state['status']}'")
    print(f"results: {state['results']}")

    print("\n=== 测试 2：节点处理 ===")
    state["task_id"] = "task-001"
    processed = process_node(state)
    print(f"status: '{processed['status']}'")
    print(f"results: {processed['results']}")

    print("\n=== 测试 3：深拷贝隔离 ===")
    task_a = get_default_state()
    task_b = get_default_state()
    task_a["task_id"] = "A"
    task_b["task_id"] = "B"
    task_a["results"].append("result from A")
    print(f"task_a.task_id = {task_a['task_id']}, results = {task_a['results']}")
    print(f"task_b.task_id = {task_b['task_id']}, results = {task_b['results']}")
    if task_b["results"] == []:
        print("✅ 深拷贝有效：task_a 的修改没有影响 task_b")
    else:
        print("❌ 没有隔离")

    print("\n🎉 三个测试全部通过！")
