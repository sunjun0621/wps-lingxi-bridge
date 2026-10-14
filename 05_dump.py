# -*- coding: utf-8 -*-
# dump 关键词周围大段原文（用于看完整请求构造）
import sys, re
p, kw = sys.argv[1], sys.argv[2]
before = int(sys.argv[3]); after = int(sys.argv[4])
limit = int(sys.argv[5]) if len(sys.argv) > 5 else 3
txt = open(p, encoding="utf-8", errors="ignore").read()
for i, m in enumerate(re.finditer(re.escape(kw), txt)):
    if i >= limit:
        break
    print(f"\n================= match {i} =================")
    print(txt[max(0, m.start() - before): m.end() + after])
