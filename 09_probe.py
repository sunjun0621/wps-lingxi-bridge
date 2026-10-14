# -*- coding: utf-8 -*-
# 离线重放验证：用解密得到的 cookie 直连 lingxi.wps.cn，验证登录态与接口可用性
import json, os, sys
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = "https://lingxi.wps.cn"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Lingxi Claw/1.3.16 Chrome/144.0.7559.236 Electron/40.8.2 Safari/537.36")

cj = json.load(open(os.path.join(HERE, "cookies_decrypted.json"), encoding="utf-8"))
cookies = {c["name"]: c["value"] for c in cj
           if c["host"] in (".wps.cn", "web.wps.cn") and not c["value"].startswith("<")}
print("using cookies:", sorted(cookies))

headers = {"Content-Type": "application/json", "X-Cc-Version": "1", "User-Agent": UA,
           "Referer": "https://lingxi.wps.cn/_desktop/lingxi/"}

def show(method, path, **kw):
    r = requests.request(method, BASE + path, headers=headers, cookies=cookies, timeout=30, **kw)
    print(f"\n==== {method} {path} -> {r.status_code} {r.headers.get('content-type')}")
    print(r.text[:1800])
    return r

show("GET", "/api/aigc/v3/assistant/sessions?page=1&size=10")
