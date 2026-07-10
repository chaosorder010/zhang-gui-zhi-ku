#!/usr/bin/env bash
# 跑测试快捷脚本
set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"
cd "$(dirname "$0")/.."
uv run python -m pytest apps/backend/tests/ "$@"
