# -*- coding: utf-8 -*-
import os, json, sys
sys.stdout.reconfigure(encoding="utf-8")
base = r"C:\Users\Administrator\AppData\Roaming\WPS 灵犀\app-server-data"

print("===== auth.json =====")
print(open(os.path.join(base, "auth.json"), encoding="utf-8").read())

sess = os.path.join(base, "state", "accounts", "20647743", "sessions")
dirs = sorted([d for d in os.scandir(sess) if d.is_dir()],
              key=lambda d: d.stat().st_mtime, reverse=True)
print("会话目录总数:", len(dirs))
for s in dirs[:4]:
    print(f"\n--- {s.name}  mtime={s.stat().st_mtime} ---")
    for f in os.scandir(s.path):
        print(f"   {f.stat().st_size:>8}  {f.name}")
