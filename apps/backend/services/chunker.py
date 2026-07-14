"""按 Markdown 章节标题递归分块 + item_name 拼头."""
from __future__ import annotations

import re
from typing import Optional

# 匹配 markdown 标题, 如 "## 1.2 小节"
_HEADER_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)


def chunk_by_section(
    markdown: str,
    item_name: Optional[str] = None,
    max_chars: int = 800,
    header_level: int = 2,
) -> list[dict]:
    """按指定级别的标题拆分 markdown, 每块开头拼 item_name.

    Args:
        markdown: 原始 markdown 文本
        item_name: 主体名, 会拼到每块开头, 如 "[iPhone16] 内容..."
        max_chars: 单块最大字符数 (含 item_name 标注)
        header_level: 在哪个深度的标题上切分. 2=##, 3=###

    Returns:
        list of {"text": str, "chunk_id": int, "item_name": Optional[str]}
    """
    tag = f"[{item_name}] " if item_name else ""

    if not markdown.strip():
        return [{"text": tag.strip(), "chunk_id": 0, "item_name": item_name}]

    # 找到所有**恰好**匹配深度的标题位置 (header_level=2 只切 ##, 不切 #)
    sections = []
    for m in _HEADER_RE.finditer(markdown):
        level = len(m.group(1))
        if level == header_level:
            sections.append((m.start(), m.group(0), m.end()))

    if not sections:
        # Auto-fallback: 指定深度无标题时, 尝试 level-1 (#) 标题.
        # MinerU 输出的 markdown 常见全 # 一级标题, 需此兜底避免退化成单块.
        if header_level > 1:
            for m in _HEADER_RE.finditer(markdown):
                level = len(m.group(1))
                if level == 1:
                    sections.append((m.start(), m.group(0), m.end()))

    if not sections:
        # 没有可读标题, 作为一整块返回
        return [{"text": _with_tag(tag, markdown), "chunk_id": 0, "item_name": item_name}]

    chunks: list[dict] = []
    for i, (start, header_text, content_start) in enumerate(sections):
        end = sections[i + 1][0] if i + 1 < len(sections) else len(markdown)
        body = markdown[content_start:end].strip()
        block = f"{header_text}\n\n{body}" if body else header_text
        text = _with_tag(tag, block)
        chunks.append({"text": text, "chunk_id": i, "item_name": item_name})

    # 合并超短块 (小于 max_chars 一半则与后一块合并), 再按 max_chars 兜底裁剪
    merged = _merge_short(chunks, max_chars)
    # 重新计数
    for i, c in enumerate(merged):
        c["chunk_id"] = i
    return merged


def _with_tag(tag: str, block: str) -> str:
    if not tag:
        return block.strip()
    return f"{tag}{block.strip()}"


def _merge_short(chunks: list[dict], max_chars: int) -> list[dict]:
    """合并过短的块 (单块 < min_section_chars 才合并), 然后按 max_chars 兜底切分."""
    if not chunks:
        return chunks

    # 只有极短的块才合并 — 阈值按文档长度自适应, 避免吃掉正常块
    min_section_chars = max(80, max_chars // 8)

    merged: list[dict] = []
    buffer: dict | None = None

    for c in chunks:
        if buffer is None:
            buffer = dict(c)
            continue
        # 仅当 buffer + 下一块仍 <= max_chars * 0.7, 且 buffer 当前长度 < min_section_chars
        can_merge = (
            len(buffer["text"]) < min_section_chars
            and len(buffer["text"]) + len(c["text"]) + 2 <= int(max_chars * 0.7)
        )
        if can_merge:
            buffer["text"] = buffer["text"] + "\n\n" + c["text"]
        else:
            merged.append(buffer)
            buffer = dict(c)
    if buffer is not None:
        merged.append(buffer)

    final: list[dict] = []
    for m in merged:
        if len(m["text"]) <= max_chars:
            final.append(m)
        else:
            parts = _split_text(m["text"], max_chars)
            final.extend(parts)
    return final


def _split_text(text: str, max_chars: int) -> list[dict]:
    """按字符硬切 (fallback, 保留 item_name tag 在每段头部)."""
    # 检测头部是否有 [item_name] tag
    tag = ""
    body = text
    if text.startswith("["):
        idx = text.find("]")
        if idx != -1:
            tag = text[: idx + 2]  # 含尾部空格
            body = text[idx + 2 :]

    result: list[dict] = []
    i = 0
    while i < len(body):
        end = min(i + max_chars - len(tag), len(body))
        piece = body[i:end]
        item_name = tag.strip().strip("[]") if tag else None
        result.append({"text": tag + piece, "chunk_id": -1, "item_name": item_name})
        i = end
    return result
