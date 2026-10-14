# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding="utf-8")
p = r"C:\Users\Administrator\Doubao\chats\2026-10-14\new-chat\lingxi-reverse\extracted\out\main\index.js"
s = open(p, encoding="utf-8").read()
out = r"C:\Users\Administrator\Doubao\chats\2026-10-14\new-chat\lingxi-reverse\authurl_anchors.txt"
terms = ["account.wps.cn","authorize","/p/login","response_type","client_id","appid",
         "redirect_uri","loginWindow","login-window","authWindow","LoginWin","buildLogin",
         "loginPageUrl","oauth","cb=","/p/auth","qrlogin","qr?","loginType","login_type",
         "sms","phone","captcha","web_login","login/web","login/web_url"]
L=[]
for a in terms:
    pos=[]; i=s.find(a)
    while i>=0 and len(pos)<8:
        pos.append(i); i=s.find(a,i+1)
    L.append(f"{a!r:18}: {pos}")
open(out,"w",encoding="utf-8").write("\n".join(L))
print("done")
