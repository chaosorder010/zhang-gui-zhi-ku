"""集成测试: LangGraph 导入工作流.

Seam: import_workflow 编排。mock 所有外部服务 (MinerU / LLM / Milvus)。
"""
from __future__ import annotations

from unittest.mock import patch, MagicMock
import pytest

from apps.backend.services.import_workflow import (
    build_import_graph,
    create_initial_import_state,
    ImportState,
    _fail_fast_edge,
    _node_extract,
    _node_recognize,
    _node_chunk,
    _node_embed,
    _node_store,
    node_handler,
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


@pytest.mark.integration
class TestImportGraphFailFast:
    """条件边 fail-fast: 任一节点失败 → 后续节点不被执行, 直接 END.

    通过 assert_not_called 验证 fail-fast 行为 — 这是 P1 的核心契约:
    失败时节点的下游不应被访问(而非静默空转)。
    """

    @patch("apps.backend.services.import_workflow.bulk_upsert")
    @patch("apps.backend.services.import_workflow.embed_chunks")
    @patch("apps.backend.services.import_workflow.chunk_by_section")
    @patch("apps.backend.services.import_workflow.recognize_item")
    @patch("apps.backend.services.import_workflow.extract_markdown")
    def test_extract_failure_skips_all_downstream(
        self, mock_extract, mock_recognize, mock_chunk, mock_embed, mock_upsert,
    ):
        """extract 失败 → recognize/chunk/embed/store 均不被调用."""
        mock_extract.side_effect = RuntimeError("mineru down")
        graph = build_import_graph()
        final = graph.invoke(_make_state())
        assert final["status"] == "failed"
        assert "extract" in final["error"]
        mock_recognize.assert_not_called()
        mock_chunk.assert_not_called()
        mock_embed.assert_not_called()
        mock_upsert.assert_not_called()

    @patch("apps.backend.services.import_workflow.bulk_upsert")
    @patch("apps.backend.services.import_workflow.embed_chunks")
    @patch("apps.backend.services.import_workflow.chunk_by_section")
    @patch("apps.backend.services.import_workflow.recognize_item")
    @patch("apps.backend.services.import_workflow.extract_markdown")
    def test_recognize_failure_skips_downstream(
        self, mock_extract, mock_recognize, mock_chunk, mock_embed, mock_upsert,
    ):
        """recognize 失败 → chunk/embed/store 均不被调用."""
        mock_extract.return_value = "# 手册\n\n## 章节\n\n正文内容"
        mock_recognize.side_effect = RuntimeError("llm api 500")
        graph = build_import_graph()
        final = graph.invoke(_make_state())
        assert final["status"] == "failed"
        assert "recognize" in final["error"]
        mock_chunk.assert_not_called()
        mock_embed.assert_not_called()
        mock_upsert.assert_not_called()

    @patch("apps.backend.services.import_workflow.bulk_upsert")
    @patch("apps.backend.services.import_workflow.embed_chunks")
    @patch("apps.backend.services.import_workflow.chunk_by_section")
    @patch("apps.backend.services.import_workflow.recognize_item")
    @patch("apps.backend.services.import_workflow.extract_markdown")
    def test_chunk_failure_skips_downstream(
        self, mock_extract, mock_recognize, mock_chunk, mock_embed, mock_upsert,
    ):
        """chunk 失败 → embed/store 均不被调用."""
        mock_extract.return_value = "# 手册\n\n## 章节\n\n正文内容"
        mock_recognize.return_value = "iPhone16"
        mock_chunk.side_effect = RuntimeError("chunker bug")
        graph = build_import_graph()
        final = graph.invoke(_make_state())
        assert final["status"] == "failed"
        assert "chunk" in final["error"]
        mock_embed.assert_not_called()
        mock_upsert.assert_not_called()

    @patch("apps.backend.services.import_workflow.bulk_upsert")
    @patch("apps.backend.services.import_workflow.embed_chunks")
    @patch("apps.backend.services.import_workflow.chunk_by_section")
    @patch("apps.backend.services.import_workflow.recognize_item")
    @patch("apps.backend.services.import_workflow.extract_markdown")
    def test_embed_failure_skips_store(
        self, mock_extract, mock_recognize, mock_chunk, mock_embed, mock_upsert,
    ):
        """embed 失败 → store 不被调用."""
        mock_extract.return_value = "# 手册\n\n## 章节\n\n正文内容"
        mock_recognize.return_value = "iPhone16"
        mock_chunk.return_value = [{"text": "x", "chunk_id": 0, "item_name": "iPhone16"}]
        mock_embed.side_effect = RuntimeError("gpu oom")
        graph = build_import_graph()
        final = graph.invoke(_make_state())
        assert final["status"] == "failed"
        assert "embed" in final["error"]
        mock_upsert.assert_not_called()

    @patch("apps.backend.services.import_workflow.bulk_upsert")
    @patch("apps.backend.services.import_workflow.embed_chunks")
    @patch("apps.backend.services.import_workflow.chunk_by_section")
    @patch("apps.backend.services.import_workflow.recognize_item")
    @patch("apps.backend.services.import_workflow.extract_markdown")
    def test_store_failure_marks_failed(
        self, mock_extract, mock_recognize, mock_chunk, mock_embed, mock_upsert,
    ):
        """store 失败 → status=failed, error 含 store."""
        mock_extract.return_value = "# 手册\n\n## 章节\n\n正文内容"
        mock_recognize.return_value = "iPhone16"
        mock_chunk.return_value = [{"text": "x", "chunk_id": 0, "item_name": "iPhone16"}]
        mock_embed.return_value = [
            {"text": "x", "chunk_id": 0, "item_name": "iPhone16",
             "dense_vector": [0.1], "sparse_vector": {1: 0.5}}
        ]
        mock_upsert.side_effect = RuntimeError("milvus conn refused")
        graph = build_import_graph()
        final = graph.invoke(_make_state())
        assert final["status"] == "failed"
        assert "store" in final["error"]


@pytest.mark.integration
class TestFailFastEdge:
    """_fail_fast_edge: 条件边路由的直接契约测试."""

    def test_routes_to_next_when_not_failed(self):
        """status != failed → 路由到 next_node."""
        from langgraph.graph import END
        router = _fail_fast_edge("next_node")
        assert router(_make_state(status="uploaded")) == "next_node"
        assert router(_make_state(status="extracting")) == "next_node"

    def test_routes_to_end_when_failed(self):
        """status == failed → 路由到 END (短路)."""
        from langgraph.graph import END
        router = _fail_fast_edge("next_node")
        state = _make_state()
        state["status"] = "failed"
        state["error"] = "something broke"
        assert router(state) == END

    def test_returns_callable_per_next_node(self):
        """不同 next_node 参数产生独立的路由函数."""
        router_a = _fail_fast_edge("node_a")
        router_b = _fail_fast_edge("node_b")
        assert router_a(_make_state(status="done")) == "node_a"
        assert router_b(_make_state(status="done")) == "node_b"


@pytest.mark.integration
class TestNodeHandlerContract:
    """@node_handler 装饰器的隔离契约测试."""

    def test_decorator_sets_success_status(self):
        """被装饰函数正常返回时, 装饰器写入 on_success_status."""
        @node_handler(on_success_status="custom_done", error_prefix="test")
        def my_node(state: ImportState) -> dict:
            return {"item_name": "Gadget"}

        result = my_node(_make_state())
        assert result["status"] == "custom_done"
        assert result["item_name"] == "Gadget"

    def test_decorator_catches_exception_and_fails(self):
        """被装饰函数抛出异常时, 装饰器捕获并设置 failed."""
        @node_handler(on_success_status="done", error_prefix="step")
        def my_node(state: ImportState) -> dict:
            raise RuntimeError("boom")

        result = my_node(_make_state())
        assert result["status"] == "failed"
        assert "step" in result["error"]
        assert "boom" in result["error"]

    def test_decorator_skips_on_prior_failure(self):
        """上游已失败 → 被装饰函数不被执行, 直接透传."""
        calls = []

        @node_handler(on_success_status="done", error_prefix="step")
        def my_node(state: ImportState) -> dict:
            calls.append(1)
            return {"item_name": "X"}

        prior_failed = _make_state()
        prior_failed["status"] = "failed"
        prior_failed["error"] = "upstream error"
        result = my_node(prior_failed)
        assert len(calls) == 0
        assert result["status"] == "failed"
        assert result["error"] == "upstream error"

    def test_decorator_handles_none_return(self):
        """被装饰函数返回 None 时, 装饰器应正常处理."""
        @node_handler(on_success_status="done", error_prefix="step")
        def my_node(state: ImportState) -> dict | None:
            return None

        result = my_node(_make_state())
        assert result["status"] == "done"

    def test_preserves_existing_state_fields(self):
        """装饰器应保留 state 中未被覆盖的字段."""
        @node_handler(on_success_status="done", error_prefix="step")
        def my_node(state: ImportState) -> dict:
            return {"markdown": "# new"}

        result = my_node(_make_state(file_name="keep.pdf", task_id="t-99"))
        assert result["file_name"] == "keep.pdf"
        assert result["task_id"] == "t-99"
        assert result["markdown"] == "# new"
        assert result["status"] == "done"


@pytest.mark.integration
class TestCreateInitialImportState:
    """create_initial_import_state 工厂函数契约."""

    def test_produces_uploaded_status(self):
        state = create_initial_import_state(
            task_id="t-1",
            file_name="a.pdf",
            file_binary=b"bin",
            mineru_base_url="https://mu",
            mineru_token="tok",
            openai_api_key="k",
            openai_base_url="https://api",
            openai_model="gpt-4o-mini",
        )
        assert state["status"] == "uploaded"
        assert state["task_id"] == "t-1"
        assert state["file_name"] == "a.pdf"
        assert state["file_binary"] == b"bin"
        assert state["item_name"] is None
        assert state["markdown"] == ""
        assert state["chunks"] == []
        assert state["vectors"] == []
        assert state["error"] is None

    def test_passes_through_external_service_config(self):
        state = create_initial_import_state(
            task_id="t",
            file_name="f.pdf",
            file_binary=b"",
            mineru_base_url="https://custom.mu",
            mineru_token="secret-tok",
            openai_api_key="real-key",
            openai_base_url="https://v1.custom",
            openai_model="gpt-4",
        )
        assert state["mineru_base_url"] == "https://custom.mu"
        assert state["mineru_token"] == "secret-tok"
        assert state["openai_api_key"] == "real-key"
        assert state["openai_base_url"] == "https://v1.custom"
        assert state["openai_model"] == "gpt-4"
