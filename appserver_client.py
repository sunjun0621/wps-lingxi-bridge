# -*- coding: utf-8 -*-
"""灵犀 app-server (lingxi.exe) 的 stdio JSON-RPC 2.0 客户端。
支持进程存活检测（poll + stdout EOF）与瞬态错误分类，供 Gateway 做崩溃自愈。"""
import subprocess, json, threading, time, os, sys

class AppServerError(Exception):
    """app-server 交互错误。

    transient=True 表示"进程崩溃/管道断开/超时"类可恢复错误，
    调用方（网关）据此执行一次"复位 + 重建 + 重试"。
    """
    def __init__(self, message, code=None, data=None, transient=False):
        super().__init__(message); self.code = code; self.data = data
        self.transient = transient

class LingxiAppServer:
    def __init__(self, exe, config, data_dir, timeout=60):
        self.exe, self.config, self.data_dir = exe, config, data_dir
        self.timeout = timeout
        self._id = 0
        self._futures = {}
        self._lock = threading.Lock()
        self._flock = threading.Lock()      # 保护 _futures 与 EOF 状态的竞态
        self._eof = threading.Event()       # stdout 已关闭（进程退出）标记
        self._notif_cbs = []
        self.proc = None

    def start(self):
        self._eof.clear()
        self.proc = subprocess.Popen(
            [self.exe, "--stdin", "--auth-storage=runtime",
             "--config", self.config, "--data-dir", self.data_dir],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            bufsize=1, text=True, encoding="utf-8")
        t = threading.Thread(target=self._reader, daemon=True); t.start()

    def is_alive(self):
        """进程存活且输出管道未关闭（取用前健康检查用）。"""
        return (self.proc is not None and self.proc.poll() is None
                and not self._eof.is_set())

    def stop(self, grace=1.5):
        """停止 app-server：关 stdin（lingxi 随 EOF 自退）→ terminate → kill 三级兜底。"""
        if self.proc is None:
            return
        try: self.proc.stdin.close()
        except Exception: pass
        try:
            self.proc.wait(timeout=grace); return   # 实测 EOF 后约 0.5s 自行退出
        except Exception: pass
        try: self.proc.terminate()
        except Exception: pass
        try:
            self.proc.wait(timeout=grace); return
        except Exception: pass
        try: self.proc.kill()
        except Exception: pass

    def on_notification(self, cb):
        self._notif_cbs.append(cb)
        return cb

    def _send(self, obj):
        line = json.dumps(obj, ensure_ascii=False) + "\n"
        with self._lock:
            try:
                self.proc.stdin.write(line); self.proc.stdin.flush()
            except (OSError, ValueError) as e:
                raise AppServerError(f"管道写入失败（app-server 可能已退出）: {e}",
                                     transient=True)

    def request(self, method, params=None, timeout=None):
        if self._eof.is_set():
            raise AppServerError("app-server 已退出，请复位重连", transient=True)
        self._id += 1
        rid = f"desktop_{self._id}"
        ev = threading.Event(); box = {}
        with self._flock:
            if self._eof.is_set():   # 复查：避免与 reader 的 EOF 清理竞态
                raise AppServerError("app-server 已退出，请复位重连", transient=True)
            self._futures[rid] = (ev, box)
        o = {"jsonrpc": "2.0", "id": rid, "method": method}
        if params is not None: o["params"] = params
        try:
            self._send(o)
        except Exception:
            with self._flock:
                self._futures.pop(rid, None)
            raise
        if not ev.wait(timeout or self.timeout):
            with self._flock:
                self._futures.pop(rid, None)
            raise AppServerError(f"请求超时: {method}", transient=True)
        if "_exc" in box:
            raise box["_exc"]
        if "error" in box:
            e = box["error"]; data = e.get("data")
            raise AppServerError(e.get("message", "RPC 错误"), e.get("code"), data)
        return box.get("result")

    def notify(self, method, params=None):
        o = {"jsonrpc": "2.0", "method": method}
        if params is not None: o["params"] = params
        self._send(o)

    def _reader(self):
        try:
            for raw in self.proc.stdout:
                raw = raw.rstrip("\r\n")
                if not raw.strip(): continue
                try: msg = json.loads(raw)
                except Exception:
                    continue
                if "id" in msg:
                    with self._flock:
                        fut = self._futures.pop(msg["id"], None)
                    if fut:
                        ev, box = fut
                        box.update(msg); ev.set()
                elif "method" in msg:
                    for cb in list(self._notif_cbs):
                        try: cb(msg)
                        except Exception: pass
        finally:
            # stdout 关闭（app-server 退出）：立即唤醒所有等待中的请求，避免干等超时
            self._eof.set()
            with self._flock:
                pending = list(self._futures.values())
                self._futures.clear()
            for ev, box in pending:
                box["_exc"] = AppServerError("app-server 进程已退出", transient=True)
                ev.set()

    # ---- 高层封装 ----
    def handshake(self, version="1.3.16", device_id="bridge-device", device_name="Bridge"):
        r = self.request("initialize", {
            "protocol_version": "2026-08-13",
            "client_info": {"name": "wps-lingxi-desktop", "version": version},
            "capabilities": {"bash_approval": False, "skill_management": False,
                             "timer_task": True, "auth_refresh": True},
            "device_id": device_id, "device_name": device_name})
        self.notify("initialized")
        return r

    def login(self, sid):
        return self.request("account/login/start",
                            {"auth_mode": "wps_sid", "wps_sid": sid})

    def start_session(self, session_id=None, session_type="cowork_client", extra=None):
        p = {"client_type": "desktop", "session_type": session_type}
        if session_id: p["session_id"] = session_id
        if extra: p.update(extra)
        return self.request("session/start", p)

    def run_start(self, session_id, agent_input, model=None):
        p = {"session_id": session_id, "agent_input": agent_input}
        if model: p["model"] = model
        return self.request("run/start", p)

    def run_stream(self, session_id, agent_input, model_key,
                   on_text=None, on_reasoning=None, timeout=180, effort=None):
        """发起一次 run 并收集流式输出。model_key 为灵犀模型 key 字符串。
        effort 为思维等级 low/high/max（仅该模型支持时有效）。
        返回 {text, reasoning, events}。"""
        if effort:
            agent_input = dict(agent_input)
            agent_input["reasoning_effort"] = effort
        collector = _RunCollector(on_text, on_reasoning)
        unreg = self.on_notification(collector.feed)
        model_map = {"provider": "lingxi", "model_name": model_key}
        try:
            ack = self.run_start(session_id, agent_input, model=model_map)
            collector.run_id = ack.get("run_id")
            # 等待 run 结束：轮询感知进程死亡（不干等满超时），并保持总超时语义
            deadline = time.time() + timeout
            while not collector.done.wait(timeout=0.5):
                if not self.is_alive():
                    raise AppServerError("app-server 进程已退出（连接中断）", transient=True)
                if time.time() >= deadline:
                    raise AppServerError("等待 run.end 超时", transient=True)
            if collector.error:
                raise AppServerError(collector.error)
            return {"text": "".join(collector.text),
                    "reasoning": "".join(collector.reasoning),
                    "events": collector.events}
        finally:
            try: self._notif_cbs.remove(unreg)
            except ValueError: pass


