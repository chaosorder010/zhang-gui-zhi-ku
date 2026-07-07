# 学习计划

> 根据你的能力评估自动生成，已掌握内容已跳过或简化。

## 学习概要

- **总知识点数**：25 个
- **预计学时**：约 20-25 小时
- **学习路径**：工程基础 → 导入管线框架 → 导入管线节点 → RAG 理论基础 → 检索管线 → Web 服务与部署
- **核心理念**：先骨架后血肉，先导入后检索，先理论后实践

## 模块 0：项目全景

### 0.1 项目全景：分层结构与模块关系
- **类型**：纯理论（无实践任务）
- **难度**：⭐
- **前置知识**：无
- **学习目标**：建立项目整体认知——知道项目分了哪几层、各自职责、为什么这样分
- **理论要点**：
  - 从项目根目录出发，介绍四层架构（API → Processor → Utils → Data）
  - 导入管线 vs 检索管线 两大工作流的区别与联系
  - 各模块职责：web/、processor/、utils/、各中间件
  - 技术选型背后的设计意图（为什么 FastAPI 而不是 Flask、为什么 LangGraph 而不是手写流程）
- **涉及文件**：项目根目录结构、`1.笔记/01【掌柜智库】项目简介.md`

---

## 模块 1：Python 工程基础

> 在深入项目代码之前，先补齐三个核心的 Python 工程模式。

### 1.1 dataclass 数据类：从零到掌握
- **类型**：理论 + 实践
- **难度**：⭐⭐
- **前置知识**：Python 基础语法（类、装饰器）
- **学习目标**：理解 `@dataclass` 的作用和 `field()` 的三个使用场景，能读懂并修改 `config.py`
- **理论要点**：
  - `@dataclass` 如何简化类的定义（自动生成 `__init__`、`__repr__`）
  - `field()` 三种用法：简单默认值、`default_factory` 可变类型、`lambda` 环境变量
  - 单例模式：`get_config()` 如何用全局变量 + 懒初始化实现单例
- **实践任务**：在 `config.py` 中添加一个新配置项（如日志级别），感受 `field(default_factory=...)` 的写法
- **涉及文件**：`processor/import_processor/config.py`

### 1.2 自定义异常层级：从 try/except 到异常体系
- **类型**：理论 + 实践
- **难度**：⭐⭐
- **前置知识**：Python try/except 基础
- **学习目标**：理解项目异常层级的设计意图，能设计类似的异常体系
- **理论要点**：
  - 为什么需要自定义异常（统一错误格式、按类型捕获、携带上下文）
  - 异常层级设计：基类 `ImportProcessError` → 分类子类 → 具体异常
  - 异常链：`cause` 参数保留原始异常，`node_name` 定位出错节点
  - `__str__` 如何拼接 `[节点名]` + 消息 + `(原因: xxx)`
- **实践任务**：在 `exceptions.py` 中新增一个异常子类（如 `NetworkTimeoutError`），并在某个节点中模拟抛出
- **涉及文件**：`processor/import_processor/exceptions.py`

### 1.3 Pydantic 数据验证：从入门到使用
- **类型**：理论 + 实践
- **难度**：⭐⭐
- **前置知识**：Python 类定义、类型提示
- **学习目标**：理解 Pydantic 的 `BaseModel` 用法，能读懂 API 层的请求/响应模型
- **理论要点**：
  - `BaseModel` 自动类型校验 + 序列化
  - 与 `dataclass` 的区别（Pydantic 侧重数据验证，dataclass 侧重简化类定义）
  - Pydantic 在 FastAPI 中的角色（自动生成 API 文档、请求校验）
- **实践任务**：定义一个 Pydantic 模型（如 `ImportRequest`），包含必填字段和可选字段，测试类型校验
- **涉及文件**：FastAPI 路由文件中的请求/响应模型

---

## 模块 2：导入管线骨架

> 理解 LangGraph 工作流的框架层——状态、节点、图的编译与执行。

### 2.1 状态设计：ImportGraphState 数据契约
- **类型**：理论 + 实践
- **难度**：⭐⭐
- **前置知识**：TypedDict（已掌握）、模块 1 的 dataclass
- **学习目标**：理解图状态的设计思路——为什么用 TypedDict、字段如何分类、如何避免全局污染
- **理论要点**：
  - `TypedDict(total=False)` 让所有字段可选 → 节点只需更新自己关心的字段
  - 字段分类：任务标识 / 控制标志 / 路径信息 / 文件信息 / 中间数据
  - `copy.deepcopy()` 创建独立副本避免共享污染
  - `create_default_state()` 工厂函数模式
