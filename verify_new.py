# -*- coding: utf-8 -*-
import requests, json, sys
sys.stdout.reconfigure(encoding="utf-8")
B = "http://127.0.0.1:8799"
T = "lingxi-bridge"
H = {"Authorization": "Bearer " + T}
out = []

out.append("console: " + str(requests.get(B + "/", params={"token": T}).status_code))

r = requests.get(B + "/v1/models", headers=H, timeout=10)
out.append("models: " + str(r.status_code))
for m in r.json()["data"]:
    if m["id"] != "auto":
        out.append(f"  {m['id']:32} efforts={m['reasoning_efforts']}")

r = requests.get(B + "/admin/account", headers=H, timeout=15)
out.append("account: " + r.text[:300])

r = requests.post(B + "/admin/qr/start", headers=H, timeout=30)
out.append("qr/start: " + r.text[:300])

open(r"C:\Users\Administrator\Doubao\chats\2026-10-14\new-chat\lingxi-reverse\verify_new_log.txt",
     "w", encoding="utf-8").write("\n".join(out))
print("done")
