# -*- coding: utf-8 -*-
"""步骤 5 探测升级验收（隔离运行目录 + 仿真桩）。

用法：python tests/e2e_probe.py
覆盖：
  P1 一键测试产出探测指标 — 进度条目含 ttfb/chars/rate
  P2 指标落盘             — /admin/results 与 model_results.json 均含 ttfb/chars/rate
  P3 速率口径自洽         — rate ≈ chars / (elapsed - ttfb)
  P4 失败不产探测器指标   — ok=false 时无 ttfb/chars/rate（只有分类提示）
安全：LINGXI_BRIDGE_RUNTIME_DIR 指向临时目录，不触碰真实数据。
"""
import os, sys, json, time, tempfile, shutil, subprocess, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GATEWAY = os.path.join(ROOT, "bridge_gateway.py")
STUB = os.path.join(HERE, "lingxi_stub.bat")
PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'✅' if cond else '❌'} {name}" + (f" —— {detail}" if detail else ""))


def api(port, path, method="GET", body=None, timeout=30):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", method=method)
    req.add_header("Authorization", "Bearer probe-tok")
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, data=data, timeout=timeout) as r:
        return json.loads(r.read().decode())


def main():
    print("== 步骤 5 探测升级验收（隔离运行目录）==")
    rt = tempfile.mkdtemp(prefix="probe_rt_")
    PORT = 8897
    env = dict(os.environ, LINGXI_BRIDGE_PORT=str(PORT), LINGXI_BRIDGE_HOST="127.0.0.1",
               LINGXI_BRIDGE_TOKEN="probe-tok", LINGXI_SID="stub-sid",
               LINGXI_BRIDGE_RUNTIME_DIR=rt, LINGXI_BRIDGE_EXE=STUB)
    out = open(os.path.join(rt, "_gw.log"), "w", encoding="utf-8")
    p = subprocess.Popen([sys.executable, GATEWAY], stdout=out, stderr=subprocess.STDOUT,
                         env=env, cwd=ROOT, creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        t0 = time.time()
        while time.time() - t0 < 20:
            try:
                if api(PORT, "/health", timeout=2).get("service") == "lingxi-bridge":
                    break
            except Exception:
                time.sleep(0.4)
        check("网关就绪", True)

        # P1 探测指标：一次成功的 [FAKE_SLOW] 请求（慢速分片,让 ttfb/rate 有意义）
        print("P1 一键测试产出探测指标")
        api(PORT, "/admin/test-all", "POST",
            {"models": ["GLM-5.3-Flash"], "prompt": "[FAKE_SLOW] 你好"})
        t0 = time.time()
        d = None
        while time.time() - t0 < 60:
            d = api(PORT, "/admin/test-progress")
            if not d["running"] and d["finished"] == 1:
                break
            time.sleep(0.4)
        it = d["done"][0]
        check("测试完成且 ok=true", it.get("ok") is True, json.dumps(it, ensure_ascii=False)[:160])
        check("含首字延迟 ttfb", it.get("ttfb") is not None, str(it.get("ttfb")))
        check("含输出字数 chars>0", (it.get("chars") or 0) > 0, str(it.get("chars")))
        check("含速率 rate>0", (it.get("rate") or 0) > 0, str(it.get("rate")))

        # P2 落盘
        print("P2 指标持久化")
        res = api(PORT, "/admin/results")["results"]["GLM-5.3-Flash"]
        check("results 端点含 ttfb/chars/rate",
              all(k in res for k in ("ttfb", "chars", "rate")),
              json.dumps(res, ensure_ascii=False))
        disk = json.load(open(os.path.join(rt, "state", "model_results.json"), encoding="utf-8"))
        gl = disk["results"]["GLM-5.3-Flash"]
        check("model_results.json 含探测指标",
              all(k in gl for k in ("ttfb", "chars", "rate")))

        # P3 速率口径自洽
        print("P3 速率口径")
        expect = round(gl["chars"] / max(gl["elapsed"] - (gl["ttfb"] or 0), 0.1), 1)
        check("rate ≈ chars/(elapsed-ttfb)", abs(gl["rate"] - expect) <= 0.2,
              f"rate={gl['rate']} expect≈{expect}")

        # P4 失败不产探测指标
        print("P4 失败路径")
        api(PORT, "/admin/test-all", "POST",
            {"models": ["GLM-5.3-Flash"], "prompt": "[FAKE_ERR] 触发错误"})
        t0 = time.time()
        while time.time() - t0 < 60:
            d = api(PORT, "/admin/test-progress")
            if not d["running"] and d["finished"] == 1:
                break
            time.sleep(0.4)
        it = d["done"][0]
        check("失败 ok=false 且有分类", it.get("ok") is False and it.get("kind"),
              json.dumps(it, ensure_ascii=False)[:160])
        check("失败无 ttfb/chars/rate", not any(k in it for k in ("ttfb", "chars", "rate")))

        print(f"\n== 结果：通过 {len(PASS)} 项，失败 {len(FAIL)} 项 ==")
        if FAIL:
            print("失败项：" + "、".join(FAIL))
        return 0 if not FAIL else 1
    finally:
        try:
            p.terminate(); p.wait(timeout=5)
        except Exception:
            p.kill()
        out.close()
        time.sleep(0.3)
        shutil.rmtree(rt, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
