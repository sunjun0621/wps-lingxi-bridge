# 灵犀 Bridge 使用说明

把 **WPS 灵犀订阅**里可用的模型（DeepSeek / Qwen / GLM / Kimi / MiMo / MiniMax / 豆包）
通过本地 `lingxi.exe`（app-server）反代成 **OpenAI 兼容接口**，提供可视化控制台：
账号扫码登录、思维等级选择、一键测试、一键导入 WorkBuddy；dsh 也可手动接入。

> 仅用于个人学习、调用本人订阅额度。请勿公开、转售、共享令牌或含凭证文件。

---

## 一、快速开始

1. 双击 **`启动灵犀Bridge.bat`**
2. 约 4 秒后浏览器自动打开控制台：`http://127.0.0.1:8799/?token=lingxi-bridge`
3. 左侧确认账号已登录；勾选模型 →（可选）一键测试 → 点击「导入 WorkBuddy」
4. 打开 WorkBuddy，选用「… · 灵犀」模型即可
5. 关闭命令行窗口即停止服务

---

## 二、左侧：灵犀账号与扫码登录

- 显示当前账号**头像、昵称、UID、手机号、会员状态**与登录状态灯；每 60 秒自动刷新
- **登录失效会自动展开二维码**（账号卡片变红时），点都不用点；
  也可手动点 **「扫码登录 / 切换账号」**：
  1. 下方出现登录二维码（用 **WPS 手机 APP** 扫码）
  2. 状态依次提示：请扫码 → 已扫码，请在手机上确认 → 登录成功
  3. 后端自动用授权码换取新的 `wps_sid`，保存并**自动重连** lingxi，无需重启
  - 二维码超过约 2 分钟未扫会提示「可能已过期」，点「刷新二维码」即可
- 新 sid 写入 `current_sid.txt`（优先级高于 cookies_decrypted.json）
- 启动网关时也会在窗口预检登录态：有效报账号、失效直接提示去扫码

> 说明：取码与轮询已实测；完整「扫码→确认→自动换 sid→重连」链路请你首次扫码时
> 留意状态提示是否依次走到「登录成功」，如遇红字发我即可定位。

---

## 三、思维等级（reasoning effort）

灵犀的思维等级为**三档**（不是常见的五档）：

| 等级 | 含义 |
|---|---|
| `low`（低） | 思考最少、最快 |
| `high`（高） | 较强推理 |
| `max`（Max） | 最充分思考（实测会输出完整思维链并自我纠错） |

- **思考强度在使用侧选择**：控制台不再设档位；导入 WorkBuddy / ZCode 的条目自带档位元数据，
  在 WorkBuddy 里直接切换低 / 高 / Max（默认高）
- **MiMo、MiniMax 为「自适应思考」**，不提供手动等级
- OpenAI 接口仍可直接透传：请求体顶层 `"reasoning_effort":"high"`，或 `"reasoning":{"effort":"high"}`（不支持的档位自动忽略）

---

## 四、一键测试全部模型

- 勾选要测的模型（支持 **全选 / 反选 / 清空**），点 **「一键测试已勾选」**
- 后端串行逐个发送极简请求（云端默认档位），模型行实时标记 **可用 / 失败、耗时**，结束后汇总
- 实测 11 个模型全部可用，耗时约 3.9–23.7 秒（首轮含启动会偏慢）

---

## 五、模型清单（11 个，另有 auto 不导入）

| 模型 key | 名称 | 思维等级 |
|---|---|---|
| `deepseek-v4-flash-0731` | DeepSeek V4 Flash | low/high/max |
| `deepseek-v4.1-flash` | DeepSeek V4.1 Flash | low/high/max |
| `deepseek-v4-pro-0813` | DeepSeek V4 Pro | low/high/max |
| `qwen3.8_flash` | Qwen3.8-Flash | low/high/max |
| `qwen3.8_max` | Qwen3.8-Max | low/high/max |
| `mimo-v2.6-pro` | Xiaomi MiMo-V2.6 Pro | 自适应 |
| `GLM-5.3-Flash` | GLM-5.3-Flash | low/high/max |
| `GLM-5.3` | GLM-5.3 | low/high/max |
| `minimax_m3` | MiniMax-M3 | 自适应 |
| `doubao_seed_2_1_pro_260628` | Doubao-Seed-2.1 Pro | low/high/max |
| `kimi-k3` | Kimi-K3 | low/high/max |

接口：
- `GET  /v1/models`（每模型含 `reasoning_efforts`）
- `POST /v1/chat/completions`，支持 `stream:true`（SSE，思维链在 `reasoning_content`）
- 令牌：`Authorization: Bearer lingxi-bridge`

### 在 WorkBuddy 中选择思维强度

导入 WorkBuddy 的模型条目自带思考强度元数据（机制对齐 OW-Bridge）：

