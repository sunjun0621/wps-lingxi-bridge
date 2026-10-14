# -*- coding: utf-8 -*-
import sys
base=r"C:\Users\Administrator\Doubao\chats\2026-10-14\new-chat\lingxi-reverse"
fn=sys.argv[1]; a=int(sys.argv[2]); b=int(sys.argv[3])
s=open(base+"\\"+fn,encoding="utf-8").read()
open(base+r"\gslice_out.txt","w",encoding="utf-8").write(s[a:b])
print("ok",len(s))
