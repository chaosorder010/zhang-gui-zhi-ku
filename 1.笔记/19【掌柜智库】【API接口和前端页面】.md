[TOC]



# 掌柜智库-【API和前端页面】

## 1. 导入API和页面

### 1.1 准备工作

#### 1.1.1 工具类和页面的引入

`utils\sse_utils.py`

`utils\task_utils.py`

`web\page\import.html`

#### 1.1.2 数据根目录配置

.env

```ini
# ====================
# 数据根目录
DATA_BASED_ROOT_DIR=D:\file
```

#### 1.1.3 添加任务追踪

```python
# knowledge/processor/import_processor/base.py

 # 开始：记录节点运行状态
add_running_task(state["task_id"], self.name)

# 2. 执行节点
result = self.process(state)

# 结束：记录节点完成状态
add_done_task(state["task_id"], self.name)
```

#### 1.1.4 修改主流程的run方法

```python
# processor/import_processor/main_graph.py

def run(self, state: ImportGraphState, stream: bool = False):

    if stream:
        # return self.graph.stream(state, stream_mode="values")
        return self.graph.stream(state)
    else:
        return self.graph.invoke(state)
```

### 1.2 代码实现详解

我们将 `web\api\import_service.py` 的实现拆分为 6 个核心部分进行讲解，以便理解每个模块的作用。

#### 1.2.1 应用初始化与跨域配置

```python

# 1. 创建应用
# 标题和描述会在Swagger文档中展示
app = FastAPI(
    title="掌柜智库-导入API",
    description="此文档是掌柜智库导入流程的API接口说明"
)

# 2. 跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许的源
    allow_credentials=True,  # 允许携带cookie
    allow_methods=["*"],  # 允许的请求方法
    allow_headers=["*"],  # 允许的请求头
)
```

#### 1.2.2 静态页面加载

```python
# 3. 静态页面路由：返回文件导入前端页面
# 访问地址：http://localhost:8000/import.html
@app.get("/import.html")  # 对外访问地址
async def get_import_page():
    # 拼接HTML文件绝对路径
    current_dir_parent_path = Path(__file__).absolute().parent.parent
    html_path = current_dir_parent_path / "page" / "import.html"
    # 如果不存在，抛出404异常
    if not html_path.exists():
        raise HTTPException(status_code=404, detail=f"没有查询到页面，地址为：{html_path}")
    return FileResponse(html_path)
```

#### 1.2.3 后台任务逻辑

这是连接 Web 服务与 LangGraph 的桥梁。`run_graph_task` 函数会在后台运行（不阻塞 HTTP 响应），它监听图的执行事件，并实时更新任务状态。

```python
# 4. 后台任务：LangGraph全流程执行
# 独立于主请求线程，由BackgroundTasks触发，避免阻塞接口响应
def run_graph_task(task_id: str, file_dir: str, import_file_path: str):
    """
    LangGraph全流程执行后台任务
    核心流程：初始化状态 → 流式执行图节点 → 实时更新任务状态 → 异常捕获
    任务状态更新：pending → processing → completed/failed
    节点进度更新：每完成一个节点，将节点名加入done_list，供前端轮询查看

    :param task_id: 全局唯一任务ID，关联单个文件的全流程处理
    :param file_dir: 该任务的本地文件存储目录（含临时文件/解析结果）
    :param import_file_path: 上传文件的本地绝对路径
    """
    try:
        # 1. 更新任务全局状态为：处理中
        update_task_status(task_id, "processing")

        # 2. 初始化LangGraph状态
        init_state = {
            "task_id": task_id,
            "file_dir": file_dir,
            "import_file_path": import_file_path,
        }

        # 3. 流式执行LangGraph全流程（stream模式：实时获取每个节点的执行结果）
        workflow = KBImportWorkflow()
        for event in  workflow.run(init_state, stream=True):
            for node_name, node_result in event.items():
                # 将完成的节点名加入【已完成列表】，前端轮询/status/{task_id}可实时获取
                add_done_task(task_id, node_name)

        # 4. 全流程执行完成，更新任务全局状态为：已完成
        update_task_status(task_id, "completed")

    except Exception as e:
        # 5. 捕获全流程异常，更新任务全局状态为：失败，并记录错误日志（含堆栈）
        update_task_status(task_id, "failed")
        logger.info(f"[{task_id}] LangGraph全流程执行失败，异常信息：{str(e)}", exc_info=True)

```

