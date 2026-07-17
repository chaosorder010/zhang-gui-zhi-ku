#!/usr/bin/env python3
"""从 MinerU Next.js RSC HTML 提取文本内容, 打印为可读文本."""
import re
import sys

html = sys.stdin.read()

# 1. strip script/style tags with content
html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL)

# 2. extract text from Next.js RSC pushes (__next_f.push([1,"..."])) which contain JSON-encoded UI payloads
# The payloads sometimes contain stringified React elements - we just want the plain text, so drop anything that looks like JSX-ish route
# The first push usually contains the rendered page text as a long string.
# Let's focus on the textual content between tags:
text = re.sub(r"<[^>]+>", " ", html)

# Collapse whitespace
text = re.sub(r"\s+", " ", text).strip()

# Save for inspection
with open("/tmp/mineru_text.txt", "w", encoding="utf-8") as f:
    f.write(text)

print(f"wrote {len(text)} chars to /tmp/mineru_text.txt")
print("---HEAD---")
print(text[:3000])
print("---key sections---")
# Find API-related snippets
for kw in ["extract/task", "api/v4", "api/v1", " Bearer ", "token", "curl", "Authorization", "upload", "result", "zip"]:
    idx = text.lower().find(kw.lower())
    if idx >= 0:
        snippet = text[max(0, idx - 100):idx + 200].replace("\n", " ")
        print(f"[{kw}] @{idx}: {snippet}")
        print()
