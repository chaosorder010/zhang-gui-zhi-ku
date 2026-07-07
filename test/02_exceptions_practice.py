"""
实践 1.2：自定义异常层级

任务：仿照项目的 ImportProcessError 结构，定义一个异常体系，
    模拟节点中的异常包装行为。
运行命令: uv run python test/02_exceptions_practice.py
"""


# ============================================================
# 任务 1：定义基础异常
# 完成以下 MyBaseError，要求带 message、cause 属性
# ============================================================

# TODO: 定义 MyBaseError(Exception)
#   __init__ 参数: message, cause=None
#   属性: self.message, self.cause
#   __str__: 返回 f"{self.message} (caused by {self.cause})"
class MyBaseError(Exception):
    def __init__(self, message, cause=None):
        self.message = message
        self.cause = cause
    def __str__(self):
        return f"{self.message} (caused by {self.cause})"

# ============================================================
# 任务 2：定义异常层级结构
# 仿照项目的结构，定义两类子异常：
#   - ConfigError: 配置错误（增加 param_name 字段）
#   - NetworkError: 网络错误（增加 url 字、timeout 字段）
# ============================================================

# TODO: 定义 ConfigError(MyBaseError)
#   额外属性: param_name (str)
#   __str__: 返回 f"配置错误 [{self.param_name}] {self.message}"
class ConfigError(MyBaseError):
    def __init__(self, message, cause=None, param_name:str = ''):
        super().__init__(message, cause)
        self.param.name = param_name
    
    def __str__(self):
        return f"配置错误[{self.param_name}] {self.message}"
    
# TODO: 定义 NetworkError(MyBaseError)
#   额外属性: url (str), timeout (float)
#   __str__: 返回 f"网络错误 [url={self.url}, timeout={self.timeout}s] {self.message}"
class NetworkError(MyBaseError):
    def __init__(self, message, cause=None, url: str = '', timeout: float = 0.0):
        super().__init__(message, cause)
        self.url = url
        self.timeout = timeout

    def __str__(self):
        return f"网络错误[url={self.url}, timeout={self.timeout}s {self.message}]"
    
# ============================================================
# 任务 3：模拟 BaseNode 的异常包装逻辑
# 模拟一个"连接数据库"的节点，当发生原始异常时自动包装成自定义异常
# ============================================================

def simulate_database_connection(fail: bool = False):
    """模拟数据库连接"""
    try:
        if fail:
            raise ConnectionError("Connection refused at 127.0.0.1:5432")
        return "连接成功！"
    except ConnectionError as e:
        # TODO: 捕捉原始异常，包装成 NetworkError
        # 提示：url="postgresql://127.0.0.1:5432", timeout=30.0
        raise NetworkError(
            "数据库连接失败",
            e,
            url="postgresql://127.0.0.1:5432",
            timeout=30.0
        )


# ============================================================
# 任务 4：测试按粒度捕获
# ============================================================

def test_catch_by_type():
    """演示不同粒度的捕获策略"""
    try:
        simulate_database_connection(fail=True)
    except NetworkError as e:
        print(f"✅ 精确捕获 NetworkError: {e}")
    except MyBaseError as e:
        print(f"🔸 兜底捕获 MyBaseError: {e}")
    except Exception as e:
        print(f"🔸 兜底 Exception: {e}")


def test_catch_all_my_errors():
    """演示统一捕获所有自定义异常"""
    try:
        # 模拟两个不同的错误
        try:
            raise ConfigError("缺少必填参数", param_name="DB_HOST")
        except Exception as e:
            raise e
    except MyBaseError as e:
        print(f"✅ 统一捕获所有自定义异常: {e}")


# ============================================================
# 运行测试（不要修改以下代码）
# ============================================================

if __name__ == "__main__":
    print("=== 测试 1：数据库连接失败场景 ===")
    test_catch_by_type()

    print("\n=== 测试 2：配置错误统一捕获 ===")
    try:
        raise ConfigError("缺少必填参数", param_name="DB_HOST")
    except Exception as e:
        print(f"捕获到: {e}")
        print(f"  - 异常类型: {type(e).__name__}")
        print(f"  - 是否 ConfigError? {isinstance(e, ConfigError)}")
        print(f"  - 是否 MyBaseError? {isinstance(e, MyBaseError)}")

    print("\n=== 测试 3：模拟 NetworkError ===")
    try:
        simulate_database_connection(fail=True)
    except MyBaseError as e:
        print(f"✅ 捕获: {e}")
        print(f"  - cause 类型: {type(e.cause).__name__ if e.cause else 'None'}")

    print("\n🎉 如果你能看到以上所有输出，说明异常体系工作正常！")