#### 1.2.4 文件上传接口

处理文件上传请求。它负责：

1. 生成全局唯一的 `task_id`。
2. 将文件保存到服务器临时目录。
3. 上传文件到 MinIO 对象存储。
4. 启动后台任务开始处理。

```python
# 5. 核心接口：文件上传接口
# 支持多文件上传，核心流程：接收文件 → 本地保存 → MinIO上传 → 启动后台任务
# 访问地址：http://localhost:8000/upload （POST请求，form-data格式传参）
@app.post("/upload", summary="文件上传接口", description="支持多文件批量上传，自动触发知识库导入全流程")
async def upload_files(background_tasks: BackgroundTasks, files: List[UploadFile] = File(...)):
    """
    文件上传核心接口
    1. 接收前端上传的多文件（PDF/MD为主）
    2. 按「日期/任务ID」分层保存到本地输出目录，避免文件冲突
    3. 将文件上传至MinIO对象存储，做持久化保存
    4. 为每个文件生成唯一TaskID，启动独立的LangGraph后台处理任务
    5. 实时更新任务状态，供前端轮询监控进度

    :param background_tasks: FastAPI后台任务对象，用于异步执行LangGraph流程
    :param files: 前端上传的文件列表（form-data格式）
    :return: 包含上传结果和所有任务ID的JSON响应
    """
    # 1. 构建本地存储根目录：项目根目录/doc/YYYYMMDD（按日期分层，方便管理）
    data_based_root_dir = os.getenv("DATA_BASED_ROOT_DIR")
    data_dir = os.path.join(data_based_root_dir, datetime.now().strftime("%Y%m%d"))
    # 初始化任务ID列表，用于返回给前端（一个文件对应一个TaskID）
    task_ids = []

    # 2. 遍历处理每个上传的文件（多文件批量处理，各自独立生成TaskID）
    for file in files:
        # 生成全局唯一TaskID（UUID4），作为单个文件的全流程标识
        task_id = str(uuid.uuid4())
        task_ids.append(task_id)
        logger.info(f"[{task_id}] 开始处理上传文件，文件名：{file.filename}，文件类型：{file.content_type}")

        # 3. 标记「文件上传」阶段为「运行中」，前端轮询可查
        add_running_task(task_id, "upload_file")

        # 4. 构建该任务的本地独立目录：output/YYYYMMDD/TaskID，避免多文件重名冲突
        file_dir = os.path.join(data_dir, task_id)
        os.makedirs(file_dir, exist_ok=True)  # 目录不存在则创建，存在则不做处理
        # 构建上传文件的本地保存绝对路径
        import_file_path = os.path.join(file_dir, file.filename)

        # 5. 将上传的文件保存到本地临时目录（后续MinIO上传/文件解析均基于此文件）
        with open(import_file_path, "wb") as file_buffer:
            shutil.copyfileobj(file.file, file_buffer)
        logger.info(f"[{task_id}] 文件已保存至本地，路径：{import_file_path}")

        # 6. 将本地文件上传至MinIO对象存储，做持久化保存
        # 构建MinIO中的文件对象名：pdf_files/YYYYMMDD/文件名（按日期分层，和本地一致）
        minio_object_name = f"pdf_files/{datetime.now().strftime('%Y%m%d')}/{file.filename}"
        try:
            # 获取MinIO客户端实例
            minio_client = get_minio_client()

            # 从环境变量获取MinIO的桶名配置
            minio_bucket_name = minio_config.bucket_name

            # 本地文件上传至MinIO（同名文件会自动覆盖，保证文件最新）
            minio_client.fput_object(
                bucket_name=minio_bucket_name,
                object_name=minio_object_name,
                file_path=import_file_path,
                content_type=file.content_type  # 传递文件原始MIME类型
            )
            logger.info(f"[{task_id}] 文件已成功上传至MinIO，桶名：{minio_bucket_name}，对象名：{minio_object_name}")
        except Exception as e:
            # MinIO上传失败，记录警告日志（不中断后续流程，本地文件仍可继续处理）
            logger.warning(f"[{task_id}] 文件上传MinIO失败，将继续执行本地处理流程，异常信息：{str(e)}", exc_info=True)

        # 7. 标记「文件上传」阶段为「已完成」，前端轮询可查
        add_done_task(task_id, "upload_file")

        # 8. 将LangGraph全流程处理加入FastAPI后台任务（异步执行，不阻塞当前接口响应）
        background_tasks.add_task(run_graph_task, task_id, file_dir, import_file_path)
        logger.info(f"[{task_id}] 已将LangGraph全流程加入后台任务，任务已启动")

    # 9. 所有文件处理完毕，返回上传成功信息和所有TaskID（前端基于TaskID轮询进度）
    logger.info(f"多文件上传处理完毕，共处理{len(files)}个文件，生成TaskID列表：{task_ids}")
    return {
        "code": 200,
        "message": f" 文件上传成功, total: {len(files)}",
        "task_ids": task_ids
    }
```

