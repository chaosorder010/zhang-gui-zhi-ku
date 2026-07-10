"""MinerU 云 API 客户端 (v4).

Spec (官方文档):
  POST {base_url}/file-urls/batch   → 申请上传链接
  PUT  <upload_url>                  → 上传文件 binary (无 Content-Type)
  GET  {base_url}/extract/result?task_id=  → 轮询

Doc: https://mineru.net/apiManage/docs
"""
from __future__ import annotations

import io
import time
import zipfile
from typing import Optional

import requests

# 轮询间隔/超时
POLL_INTERVAL_SEC = 5
POLL_TIMEOUT_SEC = 300  # 5 分钟


def _auth_headers(token: str) -> dict:
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }


def apply_upload_url(
    base_url: str,
    token: str,
    file_name: str,
    model_version: str = "vlm",
) -> tuple[str, list[dict]]:
    """申请文件上传链接.

    Returns:
        (task_id, file_urls) 其中 file_urls = [{data_id, url}, ...]
    """
    url = f"{base_url}/file-urls/batch"
    body = {
        "files": [{"name": file_name, "data_id": "f1"}],
        "model_version": model_version,
    }
    resp = requests.post(url, headers=_auth_headers(token), json=body, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"申请上传链接 HTTP 失败: {resp.status_code}")

    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"申请上传链接失败: {data.get('msg', '未知错误')}")

    task_id = data["data"]["task_id"]
    file_urls = data["data"]["file_urls"]
    return task_id, file_urls


def upload_file(upload_url: str, binary: bytes) -> None:
    """PUT 上传 binary, 无 Content-Type header."""
    resp = requests.put(upload_url, data=binary, timeout=120)
    if resp.status_code not in (200, 201, 204):
        raise RuntimeError(f"上传文件失败: HTTP {resp.status_code}")


def poll_result(
    base_url: str,
    token: str,
    task_id: str,
    interval: int = POLL_INTERVAL_SEC,
    timeout: int = POLL_TIMEOUT_SEC,
) -> dict:
    """轮询任务状态, 直到 done/failed/超时.

    Returns:
        成功的 extract_result dict, 含 state/full_zip_url/file_name
    Raises:
        RuntimeError: 失败 / 超时
    """
    url = f"{base_url}/extract/result"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        resp = requests.get(
            url,
            headers={"Authorization": f"Bearer {token}"},
            params={"task_id": task_id},
            timeout=30,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"轮询 HTTP 失败: {resp.status_code}")
        body = resp.json()
        if body.get("code") != 0:
            raise RuntimeError(f"轮询返回错误: {body.get('msg')}")

        result = body.get("data", {}).get("extract_result", {})
        state = result.get("state", "unknown")
        if state == "done":
            return result
        if state == "failed":
            err = result.get("err_msg", "未知")
            raise RuntimeError(f"解析失败: {err}")
        # 还在处理中, 等待
        time.sleep(interval)

    raise RuntimeError(f"轮询超时 ({timeout}s)")


def download_and_extract_markdown(zip_url: str) -> str:
    """下载 zip 并读取 full.md."""
    resp = requests.get(zip_url, timeout=120)
    if resp.status_code != 200:
        raise RuntimeError(f"下载 zip 失败: HTTP {resp.status_code}")

    buf = io.BytesIO(resp.content)
    with zipfile.ZipFile(buf) as zf:
        # 解压找 full.md
        for name in zf.namelist():
            if name.endswith("full.md"):
                with zf.open(name) as f:
                    return f.read().decode("utf-8")
    raise RuntimeError("zip 中未找到 full.md")


def extract_markdown(
    base_url: str,
    token: str,
    file_name: str,
    file_binary: bytes,
    model_version: str = "vlm",
) -> str:
    """完整提取流程: 申请→上传→轮询→下载→解压→返回 markdown."""
    task_id, file_urls = apply_upload_url(base_url, token, file_name, model_version)
    for fu in file_urls:
        upload_file(fu["url"], file_binary)
    result = poll_result(base_url, token, task_id)
    zip_url = result.get("full_zip_url")
    if not zip_url:
        raise RuntimeError("解析结果无 zip url")
    return download_and_extract_markdown(zip_url)
