# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding="utf-8")
p=r"C:\Users\Administrator\Doubao\chats\2026-10-14\new-chat\lingxi-reverse\extracted\out\main\index.js"
s=open(p,encoding="utf-8").read()
out=r"C:\Users\Administrator\Doubao\chats\2026-10-14\new-chat\lingxi-reverse\efforts_anchors.txt"
terms=["available-plans","AvailablePlans","getAvailablePlans","/plans","plans?",
       "xhigh","minimal","\"low\"","\"high\"","\"max\"","\"medium\"",
       "jQ=","function jQ","reasoning_efforts","REASONING","effortOptions","EFFORT"]
L=[]
for a in terms:
    pos=[];i=s.find(a)
    while i>=0 and len(pos)<6:
        pos.append(i);i=s.find(a,i+1)
    L.append(f"{a!r:20}:{pos}")
open(out,"w",encoding="utf-8").write("\n".join(L))
print("done")
