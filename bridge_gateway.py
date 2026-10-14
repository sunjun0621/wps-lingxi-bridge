# -*- coding: utf-8 -*-
"""灵犀 Bridge：把 WPS 灵犀订阅内的多模型（DeepSeek/Qwen/GLM/Kimi/MiMo...）
通过本地 app-server(lingxi.exe) 暴露为 OpenAI 兼容接口，供 WorkBuddy / dsh 使用。

能力：OpenAI 兼容对话（含思维等级 low/high/max）、可视化控制台、
      一键测试全部模型、WPS 账号扫码登录（自动更新 wps_sid）。

启动：python bridge_gateway.py   （默认仅本机 127.0.0.1:8799）

配置（三级：环境变量 > bridge-runtime/gateway.json > 内置默认）：
  LINGXI_BRIDGE_HOST / gateway.json:host       监听地址（默认 127.0.0.1；局域网访问改 0.0.0.0）
  LINGXI_BRIDGE_PORT / gateway.json:port       端口（默认 8799）
  LINGXI_BRIDGE_TOKEN / gateway.json:token     访问令牌（默认 lingxi-bridge）
  LINGXI_BRIDGE_TIMEOUT / gateway.json:timeout 对话超时秒（默认 240）
  LINGXI_BRIDGE_TEST_TIMEOUT                   一键测试单模型超时秒（默认 90）
  LINGXI_BRIDGE_LOG / gateway.json:log_enabled 日志落盘开关（默认 true）
  LINGXI_BRIDGE_LOG_MAX_MB / gateway.json:log_max_mb  日志轮转阈值 MB（默认 5）
  LINGXI_SID          wps_sid（不设则按 current_sid.txt / cookies_decrypted.json 读取）
  LINGXI_BRIDGE_EXE   app-server 可执行文件路径（覆盖默认 appserver/ 布局；测试注入用）
"""
import os, sys, json, time, uuid, threading, queue, asyncio, socket, subprocess, re, importlib.util
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)   # 行缓冲：日志/提示即时可见

# ---------------- 依赖自检（缺包给中文指引，替代裸 traceback） ----------------
# 核心依赖缺失 → 阻断并给清华源安装命令；可选依赖缺失 → 一行提示不阻断
# （websocket-client 仅研究脚本用，不参与启动自检，手动全量检查用 check_deps.py）
_CORE_DEPS = (("fastapi", "fastapi"), ("uvicorn", "uvicorn"), ("requests", "requests"))
_OPT_DEPS = (("win32crypt", "pywin32", "从灵犀客户端刷新登录 Cookie"),
             ("cryptography", "cryptography", "解密 Cookie 数据"))
_PIP_MIRROR = "https://pypi.tuna.tsinghua.edu.cn/simple"


def _dep_check():
    missing_core = [pip for mod, pip in _CORE_DEPS if importlib.util.find_spec(mod) is None]
    if missing_core:
        print("=" * 64)
        print("[错误] 缺少运行必需的 Python 包：" + "、".join(missing_core))
        print("请复制下一行到命令行执行（清华源，速度快）：")
        print(f'  "{sys.executable}" -m pip install -i {_PIP_MIRROR} ' + " ".join(missing_core))
        print("=" * 64)
        sys.exit(1)
    missing_opt = [(pip, why) for mod, pip, why in _OPT_DEPS
                   if importlib.util.find_spec(mod) is None]
    if missing_opt:
        print("[提示] 可选依赖缺失：" + "；".join(f"{pip}（{why}）" for pip, why in missing_opt))
        print(f'       需要时安装：「"{sys.executable}" -m pip install -i {_PIP_MIRROR} '
              + " ".join(pip for pip, _ in missing_opt) + "」")


_dep_check()

import requests
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse, HTMLResponse
from urllib.parse import urlparse, parse_qs
from appserver_client import LingxiAppServer, AppServerError
import workbuddy_sync, qr_login, zcode_sync

ROOT = os.path.dirname(os.path.abspath(__file__))
# 运行目录可覆盖（配置/日志/状态都放这里）；隔离测试用 LINGXI_BRIDGE_RUNTIME_DIR 指向临时目录
RT = os.environ.get("LINGXI_BRIDGE_RUNTIME_DIR") or os.path.join(ROOT, "bridge-runtime")
CONFIG_FILE = os.path.join(RT, "gateway.json")
EXE = os.environ.get("LINGXI_BRIDGE_EXE") or os.path.join(
    ROOT, "appserver", "app-server", "service", "lingxi.exe")
SID_FILE = os.path.join(ROOT, "current_sid.txt")
LOG_DIR = os.path.join(RT, "logs")
LOG_FILE = os.path.join(LOG_DIR, "bridge.log")
STATE_DIR = os.path.join(RT, "state")
RESULTS_FILE = os.path.join(STATE_DIR, "model_results.json")


