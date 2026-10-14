# 灵犀 Bridge 批次 2（可观测与体验）验收记录

> 日期：2026-10-14 ｜ 执行：ZCode ｜ 方式：**隔离端口 8891 + 协议仿真桩**离线全链路实测（全程未动 8799，无灵犀额度消耗）
> 结论：**22/22 验收项全部通过** ✅
> 背景说明：旧工作副本 `lingxi-reverse-2` 已删除、本机无 WPS 灵犀桌面端 `app-server/lingxi.exe` 运行件，
> 本轮改用自研仿真桩 `tests/fake_lingxi.py`（严格按 stdio JSON-RPC 帧协议应答，可注入错误/慢速/崩溃场景）完成验收。
> 真实 lingxi.exe 场景的协议行为批次 1 已实测确认过，仿真桩复刻同款帧序，自愈/超时语义不受影响。

---

## 一、改动清单（新增 P1-1 ~ P1-5）

| 文件 | 改动内容 |
|---|---|
| `bridge_gateway.py` | ① **活动记录**：`activity_start/stage/chars/snapshot`，内存保存在途 + 最近 20 条（模型/阶段/首字延迟/耗时/字数/错误摘要），新增 `GET /admin/activity`；② **日志落盘**：`log_line()` 同写 stdout 与 `bridge-runtime/logs/bridge.log`（5MB 轮转保留 1 份），启动横幅打印日志路径，关键事件（请求起止/自愈/lingxi 连接/落盘失败）全覆盖；③ **错误分类**：`classify_error()` 按优先级链映射 断连→登录失效→超时→限流→网关错误，非流式 502 与流式错误帧均输出中文指引 + `type` 字段；④ **结果持久化**：一键测试逐模型原子落盘 `bridge-runtime/state/model_results.json`（tmp+rename），新增 `GET /admin/results`；⑤ **状态增强**：`/admin/status` 增加 `token_mask` / `uptime` / `started_at` / `log_file` / `activity.active`；⑥ 新增 `POST /admin/open-logs`（资源管理器打开日志目录）；⑦ 非流式路径补记输出字数 |
| `console.html` | ① 服务状态行显示 **灵犀真实状态徽标**（待启动/已连接/已断开-红）与 主机:端口·令牌掩码·运行时长；② 新增 **活动区块**（2 秒轮询 `/admin/activity`，模型/阶段彩色标签/耗时或首字/字数，失败行悬停显示错误详情）；③ **「打开日志目录」按钮**；④ 加载时从 `/admin/results` **恢复历史测试徽标**（可用/失败·分类/耗时）；⑤ 一键测试失败徽标 title 带中文分类提示 |
| `tests/fake_lingxi.py` + `tests/lingxi_stub.bat` | 新增协议仿真桩：模拟 initialize/login/session/run 帧序；`[FAKE_ERR]` 注入服务错误、`[FAKE_SLOW]` 慢速分片、`[FAKE_QUIT]` 崩溃场景（预留） |
| `tests/e2e_batch2.py` | 新增 E2E 驱动（隔离端口 8891，7 组 22 断言），回归批次 1 自愈能力 |

顺带修复（批次 2 验收中发现）：
- 流式 worker 原先 `q.put(("error", str(e)))` 丢失 `transient` 标志，导致「连接断开」被误分类为「网关错误」→ 改为传异常对象本身。
- SSE error 帧（对照清单 §2.1 观察项）仍按主人决定**未加 `[DONE]`**，仅补了分类与 `type` 字段；令牌非常量时间比较（§2.2）亦维持原状未动。

未动：`appserver_client.py`、`qr_login.py`、`workbuddy_sync.py`、`models.json`、`lingxi.exe`（本机不存在）。

---

## 二、验收结果（tests/e2e_batch2.py，22/22 通过）

