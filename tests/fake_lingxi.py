# -*- coding: utf-8 -*-
"""协议仿真桩：模拟 WPS 灵犀 app-server（lingxi.exe）的 stdio JSON-RPC 2.0 行为。

用途：本机无真实 lingxi.exe 运行件时的离线 E2E 验收（批次 2「看得见」）。
通过环境变量 LINGXI_BRIDGE_EXE 指向本文件（Windows 下用 lingxi_stub.bat 包装）。
严格按 appserver_client.py 期望的帧协议应答：
  initialize → initialized(notify) → account/login/start → session/start
  → run/start(ack run_id) → component.start/content(notify) → run.end(notify)

特殊行为（由 agent_input.text 触发）：
  含 [FAKE_ERR]   → 回 agent.error（非瞬态服务错误）
  含 [FAKE_SLOW]  → 分片输出间sleep（测试首字延迟/流式阶段）
  含 [FAKE_QUIT]  → 输出半个 run 后直接退出进程（模拟崩溃，测自愈）
"""
import sys, json, time, os

FAKE_ERR = "[FAKE_ERR]"
FAKE_SLOW = "[FAKE_SLOW]"
FAKE_QUIT = "[FAKE_QUIT]"


def emit(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def reply(id_, result):
    emit({"jsonrpc": "2.0", "id": id_, "result": result})


def notify(method, params):
    emit({"jsonrpc": "2.0", "method": method, "params": params or {}})


def main():
    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        try:
            msg = json.loads(raw)
        except Exception:
            continue
        method = msg.get("method", "")
        rid = msg.get("id")
        params = msg.get("params") or {}
        if method == "initialize":
            reply(rid, {"protocol_version": "2026-08-13",
                        "server_info": {"name": "lingxi-stub", "version": "0.0.1"},
                        "capabilities": {}})
        elif method == "account/login/start":
            reply(rid, {"ok": True, "account": {"user_id": "stub-1"}})
        elif method == "session/start":
            reply(rid, {"session_id": "sess-" + str(int(time.time() * 1000) % 100000)})
        elif method == "run/start":
            text = (params.get("agent_input") or {}).get("text", "")
            model = (params.get("model") or {}).get("model_name", "?")
            reply(rid, {"run_id": "run-" + str(int(time.time() * 1000) % 100000)})
            # 在后台线程吐流式帧，主循环继续读 stdin（保持崩溃模拟能力）
            import threading
            threading.Thread(target=run_frames, args=(text, model), daemon=True).start()
        elif method == "session/stop" or method == "run/stop":
            pass
        elif rid is not None:
            reply(rid, {"ok": True})


def run_frames(text, model):
    try:
        slow = FAKE_SLOW in text
        notify("component.start", {"id": "c1", "type": "c_text"})
        out = f"收到（stub·{model}）"
        for ch in out:
            notify("component.content", {"id": "c1", "delta": ch})
            if slow:
                time.sleep(0.15)
        if FAKE_ERR in text:
            notify("agent.error", {"message": "stub 模拟的服务错误"})
            return
        notify("component.start", {"id": "c2", "type": "c_reasoning"})
        notify("component.content", {"id": "c2", "delta": "思考中…"})
        notify("run.end", {"run_id": "stub"})
    except (BrokenPipeError, OSError):
        # 网关已关闭管道：直接退出，模拟 lingxi 随 stdin-EOF 自退
        os._exit(0)


if __name__ == "__main__":
    main()
