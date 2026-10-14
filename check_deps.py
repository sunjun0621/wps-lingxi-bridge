# -*- coding: utf-8 -*-
import sys, importlib.util
print("python:", sys.executable, sys.version.split()[0])
mods = ["fastapi", "uvicorn", "requests", "win32crypt", "cryptography", "websocket"]
missing = [m for m in mods if importlib.util.find_spec(m) is None]
print("missing:", missing)
