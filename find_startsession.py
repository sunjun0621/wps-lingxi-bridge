# -*- coding: utf-8 -*-
import sys, re
sys.stdout.reconfigure(encoding="utf-8")
p = r"C:\Users\Administrator\Doubao\chats\2026-10-14\new-chat\lingxi-reverse\extracted\out\main\index.js"
s = open(p, encoding="utf-8").read()
for m in re.finditer(r'startSession', s):
    i = m.start()
    print(f"@{i}: {s[i-120:i+180]}")
    print("="*70)
