# 功能清单

## P0 — MVP 必做

| 功能 | 说明 | 优先级 |
|---|---|---|
| PDF 解析 | MinerU 解析 PDF/MD 文本和图片 | P0 |
| 主体识别 | 导入时识别 item name，拼到 chunk 开头 embedding | P0 |
| 分块策略 | 按文档章节/标题递归分块 | P0 |
| 向量化 | 本地 embedding 模型 | P0 |
| 向量存储 | Milvus 存 chunk + item_name 常量字段 + 元数据 | P0 |
| 稠密检索 | 向量相似度检索 | P0 |
| 稀疏检索 | BM25 关键词检索 | P0 |
| HyDE 检索 | 假设性文档 embedding 检索 | P0 |
| MCP 网络搜索 | 外部网络搜索补充 | P0 |
| RRF 融合 | 三路检索结果倒数排名融合 | P0 |
| Rerank 精排 | BGE-Reranker-Large / Qwen3-Reranker | P0 |
| LLM 生成 | 云端 LLM API（LangChain 调用） | P0 |
| 多轮对话 | LangGraph 编排上下文记忆 | P0 |
| FastAPI 后端 | REST API | P0 |
| 前端 UI | HTML + CSS + JS 问答界面 | P0 |
| 文档上传 | Web 上传 PDF/MD | P0 |

## P1 — 后续可做

| 功能 | 说明 |
|---|---|
| 用户反馈 | 赞/踩, 标注回答质量 |
| 检索日志 | 记录查询和命中率 |
| 文档管理 | 删除/更新已有文档 |
| 批量导入 | 批量上传 PDF |

## P2 — 远期

| 功能 | 说明 |
|---|---|
| 权限隔离 | 按部门/角色隔离 |
| 多语言 | 英文手册支持 |
| 语音输入 | ASR 转文字 |
| 页码溯源 | 答案标注来源页 |