- 9 个有档位模型（DeepSeek / Qwen / GLM / Doubao / Kimi）在 WorkBuddy 里可直接切换**低 / 高 / Max**（默认高）
- MiMo、MiniMax 为自适应思考，导入条目无手动档位（`supportsReasoning` 声明、空档位列表）
- 切换后 WorkBuddy 请求自动带 `reasoning_effort`，网关透传给灵犀；不支持的档位（如 medium）自动忽略、用云端默认，不会报错
- **导入或重新导入后需重启 WorkBuddy** 才能加载新的模型能力字段

---

## 六、手动接入 dsh（DeepSeek Harness）

- **Base URL**：`http://127.0.0.1:8799/v1`
- **API Key**：`lingxi-bridge`
- **Model**：填任一 key，如 `deepseek-v4-pro-0813`、`kimi-k3`、`GLM-5.3`

---

## 七、关于多轮对话

网关无状态：每次请求把完整 `messages` 渲染为一次输入并新建灵犀会话，上下文完整、不串会话。
当前聚焦**纯文本对话**（导入条目 `supportsToolCall=false`、`supportsImages=false`），
函数调用与图片输入为后续增强项。

---

## 八、登录态的维护（推荐全程只用扫码）

**推荐方式：控制台扫码。** 纯网页接口，不依赖任何客户端；扫码后自动换新 `wps_sid`、
写回 `current_sid.txt` 并重连，无需重启网关：

1. 登录失效时控制台会**自动展开二维码**并提示（账号卡片变红自动引导）
2. 用 **WPS 手机 APP** 扫码 → 手机确认 → 完成
3. 二维码放太久（约 2 分钟）未扫会提示「可能已过期」，点「刷新二维码」即可

其它方式（一般用不到）：
- `08_cookies.py`：从 WPS 灵犀**客户端**本地数据解密提取——需要客户端在本地；
  客户端已卸载时脚本会给出提示并引导改用扫码
- 临时指定：`set LINGXI_SID=你的sid` 后 `python bridge_gateway.py`

> 关于灵犀桌面客户端：**本桥的日常使用不需要它**。运行件是项目内自带的 `lingxi.exe`
> 拷贝（见「九、文件说明」的 `appserver/`），启动时会自动做登录态预检并打印结果；
> 客户端可随时卸载，卸载后登录/续期完全走上面的扫码流程。

环境变量：
- `LINGXI_BRIDGE_PORT`：端口（默认 8799）
- `LINGXI_BRIDGE_TOKEN`：访问令牌（默认 lingxi-bridge）
- `LINGXI_BRIDGE_HOST`：监听地址（默认 `127.0.0.1` 仅本机；如需局域网访问改为 `0.0.0.0`）
- `LINGXI_BRIDGE_EXE`：app-server 可执行文件路径（覆盖默认 `appserver/` 布局；离线测试注入用）

安全说明：网关默认仅监听本机（局域网不可达）；除 `/health` 外所有接口需令牌；
无令牌打开页面会显示中文提示页；控制台与网关同源，不依赖 CORS。

---

## 八·补、控制台新增能力（批次 2）

- **活动面板**：主界面新增「活动」区，2 秒刷新。从 WorkBuddy 发消息时能看到该请求
  从「等待上游 → 已收到内容 → 完成/失败」的推进、耗时、首字延迟与输出字数（保留最近 20 条）。
- **日志落盘**：关键事件写入 `bridge-runtime/logs/bridge.log`（5MB 轮转保留 1 份），
  活动区右上角「打开日志目录」可直达。
- **测试结果持久化**：一键测试结果保存到 `bridge-runtime/state/model_results.json`，
  刷新页面后徽标（可用/失败·原因/耗时）仍在。
- **探测指标**：一键测试同时探测每个模型的**首字延迟 / 输出字数 / 生成速率**（默认提示词为
  "请用一句话（30 字以内）介绍你自己",额度消耗极小）。徽标与耗时列悬停即可看到，如
  「首字 4.14s · 输出 30 字 · 约 17 字/秒」;指标随结果一并持久化。
- **失败有中文指引**：错误按「连接断开 / 登录失效 / 超时 / 限流 / 网关错误」分类显示，
  流式错误帧额外带 `type` 字段供客户端识别。
- **状态行增强**：显示灵犀真实连接状态（待启动/已连接/已断开）、主机:端口、令牌掩码与运行时长。
- **X-Request-Id 全链路**：每个请求响应头返回 8 位 `X-Request-Id`,日志行（`[req …]`）与活动面板条目同 id,
  排障时用 id 即可串出一次请求的完整生命周期（`curl -i` 可见）。
- **请求历史（reqlog）**：每个请求终态落一行结构化 JSON 到 `bridge-runtime/logs/reqlog.jsonl`
  （只记元数据：模型/耗时/首字/字数/错误分类，不记对话内容），超 2MB 轮转、30 天清理；
  活动区点「历史」可切换查看最近 50 条（跨重启保留），再点「实时」切回。
