# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding="utf-8")
p = r"C:\Users\Administrator\Doubao\chats\2026-10-14\new-chat\lingxi-reverse\extracted\out\main\index.js"
s = open(p, encoding="utf-8").read()
a = int(sys.argv[1]); b = int(sys.argv[2])
print(s[a:b])
