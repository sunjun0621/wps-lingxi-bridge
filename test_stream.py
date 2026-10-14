# -*- coding: utf-8 -*-
import requests, sys, time
sys.stdout.reconfigure(encoding="utf-8")
model = sys.argv[1] if len(sys.argv) > 1 else "GLM-5.3-Flash"
q = sys.argv[2] if len(sys.argv) > 2 else "用一句话介绍昆明。"
url = "http://127.0.0.1:8799/v1/chat/completions"
h = {"Authorization": "Bearer lingxi-bridge"}
t0 = time.time()
r = requests.post(url, headers=h, json={"model": model,
    "messages": [{"role": "user", "content": q}], "stream": True},
    stream=True, timeout=240)
print("status:", r.status_code)
chunks, reasoning = [], []
first = None
for line in r.iter_lines():
    if not line: continue
    line = line.decode("utf-8")
    if not line.startswith("data:"): continue
    payload = line[5:].strip()
    if payload == "[DONE]":
        print("\n[DONE]"); break
    import json
    o = json.loads(payload)
    delta = o["choices"][0].get("delta", {})
    if "content" in delta:
        if first is None: first = time.time()-t0
        chunks.append(delta["content"]); print(delta["content"], end="", flush=True)
    if "reasoning_content" in delta:
        reasoning.append(delta["reasoning_content"])
print("\n\n首字耗时: %.2fs  总耗时: %.1fs" % (first or 0, time.time()-t0))
print("正文长度:", len("".join(chunks)), " 推理长度:", len("".join(reasoning)))
