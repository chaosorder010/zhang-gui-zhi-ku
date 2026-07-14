"""集成测试: /api/upload + /api/documents.

Seam: FastAPI router, mock import_workflow。
"""
from __future__ import annotations

from unittest.mock import patch
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
