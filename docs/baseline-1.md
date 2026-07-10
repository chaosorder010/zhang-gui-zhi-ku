# Baseline-1: 项目骨架 + 最小可问答端到端

## 当前目标

从零搭到能问一句话、返回一段 LLM 回答的最短端到端链路。不分文档、不检索——先把 LangChain + LangGraph + FastAPI + 前端打通。

## In Scope

- FastAPI 项目结构 (routers, services, models)
- LangChain 调云端 LLM API（env 配置好 API key）
- LangGraph 多轮对话记忆（stateful graph）
- 原生 HTML/CSS/JS 问答 UI（先不做上传）+ nginx 直接 serve static
- Docker Compose 跑 FastAPI + 前端
- .env.example + 配置加载
- pytest 骨架 + Baseline-1 已有代码的集成测试（补欠账）

## Out of Scope

- PDF 解析（MinerU）
- 向量库（Milvus）
- 检索/重排序
- MCP/HyDE
- 主体识别
- MinIO / MongoDB
- Vite/npm 构建工具链

## 依赖护城河文档

- `docs/project-brief.md` — 目标用户/部署约束
- `docs/feature-list.md` — P0 功能拆解
- `docs/page-flow.md` — 问答流程主链路
- `docs/tech-data.md` — 技术栈选型 + API 表面 + 测试策略

## 执行拆解

1. 项目结构搭好（apps/backend, apps/frontend, docker-compose.yml）
2. FastAPI 入口 + /api/ask + LangChain LLM 调用
3. LangGraph 编排 MessagesState + 多轮记忆
4. 原生 HTML/CSS/JS 问答 UI + nginx serve static（省掉 Vite）
5. Docker Compose 起整链
6. pytest 骨架 + conftest + /api/ask 集成测试（mock LLM）
7. 多轮记忆单元测试（graph 编排，mock LLM）

## 完成标准

- [x] `docker compose up` 起整链
- [x] 浏览器打开问答页，输入问题，返回 LLM 回答
- [x] 多轮对话：问"什么是RAG"，再问"再細講"，模型记得前文
- [ ] **集成测试 /api/ask 通过（mock LLM）**
- [ ] **多轮记忆单测通过（mock LLM）**
- [ ] **CI 可跑 pytest，不需真实 LLM API**

## 本阶段决策

- **使用原生 HTML/CSS/JS + nginx, 不走 Vite**: 省掉 node_modules + 构建工具链, docker compose 启动更快。`fetch` + `crypto.randomUUID()` 够用。
- **测试欠账补上**: Baseline-1 代码已写, 测试在下一循环补。集成测试 mock LangChain LLM, 单测 mock LLM 调用 graph 多轮编排。
