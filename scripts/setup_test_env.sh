#!/usr/bin/env bash
# 在 WSL 内运行：安装测试依赖 + 跑 pytest
set -euo pipefail

export PATH="$HOME/.local/bin:$PATH"

cd "$(dirname "$0")/.."

echo "==> 同步项目依赖"
uv sync

echo "==> 添加测试依赖（pytest, httpx）"
uv add --dev pytest httpx pytest-asyncio

echo "==> 运行 pytest"
uv run python -m pytest apps/backend/tests/ -v --tb=short
