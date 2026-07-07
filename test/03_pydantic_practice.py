"""
实践 1.3：Pydantic 数据验证

任务：定义一个文档导入请求的 Pydantic 模型，体验类型校验和默认值。
运行命令: uv run python test/03_pydantic_practice.py
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional


# ============================================================
# 任务 1：定义基础请求模型
# 仿照项目中的请求模型，定义 ImportRequest：
#   - task_id: str（必填）
#   - file_path: str（必填）
#   - max_chunk_size: int = 2000（可选，默认 2000）
#   - tags: list[str] = []（可选，默认空列表）
# ============================================================

# TODO: 定义 ImportRequest(BaseModel)
class ImportRequest(BaseModel):
    task_id: str
    file_path: str
    max_chunk_size: int = 2000
    tags: list[str] = []

    @field_validator("max_chunk_size")
    @classmethod
    def check_chunk_size(cls, v):
        if v < 100 or v > 1000:
            raise ValueError("max_chunk_size 必须在 100-1000之间")
        return v
    

# ============================================================
# 任务 2：添加字段校验器
# 给 ImportRequest 加一个 field_validator：
#   - max_chunk_size 必须在 100-10000 之间
#   - 不合法时抛出 ValueError("max_chunk_size 必须在 100-10000 之间")
# ============================================================

# TODO: 添加 @field_validator("max_chunk_size")
class ImportRequest(BaseModel):
    task_id: str
    file_path: str
    max_chunk_size: int = 2000
    tags: list[str] = []

    @field_validator("max_chunk_size")
    @classmethod
    def check_chunk_size(cls, v):
        if v < 100 or v > 1000:
            raise ValueError("max_chunk_size 必须在 100-1000之间")
        return v



# ============================================================
# 任务 3：定义嵌套模型
# 定义 ProductInfo（商品信息）嵌套到 ImportRequest 中：
#   - item_name: str（必填）
#   - brand: Optional[str] = None
# 然后在 ImportRequest 中加一个可选字段 product: Optional[ProductInfo] = None
# ============================================================

# TODO: 定义 ProductInfo(BaseModel)
class ProductInfo(BaseModel):
    item_name:str
    brand: Optional[str] = None
    



# TODO: 在 ImportRequest 中添加 product 字段
class ImportRequest(BaseModel):
    task_id: str
    file_path: str
    max_chunk_size: int = 2000
    tags: list[str] = []
    product: ProductInfo = None

    @field_validator("max_chunk_size")
    @classmethod
    def check_chunk_size(cls, v):
        if v < 100 or v > 1000:
            raise ValueError("max_chunk_size 必须在 100-1000之间")
        return v



# ============================================================
# 测试代码（不要修改）
# ============================================================

if __name__ == "__main__":
    print("=== 测试 1：基础用法 ===")
    req = ImportRequest(
        task_id="task-001",
        file_path="/tmp/test.pdf",
        tags=["电子", "手册"]
    )
    print(f"task_id: {req.task_id}")
    print(f"max_chunk_size: {req.max_chunk_size}")   # 应该是 2000
    print(f"tags: {req.tags}")

    print("\n=== 测试 2：类型自动转换 ===")
    # 传字符串 "3000"，Pydantic 应该自动转成 int
    req2 = ImportRequest(
        task_id="task-002",
        file_path="/tmp/test2.pdf",
        max_chunk_size="3000"
    )
    print(f"max_chunk_size 类型: {type(req2.max_chunk_size).__name__}")
    print(f"max_chunk_size 值: {req2.max_chunk_size}")

    print("\n=== 测试 3：校验失败 ===")
    try:
        bad_req = ImportRequest(
            task_id="task-003",
            file_path="/tmp/bad.pdf",
            max_chunk_size=50   # ← 太小，应该触发校验错误
        )
        print("❌ 应该抛出 ValidationError")
    except Exception as e:
        print(f"✅ 捕获到校验错误: {e}")

    print("\n=== 测试 4：嵌套模型 ===")
    req3 = ImportRequest(
        task_id="task-004",
        file_path="/tmp/test3.pdf",
        product={
            "item_name": "Hak180 安全手册",
            "brand": "Hakko"
        }
    )
    print(f"product.item_name: {req3.product.item_name}")
    print(f"product.brand: {req3.product.brand}")

    print("\n🎉 四个测试全部通过！")
