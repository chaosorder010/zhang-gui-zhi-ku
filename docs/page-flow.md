# 页面与流程说明

> 生成日期: 2026-07-14

---

## 1. 页面

| 路径 | 类型 | 说明 |
|---|---|---|
| `/` | 静态页 | nginx serve, 问答界面 |
| `/api/upload` | API | 上传 PDF/MD |
| `/api/ask` | API | 问答 (多轮) |
| `/api/documents` | API | 文档/任务列表 |
| `/api/upload/{task_id}` | API | 导入任务状态 |

前端无构建工具链, 原生 HTML + CSS + JS。

## 2. 用户流程

### 文档导入

```
用户上传 PDF
  → POST /api/upload → 返回 task_id
  → 后台 LangGraph 编排:
      extract (MinerU) → recognize (LLM) → chunk (三层分块)
      → embed (BGE-M3) → store (Milvus)
  → 条件边: 任一节点失败 → 直接 END
  → GET /api/upload/{task_id} 查状态 (uploaded/done/failed)
```

### 问答

```
用户提问
  → POST /api/ask {question, session_id}
  → graph.py 编排:
      recognize: query 抽 item_name
      retrieve: embed query → hybrid_search (按 item_name 过滤)
      条件边:
        有结果 → chatbot: chunk 拼 system prompt → LLM 生成
        无结果 → no_results: 直接回 '知识库暂无相关信息'
  → 返回 {answer, session_id}
```

## 3. 导航地图

```
首页 (问答)
  ├── 输入框 → /api/ask
  ├── 上传按钮 → /api/upload
  └── 历史对话 → MemorySaver thread_id 隔离
```
