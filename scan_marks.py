# -*- coding: utf-8 -*-
p = r"C:\Users\Administrator\Doubao\chats\2026-10-14\new-chat\lingxi-reverse\appserver\app-server\service\lingxi.exe"
data = open(p, "rb").read()
marks = [b"python3", b"python31", b"PythonDLL", b"site-packages", b".pyc", b"libpython",
         b"Nuitka", b"nuitka", b"onefile", b"Onefile", b"__compiled__", b"zstandard", b"zstd",
         b"_MEIPASS", b"Py_SetPath", b"pyvenv.cfg", b"python.dll", b"VCRUNTIME",
         b"uvicorn", b"fastapi", b"FastAPI", b"websockets", b"sitecustomize", b"encodings",
         b"lib-dynload", b"python-standalone", b"PYTHONHOME", b"PyInstaller", b"cx_Freeze",
         b"__main__", b"importlib", b"compiled_", b".pyd", b"MSVCR", b"PYZ", b"shiv", b"pex"]
for m in marks:
    j = data.find(m)
    if j >= 0:
        print(f"{j:>9}  {m!r}")
print("---- 末尾256字节可打印预览 ----")
tail = data[-256:]
print(''.join(chr(b) if 32 <= b < 127 else '.' for b in tail))