# ---------------- 三级配置：环境变量 > gateway.json > 默认 ----------------
def _load_gateway_config():
    if not os.path.exists(CONFIG_FILE):
        return {}
    try:
        d = json.load(open(CONFIG_FILE, encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception as e:
        print(f"[配置] gateway.json 读取失败，忽略该文件：{e}")
        return {}


_cfg_file = _load_gateway_config()
CONFIG_SOURCES = {}   # 每个配置项最终生效来源（启动时打印）


def _bool_of(v):
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in ("1", "true", "yes", "on")


def cfg(key, env_name, default):
    """单一入口：返回 (值, 来源)。env > 文件 > 默认；坏值自动回落并提示。"""
    if isinstance(default, bool):
        cast = _bool_of
    elif isinstance(default, float):
        cast = float
    elif isinstance(default, int):
        cast = int
    else:
        cast = str
    for val, src in ((os.environ.get(env_name), env_name),
                     (_cfg_file.get(key), "gateway.json")):
        if val is None or val == "":
            continue
        try:
            return cast(val), src
        except (TypeError, ValueError):
            print(f"[配置] {key} 值 {val!r}（来自 {src}）无效，继续回落")
    return default, "默认"


PORT, _src_port = cfg("port", "LINGXI_BRIDGE_PORT", 8799)
HOST, _src_host = cfg("host", "LINGXI_BRIDGE_HOST", "127.0.0.1")
TOKEN, _src_token = cfg("token", "LINGXI_BRIDGE_TOKEN", "lingxi-bridge")
TIMEOUT, _src_timeout = cfg("timeout", "LINGXI_BRIDGE_TIMEOUT", 240)
TEST_TIMEOUT, _src_test_timeout = cfg("test_timeout", "LINGXI_BRIDGE_TEST_TIMEOUT", 90)
LOG_ENABLED, _src_log = cfg("log_enabled", "LINGXI_BRIDGE_LOG", True)
LOG_MAX_MB, _src_log_max = cfg("log_max_mb", "LINGXI_BRIDGE_LOG_MAX_MB", 5.0)
REQLOG_ENABLED, _src_reqlog = cfg("reqlog_enabled", "LINGXI_BRIDGE_REQLOG", True)
REQLOG_MAX_MB, _src_reqlog_max = cfg("reqlog_max_mb", "LINGXI_BRIDGE_REQLOG_MAX_MB", 2.0)
REQLOG_KEEP_DAYS, _src_reqlog_days = cfg("reqlog_keep_days", "LINGXI_BRIDGE_REQLOG_KEEP_DAYS", 30)
CONFIG_SOURCES.update(port=_src_port, host=_src_host, token=_src_token,
                      timeout=_src_timeout, test_timeout=_src_test_timeout,
                      log_enabled=_src_log, log_max_mb=_src_log_max,
                      reqlog_enabled=_src_reqlog, reqlog_max_mb=_src_reqlog_max,
                      reqlog_keep_days=_src_reqlog_days)
LOG_MAX_BYTES = int(LOG_MAX_MB * 1024 * 1024)          # 轮转阈值（MB → 字节），保留 1 份 .1
REQLOG_FILE = os.path.join(LOG_DIR, "reqlog.jsonl")    # 结构化请求日志（一行一请求）
REQLOG_MAX_BYTES = int(REQLOG_MAX_MB * 1024 * 1024)
VALID_EFFORTS = ("low", "high", "max")
START_TIME = time.time()

# 模型清单：优先 bridge-runtime/models.json（可选），缺失/损坏时回落内置清单。
# 热重载：models.json / plans.json 的 mtime 变化时自动重读；另有 POST /admin/reload-models 手动触发。
MODELS_FILE = os.path.join(RT, "models.json")
DEFAULT_MODELS = [
    ("auto", "自动"),
    ("deepseek-v4-flash-0731", "DeepSeek V4 Flash"),
    ("deepseek-v4.1-flash", "DeepSeek V4.1 Flash"),
    ("deepseek-v4-pro-0813", "DeepSeek V4 Pro"),
    ("qwen3.8_flash", "Qwen3.8-Flash"),
    ("qwen3.8_max", "Qwen3.8-Max"),
    ("mimo-v2.6-pro", "Xiaomi MiMo-V2.6 Pro"),
    ("GLM-5.3-Flash", "GLM-5.3-Flash"),
    ("GLM-5.3", "GLM-5.3"),
    ("minimax_m3", "MiniMax-M3"),
    ("doubao_seed_2_1_pro_260628", "Doubao-Seed-2.1 Pro"),
    ("kimi-k3", "Kimi-K3"),
]
_models_lock = threading.Lock()
_models_cache = {"mtime": "未加载"}


def _load_plans_efforts():
    """从 plans.json 读取每模型支持的思维等级（灵犀云端套餐缓存）。"""
    eff = {}
    p = os.path.join(ROOT, "plans.json")
    if os.path.exists(p):
        try:
            d = json.load(open(p, encoding="utf-8"))
            ms = (d.get("data") or d).get("models", [])
            for m in ms:
                e = m.get("reasoning_efforts")
                if isinstance(e, list):
                    eff[m["key"]] = [x for x in e if x in VALID_EFFORTS]
        except Exception:
            pass
    return eff


def _load_models_file():
    """读 models.json（可选）。支持 [{"key","name","efforts"?}] 或 [["key","name"],...]。
    文件不存在返回 None；损坏时提示并返回 None（回落内置）。"""
    if not os.path.exists(MODELS_FILE):
        return None
    try:
        d = json.load(open(MODELS_FILE, encoding="utf-8"))
        items = d.get("models") if isinstance(d, dict) else d
        out = []
        for m in items or []:
            if isinstance(m, dict) and m.get("key"):
                eff = m.get("efforts")
                eff = [e for e in eff if e in VALID_EFFORTS] if isinstance(eff, list) else None
                out.append((str(m["key"]), str(m.get("name") or m["key"]), eff))
            elif isinstance(m, (list, tuple)) and len(m) >= 2:
                out.append((str(m[0]), str(m[1]), None))
        if out:
            return out
        print(f"[模型] {MODELS_FILE} 中没有有效模型条目，改用内置清单")
    except Exception as e:
        print(f"[模型] {MODELS_FILE} 读取失败，改用内置清单：{e}")
    return None


def load_models_and_efforts():
    """返回 ((key,name) 列表, 档位映射, 清单来源)。档位优先级：models.json > plans.json > 空。"""
    entries = _load_models_file()
    source = "models.json" if entries else "内置"
    if not entries:
        entries = [(k, n, None) for k, n in DEFAULT_MODELS]
    plans_eff = _load_plans_efforts()
    models, efforts = [], {}
    for k, n, eff in entries:
        models.append((k, n))
        efforts[k] = eff if eff is not None else plans_eff.get(k, [])
    return models, efforts, source


MODELS, MODEL_EFFORTS, MODELS_SOURCE = load_models_and_efforts()
MODEL_KEYS = {k for k, _ in MODELS}


def _models_mtime():
    try:
        return tuple(os.path.getmtime(p) if os.path.exists(p) else None
                     for p in (MODELS_FILE, os.path.join(ROOT, "plans.json")))
    except OSError:
        return None


_models_cache["mtime"] = _models_mtime()   # 首帧完成，进入 mtime 对比模式


def refresh_models(force=False):
    """热重载：models.json / plans.json 有变化才重读（force=True 强制）。返回是否刷新。"""
    global MODELS, MODEL_KEYS, MODEL_EFFORTS, MODELS_SOURCE
    mt = _models_mtime()
    with _models_lock:
        if not force and mt == _models_cache["mtime"]:
            return False
        MODELS, MODEL_EFFORTS, MODELS_SOURCE = load_models_and_efforts()
        MODEL_KEYS = {k for k, _ in MODELS}
        _models_cache["mtime"] = mt
    print(f"[模型] 清单已重载（{MODELS_SOURCE}，{len(MODELS)} 个模型）")
    return True


def save_sid(sid):
    open(SID_FILE, "w", encoding="utf-8").write(sid.strip())


def load_sid():
    sid = os.environ.get("LINGXI_SID")
    if sid:
        return sid
    if os.path.exists(SID_FILE):
        s = open(SID_FILE, encoding="utf-8").read().strip()
        if s:
            return s
    cand = os.path.join(ROOT, "cookies_decrypted.json")
    if os.path.exists(cand):
        try:
            data = json.load(open(cand, encoding="utf-8"))
            if isinstance(data, dict):
                return data.get("wps_sid")
            if isinstance(data, list):
                for c in data:
                    if isinstance(c, dict) and c.get("name") == "wps_sid":
                        return c.get("value")
        except Exception:
            pass
    return None


def mask_sid(sid):
    if not sid:
        return None
    return sid[:6] + "****" + sid[-4:] if len(sid) > 12 else "****"


# ---------------- 日志落盘（轮转阈值可配，保留 1 份；log_enabled=false 时仅输出到控制台） ----------------
_log_lock = threading.Lock()


def log_line(msg):
    """关键事件同时打到 stdout 与 bridge-runtime/logs/bridge.log；超阈值轮转。"""
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{stamp}] {msg}"
    print(line)
    if not LOG_ENABLED:
        return
    try:
        with _log_lock:
            os.makedirs(LOG_DIR, exist_ok=True)
            if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > LOG_MAX_BYTES:
                rotated = LOG_FILE + ".1"
                if os.path.exists(rotated):
                    os.remove(rotated)
                os.replace(LOG_FILE, rotated)
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(line + "\n")
    except Exception:
        pass   # 日志落盘失败不影响服务


# ---------------- 结构化请求日志（reqlog JSONL：一行一请求，只记元数据不记正文） ----------------
_reqlog_lock = threading.Lock()


def _reqlog_line(rec):
    """把活动记录整理为一行 JSON（元数据）：rid/模型/流式/阶段/耗时/首字/字数/错误分类。"""
    return json.dumps({
        "ts": datetime.fromtimestamp(rec["start"]).strftime("%Y-%m-%d %H:%M:%S"),
        "rid": rec["id"], "model": rec["model"], "effort": rec.get("effort") or None,
        "stream": rec.get("stream", False), "stage": rec.get("stage"),
        "elapsed": rec.get("elapsed"), "ttfb": rec.get("first_byte"),
        "chars": rec.get("chars"), "kind": rec.get("kind"),
        "error": (rec.get("error") or "")[:160] or None,
    }, ensure_ascii=False)


def reqlog_write(rec):
    """请求终态落盘一行 JSONL；超阈值轮转 .1；按保留天数清理。失败静默（不影响服务）。"""
    if not REQLOG_ENABLED:
        return
    try:
        with _reqlog_lock:
            os.makedirs(LOG_DIR, exist_ok=True)
            if os.path.exists(REQLOG_FILE) and os.path.getsize(REQLOG_FILE) > REQLOG_MAX_BYTES:
                rotated = REQLOG_FILE + ".1"
                if os.path.exists(rotated):
                    os.remove(rotated)
                os.replace(REQLOG_FILE, rotated)
            with open(REQLOG_FILE, "a", encoding="utf-8") as f:
                f.write(_reqlog_line(rec) + "\n")
    except Exception:
        pass


def reqlog_cleanup():
    """启动时按保留天数清理：文件/轮转文件的 mtime 超期则删除（主文件仍会继续追加）。"""
    if not REQLOG_ENABLED:
        return
    try:
        cutoff = time.time() - REQLOG_KEEP_DAYS * 86400
        for p in (REQLOG_FILE, REQLOG_FILE + ".1"):
            if os.path.exists(p) and os.path.getmtime(p) < cutoff:
                os.remove(p)
    except Exception:
        pass


# ---------------- 错误分类（对齐 workbuddy2api 的 Classify 优先级链） ----------------
def classify_error(e) -> dict:
    """把异常映射为 {kind, hint}：kind 用于面板图标，hint 是给用户的中文指引。"""
    msg = str(e) if e else ""
    low = msg.lower()
    if isinstance(e, AppServerError) and e.transient:
        return {"kind": "disconnected", "hint": "灵犀连接已断开，正在自动恢复；若持续失败请重启网关"}
    if "wps_sid" in low or "登录" in msg or "sid" in low and "未找到" in low:
        return {"kind": "auth", "hint": "登录已失效：请在控制台扫码重新登录"}
    if "超时" in msg or "timeout" in low:
        return {"kind": "timeout", "hint": "请求超时：可降低思维等级或缩短输入后重试"}
    if "429" in msg or "限流" in msg or "rate" in low:
        return {"kind": "ratelimit", "hint": "触发限流：请稍等片刻再重试"}
    return {"kind": "server", "hint": "网关错误：" + (msg[:120] or "未知错误")}


# ---------------- 活动记录（P1-1：在途 + 最近 20 条，控制台 2s 轮询） ----------------
_activity = {"list": [], "lock": threading.Lock()}
ACTIVITY_MAX = 20
# 活动阶段：queued → upstream → content → done/failed（沿 workbuddy2api 请求日志格式）
_stage_labels = {"queued": "排队中", "upstream": "等待上游", "content": "已收到内容",
                 "done": "完成", "failed": "失败"}


def activity_start(model, effort, stream, rid=None):
    rid = rid or uuid.uuid4().hex[:12]   # 优先用中间件生成的 X-Request-Id，同 id 串联日志与响应头
    item = {"id": rid, "model": model, "effort": effort or "", "stream": stream,
            "stage": "queued", "stage_label": _stage_labels["queued"],
            "start": time.time(), "first_byte": None, "elapsed": None,
            "chars": 0, "error": None}
    with _activity["lock"]:
        _activity["list"].insert(0, item)
        del _activity["list"][ACTIVITY_MAX:]
    log_line(f"[req {rid}] start model={model} effort={effort or '-'} stream={stream}")
    return rid


def activity_stage(rid, stage, error=None, kind=None):
    """阶段推进；content 首次到达时记首字延迟。

    终态（done/failed）之后忽略回退写入：流式场景 worker 先落终态，
    消费者随后处理队列里残留的 text 帧时不能把终态改回 content。
    终态同时写一行 reqlog（结构化 JSONL）。
    """
    now = time.time()
    with _activity["lock"]:
        for it in _activity["list"]:
            if it["id"] != rid:
                continue
            if it["stage"] in ("done", "failed") and stage in ("queued", "upstream", "content"):
                break
            it["stage"] = stage
            it["stage_label"] = _stage_labels.get(stage, stage)
            if stage == "content" and it["first_byte"] is None:
                it["first_byte"] = round(now - it["start"], 2)
            if stage in ("done", "failed"):
                it["elapsed"] = round(now - it["start"], 2)
            if error:
                it["error"] = str(error)[:160]
            if kind:
                it["kind"] = kind
            break
    if stage in ("done", "failed"):
        rec = _get(rid)
        if rec:
            reqlog_write(rec)
            log_line(f"[req {rid}] {stage} in {rec.get('elapsed', '?')}s"
                     + (f" error={error}" if error else ""))


def activity_chars(rid, n):
    with _activity["lock"]:
        for it in _activity["list"]:
            if it["id"] == rid:
                it["chars"] += len(n)
                break


def _get(rid):
    with _activity["lock"]:
        for it in _activity["list"]:
            if it["id"] == rid:
                return dict(it)
    return None


def activity_snapshot():
    with _activity["lock"]:
        items = [dict(it) for it in _activity["list"]]
    active = sum(1 for it in items if it["stage"] in ("queued", "upstream", "content"))
    return {"active": active, "recent": items}


# ---------------- 结果持久化（P1-3：一键测试/单聊结果，刷新页面不丢） ----------------
def save_results(results: dict):
    """模型测试结果原子落盘（tmp + rename，防半截写）。"""
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        tmp = RESULTS_FILE + f".tmp.{int(time.time()*1000)}"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                       "results": results}, f, ensure_ascii=False, indent=1)
        os.replace(tmp, RESULTS_FILE)
    except Exception as e:
        log_line(f"[warn] 测试结果落盘失败：{e}")


