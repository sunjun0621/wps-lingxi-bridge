# -*- coding: utf-8 -*-
"""思考强度元数据注入链路离线测试（纯内存 + 临时副本，不触碰真实 models.json）。
用系统 Python 运行：python test_workbuddy_strength.py"""
import os, sys, json, tempfile
sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
import workbuddy_sync as ws

fails = []
def check(name, cond, detail=""):
    print(("PASS" if cond else "FAIL"), name, ("| " + str(detail)) if (not cond and detail != "") else "")
    if not cond:
        fails.append(name)

# ---------- 1. reasoning_meta 分支 ----------
m = ws.reasoning_meta(["low", "high", "max"])
check("有档位·supportsReasoning", m.get("supportsReasoning") is True)
check("有档位·onlyReasoning", m.get("onlyReasoning") is True)
check("有档位·supportedEfforts", m["reasoning"]["supportedEfforts"] == ["low", "high", "max"], m)
check("有档位·defaultEffort=high", m["reasoning"]["defaultEffort"] == "high")
check("有档位·canDisableThinking=False", m["reasoning"]["canDisableThinking"] is False)

m = ws.reasoning_meta([])
check("自适应·supportedEfforts=[]", m.get("reasoning", {}).get("supportedEfforts") == [])
check("自适应·onlyReasoning=True", m.get("onlyReasoning") is True)
check("未知(None)·空 dict", ws.reasoning_meta(None) == {})

# ---------- 2. build_entries ----------
names = {"deepseek-v4-pro-0813": "DeepSeek V4 Pro", "mimo-v2.6-pro": "Xiaomi MiMo-V2.6 Pro"}
effs = {"deepseek-v4-pro-0813": ["low", "high", "max"], "mimo-v2.6-pro": []}
entries = ws.build_entries(["deepseek-v4-pro-0813", "mimo-v2.6-pro"],
                           "http://127.0.0.1:8799/v1/chat/completions", "lingxi-bridge", names, effs)
e0, e1 = entries
check("条目·id", e0["id"] == "deepseek-v4-pro-0813")
check("条目·name", e0["name"] == "DeepSeek V4 Pro · 灵犀")
check("条目·reasoning 字段齐全", all(k in e0 for k in ("supportsReasoning", "onlyReasoning", "reasoning")))
check("条目·自适应模型", e1["reasoning"]["supportedEfforts"] == [])
check("条目·保持键序(可读)", list(e0.keys())[:6] == ["id", "name", "vendor", "url", "apiKey", "supportsToolCall"], list(e0.keys()))

entries_old = ws.build_entries(["deepseek-v4-pro-0813"], "u", "t", names)
check("旧调用(不传 effort)·保持旧行为", "supportsReasoning" not in entries_old[0])

# ---------- 3. merge_models ----------
doc = [
    {"id": "glm-5.3-flash", "name": "glm-5.3-flash", "vendor": "Custom"},  # 用户自己的
    {"id": "deepseek-v4.1-flash", "name": "DeepSeek V4.1 Flash · 灵犀", "buddyBridgeOwner": "lingxi-bridge-v1"},  # 旧 OWNER
]
merged = ws.merge_models(doc, [e0, e1])
ids = [m["id"] for m in merged]
check("合并·保留用户条目", "glm-5.3-flash" in ids)
check("合并·旧 OWNER 被替换", "deepseek-v4.1-flash" not in ids)
check("合并·新条目已加", "deepseek-v4-pro-0813" in ids and "mimo-v2.6-pro" in ids)

doc2 = {"models": [{"id": "x", "buddyBridgeOwner": "lingxi-bridge-v1"}], "availableModels": ["x", "y"]}
merged2 = ws.merge_models(doc2, [e0])
check("dict·availableModels 去旧增新", set(merged2["availableModels"]) == {"y", "deepseek-v4-pro-0813"}, merged2.get("availableModels"))

# ---------- 4. import_models 端到端（临时副本） ----------
with tempfile.TemporaryDirectory() as td:
    tp = os.path.join(td, "models.json")
    json.dump(doc, open(tp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    r = ws.import_models(["deepseek-v4-pro-0813", "mimo-v2.6-pro"],
                         "http://x/v1/chat/completions", "tok", names, effs, path=tp)
    saved = json.load(open(tp, encoding="utf-8"))
    tr = [m for m in saved if m.get("buddyBridgeOwner") == "lingxi-bridge-v1"]
    check("import·changed=True", r["changed"] is True)
    check("import·备份生成", bool(r["backup"]) and os.path.exists(r["backup"]))
    check("import·条目数=2", r["count"] == 2 and len(tr) == 2)
    check("import·磁盘含 reasoning", tr[0]["reasoning"]["supportedEfforts"] == ["low", "high", "max"])
    check("import·幂等(重复导入不报错)", ws.import_models(["deepseek-v4-pro-0813", "mimo-v2.6-pro"],
          "http://x/v1/chat/completions", "tok", names, effs, path=tp)["count"] == 2)

# ---------- 5. gateway resolve_effort ----------
import bridge_gateway as bg
check("effort·有档位透传 high", bg.resolve_effort("deepseek-v4-pro-0813", {"reasoning_effort": "high"}) == "high")
check("effort·reasoning.effort 格式", bg.resolve_effort("deepseek-v4-pro-0813", {"reasoning": {"effort": "max"}}) == "max")
check("effort·灵犀无 medium→忽略", bg.resolve_effort("deepseek-v4-pro-0813", {"reasoning_effort": "medium"}) is None)
check("effort·无字段→None", bg.resolve_effort("deepseek-v4-pro-0813", {}) is None)
check("effort·自适应模型忽略", bg.resolve_effort("mimo-v2.6-pro", {"reasoning_effort": "high"}) is None)
check("effort·未知档位忽略", bg.resolve_effort("deepseek-v4-pro-0813", {"reasoning_effort": "bogus"}) is None)
check("effort·大小写容错", bg.resolve_effort("deepseek-v4-pro-0813", {"reasoning_effort": "HIGH"}) == "high")
check("effort·none 忽略", bg.resolve_effort("deepseek-v4-pro-0813", {"reasoning_effort": "none"}) is None)

print()
print("FAILS:", fails if fails else "无 —— 全部通过")
sys.exit(1 if fails else 0)
