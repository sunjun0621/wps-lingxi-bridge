# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding="utf-8")
p = r"C:\Users\Administrator\Doubao\chats\2026-10-14\new-chat\lingxi-reverse\extracted\out\main\index.js"
s = open(p, encoding="utf-8").read()
for a in ["agent_input", "AgentInput", "user_input", "session_id:", "startRun(", "startRun ",
          "beginRun", "sendRun", "current_mode", "permission_mode", "reasoning_effort",
          "auto_approve", "new_session", "create_session", "session/create", "session/begin",
          "session_id", "expect_model", "resume_run", "parent_group"]:
    pos = []; i = s.find(a)
    while i >= 0 and len(pos) < 12:
        pos.append(i); i = s.find(a, i + 1)
    print(f"{a!r:20}: {pos}")