def load_results() -> dict:
    try:
        d = json.load(open(RESULTS_FILE, encoding="utf-8"))
        if isinstance(d, dict) and isinstance(d.get("results"), dict):
            return d["results"]
    except Exception:
        pass
    return {}


# 长驻 app-server（懒启动 + 串行锁 + 进程级崩溃自愈）
_runtime = {"app": None, "lock": threading.Lock()}


def _lingxi_state():
    """lingxi 真实连接状态：idle（未启动，首请求自动拉起）/ running / dead。"""
    app = _runtime["app"]
    if app is None:
        return {"state": "idle", "alive": None, "pid": None}
    pid = app.proc.pid if app.proc is not None else None
    if app.is_alive():
        return {"state": "running", "alive": True, "pid": pid}
    return {"state": "dead", "alive": False, "pid": pid}


def get_app():
    """取用 app-server：取用前做存活检查（proc.poll + EOF），已死进程自动清理重建。"""
    with _runtime["lock"]:
        app = _runtime["app"]
        if app is not None and not app.is_alive():
            code = app.proc.poll() if app.proc else None
            log_line(f"[self-heal] 检测到 lingxi 进程已退出（exit={code}），自动重启")
            try:
                app.stop()
            except Exception:
                pass
            _runtime["app"] = None
        if _runtime["app"] is None:
            sid = load_sid()
            if not sid:
                raise AppServerError("未找到 wps_sid：请扫码登录或先运行提取 Cookie")
            app = LingxiAppServer(EXE, os.path.join(RT, "config.json"),
                                  os.path.join(RT, "state"), timeout=60)
            try:
                app.start()
                app.handshake()
                app.login(sid)
            except Exception:
                try:
                    app.stop()
                except Exception:
                    pass
                raise
            log_line(f"[lingxi] 已连接 app-server（pid={app.proc.pid}）")
            _runtime["app"] = app
        return _runtime["app"]


