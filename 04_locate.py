# -*- coding: utf-8 -*-
# 在 extracted 全目录定位含指定关键词的文件及出现次数（不打印超长行）
import os, re, sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "extracted")
kws = sys.argv[1:] or ["assistant/sessions", "aioffice/v1/sessions", "public/v1/sessions", "copilot/sessions"]
rx = [(k, re.compile(re.escape(k))) for k in kws]

for dp, _, files in os.walk(ROOT):
    for fn in sorted(files):
        if not fn.endswith((".js", ".cjs", ".mjs", ".ts")):
            continue
        p = os.path.join(dp, fn)
        try:
            txt = open(p, "r", encoding="utf-8", errors="ignore").read()
        except Exception:
            continue
        hits = {k: len(r.findall(txt)) for k, r in rx if r.search(txt)}
        if hits:
            print(f"{p}  {hits}")
