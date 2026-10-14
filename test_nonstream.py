# -*- coding: utf-8 -*-
import requests, json, sys, time
sys.stdout.reconfigure(encoding="utf-8")
url = "http://127.0.0.1:8799/v1/chat/completions"
h = {"Authorization": "Bearer lingxi-bridge"}
model = sys.argv[1] if len(sys.argv) > 1 else "deepseek-v4-flash-0731"
q = sys.argv[2] if len(sys.argv) > 2 else "1+1等于几？只回答阿拉伯数字，不要解释。"
t0 = time.time()
r = requests.post(url, headers=h, json={
    "model": model,
    "messages": [{"role": "user", "content": q}],
    "stream": False}, timeout=240)
print("status:", r.status_code, "耗时: %.1fs" % (time.time()-t0))
print(json.dumps(r.json(), ensure_ascii=False, indent=2))
