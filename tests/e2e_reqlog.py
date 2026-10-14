# -*- coding: utf-8 -*-
"""步骤 4 reqlog 结构化请求日志验收（隔离运行目录 + 仿真桩）。

用法：python tests/e2e_reqlog.py
覆盖：
  R1 写入      — 请求终态落一行 JSONL，字段齐全（rid/ts/model/stream/elapsed/ttfb/chars）
  R2 不记正文  — JSONL 行里不出现对话内容（只元数据）
  R3 轮转      — 超容量阈值后 reqlog.jsonl → .1,新文件继续写
  R4 保留期清理 — 超保留天数的旧文件启动时删除
  R5 查询端点  — /admin/reqlog 返回倒序、limit 生效
  R6 开关      — reqlog_enabled=false 时不写文件
安全：使用 LINGXI_BRIDGE_RUNTIME_DIR 指向临时目录，不触碰真实 bridge-runtime。
"""
import os, sys, json, time, tempfile, shutil, subprocess, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GATEWAY = os.path.join(ROOT, "bridge_gateway.py")
STUB = os.path.join(HERE, "lingxi_stub.bat")
PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'✅' if cond else '❌'} {name}" + (f" —— {detail}" if detail else ""))


def start(port, rt_dir, extra_env=None):
    env = dict(os.environ,
               LINGXI_BRIDGE_PORT=str(port),
               LINGXI_BRIDGE_HOST="127.0.0.1",
               LINGXI_BRIDGE_TOKEN="reqlog-tok",
               LINGXI_SID="stub-sid",
               LINGXI_BRIDGE_RUNTIME_DIR=rt_dir,
               LINGXI_BRIDGE_EXE=STUB)
    env.update(extra_env or {})
    out = open(os.path.join(rt_dir, "_gw.log"), "w", encoding="utf-8")
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


def api(port, path, method="GET", body=None, timeout=30):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", method=method)
    req.add_header("Authorization", "Bearer reqlog-tok")
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, data=data, timeout=timeout) as r:
        return json.loads(r.read().decode())


def chat(port, text, stream=False):
    req = urllib.request.Request(f"http://127.0.0.1:{port}/v1/chat/completions", method="POST")
    req.add_header("Authorization", "Bearer reqlog-tok")
    req.add_header("Content-Type", "application/json")
    body = json.dumps({"model": "GLM-5.3-Flash", "stream": stream,
                       "messages": [{"role": "user", "content": text}]}).encode()
    try:
        with urllib.request.urlopen(req, body, timeout=90) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def read_lines(path):
    if not os.path.exists(path):
        return []
    return [json.loads(l) for l in open(path, encoding="utf-8").read().splitlines() if l.strip()]