- **实践任务**：在 `state.py` 中添加一个新字段（如 `log_level`），更新默认状态和工厂函数
- **涉及文件**：`processor/import_processor/state.py`

### 2.2 BaseNode 基类：模板方法模式实战
- **类型**：理论 + 实践
- **难度**：⭐⭐
- **前置知识**：ABC（已掌握）、模块 1 的异常设计
- **学习目标**：理解 `__call__` + `process` 的模板方法设计，以及日志、异常的统一包装
- **理论要点**：
  - 模板方法模式：`__call__` 定义执行骨架（日志→执行→异常包装），`process` 由子类实现
  - `logging.getLogger(f"import.{self.name}")` 命名空间设计
  - `colorlog` 彩色日志配置
  - `__call__` 中 `ImportProcessError` 自动包装非自定义异常
- **实践任务**：创建一个新的节点类继承 `BaseNode`，实现空的 `process` 方法，用日志验证基类的统一行为
- **涉及文件**：`processor/import_processor/base.py`

### 2.3 LangGraph 工作流编译：从节点到有向图
- **类型**：理论 + 实践
- **难度**：⭐⭐⭐
- **前置知识**：LangGraph 基本概念（已了解）
- **学习目标**：理解 `StateGraph` 的构建流程——注册节点、设置入口、条件路由、编译
- **理论要点**：
  - `StateGraph(ImportGraphState)` 绑定状态类型
  - `add_node()` 注册节点实例
  - `set_entry_point()` 指定入口
  - `add_conditional_edges()` 条件路由：根据 state 字段值决定下一个节点
  - `add_edge()` 顺序边：固定执行顺序
  - 懒加载编译：`@property graph` 只在首次使用时编译
- **实践任务**：在 `main_graph.py` 中添加一个调试打印，输出编译后的图结构（`get_graph().print_ascii()`）
- **涉及文件**：`processor/import_processor/main_graph.py`

### 2.4 骨架串联：端到端走一遍空节点流程
- **类型**：纯实践
- **难度**：⭐⭐
- **前置知识**：2.1-2.3
- **学习目标**：用实际运行验证对骨架的理解——7 个空节点 + 条件路由 + 日志输出
- **理论要点**：（无新理论，串联前面 3 个知识点）
- **实践任务**：运行 `main_graph.py`，观察日志中每个节点的 `--- xxx 开始 ---` 和 `--- xxx 完成 ---`，理解执行顺序
- **涉及文件**：`processor/import_processor/main_graph.py`、所有 `nodes/node_*.py`

---

## 模块 3：导入管线节点

> 逐个理解 7 个业务节点的职责和实现。

### 3.1 入口分发 + PDF 转 Markdown
- **类型**：理论 + 实践
- **难度**：⭐⭐
- **前置知识**：模块 2 的骨架
- **学习目标**：理解任务分发逻辑（PDF/MD/其他）和 MinerU PDF 解析的集成方式
- **理论要点**：
  - `node_entry`：检测文件类型，设置 `is_pdf_read_enabled` / `is_md_read_enabled` 控制标志
  - `node_pdf_to_md`：调用 MinerU API 将 PDF 转为 Markdown，处理转换结果
  - 条件路由如何根据控制标志选择路径
- **实践任务**：阅读入口节点的完整代码，画出从 state 输入到控制标志设置的流程图
- **涉及文件**：`processor/import_processor/nodes/node_entry.py`、`node_pdf_to_md.py`

### 3.2 MD 图片处理：多模态视觉理解 + MinIO
- **类型**：理论 + 实践
- **难度**：⭐⭐⭐
- **前置知识**：3.1
- **学习目标**：理解多模态 LLM（VL 模型）如何理解图片内容，以及 MinIO 对象存储的角色
- **理论要点**：
  - MD 中图片标签的识别和提取
  - VL 模型（qwen3-vl-flash）的调用：图片 → 文本描述
  - MinIO 上传：图片文件 → 对象存储 → 返回访问 URL
  - 图片 URL 替换：MD 中的本地路径 → MinIO URL
