# 📒 学习笔记本

> 由 Codojo 自动整理，按章节组织。学习过程中随时说"记一下"即可添加笔记。

## 项目概览

## Python 工程基础

- **[S1 · 2026-07-03] dataclass 三种默认值写法**：`@dataclass` 自动生成 `__init__`/`__repr__`/`__eq__`。默认值分三种场景：简单不可变类型直接写 `= 默认值`；可变类型（list/dict/set）必须用 `field(default_factory=list)` 避免多实例共享同一个对象——根因是 Python 函数默认参数只在定义时求值一次；运行时确定的值（如环境变量）用 `field(default_factory=lambda: os.getenv("KEY"))`。项目 `config.py` 中实战：`get_config()` 用全局变量 + 懒初始化实现单例模式。
- **[S3 · 2026-07-03] 异常类为什么不用 @dataclass**：`Exception` 类重写了 `__new__`/`__init__`，内部用 `self.args` 元组存储位置参数，这是异常能被 pickle 序列化、被框架依赖 `e.args` 获取信息的基础。`@dataclass` 会覆盖 `__init__`，破坏 `args` 的默认行为和 pickle 兼容性。项目中异常类一律手写 `__init__` + `super().__init__(message)`，既保留 Exception 标准行为，又添加 `node_name`/`cause` 等自定义字段。一句话：异常是控制流的一部分，不是数据容器。
- **[S3 · 2026-07-03] Pydantic vs dataclass 核心区别**：`@dataclass` 目的是简化类定义（省样板代码），类型注解只是"提示"不强制；Pydantic `BaseModel` 目的是**运行时数据验证 + 序列化**，类型不匹配会抛 `ValidationError`。在 FastAPI 中，Pydantic 模型直接做请求体校验（失败自动返回 422）+ 自动生成 Swagger 文档。项目中：`config.py` 用 dataclass（纯配置容器），API 层用 Pydantic（需要校验）。

## LangGraph 工作流

- **[S3 · 2026-07-03] BaseNode 模板方法模式**：`__call__` 定义固定骨架（日志→process→异常包装），`process()` 由子类实现业务逻辑。`__call__` 让实例可调用（`node(state)`），LangGraph 就这样调用节点。三个设计点——① 日志命名空间 `import.{name}` 便于按节点过滤日志；② 子类零样板代码（无 try/except/日志/配置注入）；③ 异常自动包装为带 `node_name` 的 `ImportProcessError`。

## RAG 与 AI 基础

## 导入管线

- **[S3 · 2026-07-03] MD 图片处理：多模态 VL + MinIO**：PDF 转 MD 后图片是本地路径，需两步处理——① 用 VL 模型（qwen3-vl-flash）理解图片内容生成文字描述；② 上传图片到 MinIO（兼容 S3 协议的对象存储）获得可访问 URL。最终 MD 中图片标签变成 URL + 文字描述。项目用 `requests_per_minute` 控制 VL 模型 API 调用频率避免限流。
- **[S3 · 2026-07-03] 文档切片：智能分块策略**：长文档切小块（chunk），核心参数 `chunk_size`（每块大小）和 `chunk_overlap`（重叠量，防止关键信息落在切分边界丢失）。项目用 LangChain `RecursiveCharacterTextSplitter` 按分隔符优先级（段落→行→句号→空格）切分，保证每块语义完整。短内容（<500字）会被合并避免碎片化。好的切片直接决定 RAG 检索质量，占系统效果的 ~40%。
- **[S3 · 2026-07-03] 主体识别：LLM 提取产品名**：入库时让 LLM 从文档开头几段自动提取产品名称（`item_name`），存入 Milvus 作为过滤标签——搜索时按产品名过滤避免跨产品的结果混杂。不是用正则匹配（产品名千奇百怪），而是靠 LLM 语义理解。只取开头几段省 token，识别不到返回"未知产品"兜底。

## 检索管线

## Web 服务与部署

## 其他
