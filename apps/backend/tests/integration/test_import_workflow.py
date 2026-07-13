"""集成测试: LangGraph 导入工作流.

Seam: import_workflow 编排。mock 所有外部服务 (MinerU / LLM / Milvus)。
"""
from __future__ import annotations

from unittest.mock import patch, MagicMock
import pytest

from apps.backend.services.import_workflow import (
    build_import_graph,
    ImportState,
    _node_extract,
    _node_recognize,
    _node_chunk,
    _node_embed,
    _node_store,
)


def _make_state(**overrides) -> ImportState:
    base: ImportState = {
        "task_id": "local-1",
        "file_name": "m.pdf",
        "file_binary": b"binary",
        "item_name": None,
        "markdown": "",
        "chunks": [],
        "vectors": [],
        "status": "uploaded",
        "error": None,
        "mineru_base_url": "https://mineru.net/api/v4",
        "mineru_token": "test-tok",
        "openai_api_key": "k",
        "openai_base_url": "https://x",
        "openai_model": "gpt-4o-mini",
    }
    base.update(overrides)
    return base


@pytest.mark.integration
class TestNodeExtract:
    @patch("apps.backend.services.import_workflow.extract_markdown")
    def test_extract_updates_markdown(self, mock_extract):
        mock_extract.return_value = "# 手册\n\n## 章节一\n\n正文内容"
        state = _node_extract(_make_state())
        assert state["markdown"] == "# 手册\n\n## 章节一\n\n正文内容"
        assert state["status"] == "extracting"

    @patch("apps.backend.services.import_workflow.extract_markdown")
    def test_extract_failure_sets_failed(self, mock_extract):
        mock_extract.side_effect = RuntimeError("boom")
        state = _node_extract(_make_state())
        assert state["status"] == "failed"
        assert "extract" in state["error"]

    @patch("apps.backend.services.import_workflow.extract_markdown")
    def test_extract_empty_markdown_fails(self, mock_extract):
        """MinerU 返回空内容时应标记失败而非继续."""
        mock_extract.return_value = ""
        state = _node_extract(_make_state())
        assert state["status"] == "failed"
        assert "extract" in state["error"].lower() or "空" in state["error"]

    @patch("apps.backend.services.import_workflow.extract_markdown")
    def test_extract_whitespace_only_fails(self, mock_extract):
        """MinerU 仅返回空白字符时应标记失败."""
        mock_extract.return_value = "   \n\n   \t  "
        state = _node_extract(_make_state())
        assert state["status"] == "failed"

    @patch("apps.backend.services.import_workflow.extract_markdown")
    def test_extract_no_h2_header_fails(self, mock_extract):
        """无 ## 标题时 chunker 会退化为单块，应标记失败."""
        mock_extract.return_value = "# 一级标题\n\n一些内容但没有二级标题"
        state = _node_extract(_make_state())
        assert state["status"] == "failed"
        assert "标题" in state["error"]

    @patch("apps.backend.services.import_workflow.extract_markdown")
    def test_extract_valid_with_h2_passes(self, mock_extract):
        """有 ## 标题的正常 markdown 通过校验."""
        mock_extract.return_value = "# 手册\n\n## 章节一\n\n内容\n\n## 章节二\n\n更多"
        state = _node_extract(_make_state())
        assert state["status"] == "extracting"
        assert "## 章节一" in state["markdown"]


@pytest.mark.integration
class TestNodeRecognize:
    @patch("apps.backend.services.import_workflow.recognize_item")
    def test_recognize_sets_item_name(self, mock_recognize):
        mock_recognize.return_value = "iPhone16"
        state = _node_recognize(_make_state(markdown="## md"))
        assert state["item_name"] == "iPhone16"
        assert state["status"] == "recognizing"

    @patch("apps.backend.services.import_workflow.recognize_item")
    def test_recognize_failure_sets_failed(self, mock_recognize):
        mock_recognize.side_effect = RuntimeError("bad")
        state = _node_recognize(_make_state(markdown="## md"))
        assert state["status"] == "failed"
        assert "recognize" in state["error"]


