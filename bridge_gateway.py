# -*- coding: utf-8 -*-
"""灵犀 Bridge：把 WPS 灵犀订阅内的多模型（DeepSeek/Qwen/GLM/Kimi/MiMo...）
通过本地 app-server(lingxi.exe) 暴露为 OpenAI 兼容接口，供 WorkBuddy / dsh 使用。

能力：OpenAI 兼容对话（含思维等级 low/high/max）、可视化控制台、
      一键测试全部模型、WPS 账号扫码登录（自动更新 wps_sid）。

启动：python bridge_gateway.py   （默认仅本机 127.0.0.1:8799）
环境变量：
  LINGXI_BRIDGE_HOST  监听地址（默认 127.0.0.1；如需局域网访问可设 0.0.0.0）
  LINGXI_BRIDGE_PORT  端口（默认 8799）
  LINGXI_BRIDGE_TOKEN 访问令牌（默认 lingxi-bridge）
  LINGXI_SID          wps_sid（不设则按 current_sid.txt / cookies_decrypted.json 读取）
"""
import os, sys, json, time, uuid, threading, queue, asyncio, socket, subprocess
import requests
sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)   # 行缓冲：日志/提示即时可见
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse, HTMLResponse
from urllib.parse import urlparse, parse_qs
from appserver_client import LingxiAppServer, AppServerError
import workbuddy_sync, qr_login

ROOT = os.path.dirname(os.path.abspath(__file__))
RT = os.path.join(ROOT, "bridge-runtime")
EXE = os.path.join(ROOT, "appserver", "app-server", "service", "lingxi.exe")
SID_FILE = os.path.join(ROOT, "current_sid.txt")
PORT = int(os.environ.get("LINGXI_BRIDGE_PORT", "8799"))
HOST = os.environ.get("LINGXI_BRIDGE_HOST", "127.0.0.1")   # 默认仅本机；局域网访问可设 0.0.0.0
TOKEN = os.environ.get("LINGXI_BRIDGE_TOKEN", "lingxi-bridge")
VALID_EFFORTS = ("low", "high", "max")

