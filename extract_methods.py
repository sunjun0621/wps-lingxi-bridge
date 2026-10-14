# -*- coding: utf-8 -*-
import re, sys
sys.stdout.reconfigure(encoding="utf-8")
p = r"C:\Users\Administrator\Doubao\chats\2026-10-14\new-chat\lingxi-reverse\extracted\out\main\index.js"
s = open(p, encoding="utf-8").read()

# 提取 .request("method" / .notify("method"
pat = re.compile(r'\.(?:request|notify)\(\s*([`"\'])([A-Za-z0-9_./\-]+)\1')
methods = {}
for m in pat.finditer(s):
    methods.setdefault(m.group(2), []).append(m.start())
print("===== transport.request/notify 的方法名 =====")
for name, pos in sorted(methods.items(), key=lambda x: x[1][0]):
    print(f"  {name:40} x{len(pos)}  first={pos[0]}")

# 提取形如 "component.xxx" / "turn.xxx" / "session.xxx" / "agent.xxx" 的字面量
print("\n===== 点号命名空间的方法/事件字面量 =====")
lit = re.compile(r'[`"\']((?:component|turn|run|session|agent|user|app|server|auth|account|skill|tool)[.][A-Za-z0-9_.\-]+)[`"\']')
found = {}
for m in lit.finditer(s):
    found.setdefault(m.group(1), m.start())
for name, pos in sorted(found.items(), key=lambda x: x[1]):
    print(f"  {name:40} @{pos}")
