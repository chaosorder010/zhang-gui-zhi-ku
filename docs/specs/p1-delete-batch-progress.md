# Spec: P1 — 删除文档 + 批量上传 + 导入进度条

> **来源:** docs/feature-list.md P1 就绪项
> **日期:** 2026-07-14
> **范围:** 三项无评估依赖的 P1 功能

---

## Problem Statement

当前掌柜智库 MVP 已闭环,但文档管理存在明显缺口:

1. **无法删除文档** — 用户上传了错误/过期的 PDF 后,没有任何途径从知识库中移除,导致检索结果包含脏数据,违背"宁缺勿错"原则。
2. **只能单文件上传** — 维修技师一批手上有 10 份手册时,需要反复选文件→等→再选文件,效率极低。
3. **导入无进度反馈** — 用户上传 PDF 后只拿到 task_id,不知道导入是正在进行、已完成还是已失败,前端没有任何进度展示,用户体验如石沉大海。

## Solution

给掌柜智库补充文档全生命周期的管理能力:

- **删除:** 新增 `DELETE /api/documents/{doc_name}`,从 Milvus 移除该文档所有 chunk,并清理本地任务状态。前端每条文档旁显示删除按钮。
- **批量上传:** 扩展 `POST /api/upload` 接受多文件,每文件独立 task_id,并行触发导入工作流。
- **进度条:** 前端上传后展示每文件导入状态(上传中/解析中/分块/嵌入/入库/完成/失败),polling `GET /api/upload/{task_id}` 实时更新。

---

## User Stories

### 删除文档

1. 作为维修技师,我想删除已上传的错误文档, 这样它就不会污染我的检索结果
2. 作为运维工程师,我想在导入失败后清理残留数据, 这样知识库不会堆集成半成品 chunk
3. 作为维修技师,我想在删除前看到文档名确认, 这样不会误删相邻文档
4. 作为维修技师,我希望删除操作即时生效, 这样下一轮问答就不会再引用已删文档
5. 作为运维工程师,我希望删除不残留元数据, 这样 task_status 不会积累僵尸条目

### 批量上传

6. 作为维修技师,我想一次选多个 PDF 批量上传, 这样不用逐文件等待
7. 作为维修技师,我想看到整体批量任务的概览, 这样知道哪些文件正在处理
8. 作为维修技师,我希望单个文件失败不影响其它文件, 这样一份坏 PDF 不会阻塞整批
9. 作为维修技师,我想每个文件独立返回 task_id, 这样我能单独追踪每份文档状态
10. 作为运维工程师,我希望批量上传共享同一个文件类型校验规则, 这样拒绝逻辑一致

### 导入进度条

11. 作为维修技师,我想看到文件上传后的实时进度, 这样知道系统在工作而不是卡住了
12. 作为维修技师,我想看到导入的当前阶段(解析/分块/嵌入/入库), 这样能预估剩余时间
13. 作为维修技师,我想在导入完成时收到提示, 这样能开始提问
14. 作为维修技师,我想在导入失败时看到错误原因, 这样能调整文件格式重试
15. 作为运维工程师,我希望前端轮询不会压垮后端, 因此需要合理间隔(2-3s)并自动停止

### 交叉关注

16. 作为维修技师,批量上传时我想为每条文件独立看到进度条, 而不是只看到一个总进度
17. 作为维修技师,我想在进度条旁看到已上传文件列表及各自状态图标, 这样一目了然
18. 作为运维工程师,我希望删除接口幂等, 重复删除同一文档不产生错误

---

## Implementation Decisions

### D1 — 删除文档:新增 `DELETE /api/documents/{doc_name}`

- **路由层:** 在 `routers/upload.py` 新增 `DELETE /api/documents/{doc_name}` endpoint
- **Milvus 操作:** 在 `milvus_client.py` 新增 `delete_by_doc_name(doc_name: str) -> int`,使用 `client.delete(collection, filter='doc_name == "..."')`,返回删除条数
- **级联清理:** 删除成功后,在 `_task_status` 中移除匹配 `file_name == doc_name` 的条目
- **响应格式:** `{"doc_name": str, "deleted_chunks": int, "status": "deleted"}`
- **幂等:** 文档不存在时返回 `{"doc_name": str, "deleted_chunks": 0, "status": "not_found"}`,HTTP 200 (不抛 404,因为幂等删除语义上视为成功)
- **doc_name 编码:** URL path 参数可能含中文/空格,前端使用 `encodeURIComponent`(已验证 `crypto.randomUUID()` 在 main.js)

### D2 — 批量上传:多文件支持

- **路由改造:** `POST /api/upload` 从单文件改为 `files: list[UploadFile]`,保留单文件兼容(传一份)
- **任务拆分:** 每份文件独立 `task_id → create_initial_import_state()`,逐个加入 `BackgroundTasks`
- **响应格式:** `{"batch_id": str, "tasks": [{"task_id": str, "file_name": str, "status": "uploaded"}], "count": int}`
- **独立失败:** 每份文件的 import graph 独立执行,某文件 crash 不影响其它(已有 `trigger_import_sync` 异常捕获)
- **文件校验:** 复用现有后缀白名单,任一文件非法 → 整批拒绝 (fail-fast 在入口)

### D3 — 导入进度条

- **前端 polling:** `main.js` 在 upload 后启动 `setInterval(2500ms)` 轮询每文件 `GET /api/upload/{task_id}`
- **进度展示:** 顶部新增 progress bar 区域,每文件一行: `[文件名] [阶段 badge] [百分比]`,失败行红色
- **阶段映射:** `uploaded→5%` / `extracting→20%` / `recognizing→40%` / `chunking→60%` / `embedding→80%` / `done→100%` / `failed→✗`
- **自动停止:** 所有文件到达终态(`done`/`failed`)后 clearInterval,避免无限轮询
- **后端不变:** 复用现有 `/api/upload/{task_id}` GET endpoint,无需新增路由