- **实践任务**：跟踪一次图片处理的数据流（图片路径 → VL 调用 → MinIO 上传 → URL 替换）
- **涉及文件**：`processor/import_processor/nodes/node_md_img.py`

### 3.3 文档切片：智能分块策略
- **类型**：理论 + 实践
- **难度**：⭐⭐
- **前置知识**：3.1、3.2
- **学习目标**：理解 LangChain text splitters 的分块策略和参数含义
- **理论要点**：
  - 为什么需要切片（LLM 上下文窗口有限、检索精度）
  - `chunk_size` vs `chunk_overlap` 的权衡
  - 句子级切分：按自然语言边界而非字符数切割
  - 短内容合并策略
- **实践任务**：调整 `max_content_length` 参数值，观察切片数量的变化
- **涉及文件**：`processor/import_processor/nodes/node_document_split.py`

### 3.4 主体识别：LLM 驱动的实体提取
- **类型**：理论 + 实践
- **难度**：⭐⭐
- **前置知识**：3.1-3.3
- **学习目标**：理解如何用 LLM 从文档中自动识别"商品/产品名称"作为知识库标签
- **理论要点**：
  - 为什么需要主体识别（多产品场景下按产品名过滤检索结果）
  - Prompt 设计：让 LLM 从文档片段中提取产品名
  - `item_name` 如何在后续流程中使用（作为 Milvus 的过滤条件）
- **实践任务**：阅读主体识别的 Prompt，尝试用自己的话描述 Prompt 的每个部分在做什么
- **涉及文件**：`processor/import_processor/nodes/node_item_name_recognition.py`

### 3.5 向量化 + 入库：BGE-M3 混合向量与 Milvus 写入
- **类型**：理论 + 实践
- **难度**：⭐⭐⭐
- **前置知识**：3.1-3.4、建议与 4.1 配合学习
- **学习目标**：理解 BGE-M3 的稠密+稀疏双向量机制，以及 Milvus 的数据写入流程
- **理论要点**：
  - BGE-M3 输出两个向量：dense（语义相似度，1024 维）+ sparse（关键词匹配，BM25 风格）
  - 批量向量化：`embedding_batch_size` 控制批次大小
  - Milvus Collection 的Schema 设计（哪些字段、什么类型）
  - `insert()` 写入向量 + 元数据
- **实践任务**：阅读 BGE-M3 调用代码和 Milvus insert 代码，画出"文本→向量→Milvus"的数据流
- **涉及文件**：`processor/import_processor/nodes/node_bge_embedding.py`、`node_import_milvus.py`

---

## 模块 4：RAG 与 AI 基础理论

> 填补你最大的知识空白——向量、LangChain、RAG 全链路。

### 4.1 Embedding 与向量相似度搜索：从"听不懂"到"讲给别人听"
- **类型**：纯理论
- **难度**：⭐⭐
- **前置知识**：无
- **学习目标**：从零理解什么是 Embedding、向量相似度、为什么能"搜意思不搜关键词"
- **理论要点**：
  - Embedding 是什么：把文本映射到高维空间中的坐标点
  - 语义相似 ≈ 空间距离近：余弦相似度、欧氏距离
  - 稠密向量（语义级）vs 稀疏向量（关键词级）各自擅长什么
  - 混合检索为什么更准：语义 + 关键词互补
  - 用生活中的例子类比（不涉及数学公式）
- **实践任务**：无（纯理论）
- **涉及文件**：无特定文件

### 4.2 LangChain 框架入门：LLM 调用的统一抽象
- **类型**：理论 + 实践
- **难度**：⭐⭐
- **前置知识**：无（听说过即可）
- **学习目标**：理解 LangChain 在项目中的角色——它不是什么"黑魔法"，而是 LLM 调用的统一接口
- **理论要点**：
  - `ChatOpenAI`：统一的 LLM 调用接口（兼容 OpenAI / DashScope 等多种后端）
  - `PromptTemplate`：模板化 Prompt，变量插值
  - `LLMChain`：Prompt + LLM 的组合
  - LangChain 在项目中的实际使用位置（各节点的 LLM 调用）
- **实践任务**：写一个独立的 Python 脚本，用 LangChain 调用一次 LLM（用项目已有的配置）
- **涉及文件**：各 `node_*.py` 中的 LLM 调用代码