def main():
    print("== 步骤 4 reqlog 验收（隔离运行目录）==")
    rt = tempfile.mkdtemp(prefix="reqlog_rt_")
    reqlog = os.path.join(rt, "logs", "reqlog.jsonl")
    p, out = None, None
    try:
        PORT = 8896
        p, out = start(PORT, rt)
        check("网关就绪", wait_port(PORT))

        # R1 写入：一次成功 + 一次失败
        print("R1 终态落盘与字段")
        st, _ = chat(PORT, "reply ok")
        chat(PORT, "[FAKE_ERR] 触发错误")
        time.sleep(0.5)
        rows = read_lines(reqlog)
        check("reqlog.jsonl 已生成且 2 行", len(rows) == 2, f"{len(rows)} 行")
        ok_row = [r for r in rows if r.get("stage") == "done"]
        fail_row = [r for r in rows if r.get("stage") == "failed"]
        check("成功行字段齐全",
              ok_row and all(k in ok_row[0] for k in
                             ("ts", "rid", "model", "stream", "elapsed", "ttfb", "chars")),
              json.dumps(ok_row[0], ensure_ascii=False) if ok_row else "无 done 行")
        check("rid 为 8 位与响应头同源", ok_row and len(ok_row[0]["rid"]) == 8)
        check("完成行 chars>0", ok_row and ok_row[0]["chars"] > 0)
        check("失败行有 error 与 kind",
              fail_row and fail_row[0].get("error") and fail_row[0].get("kind"),
              json.dumps(fail_row[0], ensure_ascii=False) if fail_row else "无 failed 行")

        # R2 不记正文
        print("R2 不记正文")
        raw = open(reqlog, encoding="utf-8").read()
        check("文件不含对话正文", "reply ok" not in raw and "FAKE_ERR" not in raw)

        # R5 查询端点
        print("R5 查询端点")
        d = api(PORT, "/admin/reqlog?limit=50")
        check("返回 2 条", d.get("count") == 2, str(d.get("count")))
        check("倒序(最新在前)", d["entries"] and d["entries"][0]["ts"] >= d["entries"][-1]["ts"])
        d1 = api(PORT, "/admin/reqlog?limit=1")
        check("limit=1 生效", d1.get("count") == 1)
        stop(p, out); p = None

        # R3 轮转：把阈值调到极小(1KB)，预填超阈值再起一个请求
        print("R3 超阈值轮转")
        os.makedirs(os.path.dirname(reqlog), exist_ok=True)
        with open(reqlog, "a", encoding="utf-8") as f:
            for i in range(30):   # 每行 ~200B，共 ~6KB > 1KB 阈值
                f.write(json.dumps({"ts": "2026-10-14 00:00:00", "rid": f"old{i:04d}",
                                    "model": "x", "stream": False, "stage": "done",
                                    "elapsed": 1.0, "ttfb": None, "chars": 1,
                                    "kind": None, "error": None}) + "\n")
        p, out = start(PORT, rt, {"LINGXI_BRIDGE_REQLOG_MAX_MB": "0.001"})
        check("网关就绪(轮转档)", wait_port(PORT))
        chat(PORT, "reply ok")
        time.sleep(0.5)
        check("生成 .1 轮转文件", os.path.exists(reqlog + ".1"))
        new_rows = read_lines(reqlog)
        old_rows = read_lines(reqlog + ".1")
        check("新文件只含新请求", len(new_rows) <= 2 and all(r["rid"] != "old0000" for r in new_rows),
              f"新 {len(new_rows)} 行")
        check(".1 含旧数据", any(r["rid"] == "old0000" for r in old_rows))
        d = api(PORT, "/admin/reqlog?limit=100")
        check("查询跨轮转文件(.1+主文件)", d.get("count") > 30, str(d.get("count")))
        stop(p, out); p = None

        # R4 保留期清理：主文件与 .1 的 mtime 设为 40 天前，重启应删除
        print("R4 保留期清理(30 天)")
        old_time = time.time() - 40 * 86400
        for f in (reqlog, reqlog + ".1"):
            if os.path.exists(f):
                os.utime(f, (old_time, old_time))
        p, out = start(PORT, rt)
        check("网关就绪(清理档)", wait_port(PORT))
        time.sleep(1.0)
        check("超期文件已删除", not os.path.exists(reqlog + ".1"))
        stop(p, out); p = None

        # R6 开关关闭
        print("R6 reqlog_enabled=false")
        for f in (reqlog, reqlog + ".1"):
            if os.path.exists(f):
                os.remove(f)
        p, out = start(PORT, rt, {"LINGXI_BRIDGE_REQLOG": "0"})
        check("网关就绪(关闭档)", wait_port(PORT))
        chat(PORT, "reply ok")
        time.sleep(0.5)
        check("关闭后不产生文件", not os.path.exists(reqlog))
        stop(p, out); p = None

        print(f"\n== 结果：通过 {len(PASS)} 项，失败 {len(FAIL)} 项 ==")
        if FAIL:
            print("失败项：" + "、".join(FAIL))
        return 0 if not FAIL else 1
    finally:
        if p is not None:
            try: stop(p, out)
            except Exception: pass
        time.sleep(0.3)
        shutil.rmtree(rt, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