@pytest.mark.integration
class TestNodeChunk:
    def test_chunk_creates_chunks(self):
        md = "## A\n\n" + "内容A。" * 50 + "\n\n## B\n\n" + "内容B。" * 50
        state = _node_chunk(_make_state(markdown=md, item_name="iPhone16"))
        assert len(state["chunks"]) >= 2
        assert state["status"] == "chunking"

    def test_chunk_failure_sets_failed(self):
        # 让 chunk_by_section 异常 - 实际上不会主动异常, 这里测状态传递
        state = _node_chunk(_make_state(status="failed", error="prior: x"))
        assert state["status"] == "failed"


@pytest.mark.integration
class TestNodeEmbed:
    @patch("apps.backend.services.import_workflow.embed_chunks")
    def test_embed_produces_vectors(self, mock_embed):
        mock_embed.return_value = [{"dense": [0.1], "sparse": {}}]
        state = _node_embed(_make_state(chunks=[{"text": "x"}]))
        assert len(state["vectors"]) == 1
        assert state["status"] == "embedding"

    @patch("apps.backend.services.import_workflow.embed_chunks")
    def test_embed_failure_sets_failed(self, mock_embed):
        mock_embed.side_effect = RuntimeError("no gpu")
        state = _node_embed(_make_state(chunks=[{"text": "x"}]))
        assert state["status"] == "failed"


@pytest.mark.integration
class TestNodeStore:
    @patch("apps.backend.services.import_workflow.bulk_upsert")
    def test_store_marks_done(self, mock_upsert):
        state = _node_store(_make_state(vectors=[{"text": "x"}]))
        assert state["status"] == "done"
        mock_upsert.assert_called_once()

    @patch("apps.backend.services.import_workflow.bulk_upsert")
    def test_store_failure_sets_failed(self, mock_upsert):
        mock_upsert.side_effect = RuntimeError("conn refused")
        state = _node_store(_make_state(vectors=[{"text": "x"}]))
        assert state["status"] == "failed"

    @patch("apps.backend.services.import_workflow.bulk_upsert")
    def test_store_passes_doc_name_from_file_name(self, mock_upsert):
        """store 节点应将 file_name 作为 doc_name 传给 Milvus."""
        state = _node_store(_make_state(
            vectors=[{"text": "x", "dense_vector": [0.1], "sparse_vector": {1: 0.5}}],
            file_name="iPhone16.pdf",
        ))
        assert state["status"] == "done"
        args, _ = mock_upsert.call_args
        sent_vectors = args[0]
        assert sent_vectors[0]["doc_name"] == "iPhone16.pdf"


@pytest.mark.integration
class TestImportGraphEndToEnd:
    @patch("apps.backend.services.import_workflow.bulk_upsert")
    @patch("apps.backend.services.import_workflow.embed_chunks")
    @patch("apps.backend.services.import_workflow.chunk_by_section")
    @patch("apps.backend.services.import_workflow.build_recognizer")
    @patch("apps.backend.services.import_workflow.extract_markdown")
    def test_full_flow_done(
        self, mock_extract, mock_recognizer, mock_chunk, mock_embed, mock_upsert
    ):
        mock_extract.return_value = "# 手册\n\n## 章节\n\n" + "正文。" * 100
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content="MacBook Pro")
        mock_recognizer.return_value = mock_llm
        mock_chunk.return_value = [{"text": "[MacBook Pro] chap", "chunk_id": 0, "item_name": "MacBook Pro"}]
        mock_embed.return_value = [{"text": "x", "dense_vector": [0.1], "sparse_vector": {}}]
        graph = build_import_graph()
        init = _make_state()
        final = graph.invoke(init)
        assert final["status"] == "done"
        assert final["item_name"] == "MacBook Pro"
        assert final["error"] is None

    @patch("apps.backend.services.import_workflow.extract_markdown")
    def test_extract_failure_stops_flow(self, mock_extract):
        mock_extract.side_effect = RuntimeError("mineru down")
        graph = build_import_graph()
        final = graph.invoke(_make_state())
        assert final["status"] == "failed"
        assert "extract" in final["error"]
