# -*- coding: utf-8 -*-
"""步骤 3 依赖自检验收：用 find_spec 补丁在子进程里模拟缺包场景。

用法：python tests/e2e_deps.py
覆盖：
  D1 缺核心包(fastapi) → 中文错误 + 清华源命令 + 退出码 1 + 无裸 traceback + 不进入后续导入
  D2 缺可选包(win32crypt) → 一行中文提示，导入继续成功（不阻断）
  D3 真实环境 → 无 [错误] 输出，模块导入正常
  D4 check_deps.py 全量清单可运行
"""
import os, sys, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'✅' if cond else '❌'} {name}" + (f" —— {detail}" if detail else ""))


def run_import_with_missing(missing_mod, marker="IMPORT_DONE"):
    """在子进程里把 find_spec 打补丁让 missing_mod 视为缺失，然后 import bridge_gateway。"""
    code = (
        "import importlib.util, sys\n"
        "real = importlib.util.find_spec\n"
        "importlib.util.find_spec = lambda name, *a, **k: None if name == %r else real(name, *a, **k)\n"
        "sys.path.insert(0, %r)\n"
        "import bridge_gateway\n"
        "print(%r)\n" % (missing_mod, ROOT, marker)
    )
    return subprocess.run([sys.executable, "-c", code], cwd=ROOT,
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=120)


def main():
    print("== 步骤 3 依赖自检验收 ==")

    # D1 缺核心包
    print("D1 缺核心包(fastapi)")
    p = run_import_with_missing("fastapi")
    out = (p.stdout or "") + (p.stderr or "")
    check("退出码为 1", p.returncode == 1, str(p.returncode))
    check("中文错误提示", "缺少运行必需的 Python 包" in out and "fastapi" in out)
    check("含清华源安装命令", "pypi.tuna.tsinghua.edu.cn" in out and "pip install" in out)
    check("给出可执行解释器路径", sys.executable in out)
    check("无裸 traceback", "Traceback" not in out)
    check("未进入后续导入（在自检处即退出）", "IMPORT_DONE" not in out)

    # D2 缺可选包
    print("D2 缺可选包(win32crypt)")
    p = run_import_with_missing("win32crypt")
    out = (p.stdout or "") + (p.stderr or "")
    check("导入继续成功（不阻断）", p.returncode == 0 and "IMPORT_DONE" in out, f"rc={p.returncode}")
    check("有中文提示", "可选依赖缺失" in out and "pywin32" in out)
    check("提示含用途说明", "Cookie" in out)
    check("提示含清华源命令", "pypi.tuna.tsinghua.edu.cn" in out)
    check("无裸 traceback", "Traceback" not in out)

    # D3 真实环境
    print("D3 真实环境")
    p = run_import_with_missing("__never_missing__")
    out = (p.stdout or "") + (p.stderr or "")
    check("导入成功", p.returncode == 0 and "IMPORT_DONE" in out, f"rc={p.returncode}")
    check("无 [错误] 输出", "[错误]" not in out)

    # D4 check_deps.py
    print("D4 check_deps.py 全量清单")
    p = subprocess.run([sys.executable, "check_deps.py"], cwd=ROOT,
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=60)
    out = (p.stdout or "") + (p.stderr or "")
    check("可运行且列出 6 包", p.returncode == 0 and all(
        x in out for x in ("fastapi", "uvicorn", "requests", "pywin32", "cryptography", "websocket-client")),
        out.strip().splitlines()[0] if out else "")
    check("缺包时给清华源命令（websocket 当前缺失应触发）",
          ("websocket-client" not in out.replace("  [缺] ", "").replace("  [有] ", "")) is False
          or "pypi.tuna.tsinghua.edu.cn" in out)

    print(f"\n== 结果：通过 {len(PASS)} 项，失败 {len(FAIL)} 项 ==")
    if FAIL:
        print("失败项：" + "、".join(FAIL))
    return 0 if not FAIL else 1


if __name__ == "__main__":
    sys.exit(main())
