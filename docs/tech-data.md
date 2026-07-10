# 技术/数据说明

## 技术栈选型

| 层 | 选型 | Rationale |
|---|---|---|
| PDF 解析 | MinerU | 中文 PDF 解析强, 处理表格/双栏/图片 |
| Embedding | 本地中文 embedding 模型 | 中文优化, 本地 GPU 跑 |
| 向量库 | Milvus | 支持稠密+稀疏混合检索, 功能强 |
| 文档库 | MongoDB | 存文档元数据/对话历史 |
| 对象存储 | MinIO | 存图片 |
| 重排序 | BGE-Reranker-Large / Qwen3-Reranker | 中文精排效果好 |
| LLM | 云端 API | LangChain 调用, 不需本地 GPU 跑 LLM |
| 编排 | LangGraph | 状态机编排: 对话历史、路由决策、重试 |
| LLM 封装 | LangChain | 云端 LLM API 调用、embedding、rerank 封装 |
| 后端 | FastAPI | 异步 Python API |
| 前端 | HTML + CSS + JS | 轻量, 几周交付够用 |
| **测试** | **pytest + httpx + TestClient** | **标准 Python 测试栈** |

## 路线

Route C 混合栈: 本地 embedding + 云端 LLM。不需要隐私保护。

## 检索架构

三路并行:

| 路 | query 构造 | 目标 | top-K |
|---|---|---|---|
| 路1 | 原始 query | Milvus 混合检索 (稠密+稀疏) | 20 |
| 路2 | HyDE 假设文档 | Milvus | 20 |
| 路3 | 原始 query | MCP 网络搜索 (外网) | 10 |

**RRF 倒数排名融合**: score(d) = Σ 1/(k + rank_i(d))
**Rerank 精排**: BGE-Reranker-Large / Qwen3-Reranker 二阶段排序

## 主体识别

- 导入时识别一次 item name
- 存入 Milvus `item_name` 常量字段
- embedding 时拼到 chunk 开头

## 数据模型 (Milvus collection)

| 字段 | 类型 | 说明 |
|---|---|---|
| id | INT64 | 主键 |
| dense_vector | FLOAT_VECTOR | 稠密向量 |
| sparse_vector | SPARSE_FLOAT_VECTOR | 稀疏向量 |
| text | VARCHAR | chunk 文本 |
| item_name | VARCHAR | 主体名 (常量字段) |
| doc_name | VARCHAR | 文档名 |
| chunk_id | INT64 | chunk 序号 |

## API 表面

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/ask` | 问答, 多轮 |
| POST | `/api/upload` | 上传文档 |
| GET | `/api/documents` | 文档列表 |
| DELETE | `/api/documents/{id}` | 删除文档 (P1) |

## 测试策略

### 分层

```
┌─────────────────────────────────────┐
│ E2E (手动, 真实 LLM API)           │  ← 单独脚本, 不跑 CI
├─────────────────────────────────────┤
│ 集成 (FastAPI TestClient, mock LLM) │  ← pytest -m integration
├─────────────────────────────────────┤
│ 单元 (纯函数, ms 级)                │  ← pytest -m unit
└─────────────────────────────────────┘
```

### Seam 清单

- `apps.backend.routers.ask.ask` — API 输入/输出，mock 掉 graph
- `apps.backend.services.graph` — 多轮记忆编排，mock 掉 LLM
- `apps.backend.services.llm.build_llm` — LLM 工厂，不测（只是 new 对象）
- 分块函数（后续）— 纯函数，独立测
- 检索融合（后续）— RRF/rerank 纯函数，独立测
- 解析函数（后续）— MinerU wrapper，mock 外部调用

### Mock 规则

- **Mock 外部边界**: LLM API、Milvus、MongoDB、MinerU、MCP
- **不 mock 内部**: 同一层 Python 对象互相调用，走真实；只 mock 出层边界

### 文件布局

```
apps/backend/
  tests/
    conftest.py              # 共享 fixture (TestClient, mock LLM 等)
    unit/
      test_chunking.py
      test_rrf.py
    integration/
      test_ask_router.py
      test_graph.py
```

### 运行命令

```bash
pytest -m unit                # 单元，CI 必跑
pytest -m integration         # 集成，CI 必跑
pytest --cov=apps.backend     # 覆盖率，阈值 80%
python scripts/e2e_test.py    # E2E，真实 LLM，手动触发
```

## 部署

- Docker Compose: FastAPI + Milvus + MongoDB + MinIO + 前端
- NVIDIA GPU 跑 embedding + rerank
- 云端 LLM API 调 embedding (可选) + 生成
