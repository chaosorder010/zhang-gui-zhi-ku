"""
实践 1.1：dataclass + field() 三种写法

任务：补全下面的代码，感受三种默认值写法的差异。
运行命令: uv run python test/01_dataclass_practice.py
"""

from dataclasses import dataclass, field
import os


# ============================================================
# 任务 1：简单默认值
# 在 MyConfig 中添加一个新字段 log_level，默认值为 "INFO"
# ============================================================

@dataclass
class MyConfig:
    max_length: int = 1000          # ← 简单默认值

    log_level: str = "INFO"

# ============================================================
# 任务 2：field(default_factory=...) 防共享
# 补充 Logger 类，让每个实例拥有独立的 tags 列表
# ============================================================

@dataclass
class Logger:
    name: str
    tags: list = field(default_factory=list)

# ============================================================
# 任务 3：从环境变量读取默认值
# 添加 api_key 字段，默认值从环境变量 MY_API_KEY 读取
# ============================================================

@dataclass
class ApiClient:
    base_url: str = "https://api.example.com"

    # TODO: 添加 api_key 字段，用 field(default_factory=lambda: ...)
    api_key: str = field(default_factory=lambda: os.getenv("MY_API_KEY"))

# ============================================================
# 测试代码（不要修改）
# ============================================================

if __name__ == "__main__":
    print("=== 任务 1：简单默认值 ===")
    cfg = MyConfig()
    print(f"max_length = {cfg.max_length}")
    # 如果你添加了 log_level，下面这行应该生效：
    # print(f"log_level = {cfg.log_level}")

    print("\n=== 任务 2：防共享 ===")
    log1 = Logger(name="auth")
    log2 = Logger(name="db")
    log1.tags.append("error")
    print(f"log1.tags = {log1.tags}")
    print(f"log2.tags = {log2.tags}")
    if log2.tags == []:
        print("✅ 每个实例拥有独立的 tags 列表！")
    else:
        print("❌ tags 被共享了，检查是否用了 field(default_factory=list)")

    print("\n=== 任务 3：环境变量读取 ===")
    # 临时设置环境变量
    os.environ["MY_API_KEY"] = "sk-test-12345"
    client = ApiClient()
    print(f"base_url = {client.base_url}")
    # 如果你添加了 api_key，下面这行应该生效：
    # print(f"api_key = {client.api_key}")

    print("\n🎉 三个任务全部通过！")
