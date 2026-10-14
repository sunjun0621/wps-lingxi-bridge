# -*- coding: utf-8 -*-
import requests, sys
sys.stdout.reconfigure(encoding="utf-8")
B = "http://127.0.0.1:8799/v1/chat/completions"
H = {"Authorization": "Bearer lingxi-bridge", "Content-Type": "application/json"}
body = {"model": "deepseek-v4-pro-0813", "stream": True,
        "reasoning_effort": "max",
        "messages": [{"role": "user", "content": "9.11 和 9.9 哪个大？一句话回答。"}]}
r = requests.post(B, headers=H, json=body, stream=True, timeout=120)
reason, answer = [], []
for line in r.iter_lines():
    if not line or not line.startswith(b"data:"):
        continue
    payload = line[5:].strip()
    if payload == b"[DONE]":
        break
    import json
    d = json.loads(payload)
    delta = d["choices"][0]["delta"]
    if delta.get("reasoning_content"):
        reason.append(delta["reasoning_content"])
    if delta.get("content"):
        answer.append(delta["content"])
print("思维链长度:", len("".join(reason)))
print("思维链片段:", ("".join(reason))[:150])
print("回答:", ("".join(answer))[:200])