#### 1.2.5 任务状态查询接口

前端轮询此接口以获取进度。它直接从内存中读取由 `task_utils` 维护的任务状态。

```python
# 6. 核心接口：任务状态查询接口
# 前端轮询此接口获取单个任务的处理进度和状态
# 访问地址：http://localhost:8000/status/{task_id} （GET请求）
@app.get("/status/{task_id}", summary="任务状态查询", description="根据TaskID查询单个文件的处理进度和全局状态")
async def get_task_progress(task_id: str):
    """
    任务状态查询接口
    前端轮询此接口（如每秒1次），获取任务的实时处理进度
    返回数据均来自内存中的任务管理字典（task_utils.py），高性能无IO

    :param task_id: 全局唯一任务ID（由/upload接口返回）
    :return: 包含任务全局状态、已完成节点、运行中节点的JSON响应
    """
    # 构造任务状态返回体
    task_status_info: Dict[str, Any] = {
        "code": 200,
        "task_id": task_id,
        "status": get_task_status(task_id),  # 任务全局状态：pending/processing/completed/failed
        "done_list": get_done_task_list(task_id),  # 已完成的节点/阶段列表
        "running_list": get_running_task_list(task_id)  # 正在运行的节点/阶段列表
    }
    # 记录状态查询日志，方便追踪前端轮询情况
    logger.info(
        f"[{task_id}] 任务状态查询，当前状态：{task_status_info['status']}，已完成节点：{task_status_info['done_list']}")
    return task_status_info
```

#### 1.2.6 启动入口

配置 Uvicorn 服务器启动参数

```python
if __name__ == "__main__":
    uvicorn.run(app=app,host="127.0.0.1",port=8000)
```

### 1.3 接口与 Task 列表关系详解

本服务通过 `utils.task_utils` 模块维护了一个内存中的任务状态列表，实现了前后端的状态同步。

1.  **上传阶段 (`/upload`)**:
    *   请求到达时，生成 `task_id`。
    *   调用 `add_running_task(task_id, "upload_file")`：此时前端查询状态，会看到 "开始上传文件" 正在运行。
    *   文件上传 MinIO 成功后，调用 `add_done_task(task_id, "upload_file")`：此时前端会看到 "开始上传文件" 变为已完成。

2.  **处理阶段 (`run_graph_task`)**:
    *   后台任务启动，调用 `update_task_status(task_id, "processing")`：标记任务整体正在处理中。
    *   LangGraph 每执行完一个节点（如 PDF 转 Markdown），流式输出会捕获到事件。
    *   调用 `add_done_task(task_id, node_name)`：将该节点标记为已完成。前端轮询时，进度条或日志列表会相应更新。

