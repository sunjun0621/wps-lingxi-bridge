# -*- coding: utf-8 -*-
"""把灵犀 Bridge 作为 Custom 供应商写入 WorkBuddy 的 models.json。
逻辑参照 OW-Bridge 的 src/sync.js（合并、去旧 owner、备份、原子写），
并按 OW-Bridge src/reasoning.js 的逻辑生成 reasoning 元数据，
使导入 WorkBuddy 的模型自带思考强度（低/高/Max）选择。"""
import os, json, time, glob, shutil

OWNER = "lingxi-bridge-v1"

def default_config_dir():
    # 环境变量覆盖（与 WorkBuddy 约定一致）
    d = os.environ.get("WORKBUDDY_CONFIG_DIR")
    if d: return d
    folder = os.environ.get("WORKBUDDY_DATA_FOLDER_NAME", ".workbuddy")
    home = os.environ.get("USERPROFILE") or os.path.expanduser("~")
    return os.path.join(home, folder)

def candidate_paths():
    paths = [os.path.join(default_config_dir(), "models.json")]
    # 常见其它位置（仅用于“查找”，不强制）
    appdata = os.environ.get("APPDATA")
    if appdata:
        paths += [os.path.join(appdata, "WorkBuddy", "models.json"),
                  os.path.join(appdata, "workbuddy", "models.json")]
    home = os.environ.get("USERPROFILE") or os.path.expanduser("~")
    paths += [os.path.join(home, ".workbuddy", "models.json")]
    # 去重保序
    seen, out = set(), []
    for p in paths:
        if p not in seen: seen.add(p); out.append(p)
    return out

def find_config():
    """返回 (path, exists)。优先返回已存在的，否则返回默认建议路径。"""
    for p in candidate_paths():
        if os.path.exists(p): return p, True
    return candidate_paths()[0], False

def read_document(path):
    if not os.path.exists(path): return []
    raw = open(path, "r", encoding="utf-8").read()
    if not raw.strip(): return []
    return json.loads(raw)

def _list_of(document):
    if isinstance(document, list): return document
    if isinstance(document, dict) and isinstance(document.get("models"), list):
        return document["models"]
    return None

def reasoning_meta(efforts):
    """按 OW-Bridge workBuddyReasoning 的逻辑生成思考强度元数据。

    efforts：该模型支持的档位列表（灵犀为 ['low','high','max']）；
             空列表 = 自适应推理（无手动档位，如 MiMo / MiniMax）。
    返回空 dict 表示不写 reasoning 字段（未知能力，保持旧行为）。
    """
    if efforts is None:
        return {}
    if not efforts:
        # 自适应推理模型：推理始终开启但无档位可调（对应 OW-Bridge 无 variants 分支）
        return {
            "supportsReasoning": True,
            "onlyReasoning": True,
            "reasoning": {"supportedEfforts": [], "canDisableThinking": False},
        }
    enabled = [e for e in efforts if e != "none"]
    if not enabled:
        return {}
    # OW-Bridge 默认档优先中间档 medium；灵犀三档的中间档是 high，其次取第一个
    default = "high" if "high" in enabled else enabled[0]
    return {
        "supportsReasoning": True,
        "onlyReasoning": "none" not in efforts,
        "reasoning": {
            "supportedEfforts": list(efforts),
            "defaultEffort": default,
            "canDisableThinking": "none" in efforts,
        },
    }


def build_entries(selected, endpoint, token, model_names, model_efforts=None):
    entries = []
    for key in selected:
        display = model_names.get(key, key)
        entry = {
            "id": key,
            "name": f"{display} · 灵犀",
            "vendor": "Custom",
            "url": endpoint,
            "apiKey": token,
            "supportsToolCall": False,   # 本反代先做纯对话，工具/图片后续增强
            "supportsImages": False,
            "buddyBridgeOwner": OWNER,
        }
        if model_efforts is not None:
            entry.update(reasoning_meta(model_efforts.get(key)))
        entries.append(entry)
    return entries

def merge_models(document, entries, force=False):
    lst = _list_of(document)
    if lst is None:
        raise ValueError("无法识别的 models.json 结构，已保持不变")
    own_out = [m for m in lst if m.get("buddyBridgeOwner") != OWNER]
    new_ids = {e["id"] for e in entries}
    if force:
        # 连同 id 的第三方旧条目一并替换（写入前整体已有 .bak 备份）
        kept = [m for m in own_out if m.get("id") not in new_ids]
        add = list(entries)
    else:
        kept = own_out
        conflicts = {m.get("id") for m in kept}
        add = [e for e in entries if e["id"] not in conflicts]
    combined = kept + add
    if isinstance(document, list):
        return combined
    updated = dict(document); updated["models"] = combined
    if isinstance(document.get("availableModels"), list):
        old_ids = {m.get("id") for m in lst if m.get("buddyBridgeOwner") == OWNER}
        am = [i for i in document["availableModels"] if i not in old_ids]
        updated["availableModels"] = list(dict.fromkeys(am + [e["id"] for e in add]))
    return updated

def write_config(path, merged, document):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    backup = None
    if os.path.exists(path):
        backup = f"{path}.lingxi-bridge-{int(time.time())}.bak"
        shutil.copy2(path, backup)
    tmp = f"{path}.tmp.{int(time.time()*1000)}"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2); f.write("\n")
    os.replace(tmp, path)
    return backup

def import_models(selected, endpoint, token, model_names, model_efforts=None, path=None, force=False):
    if path is None:
        path, _ = find_config()
    document = read_document(path)
    entries = build_entries(selected, endpoint, token, model_names, model_efforts)
    merged = merge_models(document, entries, force=force)
    final_list = _list_of(merged)
    count = len([m for m in final_list if m.get("buddyBridgeOwner") == OWNER])
    changed = json.dumps(merged, ensure_ascii=False) != json.dumps(document, ensure_ascii=False)
    backup = None
    if changed:
        backup = write_config(path, merged, document)
    return {"path": path, "count": count, "changed": changed, "backup": backup}

def imported_status(path=None):
    if path is None:
        path, exists = find_config()
    else:
        exists = os.path.exists(path)
    ids = []
    if exists:
        try:
            doc = read_document(path)
            lst = _list_of(doc) or []
            ids = [m.get("id") for m in lst if m.get("buddyBridgeOwner") == OWNER]
        except Exception: pass
    return {"path": path, "exists": exists, "imported": ids}
