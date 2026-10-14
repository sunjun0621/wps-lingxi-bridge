# -*- coding: utf-8 -*-
import subprocess, json, threading, time, sys, os
sys.stdout.reconfigure(encoding="utf-8")

RT = r"C:\Users\Administrator\Doubao\chats\2026-10-14\new-chat\lingxi-reverse\bridge-runtime"
EXE = r"C:\Users\Administrator\Doubao\chats\2026-10-14\new-chat\lingxi-reverse\appserver\app-server\service\lingxi.exe"
SID = "V02S19YHk0LsxWHTKc7z3pKcV9m75Is00acef3de00013b0f3f"
MODEL = sys.argv[1] if len(sys.argv) > 1 else "deepseek-v4-pro-0813"
QUESTION = sys.argv[2] if len(sys.argv) > 2 else "请用一句话介绍你自己，并明确说明你具体是哪个模型（含版本）。"

proc = subprocess.Popen(
    [EXE, "--stdin", "--auth-storage=runtime",
     "--config", os.path.join(RT, "config.json"),
     "--data-dir", os.path.join(RT, "state")],
    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    bufsize=1, text=True, encoding="utf-8")

lock = threading.Lock()
next_id = 0
done = threading.Event()
outcome = {"text": [], "events": []}

def send(obj):
    line = json.dumps(obj, ensure_ascii=False) + "\n"
    with lock:
        proc.stdin.write(line); proc.stdin.flush()

def request(method, params=None):
    global next_id
    next_id += 1
    rid = f"desktop_{next_id}"
    o = {"jsonrpc": "2.0", "id": rid, "method": method}
    if params is not None: o["params"] = params
    send(o)

def notify(method, params=None):
    o = {"jsonrpc": "2.0", "method": method}
    if params is not None: o["params"] = params
    send(o)

def reader():
    for raw in proc.stdout:
        raw = raw.rstrip("\n")
        if not raw.strip(): continue
        try:
            msg = json.loads(raw)
        except Exception:
            print("[RAW]", raw[:300]); continue
        handle(msg)

def handle(msg):
    method = msg.get("method")
    if method is not None:  # 服务端通知/请求
        p = msg.get("params", {})
        t = p.get("type", method)
        if t == "component.content":
            delta = p.get("delta", "")
            cid = p.get("componentId", "")
            outcome["text"].append((cid, delta))
            print(f"[内容 {cid}] {delta}", end="", flush=True)
        else:
            print(f"\n[事件] {t}  {json.dumps({k:v for k,v in p.items() if k not in ('delta',)}, ensure_ascii=False)[:300]}")
        outcome["events"].append(t)
        if t in ("run.end", "run.cancelled") or method == "agent.error":
            outcome["terminal"] = t; done.set()
    else:
        print("[响应]", json.dumps(msg, ensure_ascii=False)[:300])

th = threading.Thread(target=reader, daemon=True)
th.start()

# 1) initialize
request("initialize", {
    "protocol_version": "2026-08-13",
    "client_info": {"name": "wps-lingxi-desktop", "version": "1.3.16"},
    "capabilities": {"bash_approval": False, "skill_management": False, "timer_task": True, "auth_refresh": True},
    "device_id": "bridge-test-device", "device_name": "Bridge"})
time.sleep(1.2)
# 2) initialized
notify("initialized")
time.sleep(0.5)
# 3) login
request("account/login/start", {"auth_mode": "wps_sid", "wps_sid": SID})
time.sleep(1.5)
# 4) run/start
session_id = "119" + str(int(time.time()*1000))[:14]
request("run/start", {
    "session_id": session_id,
    "agent_input": {
        "text": QUESTION, "files": [], "file_ids": [],
        "expect_model": MODEL, "refs": [],
        "permission_mode": "default", "reasoning_effort": "default",
        "current_mode": "chat", "browser_plugin_enabled": False}})
print(f"\n>>> 已发起 run/start, model={MODEL}, session={session_id}")

if not done.wait(timeout=90):
    print("\n[超时] 90 秒未收到 run.end")
print("\n\n===== 事件序列 =====")
print(outcome["events"])
try: proc.stdin.close()
except: pass
try: proc.terminate()
except: pass
