# 灵犀 Bridge 对照 workbuddy2api-panel 经验

> 日期：2026-10-14 ｜ 性质：经验移植对照清单，待主人勾选批次后执行
> 经验源：`C:\Users\Administrator\WorkBuddy\Worktrees\workbuddy2api-panel\main-383be6a1`（Go，已更新至 `6b31db6`）
> 本体：`lingxi-reverse-2`（Python FastAPI 网关 + 浏览器控制台）

---

## 〇、结论摘要

1. **多账号池类经验整体不适用**：workbuddy2api 是"多 CodeBuddy 账号 + HTTP 直连云端"架构，灵犀是"单 WPS 订阅账号 + 本地 stdio 进程"，账号池调度、余额冷却、提示词脱敏三大类可整块跳过。
2. **真正高价值的是它的"处置与观测"层**：错误分类、SSE 流收尾、请求日志、超时语义、原子落盘——正好对应本项目的批次 2（看得见）和批次 4（强），照设计抄、不抄代码。
3. **盘点中发现 2 个真问题**（error 流缺 `[DONE]`、令牌非恒时比较）——主人决定**暂不修、先观察后果**，观察方法与风险评级留档于 §二。

---

## 一、不适用清单（排除项，避免绕路）

| workbuddy2api 经验 | 不适用原因 |
|---|---|
| 多账号池调度（加权随机 / 快过期加权 / 成本分层 / 防惊群 / Top-5 短名单） | 单 WPS 账号，无池可调 |
| 402 余额硬冷却、credit_floor 积分保底、闲置补偿 | 订阅制无积分概念 |
| 提示词体系 + 指纹脱敏（防云端审核误杀 system 指纹） | 灵犀走本地 stdio，无云端审核面 |
| OAuth 设备授权多账号管理、企业版门控 | 单账号扫码已覆盖 |
| 会话粘性绑定账号、失败解绑换号 | 无"换号"动作 |

---

## 二、真问题观察记录（暂不修，先看后果）

### 2.1 SSE error 帧后缺 `[DONE]`

- **位置**：`bridge_gateway.py` → `generator()` 的 `elif kind == "error"` 分支，`break` 前未发 `data: [DONE]`。
- **后果**：OpenAI 规范上流式响应以 `[DONE]` 收尾；严格客户端可能认为流未正常终止，表现为挂起等待或报连接异常。宽松客户端（大多数）会自行容错。
- **如何观察后果**：
  1. 启动 Bridge → 杀掉 lingxi.exe（制造上游故障）
  2. 发起流式请求：`curl -N -X POST http://127.0.0.1:8799/v1/chat/completions -H "Authorization: Bearer lingxi-bridge" -d "{\"model\":\"GLM-5.3-Flash\",\"stream\":true,\"messages\":[{\"role\":\"user\",\"content\":\"hi\"}]}"`
  3. 观察：错误帧之后是否直接断流（无 `[DONE]`）；再用 WorkBuddy 走一次同场景，看其是否卡住。
- **风险评级**：低～中（取决于客户端容错；WorkBuddy / dsh 实际表现待实测）。
- **修复预案**（待批示）：error 分支补 `yield "data: [DONE]\n\n"`，错误帧结构对齐 OpenAI 错误对象 `{"error":{"message":...,"type":...}}`。

### 2.2 令牌 `==` 逐字节比较（非常量时间）

- **位置**：`bridge_gateway.py` → `is_authorized()`，`request.headers.get("authorization") == f"Bearer {TOKEN}"`。
- **后果**：时序侧信道理论上可逐字节猜测令牌；但本项目默认仅监听 `127.0.0.1`，无远程攻击面，**实际风险极低**（仅当局域网模式 `0.0.0.0` 时才需要认真对待）。
- **如何观察后果**：日常无感，属理论性风险；可留意启动日志确认监听地址保持 `127.0.0.1`。
- **修复预案**（待批示）：对齐 workbuddy2api 做法——对令牌与请求值各做 SHA-256 摘要后用 `hmac.compare_digest` 比较，3 行改动。

---

## 三、直接可抄（成本低，随时可做）

