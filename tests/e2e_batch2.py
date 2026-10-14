# -*- coding: utf-8 -*-
"""批次 2「看得见」E2E 驱动脚本（隔离端口 8891，用协议仿真桩，不消耗灵犀额度）。

用法：python tests/e2e_batch2.py
覆盖验收项：
  T1 活动面板  — 非流式请求前后 /admin/activity 出现该请求并推进到 done，含耗时
  T2 活动面板  — 流式请求先 upstream/content 再 done，记录首字延迟与字数
  T3 日志落盘  — bridge-runtime/logs/bridge.log 生成，含 [req ...] start/done 行
  T4 结果持久化 — 一键测试写 model_results.json，/admin/results 可读回
  T5 错误分类  — [FAKE_ERR] 触发 agent.error → 非流式 502 中文分类提示；流式错误帧含 type
  T6 状态增强  — /admin/status 含 token_mask/uptime/log_file/activity；/health 正常
  T7 自愈回归  — 杀掉仿真桩进程后下一次请求自动恢复（批次 1 行为不回退）
"""
import os, sys, json, time, subprocess, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
PORT = 8891
BASE = f"http://127.0.0.1:{PORT}"
TOKEN = "lingxi-bridge"
GATEWAY = os.path.join(ROOT, "bridge_gateway.py")
RT = os.path.join(ROOT, "bridge-runtime")
LOG_FILE = os.path.join(RT, "logs", "bridge.log")
RESULTS_FILE = os.path.join(RT, "state", "model_results.json")

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'✅' if cond else '❌'} {name}" + (f" —— {detail}" if detail else ""))


def api(path, method="GET", body=None, timeout=30):
    req = urllib.request.Request(BASE + path, method=method)
    req.add_header("Authorization", f"Bearer {TOKEN}")
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, data=data, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")


