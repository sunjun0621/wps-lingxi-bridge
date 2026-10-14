# -*- coding: utf-8 -*-
# 在指定 JS 文件中按关键词提取上下文窗口（压缩成单行的 bundle 也能看），避免整行刷屏
import sys, os, re

def main():
    path = sys.argv[1]
    kws = sys.argv[2:]
    txt = open(path, "r", encoding="utf-8", errors="ignore").read()
    print("file:", path, " len:", len(txt))
    for kw in kws:
        rx = re.compile(re.escape(kw), re.I)
        seen = set()
        out = []
        for m in rx.finditer(txt):
            s = max(0, m.start() - 90)
            e = min(len(txt), m.end() + 110)
            frag = txt[s:e].replace("\n", " ")
            key = frag[60:180]
            if key in seen:
                continue
            seen.add(key)
            out.append(frag)
            if len(out) >= 8:
                break
        print("\n########## kw=%r  hits_shown=%d ##########" % (kw, len(out)))
        for i, fr in enumerate(out):
            print(f"[{i}] …{fr}…")

if __name__ == "__main__":
    main()
