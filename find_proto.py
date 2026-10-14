# -*- coding: utf-8 -*-
import re, sys
sys.stdout.reconfigure(encoding="utf-8")
p = r"C:\Users\Administrator\Doubao\chats\2026-10-14\new-chat\lingxi-reverse\extracted\out\main\index.js"
s = open(p, encoding="utf-8").read()
# protocol_version 常量
for m in re.finditer(r'protocol_version', s):
    i = m.start()
    print(f"@{i}: ...{s[i-60:i+80]}...")
    print("-"*60)
