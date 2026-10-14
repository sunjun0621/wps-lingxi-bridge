# -*- coding: utf-8 -*-
# 验证 expect_model 切换模型是否生效（UTF-8 正确解析），并验证同 session 多轮上下文
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

def ask(s, body):
    r = requests.post(BASE + f"/api/aigc/v3/assistant/sessions/{s}/completions",
                      headers=headers, cookies=cookies, json=body, timeout=60, stream=True)
    raw = b""
    for ch in r.iter_content(512):
        raw += ch
        if b"event:finish" in raw:
            break
    txt = raw.decode("utf-8", "replace")
    echo_model = ""; answer = ""
    for block in txt.split("\n\n"):
        data = ""
        for line in block.split("\n"):
            if line.startswith("data:"):
                data = line[5:].strip()
        if not data:
            continue
        try:
            j = json.loads(data)
        except Exception:
            continue
        if j.get("type") == "user" and isinstance(j.get("data"), dict):
            echo_model = j["data"].get("model", "")
        elif j.get("type") == "text":
            answer += j.get("data", "") or ""
    return echo_model, answer

for mdl in ["deepseek-v4-pro", "GLM-5-Turbo", "kimi-2.6"]:
    s = new_session()
    echo, ans = ask(s, {"question": "用一句话说明你擅长什么。", "expect_model": mdl})
    print(f"\n## 请求 expect_model={mdl}  服务端回显 model={echo}")
    print("回答：", ans)

# 多轮上下文：同 session 两问
s = new_session()
ask(s, {"question": "记住一个数字：8848。", "expect_model": "deepseek-v4-pro"})
_, ans2 = ask(s, {"question": "我刚才让你记的数字是多少？只回答数字。", "expect_model": "deepseek-v4-pro"})
print("\n## 多轮记忆测试，第二轮回答：", ans2)
