# 变更记录

> 生成日期: 2026-07-14
> 格式: 日期 + 变更 + 原因

---

## 2026-07-14

- **评估框架交付** (c343ead, PR #11)
  - 新增 `apps/backend/eval/` 模块: metrics.py / evaluate.py / queries.yaml
  - 指标: Recall@5 / Recall@10 / MRR@5, 按 4 类查询分组
  - 原因: 检索质量未验证, 先建基线再决定 HyDE/Rerank

- **架构改进** (b6f5518, 993d84d, d6df35d, 2adf4ea, 0860a68)
  - 抽取 @node_handler 装饰器统一节点错误处理
  - 结构化日志覆盖 import_workflow + upload + graph
  - 抽取 create_initial_import_state 工厂函数
  - 新增 24 个测试覆盖未测路径
  - 原因: 5 节点 import_workflow 重复 try/except 模式需统一

- **herdr 技能更新**
  - herdering + use-herder 补充: 模型不继承 / wait_agent 不准 / watch regex 类型 / 诸葛严格模式
  - 原因: pi 新 pane 默认 sonnet→Bedrock 失败, 需显式 --model longcat

- **BGE-M3 本地加载打通**
  - .env 补 BGE_MODEL_PATH + offline 环境变量
  - embedder.py 支持从本地路径加载, 不再强连 HuggingFace
  - 原因: 离线环境 FlagEmbedding 尝试联网导致 fallback 到 MockEmbedder

## 2026-07-13

- **文档导入 P0/P1/P2 全交付** (cb50905, 380b80d, db9b919, PR #9)
  - P0: 批次编码防 OOM / BackgroundTasks 事件循环安全 / MinerU 脏数据校验 / doc_name 透传
  - P1: 条件边 fail-fast (失败节点短路到 END)
  - P2: _task_status TTL 清理防内存泄漏
  - 原因: Baseline-2 导入骨架存在多个阻断性问题

- **Graph RAG 编排** (c080305, PR #8)
  - graph.py 从单 chatbot 重构为 recognize→retrieve→chatbot + 条件边
  - 空结果走 no_results 边直接回 '暂无', 绕开 LLM
  - 原因: 旧 /api/ask 纯靠 LLM 硬答, 不调检索

- **Issue #3-#7 关闭**
  - #4 #5 标 wontfix (已实现)
  - #3 epic / #6 Graph RAG / #7 Docker Milvus 完成关闭

## 2026-07-11

- **MVP 骨架** (0d90a40)
  - Baseline-1: 单 chatbot + Milvus 占位 + LLM 直答
  - 8/8 测试通过

- **护城河文档初始化** (c53d7de)
  - project-brief / feature-list / page-flow / tech-data / changelog
