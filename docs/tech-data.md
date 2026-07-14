# 技术与数据说明

> 生成日期: 2026-07-14

---

## 1. 技术栈

| 层 | 选型 | 原因 |
|---|---|---|
| 后端 | FastAPI | 异步 Python, TestClient 测 seam |
| 编排 | LangGraph | 状态机: 对话历史/路由/重试 |
| 向量库 | Milvus 2.5 | 稠密+稀疏混合检索 |
| 嵌入 | BGE-M3 | 中文优化, 同时产出稠密+稀疏 |
| LLM | longcat (OpenAI 兼容) | 中文效果优, 云端 API |
| 解析 | MinerU | 中文 PDF 强, 处理表格/双栏 |
| 前端 | HTML + CSS + JS | 无构建, nginx serve |
| 部署 | Docker Compose | 单机一键起 |
| 测试 | pytest + httpx | 标准 Python 测试栈 |

## 2. 数据模型

### Milvus Collection: zgzk

| 字段 | 类型 | 说明 |
|---|---|---|
| id | INT64 PK | auto_id |
| dense_vector | FLOAT_VECTOR (dim=1024) | BGE-M3 稠密 |
| sparse_vector | SPARSE_FLOAT_VECTOR | BGE-M3 稀疏 |
| text | VARCHAR (65535) | chunk 文本 |
| item_name | VARCHAR (256) | 主体名 (如 iPhone16) |
| doc_name | VARCHAR (1024) | 文档名 (透传自 file_name) |
| chunk_id | INT64 | chunk 序号 |

索引: dense → IVF_FLAT (L2), sparse → SPARSE_INVERTED_INDEX (IP)

### ImportState (LangGraph)

```python
class ImportState(TypedDict):
    task_id: str
    file_name: str
    file_binary: bytes
    item_name: Optional[str]
    markdown: str
    chunks: list[dict]
    vectors: list[dict]
    status: str  # uploaded→extracting→recognizing→chunking→embedding→storing→done/failed
    error: Optional[str]
    mineru_base_url: str
    mineru_token: str
    openai_api_key: str
    openai_base_url: str
    openai_model: str
```

### RagState (LangGraph)

```python
class RagState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    item_name: str | None
    retrieved_chunks: list[dict]
```

## 3. API 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/upload` | 上传 PDF/MD, 返回 task_id |
| GET | `/api/upload/{task_id}` | 导入任务状态 |
| GET | `/api/documents` | 任务列表 |
| POST | `/api/ask` | 问答 (多轮, 需 session_id) |

## 4. 关键环境变量

| 变量 | 说明 |
|---|---|
| OPENAI_API_KEY | LLM API 密钥 |
| OPENAI_BASE_URL | LLM 端点 |
| MINERU_API_KEY | MinerU 解析密钥 |
| MILVUS_HOST / MILVUS_PORT | Milvus 连接 |
| BGE_MODEL_PATH | 本地 BGE-M3 路径 (~/models/bge-m3) |
| HF_HUB_OFFLINE / TRANSFORMERS_OFFLINE | 离线模式 (禁连 HuggingFace) |
