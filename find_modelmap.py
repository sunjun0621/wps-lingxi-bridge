# -*- coding: utf-8 -*-
import sys, re
sys.stdout.reconfigure(encoding="utf-8")
p = r"C:\Users\Administrator\Doubao\chats\2026-10-14\new-chat\lingxi-reverse\extracted\out\main\index.js"
s = open(p, encoding="utf-8").read()
out = r"C:\Users\Administrator\Doubao\chats\2026-10-14\new-chat\lingxi-reverse\modelmap.txt"
L = []
for var in ["rw", "Gye", "Nye"]:
    for pat in [f"const {var}=", f",{var}=", f"function {var}("]:
        i = s.find(pat)
        if i >= 0:
            L.append(f"### {var} via {pat!r} @{i}")
            L.append(s[i:i+400]); L.append("")
            break
open(out, "w", encoding="utf-8").write("\n".join(L))
print("ok")
