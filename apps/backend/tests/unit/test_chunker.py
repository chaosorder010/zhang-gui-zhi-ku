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


@pytest.mark.unit
class TestChunkerHeaderLevelFallback:
    """真实 MinerU markdown 全用 # 一级标题时, chunker 应 auto-fallback 到 level-1."""

    def test_fallback_to_h1_when_no_h2(self):
        """文档只有 # 标题无 ## 时, 应 fallback 按 # 切割而非退化成单块."""
        md = (
            "# 用户指南\n\n前言内容。\n\n"
            "# 外观介绍\n\n" + "接口描述内容。\n" * 20 + "\n"
            "# 安全信息\n\n" + "安全相关内容。\n" * 20 + "\n"
        )
        chunks = chunk_by_section(md, item_name="Device", max_chars=800)
        assert len(chunks) >= 2, "应 fallback 按 # 切割, 不应退化成单块"
        assert all(c["text"].startswith("[Device]") for c in chunks)

    def test_no_fallback_when_h2_exists(self):
        """文档有 ## 标题时, 不应 fallback 到 #."""
        # 每节内容需 > min_section_chars (max_chars//8=100), 避免 _merge_short 合并
        md = (
            "# 手册\n\n前言。\n\n"
            "## 章节A\n\n" + "这是章节A的详细内容, 讨论各种硬件规格参数和性能指标。\n" * 10 + "\n"
            "## 章节B\n\n" + "这是章节B的详细内容, 讨论各种软件配置方法和使用技巧。\n" * 10 + "\n"
        )
        chunks = chunk_by_section(md, item_name="X", max_chars=800)
        assert len(chunks) == 2
        assert "章节A" in chunks[0]["text"]
        assert "章节B" in chunks[1]["text"]

    def test_fallback_preserves_all_content(self):
        """fallback 分块后, 所有正文内容应完整保留."""
        md = (
            "# 第一章\n\n第一段正文。\n\n"
            "# 第二章\n\n第二段正文。\n\n"
            "# 第三章\n\n第三段正文。\n\n"
        )
        chunks = chunk_by_section(md, item_name="Book", max_chars=1000)
        full = " ".join(c["text"] for c in chunks)
        assert "第一段正文" in full
        assert "第二段正文" in full
        assert "第三段正文" in full
