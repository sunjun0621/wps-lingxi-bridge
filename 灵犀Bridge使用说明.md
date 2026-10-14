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
- 登录失效时：点 **「扫码登录 / 切换账号」**
  1. 下方出现登录二维码（用 **WPS 手机 APP** 扫码）
  2. 状态依次提示：请扫码 → 已扫码，请在手机上确认 → 登录成功
  3. 后端自动用授权码换取新的 `wps_sid`，保存并**自动重连** lingxi，无需重启
  - 二维码过期可点「刷新二维码」
- 新 sid 写入 `current_sid.txt`（优先级高于 cookies_decrypted.json）

> 说明：取码与轮询已验证；「扫码后自动换 sid」这一步请你实际扫一次确认，
> 若有提示异常，把界面红字发我即可定位。

---

## 三、思维等级（reasoning effort）

灵犀的思维等级为**三档**（不是常见的五档）：

| 等级 | 含义 |
|---|---|
| `low`（低） | 思考最少、最快 |
| `high`（高） | 较强推理 |
| `max`（Max） | 最充分思考（实测会输出完整思维链并自我纠错） |

- 每个模型行有「低 / 高 / Max」分段按钮，点选即可，再点一次取消；不选则用云端默认
- **MiMo、MiniMax 为「自适应思考」**，不提供手动等级
- 单个对话、一键测试、OpenAI 接口都会带上所选等级
- OpenAI 调用方式：请求体顶层 `"reasoning_effort":"high"`，或 `"reasoning":{"effort":"high"}`

---

## 四、一键测试全部模型

- 先勾选要测的模型（可在模型行选好各自的思维等级），点 **「一键测试已勾选」**
- 顶部「测试等级」下拉可给所有模型统一指定等级；默认用各模型已选等级
- 后端串行逐个发送极简请求，模型行实时标记 **可用 / 失败、耗时**，结束后汇总
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

## 八、登录态的其它处理方式

- 扫码登录会自动更新 `current_sid.txt`，最省事
- 也可运行 `08_cookies.py`（或 `灵犀反代工具.bat` 选 1）重新提取，再启动
- 临时指定：`set LINGXI_SID=你的sid` 后 `python bridge_gateway.py`

环境变量：
- `LINGXI_BRIDGE_PORT`：端口（默认 8799）
- `LINGXI_BRIDGE_TOKEN`：访问令牌（默认 lingxi-bridge）
- `LINGXI_BRIDGE_HOST`：监听地址（默认 `127.0.0.1` 仅本机；如需局域网访问改为 `0.0.0.0`）

安全说明：网关默认仅监听本机（局域网不可达）；除 `/health` 外所有接口需令牌；
无令牌打开页面会显示中文提示页；控制台与网关同源，不依赖 CORS。

---

## 九、文件说明

| 文件 | 作用 |
|---|---|
| `启动灵犀Bridge.bat` | 双击启动网关并打开控制台 |
| `bridge_gateway.py` | FastAPI 网关：OpenAI 接口 + 控制台 + admin（崩溃自愈 · 单实例 · 仅本机监听） |
| `appserver_client.py` | lingxi.exe 的 stdio JSON-RPC 客户端（含 effort · 存活检测 · 瞬态错误分类） |
| `qr_login.py` | WPS 扫码登录、grant_token、账号检查 |
| `workbuddy_sync.py` | 定位/合并/备份/写入 WorkBuddy models.json |
| `console.html` | 可视化控制台 |
| `plans.json` | 云端套餐与每模型思维等级缓存 |
| `current_sid.txt` | 扫码更新后的 wps_sid（自动生成） |
| `bridge-runtime/`、`appserver/` | 运行目录与 app-server 程序 |

---

## 十、故障排查

- **lingxi 意外退出/被结束后**：网关会自动检测，并在下一次请求时自动重启 lingxi（启动窗口出现 `[self-heal]` 字样），无需人工重启网关。
- **重复双击启动**：会提示"灵犀 Bridge 已在运行"并直接退出；端口被其他程序占用时给出中文报错与换端口指引。
- **打不开控制台、提示"需要访问令牌"**：请使用启动窗口中给出的完整地址（含 `?token=…`）打开。
- **扫码后提示 grant_failed**：多为二维码过期或网络抖动，刷新二维码重扫；仍异常把红字发我。
- **一键测试个别失败**：重试该模型；连续失败检查账号是否登录、网络是否正常。
- **WorkBuddy 看不到模型**：用「读取 WorkBuddy 配置」核对路径，重启 WorkBuddy。
- **撤销导入**：用 models.json 同目录 `.lingxi-bridge-*.bak` 还原。
