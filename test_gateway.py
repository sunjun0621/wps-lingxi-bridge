# -*- coding: utf-8 -*-
# 网关自测：流式单轮 + 同会话多轮记忆
import json, requests

G = "http://127.0.0.1:8788/v1"

def chat(messages, stream=False, model="wps-ai"):
    r = requests.post(G + "/chat/completions",
                      json={"model": model, "messages": messages, "stream": stream},
                      stream=stream, timeout=120)
    if not stream:
        return r.json()["choices"][0]["message"]["content"]
    out = ""
    for line in r.iter_lines(decode_unicode=True):
        if line and line.startswith("data:") and line != "data: [DONE]":
            j = json.loads(line[5:].strip())
            d = j["choices"][0]["delta"].get("content")
            if d:
                out += d
    return out

print("===== 流式单轮 =====")
print(chat([{"role": "user", "content": "用一句话介绍昆明"}], stream=True))

print("\n===== 多轮记忆 =====")
m = [{"role": "user", "content": "记住一个数字：6688。回复“收到”即可。"}]
a = chat(m)
print("第一轮：", a)
m += [{"role": "assistant", "content": a},
      {"role": "user", "content": "我刚才让你记的数字是多少？只回答数字。"}]
print("第二轮：", chat(m))
