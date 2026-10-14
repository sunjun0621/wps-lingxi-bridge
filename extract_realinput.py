# -*- coding: utf-8 -*-
import os, json, collections
out = r"C:\Users\Administrator\Doubao\chats\2026-10-14\new-chat\lingxi-reverse\realinput_report.txt"
base = r"C:\Users\Administrator\AppData\Roaming\WPS 灵犀\app-server-data\state\accounts\20647743\sessions"
samples = []
cm = collections.Counter(); re_ = collections.Counter(); keys = collections.Counter()
for d in os.listdir(base):
    rf = os.path.join(base, d, "rollout.jsonl")
    if not os.path.exists(rf): continue
    for line in open(rf, encoding="utf-8"):
        try: o = json.loads(line)
        except: continue
        if o.get("kind") == "user.input":
            c = o.get("content", {})
            if isinstance(c, dict):
                for k in c: keys[k] += 1
                cm[c.get("current_mode")] += 1
                re_[c.get("reasoning_effort")] += 1
                if len(samples) < 3 and c.get("text"):
                    samples.append(c)
lines = ["字段出现次数:", dict(keys), "",
         "current_mode 取值:", dict(cm), "",
         "reasoning_effort 取值:", dict(re_), "",
         "完整样本:"]
for s in samples:
    lines.append(json.dumps(s, ensure_ascii=False, indent=2)); lines.append("-"*50)
open(out, "w", encoding="utf-8").write("\n".join(str(x) for x in lines))
print("samples", len(samples))
