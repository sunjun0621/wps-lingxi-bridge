# -*- coding: utf-8 -*-
# 解析 WPS 灵犀 app.asar，列出文件清单，定位网络/鉴权/模型相关模块（只读分析，不修改原程序）
import struct, json, os

ASAR = r"D:\Softstore\2_Daily\lingxi-desktop\resources\app.asar"
OUTDIR = os.path.dirname(os.path.abspath(__file__))

f = open(ASAR, "rb")
b = f.read(16)
header_size = struct.unpack("<I", b[4:8])[0]   # 头部 pickle 总大小
json_len = struct.unpack("<I", b[12:16])[0]    # JSON 字符串长度，JSON 从偏移 16 开始
header = json.loads(f.read(json_len).decode("utf-8"))
DATA_START = 8 + header_size

entries = {}  # 路径 -> (offset, size, unpacked)

def walk(node, prefix):
    for name, e in node.get("files", {}).items():
        p = prefix + "/" + name
        if "files" in e:
            walk(e, p)
        else:
            entries[p] = (int(e.get("offset", 0)), int(e.get("size", 0)), e.get("unpacked", False))

walk(header, "")
listing = sorted(entries)

with open(os.path.join(OUTDIR, "asar_filelist.txt"), "w", encoding="utf-8") as o:
    for p in listing:
        off, size, unp = entries[p]
        o.write(f"{size}\t{int(unp)}\t{p}\n")

print("DATA_START =", DATA_START)
print("total files =", len(listing))
tops = sorted({p.split("/")[1] for p in listing if len(p.split("/")) > 1})
print("top level =", tops)

# 非 node_modules 的目录树（前 120 条）
own = [p for p in listing if "/node_modules/" not in p]
print("\n===== 业务自有文件（共 %d，显示前 120）=====" % len(own))
for p in own[:120]:
    print(entries[p][1], p)

kw = ["request", "http", "network", "api", "llm", "chat", "model", "aigc",
      "auth", "token", "sign", "proxy", "stream", "complet", "fetch", "client"]
hits = [p for p in own if p.endswith((".js", ".cjs", ".mjs", ".ts"))
        and any(k in p.lower() for k in kw)]
print("\n===== 业务自有中疑似网络/鉴权/模型文件（%d）=====" % len(hits))
for p in hits:
    print(entries[p][1], p)
