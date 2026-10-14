# -*- coding: utf-8 -*-
import requests, json, time
B="http://127.0.0.1:8799"; T="lingxi-bridge"
H={"Authorization":"Bearer "+T}; O=[]
time.sleep(5)

# 1) 控制台页面
r=requests.get(B+"/", params={"token":T}, timeout=20)
O.append(f"控制台页面: status={r.status_code} 含标题={'灵犀 Bridge' in r.text}")
# 无令牌应 401
r0=requests.get(B+"/", timeout=20)
O.append(f"无令牌访问控制台: status={r0.status_code}")

# 2) 强制导入全部
models=requests.get(B+"/v1/models",headers=H,timeout=20).json()["data"]
sel=[m["id"] for m in models if m["id"]!="auto"]
imp=requests.post(B+"/admin/import",headers={**H,"Content-Type":"application/json"},
                  json={"selected":sel,"force":True},timeout=60).json()
O.append("强制导入: count=%d changed=%s backup=%s"%(imp["count"],imp["changed"],imp["backup"]))

# 3) status
st=requests.get(B+"/admin/status",headers=H,timeout=20).json()
O.append("已导入 (%d): %s"%(len(st["config"]["imported"]),st["config"]["imported"]))

# 4) 实测 kimi-k3
t0=time.time()
rk=requests.post(B+"/v1/chat/completions",headers={**H,"Content-Type":"application/json"},
   json={"model":"kimi-k3","messages":[{"role":"user","content":"用一句话介绍云南的省会城市。"}]},timeout=240)
oj=rk.json()
O.append("kimi-k3: status=%d 耗时=%.1fs\n  输出: %s"%(rk.status_code,time.time()-t0,
   oj.get("choices",[{}])[0].get("message",{}).get("content",oj)))

open(r"C:\Users\Administrator\Doubao\chats\2026-10-14\new-chat\lingxi-reverse\e2e_log.txt",
     "w",encoding="utf-8").write("\n\n".join(O))
print("done")
