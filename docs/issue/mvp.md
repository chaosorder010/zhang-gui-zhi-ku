使用路线c
     不需要隐私保护了

关于技术栈
    LLM调用使用langchain
    后端框架
        fastapi

    工作流编排
        langgraph

    向量数据库
        Milvus

    | 文档数据库 | MongoDB |
    | --- | --- |
    | 对象存储 | MinIO |
    | --- | --- |
        存图片

    | PDF解析 | MinerU |
    | --- | --- |
    | 前端 | HTML + CSS + JS |
    | --- | --- |
    重排序
        BGE-Reranker-Large / qwen3-rerank


补充
    不需要溯源了
    输入数据
        支持pdf、md

    导入
        导入时需要 主体识别 item name reconigtion 
            存入Milvus时放入itemname常量字段
            embdding时 itemname拼接到开头


    检索
        三路检索
            稠密 + 稀疏 检索
            hyde假设性文档检索
            mcp 网络搜索

        对三路结果rrf 倒数排名融合
        rerank  精排
        补充
            需要主体识别：item



