# -*- coding: utf-8 -*-
# 提取 app.asar 中业务自有文件（排除 node_modules），并扫描接口域名/路径/鉴权关键字
import struct, json, os, re
from collections import Counter

ASAR = r"D:\Softstore\2_Daily\lingxi-desktop\resources\app.asar"
ROOT = os.path.dirname(os.path.abspath(__file__))
EXDIR = os.path.join(ROOT, "extracted")

f = open(ASAR, "rb")
b = f.read(16)
header_size = struct.unpack("<I", b[4:8])[0]
json_len = struct.unpack("<I", b[12:16])[0]
header = json.loads(f.read(json_len).decode("utf-8"))
DATA_START = 8 + header_size

entries = {}

def walk(node, prefix):
    for name, e in node.get("files", {}).items():
        p = prefix + "/" + name
        if "files" in e:
            walk(e, p)
        else:
            entries[p] = (int(e.get("offset", 0)), int(e.get("size", 0)), e.get("unpacked", False))

walk(header, "")

def read_file(p):
    off, size, unp = entries[p]
    if unp:
        return None
    f.seek(DATA_START + off)
    return f.read(size)

# 1) 提取业务自有文件
own = [p for p in entries if "/node_modules/" not in p and not p.startswith("/node_modules")]
for p in own:
    data = read_file(p)
    if data is None:
        continue
    dst = os.path.join(EXDIR, p.lstrip("/").replace("/", os.sep))
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(dst, "wb") as o:
        o.write(data)
print("extracted business files:", len(own))

# 2) 扫描
url_re = re.compile(r"https?://[a-zA-Z0-9.\-]+(?::\d+)?(?:/[^\s\"'`<>\\)]*)?")
path_re = re.compile(r"[\"'`](/[a-zA-Z0-9_\-./{}:]*(?:api|aigc|chat|complet|stream|llm|model|conv|message|dialog|infer)[a-zA-Z0-9_\-./{}:]*)[\"'`]", re.I)
hosts = Counter()
urls = set()
paths = set()
auth_hits = []
auth_re = re.compile(r"(authorization|x-csrf|csrf|signature|x-sign|signkey|bearer|access[_-]?token|wps[_-]?token|set-cookie)", re.I)

for p in own:
    if not p.endswith((".js", ".cjs", ".mjs", ".ts", ".json", ".html")):
        continue
    data = read_file(p)
    if data is None:
        continue
    try:
        txt = data.decode("utf-8", "ignore")
    except Exception:
        continue
    for u in url_re.findall(txt):
        urls.add(u)
        m = re.match(r"https?://([a-zA-Z0-9.\-]+)", u)
        if m:
            hosts[m.group(1)] += 1
    for pp in path_re.findall(txt):
        paths.add(pp)
    if auth_re.search(txt):
        for mm in auth_re.finditer(txt):
            auth_hits.append((p, mm.group(1).lower()))

with open(os.path.join(ROOT, "endpoints_report.txt"), "w", encoding="utf-8") as r:
    r.write("===== HOSTS =====\n")
    for h, c in hosts.most_common():
        r.write(f"{c}\t{h}\n")
    r.write("\n===== URLS (含 wps/kingsoft/aigc/copilot/ai) =====\n")
    for u in sorted(urls):
        if re.search(r"wps|kingsoft|aigc|copilot|\bai\b|llm|chat|model", u, re.I):
            r.write(u + "\n")
    r.write("\n===== API PATHS =====\n")
    for pp in sorted(paths):
        r.write(pp + "\n")
    r.write("\n===== AUTH KEYWORD FILES =====\n")
    af = {}
    for p, k in auth_hits:
        af.setdefault(p, set()).add(k)
    for p in sorted(af):
        r.write(f"{p}\t{sorted(af[p])}\n")

print("hosts:", len(hosts), " urls:", len(urls), " paths:", len(paths), " authFiles:", len(set(x[0] for x in auth_hits)))
print("\n--- top hosts ---")
for h, c in hosts.most_common(25):
    print(c, h)
