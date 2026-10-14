# wps-lingxi-bridge · WPS 灵犀模型反代桥

把 **WPS 灵犀桌面端**（订阅版）的云端模型能力，桥接为本机 **OpenAI 兼容接口**——
供 dsh（DeepSeek Harness）/ WorkBuddy / 任意 OpenAI 兼容客户端直接使用。

> 自研项目。经多组关键词检索，GitHub 上无针对 WPS 灵犀桌面端的同类反代开源项目；
> 独特请求头 `X-Cc-Version` 全网零第三方引用。

## 架构

```
任意 OpenAI 兼容客户端（dsh / WorkBuddy / …）
        │  HTTP · http://127.0.0.1:8799/v1
        ▼
bridge_gateway.py（FastAPI 网关 + 可视化控制台）
        │  stdio · JSON-RPC 2.0（newline-delimited）
        ▼
lingxi.exe（WPS 灵犀 app-server，本地进程）
        │  HTTPS · Cookie: wps_sid
        ▼
WPS 云端模型（DeepSeek / Qwen / GLM / Kimi / MiMo / MiniMax / 豆包）
```

原理要点：

- **鉴权极简**：云端请求仅凭 Cookie 中的 `wps_sid` 会话凭证（外加 `X-Cc-Version: 1` 等少量头），
  无私有签名、无 CSRF、无证书绑定。拿到 `wps_sid` 即可脱离客户端直连——这是本项目成立的根因。
- **桥接路线（现行）**：直接驱动官方 `lingxi.exe` app-server（stdio JSON-RPC），协议稳、不依赖网页端。
- **早期路线（留存于 `gateway/`）**：HTTP 直连 `/api/aigc/v3/assistant/*` 的 assistant 通道（`model-s`），
  是可行性验证时的方案，留作研究参考。

## 模型与能力

当前网关支持 11 个模型 + auto（均已实测可用）：

| 模型 | 思维等级（reasoning effort） |
|---|---|
| DeepSeek V4 Flash / V4.1 Flash / V4 Pro | 低 / 高 / Max |
| Qwen3.8-Flash / Qwen3.8-Max | 低 / 高 / Max |
| GLM-5.3-Flash / GLM-5.3 | 低 / 高 / Max |
| Doubao-Seed-2.1 Pro | 低 / 高 / Max |
| Kimi-K3 | 低 / 高 / Max |
| MiMo-V2.6 Pro / MiniMax-M3 | 自适应思考（无手动档位） |

接口：

- `GET /v1/models`（含每模型 `reasoning_efforts`）
- `POST /v1/chat/completions`（支持 `stream: true`，SSE 流式，思维链在 `reasoning_content`）
- 思维等级透传：请求体 `"reasoning_effort": "low|high|max"`（不支持的档位自动忽略）
- 令牌：`Authorization: Bearer lingxi-bridge`（默认值，环境变量可改）

## 快速开始

### 0. 准备

- Windows；Python 3.11+：`pip install -r requirements.txt`
- **运行件**（本仓库不含 WPS 官方文件）：项目根目录需有 `appserver/app-server/`，
  含 `service/lingxi.exe` 与 `lingxi-native-host.exe`。
  获取方式二选一：
  1. 从 WPS 灵犀桌面的安装目录复制 `resources/app-server/`（或其中的
     `app-server-windows-amd64.zip` 解压）到项目根目录；
  2. 沿用他人已备好的 `appserver/` 目录拷贝（自用范围内）。
- **无需安装或运行 WPS 灵犀桌面客户端**：桥驱动的是项目内自带的
  `lingxi.exe` 拷贝，与客户端安装目录、客户端数据目录均无依赖（已实测）；
  登录、掉线恢复全部走控制台扫码（纯网页接口）。

### 1. 启动

双击 `启动灵犀Bridge.bat`（等价 `python bridge_gateway.py`）。
约 4 秒后浏览器自动打开控制台：`http://127.0.0.1:8799/?token=lingxi-bridge`。
启动后约 2 秒内，窗口会打印登录态预检结果（有效 / 失效及扫码指引）。

### 2. 登录

控制台左侧点「扫码登录 / 切换账号」，用 **WPS 手机 APP** 扫码 →
自动换取新的 `wps_sid` 并重连，无需重启、无需任何客户端。
登录失效时控制台会自动展开二维码并提示；扫码即恢复。
（亦可用 `08_cookies.py` 从灵犀客户端本地数据解密提取——需客户端在；
或临时 `set LINGXI_SID=…`）

### 3. 接入客户端

- **dsh**：Base URL `http://127.0.0.1:8799/v1`，API Key `lingxi-bridge`，模型填任一 key
- **WorkBuddy**：控制台勾选模型 →「导入 WorkBuddy」→ 重启 WorkBuddy

完整功能说明（思维等级 / 一键测试 / 多轮对话 / 故障排查）见 **《灵犀Bridge使用说明.md》**。

## 安全设计

- 默认仅监听 `127.0.0.1`（`LINGXI_BRIDGE_HOST=0.0.0.0` 可开局域网）
- 除 `/health` 外全部接口需令牌；无令牌时浏览器显示中文提示页、API 返回 JSON
- 崩溃自愈：lingxi.exe 意外退出在后端自动重启；瞬态失败自动重试一次
- 单实例保护：重复启动给出中文提示并退出；端口被占用给出换端口指引
- `bridge-runtime/`、`current_sid.txt`、cookies 提取结果等敏感运行数据已由 `.gitignore` 排除

## 目录结构

```
├─ 启动灵犀Bridge.bat      # 双击入口：启动网关 + 打开控制台
├─ bridge_gateway.py       # FastAPI 网关（OpenAI 接口 + 控制台 + admin API）
├─ appserver_client.py     # lingxi.exe stdio JSON-RPC 客户端（effort / 存活检测 / 错误分类）
├─ qr_login.py             # 扫码登录：取码 → 轮询 → grant_token 换 wps_sid
├─ workbuddy_sync.py       # 定位 / 合并 / 备份 WorkBuddy models.json
├─ console.html            # 可视化控制台
├─ gateway/                # 早期 HTTP 直连路线（assistant 通道研究）
├─ 01~18_*.py              # 逆向过程：asar 解包 → 接口扫描 → 协议与字段验证
├─ *_probe / find_* / test_* # 探测、定位与端到端测试脚本（研究过程）
├─ 灵犀Bridge使用说明.md    # 完整使用文档
├─ 灵犀Bridge优化方案.md    # 优化方案与验证记录
├─ 灵犀Bridge操作清单.md    # 各批任务提示词与守则
├─ 灵犀Bridge批次1验收记录.md
└─ appserver/              # （不入库）WPS 官方运行件，见「准备」
```

## 免责声明

本工具仅用于**个人学习研究**，调用本人账号已订阅的额度；不得转卖、共享或用于商业用途。
请遵守 WPS 服务条款；此类调用可能被 WPS 判定为异常流量，存在账号风控 / 限流风险，后果自负。