class _RunCollector:
    def __init__(self, on_text=None, on_reasoning=None):
        self.on_text = on_text or (lambda d: None)
        self.on_reasoning = on_reasoning or (lambda d: None)
        self.components = {}
        self.text, self.reasoning = [], []
        self.events = []
        self.done = threading.Event()
        self.error = None
        self.run_id = None

    def feed(self, msg):
        method = msg.get("method", "")
        p = msg.get("params", {}) or {}
        t = p.get("type", method)
        if method == "component.start":
            self.components[p.get("id")] = p.get("type")
            self.events.append(t)
        elif method == "component.content":
            cid = p.get("id")
            ctype = self.components.get(cid)
            delta = p.get("delta", "") or ""
            if ctype == "c_text":
                self.text.append(delta); self.on_text(delta)
            elif ctype == "c_reasoning":
                self.reasoning.append(delta); self.on_reasoning(delta)
            self.events.append(t)
        elif t in ("run.end",) or method in ("run.end",):
            self.events.append("run.end"); self.done.set()
        elif t in ("run.cancelled", "force.stop") or method in ("run.cancelled", "force.stop"):
            self.error = p.get("reason", "运行被取消"); self.done.set()
        elif t == "agent.error" or method in ("agent.error", "error"):
            self.error = p.get("message", "运行错误"); self.done.set()