### D4 — 前端架构调整

- **新增 `upload-panel` 区域:** 覆盖原有简单 input,改为含文件选择 + 上传按钮 + 进度展示的 upload panel
- **状态管理:** `main.js` 维护 `uploadState = Map<task_id, {status, progress, fileName}>`
- **复用现有 ask/panel:** 问答区保持不动,upload panel 作为新区域加入(在 chat 下方或侧边)

### D5 — 导入状态枚举扩展

- **无需改后端:** 现有状态流转 `uploaded→extracting→recognizing→chunking→embedding→storing→done/failed` 已覆盖所有阶段
- **前端映射:** `storing` 作为 90%, `done` 作为 100%
- **留存兼容:** `_task_status` TTL 1h 不变

---

## Testing Decisions

### 总体原则

> 仅测外部行为,不测实现细节。
> 优先通过已有 seam(router TestClient / mock Milvus) 测试,避免引入浏览器自动化。

### T1 — 删除文档 (Router + Milvus Client)

**Seam:** `TestClient` + mock `milvus_client.delete_by_doc_name`

| 测试 | 类型 | 说明 |
|---|---|---|
| delete 成功返回 deleted_chunks | integration | mock delete 返回 42,response 含 deleted_chunks=42 |
| delete 级联清理 task_status | integration | 创建 task → delete → task 不存在 |
| delete 不存在的文档返回 0 + not_found | integration | mock delete 返回 0 |
| delete doc_name 含中文/特殊字符 | integration | URL encode 正确传递 |
| delete_by_doc_name 调 Milvus filter 正确 | unit | mock client.delete,验证 filter 字符串 |

### T2 — 批量上传 (Router)

**Seam:** `TestClient` + mock `trigger_import_sync`

| 测试 | 类型 | 说明 |
|---|---|---|
| 多文件上传返回 N 个 task_id | integration | 上传 3 文件 → response.count=3, 3 个独立 task_id |
| 单文件上传仍兼容 | integration | 上传 1 文件 → 行为同旧 |
| 任一文件后缀非法 → 整批拒绝 400 | integration | 2 pdf + 1 txt → 400,0 个 task |
| 空文件 → 整批拒绝 400 | integration | 含空 body → 400 |
| batch_id 为合法 UUID | integration | response.batch_id 格式正确 |
| 每文件独立 background task | integration | trigger_import_sync 调用 N 次 |

### T3 — 进度条 (前端逻辑)

**Seam:** 前端不可用 pytest TestClient 单独测。策略:
- 后端 `GET /api/upload/{task_id}` 状态返回已由现有 integration test 覆盖
- 前端 polling 逻辑提取为纯函数 `mapStatusToProgress(status) → {percent, label}`,单元测试该函数
- 完整前端行为通过手动 E2E 验证(参考 `e2e-test-report.md` 方式)

| 测试 | 类型 | 说明 |
|---|---|---|
| mapStatusToProgress 各状态映射 | unit | uploaded→5, extracting→20, ..., done→100, failed→-1 |
| polling 间隔定时器 | unit | jest-style mock setTimeout 验证 2500ms |
| 终态自动停止 polling | unit | 所有 done/failed 后不再发起请求 |

### 优先 art

- **router 测试参考:** `tests/integration/test_upload_router.py` — 同样的 mock + TestClient 模式
- **Milvus client 测试参考:** `tests/unit/test_milvus_client.py` — mock `_get_client` 模式
- **现有 batch/upload 单测基准:** `trigger_import_sync` 的成功/失败路径(已在 test_upload_router 覆盖)

---

## Out of Scope

- **HyDE 检索 / Rerank 精排:** 评估数据显示需要后再做(依赖 baseline Recall)
- **检索日志看板:** 命中率/延迟统计,属于 P1 但依赖数据积累
- **用户反馈 (赞/踩):** 质量回馈,需评估框架产出数据后
- **WebSocket 推送:** 进度条用 polling,不引入 WebSocket(部署复杂度不值得)
- **分页 / 全文搜索文档列表:** 当前文档量小(5 份),无需分页
- **文档编辑 / 重命名:** 导入后不可改 doc_name,需删了重传
- **权限隔离:** P2 功能,单人使用场景不需要

---

## Further Notes

### 架构注意事项

1. **删除用 doc_name 还是 task_id?** 选 `doc_name`,因为用户视角认可的是"手册名",task_id 只有系统发起时才有。Milvus 的 `delete(filter='doc_name == "xxx"')` 会删该文档所有 chunk,语义正确。

2. **批量上传背景并发:** `BackgroundTasks` 在线程池执行,`build_import_graph()` 每次返回新实例(LangGraph 不可复用),因此每文件独立 graph 是安全的。

3. **前端 polling 合理性:** 2.5s 间隔 × 1h TTL = 最多 1440 次请求。单用户场景合理。后续如果扩展多用户,再考虑 SSE/WebSocket。

### 当前 Milvus 容量

- 137 chunks, 5 份 PDF — 删除/批量操作在此规模验证即可
- 后续规模增长需评估 `delete(filter=...)` 在大数据集性能

### 关联 Issue

- #10 (评估框架)已关闭,本 spec 不触及评估
- 新功能应新建 Issue,标 `ready-for-agent` 后开发

### 验收标准

- [ ] DELETE /api/documents/xxx 删除后 Milvus 查不到对应 chunk
- [ ] 批量上传 3 文件返回 3 task_id,各独立导入
- [ ] 前端上传后展示进度条,阶段与后端状态同步
- [ ] 所有新旧测试 ≥130+ 仍全绿
