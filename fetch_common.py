# -*- coding: utf-8 -*-
import requests, re
base = r"C:\Users\Administrator\Doubao\chats\2026-10-14\new-chat\lingxi-reverse"
H={"User-Agent":"Mozilla/5.0"}
files = {
 "common.js":"https://ac.wpscdn.cn/account/js/common.4ab7f884.js",
 "kso-sdk.js":"https://ac.wpscdn.cn/account/libs/js/kso-acct-sdk.min.56e1089c.js",
}
L=[]
for name,u in files.items():
    t=requests.get(u,headers=H,timeout=30).text
    open(base+"\\"+name,"w",encoding="utf-8").write(t)
    L.append(f"### {name} len={len(t)}")
    for kw in ["getDomainUrl","buildPassportSignParams","generatePKCEParam","qr","getBaseUrl"]:
        i=t.find(kw)
        if i>=0: L.append(f"  {kw} @{i}: {t[max(0,i-30):i+220]}")
    L.append("")
open(base+r"\common_extract.txt","w",encoding="utf-8").write("\n".join(L))
print("done")
