# 灵犀 Bridge 操作清单（验证版）

> 2026-10-14 ｜ 配合《灵犀Bridge优化方案.md》使用
> 用法：按批次从上到下执行。每批末尾的【AI 提示词】整段复制到 WorkBuddy 新对话即可开工；每批独立验收、可随时叫停。
> 所有批次均为项目内文件改动（不涉及系统级安装），沙箱内即可完成；建议每批完成后叫小灵复跑一次"隔离端口 8855 全流程实测"。

---

## 〇、本次验证结论（先看这里）

已在隔离端口 8855 上做过真实运行验证（未动 8799，结束已清理），结论：

| # | 结论 | 结果 |
|---|---|---|
| 1 | **崩溃不自愈（实锤）** | 杀 lingxi.exe 后连续 3 次请求均 0.02 秒返回 500 "Internal Server Error"，无自动恢复；重启网关才恢复 |
| 2 | **/health 是浅检查** | lingxi 已死仍返回 `{"ok":true}`，监控/单实例判断都不可靠 |
| 3 | 无令牌访问 | 当前版本正确返回 401（旧版 e2e 记录的 500 已不适用）|
| 4 | 监听 0.0.0.0 | 实测确认，局域网可访问 |
| 5 | 固定令牌 lingxi-bridge | 确认（与已导入模型的 apiKey 一致，改了要重导入）|
| 6 | 全局串行 / 无日志 / 结果不持久化 | 全部确认 |
| 7 | **孤儿进程风险：不成立** | lingxi.exe 在 stdin 关闭后 0.5 秒内自行退出（原判断下调）|

**对方案的三处修正**：① P0-2「退出清理」降级为可选防御项；② P0-4a「500 问题」更正为已正确返回 401；③ 新增「/health 浅检查」发现，并入 P0-1/P1-5 一并修。

---

## 一、通用执行守则（每批都适用）

1. **先备份**：改动涉及的每个文件先复制 `.bak-20261014`；目录整理前先列迁移清单。
2. **完工自测**：启动 → /health → 控制台 → 一键测试 → 真实请求（可选）全链路走一遍，输出验收记录。
3. **收尾**：更新《灵犀Bridge使用说明.md》与项目 memory 的改动清单。
4. **不越界**：每批只做本批范围；不动 lingxi.exe、不删任何文件（敏感文件只迁移）。
5. **按需恢复导入**：当前 models.json 灵犀条目只剩 1 条（GLM-5.3-Flash），如需恢复 11 个模型，在控制台重新勾选导入即可（不需要时可跳过）。

---

## 二、批次 1「稳」（建议先做）

**包含**：P0-1 崩溃自愈【核心】/ P0-3 单实例与端口提示 / P0-4 安全快修 / `/health` 真实探活

**验收**：杀掉 lingxi.exe 后下一次请求自动恢复；/health 反映真实连接状态；重复启动有中文提示；非本机不可访问、无令牌有友好提示。

【AI 提示词】
```
执行「灵犀 Bridge」优化批次 1（稳定性加固）。
项目目录：C:\Users\Administrator\Documents\deepseek-harness\lingxi-reverse-2
参考文档：项目根目录《灵犀Bridge优化方案.md》批次 1 + 六、验证记录。
待修内容（均已实测确认）：
1)【核心】app-server 崩溃自愈：修改 bridge_gateway.py 的 get_app() 与 appserver_client.py——取用前检查子进程存活（proc.poll()），死进程自动 reset_app() 并重启、重试一次；请求过程中管道断开（OSError/BrokenPipe）或超时时同样触发复位重试。【验收：启动网关后强杀 lingxi.exe，下一次对话请求能自动恢复成功】
2) /health 与 /admin/status 增强：返回 lingxi 真实连接状态（当前 lingxi 死后仍报 ok，不可信）。
3) 单实例与端口占用：启动前探测端口（默认 8799）：若是本程序在跑 → 中文提示"已在运行"并退出；否则中文报错。【验收：二次启动给出提示】
4) 安全快修：① 监听默认改 127.0.0.1（保留 LINGXI_BRIDGE_HOST 环境变量可覆盖）；② 移除 CORS 通配头（控制台同源不受影响，改后实测控制台+WorkBuddy 双通道仍通）；③ 无令牌访问返回友好提示（401）。
5)（可选）启动时检测残留 lingxi 并提示清理（极端卡死场景保险）。
要求：改前备份（.bak-20261014）；改完全链路自测并输出验收记录；不动 lingxi.exe、不改 models.json。
```

