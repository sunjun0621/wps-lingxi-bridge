# -*- coding: utf-8 -*-
import os, json
out = r"C:\Users\Administrator\Doubao\chats\2026-10-14\new-chat\lingxi-reverse\raw_rollout.txt"
base = r"C:\Users\Administrator\AppData\Roaming\WPS 灵犀\app-server-data\state\accounts\20647743\sessions"
L = []
for d in sorted(os.listdir(base)):
    rf = os.path.join(base, d, "rollout.jsonl")
    if not os.path.exists(rf): continue
    lines = open(rf, encoding="utf-8").read().splitlines()
    if not lines: continue
    L.append(f"### session {d}, {len(lines)} lines")
    for ln in lines[:2]:
        try:
            L.append(json.dumps(json.loads(ln), ensure_ascii=False)[:600])
        except: L.append("PARSE FAIL: " + ln[:200])
    L.append("")
    if len(L) > 20: break
open(out, "w", encoding="utf-8").write("\n".join(L))
print("ok")