def reset_app():
    """停止当前 app-server，下次 get_app 用最新 sid 重启。"""
    with _runtime["lock"]:
        if _runtime["app"] is not None:
            try:
                _runtime["app"].stop()
            except Exception:
                pass
        _runtime["app"] = None


def do_run(model, agent_input, effort, timeout=240, on_text=None, on_reasoning=None,
           cancel_event=None):
    """执行一轮对话。进程死亡 / 管道断开 / 超时 → 复位 app-server 并自动重试一次。

    - 重试仅发生在尚未产出任何内容的阶段（避免客户端收到重复内容）；
      已产出内容后再失败则报错，但同样会复位连接，保证下一请求干净。
    - 取用前已由 get_app() 做存活检查，死进程先重建再请求。
    - cancel_event 置位（如客户端断开）时不重试，复位连接终止上游 run。
    """
    had_output = {"v": False}

    def _wrap(cb):
        def f(d):
            had_output["v"] = True
            if cb:
                cb(d)
        return f

    t_cb, r_cb = _wrap(on_text), _wrap(on_reasoning)
    for attempt in (1, 2):
        try:
            a = get_app()
            sess = a.start_session()
            return a.run_stream(sess["session_id"], agent_input, model,
                                t_cb, r_cb, timeout=timeout, effort=effort,
                                cancel_event=cancel_event)
        except (AppServerError, OSError) as e:
            transient = e.transient if isinstance(e, AppServerError) else True
            if not transient:
                raise
            cancelled = cancel_event is not None and cancel_event.is_set()
            can_retry = (attempt == 1 and not had_output["v"] and not cancelled)
            reset_app()   # 无论是否重试，先复位坏连接，保证下一请求干净
            if not can_retry:
                if attempt == 1 and not cancelled:
                    log_line(f"[self-heal] 请求失败（{e}）且已产出内容，不再重试；连接已复位")
                raise
            log_line(f"[self-heal] 请求失败（{e}），已复位 app-server，自动重试一次")
    raise AppServerError("意外的重试流程状态")


