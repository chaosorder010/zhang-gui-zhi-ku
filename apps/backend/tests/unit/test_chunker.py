"""单元测试: 按标题分块 + item_name 拼头.

Seam: chunker.chunk_by_section, 纯函数。
"""
from __future__ import annotations

import pytest
from apps.backend.services.chunker import chunk_by_section


@pytest.mark.unit
class TestChunkBySection:
    def test_basic_split_by_h2(self):
        # 每块内容 > min_section_chars 避免合并
        content_a = "这是章节A的详细内容, 讨论iPhone16的外观设计、材质和颜色选项。\n" * 8
        content_b = "这是章节B的详细内容, 讨论iPhone16的硬件配置和性能指标。\n" * 8
        md = (
            "# 手册标题\n\n忽略我(前导内容)\n\n"
            f"## 章节A\n\n{content_a}\n"
            f"## 章节B\n\n{content_b}\n"
        )
        chunks = chunk_by_section(md, item_name="iPhone16", max_chars=1000)
        assert len(chunks) == 2
        for c in chunks:
            assert c["text"].startswith("[iPhone16]")
        full_text = " ".join(c["text"] for c in chunks)
        assert "外观设计" in full_text
        assert "硬件配置" in full_text

    def test_respects_max_chars(self):
        md = "# T\n\n" + "字" * 500 + "\n\n## S1\n\n" + "词" * 500 + "\n"
        chunks = chunk_by_section(md, item_name="X", max_chars=300)
        for c in chunks:
            assert len(c["text"]) <= 400  # 容忍 item_name 标注 + overshoot

    def test_empty_markdown_returns_single_chunk(self):
        chunks = chunk_by_section("", item_name="X")
        assert len(chunks) == 1
        assert chunks[0]["text"].strip() == "[X]"

    def test_item_name_optional(self):
        md = "# T\n\nhello\n"
        chunks = chunk_by_section(md, item_name=None)
        assert chunks[0]["text"].startswith("# T")

    def test_chunk_ids_increment(self):
        md = "# A\n\na1\n\n# B\n\nb1\n\n# C\n\nc1\n"
        chunks = chunk_by_section(md, item_name="X", max_chars=500)
        ids = [c["chunk_id"] for c in chunks]
        assert ids == list(range(len(ids)))

    def test_preserves_all_text(self):
        md = "## H1\n\n第一段内容。\n\n## H2\n\n第二段内容。\n\n"
        chunks = chunk_by_section(md, item_name="Doc", max_chars=1000)
        reconstructed = " ".join(c["text"].replace("[Doc] ", "", 1) for c in chunks)
        assert "第一段" in reconstructed
        assert "第二段" in reconstructed
