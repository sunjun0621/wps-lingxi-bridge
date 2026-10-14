# -*- coding: utf-8 -*-
import os, json, collections
out = r"C:\Users\Administrator\Doubao\chats\2026-10-14\new-chat\lingxi-reverse\sessions_now.txt"
base = r"C:\Users\Administrator\AppData\Roaming\WPS 灵犀\app-server-data\state\accounts\20647743\sessions"
L = []
L.append(f"base exists: {os.path.exists(base)}")
if os.path.exists(base):
    ds = os.listdir(base); L.append(f"session dirs: {len(ds)}")
    kinds = collections.Counter()
    found = None
    for d in ds:
        rf = os.path.join(base, d, "rollout.jsonl")
        if not os.path.exists(rf): continue
        for line in open(rf, encoding="utf-8"):
            try: o = json.loads(line)
            except: continue
            kinds[o.get("kind")] += 1
            if o.get("kind") == "user.input" and found is None:
                found = o.get("content")
    L.append(f"kinds: {dict(kinds)}")
    if found is not None:
        L.append("FOUND content: " + json.dumps(found, ensure_ascii=False, indent=2))
open(out, "w", encoding="utf-8").write("\n".join(L))
print("ok")
