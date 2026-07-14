# 检索评估框架 — `apps/backend/eval/`

> **真实评估前置步骤**：需先通过 `import_workflow` 导入一份 PDF 到 Milvus，再运行 `evaluate`。Milvus 为空时跑评估会得到 0/0 指标（无命中可能）。单元测试与 smoke test 使用 mock Milvus，无需真实数据。

离线评估当前 **hybrid search**（稠密 BGE-M3 + 稀疏 IP，WeightedRanker 0.5/0.5）的召回率。
框架是**可复用的回归工具** — 加 HyDE / Rerank / 调 α 参数后继续复用同一组 Q-A 对对比。

## 文件结构

| 文件 | 用途 |
| --- | --- |
| `queries.yaml` | 评估 Q-A 数据集（手动维护，20–30 条，分 4 型） |
| `metrics.py` | 纯函数 `recall_at_k` / `mrr_at_k`（无副作用） |
| `evaluate.py` | 跑评估的主逻辑 + CLI |
| `README.md` | 本文件 |

## 指标

| 指标 | 含义 | 公式 |
| --- | --- | --- |
| Recall@5 | top-5 含正确 chunk 的查询比例 | `mean( has_hit(top5) )` |
| Recall@10 | top-10 含正确 chunk 的查询比例 | `mean( has_hit(top10) )` |
| MRR@5 | 正确 chunk 在 top-5 中排名的倒数均值 | `mean( 1/rank_first_hit, 0 if miss )` |

> Per-query `Recall@K` 是二值（命中=1 / 未命中=0）；per-type 与 overall 是均值。

## 查询类型（4 类）

| type | 中文名 | 示例 |
| --- | --- | --- |
| `tech_spec` | 技术参数问 | "iPhone 16 Pro 螺丝扭矩是多少" |
| `error_code` | 故障码问 | "故障码 E01 怎么处理" |
| `item_specific` | 主体相关问 | "iPad Pro 的充电口类型" |
| `generic_context` | 通用问 | "USB-C 和 Lightning 区别" |

## 跑评估

```shell
# 跑全量(默认), 仅输出终端表
python -m apps.backend.eval.evaluate

# 限 30 条 + 导 JSON 报告
python -m apps.backend.eval.evaluate --limit 30 --output report.json
```

输出：

- **终端表** — 按 query type 分组（含 Recall@5 / Recall@10 / MRR@5）+ TOTAL 行
- **JSON 报告**（`-o`）— `{ overall, by_type, per_query }`，便于存档对比

## 数据维护约定

- `query_id` 全局唯一，**新增不删旧**，保证跨版本可比。
- `relevant_texts` 是**入库 chunk 的精确文本片段**（substring 匹配，大小写敏感）。
- `item_name` 对应 Milvus 中的主体过滤字段；无特定主体写 `null`。
- 每次文档库有较大更新后，应复核 / 补充 `queries.yaml`。

## 数据准备（首次）

当前 Milvus 为空时，需先准备一份典型测试 PDF（含明确的技术参数表
格），通过现有 `import_workflow` extract→chunk→embed→store 入库，再针
对入库的真实 chunk 编写/更新 ``queries.yaml`` 中的 relevant_texts。
库为空时运行评估会得到 0/0 指标（无命中可能）。

## 测试

```shell
python -m pytest apps/backend/tests/unit/test_evaluate.py -v
```

策略（`test_evaluate.py`）：

- **Cycle 1 纯函数** — 已知答案断言 Recall/MRR 公式，不依赖外部。
- **Cycle 2 流水线** — `mock milvus_client.hybrid_search` 返回预设
  golden，验证 `evaluate_all / group_by_type / build_report / render_table`
  整条链路。
- **CLI** — patch `evaluate_all` 注入假结果，验证终端表 + JSON 输出。

## 与现有代码的整合

- 复用 `milvus_client.hybrid_search` + `embedder.embed_chunks`，不改被测代码。
- 评估调用路径与 `graph.py` retrieve 节点完全隔离（直调 Milvus 链路）。
- 后续加 HyDE / Rerank 时，新建 `evaluate_X.py`，共用 `queries.yaml`
  与 `metrics.py` 即可对比收益。
