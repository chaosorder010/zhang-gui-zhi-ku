# 页面/流程说明

## 用户页面

| 页面 | 路由 | 说明 |
|---|---|---|
| 问答页 | `/` | 主界面, 输入问题, 显示回答+来源 |
| 上传页 | `/upload` | 上传 PDF/MD 文档 |

## 问答流程

```
用户输入问题
    |
    v
FastAPI 接收
    |
    v
LangGraph 编排
    |-- 读取对话历史 (多轮上下文)
    |-- 三路并行检索
    |     |-- 稠密: 向量相似度 Milvus
    |     |-- 稀疏: BM25 Milvus
    |     |-- HyDE: 生成假设文档 -> embedding -> Milvus
    |-- MCP 网络搜索 (可选)
    |
    v
RRF 倒数排名融合 (三路结果)
    |
    v
Rerank 精排 (BGE-Reranker-Large)
    |
    v
组装 prompt (上下文 + 检索片段)
    |
    v
云端 LLM API 生成 (LangChain)
    |
    v
返回回答 + 来源片段
    |
    v
前端展示, 存入对话历史
```

## 导入(索引)流程

```
上传 PDF/MD
    |
    v
MinerU 解析 (文本+图片)
    |
    v
主体识别 (item name)
    |
    v
按章节/标题分块
    |
    v
每 chunk 开头拼接 item_name
    |
    v
embedding 向量化
    |
    v
Milvus 入库 (chunk + item_name 常量字段 + 元数据)
```

## 导航问答

问答页 <--> 上传页 (顶部导航切换)
