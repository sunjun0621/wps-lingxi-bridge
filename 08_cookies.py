# -*- coding: utf-8 -*-
# 解密灵犀 lingxi.wps.cn 分区 Cookies，提取 wps_sid 等登录态（结果敏感，勿外传）
# 注意：本脚本依赖「WPS 灵犀桌面客户端」的本地数据目录；客户端已卸载时请改用
#       控制台扫码登录（http://127.0.0.1:8799/ → 扫码登录 / 切换账号），无需任何客户端。
import os, sys, json, base64, sqlite3, shutil
import win32crypt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

HERE = os.path.dirname(os.path.abspath(__file__))
UD = r"C:\Users\Administrator\AppData\Roaming\WPS 灵犀"

if not os.path.isdir(UD):
    print("[提示] 未找到灵犀客户端数据目录：", UD)
    print("       客户端可能已卸载/未安装——这是正常的：本桥运行不依赖客户端。")
    print("       刷新登录请改用控制台扫码（无需任何客户端）：")
    print("         http://127.0.0.1:8799/  → 「扫码登录 / 切换账号」→ WPS 手机 APP 扫码")
    sys.exit(0)

ls = json.load(open(os.path.join(UD, "Local State"), encoding="utf-8"))
raw = base64.b64decode(ls["os_crypt"]["encrypted_key"])
assert raw[:5] == b"DPAPI", raw[:5]
_, master = win32crypt.CryptUnprotectData(raw[5:], None, None, None, 0)
print("master key len:", len(master))

src = os.path.join(UD, r"Partitions\lingxi.wps.cn\Network\Cookies")
tmp = os.path.join(HERE, "_Cookies.db")
shutil.copy2(src, tmp)
con = sqlite3.connect(tmp)
rows = con.execute("select host_key,name,encrypted_value,path from cookies").fetchall()

def dec(v):
    if v[:3] in (b"v10", b"v20"):
        nonce = v[3:15]; data = v[15:]
        pt = AESGCM(master).decrypt(nonce, data, None)
        # Chrome 130+ 明文前 32 字节为 host 绑定摘要，其后才是 cookie 真实值
        return pt[32:].decode("utf-8", "replace")
    try:
        _, val = win32crypt.CryptUnprotectData(v, None, None, None, 0)
        return val.decode("utf-8", "replace")
    except Exception as e:
        return "<dec fail %r>" % e

out = []
for host, name, v, path in rows:
    out.append({"host": host, "name": name, "value": dec(v), "path": path})

json.dump(out, open(os.path.join(HERE, "cookies_decrypted.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
print("cookie count:", len(out))
for c in out:
    print(c["host"], c["name"], "=", c["value"][:70])
