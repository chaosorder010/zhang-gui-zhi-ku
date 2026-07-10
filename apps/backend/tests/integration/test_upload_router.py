"""集成测试: /api/upload + /api/documents.

Seam: FastAPI router, mock import_workflow。
"""
from __future__ import annotations

from unittest.mock import patch, AsyncMock
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
    @patch("apps.backend.routers.upload.trigger_import", new_callable=AsyncMock)
    def test_upload_pdf_returns_task_id(self, mock_trigger):
        mock_trigger.return_value = None
        resp = _client().post(
            "/api/upload",
            files={"file": ("test.pdf", b"%PDF-1.4 fake", "application/pdf")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "task_id" in data
        assert data["file_name"] == "test.pdf"
        mock_trigger.assert_called_once()

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
