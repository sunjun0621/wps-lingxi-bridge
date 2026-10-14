# -*- coding: utf-8 -*-
import requests, hashlib, base64, json, os, sys
sys.stdout.reconfigure(encoding="utf-8")
QR="https://qr.wps.cn"
s=requests.Session()
s.headers["User-Agent"]="Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
s.headers["Referer"]="https://account.wps.cn/"

# PKCE
def b64url(b): return base64.urlsafe_b64encode(b).rstrip(b"=").decode()
verifier=b64url(os.urandom(40))
challenge=b64url(hashlib.sha256(verifier.encode()).digest())
print("verifier:",verifier)
print("challenge:",challenge)

# 1) login_qrcode（不带 _jsonp，期望纯 JSON）
r=s.get(QR+"/api/v3/login_qrcode",params={"code_challenge":challenge},timeout=30)
print("\n[1] login_qrcode status:",r.status_code,"ct:",r.headers.get("content-type"))
print("   body:",r.text[:400])
o=r.json(); loginid=o.get("loginid") or o.get("data",{}).get("loginid")
print("   loginid:",loginid)

# 2) url
r2=s.get(QR+"/api/v3/login_qrcode/url",params={"loginid":loginid,"data":json.dumps({})},timeout=30)
print("\n[2] url status:",r2.status_code)
print("   body:",r2.text[:500])
try:
    uo=r2.json(); qrurl=uo.get("url") or uo.get("data",{}).get("url")
    print("   qr image url:",qrurl)
except: pass

# 3) login poll (state=scan)
r3=s.get(QR+"/api/v3/login_qrcode/login",params={"loginid":loginid,"state":"scan"},timeout=40)
print("\n[3] login poll status:",r3.status_code)
print("   body:",r3.text[:500])
