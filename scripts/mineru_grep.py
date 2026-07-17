#!/usr/bin/env python3
"""在 /tmp/mineru_text.txt 中 grep 关键词, 打印前后上下文."""
import re
import sys

with open("/tmp/mineru_text.txt", encoding="utf-8") as f:
    text = f.read()

keywords = sys.argv[1:] or [
    "task_id",
    "extract/result",
    "/api/v4/",
    "/api/v1/",
    '"code"',
    '"status"',
    "download_url",
    "zip_url",
    "trace_id",
    " ",
]

for kw in keywords:
    pattern = re.escape(kw)
    for m in re.finditer(pattern, text, re.IGNORECASE):
        s = text[max(0, m.start() - 60):m.start() + 200].replace("\n", " ")
        print(f"[{kw}] @{m.start()}: {s}")
        print()
        break
