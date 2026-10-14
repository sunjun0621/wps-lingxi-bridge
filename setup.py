# -*- coding: utf-8 -*-
"""新机初始化：克隆本仓库后跑一次即可就绪。

用法：python setup.py
做什么：
  1. 依赖自检（缺包给清华源安装命令后退出，重跑即可）
  2. 从入库的运行件 zip 解压出 appserver/app-server/（已存在且完整则跳过）
  3. 生成 bridge-runtime/ 骨架（config.json 首次运行由 app-server 自建；state 目录预建）
不做什么：不碰登录态——wps_sid 永不入库，启动后在控制台扫码登录即可（无需客户端）。
"""
import os, sys, zipfile, importlib.util

ROOT = os.path.dirname(os.path.abspath(__file__))
ZIP = os.path.join(ROOT, "appserver", "app-server-windows-amd64.zip")
DEST = os.path.join(ROOT, "appserver")
EXE = os.path.join(DEST, "app-server", "service", "lingxi.exe")
RT = os.path.join(ROOT, "bridge-runtime")

CORE = ["fastapi", "uvicorn", "requests"]
MIRROR = "https://pypi.tuna.tsinghua.edu.cn/simple"


def step_deps():
    print("[1/3] 依赖自检")
    missing = [m for m in CORE if importlib.util.find_spec(m) is None]
    if missing:
        print("  缺少必需包：" + "、".join(missing))
        print(f'  请执行："{sys.executable}" -m pip install -i {MIRROR} ' + " ".join(missing))
        print("  装好后重新运行本脚本。")
        sys.exit(1)
    print("  依赖就绪")


def step_runtime():
    print("[2/3] 运行件")
    if os.path.exists(EXE):
        print("  appserver/app-server 已就绪，跳过解压")
        return
    if not os.path.exists(ZIP):
        print(f"  [错误] 未找到运行件 zip：{ZIP}")
        print("  请从 WPS 灵犀桌面安装目录复制 resources/app-server/app-server-windows-amd64.zip")
        print("  到项目 appserver/ 下，或向仓库所有者索取。")
        sys.exit(1)
    print("  解压运行件（约 200MB，几秒钟）…")
    with zipfile.ZipFile(ZIP) as z:
        z.extractall(DEST)
    ok = os.path.exists(EXE)
    print("  解压完成" if ok else "  [警告] 解压后未找到 lingxi.exe，请检查 zip 内容")
    if not ok:
        sys.exit(1)


def step_runtime_dir():
    print("[3/3] 运行目录骨架")
    os.makedirs(os.path.join(RT, "state"), exist_ok=True)
    os.makedirs(os.path.join(RT, "logs"), exist_ok=True)
    cfg = os.path.join(RT, "config.json")
    if os.path.exists(cfg):
        print("  config.json 已存在")
    else:
        # 空骨架：app-server 首次运行会自建/补全；sandbox 段缺失不影响对话（已实测）
        import json
        json.dump({"sandbox": {}, "compact": {
            "cache_expire_snip": {"gap_minutes": 60, "keep_recent": 5}}},
            open(cfg, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("  已生成最小 config.json（app-server 首次运行会自动补全）")
    print("  bridge-runtime/ 就绪")


def main():
    print("== 灵犀 Bridge 新机初始化 ==")
    step_deps()
    step_runtime()
    step_runtime_dir()
    print("\n完成。下一步：")
    print('  1. 双击「启动灵犀Bridge.bat」启动（或 python bridge_gateway.py）')
    print("  2. 控制台点「扫码登录 / 切换账号」，用 WPS 手机 APP 扫码（无需任何客户端）")
    print("  3. 勾选模型 → 一键测试 → 导入 WorkBuddy / ZCode")


if __name__ == "__main__":
    main()
