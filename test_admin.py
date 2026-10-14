# -*- coding: utf-8 -*-
import requests, json, sys
sys.stdout.reconfigure(encoding="utf-8")
B = "http://127.0.0.1:8799"
H = {"Authorization": "Bearer lingxi-bridge"}
out = []

s = requests.get(B+"/admin/status", headers=H, timeout=30)
out.append("STATUS: "+json.dumps(s.json(), ensure_ascii=False, indent=2))

fc = requests.post(B+"/admin/find-config", headers=H, timeout=30)
out.append("FIND-CONFIG: "+json.dumps(fc.json(), ensure_ascii=False))

# 全部非 auto 模型
models = requests.get(B+"/v1/models", headers=H, timeout=30).json()["data"]
selected = [m["id"] for m in models if m["id"] != "auto"]
out.append("待导入: "+str(selected))

imp = requests.post(B+"/admin/import", headers={**H,"Content-Type":"application/json"},
                    json={"selected": selected}, timeout=60)
out.append("IMPORT: "+json.dumps(imp.json(), ensure_ascii=False, indent=2))

s2 = requests.get(B+"/admin/status", headers=H, timeout=30)
out.append("STATUS AFTER: imported="+str(s2.json()["config"]["imported"]))

open(r"C:\Users\Administrator\Doubao\chats\2026-10-14\new-chat\lingxi-reverse\admin_log.txt",
     "w", encoding="utf-8").write("\n\n".join(out))
print("done")
