# -*- coding: utf-8 -*-
# 单独测 assistant completions：空 body 报错，明确必填字段
import json, os
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = "https://lingxi.wps.cn"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Lingxi Claw/1.3.16 Chrome/144.0.7559.236 Electron/40.8.2 Safari/537.36")
cj = json.load(open(os.path.join(HERE, "cookies_decrypted.json"), encoding="utf-8"))
cookies = {c["name"]: c["value"] for c in cj
           if c["host"] in (".wps.cn", "web.wps.cn") and not c["value"].startswith("<")}
headers = {"Content-Type": "application/json", "X-Cc-Version": "1", "User-Agent": UA,
           "Referer": "https://lingxi.wps.cn/_desktop/lingxi/"}

s = requests.post(BASE + "/api/aigc/v3/assistant/sessions", headers=headers,
                  cookies=cookies, json={}, timeout=30).json()["data"]["session_id"]
print("session:", s)

r = requests.post(BASE + f"/api/aigc/v3/assistant/sessions/{s}/completions",
                  headers=headers, cookies=cookies, json={}, timeout=30)
print("empty body ->", r.status_code, r.headers.get("content-type"))
print(r.text[:1500])
