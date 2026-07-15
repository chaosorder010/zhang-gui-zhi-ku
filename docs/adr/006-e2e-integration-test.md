# ADR-006: 前后端全栈 E2E 集成测试策略

> 状态: 已接受 (暂未实现)
> 日期: 2026-07-15
> 决策者: 开发团队
> 相关: ADR-005 (worktree 隔离), docs/e2e-test-report.md (已有手工测试报告)

---

## 背景

掌柜智库已有 168 个后端单元测试 + 9 个前端 Jest 测试,但前后端之间的集成链路 (nginx 代理 → FastAPI → Milvus → LLM) 仅有早期手工验证 (docs/e2e-test-report.md,已过时)。P1 特性 (删除文档、批量上传、前端进度条、HyDE、Rerank) 落地后,需要一套自动化回归保证全链路不断链。

---

## 决策

### 1. 目标
**跑通现有集成,不是加功能。** 验证全链路不断链。

### 2. 方法
自动化端到端测试脚本 `run_e2e.py`,交付 pass/fail 报告,退出码 0/1。

### 3. 环境
**全栈真实容器** — docker-compose 起全套:
- `zgzk-frontend` (nginx:alpine,主机 5173)
- `zgzk-backend` (FastAPI 8000)
- `zgzk-milvus` (standalone)

主机走 nginx 5173 端口,与真实用户路径一致。

### 4. 覆盖范围 (全 P0)
| 流程 | 覆盖点 |
|---|---|
| 上传 | 上传成功 + 轮询到 done;上传失败 (错误文件格式) |
| 问答 | 正常问答 (结构断言);多轮对话 (session_id 保持);空结果兜底 |
| 文档列表 | GET /api/documents 返回非空 |
| 删除文档 | DELETE /api/documents/{doc_name} → 列表不再包含 |

### 5. 断言策略
**结构断言** — 不断言 LLM 输出内容 (非确定性),只断言:
- HTTP 状态码 200
- `answer` 字段非空
- `answer` 长度 > 10

### 6. 测试数据
**复用现有 real PDF** — 之前 eval 用的 PDF (已知能解析出 137 chunks)。不合成 fixture,保真度最高。

### 7. 交付物
- `run_e2e.py` — 测试脚本
- 终端输出 pass/fail 报告
- 退出码 0 (全通过) / 1 (有失败),CI 可直接接

### 8. Docker 生命周期
**脚本管全生命周期** — 自包含:
```
run_e2e.py
├── subprocess: docker-compose up -d (后台)
├── wait for healthy (backend /api/ok + Milvus healthz)
├── run test scenarios
├── collect results
├── subprocess: docker-compose down -v
└── print report + exit(0/1)
```

测试挂掉时 `down -v` 可能残留容器 (需在 finally 块保证执行)。

---

## 未决策 / 后续

- CI 集成 (GitHub Actions) 推迟 — 脚本先稳定
- HyDE/Rerank 开关的前端 UI — 不在本次范围
- 真实 eval 数字对比 (Recall@5 / MRR@5 lift) — 单独任务

---

## 后果

### 正面
- 全栈真实路径验证,覆盖 nginx 代理 + 真实 Milvus + 真实 BGE-M3
- 自包含脚本,CI 友好
- 退出码机制,可接任何 CI

### 负面 / 风险
- **慢** — BGE-M3 加载 + Milvus 启动 + PDF 解析,单次运行 ~3-5 分钟
- 脚本需要处理容器启动超时 / Milvus healthcheck 失败等边界
- PDF 上传测试依赖大文件体,网络/磁盘 IO 可能波动

---

## 代码位置

- 脚本: `scripts/run_e2e.py`
- 现有参考: `docs/e2e-test-report.md` (手工报告,已过时)
- 测试 PDF: 复用之前 eval 数据集路径
