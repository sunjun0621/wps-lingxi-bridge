# -*- coding: utf-8 -*-
import requests, re, json
out = r"C:\Users\Administrator\Doubao\chats\2026-10-14\new-chat\lingxi-reverse\account_probe.txt"
sess = requests.Session()
sess.headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
url = "https://account.wps.cn/?protocolnames=lingxi_privacy,lingxi_agreements&cb="+requests.utils.quote("https://lingxi.wps.cn/_desktop/lingxi/index.html")
r = sess.get(url, timeout=30, allow_redirects=True)
L=[f"status={r.status_code} url={r.url} len={len(r.text)}",
   "set-cookie="+str(r.headers.get("set-cookie"))]
# script src
for m in re.finditer(r'<script[^>]+src=["\']([^"\']+)["\']', r.text):
    L.append("script src: "+m.group(1))
for m in re.finditer(r'<link[^>]+href=["\']([^"\']+)["\']', r.text):
    L.append("link: "+m.group(1))
# 标题/关键文本
t = re.search(r'<title>(.*?)</title>', r.text)
L.append("title: "+(t.group(1) if t else "?"))
# 找二维码/qr 相关内联
for kw in ["qrcode","qr_code","qr-code","二维码","/p/","passport","api/"]:
    i = r.text.find(kw)
    if i>=0: L.append(f"inline {kw}: ...{r.text[max(0,i-40):i+80]}...")
open(out,"w",encoding="utf-8").write("\n".join(L))
print("done", r.status_code)
