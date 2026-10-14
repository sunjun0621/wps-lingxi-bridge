# -*- coding: utf-8 -*-
"""把灵犀 Bridge 写入 ZCode 的自定义供应商配置（~/.zcode/v2/provider_config.json）。

写入逻辑对照 workbuddy2api-hub 的 wb_agents._apply_zcode（照设计不抄代码）：
- schemaVersion 1：config.providerOrder（显示顺序）+ config.providerConfigRules.providerRules[]；
- 以稳定 providerId 定位条目：存在则深合并更新，不存在才追加（幂等，重复导入不堆叠）；
- 其余供应商条目与顺序原样保留；
- 写前字节级备份（保留最近 10 份），tmp + os.replace 原子落盘；
- ZCode 运行时会重写该文件：导入前检测进程，运行中给出明确提示（需完全重启 ZCode 生效）。
"""
import os, json, time, shutil, glob

PROVIDER_ID = "wps-lingxi"
PROVIDER_NAME = "WPS 灵犀 Bridge"
BACKUP_KEEP = 10


def config_path():
    return os.path.join(os.environ.get("USERPROFILE") or os.path.expanduser("~"),
                        ".zcode", "v2", "provider_config.json")


def zcode_running():
    """ZCode 桌面端是否在运行（运行中写配置会被其下一次保存覆盖）。"""
    try:
        import subprocess
        r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq ZCode.exe", "/FO", "CSV", "/NH"],
                           capture_output=True, text=True, encoding="gbk", errors="replace",
                           timeout=8,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return "ZCode.exe" in (r.stdout or "")
    except Exception:
        return False


def _load(path):
    if not os.path.exists(path):
        return None
    text = open(path, encoding="utf-8").read()
    if not text.strip():
        return None
    return json.loads(text)   # 解析失败直接抛,由调用方转为 4xx 提示,绝不半写


def _rule_base_url(port):
    return f"http://127.0.0.1:{port}/v1"


def build_rule(port, token, model_keys, model_efforts=None):
    """构造本 Bridge 的 provider rule。model_keys 为勾选的模型 id 列表。"""
    rule = {
        "providerId": PROVIDER_ID,
        "providerName": PROVIDER_NAME,
        "enabled": True,
        "config": {
            "group": "standard-personal",
            "access": {"type": "api-key", "apiKey": token},
            "api": {"type": "openai-chat-completions",
                    "baseUrl": _rule_base_url(port)},
        },
    }
    if model_keys:
        rule["config"]["personalModelIds"] = list(model_keys)
        rule["config"]["modelOrder"] = list(model_keys)
    return rule


def _deep_merge(base, patch):
    """递归合并 patch 到 base,patch 之外的兄弟键保留;返回新 dict。"""
    out = dict(base or {})
    for k, v in (patch or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def merge_document(data, rule):
    """把 rule 合并进文档:同 providerId 更新,否则追加;providerOrder 补位。"""
    if not isinstance(data, dict):
        data = {}
    config = data.get("config") if isinstance(data.get("config"), dict) else {}
    data["schemaVersion"] = data.get("schemaVersion", 1)
    if not isinstance(config.get("providerOrder"), list):
        config["providerOrder"] = []
    holder = config.get("providerConfigRules")
    if not (isinstance(holder, dict) and isinstance(holder.get("providerRules"), list)):
        holder = {"providerRules": []}
    rules = holder["providerRules"]

    replaced = False
    for i, existing in enumerate(rules):
        if isinstance(existing, dict) and existing.get("providerId") == PROVIDER_ID:
            rules[i] = _deep_merge(existing, rule)
            replaced = True
            break
    if not replaced:
        rules.append(rule)
    config["providerConfigRules"] = holder

    if PROVIDER_ID not in config["providerOrder"]:
        config["providerOrder"].append(PROVIDER_ID)
    data["config"] = config
    return data


def current_status(path=None):
    """读取现状:provider 是否已配置、指向、模型数。"""
    path = path or config_path()
    out = {"path": path, "exists": os.path.exists(path),
           "configured": False, "models": [], "baseUrl": None, "parse_error": None}
    try:
        data = _load(path)
    except Exception as e:
        out["parse_error"] = str(e)[:120]
        return out
    if not data:
        return out
    config = data.get("config") if isinstance(data.get("config"), dict) else {}
    holder = config.get("providerConfigRules")
    rules = holder.get("providerRules") if isinstance(holder, dict) else []
    for r in rules or []:
        if isinstance(r, dict) and r.get("providerId") == PROVIDER_ID:
            c = r.get("config") or {}
            out.update(configured=True,
                       models=list(c.get("personalModelIds") or []),
                       baseUrl=(c.get("api") or {}).get("baseUrl"),
                       enabled=r.get("enabled", True))
            break
    return out


def _backup(path):
    stamp = time.strftime("%Y%m%d-%H%M%S")
    directory = os.path.join(os.path.dirname(path), "provider-config-backups")
    os.makedirs(directory, exist_ok=True)
    target = os.path.join(directory, f"{stamp}-{os.path.basename(path)}")
    seq = 1
    while os.path.exists(target):
        target = os.path.join(directory, f"{stamp}-{seq}-{os.path.basename(path)}")
        seq += 1
    shutil.copy2(path, target)
    # 只保留最近 BACKUP_KEEP 份
    olds = sorted(glob.glob(os.path.join(directory, f"*-{os.path.basename(path)}")))
    for old in olds[:-BACKUP_KEEP]:
        try:
            os.remove(old)
        except OSError:
            pass
    return target


def import_to_zcode(port, token, model_keys, path=None):
    """勾选的模型写入 ZCode provider。返回 {changed, backup, path, zcode_running, hint}。"""
    path = path or config_path()
    running = zcode_running()
    data = _load(path)
    if data is None:
        # 首次:按 live 3.x 档案的外壳结构起步(与 workbuddy2api-hub 同款兜底)
        data = {"schemaVersion": 1,
                "config": {"providerOrder": [],
                           "providerConfigRules": {"providerRules": []}}}
    rule = build_rule(port, token, model_keys)
    before = json.dumps(data, ensure_ascii=False, sort_keys=True)   # merge 会原地改引用,先快照
    merged = merge_document(data, rule)
    changed = json.dumps(merged, ensure_ascii=False, sort_keys=True) != before
    backup = None
    if changed:
        os.makedirs(os.path.dirname(path), exist_ok=True)   # 首次写入时父目录可能不存在
        if os.path.exists(path):
            backup = _backup(path)
        tmp = f"{path}.tmp.{int(time.time() * 1000)}"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(merged, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, path)
    hint = ("已写入,需完全重启 ZCode 后生效(模型分组不会自动跟随,手动勾选或等待刷新)"
            if running else
            "已写入,启动/重启 ZCode 后生效")
    return {"changed": changed, "backup": backup, "path": path,
            "zcode_running": running, "hint": hint,
            "models": list(model_keys)}
