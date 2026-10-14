# -*- coding: utf-8 -*-
import requests, sys
sys.stdout.reconfigure(encoding="utf-8")
H = {"Authorization": "Bearer lingxi-bridge"}
d = requests.get("http://127.0.0.1:8799/admin/test-progress", headers=H).json()
for it in d["done"]:
    print(f"{it['model']:32} {'OK ' if it['ok'] else 'FAIL'} {it['elapsed']:>5}s "
          + (it.get("snippet") or it.get("error") or ""))
print("running:", d["running"], "total:", d["total"])
