"""主体识别: 从 markdown 全文 LLM 抽取 item name."""
from __future__ import annotations

import re
from typing import Optional

from langchain_core.messages import HumanMessage
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI

from apps.backend.core.config import Settings


def build_recognizer(settings: Settings) -> BaseChatModel:
    """根据 settings 构造 LLM 实例."""
    return ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        temperature=0,
    )


# 产品名常用中文字符 + 数字组合, 粗略校验
_ITEM_PATTERN = re.compile(r"[一-鿿A-Za-z0-9]+")


def recognize_item(
    markdown: str,
    llm: BaseChatModel,
    settings: Settings | None = None,
    max_chars: int = 2000,
) -> str:
    """LLM 抽取文档主体名 (产品名/型号).

    Args:
        markdown: 文档全文 (或前 max_chars 字符)
        llm: 注入的 LLM 实例
        settings: 仅 build_recognizer 时使用, 本函数内保留为向后兼容
        max_chars: 送入 LLM 的最大字符数

    Returns:
        主体名, 如 "iPhone 16 Pro"; 识别失败返回 "未知"
    """
    sample = markdown[:max_chars].strip()
    if not sample:
        return "未知"

    prompt = (
        "你是一个文档分析助手。给定一份电子产品手册/维修指南的部分内容,"
        "请识别描述的产品名称/型号 (item name)。\n"
        "仅输出产品名或型号, 不要解释、标点或额外文字。\n"
        "如果看不出, 输出: 未知。\n\n"
        f"文档内容:\n{sample}"
    )

    response = llm.invoke([HumanMessage(content=prompt)])
    raw = getattr(response, "content", str(response)).strip()

    # 清理: 去引号, 去尾部标点
    cleaned = raw.strip().strip('"').strip("'").strip()

    # 校验是否看起来像产品名 (至少含字母/数字)
    if not cleaned or not _ITEM_PATTERN.search(cleaned):
        return "未知"

    # 截断过长的内容
    if len(cleaned) > 100:
        cleaned = cleaned[:100]

    return cleaned
