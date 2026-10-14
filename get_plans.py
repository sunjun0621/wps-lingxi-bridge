# -*- coding: utf-8 -*-
import requests, json, sys
sys.stdout.reconfigure(encoding="utf-8")
base=r"C:\Users\Administrator\Doubao\chats\2026-10-14\new-chat\lingxi-reverse"
ck=json.load(open(base+r"\cookies_decrypted.json",encoding="utf-8"))
items=ck if isinstance(ck,list) else ck.get("cookies",[])
sid=next((c["value"] for c in items if c.get("name")=="wps_sid"),None)
print("sid?",bool(sid))
H={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
   "Accept":"application/json",
   "Cookie":"wps_sid="+sid,
   "Referer":"https://lingxi.wps.cn/"}
data=None
for host in ["https://lingxi.wps.cn","https://www.wps.cn"]:
    try:
        r=requests.get(host+"/api/aioffice/v1/sessions/plans",headers=H,timeout=30)
        print(host,r.status_code,r.headers.get("content-type"))
        if r.status_code==200 and "json" in (r.headers.get("content-type") or ""):
            data=r.json(); print("from",host); break
    except Exception as e:
        print(host,"err",e)
if data is not None:
    json.dump(data,open(base+r"\plans.json","w",encoding="utf-8"),ensure_ascii=False,indent=2)
    models=(data.get("data") or data).get("models") if isinstance(data,dict) else None
    if models:
        for m in models:
            print(m.get("key"),"->",m.get("reasoning_efforts"), "| default:",m.get("default_reasoning_effort"))
