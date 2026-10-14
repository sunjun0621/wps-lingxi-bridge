# -*- coding: utf-8 -*-
import os, json, sys
sys.stdout.reconfigure(encoding="utf-8")
base = r"C:\Users\Administrator\AppData\Roaming\WPS 灵犀\app-server-data\state\accounts\20647743\sessions"
s = os.path.join(base, "11959294053515412")

print("===== meta.json =====")
print(open(os.path.join(s, "meta.json"), encoding="utf-8").read())

print("===== rollout.jsonl 行结构 =====")
lines = open(os.path.join(s, "rollout.jsonl"), encoding="utf-8").read().splitlines()
print("总行数:", len(lines))
for i, ln in enumerate(lines):
    try:
        o = json.loads(ln)
    except Exception as e:
        print(i, "解析失败", e); continue
    keys = list(o.keys())
    t = o.get("type") or o.get("role") or o.get("kind")
    print(f"[{i}] type={t!r} keys={keys}")