| # | 验收项 | 结果 |
|---|---|---|
| T0 | 网关 20s 内就绪（隔离端口 8891 + 仿真桩注入 `LINGXI_BRIDGE_EXE`） | ✅ |
| T6-1 | `/admin/status` 含 `token_mask`（`ling****`） | ✅ |
| T6-2 | `uptime` / `log_file` / `activity` 字段齐备 | ✅ |
| T6-3 | `log_file` 指向 `bridge-runtime/logs/bridge.log` | ✅ |
| T1-1 | 非流式请求 200 且有内容 | ✅ |
| T1-2 | 活动区记录该请求且推进到 done | ✅ |
| T1-3 | done 记录含耗时 | ✅ |
| T1-4 | 请求结束后 `active` 归零 | ✅ |
| T1-5 | 非流式 done 记录含输出字数（chars=22） | ✅ |
| T2-1 | 流式 200 且以 `[DONE]` 收尾 | ✅ |
| T2-2 | 流式 done 记录含首字延迟（0.0s）与字数（22） | ✅ |
| T3-1 | `bridge.log` 自动生成 | ✅ |
| T3-2 | 日志含 `[req …] start` / `done` 行 | ✅ |
| T4-1 | `/admin/test-all` 受理并完成 | ✅ |
| T4-2 | 结果写入 `/admin/results`（ok=true） | ✅ |
| T4-3 | `model_results.json` 原子落盘 | ✅ |
| T5-1 | 非流式服务错误 → 502 中文提示「网关错误：…」 | ✅ |
| T5-2 | 流式错误帧含中文提示与 `type` 字段 | ✅ |
| T5-3 | 失败请求在活动面板可见（failed 阶段） | ✅ |
| T7-1 | 从日志取到桩进程 pid | ✅ |
| T7-2 | 强杀桩后下一次请求自动恢复（200，批次 1 自愈不回退） | ✅ |
| T7-3 | 恢复后 `/health` 回到 running（新 pid） | ✅ |

**控制台侧验证**（人工核对 console.html 逻辑）：活动区块渲染/彩色阶段标签/日志按钮/徽标恢复的 JS 与新增端点一一对应；HTML 解析通过；暗色主题沿用现有变量无新增硬编码色值。

---

## 三、边界说明（如实记录）

1. **验收方式差异**：本轮为仿真桩离线验收，未消耗灵犀额度；真实上游下的首字延迟量级（秒级）与限流分类（429）路径未覆盖——`classify_error` 的限流分支按 workbuddy2api 经验实现，待有真实运行件后回归确认。
2. **观察项维持原判**：SSE error 帧后缺 `[DONE]`、令牌 `==` 比较，两处按主人既定决定未修，仅在错误帧上补了分类信息。
3. `bridge-runtime/` 运行产物（logs/state）已 gitignore，测试后已清理，现场干净。
4. 复跑方式：`python tests/e2e_batch2.py`（自动起停网关与仿真桩，约 40 秒）。

---

## 四、真实上游回归（2026-10-14 晚间补充，灵犀桌面端已安装）

> 运行件从 `C:\Program Files\lingxi-desktop\resources\app-server\app-server-windows-amd64.zip`（v4.27.0）
> 解压至项目 `appserver/`；`wps_sid` 用 08_cookies 同款方法从客户端 `Partitions/*/Network/Cookies`
> 提取（Chrome 130+ 明文前 32 字节为 host 绑定摘要，须剥离，否则 sid 损坏报"登录已失效"）。

### 真实回归结果（全部通过）

| # | 项目 | 结果 |
|---|---|---|
| 1 | 非流式 GLM-5.3-Flash / DeepSeek V4 Flash / V4.1 / Qwen3.8 / Kimi-K3 / Doubao(含 effort=high) | ✅ 全部 200，3.0~5.8s |
| 2 | 流式 GLM-5.3（effort=low / max） | ✅ `[DONE]` 收尾，首字 5.8s |
| 3 | 批次 1 自愈（杀 lingxi.exe 后下一请求） | ✅ 0.09s 内自动恢复，新 pid 重连 |
| 4 | 一键测试 + 结果持久化 + 控制台徽标恢复（浏览器实测） | ✅ |

### 真实回归发现并修复的 2 个 bug

| # | 问题 | 根因 | 修复 |
|---|---|---|---|
| B1 | 客户端断开后，流式请求的活动记录**永远停在 content**，且上游 run 白跑到 240s 超时 | 消费者 generator 被客户端断开杀死后，终态由它转发的设计导致 worker 的最终状态永远丢失；且无断开止损 | ① 终态改由 **worker（生产者）侧落定**；② generator `finally` 置位 `client_gone`，worker 的 `on_text` 收到下一个 delta 时抛瞬态错误**终止上游 run**（已有产出不重试） |
| B2 | worker 先写 `done` 终态后，消费者处理队列中**残留 text 帧**把 stage 覆盖回 content（e2e 偶发 21/22 的根因） | `activity_stage` 允许任意回写 | 加**单调守卫**：终态（done/failed）之后忽略 queued/upstream/content 的回退写入 |

修复后：仿真桩 E2E **22/22 全绿**；真实上游断开止损实测——客户端断开后 run 立即终止、activity 落 `done`、锁释放、下一请求不受影响。

### 边界更新

- 原第 1 条边界（限流 429 分类路径未覆盖）仍然成立：本轮全部请求成功，未触发限流。
- `lingxi.exe` 上游存在**偶发"停发 run.end"挂死**（15k 字后停止输出但不断开，直连 app-server 亦复现不出规律，属云端行为）；现有 240s 总超时兜底会在超时后复位重连，客户端断开止损（B1 修复）另提供一层保护。
