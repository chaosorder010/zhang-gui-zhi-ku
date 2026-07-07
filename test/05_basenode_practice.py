"""
实践 2.2：BaseNode 基类 - 模板方法模式

任务：创建一个新节点类继承 BaseNode，体验基类的统一行为。
运行命令: uv run python test/05_basenode_practice.py
"""

import logging
from abc import ABC, abstractmethod
from typing import TypeVar, Optional, Dict

# ============================================================
# 任务 1：搭建最小可运行的 BaseNode（模拟项目）
# 复制项目的核心结构，省略了 config 依赖
# ============================================================

T = TypeVar("T")


class ImportProcessError(Exception):
    """简化版基础异常"""
    def __init__(self, message: str, node_name: str = "", cause: Exception = None):
        self.node_name = node_name
        self.cause = cause
        super().__init__(message)

    def __str__(self):
        parts = []
        if self.node_name:
            parts.append(f"[{self.node_name}]")
        parts.append(super().__str__())
        if self.cause:
            parts.append(f"(原因: {self.cause})")
        return " ".join(parts)


class BaseNode(ABC):
    """简化版 BaseNode"""
    name: str = "base_node"

    def __init__(self):
        self.logger = logging.getLogger(f"import.{self.name}")

    def __call__(self, state: T) -> T:
        try:
            self.logger.info(f"--- {self.name} 开始 ---")
            result = self.process(state)
            self.logger.info(f"--- {self.name} 完成 ---")
            return result
        except Exception as e:
            raise ImportProcessError(
                message=str(e),
                node_name=self.name,
                cause=e
            )

    @abstractmethod
    def process(self, state: T) -> T:
        pass


# ============================================================
# 任务 2：创建你的第一个节点类
# 定义 HelloNode，实现 process：
#   - 打印一条消息到日志
#   - 给 state 添加一个字段 "greeting" = "Hello from HelloNode!"
#   - 返回更新后的 state
# ============================================================

# TODO: 创建 class HelloNode(BaseNode):
#   设置 name = "hello_node"
#   实现 process(self, state) -> state
class HelloNode(BaseNode):
    name = "hello_node"
    
    def process(self, state):
        self.logger.info("Hello")
        state["greeting"] = "Hello from HelloNone"
        return state



# ============================================================
# 任务 3：创建一个会抛出异常的节点
# 定义 ErrorNode，在 process 中主动抛出一个 ValueError
# 体验基类的异常自动包装
# ============================================================

# TODO: 创建 class ErrorNode(BaseNode):
#   设置 name = "error_node"
#   在 process 中 raise ValueError("模拟错误")

class ErrorNode(BaseNode):
    name = "error_node"
    
    def process(self, state):
        raise ValueError("模拟错误")

# ============================================================
# 任务 4：链式调用 - 让两个节点串联执行
# state 依次经过 HelloNode 和 ErrorNode
# 体验节点是可调用对象，可以像函数一样传递
# ============================================================

# TODO:
#   state = {"task_id": "test-001"}
#   hello = HelloNode()
#   error = ErrorNode()
#   先调用 hello(state)
#   再对结果调用 error() - 应该触发 ImportProcessError
state = {"task_id": "test-001"}

hello = HelloNode()
error = ErrorNode()

result = hello(state)
error(result)
# ============================================================
# 测试代码（不要修改）
# ============================================================

if __name__ == "__main__":
    # 配置日志显示
    logging.basicConfig(
        level=logging.INFO,
        format='%(name)s - %(levelname)s - %(message)s'
    )

    print("=== 测试 1：正常节点执行 ===")
    state = {"task_id": "test-001"}
    hello = HelloNode()
    result = hello(state)
    print(f"state 结果: {result}")

    print("\n=== 测试 2：异常自动包装 ===")
    error = ErrorNode()
    try:
        error({"task_id": "test-002"})
        print("❌ 应该抛出异常")
    except ImportProcessError as e:
        print(f"✅ 异常被自动包装: {e}")
        print(f"  - 节点名: {e.node_name}")
        print(f"  - 原始异常类型: {type(e.cause).__name__}")

    print("\n=== 测试 3：链式调用 ===")
    try:
        result = hello({"task_id": "test-003"})
        error(result)
    except ImportProcessError as e:
        print(f"✅ 链式调用中捕获: {e}")

    print("\n🎉 三个测试全部通过！")
