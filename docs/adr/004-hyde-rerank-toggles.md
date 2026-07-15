# ADR-004: HyDE / Rerank 双开关图编排

> 状态: 已接受
> 日期: 2026-07-15
> 决策者: 开发团队
> 相关: ADR-003 (Graph RAG 编排), ADR-002 (混合检索)

---

## 背景

掌柜智库的 RAG pipeline 在 137 chunks 的 PDF 数据集上 Recall@5=100%、MRR@5=0.812。为进一步提升回答质量,引入两种检索增强技术:

- **HyDE (Hypothetical Document Embeddings)**: 用 LLM 生成假设答案,对其 embedding 检索,解决 query-chunk 语义鸿沟
- **Rerank (LLM 精排)**: 对 Milvus 返回的 top-K chunk 用 LLM 打 1-5 分重排序,提升首位相关性

两种技术都改 `graph.py` 的 `build_graph()`,需要独立开关控制。

---

## 决策

### 1. 双独立开关

```python
# core/config.py
enable_hyde: bool = False      # HyDE 检索开关
enable_rerank: bool = False    # Rerank 精排开关
```

两个开关独立,可任意组合 (4 种模式)。默认都关闭,保证生产环境零风险。

### 2. 图拓扑

```
recognize → [hyde | retrieve] → [rerank] → chatbot
              ↑ 二选一           ↑ 可选
```

| enable_hyde | enable_rerank | 路径 |
|---|---|---|
| False | False | recognize → retrieve → chatbot (原始) |
| True | False | recognize → hyde → chatbot |
| False | True | recognize → retrieve → rerank → chatbot |
| True | True | recognize → hyde → rerank → chatbot |

### 3. 字节级不变性保证

**关键约束**: 开关关闭时,`build_graph()` 编译出的图与改动前**字节级一致** (节点列表 + 边列表完全相同)。

实现方式: 用 `if enable_xxx: graph.add_node(...)` 条件注册,不满足条件时节点/边不存在于图中。

**测试验证**: `test_hyde.py::test_enable_hyde_false_has_no_hyde_node` 等 4 个测试断言图结构。

### 4. 护栏设计

| 场景 | 护栏行为 |
|---|---|
| HyDE 命中 0 条 | 退回原始 query 嵌入检索结果 |
| Rerank LLM 抛异常 | 退回 Milvus 原始排序 |
| 检索空结果 | 直接回 "暂无相关信息",绕开 LLM |

---

## 后果

### 正面
- 开关默认关闭,生产部署零风险
- 4 种模式可独立 A/B 测试
- 字节级不变性保证让现有 168 个测试无需修改

### 负面 / 风险
- `build_graph()` 复杂度增加,条件边逻辑需仔细维护
- 两个特性共享 `graph.py`,并行开发时需 worktree 隔离 (见 ADR-005)
- HyDE 增加一次 LLM 调用 (~2s 延迟),Rerank 增加 N 次 LLM 调用 (N=top-K)

---

## 代码位置

- `apps/backend/services/graph.py` — `build_graph()` + hyde/rerank 节点
- `apps/backend/services/reranker.py` — LLM 打分 1-5 + 异常护栏
- `apps/backend/core/config.py` — enable_hyde / enable_rerank / hyde_prompt_template
- `apps/backend/tests/unit/test_hyde.py` — 4 个 HyDE 测试
- `apps/backend/tests/unit/test_reranker.py` — Reranker 单元测试
- `apps/backend/tests/unit/test_graph_rerank.py` — Rerank 图编排测试

---

## 相关决策

- ADR-005: 并行开发的 worktree 隔离模式
- ADR-003: Graph RAG 编排 (recognize→retrieve→chatbot)
- ADR-002: 混合检索 (BGE-M3 稠密+稀疏)
