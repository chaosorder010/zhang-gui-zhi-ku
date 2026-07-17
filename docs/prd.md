# PRD: 掌柜智库 — 企业级 RAG 知识库系统

> 生成日期: 2026-07-10
> 状态: MVP 冻结，进入闭环执行阶段

---

## 1. Problem Statement

企业内部员工查阅电子产品手册/维修指南时，需在几十本 PDF 中人工翻找信息，耗时长、效率低。手册含大量技术参数（扭矩值、故障码、零件编号），人工查找易出错，错误信息在维修场景中代价高（损坏设备、安全风险）。

员工需要: 用自然语言直接提问，几秒内得到准确答案。

---

## 2. Solution

构建基于 RAG（检索增强生成）的 Web 知识库系统:

1. 上传 PDF/MD 手册 → 系统自动解析、分块、向量化入库
2. 员工用中文自然语言提问 → 三路并行检索 + 精排 → LLM 生成答案
3. 支持多轮对话，记住上下文
4. 无答案场景诚实告知，不调 LLM 兜底（宁缺勿错）

---

## 3. User Stories

### 核心问答流程

1. 作为维修技师，我上传一批 PDF 手册，以便系统能从中检索信息
2. 作为维修技师，我用中文自然语言提问"XX 型号螺丝扭矩是多少"，以便几秒内得到答案
3. 作为维修技师，我问完一个技术细节后继续追问"那 YY 型号呢"，系统能记住上文，以便多轮对话无需重复背景
4. 作为维修技师，我问了一个手册外的问题，系统告知"知识库无此信息"，以便我知道它不会编造技术参数
5. 作为维修技师，我上传含图片/表格的 PDF，系统正确解析文本和图片，以便表格参数可被检索

### 文档上传与管理

6. 作为维修技师，我在 Web 页面上传单个 PDF/MD 文件，以便向知识库添加新手册
7. 作为维修技师，上传后系统自动完成解析+分块+向量化，以便几分钟后文档可查
8. 作为维修技师，我查看已上传文档列表，以便了解知识库覆盖范围
9. 作为维修技师，我删除错误上传的文档，以便知识库保持干净 (P1)

### 检索与召回

10. 作为维修技师，我问"故障码 E01 怎么处理"，系统召回含"E01"关键词的 chunk，以便精确数字/代码准
11. 作为维修技师，我问"螺丝拧紧力矩"，系统也召回"扭矩参数"语义相关但关键词不同的 chunk，以便同义词不漏
12. 作为维修技师，我指定主体"A型号"，系统仅召回item_name=A型号的 chunk，以便同类手册不串
13. 作为维修技师，我问了一个模糊问题，系统用 HyDE 生成假设文档再去检索，以便深层语义能匹配
14. 作为维修技师，我问了一个行业通用问题，系统还走 MCP 网络搜索补充，以便手册外常识也有召回

### 前端交互

15. 作为维修技师，我打开首页直接进入问答界面，无需登录，以便快速使用
16. 作为维修技师，我在问答输入框下方看到历史对话，以便参考上文
17. 作为维修技师，回答下方显示来源文档名，以便我回查原文确认
18. 作为维修技师，URL 能分享/收藏某个对话，以便后续复现同一讨论

### 运维与部署

19. 作为运维工程师，整个系统一个 `docker compose up` 启动，以便内网部署简单
20. 作为运维工程师，云端 LLM API 密钥通过环境变量注入，以便更换厂商不改代码

### 后续 (P1/P2，不在 MVP)

21. 作为维修技师，我对回答赞/踩，以便系统团队评估质量 (P1)
22. 作为维修技师，我批量上传一次多个 PDF，以便大规模入库 (P1)
23. 作为运维工程师，我查看检索日志和命中率，以便优化检索效果 (P1)
24. 作为部门主管，我限制本部门员工只看本部门手册，以便数据安全 (P2，本期不做)

---

## 4. Implementation Decisions

### 4.1 总体路线

- **Route C 混合栈**: 本地 embedding + 云端 LLM API
  - 原因: 不需要隐私保护，云端 LLM 中文效果优，开发速度快
- **数据流**: PDF/MD → MinerU 解析 → LLM 主体识别 → 三层分块 → embedding → Milvus 入库
- **查询流**: query → LLM 主体识别 → 三路并行检索 → Milvus 内线性加权 → RRF 三路融合 → Rerank → LLM 生成

### 4.2 技术栈

| 层 | 选型 | 原因 |
|---|---|---|
| PDF 解析 | MinerU | 中文 PDF 强，处理表格/双栏/图片，输出 MD |
| Embedding | 本地中文 embedding | 中文优化，本地 GPU 跑 |
| 向量库 | Milvus | 稠密+稀疏混合检索，功能强 |
| 文档库 | MongoDB | 存文档元数据/对话历史 |
| 对象存储 | MinIO | 存图片 |
| 重排序 | BGE-Reranker-Large / Qwen3-Reranker | 中文精排效果好 |
| LLM | 云端 API (LangChain) | 不需本地 GPU 跑 LLM |
| 编排 | LangGraph | 状态机编排: 对话历史、路由决策、重试 |
| LLM 封装 | LangChain | 云端 LLM/embedding/rerank 调用封装 |
| 后端 | FastAPI | 异步 Python API |
| 前端 | HTML + CSS + JS | 原生无构建，nginx serve static |
| 测试 | pytest + httpx + TestClient | 标准 Python 测试栈 |

### 4.3 检索架构

三路并行检索:

