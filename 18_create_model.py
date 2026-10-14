# -*- coding: utf-8 -*-
# 尝试在创建 assistant 会话时绑定模型，再补全，看回显模型是否变化
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

def ask(s, body):
    r = requests.post(BASE + f"/api/aigc/v3/assistant/sessions/{s}/completions",
                      headers=headers, cookies=cookies, json=body, timeout=60, stream=True)
    raw = b""
    for ch in r.iter_content(512):
        raw += ch
        if b"event:finish" in raw:
            break
    txt = raw.decode("utf-8", "replace")
    echo = ""; answer = ""
    for block in txt.split("\n\n"):
        data = ""
        for line in block.split("\n"):
            if line.startswith("data:"):
                data = line[5:].strip()
        if not data: continue
        try: j = json.loads(data)
        except Exception: continue
        if j.get("type") == "user" and isinstance(j.get("data"), dict):
            echo = j["data"].get("model", "")
        elif j.get("type") == "text":
            answer += j.get("data", "") or ""
    return echo, answer

create_variants = [
    {"expect_model": "deepseek-v4-pro"},
    {"model": "deepseek-v4-pro"},
    {"agent_id": "deepseek-v4-pro"},
    {"model_key": "deepseek-v4-pro"},
]
for cv in create_variants:
    r = requests.post(BASE + "/api/aigc/v3/assistant/sessions", headers=headers,
                      cookies=cookies, json=cv, timeout=30)
    s = r.json()["data"]["session_id"]
    echo, ans = ask(s, {"question": "你是哪个模型？只报名称。"})
    print(f"\n创建 body={cv} -> session={s} 回显 model={echo}")
    print("回答：", ans[:120])
