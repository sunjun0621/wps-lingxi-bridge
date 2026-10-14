# -*- coding: utf-8 -*-
"""灵犀 Bridge 体检工具。

用法：
  python check_deps.py            依赖清单（6 包状态 + 缺包清华源安装命令）
  python check_deps.py --status   网关/登录状态速查（需网关在运行；令牌自动读 gateway.json）
"""
import sys, importlib.util, os

MODS = [("fastapi", "fastapi"), ("uvicorn", "uvicorn"), ("requests", "requests"),
        ("win32crypt", "pywin32"), ("cryptography", "cryptography"),
        ("websocket", "websocket-client")]
MIRROR = "https://pypi.tuna.tsinghua.edu.cn/simple"


def deps_report():
    print("python:", sys.executable, sys.version.split()[0])
    missing = [pip for mod, pip in MODS if importlib.util.find_spec(mod) is None]
    for mod, pip in MODS:
        print(f"  [{'缺' if pip in missing else '有'}] {pip}")
    if missing:
        print("缺失包安装命令（清华源）：")
        print(f'  "{sys.executable}" -m pip install -i {MIRROR} ' + " ".join(missing))
    else:
        print("全部就绪")


def status_report():
    import json, urllib.request
    port = os.environ.get("LINGXI_BRIDGE_PORT", "")
    token = os.environ.get("LINGXI_BRIDGE_TOKEN", "")
    try:   # 令牌/端口与网关切面配置保持一致（env > gateway.json > 默认）
        cfg = json.load(open(os.path.join("bridge-runtime", "gateway.json"), encoding="utf-8"))
        port = port or str(cfg.get("port") or "")
        token = token or str(cfg.get("token") or "")
    except Exception:
        pass
    port, token = port or "8799", token or "lingxi-bridge"
    base = f"http://127.0.0.1:{port}"
    print(f"目标: {base}")
    try:
        with urllib.request.urlopen(base + "/health", timeout=3) as r:
            h = json.loads(r.read().decode())
        lx = h.get("lingxi") or {}
        print(f"  网关: 运行中（模型 {h.get('models')} 个）")
        print(f"  灵犀: {lx.get('state')}" + (f"（pid {lx.get('pid')}）" if lx.get("pid") else ""))
        if lx.get("state") == "dead":
            print("  -> 灵犀进程已退出：下一次请求会自动重启恢复，无需处理")
    except Exception as e:
        print(f"  网关: 未运行或不可达（{e}）")
        print("  -> 双击「启动灵犀Bridge.bat」启动")
        return
    req = urllib.request.Request(base + "/admin/account")
    req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=6) as r:
            a = json.loads(r.read().decode())
        acct = a.get("account")
        if acct:
            print(f"  登录: {acct.get('nickname') or '已登录'}" + ("（会员）" if acct.get("is_plus") else ""))
        elif a.get("has_sid"):
            print("  登录: sid 已失效 -> 打开控制台会自动展开二维码，扫码即可恢复")
        else:
            print("  登录: 无 sid -> 打开控制台扫码登录（WPS 手机 APP，无需客户端）")
    except Exception as e:
        print(f"  登录: 查询失败（{e}）：若改动过令牌，请与启动窗口显示的一致")


if __name__ == "__main__":
    if "--status" in sys.argv:
        status_report()
    else:
        deps_report()