---

## 三、批次 2「看得见」（体验收益最大）

**包含**：P1-1 活动面板 / P1-2 日志落盘 / P1-3 结果持久化 / P1-4 错误分类 / P1-5 状态区

**验收**：WorkBuddy 发消息时控制台显示"进行中 → 完成+耗时+首字延迟"；日志文件生成并轮转；刷新页面测试结果仍在；lingxi 断开时控制台有中文红字指引。

【AI 提示词】
```
执行「灵犀 Bridge」优化批次 2（可观测与体验）。
项目目录：C:\Users\Administrator\Documents\deepseek-harness\lingxi-reverse-2
参考文档：项目根目录《灵犀Bridge优化方案.md》批次 2。
待做内容：
1) 实时活动面板：网关内存记录在途与最近 20 条请求（模型、阶段[排队/等待上游/收到内容/完成/失败]、开始时间、首字延迟、输出字数、错误摘要），新增 GET /admin/activity；console.html 新增"活动"区块（2 秒轮询）。【验收：从 WorkBuddy 发一条消息，控制台可见该请求从"进行中"到"完成+耗时"】
2) 日志落盘：关键事件与请求记录写 bridge-runtime/logs/bridge.log（5MB 轮转、保留 1 份）；控制台加"打开日志目录"按钮。
3) 结果持久化：一键测试与单聊结果写 bridge-runtime/state/model_results.json；控制台加载时恢复徽标（可用/失败/耗时）。【验收：刷新页面结果仍在】
4) 错误分类：把 lingxi 断开、登录失效、超时、限流、网关错误映射为中文分类提示（例："灵犀连接已断开，正在自动恢复"/"登录已失效，请扫码登录"），控制台与 API 响应均体现。
5) 状态区增强：/admin/status 增加端口、令牌掩码、运行时长、lingxi 真实连接状态、活动/队列数；console 展示。
要求：改前备份；改完全链路自测（含杀掉 lingxi 看控制台提示）并输出验收记录；不动 models.json。
```

---

## 四、批次 3「齐」（目录分层与工程化）

**包含**：P3-1 目录分层（gateway / tools / secrets）/ P3-2 依赖自检 / P3-3 配置集中

**验收**：整理后双击 bat 全链路通过；缺依赖有中文安装提示；改配置文件端口生效。

【AI 提示词】
```
执行「灵犀 Bridge」优化批次 3（目录分层与工程化）。
项目目录：C:\Users\Administrator\Documents\deepseek-harness\lingxi-reverse-2
参考文档：项目根目录《灵犀Bridge优化方案.md》批次 3。
待做内容：
1) 目录分层（只移动、不删除）：
   - gateway/：bridge_gateway.py、console.html、appserver_client.py、qr_login.py、workbuddy_sync.py、plans.json
   - secrets/：cookies_decrypted.json、_Cookies.db、account_login.html、account_probe.txt 等账号敏感文件
   - tools/：01~18 编号脚本及 find_*/extract_*/probe 等全部逆向研究脚本、实验记录 txt
   - bridge-runtime/、appserver/、extracted/ 保持原位
   - 同步更新：启动灵犀Bridge.bat 入口路径；bridge_gateway.py 内部 ROOT 逻辑改为"gateway 的上一层为项目根"（bridge-runtime、appserver 引用随之修正）
2) 依赖自检：新增根 requirements.txt（fastapi/uvicorn/requests）；启动时检测缺包并输出清华源安装命令。【注意：实测依赖装在系统 Python 3.13.14；确认 bat 的 python 解析一致】
3) 配置集中：新增 bridge-runtime/gateway.json（port/token/host/并发/timeout/日志开关），优先级 env > 文件 > 默认。
【验收：整理后双击 bat 全链路通过：启动→健康→控制台→一键测试→真实请求；缺包场景提示可读】
要求：迁移前 grep 核对无遗漏引用；迁移后跑全链路自测；敏感文件只移动不删除、不打印内容。
```

---

