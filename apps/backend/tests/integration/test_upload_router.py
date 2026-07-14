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
            files={"file": ("test.pdf", b"%PDF-1.4 fake", "application/pdf")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "task_id" in data
        assert data["file_name"] == "test.pdf"
        mock_trigger_sync.assert_called_once()

    def test_upload_rejects_non_pdf(self):
        resp = _client().post(
            "/api/upload",
            files={"file": ("test.txt", b"hello", "text/plain")},
        )
        assert resp.status_code == 400

    def test_upload_requires_file(self):
        resp = _client().post("/api/upload")
        assert resp.status_code in (400, 422)


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
