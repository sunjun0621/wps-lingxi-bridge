# -*- coding: utf-8 -*-
# 探测身份/配置/权益接口，获取可用模型列表与当前模型
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

def show(method, path, **kw):
    r = requests.request(method, BASE + path, headers=headers, cookies=cookies, timeout=30, **kw)
    print(f"\n==== {method} {path} -> {r.status_code}")
    print(r.text[:2600])

for p in ["/api/aigc/v3/assistant/identity",
          "/api/aioffice/v1/cowork/profile",
          "/api/v3/userinfo",
          "/query/api/v1/list_merchandise"]:
    show("GET", p)
