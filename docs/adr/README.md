# Architecture Decision Records

> 掌柜智库的架构决策记录索引

| ADR | 标题 | 状态 | 日期 |
|---|---|---|---|
| ADR-001 | 技术栈选型 (FastAPI + LangGraph + Milvus) | 已接受 | 2026-07-08 |
| ADR-002 | 混合检索 (BGE-M3 稠密+稀疏) | 已接受 | 2026-07-11 |
| ADR-003 | Graph RAG 编排 (recognize→retrieve→chatbot) | 已接受 | 2026-07-13 |
| ADR-004 | HyDE / Rerank 双开关图编排 | 已接受 | 2026-07-15 |
| ADR-005 | 并行开发的 Git Worktree 隔离 | 已接受 | 2026-07-15 |

---

## 添加新 ADR

1. 在 `docs/adr/` 创建 `NNN-title.md`
2. 更新本索引
3. commit message: `adr-NNN: <title>`
