# -*- coding: utf-8 -*-
# 完整抓取一次带模型指定的对话，落盘原始 SSE，并解析事件类型序列
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

body = {"question": "1+1等于几？只回答阿拉伯数字，不要解释。", "model": "deepseek-v4-pro"}
r = requests.post(BASE + f"/api/aigc/v3/assistant/sessions/{s}/completions",
                  headers=headers, cookies=cookies, json=body, timeout=60, stream=True)

raw_lines = []
for ln in r.iter_lines(decode_unicode=True):
    raw_lines.append("" if ln is None else ln)
raw = "\n".join(raw_lines)
open(os.path.join(HERE, "sample_sse.txt"), "w", encoding="utf-8").write(raw)

# 解析事件块
blocks = [b for b in raw.split("\n\n") if b.strip()]
print("\n===== 事件序列 =====")
for b in blocks:
    ev = ""; data = ""
    for line in b.split("\n"):
        if line.startswith("event:"):
            ev = line[6:].strip()
        elif line.startswith("data:"):
            data = line[5:].strip()
    info = ""
    try:
        j = json.loads(data)
        info = f"type={j.get('type')} model={j.get('data',{}).get('model') if isinstance(j.get('data'),dict) else ''}"
    except Exception:
        info = data[:60]
    print(f"event={ev:10} {info}")
