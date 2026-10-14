# -*- coding: utf-8 -*-
"""步骤 2 配置中心验收：env > gateway.json > 默认 三级优先级。

用法：python tests/e2e_config.py
覆盖：
  C1 仅文件   — 端口/令牌/超时/日志开关来自 gateway.json，启动打印来源为 gateway.json
  C2 混合     — env 覆盖端口与令牌，未设 env 的超时仍取文件值（逐键独立）
  C3 日志开关 — log_enabled=false 时不写 bridge.log（stdout 照常）
  C4 默认回落 — 无文件且无 env 时全部默认，来源打印"默认"
安全：真实的 bridge-runtime/gateway.json 若存在会先备份、结束后还原；测试用隔离端口。
"""
import os, sys, json, time, shutil, subprocess, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
GATEWAY = os.path.join(ROOT, "bridge_gateway.py")
RT = os.path.join(ROOT, "bridge-runtime")
CONFIG = os.path.join(RT, "gateway.json")
LOG_FILE = os.path.join(RT, "logs", "bridge.log")
STUB = os.path.join(HERE, "lingxi_stub.bat")

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'✅' if cond else '❌'} {name}" + (f" —— {detail}" if detail else ""))


def start(env_extra=None):
    env = dict(os.environ)
    env.pop("LINGXI_BRIDGE_PORT", None)
    env.pop("LINGXI_BRIDGE_TOKEN", None)
    env.pop("LINGXI_BRIDGE_TIMEOUT", None)
    env.pop("LINGXI_BRIDGE_LOG", None)
    env.update(env_extra or {})
    out = open(os.path.join(HERE, "_cfg_gw.log"), "w", encoding="utf-8")
    p = subprocess.Popen([sys.executable, GATEWAY], stdout=out, stderr=subprocess.STDOUT,
                         env=env, cwd=ROOT, creationflags=subprocess.CREATE_NO_WINDOW)
    return p, out


def stop(p, out):
    p.terminate()
    try:
        p.wait(timeout=5)
    except Exception:
        p.kill()
    out.close()


def wait_port(port, timeout=20):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as r:
                if json.loads(r.read().decode()).get("service") == "lingxi-bridge":
                    return True
        except Exception:
            time.sleep(0.4)
    return False


def status(port, token):
    req = urllib.request.Request(f"http://127.0.0.1:{port}/admin/status")
    req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.loads(r.read().decode())


def read_gw_stdout():
    return open(os.path.join(HERE, "_cfg_gw.log"), encoding="utf-8", errors="replace").read()


def main():
    print("== 步骤 2 配置中心验收（隔离端口）==")
    had_config = os.path.exists(CONFIG)
    backup = None
    if had_config:
        backup = CONFIG + ".e2e-backup"
        shutil.copy2(CONFIG, backup)
    try:
        os.makedirs(RT, exist_ok=True)

        # C1 仅文件：端口/令牌/超时来自 gateway.json，日志关闭
        print("C1 仅文件生效")
        json.dump({"port": 8893, "token": "cfg-token-123456", "timeout": 123,
                   "test_timeout": 45, "log_enabled": False, "log_max_mb": 1},
                  open(CONFIG, "w", encoding="utf-8"), ensure_ascii=False)
        p, out = start({"LINGXI_BRIDGE_EXE": STUB, "LINGXI_SID": "stub-for-cfg"})
        check("文件端口生效(8893)", wait_port(8893))
        st = status(8893, "cfg-token-123456")
        check("文件令牌生效", st.get("token_mask") == "cfg-****", str(st.get("token_mask")))
        check("文件超时生效(123s)", st.get("timeout") == 123, str(st.get("timeout")))
        check("状态标记配置文件存在", st.get("gateway_config", {}).get("exists") is True)
        check("来源=gateway.json", st.get("gateway_config", {}).get("sources", {}).get("port") == "gateway.json")
        # 触发一次请求（stub 聊天），验证 log_enabled=false 不落盘：
        # 用 X-Request-Id 精确断言该请求的行不出现在 bridge.log（8799 上的正式网关在跑，
        # 可能同时写同一日志文件，因此不做大小比较、只查 rid）
        req = urllib.request.Request("http://127.0.0.1:8893/v1/chat/completions", method="POST")
        req.add_header("Authorization", "Bearer cfg-token-123456")
        req.add_header("Content-Type", "application/json")
        rid = None
        try:
            with urllib.request.urlopen(req, json.dumps(
                    {"model": "GLM-5.3-Flash", "messages": [{"role": "user", "content": "hi"}]}
                    ).encode(), timeout=60) as r:
                rid = r.headers.get("X-Request-Id")
                r.read()
        except Exception as e:
            check("stub 请求成功", False, str(e))
        check("stub 请求返回 rid", bool(rid), str(rid))
        time.sleep(0.5)
        logtxt = open(LOG_FILE, encoding="utf-8", errors="replace").read() \
            if os.path.exists(LOG_FILE) else ""
        check("log_enabled=false 不写日志文件（按 rid 查无）",
              bool(rid) and f"[req {rid}]" not in logtxt, f"rid={rid}")
        stop(p, out)
        check("启动打印来源含 gateway.json", "gateway.json" in read_gw_stdout())

        # C2 env 覆盖（逐键独立）
        print("C2 env 覆盖文件（逐键）")
        p, out = start({"LINGXI_BRIDGE_PORT": "8894", "LINGXI_BRIDGE_TOKEN": "env-token-999888"})
        check("env 端口覆盖文件(8894)", wait_port(8894))
        st = status(8894, "env-token-999888")
        srcs = st.get("gateway_config", {}).get("sources", {})
        check("env 令牌覆盖生效", st.get("token_mask") == "env-****", str(st.get("token_mask")))
        check("未设 env 的超时仍取文件(123s)", st.get("timeout") == 123, str(st.get("timeout")))
        check("来源: port=env", srcs.get("port") == "LINGXI_BRIDGE_PORT", srcs.get("port"))
        check("来源: timeout=gateway.json", srcs.get("timeout") == "gateway.json", srcs.get("timeout"))
        stop(p, out)

        # C3 默认回落（删文件）。真实网关通常占着 8799：
        # 此步验证"来源全部=默认"与"探测到已在运行后安全退出"，不强行绑定端口。
        print("C3 无文件回落默认")
        os.remove(CONFIG)
        p, out = start()
        p.wait(timeout=30)
        si = read_gw_stdout()
        out.close()
        stop(p, out)
        check("默认来源=默认(端口 8799)", "端口 8799(默认)" in si, si.strip().splitlines()[:3])
        check("默认超时 240s", "超时 240s(默认)" in si)
        check("默认日志=开 5MB", "日志 开(默认) · 5MB(默认)" in si)
        check("启动打印'未创建'提示", "未创建" in si)
        started = ("已在运行" in si) or ("Application startup complete" in si)
        check("探测运行中实例或正常启动", started, si.strip().splitlines()[-1:] if si else "")

        print(f"\n== 结果：通过 {len(PASS)} 项，失败 {len(FAIL)} 项 ==")
        if FAIL:
            print("失败项：" + "、".join(FAIL))
        return 0 if not FAIL else 1
    finally:
        # 还原现场
        if backup:
            shutil.move(backup, CONFIG)
        elif os.path.exists(CONFIG):
            os.remove(CONFIG)
        for f in ("_cfg_gw.log",):
            fp = os.path.join(HERE, f)
            try:
                if os.path.exists(fp):
                    os.remove(fp)
            except PermissionError:
                pass   # 极少数情况下句柄尚未释放，留待下次运行覆盖


if __name__ == "__main__":
    sys.exit(main())
