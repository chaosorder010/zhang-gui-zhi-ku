# 变更记录

## 2026-07-10

### Baseline-2 启动: LangGraph 编排导入工作流

- **决策**: 后端用 LangGraph 状态机编排导入链路
  - 节点: extract_with_mineru → recognize_item → chunk → embed → store_milvus
  - ImportState 持久化 checkpoint, 失败可重试
- **决策**: MinerU 改用云 API, 调用 `/api/v4/file-urls/batch` 申请上传 URL → PUT → 轮询
  - Why: 无需本地 GPU + 模型下载
- **决策**: Milvus Standalone (轻量)

### Slices 2-5 完成: recognizer + mineru_client + LangGraph + upload router

- Slice 2: recognizer (LLM 抽主体名, mock LLM) — 7 tests
- Slice 3: mineru_client (MinerU v4 API: 申请URL→PUT上传→轮询→下载zip→解压md) — 10 tests
- Slice 4: import_workflow (LangGraph 状态机编排: extract→recognize→chunk→embed→store) — 12 tests
- Slice 5: upload router (POST /api/upload + GET /api/documents, 后台触发 workflow) — 4 tests
- 总: 53 tests, 1.32s

### Slice 1 完成: chunker + retriever TDD

- `chunker.chunk_by_section`: 按 `##` 标题深度切分, 每块头拼 `[item_name]`, 兜底 max_chars 切
- `retriever.rrf_fuse`: RRF 倒数排名融合, 支持 top_k
- 测试: unit 20/20 通过 (0.10s)

### 初始设计

- **决策**: 选 Route C 混合栈 (本地 embedding + 云端 LLM)
  - **Why**: 不需要隐私保护，云端 LLM 效果优，开发速度快
- **框架**: LangChain + LangGraph
  - **Why**: 编排多轮对话，抽象层加速开发（页码溯源不需要，无碍）
- **向量库**: Milvus（非 Qdrant）
  - **Why**: 支持稠密+稀疏混合检索，功能更强
- **PDF 解析**: MinerU（非 PyMuPDF）
  - **Why**: 中文 PDF 解析强，处理表格/双栏/图片
- **重排序**: BGE-Reranker-Large / Qwen3-Reranker
- **去除页码溯源**: 不需要精确到页
- **文档数据库**: MongoDB
- **对象存储**: MinIO 存图片
- **检索增强**: 三路检索（稠密+稀疏+HyDE）+ MCP 网络搜索，RRF 融合

### 空结果处理澄清

- **变更**: Milvus 无结果或全低分 → 直接回"知识库无此信息", 不调 LLM 兜底
  - **Why**: 电子产品维修场景错误信息代价高, 宁缺勿错

### 分块策略澄清

- **变更**: 三层分块 (标题切分 → 超长二次切 → 过短合并)
  - **Why**: MinerU 输出 MD 带标题层级, 可利用; 三层兜底保证 chunk 大小均匀
- **接缝**: 纯函数 `split_markdown`, 可独立单元测

### 稠密稀疏融合澄清

- **变更**: 路1 Milvus 内线性加权 `score = α·dense + (1-α)·sparse`
  - **Why**: 稠密稀疏同类排名空间, 线性加权简单可解释, α 网格搜索调参

### 框架职责澄清

- **变更**: LangGraph 做状态机编排, LangChain 做 LLM 调用封装
  - **Why**: 职责清晰, LangGraph 节点内嵌 LangChain callable, 并行不冲突

### query 主体识别澄清

- **变更**: query 也跑 LLM 抽取 item name, 匹配 Milvus `item_name` 硬过滤
  - **Why**: chunk 开头拼 item name 仅提升 embedding 权重; Milvus 字段过滤精准锁定主体
  - **fallback**: 识别失败则 filter 关, 走全量召回

### 三路检索澄清

- **变更**: 明确三路 = Milvus混合(query) + Milvus(HyDE) + MCP网络搜索
  - **Why**: 前两路同 Milvus 同 item 空间, HyDE 是 query 变体; 第三路外网不同数据源
- **RRF 公式**: score(d) = Σ 1/(k + rank_i(d))
- **top-K**: Milvus 两路各取 20, MCP 取 10

### 主体识别澄清

- **变更**: 主体识别不在检索时跑，改到导入时跑一次
- **Why**: 减轻查询时延迟，item name 作为常量字段存储
- **实现**: 导入时识别 → 拼到 chunk 开头 embedding → Milvus `item_name` 常量字段

### 前端构建决策

- **变更**: 前端不用 Vite, 改原生 HTML/CSS/JS + nginx serve static
- **Why**: 几周交付不需要构建工具链, 省 node_modules; fetch + crypto.randomUUID() 够用

### TDD 方法论引入

- **决策**: 后续开发全部 TDD
- **Why**: 用户要求，红→绿循环
- **分层**: 单元(ms 级, 纯函数) + 集成(mock 外部 LLM/Milvus, TestClient) + E2E(手动, 真实 LLM)
- **Seam**: API router, graph 编排, 分块/检索纯函数
- **Mock 规则**: 只 mock 外部边界(LLM/Milvus/MongoDB/MinerU/MCP), 不 mock 内部 collaborator
- **CI**: pytest unit + integration 必跑, 覆盖率阈值 80%; E2E 单独脚本手动触发
- **欠账**: Baseline-1 代码已写, 测试在下一循环补

### 补全护城河文档

- **变更**: 更新 5 份护城河文档, 填充项目-specific 内容
- **新增**: project-brief.md (方法论加 TDD), tech-data.md (加测试策略/分层/seam), baseline-1.md (补测试欠账 + 前端决策)

### Baseline-1 MVP 完成

- **代码**: FastAPI + LangChain + LangGraph 最小问答链路, /api/ask 多轮对话
- **前端**: 原生 HTML/CSS/JS + nginx serve static（无 Vite）
- **测试**: pytest 骨架, conftest `_force_test_env` + `lru_cache clear`, 8 测试全过 (0.07s)
  - 集成 5: router + mock graph (返回/session_id/空 key 400/空 question 422)
  - 单元 3: graph 多轮记忆 + thread_id 隔离
- **TDD 驱动改进**: `build_graph(llm=None)` 接口由测试驱动加出, 可注入 mock
- **Docker**: Dockerfile.backend + docker-compose.yml + nginx.conf
- **脚本**: scripts/setup_test_env.sh + scripts/run_tests.sh