# 一次只跑一个 run（lingxi 会话串行最稳）
_run_lock = threading.Lock()


def make_agent_input(text, model):
    return {"text": text, "files": [], "file_ids": [], "expect_model": model,
            "refs": [], "permission_mode": "default", "current_mode": "agent"}


def content_of(m):
    c = m.get("content")
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        out = []
        for part in c:
            if isinstance(part, dict):
                if part.get("type") == "text":
                    out.append(part.get("text", ""))
            else:
                out.append(str(part))
        return "\n".join(out)
    return "" if c is None else str(c)


def render_messages(messages):
    system = [content_of(m) for m in messages if m.get("role") == "system"]
    system = [s for s in system if s.strip()]
    blocks = []
    if system:
        blocks.append("[系统指令]\n" + "\n".join(system))
    conv = []
    for m in messages:
        role = m.get("role")
        if role == "system":
            continue
        c = content_of(m)
        if role == "user":
            conv.append(f"用户：{c}")
        elif role == "assistant":
            conv.append(f"助手：{c}")
    if conv:
        blocks.append("[历史对话]\n" + "\n".join(conv))
    return "\n\n".join(blocks)


def resolve_effort(model, body):
    """解析请求中的思维等级，返回要透传给灵犀的档位值，或 None（用云端默认）。

    宽容策略（对齐 OW-Bridge 的 defaultReasoning 兜底）：
      - 未提供 / 非字符串 → None
      - 自适应模型（无手动档位）→ 忽略任何传入档位，保持云端自适应
      - 有档位但值不可用（如灵犀三档之外的 medium/none，或该模型不支持的档）
        → 忽略并记日志，不中断对话
    """
    effort = body.get("reasoning_effort")
    if not effort and isinstance(body.get("reasoning"), dict):
        effort = body["reasoning"].get("effort")
    if not isinstance(effort, str) or not effort.strip():
        return None
    effort = effort.strip().lower()
    supported = MODEL_EFFORTS.get(model) or []
    if effort in supported:
        return effort
    if not supported:
        print(f"[effort] 忽略档位 {effort!r}：模型 {model} 为自适应（无手动档位）")
    else:
        print(f"[effort] 忽略档位 {effort!r}：模型 {model} 仅支持 {supported}")
    return None


app = FastAPI(title="Lingxi Bridge")


def is_authorized(request: Request):
    if request.headers.get("authorization", "") == f"Bearer {TOKEN}":
        return True
    if request.method == "GET" and request.url.path in ("/", "/index.html"):
        q = parse_qs(urlparse(str(request.url)).query)
        if q.get("token", [""])[0] == TOKEN:
            return True
    return False


NO_TOKEN_HINT = ("无效令牌：请在 Authorization 头携带 Bearer <令牌> 后重试"
                 "（浏览器打开控制台请使用启动窗口中带 ?token=… 的完整地址）")


