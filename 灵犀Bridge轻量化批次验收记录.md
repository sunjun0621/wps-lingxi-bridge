# 灵犀 Bridge 轻量化批次验收记录（X-Request-Id → 配置 → 依赖 → reqlog → 探测）

> 日期：2026-10-14 ｜ 执行：ZCode ｜ 方式：每步独立验收脚本（`tests/e2e_*.py`,隔离端口/隔离运行目录,仿真桩）+ 真实上游复测
> 结论：**5 步全部完成,累计 86 项断言全过**（19+10 为本批次新增脚本,24/18/15 为回归）

---

## 一、五步改动清单

| 步骤 | 功能 | 落地 |
|---|---|---|
| 1 | **X-Request-Id 全链路** | 中间件为每请求生成 8 位 id：响应头 + 日志行（`[req …]`）+ 活动面板条目同 id；E2E 固化 T1b 断言 |
| 2 | **配置集中 gateway.json** | `bridge-runtime/gateway.json`(可选) + 环境变量,优先级 **env > 文件 > 默认**;7 键（port/host/token/timeout/test_timeout/log_enabled/log_max_mb）;启动逐项打印生效来源;/admin/status 返回来源;控制台状态行显示超时+悬停配置文件路径;根目录 `gateway.example.json` 模板 |
| 3 | **依赖自检** | 启动时 `_dep_check()`:缺核心包（fastapi/uvicorn/requests）→ 中文提示 + 清华源安装命令 + 退出码 1,不再裸 traceback;缺可选包（pywin32/cryptography）→ 一行用途提示不阻断;bat 增加 python 缺失检查;`check_deps.py` 升级为中文全量体检 |
| 4 | **reqlog 结构化请求日志** | 请求终态落一行 JSON 到 `bridge-runtime/logs/reqlog.jsonl`（只元数据不记正文）;2MB 轮转 + 30 天清理（均可配）;`GET /admin/reqlog`;控制台活动区「历史」切换（跨重启保留）;顺带把断连检测升级为 `request.is_disconnected()` + `run_stream(cancel_event)`,断连 0.5s 内终止上游并以 `kind=client_gone` 如实记录 |
| 5 | **探测升级** | 一键测试采集**首字延迟 / 输出字数 / 生成速率**（rate = chars / (elapsed − ttfb)）;随结果持久化到 model_results.json;控制台徽标/耗时列悬停显示「首字 4.14s · 输出 30 字 · 约 17 字/秒」;默认探测提示词改为 30 字简介（原"回复两个字"无法测速率） |

---

## 二、验收结果

### 新增脚本

| 脚本 | 项数 | 结果 |
|---|---|---|
| `tests/e2e_config.py`(步骤 2) | 18 | ✅ 全部通过（含 log_enabled=false 按 rid 精确断言不落盘;env 逐键覆盖;默认回落+启动打印） |
| `tests/e2e_deps.py`(步骤 3) | 15 | ✅ 全部通过（find_spec 补丁模拟缺包：阻断/提示/无 traceback/未进入后续导入） |
| `tests/e2e_reqlog.py`(步骤 4) | 19 | ✅ 全部通过（写入/不记正文/轮转/保留期清理/查询倒序/开关） |
| `tests/e2e_probe.py`(步骤 5) | 10 | ✅ 全部通过（指标齐全/落盘/速率口径自洽/失败路径无指标） |

### 回归（全部通过）

| 脚本 | 项数 | 结果 |
|---|---|---|
| `tests/e2e_batch2.py` | 24 | ✅（含新增 T1b X-Request-Id 断言） |
| `tests/e2e_config.py` / `e2e_deps.py` / `e2e_reqlog.py` 全量复跑 | 52 | ✅ |

### 真实上游实测（8799,真实 lingxi.exe）

- 配置来源打印：`端口 8799(默认) | … | 请求历史 开(默认) · 2MB/30天`
- 真实请求 → reqlog 正确落盘（`a8d28427 GLM-5.3-Flash done 4.62s`）
- 真实探测（30 字提示词）：GLM-5.3-Flash 首字 4.14s / 30 字 / 17.0 字/秒;kimi-k3 首字 8.06s / 29 字 / 12.9 字/秒
- 控制台（浏览器实测）：状态行「超时 240s」+ 配置悬停;活动区「历史」切换返回 16 条持久记录;徽标悬停「首字 4.14s · 输出 30 字 · 约 17 字/秒」

---

## 三、边界与说明

1. 测试隔离：配置/reqlog/probe 验收均用隔离端口（8893-8897）+ 临时运行目录（`LINGXI_BRIDGE_RUNTIME_DIR`）,不碰真实运行数据;`e2e_config` 对真实 `gateway.json` 先备份后还原。
2. 新增配置项 `LINGXI_BRIDGE_RUNTIME_DIR` 仅用于隔离测试,文档未对用户宣传（属测试基建）。
3. 探测速率为**近似值**（按字符数计,未 tokenize;`elapsed − ttfb` 为生成窗口）,用途是横向对比模型快慢,不作精确吞吐承诺。
4. reqlog 只记元数据,不记对话内容;文件在 gitignore 的 `bridge-runtime/` 内,不会入库。
5. 复跑全部验收：`python tests/e2e_batch2.py && python tests/e2e_config.py && python tests/e2e_deps.py && python tests/e2e_reqlog.py && python tests/e2e_probe.py`（约 3-4 分钟）。
