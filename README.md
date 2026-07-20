# 掌柜智库

> 企业级 RAG（检索增强生成）智能知识库系统
> 让维修技师用自然语言提问，几秒内从已上传的电子产品手册/维修指南中获取准确技术参数。

**核心原则：宁缺勿错** — 知识库无答案时直接告知，绝不让 LLM 编造技术参数。

---

## 目录

- [项目简介](#项目简介)
- [核心特性](#核心特性)
- [技术栈](#技术栈)
- [系统架构](#系统架构)
- [项目结构](#项目结构)
- [快速开始](#快速开始)
- [配置说明](#配置说明)
- [API 接口](#api-接口)
- [测试](#测试)
- [检索质量评估](#检索质量评估)
- [文档](#文档)
- [许可证](#许可证)

---

## 项目简介

掌柜智库是一个面向垂直领域（电子产品手册、维修指南、技术文档等）的企业级智能知识库系统。系统基于 RAG 技术，将上传的 PDF/MD/DOC/DOCX/PPT/PPTX 文档自动解析、分块、向量化入库，用户用中文自然语言提问时，通过混合检索 + 精排 + LLM 生成的方式给出准确回答，并支持多轮对话。

### 目标用户

| 角色 | 需求 |
|---|---|
| 维修技师 | 用中文自然语言提问，秒级获取准确技术参数 |
| 运维工程师 | `docker compose up` 一键部署，环境变量注入密钥 |

---

## 核心特性

### 文档导入链路（P0 已交付）

- ✅ 多格式上传：PDF / MD / DOC / DOCX / PPT / PPTX
- ✅ MinerU 解析：中文 PDF 强，处理表格 / 双栏 / 图片，输出 Markdown
- ✅ 主体识别：LLM 抽取 `item_name`（如 iPhone16），用于检索过滤
- ✅ 三层分块：按标题切 → 超长二次切 → 过短合并，`item_name` 拼头
- ✅ 混合嵌入：BGE-M3 同时产出稠密 + 稀疏向量，batch_size=32 防 OOM
- ✅ Milvus 入库：`bulk_upsert`，`doc_name` 透传
- ✅ 导入状态追踪：TTL 1h，惰性清理防内存泄漏
- ✅ Fail-fast：条件边任一节点失败直接短路到 END

### 问答链路（P0 已交付）

- ✅ 主体识别检索：query 抽 `item_name`，hybrid_search 按主体硬过滤
- ✅ 混合检索：Milvus `WeightedRanker`（0.5/0.5），L2 + IP
- ✅ 空结果兜底：无结果直接回"暂无相关信息"，绕开 LLM
- ✅ 多轮对话：`MemorySaver` + `thread_id` 隔离

### 增强能力（P1 已交付）

- ✅ HyDE 检索：LLM 生成假设答案 → 双路检索 → RRF 融合
- ✅ Rerank 精排：LLM 对 `retrieved_chunks` 按相关性重排序
- ✅ 批量上传：一次选多个文件并行入库
- ✅ 前端进度条：实时展示导入状态
- ✅ 删除文档：级联清理 Milvus chunks + 任务状态

---

## 技术栈

| 层 | 选型 | 原因 |
|---|---|---|
| 后端 | FastAPI | 异步 Python，TestClient 测 seam |
| 编排 | LangGraph | 状态机：对话历史 / 路由决策 / 重试 |
| 向量库 | Milvus 2.5 | 稠密 + 稀疏混合检索 |
| 嵌入 | BGE-M3（本地） | 中文优化，同时产出稠密 + 稀疏 |
| LLM | OpenAI 兼容（可换智谱/通义/DeepSeek/longcat） | 中文效果优，云端 API |
| 解析 | MinerU | 中文 PDF 强，处理表格 / 双栏 |
| 前端 | HTML + CSS + JS | 无构建工具链，nginx serve static |
| 部署 | Docker Compose | 单机一键起 |
| 测试 | pytest + httpx | 标准 Python 测试栈 |
| 包管理 | uv | 快速依赖安装 |

---

## 系统架构

掌柜智库由两条 LangGraph 状态机编排：

### 1. 文档导入工作流（`import_workflow.py`）

```
上传 PDF
  → extract (MinerU 解析)
  → recognize_item (LLM 抽主体名)
  → chunk (三层分块 + item_name 拼头)
  → embed (BGE-M3 稠密+稀疏)
  → store (Milvus 入库)
  → done / failed (条件边 fail-fast)
```

### 2. RAG 问答工作流（`graph.py`）

```
用户提问
  → recognize (LLM 抽 item_name)
  → [hyde | retrieve]
      ├ enable_hyde=true:  hyde (LLM 生成假设答案 → 双路检索 → RRF 融合)
      └ enable_hyde=false: retrieve (embed query → Milvus hybrid_search)
  → 条件边路由:
      有结果 → [rerank] → chatbot (chunk 拼 system prompt → LLM 生成)
      无结果 → no_results (直接回"暂无相关信息"，绕开 LLM)
```

### 部署拓扑

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  frontend    │───▶│   backend    │───▶│   milvus     │
│  (nginx)     │    │  (FastAPI)   │    │  (vector db) │
│  :5200       │    │  :8000       │    │  :19530      │
└──────────────┘    └──────────────┘    └──────────────┘
                          │
                          ├─▶ MinerU API (云端 PDF 解析)
                          ├─▶ OpenAI 兼容 LLM API
                          └─▶ 本地 BGE-M3 模型 (/models/bge-m3)
```

---

## 项目结构

```
zhang-gui-zhi-ku/
├── apps/
│   ├── backend/
│   │   ├── core/
│   │   │   └── config.py            # pydantic-settings 配置
│   │   ├── routers/
│   │   │   ├── ask.py               # POST /api/ask 问答
│   │   │   └── upload.py            # POST /api/upload 上传
│   │   ├── services/
│   │   │   ├── graph.py             # RAG 问答 LangGraph
│   │   │   ├── import_workflow.py   # 文档导入 LangGraph
│   │   │   ├── mineru_client.py     # MinerU PDF 解析
│   │   │   ├── recognizer.py        # LLM 主体识别
│   │   │   ├── chunker.py           # 三层分块
│   │   │   ├── embedder.py          # BGE-M3 嵌入
│   │   │   ├── milvus_client.py     # Milvus 混合检索
│   │   │   ├── reranker.py          # LLM 精排
│   │   │   ├── retriever.py         # RRF 融合
│   │   │   └── llm.py               # LLM 工厂
│   │   ├── eval/                    # 检索质量评估框架
│   │   ├── tests/                   # unit + integration 测试
│   │   └── main.py                  # FastAPI 入口
│   └── frontend/                    # 原生 HTML/CSS/JS 前端
│       ├── index.html
│       ├── main.js
│       ├── progress.js
│       └── style.css
├── docs/                            # 项目文档
│   ├── prd.md                       # 产品需求文档
│   ├── project-brief.md             # 项目总纲
│   ├── feature-list.md              # 功能清单
│   ├── tech-data.md                 # 技术与数据说明
│   ├── page-flow.md                 # 页面与流程
│   ├── changelog.md                 # 变更记录
│   └── adr/                         # 架构决策记录
├── scripts/
│   ├── run_tests.sh                 # 跑测试
│   ├── run_e2e.py                   # E2E 全栈集成测试
│   └── ...
├── docker-compose.yml               # 一键部署
├── Dockerfile.backend               # CPU 版后端镜像
├── Dockerfile.backend-cuda          # CUDA 版后端镜像
├── nginx.conf                       # 前端 nginx 配置
├── pyproject.toml                   # Python 依赖 (uv)
└── .env.example                     # 环境变量模板
```

---

## 快速开始

### 前置条件

- Docker + Docker Compose（部署）
- NVIDIA GPU + 驱动（可选，用于 BGE-M3 加速；无 GPU 时自动回退 CPU 或 MockEmbedder）
- MinerU API Key（[https://mineru.net](https://mineru.net)）
- OpenAI 兼容 LLM API Key

### 1. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入:
#   OPENAI_API_KEY       — LLM 密钥
#   OPENAI_BASE_URL      — LLM 端点（可换智谱/通义/DeepSeek）
#   OPENAI_MODEL         — 模型名（如 gpt-4o-mini）
#   MINERU_API_KEY       — MinerU 解析密钥
#   BGE_MODEL_PATH       — 本地 BGE-M3 路径（默认 ~/models/bge-m3）
```

### 2. 准备 BGE-M3 模型（可选，有 GPU 时推荐）

将 BGE-M3 模型权重下载到 `~/models/bge-m3`，目录下需含 `config.json`。系统会自动检测 CUDA 并使用 fp16 + GPU 加速；无 GPU 时回退 CPU；无 FlagEmbedding 时回退 `_MockEmbedder`，保证端到端流程可跑通。

### 3. Docker Compose 一键部署

```bash
# 构建后端镜像（CPU 版）
docker build -t zhang-gui-zhi-ku-backend:latest -f Dockerfile.backend .

# 叠加 CUDA torch（有 NVIDIA GPU 时）
docker build -t zhang-gui-zhi-ku-backend:cuda -f Dockerfile.backend-cuda .

# 启动全部服务
docker compose up -d
```

启动后：

- 前端：http://localhost:5200
- 后端 API：http://localhost:5200/api（经 nginx 代理）/ http://localhost:8000（容器内）
- Milvus：localhost:19530

### 4. 本地开发（不走 Docker）

```bash
# 安装依赖（需 Python 3.13+ 和 uv）
uv sync

# 启动 Milvus（仍需 docker）
docker compose up -d milvus

# 启动后端
uv run uvicorn apps.backend.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 配置说明

所有配置通过环境变量注入（`.env` 文件），定义见 [`apps/backend/core/config.py`](apps/backend/core/config.py)。

| 变量 | 默认值 | 说明 |
|---|---|---|
| `APP_NAME` | `zhang-gui-zhi-ku` | 应用名 |
| `APP_DEBUG` | `true` | 调试模式 |
| `HOST` / `PORT` | `0.0.0.0` / `8000` | 后端监听 |
| `OPENAI_API_KEY` | — | LLM 密钥（必填） |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | LLM 端点（可换国产兼容 API） |
| `OPENAI_MODEL` | `gpt-4o-mini` | 模型名 |
| `MINERU_API_KEY` | — | MinerU 解析密钥（上传必填） |
| `MINERU_BASE_URL` | `https://mineru.net/api/v4` | MinerU API 端点 |
| `MILVUS_HOST` / `MILVUS_PORT` | `localhost` / `19530` | Milvus 连接 |
| `MILVUS_COLLECTION` | `zgzk` | Milvus collection 名 |
| `BGE_MODEL_PATH` | `~/models/bge-m3` | 本地 BGE-M3 路径 |
| `CORS_ORIGINS` | `["*"]` | CORS 白名单 |
| `HISTORY_MAX_TURNS` | `10` | 对话历史保留轮数 |
| `ENABLE_HYDE` | `false` | HyDE 检索开关 |
| `ENABLE_RERANK` | `false` | Rerank 精排开关 |

---

## API 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/api/upload` | 上传文档（支持多文件），返回 `task_id` 列表 |
| `GET` | `/api/upload/{task_id}` | 查询导入任务状态 |
| `GET` | `/api/documents` | 文档 / 任务列表 |
| `DELETE` | `/api/documents/{doc_name}` | 删除文档（级联清理 chunks + 任务状态） |
| `POST` | `/api/ask` | 问答（多轮，需 `session_id`） |

### 示例

```bash
# 上传 PDF
curl -F "files=@manual.pdf" http://localhost:5200/api/upload

# 查询任务状态
curl http://localhost:5200/api/upload/<task_id>

# 问答（单轮）
curl -X POST http://localhost:5200/api/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "iPhone16 螺丝扭矩是多少", "session_id": "s1"}'

# 问答（多轮，同 session_id 保持上下文）
curl -X POST http://localhost:5200/api/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "那 iPhone15 呢", "session_id": "s1"}'
```

---

## 测试

测试分三层（TDD 驱动，详见 [`docs/prd.md`](docs/prd.md) §5）：

```
┌─────────────────────────────────────┐
│ E2E (手动, 真实 LLM API)           │  ← scripts/run_e2e.py，不跑 CI
├─────────────────────────────────────┤
│ 集成 (FastAPI TestClient, mock LLM) │  ← pytest -m integration
├─────────────────────────────────────┤
│ 单元 (纯函数, ms 级)                │  ← pytest -m unit
└─────────────────────────────────────┘
```

### 跑测试

```bash
# 全量（单元 + 集成）
./scripts/run_tests.sh
# 或
uv run python -m pytest apps/backend/tests/

# 仅单元测试
uv run python -m pytest -m unit

# 仅集成测试
uv run python -m pytest -m integration

# E2E 全栈集成测试（启动真实 docker-compose）
uv run python scripts/run_e2e.py
```

Mock 规则：mock 外部边界（LLM API、Milvus、MinerU），不 mock 内部同层 Python 对象。

---

## 检索质量评估

系统内置评估框架（`apps/backend/eval/`），指标包括 Recall@5 / Recall@10 / MRR@5，按 4 类查询分组。用于在导入真实 PDF 后建立基线，再决定是否启用 HyDE / Rerank / 调 α。

```bash
# 跑评估
uv run python -m apps.backend.eval.evaluate

# 对比 Rerank 前后
uv run python -m apps.backend.eval.evaluate --rerank
```

详见 [`docs/changelog.md`](docs/changelog.md) 中评估框架交付记录。

---

## 文档

更详细的设计文档位于 [`docs/`](docs/)：

- [PRD 产品需求文档](docs/prd.md)
- [项目总纲](docs/project-brief.md)
- [功能清单](docs/feature-list.md)
- [技术与数据说明](docs/tech-data.md)
- [页面与流程](docs/page-flow.md)
- [变更记录](docs/changelog.md)
- [架构决策记录 (ADR)](docs/adr/README.md)

---

## 许可证

本项目仅供学习与内部使用。