def chat(text, stream=False, model="GLM-5.3-Flash", full=True):
    body = {"model": model, "stream": stream,
            "messages": [{"role": "user", "content": text}]}
    req = urllib.request.Request(BASE + "/v1/chat/completions", method="POST")
    req.add_header("Authorization", f"Bearer {TOKEN}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, json.dumps(body).encode(), timeout=90) as r:
            if stream:
                return r.status, r.read().decode()
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")


def wait_health(timeout=20):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            st, d = api("/health", timeout=3)
            if st == 200 and d.get("service") == "lingxi-bridge":
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def wait_activity(rid, stage, timeout=15):
    t0 = time.time()
    while time.time() - t0 < timeout:
        _, d = api("/admin/activity")
        for it in d.get("recent", []):
            if it["id"] == rid and (stage is None or it["stage"] == stage):
                return it
        time.sleep(0.3)
    return None


def main():
    print("== 批次 2 E2E（隔离端口 8891 · 协议仿真桩）==")
    env = dict(os.environ,
               LINGXI_BRIDGE_PORT=str(PORT),
               LINGXI_BRIDGE_TOKEN=TOKEN,
               LINGXI_BRIDGE_HOST="127.0.0.1",
               LINGXI_SID="stub-sid-for-e2e",   # 仿真桩不校验 sid，仅为过 get_app 的存在性检查
               LINGXI_BRIDGE_EXE=os.path.join(HERE, "lingxi_stub.bat"))
    # 用真实 python 而非 bat 包装：子进程需要 python 解析（.bat 里已有，这里直接指 py 文件也行，
    # 但 LingxiAppServer.Popen 需要 .exe/.bat 可执行 → 用 cmd 包装的 bat）
    gw_log = open(os.path.join(HERE, "_e2e_gateway.log"), "w", encoding="utf-8")
    gw = subprocess.Popen([sys.executable, GATEWAY], stdout=gw_log,
                          stderr=subprocess.STDOUT, env=env,
                          cwd=ROOT, creationflags=subprocess.CREATE_NO_WINDOW)
    stub_procs = []
    try:
        # 启动网关
        print("T0 启动网关")
        check("网关 20s 内就绪", wait_health())
        stub_pids = lambda: [p.pid for p in stub_procs if p.poll() is None]
        import re
        def stub_pid_from_log():
            """从网关日志读最新 lingxi pid（[lingxi] 已连接 app-server（pid=NNN)）"""
            try:
                txt = open(LOG_FILE, encoding="utf-8").read()
                pids = re.findall(r"pid=(\d+)", txt)
                return int(pids[-1]) if pids else None
            except Exception:
                return None

        # T6 状态增强
        print("T6 /admin/status 与 /health")
        st, s = api("/admin/status")
        check("status 含 token_mask", st == 200 and s.get("token_mask") == "ling****", str(s.get("token_mask")))
        check("status 含 uptime/log_file/activity",
              all(k in s for k in ("uptime", "log_file", "activity")), json.dumps({k: s.get(k) for k in ("uptime", "activity")}, ensure_ascii=False))
        check("log_file 指向 bridge-runtime/logs/bridge.log",
              s.get("log_file", "").replace("/", "\\").endswith("bridge-runtime\\logs\\bridge.log"))

        # T1 非流式活动
        print("T1 非流式请求 → 活动面板")
        st, r = chat("你好，请回一句话。")
        check("非流式 200 且有内容", st == 200 and (r["choices"][0]["message"]["content"] or "").strip() != "",
              (r.get("choices", [{}])[0].get("message", {}) or {}).get("content", ""))
        _, act = api("/admin/activity")
        mine = [it for it in act["recent"] if it["model"] == "GLM-5.3-Flash"]
        check("活动区记录了该请求且已 done", mine and mine[0]["stage"] == "done",
              json.dumps(mine[0], ensure_ascii=False) if mine else "无记录")
        check("done 记录含耗时", mine and mine[0]["elapsed"] is not None)
        rid1 = mine[0]["id"] if mine else None
        check("active 归零", act["active"] == 0)

        # T1b X-Request-Id 全链路（响应头 = 活动面板 id = 日志 rid）
        print("T1b X-Request-Id 全链路串联")
        req2 = urllib.request.Request(BASE + "/v1/chat/completions", method="POST")
        req2.add_header("Authorization", f"Bearer {TOKEN}")
        req2.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req2, json.dumps(
                {"model": "GLM-5.3-Flash",
                 "messages": [{"role": "user", "content": "reply ok"}]}).encode(),
                timeout=60) as rr:
            hdr_rid = rr.headers.get("X-Request-Id")
            rr.read()
        _, act2 = api("/admin/activity")
        check("响应头 X-Request-Id 为 8 位", bool(hdr_rid) and len(hdr_rid) == 8, str(hdr_rid))
        check("响应头 id 与活动面板条目一致",
              bool(hdr_rid) and any(it["id"] == hdr_rid for it in act2["recent"]), str(hdr_rid))

        # T2 流式活动
        print("T2 流式请求 → 阶段推进与首字延迟")
        st, raw = chat("[FAKE_SLOW] 你好", stream=True)
        check("流式 200 且含 [DONE]", st == 200 and "[DONE]" in raw)
        # done 终态由 worker 线程落定,与流收尾存在毫秒级竞态,轮询等待
        deadline_t2 = time.time() + 8
        while time.time() < deadline_t2:
            _, act = api("/admin/activity")
            mine = [it for it in act["recent"] if it["model"] == "GLM-5.3-Flash" and it["stream"]]
            if mine and mine[0]["stage"] == "done":
                break
            time.sleep(0.3)
        check("流式请求记录 done 且有首字延迟/字数",
              mine and mine[0]["stage"] == "done" and mine[0]["first_byte"] is not None and mine[0]["chars"] > 0,
              json.dumps(mine[0], ensure_ascii=False) if mine else "无记录")

        # T3 日志落盘
        print("T3 日志落盘")
        time.sleep(0.5)
        logtxt = open(LOG_FILE, encoding="utf-8").read() if os.path.exists(LOG_FILE) else ""
        check("bridge.log 已生成", os.path.exists(LOG_FILE))
        check("日志含 start/done 请求行", rid1 and f"[req {rid1}] start" in logtxt and f"[req {rid1}] done" in logtxt)

        # T4 结果持久化（一键测试 2 个模型：其一必失败——不存在的触发不了，
        # stub 对所有模型都成功，所以这里只验证成功路径 + /admin/results 读回）
        print("T4 一键测试结果持久化")
        st, t = api("/admin/test-all", "POST", {"models": ["GLM-5.3-Flash"], "prompt": "在吗"})
        check("test-all 受理", st == 200 and t.get("total") == 1)
        t0 = time.time()
        while time.time() - t0 < 30:
            _, tp = api("/admin/test-progress")
            if not tp["running"]:
                break
            time.sleep(0.4)
        check("测试完成", not tp["running"] and tp["finished"] == 1)
        st, res = api("/admin/results")
        gl = res["results"].get("GLM-5.3-Flash")
        check("结果写入 /admin/results", st == 200 and gl and gl.get("ok") is True, json.dumps(gl, ensure_ascii=False) if gl else "无")
        check("model_results.json 落盘", os.path.exists(RESULTS_FILE))

        # T5 错误分类
        print("T5 错误分类")
        st, e = chat("[FAKE_ERR] 测试错误")
        check("非流式服务错误 → 502 且中文提示", st == 502 and "网关错误" in e.get("detail", ""), e.get("detail", ""))
        st, raw = chat("[FAKE_ERR] 测试错误", stream=True)
        err_frame = [ln for ln in raw.splitlines() if ln.startswith("data:") and '"error"' in ln]
        check("流式错误帧含 type 与中文提示", err_frame and '"type"' in err_frame[0] and "网关错误" in err_frame[0],
              err_frame[0][:120] if err_frame else raw[:120])
        _, act = api("/admin/activity")
        failed = [it for it in act["recent"] if it["stage"] == "failed"]
        check("失败请求在活动面板可见", bool(failed), json.dumps(failed[0], ensure_ascii=False) if failed else "无")

        # T7 自愈回归：杀掉仿真桩进程
        print("T7 自愈回归（杀仿真桩）")
        pid = stub_pid_from_log()
        check("从日志取到 stub pid", bool(pid), str(pid))
        if pid:
            subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
            time.sleep(0.6)
            st, r = chat("杀桩后第一条")   # 应触发自愈重试
            check("杀桩后下一次请求自动恢复", st == 200 and "收到" in r["choices"][0]["message"]["content"], str(st))
            _, h = api("/health")
            check("恢复后 health.running", h["lingxi"]["state"] == "running", json.dumps(h["lingxi"]))

        print(f"\n== 结果：通过 {len(PASS)} 项，失败 {len(FAIL)} 项 ==")
        if FAIL:
            print("失败项：" + "、".join(FAIL))
        return 0 if not FAIL else 1
    finally:
        try:
            gw.terminate(); gw.wait(timeout=5)
        except Exception:
            gw.kill()
        gw_log.close()
        # 网关退出 → stdin EOF → stub 自退；兜底清一次
        subprocess.run(["taskkill", "/IM", "python.exe", "/FI", f"PID eq {os.getpid()}"], capture_output=True)


if __name__ == "__main__":
    sys.exit(main())
