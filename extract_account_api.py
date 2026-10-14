# -*- coding: utf-8 -*-
import requests, re
sess = requests.Session()
sess.headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
url = "https://account.wps.cn/?protocolnames=lingxi_privacy,lingxi_agreements&cb="+requests.utils.quote("https://lingxi.wps.cn/_desktop/lingxi/index.html")
html = sess.get(url, timeout=30).text
base = r"C:\Users\Administrator\Doubao\chats\2026-10-14\new-chat\lingxi-reverse"
open(base+r"\account_login.html","w",encoding="utf-8").write(html)

paths=set()
for m in re.finditer(r'["\'`](/?(?:p|passport|api)/[A-Za-z0-9_./\-]+)', html):
    paths.add(m.group(1))
L=["===== 接口路径 ====="]+sorted(paths)
# 二维码相关函数上下文
for kw in ["qrcode","qr_code","scan","poll","qrcode_status","setInterval","grant_token","wps_sid"]:
    for m in list(re.finditer(re.escape(kw), html))[:3]:
        i=m.start(); L.append(f"\n--- {kw} @{i} ---\n"+html[max(0,i-150):i+200])
open(base+r"\account_api.txt","w",encoding="utf-8").write("\n".join(L))
print("paths:",len(paths))
