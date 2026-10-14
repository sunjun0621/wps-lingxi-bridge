# -*- coding: utf-8 -*-
"""依赖全量体检（手动排查用）：列出 6 个依赖包状态，缺包给清华源安装命令。

用法：python check_deps.py
说明：启动自检（bridge_gateway.py 内 _dep_check）只把关核心 3 包 + 可选 2 包；
      websocket-client 仅研究脚本使用，只在本全量清单里体现。
"""
import sys, importlib.util

MODS = [("fastapi", "fastapi"), ("uvicorn", "uvicorn"), ("requests", "requests"),
        ("win32crypt", "pywin32"), ("cryptography", "cryptography"),
        ("websocket", "websocket-client")]
MIRROR = "https://pypi.tuna.tsinghua.edu.cn/simple"

print("python:", sys.executable, sys.version.split()[0])
missing = [pip for mod, pip in MODS if importlib.util.find_spec(mod) is None]
for mod, pip in MODS:
    print(f"  [{'缺' if pip in missing else '有'}] {pip}")
if missing:
    print("缺失包安装命令（清华源）：")
    print(f'  "{sys.executable}" -m pip install -i {MIRROR} ' + " ".join(missing))
else:
    print("全部就绪")