| # | 经验（workbuddy2api 源文件） | 落到 lingxi-reverse-2 | 改动量 |
|---|---|---|---|
| 1 | 请求级日志行：`TTFB / tok/s / 状态 / 模型 / 首字延迟`（`internal/server/logging.go`） | P1-1 活动面板数据源，格式照搬 | 小 |
| 2 | reqlog JSONL 归档：只记元数据不记正文、保留天数 + 容量上限双清理（`internal/reqlog/reqlog.go`，`6b31db6` 新模块） | P1-2 日志落盘，清理策略现成 | 小～中 |
| 3 | `X-Request-Id` 响应头 + 全链路日志串联 | 排障利器，中间件加一行生成 | 极小 |
| 4 | 状态原子落盘：tmp + rename（`internal/pool/persist.go`） | `current_sid.txt`、将来 model_results.json 统一写法，防半截写 | 极小 |
| 5 | 探测结果落盘不硬编码（probe_max_tokens 思想：声称值虚高，实测才可信） | 一键测试升级为"输出上限/耗时/速率"探测并持久化（P1-3） | 中 |

## 四、对应批次规划的参考（做批次时翻开对应源文件）

| # | 经验（源文件） | 对应本项目批次项 | 要点 |
|---|---|---|---|
| 6 | **超时三段语义**：短 RPC 总时长 / 首字节超时 / 流中空闲超时；活跃吐数据续命、静默才断（README"上游超时语义"节 + `internal/server/handler.go`） | **P2-4 超时可配置** | `run_stream` 现为 240s 总 deadline，max 档长文会被硬掐；改"首字 + 空闲"两段后长文安全 |
| 7 | **模型级冷却 + 锁池视图**（6004 模型限流经验，`internal/pool/modelview.go`、`modelcooldown_test.go`） | 一键测试 / 控制台健康态 | 失败模型临时标记"暂不可用 + 预计恢复时间"，测试结果不再刷新即丢 |
| 8 | **会话键派生**：客户端不发 conversation_id 时用 `system + 首条 user` 哈希派生（`d-` 前缀）、失败自动解绑（`internal/pool/entry.go`、state.go） | **P2-3 会话复用实验** | 哈希 → session_id 缓存映射；先指纹命中再复用，失败回退新建，语义现成 |
| 9 | **连败退避 / 唯一熔断计数器**（`internal/scheduler/scheduler.go`） | `get_app()` 崩溃自愈 | 加指数退避封顶，防 lingxi.exe 起不来时每请求疯狂重启 |
| 10 | **工具调用标记还原判定框架**（`internal/upstream/dsml.go` + `tool_pairing.go`）：严格/弱两级名单、闭合校验、不吞字节、命中与否各记日志 | **P4-1 spike** | 灵犀若支持工具通道，判定设计直接套用，少走弯路 |
| 11 | **配置热生效**：深合并 + 原子替换、区分"需重启字段"清单（`cmd/server/config.go` + livecfg） | P3-3 配置集中 | env > 文件 > 默认 三级已有雏形 |
| 12 | **面板细节**：日志分频道（任务/对话/系统）、时间范围由浏览器算本地时区、明暗主题 | 批次 2/4 控制台 | 参见 `internal/panel/app.js`、timerange_test.go |
| 13 | **失败分类与指引**（Classify 优先级链：登录失效 → 限流 → 超时 → 状态码兜底；"不罚账号"思想：客户端畸形请求不算上游故障） | P1-4 失败分类 | 灵犀版映射：sid 失效→请扫码；管道断→已自愈重试；超时→建议降档 |

## 五、教训类经验

- **上游 Sliverkiss 删库的直接诱因**是有人拿反代做账号分发/售卖。本项目 README 已有"仅自用订阅额度"声明——**坚持此边界**是此类项目寿命的关键变量；公开仓库时同样注意不提交 `current_sid.txt`、`cookies_decrypted.json` 等凭证（.gitignore 已覆盖，保持）。

## 六、附：workbuddy2api-panel 关键源文件索引

> 根目录：`C:\Users\Administrator\WorkBuddy\Worktrees\workbuddy2api-panel\main-383be6a1`

| 主题 | 文件 |
|---|---|
| 请求日志 | `internal/reqlog/reqlog.go`、`internal/server/logging.go` |
| SSE 处理 | `internal/upstream/sse.go` |
| 超时语义 | `internal/server/handler.go`、`upstream_timeout_test.go` |
| 模型视图/冷却 | `internal/pool/modelview.go`、`modelcooldown_test.go` |
| 会话键派生 | `internal/pool/entry.go`、`state.go` |
| 工具调用修复 | `internal/upstream/dsml.go`、`tool_pairing.go` |
| 配置热生效 | `cmd/server/config.go`、`internal/livecfg/livecfg.go` |
| 面板 | `internal/panel/app.js`、`panel.go`、`taskcenter.go` |
| 原子落盘 | `internal/pool/persist.go` |
