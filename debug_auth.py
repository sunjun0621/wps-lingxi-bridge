# -*- coding: utf-8 -*-
import json, sys, requests
sys.stdout.reconfigure(encoding="utf-8")
base = r"C:\Users\Administrator\Doubao\chats\2026-10-14\new-chat\lingxi-reverse"
ck = json.load(open(base + r"\cookies_decrypted.json", encoding="utf-8"))
items = ck if isinstance(ck, list) else ck.get("cookies", [])
sid = next(c["value"] for c in items if c.get("name") == "wps_sid")
r = requests.post("https://account.wps.cn/p/auth/check",
                   headers={"User-Agent": "Mozilla/5.0", "Cookie": "wps_sid=" + sid,
                            "Accept": "application/json", "Origin": "https://lingxi.wps.cn",
                            "Referer": "https://lingxi.wps.cn/"},
                   timeout=10, allow_redirects=False)
print(json.dumps(r.json(), ensure_ascii=False, indent=2))
