# -*- coding: utf-8 -*-
import os
out = r"C:\Users\Administrator\Doubao\chats\2026-10-14\new-chat\lingxi-reverse\state_report.txt"
lines = []
def walk(root, maxdepth=3, title=""):
    lines.append(f"\n===== {title} {root} =====")
    root = root.rstrip("\\")
    base_depth = root.count(os.sep)
    for dp, dn, fn in os.walk(root):
        depth = dp.count(os.sep) - base_depth
        if depth > maxdepth:
            dn[:] = []; continue
        rel = dp.replace(root, "")
        for f in fn:
            fp = os.path.join(dp, f)
            try: sz = os.path.getsize(fp)
            except: sz = -1
            lines.append(f"{sz:9} {rel}\\{f}")

rt = r"C:\Users\Administrator\Doubao\chats\2026-10-14\new-chat\lingxi-reverse\bridge-runtime"
walk(rt, 4, "我的 bridge-runtime")
real = r"C:\Users\Administrator\AppData\Roaming\WPS 灵犀\app-server-data\state"
walk(real, 3, "真实 state")
# 也看 app-server-data 根
walk(r"C:\Users\Administrator\AppData\Roaming\WPS 灵犀\app-server-data", 1, "app-server-data 根")
open(out, "w", encoding="utf-8").write("\n".join(lines))
print("lines:", len(lines))