### 4.3 RAG 全链路：从文档到答案的完整旅程
- **类型**：理论 + 实践
- **难度**：⭐⭐⭐
- **前置知识**：4.1 Embedding、4.2 LangChain
- **学习目标**：把前面学的"零件"串成一条完整的 RAG 链路
- **理论要点**：
  - 离线阶段（导入）：文档 → 切片 → 向量化 → 存入向量库
  - 在线阶段（检索）：问题 → 向量化 → 相似度搜索 → 召回片段 → 拼接 Prompt → LLM 生成答案
  - 本项目中的多路召回策略：向量检索 + HyDE + Web 搜索
  - 重排序（Rerank）的作用：对多路结果精排，截断低质量结果
- **实践任务**：在纸上画出"用户提问 → 最终答案"的完整数据流，标注每一步的数据形态变化
- **涉及文件**：导入管线 + 检索管线的全部节点

---

## 模块 5：检索管线

> 理解查询流程的每个节点——从用户提问到最终答案。

### 5.1 检索管线骨架：状态定义 + 工作流结构
- **类型**：理论 + 实践
- **难度**：⭐⭐
- **前置知识**：模块 2（导入管线骨架）
- **学习目标**：对比导入管线，理解检索管线的状态字段和流程差异
- **理论要点**：
  - `QueryGraphState` vs `ImportGraphState`：字段对比
  - 检索流程：产品确认 → 多路搜索(并行) → 结果融合 → 重排序 → 答案生成
  - 并行节点设计：向量搜索、HyDE 搜索、Web 搜索同时进行
- **实践任务**：对比两个 main_graph.py，找出结构上的 3 个相同点和 3 个不同点
- **涉及文件**：`processor/query_processor/state.py`、`main_graph.py`

### 5.2 向量检索节点：混合搜索实战
- **类型**：理论 + 实践
- **难度**：⭐⭐⭐
- **前置知识**：4.1 Embedding、5.1 检索骨架
- **学习目标**：理解 Milvus 的混合检索（dense_vector + sparse_vector）如何实现
- **理论要点**：
  - 查询向量化：用户问题 → BGE-M3 → dense + sparse 双向量
  - Milvus `search()` 参数：`anns_field`、`limit`、`output_fields`
  - 混合检索的权重配置
  - `item_name` 过滤：限定搜索范围到指定产品
- **实践任务**：画一个时序图，描述"用户输入问题 → 向量化 → Milvus 搜索 → 返回结果"的完整调用链
- **涉及文件**：`processor/query_processor/nodes/node_milvus_search.py`

### 5.3 HyDE + Web 搜索：多路召回的两条支线
- **类型**：理论 + 实践
- **难度**：⭐⭐⭐
- **前置知识**：5.2
- **学习目标**：理解 HyDE 的"假设性文档"策略和 MCP Web 搜索的集成
- **理论要点**：
  - HyDE 原理：让 LLM 先"编"一个假设性答案 → 用这个答案去检索 → 比直接用问题检索更准
  - 为什么 HyDE 有效：假设性答案和真实文档在向量空间中更接近
  - MCP（Model Context Protocol）Web 搜索：LLM 自主决定搜索关键词 → 调用搜索引擎 → 获取网页内容
  - `asyncio` 异步在 Web 搜索中的应用
- **实践任务**：给自己的一个问题写一个"假设性答案"，理解 HyDE 的直觉
- **涉及文件**：`processor/query_processor/nodes/node_hyde_search.py`、`node_web_search.py`

### 5.4 RRF 融合 + Rerank 重排序：多路结果的"裁判"
- **类型**：理论 + 实践
- **难度**：⭐⭐⭐
- **前置知识**：5.2、5.3
- **学习目标**：理解 RRF 融合算法和 BGE-Reranker 的重排序+断崖检测机制
- **理论要点**：
  - RRF（Reciprocal Rank Fusion）：加权融合多路结果，取各路排名的倒数作为分数
  - 为什么需要 RRF：不同来源的相似度分数不可直接比较（向量距离 ≠ BM25 分数）
  - BGE-Reranker：交叉编码器，对 query-doc 对重新打分
  - 断崖检测（Cliff Detection）：相邻文档分差过大时自动截断，只保留 Top-K 高质量结果