3.  **完成阶段**:
    *   图执行结束，调用 `update_task_status(task_id, "completed")`。
    *   前端收到 completed 状态，提示用户导入成功。

### 1.4 页面导入配置

**文件位置**: `web/page/import.html`

这是一个简洁的原生 HTML/JS 页面，实现了以下功能：

1.  **文件拖拽/选择**：支持 PDF 和 MD 文件。
2.  **上传进度条**：显示文件上传到服务器的进度。
3.  **状态轮询**：上传成功后，通过 `setInterval` 每 2 秒请求一次 `/status` 接口。
4.  **日志展示**：根据后端返回的 `done_list` 和 `running_list`，动态渲染任务执行日志（如 "node_entry已完成", "node_pdf_to_md正在进行..."）。

### 1.5 服务启动与测试流程

#### 1.5.1 启动服务

在项目根目录下（`knowledge_base`），运行以下命令：

```bash
# 方式一：直接运行 Python 模块
✅ 直接执行脚本中的 if __name__ == "__main__" 代码块
✅ 会启动内置的 uvicorn（第 233 行）
❌ 没有热重载：代码修改后需要手动重启
✅ 适合简单测试

# 方式二：使用 uvicorn 命令
✅ 热重载：代码修改后自动重启
✅ 生产级 ASGI 服务器
✅ 支持多进程
✅ 开发环境首选
uv run uvicorn app.import_process.api.file_import_service:app --host 0.0.0.0 --port 8000 --reload
```

看到 `Application startup complete` 即表示启动成功。

前端页面：http://localhost:8000/import.html
API 文档：http://localhost:8000/docs
上传接口：http://localhost:8000/upload

#### 1.5.2 页面测试

1.  打开浏览器访问：`http://127.0.0.1:8000/import.html`
2.  点击上传区域，选择一个测试文件（如 `hak180产品安全手册.pdf`）。
3.  **观察页面交互**：
    *   状态变为 "上传中..." -> "处理中..."。
    *   点击 "日志（点击展开）"，可以看到节点逐个执行的过程。
    *   等待所有节点执行完毕，状态变为 "已完成" (绿色)。



## 2. 检索API和前端页面

### 2.1 前端交互设计

#### 2.1.1 页面核心组件

- **顶栏 (Topbar)**：展示服务连接状态与流式开关。
- **对话区 (Chat)**：
  - **用户气泡**：展示提问内容。
  - **系统气泡**：集成**文本答案**与**处理进度**（折叠面板），实时展示后台（检索/重排/生成）的执行状态。
- **输入区 (Composer)**：支持快捷发送与多行输入。

#### 2.1.2 数据交互闭环

前端与后端的全双工交互流程如下：

1. **会话初始化**：加载页面时生成或读取 `session_id`，作为用户唯一标识。
2. **提交任务**：点击发送 -> POST `/query`（携带问题与流式标记） -> 获取 `session_id` 确认任务已接收。
3. **建立长连接 (SSE)**：立即通过 `EventSource` 监听 `/stream/{session_id}`，建立实时通信管道。
4. **事件驱动更新**：
   - `ready`: 连接握手成功。
   - `progress`: **实时更新进度条**（如：正在检索... -> 检索完成）。
   - `delta`: **流式逐字输出**（打字机效果）。
   - `final`: 接收完整答案与引用源。

基于此逻辑，后端需提供 `/query`（任务提交）与 `/stream`（事件推送）两个核心接口。

### 2.2 服务接口设计

本节详细定义查询服务的所有对外接口，包括页面访问、任务提交、流式推送及历史管理。

#### 2.2.1 页面访问接口

- **路径**: `/chat.html` (GET)
- **功能**: 返回前端聊天界面。
- **响应**: HTML 静态页面。

#### 2.2.2 检索查询接口

- **路径**: `/query` (POST)

