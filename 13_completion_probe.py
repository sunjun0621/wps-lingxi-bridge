# -*- coding: utf-8 -*-
# 实验：对新建会话触发补全（空 body），从报错/响应反推补全端点与字段
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

def create(path):
    r = requests.post(BASE + path, headers=headers, cookies=cookies, json={}, timeout=30)
    return r.json()["data"]["session_id"]

s_ai = create("/api/aigc/v3/assistant/sessions")
s_ao = create("/api/aioffice/v1/sessions")
print("assistant session:", s_ai, " aioffice session:", s_ao)

def trial(method, path, body):
    r = requests.request(method, BASE + path, headers=headers, cookies=cookies,
                         json=body, timeout=30, stream=True)
    print(f"\n==== {method} {path} -> {r.status_code} {r.headers.get('content-type')}")
    buf = b""
    for ch in r.iter_content(512):
        buf += ch
        if len(buf) > 1400:
            break
    print(buf.decode("utf-8", "replace"))

trial("POST", f"/api/aigc/v3/assistant/sessions/{s_ai}/completions", {})
trial("POST", f"/api/aioffice/v1/sessions/{s_ao}/completions", {})
trial("POST", f"/api/aioffice/v1/sessions/{s_ao}/messages", {})