- **实践任务**：用 3 个搜索结果列表手动计算一次 RRF 融合，感受算法逻辑
- **涉及文件**：`processor/query_processor/nodes/node_rrf.py`、`node_rerank.py`

### 5.5 答案生成 + 对话历史：从片段到完整回答
- **类型**：理论 + 实践
- **难度**：⭐⭐
- **前置知识**：5.4、模块 1.3 Pydantic
- **学习目标**：理解如何将检索到的片段拼入 Prompt，以及 MongoDB 对话历史管理
- **理论要点**：
  - Prompt 组装：System Prompt + 检索片段(Reference) + 用户问题 + 对话历史
  - SSE 流式输出：逐 token 推送，前端实时渲染
  - MongoDB 存储对话历史：`session_id` + `message_id` 结构
  - 对话上下文的窗口管理（保留最近 N 轮）
- **实践任务**：手写一个完整的 Prompt，包含 system、context、history、question 四个部分
- **涉及文件**：`processor/query_processor/nodes/node_answer.py`

---

## 模块 6：Web 服务与部署

> 从代码到可运行的服务——API、SSE、Docker。

### 6.1 FastAPI 异步编程：从"会用"到"理解"
- **类型**：理论 + 实践
- **难度**：⭐⭐⭐
- **前置知识**：用过 FastAPI（已具备）
- **学习目标**：理解 `async/await` 的核心原理——为什么异步适合 I/O 密集型场景
- **理论要点**：
  - 同步 vs 异步：阻塞等待 vs 事件循环
  - `async def` → 协程函数，`await` → 挂起当前协程，让出执行权
  - FastAPI 自动将 `async def` 端点跑在 asyncio 事件循环中
  - `StreamingResponse` 与 SSE 的异步本质：持续写数据不阻塞
- **实践任务**：写一个同步版和一个异步版的 HTTP 请求，对比耗时差异
- **涉及文件**：`web/api/import_service.py`、`web/api/query_service.py`

### 6.2 导入 API：文件上传 + 异步任务 + SSE 进度推送
- **类型**：理论 + 实践
- **难度**：⭐⭐⭐
- **前置知识**：6.1、模块 2 导入骨架
- **学习目标**：理解导入接口的完整请求处理流程——从文件上传到流程完成
- **理论要点**：
  - FastAPI `UploadFile` 文件上传
  - 后台异步任务执行 LangGraph 工作流
  - SSE 推送任务进度（`add_running_task` / `add_done_task`）
  - CORS 中间件配置
- **实践任务**：用浏览器打开 `/docs` 查看 Swagger 文档，测试上传接口
- **涉及文件**：`web/api/import_service.py`、`utils/sse_utils.py`、`utils/task_utils.py`

### 6.3 查询 API：流式问答 + 会话管理
- **类型**：理论 + 实践
- **难度**：⭐⭐⭐
- **前置知识**：6.1、模块 5 检索管线
- **学习目标**：理解流式问答接口的设计——SSE 逐字输出 + session 管理
- **理论要点**：
  - `/query` POST 接口：接收问题 + session_id
  - `StreamingResponse` + SSE 格式：`data: {...}\n\n`
  - 前端 EventSource 消费 SSE 流
  - `session_id` 关联 MongoDB 对话历史
- **实践任务**：用 curl 或浏览器测试流式问答接口，观察 SSE 输出的原始格式
- **涉及文件**：`web/api/query_service.py`

### 6.4 Docker 基础设施：Milvus 全家桶深度解析
- **类型**：理论 + 实践
- **难度**：⭐⭐
- **前置知识**：会用 docker-compose（已具备）
- **学习目标**：深入理解 docker-compose.yml 中每个服务的作用和它们之间的依赖关系
- **理论要点**：
  - etcd：Milvus 的元数据存储（集合 Schema、索引信息）
  - MinIO：Milvus 的数据持久化（向量数据、索引文件）
  - Milvus Standalone：向量数据库核心服务
  - Attu：Milvus 的 Web 管理界面（可视化查看 Collection、执行搜索）
  - 服务间依赖关系：etcd + MinIO 先启动 → Milvus → Attu
  - 健康检查机制：`healthcheck` 确保依赖就绪
- **实践任务**：逐个进入每个服务的容器，观察日志输出，验证服务间通信
- **涉及文件**：`docker-compose.yml`
