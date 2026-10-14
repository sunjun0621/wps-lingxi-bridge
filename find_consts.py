# -*- coding: utf-8 -*-
import re, sys
sys.stdout.reconfigure(encoding="utf-8")
p = r"C:\Users\Administrator\Doubao\chats\2026-10-14\new-chat\lingxi-reverse\extracted\out\main\index.js"
s = open(p, encoding="utf-8").read()
# 找常量定义
for var in ["SZ", "jme", "Nme", "yU"]:
    for pat in [f"const {var}=", f",{var}=", f" {var}=", f";{var}="]:
        i = s.find(pat)
        if i >= 0:
            print(f"{var} 定义 @{i}: {s[i:i+160]}")
            print("-"*60)
            break
