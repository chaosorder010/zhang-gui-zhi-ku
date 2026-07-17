#!/usr/bin/env python3
from apps.backend.services.chunker import chunk_by_section

md = "# 手册标题\n\n忽略我(前导内容)\n\n## 章节A\n\n内容A。\n\n## 章节B\n\n内容B。\n\n"
chunks = chunk_by_section(md, item_name="iPhone16", max_chars=1000)
print(f"n chunks: {len(chunks)}")
for c in chunks:
    print(repr(c["text"]), "len=", len(c["text"]))

# 极短的 max_chars
print("\n -- max_chars=60 --")
chunks2 = chunk_by_section(md, item_name="iPhone16", max_chars=60)
for c in chunks2:
    print(repr(c["text"]), "len=", len(c["text"]))
