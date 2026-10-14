# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding="utf-8")
p = r"C:\Users\Administrator\Doubao\chats\2026-10-14\new-chat\lingxi-reverse\extracted\out\main\index.js"
s = open(p, encoding="utf-8").read()
print("START, len=", len(s))
anchors = ["stdin", "stdout", "jsonrpc", "Content-Length", "createInterface",
           "method", "initialize", "write", "frame", "Frame",
           "notification", "request_id", "client_type", "auth", "Auth",
           "send", "input", "Input", "onData", "readline"]
for a in anchors:
    cnt = s.count(a)
    first = s.find(a)
    print(f"{a!r:18} count={cnt:4} first={first}")
