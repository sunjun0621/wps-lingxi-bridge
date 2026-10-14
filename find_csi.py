# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding="utf-8")
p = r"C:\Users\Administrator\Doubao\chats\2026-10-14\new-chat\lingxi-reverse\extracted\out\main\index.js"
s = open(p, encoding="utf-8").read()
for a in ["createSessionInternal", "session/start", "WT=", "const WT", "session_type:"]:
    pos = []; i = s.find(a)
    while i >= 0 and len(pos) < 10:
        pos.append(i); i = s.find(a, i + 1)
    print(f"{a!r:24}: {pos}")
