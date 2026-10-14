# -*- coding: utf-8 -*-
# 提取 bundle 中所有 /api 开头的路径字符串，去重排序，定位模型列表等接口
import re, sys
for p in sys.argv[1:]:
    t = open(p, encoding="utf-8", errors="ignore").read()
    ps = sorted(set(re.findall(r"""["'`](/[a-zA-Z0-9_\-./{}:]*api[a-zA-Z0-9_\-./{}:]*)["'`]""", t, re.I)))
    print("\n#### ", p, " 共", len(ps))
    for x in ps:
        print(x)
