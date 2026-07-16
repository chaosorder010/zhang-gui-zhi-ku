#!/usr/bin/env python3
"""E2E 集成测试 — 全栈真实容器。

启动 docker-compose (frontend + backend + Milvus),跑 P0 场景,输出报告 + 退出码。
脚本管全生命周期 (up -d → wait healthy → test → down -v)。

退出码: 0 = 全通过, 1 = 有失败。
"""
from __future__ import annotations

import os
import sys
import time
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import httpx

# --- 配置 ---
COMPOSE_DIR = Path(__file__).resolve().parent.parent
BASE_URL = "http://localhost:5200"
HTTP_TIMEOUT = 60.0          # 单个请求超时 (ask 链 LL M,留足余量)
HEALTH_RETRY_SECONDS = 180.0 # 等 backend healthy 的总预算
HEALTH_INTERVAL = 3.0


# --- 数据结构 ---
@dataclass
class Scenario:
    name: str
    passed: bool = False
    detail: str = ""
    duration_s: float = 0.0


@dataclass
class Report:
    scenarios: list[Scenario] = field(default_factory=list)

    def add(self, name: str, passed: bool, detail: str = "", duration: float = 0.0):
        self.scenarios.append(Scenario(name, passed, detail, duration))

    @property
    def passed_count(self) -> int:
        return sum(1 for s in self.scenarios if s.passed)

    @property
    def failed_count(self) -> int:
        return sum(1 for s in self.scenarios if not s.passed)

    def print_summary(self):
        print("\n" + "=" * 60)
        print("E2E 集成测试报告")
        print("=" * 60)
        for s in self.scenarios:
            status = "PASS" if s.passed else "FAIL"
            line = f"  [{status}] {s.name}  ({s.duration_s:.1f}s)"
            print(line)
            if s.detail:
                print(f"         {s.detail}")
        print("-" * 60)
        print(f"  Total: {len(self.scenarios)} | Pass: {self.passed_count} | Fail: {self.failed_count}")
        print("=" * 60)


# --- docker 生命周期 ---
def compose(*args: str) -> subprocess.CompletedProcess:
    """在 COMPOSE_DIR 执行 docker compose ..."""
    cmd = ["docker", "compose", *args]
    return subprocess.run(
        cmd,
        cwd=str(COMPOSE_DIR),
        capture_output=True,
        text=True,
    )


def up():
    print("[e2e] docker compose up -d (no build, use local images) ...")
    r = compose("up", "-d")
    if r.returncode != 0:
        raise RuntimeError(f"docker compose up failed:\n{r.stderr}")


def down():
    print("[e2e] docker compose down -v ...")
    r = compose("down", "-v")
    if r.returncode != 0:
        print(f"[e2e] WARNING: docker compose down failed:\n{r.stderr}", file=sys.stderr)


def wait_healthy(client: httpx.Client):
    """轮询 backend /api/documents,直到 200 或超时。"""
    url = f"{BASE_URL}/api/documents"
    deadline = time.time() + HEALTH_RETRY_SECONDS
    last_err = ""
    while time.time() < deadline:
        try:
            r = client.get(url, timeout=5.0)
            if r.status_code == 200:
                print(f"[e2e] backend healthy ({url})")
                return
            last_err = f"status={r.status_code}"
        except httpx.TransportError as e:
            last_err = str(e)
        time.sleep(HEALTH_INTERVAL)
    raise TimeoutError(
        f"backend not healthy after {HEALTH_RETRY_SECONDS}s (last: {last_err})"
    )


