# -*- coding: utf-8 -*-
import os, sys, time, json
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(__file__))
from appserver_client import LingxiAppServer, AppServerError

ROOT = os.path.dirname(__file__)
RT = os.path.join(ROOT, "bridge-runtime")
EXE = os.path.join(ROOT, "appserver", "app-server", "service", "lingxi.exe")
SID = "V02S19YHk0LsxWHTKc7z3pKcV9m75Is00acef3de00013b0f3f"
os.makedirs(os.path.join(RT, "workspace"), exist_ok=True)

c = LingxiAppServer(EXE, os.path.join(RT, "config.json"),
                    os.path.join(RT, "state"), timeout=40)
c.start()
try:
    print("握手 OK:", c.handshake()["server_info"]["version"])
    print("登录:", c.login(SID))
    time.sleep(1.0)

    attempts = [
        ("A 最简(无session_id)", dict()),
        ("B 加workspace/skills/env", {
            "workspace_dir": os.path.join(RT, "workspace"),
            "official_skills_dir": r"C:\Users\Administrator\AppData\Roaming\WPS 灵犀\app_server_link\skills",
            "user_skills_dir": "", "target_skills_dir": "", "env": {}}),
    ]
    for name, extra in attempts:
        try:
            r = c.start_session(session_id=None, extra=extra if extra else None)
            print(f"[{name}] 成功:", json.dumps(r, ensure_ascii=False))
            break
        except AppServerError as e:
            print(f"[{name}] 失败: {e} | data={json.dumps(e.data, ensure_ascii=False)}")
finally:
    c.stop()
