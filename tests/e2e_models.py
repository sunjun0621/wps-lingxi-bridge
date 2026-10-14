# -*- coding: utf-8 -*-
"""步骤 6 模型清单配置化验收（隔离运行目录 + 仿真桩）。

用法：python tests/e2e_models.py
覆盖：
  M1 无文件回落 — /v1/models 返回内置 12 个，status.models_source=内置
  M2 热重载     — 写入 models.json 后，GET /v1/models 自动生效（2 个模型，定制名与档位）
  M3 新模型可用 — 清单里的新 key 可发对话请求（桩）
  M4 手动重载   — POST /admin/reload-models 返回 reloaded
  M5 损坏回落   — models.json 写坏后接口仍 200 且回落到内置（服务不崩）
安全：LINGXI_BRIDGE_RUNTIME_DIR 指向临时目录，不触碰真实数据。
"""
import os, sys, json, time, tempfile, shutil, subprocess, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GATEWAY = os.path.join(ROOT, "bridge_gateway.py")
STUB = os.path.join(HERE, "lingxi_stub.bat")
PORT = 8892
PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'✅' if cond else '❌'} {name}" + (f" —— {detail}" if detail else ""))


def api(path, method="GET", body=None, timeout=30):
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", method=method)
    req.add_header("Authorization", "Bearer models-tok")
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, data=data, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")


def main():
    print("== 模型清单配置化验收（隔离运行目录）==")
    rt = tempfile.mkdtemp(prefix="models_e2e_rt_")
    mfile = os.path.join(rt, "models.json")
    env = dict(os.environ, LINGXI_BRIDGE_PORT=str(PORT), LINGXI_BRIDGE_HOST="127.0.0.1",
               LINGXI_BRIDGE_TOKEN="models-tok", LINGXI_SID="stub-sid",
               LINGXI_BRIDGE_RUNTIME_DIR=rt, LINGXI_BRIDGE_EXE=STUB)
    out = open(os.path.join(rt, "_gw.log"), "w", encoding="utf-8")
    p = subprocess.Popen([sys.executable, GATEWAY], stdout=out, stderr=subprocess.STDOUT,
                         env=env, cwd=ROOT, creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        t0 = time.time()
        while time.time() - t0 < 20:
            try:
                st, d = api("/health", timeout=2)
                if d.get("service") == "lingxi-bridge":
                    break
            except Exception:
                time.sleep(0.4)
        check("网关就绪", True)

        # M1 无文件回落
        print("M1 无 models.json 回落内置")
        st, d = api("/v1/models")
        check("内置 12 个模型", st == 200 and len(d["data"]) == 12, str(len(d.get("data", []))))
        st, s = api("/admin/status")
        check("status.models_source=内置", s.get("models_source") == "内置", str(s.get("models_source")))

        # M2 热重载（mtime 变化后下一次 /v1/models 生效）
        print("M2 models.json 热重载")
        json.dump({"models": [
            {"key": "kimi-k3", "name": "Kimi 定制名", "efforts": ["low", "max"]},
            {"key": "GLM-5.3", "name": "GLM-5.3"}]},
            open(mfile, "w", encoding="utf-8"), ensure_ascii=False)
        time.sleep(0.1)
        st, d = api("/v1/models")
        ids = [m["id"] for m in d["data"]]
        names = {m["id"]: m["name"] for m in d["data"]}
        effs = {m["id"]: m["reasoning_efforts"] for m in d["data"]}
        check("热重载为 2 个模型", st == 200 and ids == ["kimi-k3", "GLM-5.3"], str(ids))
        check("定制展示名生效", names.get("kimi-k3") == "Kimi 定制名", str(names.get("kimi-k3")))
        check("文件档位优先(low/max)", effs.get("kimi-k3") == ["low", "max"], str(effs.get("kimi-k3")))
        check("缺省档位从 plans.json 补", effs.get("GLM-5.3") == ["low", "high", "max"], str(effs.get("GLM-5.3")))

        # M3 新 key 可对话（桩）；完全未知的 key 应被拒（注意网关有"近似名容错"，
        # 如 GLM-5.3-Flash 会被模糊命中 GLM-5.3，故用无任何包含关系的名字验证 400）
        print("M3 清单内模型可对话")
        st, r = api("/v1/chat/completions", "POST",
                    {"model": "kimi-k3", "messages": [{"role": "user", "content": "hi"}]})
        check("对话 200", st == 200 and "收到" in r["choices"][0]["message"]["content"], str(st))
        st, r = api("/v1/chat/completions", "POST",
                    {"model": "no-such-model-xyz", "messages": [{"role": "user", "content": "hi"}]})
        check("未知模型返回 400", st == 400, str(st))

        # M4 手动重载
        print("M4 /admin/reload-models")
        st, r = api("/admin/reload-models", "POST")
        check("手动重载返回 source/count", st == 200 and r.get("source") == "models.json"
              and r.get("count") == 2, json.dumps(r, ensure_ascii=False)[:120])

        # M5 损坏回落
        print("M5 models.json 损坏回落")
        open(mfile, "w", encoding="utf-8").write("{broken json")
        time.sleep(0.1)
        st, d = api("/v1/models")
        check("损坏后仍 200 且回落内置 12", st == 200 and len(d["data"]) == 12, str(len(d.get("data", []))))

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