- **功能**: 接收用户提问并启动后台处理图逻辑。

- **参数**:

  ```json
  {
    "query": "万用表怎么测量电压？",
    "session_id": "可选，未传则后台自动生成",
    "is_stream": true // 是否启用流式推送
  }
  ```

- **响应 (is_stream: true)**:

  ```json
  { "message": "结果正在处理中...", "session_id": "xxx-uuid" }
  ```

- **响应 (is_stream: false)**:

  ```json
  { "message": "处理完成！", "session_id": "xxx", "answer": "回答内容...", "done_list": [] }
  ```

#### 2.2.3 流式获取接口 (SSE)

- **路径**: `/stream/{session_id}` (GET)
- **功能**: 建立 SSE 长连接，实时推送任务进度与生成文本。
- **推送数据格式 (JSON)**:
  - **progress 事件**: `{"done_list": ["节点A", "节点B"], "running_list": ["节点C"]}`
  - **delta 事件**: `{"text": "生成的增量字符"}`
  - **final 事件**: `{"answer": "完整最终答案"}`
  - **error 事件**: `{"error": "错误详情"}`

#### 2.2.4 会话历史查询

- **路径**: `/history/{session_id}` (GET)

- **功能**: 从 MongoDB 中获取当前会话的历史聊天记录。

- **参数**: `limit` (可选，默认50条)

- **响应**:

  ```json
  {
    "session_id": "xxx",
    "items": [
      {
        "_id": str(r.get("_id")) if r.get("_id") is not None else "",
        "session_id": r.get("session_id", ""),
         "role": r.get("role", ""),
         "text": r.get("text", ""),
         "rewritten_query": r.get("rewritten_query", ""),
          "item_names": r.get("item_names", []),
          "ts": r.get("ts")
        }
    ]
  }
  ```

#### 2.2.5 清空会话历史

- **路径**: `/history/{session_id}` (DELETE)
- **功能**: 删除 MongoDB 中该会话的所有记录。
- **响应**: `{ "message": "History cleared", "deleted_count": 10 }`

#### 2.2.6 健康检查接口

- **路径**: `/health` (GET)
- **功能**: 检查服务存活状态。
- **响应**: `{ "ok": True }`

### 2.3 代码实现详解

#### 2.3.1 前后端交互说明

知识库查询服务的流式响应流程 ，涉及到四个核心模块的协同工作：

1. Web 服务层 ( query_service.py ): 负责接收请求、建立 SSE 连接。
2. SSE 工具层 ( sse_utils.py ): 负责管理消息队列、打包和推送事件。
3. 任务状态层 ( task_utils.py ): 负责记录每个节点的执行进度，并自动触发 SSE 推送。
4. 图节点执行层 ( query_process/ ): 实际的业务逻辑节点（如检索、Rerank、生成答案），它们通过更新状态来驱动进度条。

#### 2.3.2  应用初始化与跨域配置

在 `web/api` 目录下创建 `query_service.py`，我们将代码拆解为以下几个部分进行实现。

```python
# 1. 创建应用
app = FastAPI(
    title="掌柜智库-查询API",
    description="此文档是掌柜智库查询流程的API接口说明"
)

# 2. 跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许的源
    allow_credentials=True,  # 允许携带cookie
    allow_methods=["*"],  # 允许的请求方法
    allow_headers=["*"],  # 允许的请求头
)

# 3. 静态页面路由
@app.get("/chat.html")  # 对外访问地址
async def chat():
    current_dir_parent_path = Path(__file__).absolute().parent.parent
    html_path = current_dir_parent_path / "page" / "chat.html"
    # 如果不存在，抛出404异常
    if not html_path.exists():
        raise HTTPException(status_code=404, detail=f"没有查询到页面，地址为：{html_path}")
    return FileResponse(html_path)
```

#### 2.3.3 定义数据模型 (Pydantic)

定义前端请求的数据结构，确保参数类型安全，并增加兼容字段。