## 五、批次 4「强」（功能增强）

**包含**：P2-1 并发 / P2-2 模型清单配置化 / P2-4 超时可配 / P2-5 流式单聊+停止 / P2-6 同步细节 /（可选）P2-3 会话提速实验

**验收**：两并发请求不互相阻塞或有排队提示；新增模型改 JSON 即生效；单聊流式可停止；断连后上游取消。

【AI 提示词】
```
执行「灵犀 Bridge」优化批次 4（功能增强）。
项目目录：C:\Users\Administrator\Documents\deepseek-harness\lingxi-reverse-2
参考文档：项目根目录《灵犀Bridge优化方案.md》批次 4。
待做内容：
1) 并发实测与改造：先写脚本实测 lingxi 对 2~3 个并发 run 的承受度（记录成功率/耗时/是否限流，短提示词）；通过则把全局 _run_lock 改为信号量+队列（默认并发 2，可配置），超限请求排队并在控制台显示排队数；不通过则保留串行并显示"排队中"提示。
2) 模型清单配置化：模型清单移入 bridge-runtime/models.json（key/名称/档位，内置兜底）；支持热重载（POST /admin/reload-models）。【验收：改 JSON 即生效】
3) 超时可配置：请求/流式超时移入配置（默认 240 秒，可调）；流式有内容输出时不判超时。
4) 流式单聊 + 停止：控制台单聊改流式显示；加"停止"按钮（先探明 appserver 是否有 run 取消 RPC；无则前端断开并尽力终止上游）。
5) 同步细节：记忆 WorkBuddy 配置路径（写入 gateway.json）；写入 models.json 前重读检测并发修改；Windows 下 os.replace 重试；导入后提示"重启 WorkBuddy 生效"。
6)（可选实验）会话复用提速：对话指纹→session_id 复用，做 3 轮对比实验（新建 vs 复用耗时），用开关控制、默认关；无显著收益或偶发串话则放弃。
要求：每项独立小步完成+自测；并发实验先出数据再改代码；改前备份。
```

---

## 六、批次 5「探索」（工具调用 spike）

**包含**：P4-1 工具调用可行性评估（先 spike 后立项）；P4-2 图片输入可并入其后。

**验收**：产出可行性报告（含真实协议样本、改造点、风险与工作量），再决定是否完整实现。

【AI 提示词】
```
执行「灵犀 Bridge」探索 spike：工具调用可行性评估（不改生产代码）。
项目目录：C:\Users\Administrator\Documents\deepseek-harness\lingxi-reverse-2
目标：探明 lingxi.exe（app-server）cowork 协议中"工具调用/权限审批"能力，评估把 WorkBuddy 条目升级为 supportsToolCall=true 的可行性与改造点。
方法：
1) 用 appserver_client.py 建会话，构造带工具/权限语义的输入（探索 permission_mode、bash_approval、skill_management、tools 等字段真实用法），抓 5+ 组真实通知帧落盘到 samples/。
2) 判定：模型能否接收工具定义、发出工具调用、等待工具结果并继续（对应 WorkBuddy function-calling 回路）；权限审批帧能否对接。
3) 产出《工具调用 spike 报告》：结论（可行/不可行/部分可行）、证据样本、改造点清单、风险与工作量。
注意：只读研究，不改动 bridge_gateway.py 现有行为；额度消耗最小化（短提示词）；结束后恢复现场。
```

---

## 七、默认决策（按建议已预设，可随时改）

| 决策点 | 建议默认 | 说明 |
|---|---|---|
| 批次范围 | 1 → 2 → 3 → 4，批次 5 先 spike | 若先试水可只做 1+2 |
| 令牌策略 | **保留** `lingxi-bridge` | 绑定收紧到 127.0.0.1 + 去 CORS 后本机风险已低；改随机令牌需重导入 WorkBuddy，列为可选 |
| P2-3 会话提速 | 列为可选实验 | 先出对比数据再决定，默认关闭 |
| P3-4 托盘/后台 | 暂缓 | 保持 bat + 浏览器控制台形态 |
| P4 探索 | 建议做 spike | 先评估可行性再立项 |

---

*本清单基于 2026-10-14 实测验证；方案细节与变更依据见《灵犀Bridge优化方案.md》。*
