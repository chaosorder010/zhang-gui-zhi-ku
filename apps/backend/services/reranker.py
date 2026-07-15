"""LLM-based Rerank: 对 Milvus 召回的 chunk 做精排.

接口: rerank_chunks(chunks, question, llm) -> list[dict].
- 调用 LLM 给每条 chunk 打 1-5 分 + 理由, 按分数降序重排.
- 异常 / 解析失败时退回原始 Milvus 顺序, 不丢 chunk, 不修改输入列表.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage

logger = logging.getLogger(__name__)


# 默认 Rerank prompt: 给 chunk 列表 + 问题, 返回 JSON 数组 [{idx, score, reason}]
RERANK_PROMPT_TEMPLATE = """你是一个相关性评分助手. 给定用户问题 (question) 和若干参考资料 (chunks), 请按每条资料与问题的相关性打分.

评分标准:
- 5: 直接、完整回答问题
- 4: 强相关, 提供主要答案
- 3: 部分相关, 提供背景信息
- 2: 弱相关, 仅涉及同类主题
- 1: 完全不相关

question: {question}

{chunks}

请严格返回 JSON 数组, 每项包含:
- idx: 资料序号 (从 1 开始, 与上方 [N] 编号对应)
- score: 1-5 整数
- reason: 一句话理由

示例:
[{{"idx":1,"score":4,"reason":"直接回答问题..."}}, {{"idx":2,"score":1,"reason":"不相关"}}]

仅返回 JSON, 不要解释.
"""


def rerank_chunks(
    chunks: list[dict],
    question: str,
    llm: Any,
    prompt_template: str = RERANK_PROMPT_TEMPLATE,
    max_chunk_chars: int = 500,
) -> list[dict]:
    """LLM 精排 chunk 列表.

    Args:
        chunks: Milvus 召回的 chunk 列表 (每项至少含 "text")
        question: 用户问题
        llm: LLM 实例, 需实现 invoke([HumanMessage]) -> response (含 .content)
        prompt_template: 可注入自定义 prompt (测试用)
        max_chunk_chars: 单条 chunk 送入 LLM 的最大字符数

    Returns:
        按相关性降序排列的新 chunk 列表.
        异常 / 解析失败时返回原始顺序的拷贝 (不丢 chunk, 不修改输入).
    """
    if not chunks or len(chunks) <= 1:
        return list(chunks)

    numbered = _format_chunks(chunks, max_chunk_chars)
    prompt = prompt_template.format(question=question, chunks=numbered)

    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        content = getattr(response, "content", str(response))
        scores = _parse_scores(content)
        if not scores:
            logger.warning("[rerank] LLM 返回空分数, 退回原始顺序")
            return list(chunks)
        return _apply_scores(chunks, scores)
    except Exception as e:
        logger.warning("[rerank] LLM 调用失败, 退回原始顺序: %s", e)
        return list(chunks)


def _format_chunks(chunks: list[dict], max_chars: int) -> str:
    """把 chunk 列表拼成带编号的文本, 供 LLM 评分."""
    lines = []
    for i, c in enumerate(chunks, 1):
        text = c.get("text", "").strip()
        if len(text) > max_chars:
            text = text[:max_chars] + "..."
        lines.append(f"[{i}] {text}")
    return "\n\n".join(lines)


def _parse_scores(content: str) -> list[dict]:
    """解析 LLM 返回的 JSON 分数数组.

    支持:
    - 纯 JSON 数组
    - 被 ```json ... ``` 包裹的 JSON
    - 前后有额外文字 (取第一个 '[' 到最后一个 ']')
    """
    text = content.strip()
    if not text:
        return []

    # 去 ```json ... ``` 包裹
    if "```" in text:
        # 取第一对 ``` 之间的内容
        parts = text.split("```")
        for part in parts:
            stripped = part.strip()
            if stripped.startswith("json"):
                stripped = stripped[4:].strip()
            if stripped.startswith("["):
                text = stripped
                break

    # 取第一个 '[' 到最后一个 ']'
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end <= start:
        return []
    text = text[start : end + 1]

    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return []

    if not isinstance(data, list):
        return []

    valid = []
    for item in data:
        if not isinstance(item, dict):
            continue
        idx = item.get("idx")
        score = item.get("score")
        if isinstance(idx, int) and isinstance(score, (int, float)):
            valid.append({"idx": idx, "score": float(score), "reason": item.get("reason", "")})
    return valid


def _apply_scores(chunks: list[dict], scores: list[dict]) -> list[dict]:
    """按分数降序重排 chunk. 未评分的 chunk 视为 0 分, 按原始顺序排在末尾."""
    # idx (1-based) -> score
    score_map = {item["idx"]: item["score"] for item in scores}

    # 打包 (原始位置, chunk, score), 稳定排序: 先按 score 降序, 同分按原始位置
    indexed = [(i, c, score_map.get(i + 1, 0.0)) for i, c in enumerate(chunks)]
    indexed.sort(key=lambda t: (-t[2], t[0]))
    return [c for _, c, _ in indexed]