```python
# 定义接口接收的数据结构
class QueryRequest(BaseModel):
    """查询请求数据结构"""
    query: str = Field(..., description="查询内容")  # ...必须填写
    session_id: str = Field(None, description="会话ID")
    is_stream: bool = Field(False, description="是否流式返回")
```

#### 2.3.4 实现核心查询逻辑

这是最关键的逻辑部分，包含后台任务处理函数 `run_query_graph` 和 API 接口 `/query`。

```python
@app.post("/query")
async def query(background_tasks: BackgroundTasks, request: QueryRequest):
    """
    1 解析参数
    2 更新任务状态
    3 调用处理流程图
    4 返回结果
    :param background_tasks:
    :param request:
    :return:
    """
    user_query = request.query
    session_id = request.session_id if request.session_id else str(uuid.uuid4())

    # 处理是不是流式返回结果
    is_stream = request.is_stream
    if is_stream:
        # 创建一个字典 存储对一个session_id : queue 结果队列
        create_sse_queue(session_id)
    # 更新任务状态
    # 当前会话id作为key! 整体装填处于运行中！
    update_task_status(session_id, TASK_STATUS_PROCESSING,is_stream)

    print("开始处理流程... 是否流式:", is_stream, f"其他参数:{user_query}, session_id:{session_id}")

    if is_stream:
        # 如果是流式，则返回一个流式响应，过程不断地推送
        # 运行执行图对象方法
        background_tasks.add_task(run_query_graph, session_id,user_query,is_stream)
        # 返回结果
        print("开始处理结果....")
        return {
            "message":"结果正在处理中...",
            "session_id":session_id
        }
    else:
        # 同步运行
        run_query_graph(session_id, user_query, is_stream)
        answer = get_task_result(session_id,"answer","")
        return {
            "message":"处理完成！",
            "session_id":session_id,
            "answer":answer,
            "done_list":[]
        }

# 定义查询接口
def run_query_graph(session_id: str, user_query: str, is_stream: bool = True):
    print(f"开始流程图处理...{session_id} {user_query} {is_stream}")

    init_state = {
        "original_query": user_query,
        "session_id": session_id,
        "is_stream": is_stream
    }

    try:
        workflow = KBQueryWorkflow()
        workflow.run(init_state, stream=is_stream)
        update_task_status(session_id, TASK_STATUS_COMPLETED, is_stream)
    except Exception as e:
        print(f"流程执行异常: {e}")
        update_task_status(session_id, TASK_STATUS_FAILED, is_stream)
        if is_stream:
            push_to_session(session_id, SSEEvent.ERROR, {"error": str(e)})

@app.get("/stream/{session_id}")
async def stream(session_id: str, request: Request):
    print("调用流式/stream...")
    """
    sse 实时返回结果
    """
    return StreamingResponse(
        sse_generator(session_id, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
```

#### 2.3.5 历史会话管理

```python
@app.delete("/history/{session_id}")
async def clear_chat_history(session_id: str):
    """
    清空指定会话的历史记录
    """
    count = clear_history(session_id)
    return {"message": "历史会话已清空", "deleted_count": count}

@app.get("/history/{session_id}")
async def history(session_id: str, limit: int = 50):
    """
    查询当前会话历史记录
    """
    try:
        records = get_recent_messages(session_id, limit=limit)
        items = []
        for r in records:
            items.append({
                "_id": str(r.get("_id")) if r.get("_id") is not None else "",
                "session_id": r.get("session_id", ""),
                "role": r.get("role", ""),
                "text": r.get("text", ""),
                "rewritten_query": r.get("rewritten_query", ""),
                "item_names": r.get("item_names", []),
                "ts": r.get("ts")
            })
        return {"session_id": session_id, "items": items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"history error: {e}")
```

#### 2.3.6 健康检查接口

```python
# 证明服务器启动即可
@app.get("/health")
async def health():
    """
    检查服务是否正常
    """
    return {"ok": True}
```

#### 2.3.7 启动查询服务

```python
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8001)
```