| 路 | query 构造 | 目标 | top-K |
|---|---|---|---|
| 路1 | 原始 query | Milvus 混合检索 (稠密+稀疏) | 20 |
| 路2 | HyDE 假设文档 | Milvus | 20 |
| 路3 | 原始 query | MCP 网络搜索 (外网) | 10 |

- **Milvus 内融合 (路1)**: 线性加权 `score = α·dense + (1-α)·sparse`, α 网格搜索调参
- **RRF 融合 (路1+路2+路3)**: `score(d) = Σ 1/(k + rank_i(d))`
- **Rerank 精排**: BGE-Reranker-Large / Qwen3-Reranker 二阶段排序

### 4.4 主体识别

- **导入时**: LLM 抽取 item name → chunk 开头拼 item_name 提 embedding 权重 → Milvus `item_name` 常量字段存储
- **查询时**: query 也跑 LLM 抽取 item name → 匹配 Milvus `item_name` 硬过滤
- **fallback**: 主体识别失败则 filter 关，走全量召回
- **空结果处理**: Milvus 无结果或全低分 → 直接回"知识库无此信息"，不调 LLM 兜底

### 4.5 分块策略

三层:

1. **按标题切**: MD 标题层级 (`#`/`##`/`###`) 识别章节边界
2. **超长二次切**: 超 max_tokens 按段落/字符再切
3. **过短合并**: 低于 min_tokens 合入相邻 chunk

- **接缝**: 纯函数 `split_markdown(text, item_name, max_tokens, min_tokens) -> list[Chunk]`
- **item_name 前缀**: 切分和合并操作都保留 item_name 前缀

### 4.6 Milvus 数据模型

| 字段 | 类型 | 说明 |
|---|---|---|
| id | INT64 | 主键 |
| dense_vector | FLOAT_VECTOR | 稠密向量 |
| sparse_vector | SPARSE_FLOAT_VECTOR | 稀疏向量 |
| text | VARCHAR | chunk 文本 |
| item_name | VARCHAR | 主体名 (常量字段) |
| doc_name | VARCHAR | 文档名 |
| chunk_id | INT64 | chunk 序号 |

### 4.7 API 表面

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/ask` | 问答，多轮 |
| POST | `/api/upload` | 上传文档 |
| GET | `/api/documents` | 文档列表 |
| DELETE | `/api/documents/{id}` | 删除文档 (P1) |

### 4.8 部署

- Docker Compose: FastAPI + Milvus + MongoDB + MinIO + 前端
- NVIDIA GPU 跑 embedding + rerank
- 云端 LLM API 调 embedding (可选) + 生成
- 前端 nginx serve static, 无构建工具链

---

## 5. Testing Decisions

### 5.1 分层

```
┌─────────────────────────────────────┐
│ E2E (手动, 真实 LLM API)           │  ← 单独脚本, 不跑 CI
├─────────────────────────────────────┤
│ 集成 (FastAPI TestClient, mock LLM) │  ← pytest -m integration
├─────────────────────────────────────┤
│ 单元 (纯函数, ms 级)                │  ← pytest -m unit
└─────────────────────────────────────┘
```

### 5.2 Seam 清单与测试重点

- **API router** (`/api/ask`, `/api/upload`) — 输入校验、错误码、session_id 必填 400、空 question 422
- **Graph 编排** — 多轮记忆 thread_id 隔离、对话历史正确累积
- **分块函数** (`split_markdown`) — 标题识别、超长切分界、过短合并、item_name 前缀保
- **检索融合** — RRF 公式正确性、线性加权 α 输出、三路输入输出形态
- **MinerU 包装** — mock 外部调用，测 wrapper 输出转内部 Chunk 结构

### 5.3 Mock 规则

- **Mock 外部边界**: LLM API、Milvus、MongoDB、MinerU、MCP
- **不 mock 内部**: 同一层 Python 对象互相调用走真实；只 mock 出层边界

### 5.4 覆盖率与 CI

- pytest unit + integration 必跑 CI
- 覆盖率阈值 80%
- E2E 单独脚本手动触发（真实 LLM，费钱）

### 5.5 测试风格

- 只测 seam（公共接口），不耦合实现细节
- TDD 驱动：先写失败测试，再写刚好能过的代码

---

## 6. Out of Scope

明确不做:

- ✗ 页码溯源（答案标注"第X页"）
- ✗ 多语言（英文手册）
- ✗ 语音输入（ASR）
- ✗ 文档自动同步更新
- ✗ 权限隔离（按部门/角色）
- ✗ 用户反馈收集（赞/踩）— P1
- ✗ 批量导入 — P1
- ✗ 检索日志与命中率看板 — P1

---

## 7. Further Notes

### 7.1 已知风险

| 风险 | 缓解 |
|---|---|
| 中文 PDF 双栏/表格排版复杂，分块质量定天花板 | MVP 先拿几种典型手册实测分块效果 |
| Milvus 运维比 Qdrant 重 | Docker Compose 单机版先扛，用户量上来再评估 |
| MCP 网络搜索 + HyDE 增加延迟和故障点 | MCP 设超时，失败不影响主流程 |
| 主体识别有误导致漏召回 | query 主体识别失败自动关 filter，走全量兜底 |
| 错误技术参数代价高 | 空结果直接回"无信息"，宁缺勿错 |

### 7.2 成功验证

- 人工抽查询问核对原 PDF
- 响应速度几秒内
- P0 功能集成测试覆盖率 ≥ 80%

### 7.3 后续演进

- P1: 用户反馈、检索日志、文档管理、批量导入
- P2: 权限隔离、多语言、语音输入、页码溯源

### 7.4 变更记录

所有设计决策和方向变更详见 `docs/changelog.md`，每条带 Why。
