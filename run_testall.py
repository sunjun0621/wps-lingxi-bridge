# -*- coding: utf-8 -*-
import requests, time, sys
sys.stdout.reconfigure(encoding="utf-8")
B = "http://127.0.0.1:8799"
H = {"Authorization": "Bearer lingxi-bridge", "Content-Type": "application/json"}
keys = ["deepseek-v4-flash-0731","deepseek-v4.1-flash","deepseek-v4-pro-0813",
        "qwen3.8_flash","qwen3.8_max","mimo-v2.6-pro","GLM-5.3-Flash","GLM-5.3",
        "minimax_m3","doubao_seed_2_1_pro_260628","kimi-k3"]
r = requests.post(B + "/admin/test-all", headers=H, json={"models": keys}, timeout=30)
print("start:", r.status_code, r.text)
last = -1
for _ in range(120):
    d = requests.get(B + "/admin/test-progress", headers=H, timeout=15).json()
    if d["finished"] != last:
        for it in d["done"][last + 1:] if last >= 0 else d["done"]:
            print(f"  {it['model']:32} {'OK ' if it['ok'] else 'FAIL'} {it['elapsed']}s "
                  + (it.get("snippet") or it.get("error") or ""))
        last = d["finished"]
    if not d["running"]:
        ok = sum(1 for x in d["done"] if x["ok"])
        print(f"DONE {ok}/{d['total']} available")
        break
    time.sleep(2)
