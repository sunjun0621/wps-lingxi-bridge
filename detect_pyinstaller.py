# -*- coding: utf-8 -*-
import sys
p = r"C:\Users\Administrator\Doubao\chats\2026-10-14\new-chat\lingxi-reverse\appserver\app-server\service\lingxi.exe"
data = open(p, "rb").read()
print("exe大小:", len(data))
magic = b"MEI\014\013\012\013\016"
print("PyInstaller cookie位置:", data.rfind(magic))
for m in [b"pyiboot", b"pyi-windows", b"PYZ-00.pyz", b"PYZ\x00", b"Nuitka", b"_pyinstaller", b"struct.pyc"]:
    print(repr(m), "->", data.find(m))