# --- 场景 ---
class Runner:
    def __init__(self):
        self.report = Report()
        self._client = httpx.Client(base_url=BASE_URL, timeout=HTTP_TIMEOUT)

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()

    def _run(self, name: str, fn):
        start = time.time()
        try:
            fn()
            dur = time.time() - start
            self.report.add(name, True, duration=dur)
            print(f"  [PASS] {name}  ({dur:.1f}s)")
        except Exception as e:
            dur = time.time() - start
            self.report.add(name, False, detail=str(e), duration=dur)
            print(f"  [FAIL] {name}  ({dur:.1f}s) -> {e}")

    # --- frontend ---
    def frontend_index(self):
        r = self._client.get("/")
        assert r.status_code == 200, f"status={r.status_code}"
        assert "掌柜智库" in r.text, "title not found in HTML"

    def frontend_style_css(self):
        r = self._client.get("/style.css")
        assert r.status_code == 200, f"status={r.status_code}"
        assert "body" in r.text or "{" in r.text, "not CSS"

    def frontend_main_js(self):
        r = self._client.get("/main.js")
        assert r.status_code == 200, f"status={r.status_code}"
        assert "/api/ask" in r.text, "main.js missing /api/ask call"

    def frontend_progress_js(self):
        r = self._client.get("/progress.js")
        assert r.status_code == 200, f"status={r.status_code}"
        assert "mapStatusToProgress" in r.text, "progress.js missing mapStatusToProgress"

    # --- upload 失败路径 ---
    def upload_wrong_format_rejected(self):
        """非白名单后缀 (.txt) → 400。"""
        f = tempfile.NamedTemporaryFile(suffix=".txt", delete=False)
        f.write(b"hello")
        f.close()
        try:
            with open(f.name, "rb") as fp:
                # FastAPI list[UploadFile] 需要 list of tuples
                r = self._client.post("/api/upload", files=[("files", ("note.txt", fp))])
            assert r.status_code == 400, f"status={r.status_code}"
            assert "仅支持" in r.text or "detail" in r.text, f"error body: {r.text[:200]}"
        finally:
            os.unlink(f.name)

    def upload_mineru_not_configured(self):
        """MinerU 未配置时 → 400 (fail-fast 护栏)。"""
        f = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        f.write(b"%PDF-1.4 fake")
        f.close()
        try:
            with open(f.name, "rb") as fp:
                r = self._client.post("/api/upload", files=[("files", ("x.pdf", fp))])
            assert r.status_code == 400, f"status={r.status_code}"
            assert "MinerU" in r.text or "MINERU" in r.text.upper(), f"error body: {r.text[:200]}"
        finally:
            os.unlink(f.name)

    # --- documents ---
    def documents_list_is_array(self):
        r = self._client.get("/api/documents")
        assert r.status_code == 200, f"status={r.status_code}"
        import json
        data = json.loads(r.text)
        assert isinstance(data, list), f"expected list, got {type(data).__name__}"

    def documents_delete_nonexistent(self):
        r = self._client.delete("/api/documents/__nonexistent__")
        assert r.status_code == 200, f"status={r.status_code}"
        import json
        body = json.loads(r.text)
        assert body.get("status") in ("not_found", "deleted"), f"body={body}"

    # --- ask ---
    def ask_returns_answer(self):
        """单问 — 结构断言: 200 + answer 非空 + 长度 > 10。"""
        import json
        r = self._client.post("/api/ask", json={
            "question": "这个知识库支持哪些产品",
            "session_id": "e2e-test-single",
        })
        assert r.status_code == 200, f"status={r.status_code}"
        body = json.loads(r.text)
        ans = body.get("answer", "")
        assert isinstance(ans, str) and len(ans.strip()) > 10, f"answer too short: {ans!r}"
        assert body.get("session_id") == "e2e-test-single", "session_id mismatch"

    def ask_multi_turn_same_session(self):
        """同 session_id 问两轮 — backend 保持多轮上下文。"""
        import json
        sid = "e2e-test-multiturn"
        for i, q in enumerate(["什么是万用表", "怎么测直流电压"], 1):
            r = self._client.post("/api/ask", json={"question": q, "session_id": sid})
            assert r.status_code == 200, f"turn {i} status={r.status_code}"
            body = json.loads(r.text)
            assert len(body.get("answer", "").strip()) > 10, f"turn {i} answer too short"
            assert body.get("session_id") == sid, f"turn {i} session_id mismatch"

    def ask_question_validation(self):
        """空问题 → 422 (Pydantic min_length=1)。"""
        import json
        r = self._client.post("/api/ask", json={"question": "", "session_id": "e2e-x"})
        assert r.status_code == 422, f"status={r.status_code}"

    # --- polling ---
    def polling_nonexistent_task_404(self):
        r = self._client.get("/api/upload/00000000-0000-0000-0000-000000000000")
        assert r.status_code == 404, f"status={r.status_code}"

    # --- 编排 ---
    def run_all(self):
        print("\n--- Frontend ---")
        self._run("frontend: index.html", self.frontend_index)
        self._run("frontend: style.css", self.frontend_style_css)
        self._run("frontend: main.js", self.frontend_main_js)
        self._run("frontend: progress.js", self.frontend_progress_js)

        print("\n--- Upload 失败路径 ---")
        self._run("upload: .txt 被拒", self.upload_wrong_format_rejected)
        self._run("upload: MinerU 未配置护栏", self.upload_mineru_not_configured)

        print("\n--- Documents ---")
        self._run("documents: 返回数组", self.documents_list_is_array)
        self._run("documents: 删除不存在文档 200", self.documents_delete_nonexistent)

        print("\n--- Ask (结构断言) ---")
        self._run("ask: 单问答复非空", self.ask_returns_answer)
        self._run("ask: 多轮同 session", self.ask_multi_turn_same_session)
        self._run("ask: 空问题 422", self.ask_question_validation)

        print("\n--- Polling ---")
        self._run("polling: 不存在任务 404", self.polling_nonexistent_task_404)


# --- main ---
def main() -> int:
    report = Report()
    try:
        up()
        with Runner() as runner:
            wait_healthy(runner._client)
            runner.run_all()
            report = runner.report
    except Exception as e:
        print(f"\n[FATAL] {e}", file=sys.stderr)
        return 1
    finally:
        down()

    report.print_summary()
    return 0 if report.failed_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
