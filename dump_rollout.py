# -*- coding: utf-8 -*-
import os, json, sys
sys.stdout.reconfigure(encoding="utf-8")
base = r"C:\Users\Administrator\AppData\Roaming\WPS 灵犀\app-server-data\state\accounts\20647743\sessions"
s = os.path.join(base, "11959294053515412")
lines = open(os.path.join(s, "rollout.jsonl"), encoding="utf-8").read().splitlines()

def short(v, n=600):
    t = json.dumps(v, ensure_ascii=False)
    return t if len(t) <= n else t[:n] + f" …(+{len(t)-n}字符)"

want = [0, 1, 2, 4, 6, 7, 24, 25, 27, 28, 29, 30]
for i in want:
    o = json.loads(lines[i])
    print(f"\n========== [{i}] type={o['type']} ==========")
    print("content:", short(o.get("content")))
    print("status:", short(o.get("status"), 200))
