# 功能清单

> 生成日期: 2026-07-14
> 优先级: P0 = 必须 | P1 = 重要 | P2 = 可选

---

## P0 — 核心 (已交付)

| 功能 | 状态 | 验证 |
|---|---|---|
| PDF/MD 上传 | ✅ | POST /api/upload → 后台触发 |
| MinerU 解析 | ✅ | extract 节点, 轮询 300s 超时 |
| 主体识别 | ✅ | LLM 抽取 item_name, 失败回 '未知' |
| 三层分块 | ✅ | 标题切/超长切/过短合并, item_name 拼头 |
| 混合嵌入 | ✅ | BGE-M3 稠密+稀疏, batch_size=32 防 OOM |
| Milvus 写入 | ✅ | bulk_upsert, doc_name 透传 |
| 导入状态追踪 | ✅ | TTL 1h, 惰性清理 |
| 主体识别检索 | ✅ | query 抽 item_name, hybrid_search 过滤 |
| 混合检索 | ✅ | WeightedRanker 0.5/0.5, L2 + IP |
| 空结果兜底 | ✅ | 无结果直接回 '暂无', 绕开 LLM |
| 多轮对话 | ✅ | MemorySaver + thread_id 隔离 |

## P1 — 重要 (待排)

| 功能 | 状态 | 依赖 |
|---|---|---|
| 删除文档 | ❌ | DELETE /api/documents/{id} |
| 批量上传 | ❌ | 一次多个 PDF |
| 前端进度条 | ❌ | WebSocket 或 polling |
| HyDE 检索 | ✅ | 3b507b1 |
| Rerank 精排 | ✅ | dd64654 |
| 检索日志看板 | ❌ | 命中率/延迟统计 |
| 用户反馈 (赞/踩) | ❌ | 质量回馈 |

## P2 — 可选 (远期)

| 功能 | 状态 |
|---|---|
| 权限隔离 | ❌ |
| 多语言 | ❌ |
| 语音输入 | ❌ |
| 页码溯源 | ❌ |
