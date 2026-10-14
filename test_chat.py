# -*- coding: utf-8 -*-
import os, sys, time, json, threading
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(__file__))
from appserver_client import LingxiAppServer, AppServerError

ROOT = os.path.dirname(__file__)
RT = os.path.join(ROOT, "bridge-runtime")
EXE = os.path.join(ROOT, "appserver", "app-server", "service", "lingxi.exe")
SID = "V02S19YHk0LsxWHTKc7z3pKcV9m75Is00acef3de00013b0f3f"
MODEL = sys.argv[1] if len(sys.argv) > 1 else "deepseek-v4-pro-0813"
Q = sys.argv[2] if len(sys.argv) > 2 else "请用一句话介绍你自己，并明确说明你具体是哪个模型、哪个版本。"

state = {"types": {}, "parts": {}, "events": [], "done": threading.Event(), "raw": []}

def on_notif(msg):
    method = msg.get("method"); p = msg.get("params", {})
    t = p.get("type", method)
    # dump 关键通知完整结构
    if t in ("c_text", "c_reasoning") and len(state["raw"]) < 6:
        state["raw"].append(msg)
    if t == "c_text":
        cid = p.get("id", p.get("componentId", "text"))
        state["types"][cid] = "c_text"
        state["parts"].setdefault(cid, []).append(p.get("delta", p.get("text", p.get("content", ""))))
    elif t in ("run.end", "run.cancelled") or t == "agent.error":
        state["terminal"] = t; state["done"].set()
    state["events"].append(t)

c = LingxiAppServer(EXE, os.path.join(RT, "config.json"),
                    os.path.join(RT, "state"), timeout=60)
c.on_notification(on_notif)
c.start()
try:
    c.handshake(); c.login(SID); time.sleep(0.8)
    sess = c.start_session()
    sid = sess["session_id"]
    print("会话:", sid)
    r = c.run_start(sid, {
        "text": Q, "files": [], "file_ids": [], "expect_model": MODEL,
        "refs": [], "permission_mode": "default", "current_mode": "agent"},
        model={"provider": "lingxi", "model_name": MODEL})
    print("run/start:", json.dumps(r, ensure_ascii=False))
    if not state["done"].wait(timeout=120):
        print("[超时]")
finally:
    c.stop()

print("\n===== 组件类型 =====")
for cid, ctype in state["types"].items():
    print(f"  {cid}: {ctype}")
print("\n===== 各组件内容 =====")
for cid, parts in state["parts"].items():
    txt = "".join(parts)
    if not txt.strip(): continue
    ctype = state["types"].get(cid, "?")
    print(f"\n--- [{ctype}] {cid} ---")
    print(txt)
print("\n===== RAW c_text/c_reasoning 通知样本 =====")
for m in state["raw"]:
    print(json.dumps(m, ensure_ascii=False))
print("\n事件:", state["events"])
