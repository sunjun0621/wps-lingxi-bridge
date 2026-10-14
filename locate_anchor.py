# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding="utf-8")
p = r"C:\Users\Administrator\Doubao\chats\2026-10-14\new-chat\lingxi-reverse\extracted\out\main\index.js"
s = open(p, encoding="utf-8").read()
print("文件字符数:", len(s))
anchors = ["--stdin", "auth-storage", "app_server_link", "localAgentFacade", "lingxi.exe",
           "AgentInput", "open_position", "lingxiclaw", "expect_model", "auth_mode",
           "--data-dir", "--config", "wps_sid"]
for a in anchors:
    pos = []
    i = s.find(a)
    while i >= 0 and len(pos) < 6:
        pos.append(i); i = s.find(a, i + 1)
    print(f"\n### {a!r} 出现位置: {pos}")
