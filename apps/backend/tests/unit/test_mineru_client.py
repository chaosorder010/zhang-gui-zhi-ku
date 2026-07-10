"""单元测试: MinerU API 客户端.

Seam: mineru_client, mock requests (外部 HTTP 边界)。
Spec (从官方文档提取):
  POST /api/v4/file-urls/batch   → 申请上传 URL
  PUT <upload_url>               → 上传 binary (无 Content-Type)
  GET  /api/v4/extract/result?task_id=  → 轮询 (state: waiting-file/pending/running/done/failed)
"""
from __future__ import annotations

from unittest.mock import patch, MagicMock, Mock
import pytest
from apps.backend.services import mineru_client as mc


def _mock_response(status: int = 200, json_data: dict | None = None, content: bytes = b""):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = json_data or {}
    resp.content = content
    resp.text = content.decode("utf-8", errors="replace")
    return resp


@pytest.mark.unit
class TestApplyUploadUrl:
    @patch("apps.backend.services.mineru_client.requests.post")
    def test_returns_upload_url_and_task_id(self, mock_post):
        mock_post.return_value = _mock_response(200, {
            "code": 0,
            "data": {
                "task_id": "abc-123",
                "file_urls": [{"data_id": "f1", "url": "https://upload.x/1"}],
            },
        })
        task_id, urls = mc.apply_upload_url("https://mineru.net/api/v4/file-urls/batch", "tok", "manual.pdf")
        assert task_id == "abc-123"
        assert urls == [{"data_id": "f1", "url": "https://upload.x/1"}]
        # 验证请求 body
        call_kwargs = mock_post.call_args[1]
        assert call_kwargs["headers"]["Authorization"] == "Bearer tok"
        body = call_kwargs["json"]
        assert body["files"][0]["name"] == "manual.pdf"

    @patch("apps.backend.services.mineru_client.requests.post")
    def test_raises_on_error_code(self, mock_post):
        mock_post.return_value = _mock_response(200, {"code": -1, "msg": "bad"})
        with pytest.raises(RuntimeError, match="申请上传链接失败"):
            mc.apply_upload_url("url", "tok", "f.pdf")


@pytest.mark.unit
class TestUploadFile:
    @patch("apps.backend.services.mineru_client.requests.put")
    def test_puts_binary_without_content_type(self, mock_put):
        mock_put.return_value = _mock_response(200)
        mc.upload_file("https://upload.x/1", b"binary data")
        call_kwargs = mock_put.call_args[1]
        assert call_kwargs["data"] == b"binary data"
        # 无 Content-Type header
        assert "Content-Type" not in call_kwargs.get("headers", {})

    @patch("apps.backend.services.mineru_client.requests.put")
    def test_raises_on_non_200(self, mock_put):
        mock_put.return_value = _mock_response(403)
        with pytest.raises(RuntimeError, match="上传文件失败"):
            mc.upload_file("url", b"data")


@pytest.mark.unit
class TestPollResult:
    @patch("apps.backend.services.mineru_client.requests.get")
    def test_done_returns_zip_url(self, mock_get):
        mock_get.return_value = _mock_response(200, {
            "code": 0,
            "data": {
                "task_id": "t1",
                "extract_result": {
                    "state": "done",
                    "file_name": "m.pdf",
                    "full_zip_url": "https://cdn.x/m.zip",
                },
            },
        })
        result = mc.poll_result("https://mineru.net/api/v4/extract/result", "tok", "t1")
        assert result["state"] == "done"
        assert result["full_zip_url"] == "https://cdn.x/m.zip"

    @patch("apps.backend.services.mineru_client.requests.get")
    def test_running_keeps_polling(self, mock_get):
        """state=running 时应继续轮询; 为快速测试, 覆盖 interval/timeout."""
        mock_get.return_value = _mock_response(200, {
            "code": 0,
            "data": {
                "task_id": "t1",
                "extract_result": {"state": "running", "file_name": "m.pdf"},
            },
        })
        with pytest.raises(RuntimeError, match="轮询超时"):
            mc.poll_result("https://mineru.net/api/v4/extract/result", "tok", "t1",
                           interval=0, timeout=1)
        # 验证轮询了多次
        assert mock_get.call_count >= 1

    @patch("apps.backend.services.mineru_client.requests.get")
    def test_failed_raises(self, mock_get):
        mock_get.return_value = _mock_response(200, {
            "code": 0,
            "data": {
                "task_id": "t1",
                "extract_result": {
                    "state": "failed",
                    "err_msg": "page count exceeds limit",
                },
            },
        })
        with pytest.raises(RuntimeError, match="解析失败"):
            mc.poll_result("https://mineru.net/api/v4/extract/result", "tok", "t1")


@pytest.mark.unit
class TestDownloadAndExtractMarkdown:
    @patch("apps.backend.services.mineru_client.requests.get")
    def test_extracts_full_md_from_zip(self, mock_get):
        import zipfile, io
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("full.md", "# 标题\n\n解析结果\n")
        mock_get.return_value = _mock_response(200, content=buf.getvalue())
        md = mc.download_and_extract_markdown("https://cdn.x/m.zip")
        assert md == "# 标题\n\n解析结果\n"

    @patch("apps.backend.services.mineru_client.requests.get")
    def test_missing_full_md_raises(self, mock_get):
        import zipfile, io
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("other.txt", "内容")
        mock_get.return_value = _mock_response(200, content=buf.getvalue())
        with pytest.raises(RuntimeError, match="full.md"):
            mc.download_and_extract_markdown("https://cdn.x/m.zip")


@pytest.mark.unit
class TestEndToEndExtract:
    @patch("apps.backend.services.mineru_client.download_and_extract_markdown")
    @patch("apps.backend.services.mineru_client.poll_result")
    @patch("apps.backend.services.mineru_client.upload_file")
    @patch("apps.backend.services.mineru_client.apply_upload_url")
    def test_full_flow(self, mock_apply, mock_upload, mock_poll, mock_download):
        mock_apply.return_value = ("task-1", [{"data_id": "f1", "url": "https://up/1"}])
        mock_poll.return_value = {
            "state": "done",
            "full_zip_url": "https://cdn.zip",
            "file_name": "m.pdf",
        }
        mock_download.return_value = "# MD内容"
        md = mc.extract_markdown(
            base_url="https://mineru.net/api/v4",
            token="tok",
            file_name="m.pdf",
            file_binary=b"binary",
        )
        assert md == "# MD内容"
        mock_apply.assert_called_once()
        mock_upload.assert_called_once_with("https://up/1", b"binary")
        assert mock_poll.call_count >= 1
        mock_download.assert_called_once_with("https://cdn.zip")
