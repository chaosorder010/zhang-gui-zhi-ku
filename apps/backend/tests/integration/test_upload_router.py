"""集成测试: /api/upload + /api/documents.

Seam: FastAPI router, mock import_workflow。
"""
from __future__ import annotations

from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient

from apps.backend.main import create_app
from apps.backend.core.config import Settings


def _client():
    import os
    os.environ["OPENAI_API_KEY"] = "k"
    os.environ["OPENAI_BASE_URL"] = "https://x"
    os.environ["MINERU_API_KEY"] = "mtok"
    os.environ["MINERU_BASE_URL"] = "https://mineru.net/api/v4"
    return TestClient(create_app())


@pytest.mark.integration
class TestUploadRouter:
    @patch("apps.backend.routers.upload.trigger_import_sync")
    def test_upload_pdf_returns_task_id(self, mock_trigger_sync):
        resp = _client().post(
            "/api/upload",
            files={"files": ("test.pdf", b"%PDF-1.4 fake", "application/pdf")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "batch_id" in data
        assert data["count"] == 1
        assert data["tasks"][0]["file_name"] == "test.pdf"
        assert data["tasks"][0]["status"] == "uploaded"
        mock_trigger_sync.assert_called_once()

    def test_upload_rejects_non_pdf(self):
        resp = _client().post(
            "/api/upload",
            files={"files": ("test.txt", b"hello", "text/plain")},
        )
        assert resp.status_code == 400

    def test_upload_requires_file(self):
        resp = _client().post("/api/upload")
        assert resp.status_code == 422


@pytest.mark.integration
class TestBatchUpload:
    """T02: POST /api/upload 多文件支持 (fail-fast + 独立 task_id)."""

    @patch("apps.backend.routers.upload.trigger_import_sync")
    def test_batch_returns_n_independent_task_ids(self, mock_trigger):
        """3 文件 → count=3, 3 个唯一 task_id, trigger 调 3 次."""
        import uuid as _uuid
        client = _client()
        files = [
            ("files", ("a.pdf", b"%PDF-1.4 a", "application/pdf")),
            ("files", ("b.pdf", b"%PDF-1.4 b", "application/pdf")),
            ("files", ("c.md", b"# hello", "text/markdown")),
        ]
        resp = client.post("/api/upload", files=files)
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 3
        # batch_id 合法 UUID
        _uuid.UUID(data["batch_id"])
        # 3 个独立 task_id
        task_ids = [t["task_id"] for t in data["tasks"]]
        assert len(set(task_ids)) == 3
        # 每 task 含 file_name + status
        names = [t["file_name"] for t in data["tasks"]]
        assert names == ["a.pdf", "b.pdf", "c.md"]
        assert all(t["status"] == "uploaded" for t in data["tasks"])
        assert mock_trigger.call_count == 3

    @patch("apps.backend.routers.upload.trigger_import_sync")
    def test_single_file_compat(self, mock_trigger):
        """单文件仍兼容 → count=1, 结构同 batch."""
        resp = _client().post(
            "/api/upload",
            files={"files": ("solo.pdf", b"%PDF-1.4", "application/pdf")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert len(data["tasks"]) == 1
        assert data["tasks"][0]["file_name"] == "solo.pdf"
        mock_trigger.assert_called_once()

    def test_batch_rejects_invalid_suffix_fail_fast(self):
        """任一后缀非法 → 整批 400, trigger 0 次."""
        with patch("apps.backend.routers.upload.trigger_import_sync") as mock_trigger:
            resp = _client().post(
                "/api/upload",
                files=[
                    ("files", ("ok1.pdf", b"%PDF-1.4", "application/pdf")),
                    ("files", ("bad.txt", b"hello", "text/plain")),
                    ("files", ("ok2.pdf", b"%PDF-1.4", "application/pdf")),
                ],
            )
            assert resp.status_code == 400
            mock_trigger.assert_not_called()

    def test_batch_rejects_empty_file_fail_fast(self):
        """含空文件 → 整批 400."""
        with patch("apps.backend.routers.upload.trigger_import_sync") as mock_trigger:
            resp = _client().post(
                "/api/upload",
                files=[
                    ("files", ("ok.pdf", b"%PDF-1.4", "application/pdf")),
                    ("files", ("empty.pdf", b"", "application/pdf")),
                ],
            )
            assert resp.status_code == 400
            mock_trigger.assert_not_called()

    @patch("apps.backend.routers.upload.trigger_import_sync")
    def test_batch_each_file_triggers_independently(self, mock_trigger):
        """每文件独立调 trigger_import_sync + 注册到 _task_status."""
        import apps.backend.routers.upload as upload_mod
        resp = _client().post(
            "/api/upload",
            files=[
                ("files", ("x.pdf", b"%PDF-1.4 x", "application/pdf")),
                ("files", ("y.md", b"# y", "text/markdown")),
            ],
        )
        assert resp.status_code == 200
        data = resp.json()
        # 两 task 都注册到 _task_status
        for t in data["tasks"]:
            assert t["task_id"] in upload_mod._task_status
            assert upload_mod._task_status[t["task_id"]]["status"] == "uploaded"
        assert mock_trigger.call_count == 2

    def test_batch_fail_fast_before_read(self):
        """后缀校验在 read 前 → 非法文件还没被读取即整批拒."""
        # 用含非法后缀的 batch 验证 400, 无论文件顺序
        resp = _client().post(
            "/api/upload",
            files=[
                ("files", ("first.txt", b"text", "text/plain")),
                ("files", ("second.pdf", b"%PDF-1.4", "application/pdf")),
            ],
        )
        assert resp.status_code == 400


@pytest.mark.integration
class TestListDocuments:
    @patch("apps.backend.routers.upload.list_documents", return_value=[])
    def test_list_returns_array(self, mock_list):
        resp = _client().get("/api/documents")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


@pytest.mark.integration
class TestTaskStatusTTL:
    """_task_status TTL 惰性清理: 过期条目在读取时被移除."""

    def test_entry_expires_after_ttl(self, monkeypatch):
        import apps.backend.routers.upload as upload_mod
        import time as _time

        ttl = 1  # 1 秒 TTL
        monkeypatch.setattr(upload_mod, "_TTL_SECONDS", ttl)
        old_status = upload_mod._task_status
        upload_mod._task_status = {
            "aging": {"task_id": "aging", "status": "done", "ts": _time.time()},
        }
        try:
            client = _client()
            # TTL 内应存在
            resp = client.get("/api/upload/aging")
            assert resp.status_code == 200
            assert resp.json()["task_id"] == "aging"
            # 等 TTL 过期后再读 → 应被清理
            _time.sleep(ttl + 0.1)
            resp2 = client.get("/api/upload/aging")
            assert resp2.status_code == 404
            assert "aging" not in upload_mod._task_status
        finally:
            upload_mod._task_status = old_status


@pytest.mark.integration
class TestTriggerImportSync:
    """trigger_import_sync 的异常路径: graph.invoke 抛出异常."""

    def test_graph_invoke_exception_marks_failed(self):
        """graph.invoke 抛异常 → 任务状态标记为 failed."""
        import apps.backend.routers.upload as upload_mod
        from apps.backend.services.import_workflow import create_initial_import_state

        state = create_initial_import_state(
            task_id="crash-1",
            file_name="boom.pdf",
            file_binary=b"bin",
            mineru_base_url="https://mu",
            mineru_token="tok",
            openai_api_key="k",
            openai_base_url="https://api",
            openai_model="gpt-4o-mini",
        )
        upload_mod._task_status.pop("crash-1", None)

        with patch.object(upload_mod, "build_import_graph") as mock_builder:
            mock_graph = MagicMock()
            mock_graph.invoke.side_effect = RuntimeError("graph exploded")
            mock_builder.return_value = mock_graph
            upload_mod.trigger_import_sync(state)

        stored = upload_mod._task_status.get("crash-1")
        assert stored is not None
        assert stored["status"] == "failed"
        assert "graph exploded" in stored["error"]
        # cleanup
        upload_mod._task_status.pop("crash-1", None)

    def test_graph_invoke_success_stores_result(self):
        """graph.invoke 成功 → 任务状态存储 final status."""
        import apps.backend.routers.upload as upload_mod
        from apps.backend.services.import_workflow import create_initial_import_state

        state = create_initial_import_state(
            task_id="ok-1",
            file_name="ok.pdf",
            file_binary=b"bin",
            mineru_base_url="https://mu",
            mineru_token="tok",
            openai_api_key="k",
            openai_base_url="https://api",
            openai_model="gpt-4o-mini",
        )
        upload_mod._task_status.pop("ok-1", None)

        with patch.object(upload_mod, "build_import_graph") as mock_builder:
            mock_graph = MagicMock()
            mock_graph.invoke.return_value = {
                "status": "done",
                "item_name": "iPhone16",
                "error": None,
            }
            mock_builder.return_value = mock_graph
            upload_mod.trigger_import_sync(state)

        stored = upload_mod._task_status.get("ok-1")
        assert stored is not None
        assert stored["status"] == "done"
        assert stored["item_name"] == "iPhone16"
        # cleanup
        upload_mod._task_status.pop("ok-1", None)


@pytest.mark.integration
class TestCleanupExpired:
    """_cleanup_expired 的边界行为."""

    def test_removes_only_expired_entries(self, monkeypatch):
        import apps.backend.routers.upload as upload_mod
        import time as _time

        monkeypatch.setattr(upload_mod, "_TTL_SECONDS", 1)
        old_status = upload_mod._task_status
        now = _time.time()
        upload_mod._task_status = {
            "fresh": {"task_id": "fresh", "status": "done", "ts": now},
            "stale": {"task_id": "stale", "status": "done", "ts": now - 100},
        }
        try:
            upload_mod._cleanup_expired()
            assert "fresh" in upload_mod._task_status
            assert "stale" not in upload_mod._task_status
        finally:
            upload_mod._task_status = old_status

    def test_empty_status_no_error(self):
        import apps.backend.routers.upload as upload_mod

        old_status = upload_mod._task_status
        upload_mod._task_status = {}
        try:
            upload_mod._cleanup_expired()  # should not raise
        finally:
            upload_mod._task_status = old_status


@pytest.mark.integration
class TestDeleteDocument:
    """DELETE /api/documents/{doc_name} 集成测试."""

    @patch("apps.backend.routers.upload.delete_by_doc_name")
    def test_delete_returns_deleted_chunks(self, mock_delete):
        """删除成功应返回 deleted_chunks = mock 返回值."""
        mock_delete.return_value = 42
        client = _client()

        resp = client.delete("/api/documents/test.pdf")

        assert resp.status_code == 200
        data = resp.json()
        assert data["doc_name"] == "test.pdf"
        assert data["deleted_chunks"] == 42
        assert data["status"] == "deleted"
        mock_delete.assert_called_once_with("test.pdf")

    @patch("apps.backend.routers.upload.delete_by_doc_name")
    def test_delete_cleans_task_status(self, mock_delete):
        """删除后应清理 _task_status 中 file_name == doc_name 的条目."""
        import apps.backend.routers.upload as upload_mod

        mock_delete.return_value = 5
        old_status = upload_mod._task_status
        upload_mod._task_status = {
            "t1": {"task_id": "t1", "file_name": "test.pdf", "status": "done", "ts": 9999999999},
            "t2": {"task_id": "t2", "file_name": "other.pdf", "status": "done", "ts": 9999999999},
        }
        try:
            client = _client()
            resp = client.delete("/api/documents/test.pdf")

            assert resp.status_code == 200
            # t1 应被移除,t2 保留
            assert "t1" not in upload_mod._task_status
            assert "t2" in upload_mod._task_status
        finally:
            upload_mod._task_status = old_status

    @patch("apps.backend.routers.upload.delete_by_doc_name")
    def test_delete_nonexistent_returns_not_found(self, mock_delete):
        """不存在的文档应返回 deleted_chunks=0, status=not_found, HTTP 200."""
        mock_delete.return_value = 0
        client = _client()

        resp = client.delete("/api/documents/nonexistent.pdf")

        assert resp.status_code == 200
        data = resp.json()
        assert data["doc_name"] == "nonexistent.pdf"
        assert data["deleted_chunks"] == 0
        assert data["status"] == "not_found"

    @patch("apps.backend.routers.upload.delete_by_doc_name")
    def test_delete_chinese_doc_name(self, mock_delete):
        """中文 doc_name 应正确传递给 Milvus client."""
        mock_delete.return_value = 3
        client = _client()

        doc_name = "苹果维修手册.pdf"
        import urllib.parse
        encoded = urllib.parse.quote(doc_name)
        resp = client.delete(f"/api/documents/{encoded}")

        assert resp.status_code == 200
        data = resp.json()
        # FastAPI decode URL path param
        mock_delete.assert_called_once_with(doc_name)
        assert data["doc_name"] == doc_name
        assert data["deleted_chunks"] == 3
        assert data["status"] == "deleted"
