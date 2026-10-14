# -*- coding: utf-8 -*-
# 实验：逐个候选字段名发送，判断哪个是用户输入字段（看 SSE 是否进入正常生成而非 error）
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

def new_session():
    return requests.post(BASE + "/api/aigc/v3/assistant/sessions", headers=headers,
                         cookies=cookies, json={}, timeout=30).json()["data"]["session_id"]

def read_some(r, maxlines=14):
    lines = []
    for ln in r.iter_lines(decode_unicode=True):
        lines.append(ln if ln is not None else "")
        if len(lines) >= maxlines or (isinstance(ln, str) and ln.startswith("event:finish")):
            break
    return "\n".join(lines)

for field in ["query", "question", "content", "prompt", "text", "message"]:
    s = new_session()
    r = requests.post(BASE + f"/api/aigc/v3/assistant/sessions/{s}/completions",
                      headers=headers, cookies=cookies, json={field: "你好"},
                      timeout=40, stream=True)
    print(f"\n######## field={field} -> {r.status_code}")
    print(read_some(r)[:900])
