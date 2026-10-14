# -*- coding: utf-8 -*-
# 通过 CDP 抓取灵犀 completions/sessions 请求的 URL/请求头/请求体/响应（含登录 Cookie，文件敏感，勿外传）
import json, time, sys, os
import websocket

wsurl = sys.argv[1]
duration = int(sys.argv[2]) if len(sys.argv) > 2 else 120
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cdp_capture.json")

ws = websocket.create_connection(wsurl)
mid = 0
pending = {}

def send(method, params=None):
    global mid
    mid += 1
    ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
    return mid

send("Network.enable")
send("Runtime.enable")
start = time.time()
results = []
reqmeta = {}

def save():
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

while time.time() - start < duration:
    try:
        ws.settimeout(2)
        m = json.loads(ws.recv())
    except Exception:
        continue
    meth = m.get("method")
    p = m.get("params", {})
    if meth == "Network.requestWillBeSent":
        req = p["request"]; rid = p["requestId"]; url = req["url"]
        if "/completions" in url or url.rstrip("/").endswith("/sessions"):
            meta = {"requestId": rid, "url": url, "method": req["method"],
                    "headers": req["headers"], "postData": req.get("postData"), "response": None}
            reqmeta[rid] = meta; results.append(meta)
            print(">>> REQ", req["method"], url, flush=True)
            if not req.get("postData"):
                try:
                    pending[send("Network.getRequestPostData", {"requestId": rid})] = ("post", rid)
                except Exception as e:
                    print("postdata err", e)
            save()
    elif meth == "Network.loadingFinished":
        rid = p["requestId"]
        if rid in reqmeta:
            try:
                pending[send("Network.getResponseBody", {"requestId": rid})] = ("body", rid)
            except Exception as e:
                print("body err", e)
    if "id" in m and m["id"] in pending:
        kind, rid = pending.pop(m["id"])
        if rid in reqmeta:
            if kind == "post":
                reqmeta[rid]["postData"] = m.get("result", {}).get("postData", "")
            else:
                reqmeta[rid]["response"] = m.get("result", {}).get("body", "")
        save()

save()
print("done, captures:", len(results))
