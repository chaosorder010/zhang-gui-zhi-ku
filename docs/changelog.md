# 变更记录

## 2026-07-10

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

### 主体识别澄清

- **变更**: 主体识别不在检索时跑，改到导入时跑一次
- **Why**: 减轻查询时延迟，item name 作为常量字段存储
- **实现**: 导入时识别 → 拼到 chunk 开头 embedding → Milvus `item_name` 常量字段
