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
| 编排 | LangGraph | 多轮对话/工作流 |
| 后端 | FastAPI | 异步 Python API |
| 前端 | HTML + CSS + JS | 轻量, 几周交付够用 |

## 路线

Route C 混合栈: 本地 embedding + 云端 LLM。不需要隐私保护。

## 检索架构

- **三路检索**: 稠密(向量) + 稀疏(BM25) + HyDE(假设文档)
- **MCP 网络搜索**: 外部搜索补充
- **RRF 倒数排名融合**: 合并三路结果
- **Rerank 精排**: 二阶段排序提升精度

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

## 部署

- Docker Compose: FastAPI + Milvus + MongoDB + MinIO + 前端
- NVIDIA GPU 跑 embedding + rerank
- 云端 LLM API 调 embedding (可选) + 生成
