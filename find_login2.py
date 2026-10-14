# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding="utf-8")
p = r"C:\Users\Administrator\Doubao\chats\2026-10-14\new-chat\lingxi-reverse\extracted\out\main\index.js"
s = open(p, encoding="utf-8").read()
out = r"C:\Users\Administrator\Doubao\chats\2026-10-14\new-chat\lingxi-reverse\login_anchors.txt"
terms = ["qrcode","qr_code","qrLogin","qr-url","二维码","scan","auth_mode",
         "account/login","login/start","login/url","login/qr","login/poll","login/refresh",
         "login/status","login/cancel","account/logout","account/status","account/info",
         "reasoning_effort","supported_efforts","supportedEfforts","efforts","thinking",
         "loginUrl","login_url","passport","account/wps","wps_login","sso"]
L=[]
for a in terms:
    pos=[]; i=s.find(a)
    while i>=0 and len(pos)<8:
        pos.append(i); i=s.find(a,i+1)
    L.append(f"{a!r:20}: {pos}")
open(out,"w",encoding="utf-8").write("\n".join(L))
print("done")