# key -> 展示名
MODELS = [
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
MODEL_KEYS = {k for k, _ in MODELS}


def load_efforts():
    """从 plans.json 读取每模型支持的思维等级。"""
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
    for k, _ in MODELS:
        eff.setdefault(k, [])
    return eff


MODEL_EFFORTS = load_efforts()


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
            print(f"[self-heal] 检测到 lingxi 进程已退出（exit={code}），自动重启")
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


def do_run(model, agent_input, effort, timeout=240, on_text=None, on_reasoning=None):
    """执行一轮对话。进程死亡 / 管道断开 / 超时 → 复位 app-server 并自动重试一次。

    - 重试仅发生在尚未产出任何内容的阶段（避免客户端收到重复内容）；
      已产出内容后再失败则报错，但同样会复位连接，保证下一请求干净。
    - 取用前已由 get_app() 做存活检查，死进程先重建再请求。
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
                                t_cb, r_cb, timeout=timeout, effort=effort)
        except (AppServerError, OSError) as e:
            transient = e.transient if isinstance(e, AppServerError) else True
            if not transient:
                raise
            can_retry = (attempt == 1 and not had_output["v"])
            reset_app()   # 无论是否重试，先复位坏连接，保证下一请求干净
            if not can_retry:
                if attempt == 1:
                    print(f"[self-heal] 请求失败（{e}）且已产出内容，不再重试；连接已复位")
                raise
            print(f"[self-heal] 请求失败（{e}），已复位 app-server，自动重试一次")
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
    """鉴权中间件：/health 免令牌，其余无令牌一律 401（浏览器导航给中文提示页）。

    安全说明：控制台与网关同源，无需任何 CORS 头（已全部移除）；
    监听默认仅本机 127.0.0.1，跨机器访问自然不可达。
    """
    path = request.url.path
    if path.startswith("/health") or is_authorized(request):
        return await call_next(request)
    if "text/html" in (request.headers.get("accept") or ""):
        return HTMLResponse(status_code=401, content=_no_token_html())
    return JSONResponse(status_code=401, content={"detail": NO_TOKEN_HINT})


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
    for m in models:
        t0 = time.time()
        item = {"model": m}
        try:
            with _run_lock:
                r = do_run(m, make_agent_input(prompt, m), effort_map.get(m),
                           timeout=90)
            item.update(ok=True, elapsed=round(time.time() - t0, 1),
                        snippet=(r["text"] or "").strip()[:60])
        except Exception as e:
            item.update(ok=False, elapsed=round(time.time() - t0, 1),
                        error=str(e)[:140])
        with _test["lock"]:
            _test["done"].append(item)
            _test["finished"] += 1
    with _test["lock"]:
        _test["running"] = False


@app.post("/admin/test-all")
async def test_all(request: Request):
    body = await request.json()
    models = body.get("models", [])
    models = [m for m in models if m in MODEL_KEYS and m != "auto"]
    if not models:
        raise HTTPException(status_code=400, detail="未选择有效模型")
    if _test["running"]:
        raise HTTPException(status_code=409, detail="测试正在进行中")
    prompt = body.get("prompt") or "请只回复两个字：在的"
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
    return {"service": "lingxi-bridge", "port": PORT, "host": HOST,
            "endpoint": f"http://127.0.0.1:{PORT}/v1/chat/completions",
            "lingxi": _lingxi_state(),
            "config": workbuddy_sync.imported_status()}


@app.post("/admin/find-config")
def admin_find_config():
    p, exists = workbuddy_sync.find_config()
    return {"path": p, "exists": exists}


@app.post("/admin/import")
async def admin_import(request: Request):
    body = await request.json()
    selected = body.get("selected", [])
    force = bool(body.get("force", False))
    endpoint = body.get("endpoint") or f"http://127.0.0.1:{PORT}/v1/chat/completions"
    return workbuddy_sync.import_models(selected, endpoint, TOKEN, dict(MODELS),
                                        model_efforts=MODEL_EFFORTS, force=force)


# ---------------- OpenAI 兼容接口 ----------------
@app.get("/v1/models")
def list_models():
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
        def work():
            with _run_lock:
                return do_run(model, agent_input, effort, timeout=240)
        try:
            result = await asyncio.get_event_loop().run_in_executor(None, work)
        except AppServerError as e:
            raise HTTPException(status_code=502, detail=str(e))
        return {"id": "chatcmpl-" + uuid.uuid4().hex[:24],
                "object": "chat.completion", "created": int(time.time()),
                "model": model,
                "choices": [{"index": 0, "message": {"role": "assistant",
                            "content": result["text"]}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}}

    def generator():
        q = queue.Queue()

        def on_text(d):
            q.put(("text", d))

        def on_reasoning(d):
            q.put(("reasoning", d))

        def worker():
            try:
                with _run_lock:
                    do_run(model, agent_input, effort, timeout=240,
                           on_text=on_text, on_reasoning=on_reasoning)
                q.put(("done", None))
            except Exception as e:
                q.put(("error", str(e)))
        threading.Thread(target=worker, daemon=True).start()
        yield sse_chunk(model, {"role": "assistant"})
        while True:
            kind, payload = q.get()
            if kind == "text":
                yield sse_chunk(model, {"content": payload})
            elif kind == "reasoning":
                yield sse_chunk(model, {"reasoning_content": payload})
            elif kind == "error":
                yield "data: " + json.dumps({"error": {"message": payload}},
                                            ensure_ascii=False) + "\n\n"
                break
            else:
                yield sse_chunk(model, finish="stop")
                yield "data: [DONE]\n\n"
                break

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


if __name__ == "__main__":
    import uvicorn
    status = probe_port(HOST, PORT)
    if status == "running":
        print(f"[提示] 灵犀 Bridge 已在运行（端口 {PORT}），无需重复启动。")
        print(f"       打开控制台：http://127.0.0.1:{PORT}/?token={TOKEN}")
        print("       如需重启：请先关闭此前运行本程序的窗口，再双击启动。")
        sys.exit(0)
    if status == "occupied":
        print(f"[错误] 端口 {PORT} 已被其他程序占用，灵犀 Bridge 无法启动。")
        print("       可换端口启动，例如：set LINGXI_BRIDGE_PORT=8800")
        sys.exit(1)
    warn_leftover_lingxi()
    print(f"灵犀 Bridge 启动: http://127.0.0.1:{PORT}  token={TOKEN}")
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")