def _no_token_html():
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="UTF-8"><title>灵犀 Bridge · 需要令牌</title>
<style>
body{{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;
background:#f3f5f4;color:#202826;font:14px "Microsoft YaHei",system-ui,sans-serif}}
.card{{background:#fff;border:1px solid #e0e7e3;border-radius:12px;padding:28px 32px;max-width:470px;line-height:2}}
h1{{font-size:17px;margin:0 0 8px;color:#266e5c}}
code{{background:#e8f1ed;padding:2px 6px;border-radius:5px;color:#266e5c;word-break:break-all}}
p{{margin:6px 0;font-size:13px}}
.muted{{color:#78817e;font-size:12px}}
</style></head><body><div class="card">
<h1>灵犀 Bridge · 需要访问令牌</h1>
<p>服务已在本机运行，此页面需要携带令牌才能打开控制台。</p>
<p>请使用启动窗口中给出的完整地址（含 <code>?token=…</code>），例如：</p>
<p><code>http://127.0.0.1:{PORT}/?token=&lt;令牌&gt;</code></p>
<p class="muted">提示：双击「启动灵犀Bridge.bat」会自动用正确地址打开控制台。</p>
</div></body></html>"""


@app.middleware("http")
async def auth_guard(request: Request, call_next):
    """鉴权 + 请求串联中间件：/health 免令牌，其余无令牌一律 401（浏览器导航给中文提示页）。

    每个请求生成 8 位 X-Request-Id：响应头取回，日志行与活动面板同 id，
    全链路可串联排障（对齐 workbuddy2api 经验）。
    安全说明：控制台与网关同源，无需任何 CORS 头（已全部移除）；
    监听默认仅本机 127.0.0.1，跨机器访问自然不可达。
    """
    rid = uuid.uuid4().hex[:8]
    request.state.rid = rid
    path = request.url.path
    if path.startswith("/health") or is_authorized(request):
        response = await call_next(request)
    elif "text/html" in (request.headers.get("accept") or ""):
        response = HTMLResponse(status_code=401, content=_no_token_html())
    else:
        response = JSONResponse(status_code=401, content={"detail": NO_TOKEN_HINT})
    response.headers["X-Request-Id"] = rid
    return response


@app.get("/", include_in_schema=False)
def console_page():
    return HTMLResponse(open(os.path.join(ROOT, "console.html"), encoding="utf-8").read())


@app.get("/health")
def health():
    """真实探活：lingxi 字段反映 app-server 真实连接状态（idle/running/dead）。

    ok=false 表示 lingxi 已崩溃（网关自身正常，下一请求会自动重建恢复）。
    """
    st = _lingxi_state()
    return {"ok": st["state"] != "dead", "service": "lingxi-bridge",
            "models": len(MODELS), "lingxi": st}


def _token_mask():
    return TOKEN[:4] + "****" if len(TOKEN) > 6 else "****"


def _uptime():
    s = int(time.time() - START_TIME)
    return f"{s // 3600}小时{s % 3600 // 60}分" if s >= 3600 else \
           f"{s // 60}分{s % 60}秒" if s >= 60 else f"{s}秒"


# ---------------- 账号与扫码登录 ----------------
@app.get("/admin/account")
def admin_account():
    sid = load_sid()
    info = {"sid": mask_sid(sid), "has_sid": bool(sid), "account": None}
    if sid:
        try:
            info["account"] = qr_login.check_session(sid)
        except Exception:
            pass
    return info


_qr = {"sess": None, "lock": threading.Lock()}


@app.post("/admin/qr/start")
def qr_start():
    sess = qr_login.QrSession()
    d = sess.start()
    with _qr["lock"]:
        _qr["sess"] = sess
    return d


@app.get("/admin/qr/poll")
def qr_poll(phase: str = "scan"):
    sess = _qr["sess"]
    if sess is None:
        raise HTTPException(status_code=400, detail="请先获取二维码")
    o = sess.poll(phase)
    # 登录成功：后端自动用 kso_authcode 换 wps_sid
    if o.get("state") == "logined" and o.get("kso_authcode"):
        data, newsid, code = sess.grant(o["kso_authcode"])
        if newsid:
            save_sid(newsid)
            reset_app()
            return {"state": "logined", "account": qr_login.check_session(newsid)}
        return {"state": "grant_failed", "detail": data}
    return o


# ---------------- 一键测试 ----------------
_test = {"running": False, "done": [], "total": 0, "finished": 0, "lock": threading.Lock()}


def _run_tests(models, effort_map, prompt):
    with _test["lock"]:
        _test.update(running=True, done=[], total=len(models), finished=0)
    persisted = load_results()
    for m in models:
        t0 = time.time()
        item = {"model": m}
        rid = activity_start(m, effort_map.get(m), stream=False)
        activity_stage(rid, "upstream")
        probe = {"ttfb": None, "chars": 0}   # 探测：首字延迟 / 输出字数（速率由两者算出）

        def on_text(d, _p=probe, _t0=t0):
            if _p["ttfb"] is None:
                _p["ttfb"] = round(time.time() - _t0, 2)
            _p["chars"] += len(d)

        try:
            with _run_lock:
                r = do_run(m, make_agent_input(prompt, m), effort_map.get(m),
                           timeout=TEST_TIMEOUT, on_text=on_text)
            elapsed = round(time.time() - t0, 1)
            chars = probe["chars"] or len((r["text"] or "").strip())
            ttfb = probe["ttfb"]
            rate = round(chars / max(elapsed - (ttfb or 0), 0.1), 1) if chars else None
            item.update(ok=True, elapsed=elapsed, ttfb=ttfb, chars=chars, rate=rate,
                        snippet=(r["text"] or "").strip()[:60])
            activity_stage(rid, "done")
            persisted[m] = {"ok": True, "elapsed": elapsed, "ttfb": ttfb,
                            "chars": chars, "rate": rate,
                            "at": datetime.now().strftime("%m-%d %H:%M")}
        except Exception as e:
            cls = classify_error(e)
            item.update(ok=False, elapsed=round(time.time() - t0, 1),
                        error=str(e)[:140], kind=cls["kind"], hint=cls["hint"])
            activity_stage(rid, "failed", error=e, kind=cls["kind"])
            persisted[m] = {"ok": False, "elapsed": item["elapsed"],
                            "kind": cls["kind"], "hint": cls["hint"],
                            "at": datetime.now().strftime("%m-%d %H:%M")}
        with _test["lock"]:
            _test["done"].append(item)
            _test["finished"] += 1
        save_results(persisted)   # 每个模型测完即落盘，中途刷新也不丢
    with _test["lock"]:
        _test["running"] = False


@app.post("/admin/test-all")
async def test_all(request: Request):
    refresh_models()
    body = await request.json()
    models = body.get("models", [])
    models = [m for m in models if m in MODEL_KEYS and m != "auto"]
    if not models:
        raise HTTPException(status_code=400, detail="未选择有效模型")
    if _test["running"]:
        raise HTTPException(status_code=409, detail="测试正在进行中")
    # 探测用默认提示：约 30 字输出，让"首字延迟/速率"两个指标都有参考价值（额度消耗仍极小）
    prompt = body.get("prompt") or "请用一句话（30 字以内）介绍你自己。"
    effort = body.get("effort")
    raw_map = body.get("effort_map") if isinstance(body.get("effort_map"), dict) else {}
    effort_map = {m: e for m, e in raw_map.items()
                  if e in VALID_EFFORTS and e in MODEL_EFFORTS.get(m, [])}
    if effort in VALID_EFFORTS:
        for m in models:
            if effort in MODEL_EFFORTS.get(m, []):
                effort_map[m] = effort
    threading.Thread(target=_run_tests, args=(models, effort_map, prompt),
                     daemon=True).start()
    return {"started": True, "total": len(models)}


@app.get("/admin/test-progress")
def test_progress():
    with _test["lock"]:
        return {"running": _test["running"], "total": _test["total"],
                "finished": _test["finished"], "done": list(_test["done"])}


# ---------------- WorkBuddy 导入 ----------------
@app.get("/admin/status")
def admin_status():
    act = activity_snapshot()
    return {"service": "lingxi-bridge", "port": PORT, "host": HOST,
            "endpoint": f"http://127.0.0.1:{PORT}/v1/chat/completions",
            "token_mask": _token_mask(), "uptime": _uptime(),
            "started_at": datetime.fromtimestamp(START_TIME).strftime("%Y-%m-%d %H:%M:%S"),
            "log_file": LOG_FILE,
            "timeout": TIMEOUT,
            "gateway_config": {"path": CONFIG_FILE, "exists": os.path.exists(CONFIG_FILE),
                               "sources": dict(CONFIG_SOURCES)},
            "activity": {"active": act["active"]},
            "lingxi": _lingxi_state(),
            "models_source": MODELS_SOURCE,
            "models_file": MODELS_FILE,
            "config": workbuddy_sync.imported_status()}


# ---------------- 活动面板 / 结果持久化（P1-1 / P1-3） ----------------
@app.get("/admin/activity")
def admin_activity():
    return activity_snapshot()


@app.get("/admin/results")
def admin_results():
    return {"results": load_results()}


@app.get("/admin/reqlog")
def admin_reqlog(limit: int = 50):
    """最近 N 条结构化请求记录（reqlog.jsonl 尾部，含轮转文件 .1），倒序返回。"""
    limit = max(1, min(int(limit or 50), 500))
    lines = []
    for p in (REQLOG_FILE + ".1", REQLOG_FILE):   # .1 更旧，先读
        if os.path.exists(p):
            try:
                with open(p, encoding="utf-8") as f:
                    lines.extend(f.readlines()[-limit:])
            except Exception:
                pass
    out = []
    for ln in lines[-limit:]:
        ln = ln.strip()
        if not ln:
            continue
        try:
            out.append(json.loads(ln))
        except Exception:
            continue
    out.reverse()   # 最新在前
    return {"count": len(out), "entries": out, "file": REQLOG_FILE}


@app.post("/admin/open-logs")
def admin_open_logs():
    """控制台「打开日志目录」：资源管理器打开 bridge-runtime/logs。"""
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        subprocess.Popen(["explorer", os.path.normpath(LOG_DIR)])
        return {"ok": True, "path": LOG_DIR}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/admin/find-config")
def admin_find_config():
    p, exists = workbuddy_sync.find_config()
    return {"path": p, "exists": exists}


@app.post("/admin/reload-models")
def admin_reload_models():
    """手动重载模型清单（改完 bridge-runtime/models.json 调一下即生效，无需重启）。"""
    changed = refresh_models(force=True)
    return {"reloaded": changed, "source": MODELS_SOURCE, "count": len(MODELS),
            "models": [k for k, _ in MODELS]}


@app.post("/admin/import")
async def admin_import(request: Request):
    refresh_models()
    body = await request.json()
    selected = body.get("selected", [])
    force = bool(body.get("force", False))
    endpoint = body.get("endpoint") or f"http://127.0.0.1:{PORT}/v1/chat/completions"
    return workbuddy_sync.import_models(selected, endpoint, TOKEN, dict(MODELS),
                                        model_efforts=MODEL_EFFORTS, force=force)


# ---------------- ZCode 导入 ----------------
@app.get("/admin/zcode-status")
def admin_zcode_status():
    st = zcode_sync.current_status()
    st["zcode_running"] = zcode_sync.zcode_running()
    return st


@app.post("/admin/import-zcode")
async def admin_import_zcode(request: Request):
    refresh_models()
    body = await request.json()
    selected = [m for m in body.get("selected", []) if m in MODEL_KEYS and m != "auto"]
    if not selected:
        raise HTTPException(status_code=400, detail="未选择有效模型")
    try:
        return zcode_sync.import_to_zcode(PORT, TOKEN, selected)
    except Exception as e:
        raise HTTPException(status_code=500,
                            detail=f"写入 ZCode 配置失败（文件未改动）：{e}")


# ---------------- OpenAI 兼容接口 ----------------
@app.get("/v1/models")
def list_models():
    refresh_models()
    return {"object": "list", "data": [
        {"id": k, "object": "model", "created": 0, "owned_by": "lingxi",
         "name": name, "reasoning_efforts": MODEL_EFFORTS.get(k, [])}
        for k, name in MODELS]}


def sse_chunk(model, delta=None, finish=None):
    choice = {"index": 0, "delta": delta or {}, "finish_reason": finish}
    o = {"id": "chatcmpl-" + uuid.uuid4().hex[:24], "object": "chat.completion.chunk",
         "created": int(time.time()), "model": model, "choices": [choice]}
    return "data: " + json.dumps(o, ensure_ascii=False) + "\n\n"


@app.post("/v1/chat/completions")
async def chat(request: Request):
    refresh_models()   # 清单有变自动重读（mtime 对比，无变化时开销仅两次 stat）
    body = await request.json()
    model = body.get("model", "deepseek-v4-pro-0813")
    if model not in MODEL_KEYS:
        cand = [k for k in MODEL_KEYS if model in k or k in model]
        if cand:
            model = cand[0]
        else:
            raise HTTPException(status_code=400, detail=f"未知模型: {model}")
    messages = body.get("messages", [])
    if not messages:
        raise HTTPException(status_code=400, detail="缺少 messages")
    text = render_messages(messages)
    stream = bool(body.get("stream", False))
    effort = resolve_effort(model, body)
    agent_input = make_agent_input(text, model)

    if not stream:
        rid = activity_start(model, effort, stream=False,
                             rid=getattr(request.state, "rid", None))

        def work():
            with _run_lock:
                return do_run(model, agent_input, effort, timeout=TIMEOUT)
        try:
            activity_stage(rid, "upstream")
            result = await asyncio.get_event_loop().run_in_executor(None, work)
        except AppServerError as e:
            cls = classify_error(e)
            activity_stage(rid, "failed", error=e, kind=cls["kind"])
            log_line(f"[req {rid}] failed: {cls['hint']}")
            raise HTTPException(status_code=502, detail=cls["hint"] + f"（{e}）")
        if result.get("text"):
            activity_chars(rid, result["text"])
        activity_stage(rid, "done")
        return {"id": "chatcmpl-" + uuid.uuid4().hex[:24],
                "object": "chat.completion", "created": int(time.time()),
                "model": model,
                "choices": [{"index": 0, "message": {"role": "assistant",
                            "content": result["text"]}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}}

    rid = activity_start(model, effort, stream=True,
                         rid=getattr(request.state, "rid", None))
    client_gone = threading.Event()   # 客户端断开:generator finally 置位,worker 据此止损

    def generator():
        q = queue.Queue()

        def on_text(d):
            activity_chars(rid, d)
            q.put(("text", d))

        def on_reasoning(d):
            q.put(("reasoning", d))

        def worker():
            try:
                activity_stage(rid, "upstream")
                with _run_lock:
                    do_run(model, agent_input, effort, timeout=TIMEOUT,
                           on_text=on_text, on_reasoning=on_reasoning,
                           cancel_event=client_gone)
                # 终态在生产者侧落定:客户端断开时消费者已死,靠它转发会永远丢状态
                if client_gone.is_set():
                    activity_stage(rid, "failed", error="客户端已断开，已终止上游 run",
                                   kind="client_gone")
                    log_line(f"[req {rid}] 客户端已断开，上游 run 已终止")
                else:
                    activity_stage(rid, "done")
                    q.put(("done", None))
            except Exception as e:
                if client_gone.is_set():
                    activity_stage(rid, "failed", error="客户端已断开，已终止上游 run",
                                   kind="client_gone")
                    log_line(f"[req {rid}] 客户端已断开，上游 run 已终止")
                else:
                    cls = classify_error(e)
                    activity_stage(rid, "failed", error=e, kind=cls["kind"])
                    log_line(f"[req {rid}] stream failed: {cls['hint']}")
                    q.put(("error", cls, str(e)))
        threading.Thread(target=worker, daemon=True).start()

        async def agen():
            yield sse_chunk(model, {"role": "assistant"})
            try:
                while True:
                    try:
                        item = q.get_nowait()
                    except queue.Empty:
                        # 空闲时探测客户端断开(BaseHTTPMiddleware 下 finally 可能滞后)
                        try:
                            if await request.is_disconnected():
                                client_gone.set()
                                break
                        except Exception:
                            pass
                        await asyncio.sleep(0.15)
                        continue
                    kind = item[0]
                    if kind == "text":
                        activity_stage(rid, "content")   # 首字延迟在首次到达时记录
                        yield sse_chunk(model, {"content": item[1]})
                    elif kind == "reasoning":
                        activity_stage(rid, "content")
                        yield sse_chunk(model, {"reasoning_content": item[1]})
                    elif kind == "error":
                        cls, msg = item[1], item[2]
                        yield "data: " + json.dumps(
                            {"error": {"message": f"{cls['hint']}（{msg}）",
                                       "type": cls["kind"]}},
                            ensure_ascii=False) + "\n\n"
                        break
                    else:
                        yield sse_chunk(model, finish="stop")
                        yield "data: [DONE]\n\n"
                        break
            finally:
                # 正常收尾或客户端断开:置位让 worker 终止上游
                client_gone.set()

        return agen()

    return StreamingResponse(generator(), media_type="text/event-stream")


def probe_port(host, port):
    """启动前端口体检：'running'=本程序在跑 / 'occupied'=被其他程序占用 / None=空闲。"""
    target = "127.0.0.1" if host in ("", "0.0.0.0") else host
    s = socket.socket()
    s.settimeout(1.5)
    try:
        s.connect((target, port))
    except OSError:
        return None
    finally:
        s.close()
    try:
        d = requests.get(f"http://{target}:{port}/health", timeout=2).json()
        if isinstance(d, dict) and d.get("service") == "lingxi-bridge":
            return "running"
    except Exception:
        pass
    return "occupied"


def warn_leftover_lingxi():
    """启动时检测残留 lingxi.exe（极端卡死场景保险），仅提示、不强杀。"""
    try:
        r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq lingxi.exe",
                            "/FO", "CSV", "/NH"],
                           capture_output=True, text=True, encoding="gbk",
                           errors="replace", timeout=8,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        out = r.stdout or ""
        if "lingxi.exe" in out:
            pids = [ln.split('","')[1] for ln in out.splitlines()
                    if "lingxi.exe" in ln and '","' in ln]
            pid_txt = ("，PID " + "、".join(pids)) if pids else ""
            print(f"[提示] 检测到系统中已有 lingxi.exe 进程{pid_txt}（可能是上次的残留）。")
            print("       如稍后遇到异常，可在任务管理器结束它，或执行：taskkill /IM lingxi.exe /F")
    except Exception:
        pass


def startup_login_check():
    """启动后后台预检登录态：有效则报账号，失效则直接指引去控制台扫码（无需客户端）。"""
    try:
        sid = load_sid()
        if not sid:
            print("[登录] 未找到 wps_sid：请打开控制台点「扫码登录 / 切换账号」扫码，无需安装任何客户端。")
            return
        acct = None
        try:
            acct = qr_login.check_session(sid)
        except Exception:
            pass
        if acct:
            who = acct.get("nickname") or acct.get("user_id") or "已登录"
            print(f"[登录] wps_sid 有效（{who}），账号正常。")
        else:
            print("[登录] wps_sid 已失效或校验失败：请打开控制台点「扫码登录 / 切换账号」重新扫码；")
            print("       扫码后自动换新 sid 并重连，无需重启本程序，也不需安装灵犀客户端。")
    except Exception:
        pass


if __name__ == "__main__":
    import uvicorn
    cfg_bits = [
        f"端口 {PORT}({_src_port})", f"监听 {HOST}({_src_host})",
        f"超时 {TIMEOUT}s({_src_timeout})", f"测试超时 {TEST_TIMEOUT}s({_src_test_timeout})",
        f"日志 {'开' if LOG_ENABLED else '关'}({_src_log}) · {LOG_MAX_MB:g}MB({_src_log_max})",
        f"请求历史 {'开' if REQLOG_ENABLED else '关'}({_src_reqlog}) · {REQLOG_MAX_MB:g}MB/{REQLOG_KEEP_DAYS}天",
    ]
    if os.path.exists(CONFIG_FILE):
        print(f"配置文件: {CONFIG_FILE}")
    else:
        print(f"配置文件: 未创建（可选，模板见 gateway.example.json；键名与含义见文件内注释）")
    print("配置来源: " + " | ".join(cfg_bits))
    status = probe_port(HOST, PORT)
    if status == "running":
        print(f"[提示] 灵犀 Bridge 已在运行（端口 {PORT}），无需重复启动。")
        print(f"       打开控制台：http://127.0.0.1:{PORT}/?token={TOKEN}")
        print("       如需重启：请先关闭此前运行本程序的窗口，再双击启动。")
        sys.exit(0)
    if status == "occupied":
        print(f"[错误] 端口 {PORT} 已被其他程序占用，灵犀 Bridge 无法启动。")
        print("       可换端口启动：改 bridge-runtime/gateway.json 的 port，或 set LINGXI_BRIDGE_PORT=8800")
        sys.exit(1)
    warn_leftover_lingxi()
    reqlog_cleanup()   # 按保留天数清理历史请求记录（超期才删）
    print(f"灵犀 Bridge 启动: http://127.0.0.1:{PORT}  token={TOKEN}")
    print(f"日志文件: {LOG_FILE}" + ("" if LOG_ENABLED else "（log_enabled=false，已关闭落盘）"))
    threading.Thread(target=startup_login_check, daemon=True).start()   # 登录预检（不阻塞启动）
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")
