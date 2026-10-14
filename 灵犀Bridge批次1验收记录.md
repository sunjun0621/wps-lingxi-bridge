# 灵犀 Bridge 批次 1（稳定性加固）验收记录

> 日期：2026-10-14 ｜ 执行：小灵 ｜ 方式：隔离端口 8856 全链路实测（全程未动 8799）
> 结论：**全部验收项通过** ✅（含核心项"杀 lingxi 后下一次请求自动恢复"）

---

## 一、改动清单（改动前已备份）

| 文件 | 备份 | 改动内容 |
|---|---|---|
| `bridge_gateway.py` | `bridge_gateway.py.bak-20261014` | ① `get_app()` 取用前存活检查（`proc.poll`+EOF），死进程自动重建；② 新增 `do_run()` 统一执行：瞬态失败自动复位重试一次（已产出内容不重试、但复位连接）；③ `/health`、`/admin/status` 返回 lingxi 真实状态；④ 启动端口探测（本程序在跑→中文提示退出；被占→中文报错）；⑤ 残留 lingxi 检测（仅提示不强杀）；⑥ 默认监听 127.0.0.1（`LINGXI_BRIDGE_HOST` 可覆盖）；⑦ 移除全部 CORS 头；⑧ 无令牌 401 友好提示（浏览器→中文 HTML，API→中文 JSON）；⑨ stdout 行缓冲（日志即时落盘） |
| `appserver_client.py` | `appserver_client.py.bak-20261014` | ① `AppServerError` 增加 `transient` 分类；② 新增 `is_alive()`（poll + stdout EOF 综合判断）；③ `stop()` 三级兜底（stdin EOF → terminate → kill）；④ 管道写失败包装为瞬态错误；⑤ stdout 关闭瞬间唤醒全部等待请求（不再干等超时）；⑥ `run_stream` 0.5s 轮询感知进程死亡（快速失败），保持总超时语义 |

未动：`lingxi.exe`、`models.json`（仅只读核对）、`console.html`、`qr_login.py`、`workbuddy_sync.py`。

---

## 二、验收结果总表

| # | 验收项 | 方法 | 结果 |
|---|---|---|---|
| 1 | **【核心】崩溃自愈** | 起网关 → 请求成功 → 强杀 lingxi(PID 9408) → 下一次请求 | ✅ **5.0s 自动恢复成功（200，"收到"），新 lingxi PID 14520，全程零人工干预** |
| 2 | /health 真实状态 | lingxi 死后访问 /health | ✅ 死时 `ok=false, state=dead, alive=false`；恢复后 `running`；不再"死的还报 ok" |
| 3 | /admin/status 增强 | 带令牌访问 | ✅ 含 `lingxi:{state,alive,pid}` 与 `host` 字段 |
| 4 | 单实例（二次启动） | 同端口再启一个进程 | ✅ 中文提示"灵犀 Bridge 已在运行（端口 8856）…"+控制台地址，退出码 0，不占端口 |
| 5 | 端口被其他程序占用 | 先占 8857 再启动 | ✅ 中文报错"端口 8857 已被其他程序占用…"+换端口指引，退出码 1 |
| 6 | 监听改 127.0.0.1 | netstat + 日志 | ✅ `Uvicorn running on http://127.0.0.1:8856`；`LINGXI_BRIDGE_HOST` 可覆盖 |
| 7 | 移除 CORS 通配头 | 核对响应头 | ✅ 全部响应无 `Access-Control-Allow-*`；跨域预检 OPTIONS → 401 拒绝 |
| 8 | 无令牌访问 401 友好提示 | 浏览器导航 / API 调用 | ✅ 浏览器（Accept: text/html）→ 401 中文提示页；API → 401 中文 JSON（含携带方式指引） |
| 9 | 控制台通道仍通 | 带 token 打开 `/` + `/admin/status` + `/v1/models` | ✅ 全 200（同源无需 CORS，不受影响） |
| 10 | WorkBuddy 通道仍通 | 带令牌 `POST /v1/chat/completions`（非流式+流式） | ✅ 非流式 200/5.4s；流式 SSE 完整（首字 2.75s、`[DONE]` 正常） |
| 11 | 流式场景自愈 | 杀 lingxi → 流式请求 | ✅ 7.1s 自动恢复，流式输出完整 |
| 12 | 流式中途断开快速失败 | 流式进行中强杀 lingxi | ✅ 杀后 **0.2s** 流即结束，返回错误帧「app-server 进程已退出（连接中断）」（原逻辑会干等 240s 超时）；下一次请求 6.5s 正常恢复 |
| 13 | 可选：残留 lingxi 提示 | 起裸 lingxi(PID 15508) 后启动网关 | ✅ 提示「检测到系统中已有 lingxi.exe 进程，PID 15508（可能是上次的残留）」+ 清理命令；仅提示不自动杀 |
| 14 | 无孤儿进程（回归） | 强杀网关进程 | ✅ lingxi 2.5s 内自随 stdin-EOF 退出，无残留 |
| 15 | 环境恢复 | 收尾检查 | ✅ 8799 / 8856 / 8857 全部释放；无 lingxi 残留；测试文件归档 `_cleanup_backup/batch1-20261014/` |

---

## 三、关键证据（网关日志摘录）

```
[self-heal] 检测到 lingxi 进程已退出（exit=1），自动重启        ← 杀 lingxi 后首次请求触发
INFO:  127.0.0.1:50493 - "POST /v1/chat/completions" 200 OK    ← 自动恢复成功（5.0s）

[提示] 检测到系统中已有 lingxi.exe 进程，PID 15508（可能是上次的残留）。
       如稍后遇到异常，可在任务管理器结束它，或执行：taskkill /IM lingxi.exe /F
```

/health 实测（死亡瞬间即反映）：
```json
{"ok": false, "service": "lingxi-bridge", "models": 12,
 "lingxi": {"state": "dead", "alive": false, "pid": 9408}}
```

---

## 四、边界说明（如实记录）

1. **流式已产出内容后断开**：不自动重试（避免客户端收到重复内容），返回中文错误帧；连接已复位，**下一次请求必定恢复正常**（已实测）。
2. 中途断开测试在最终回归轮（T7）因短文本输出过快未复现触发窗口，但同场景已在 T4b 完整实测通过（见上表 #12），两轮代码一致。
3. 重试语义：非流式或"尚未有输出"阶段的瞬态失败 → 复位+重试一次；重试仍失败 → 报错（连接已复位）。
4. 单实例判断依据 `/health` 的 `service` 字段（兼容旧版本网关的 /health 响应）。
5. 测试期间产生少量灵犀额度消耗（若干短对话，均 ≤200 字输出）。

---

## 五、测试现场归档

- 测试脚本与完整输出：`_cleanup_backup/batch1-20261014/`（`_t1_gw.log` 为第一轮网关全日志，`_t6_gw2.log` 为最终代码轮日志）
- 备份文件：`bridge_gateway.py.bak-20261014`、`appserver_client.py.bak-20261014`（项目根目录）
- 回滚方式：将 `.bak-20261014` 文件覆盖回原名即可（测试归档内亦有完整脚本可复跑）