- **导入 ZCode**：勾选模型后点「导入 ZCode」，把所选模型写入 ZCode 自定义供应商
  （`~/.zcode/v2/provider_config.json`，条目 id 固定 `wps-lingxi`，重复导入更新不堆叠，
  写前自动备份到 `provider-config-backups/`）。`auto` 不写入（它是网关路由语义，非真实模型）。
  **注意**：ZCode 运行中写入会被它的下一次保存覆盖——建议完全退出 ZCode 再导入，写完重启 ZCode 生效；
  模型分组不会自动跟随，首次使用需在 ZCode 模型列表里手动勾选。
- **配置集中（gateway.json）**：可选配置文件 `bridge-runtime/gateway.json`，
  键：`port` / `host` / `token` / `timeout`（对话超时秒）/ `test_timeout`（一键测试超时秒）/
  `log_enabled`（日志落盘开关）/ `log_max_mb`（轮转阈值）/ `reqlog_enabled` / `reqlog_max_mb` / `reqlog_keep_days`。
  **优先级：环境变量 > gateway.json > 内置默认**,启动窗口会逐行打印每一项的生效来源；
  改完文件重启网关生效。模板见项目根目录 `gateway.example.json`(复制改名即可)。
- **模型清单配置化（models.json）**：可选文件 `bridge-runtime/models.json`，
  格式见根目录 `models.example.json`(key / 展示名 / 可选档位数组)。
  **改完保存即热重载**（下次请求自动重读，无需重启；也可 `POST /admin/reload-models` 手动触发）；
  不提供此文件时用内置 12 模型清单；文件损坏时自动回落内置并提示，网关不受影响。
  模型档位缺省时自动用 `plans.json` 的缓存填充。

---

## 九、文件说明

| 文件 | 作用 |
|---|---|
| `启动灵犀Bridge.bat` | 双击启动网关并打开控制台 |
| `bridge_gateway.py` | FastAPI 网关：OpenAI 接口 + 控制台 + admin（崩溃自愈 · 单实例 · 仅本机监听） |
| `appserver_client.py` | lingxi.exe 的 stdio JSON-RPC 客户端（含 effort · 存活检测 · 瞬态错误分类） |
| `qr_login.py` | WPS 扫码登录、grant_token、账号检查 |
| `workbuddy_sync.py` | 定位/合并/备份/写入 WorkBuddy models.json |
| `zcode_sync.py` | 写入 ZCode 自定义供应商（provider_config.json，幂等合并+备份+ZCode 运行检测） |
| `gateway.example.json` | 可选配置模板（复制为 `bridge-runtime/gateway.json` 生效） |
| `models.example.json` | 可选模型清单模板（复制为 `bridge-runtime/models.json` 生效，保存即热重载） |
| `console.html` | 可视化控制台（含活动面板 · 结果持久化恢复） |
| `check_deps.py` | 依赖全量体检（`python check_deps.py`，列 6 包状态 + 清华源命令） |
| `plans.json` | 云端套餐与每模型思维等级缓存 |
| `current_sid.txt` | 扫码更新后的 wps_sid（自动生成） |
| `bridge-runtime/`、`appserver/` | 运行目录与 app-server 程序（`appserver/` 内另存有原始运行件 zip 备份，客户端卸载后重建运行件就靠它） |
| `tests/` | 协议仿真桩与批次验收 E2E 脚本（`e2e_batch2` / `e2e_config` / `e2e_deps` / `e2e_reqlog` / `e2e_probe` 均可复跑） |

---

## 十、故障排查

- **启动提示缺依赖包**：窗口会直接给出中文提示与清华源安装命令（复制执行即可）。
  缺失 fastapi/uvicorn/requests 会阻断启动；缺 pywin32/cryptography 只影响"刷新 Cookie"功能、不阻断。
  手动全量体检：`python check_deps.py`。
- **双击 bat 提示未找到 python**：先装 Python 3.11+ 并勾选 "Add python.exe to PATH"，重开窗口再试。
- **lingxi 意外退出/被结束后**：网关会自动检测，并在下一次请求时自动重启 lingxi（启动窗口出现 `[self-heal]` 字样），无需人工重启网关。
- **重复双击启动**：会提示"灵犀 Bridge 已在运行"并直接退出；端口被其他程序占用时给出中文报错与换端口指引。
- **打不开控制台、提示"需要访问令牌"**：请使用启动窗口中给出的完整地址（含 `?token=…`）打开。
- **扫码后提示 grant_failed**：多为二维码过期或网络抖动，刷新二维码重扫；仍异常把红字发我。
- **一键测试个别失败**：重试该模型；连续失败检查账号是否登录、网络是否正常。
- **WorkBuddy 看不到模型**：用「读取 WorkBuddy 配置」核对路径，重启 WorkBuddy。
- **撤销导入**：用 models.json 同目录 `.lingxi-bridge-*.bak` 还原。
