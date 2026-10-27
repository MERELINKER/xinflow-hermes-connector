# XinFlow × Hermes 接入指南

把自己服务器上的 Hermes 接到 MarginNote 的心流插件，在「本地 Agent」和 Hermes 之间切换。Hermes 的模型、记忆与工具仍由自己的服务器管理。

## 让你的 Agent 帮你配置

将下面整段发给有服务器操作权限的 Agent：

> 请按照 https://github.com/MERELINKER/xinflow-hermes-connector 的 README 和 API-CONTRACT.md，检查我的 Hermes 部署并配置心流插件接入口。先确认运行版本、认证、HTTPS 和接口能力，备份相关反向代理配置。优先复用现有 Agent API；缺少图片/语音媒体入口时，按仓库中的可选媒体适配配置。保持现有微信及其他渠道的登录、会话、模型、记忆和语音配置，不执行重新配对或覆盖全局配置。不要将 Token 发到 GitHub、日志或公共聊天。完成后验证匿名请求被拒绝、认证请求成功、稳定 operationId 的幂等重试、独立插件会话以及图片/音频能力。给我最终的服务器 API 地址、需要在本地填写的 Token 获取位置和验证结果。没有权限或接口不兼容时指出具体缺口，不要虚构连接成功。

## 在插件中填写

1. 打开心流「设置 → Lab → Hermes」，点击＋。
2. **连接标识**：如 `my-hermes`，保存后不要随意更改。
3. **显示名称**：聊天中显示的名字。
4. **服务器地址**：如 `https://your-domain.example/hermes/v1`。这是 API 地址，不是 Dashboard 网页。
5. **API Token**：自己的 Hermes Agent API 访问令牌，不是模型提供商的 Key。
6. 保存，再点击「检测连接」。文字、连续消息、图片与音频分别按真实接口能力显示。
7. AI 窗口顶部按钮切换到 Hermes。点击头像可更换图片；＋选择图片或音频，麦克风录音（需宿主支持和系统授权）；音频识别为文字后可修改再发送。返回图片直接显示，音频可以播放；文字回复可选择「播放语音」。

心流的本地 CLI 已启用时，Agent 可先调用 `config.get` 读取 `xinflow_light_ai_settings` 的当前 revision，再通过 `config.patch` 保存连接。必须保留现有全部 profiles、凭证和默认模型；敏感字段的脱敏值不能写回覆盖真实 Key。让用户在插件内填写 Token 是更简单的方式。最后通过 `ai.chat.service` 的 `connection.test` 验证。CLI 的 `confirm:true` 只确认这次操作，不代表绕过宿主授权。

## 服务器最低要求

仅有 OpenAI `/chat/completions` 不足以接入长期运行的 Hermes Agent。需提供认证后的 `/v1/capabilities`、`/v1/runs`、运行状态、停止与持久化 Idempotency-Key；连续追问需 `run_steer`。具体请求和返回见 API-CONTRACT.md。不能把微信会话 ID 填进插件请求。

图片输入使用 OpenAI content parts 中的 `image_url` data URL；图片/音频输出使用运行结果的 `media` 数组。语音接口为可选的 `/v1/media/transcribe` 和 `/v1/media/speech`。本仓库提供独立适配参考，不表示所有 Hermes 版本都原生提供这些接口。

## 可选媒体适配（Docker / Linux）

先阅读两份 Python 源码和接口约定，再由自己的 Agent 适配部署方式，不要未经检查直接运行远程脚本。

- `hermes-media-worker.py` 放进 Hermes 容器可持久化目录，例如 `/opt/data/xinflow-media/`。复用安装好的 Hermes STT 与 TTS 配置；识别需配置有效 STT 后端。支持当前 MiMo 语音合成配置（MIMO_API_KEY 从服务器本地读取），其他提供方使用 Hermes 自带 TTS 工具。
- `hermes-media-proxy.py` 在 Docker 宿主机运行，只监听 `127.0.0.1:8643`，默认转发 `127.0.0.1:8642`。环境变量可指定 `HERMES_API_UPSTREAM`、`HERMES_CONTAINER`、`HERMES_MEDIA_WORKER`、`HERMES_MEDIA_CACHE`、`HERMES_MEDIA_PORT`。
- 把**插件 API 专属路径**反向代理到 8643；保留 Dashboard 和微信渠道路径。配置 TLS、至少 12MB 请求体限制及 180 秒超时。8643 不直接暴露公网。
- 服务进程需调用指定 Hermes 容器的权限；由部署者评估本机 Docker 权限，不给其他服务新增访问权。认证完全沿用上游 Hermes API。
- 媒体适配读取当前 TTS 配置，不修改 Hermes 全局微信音色。每个文件上限6MB，每次最多4个附件。当前回复未结束时，图片/音频附件保留到本轮结束后发送；纯文字可连续追加。
- 保留媒体操作的幂等回执目录。未知操作先查询原记录，不换编号盲重试。定期检查缓存磁盘空间；停止服务即可撤回媒体路由，不需要重新配对微信。

## 验证与排错

匿名 `/v1/capabilities` 应返回401/403；有效 Token 返回200。Token不要写在URL中。连接检测成功只证明认证及能力声明；图片识别、语音转写、音频播放需分别实测。

- 401/403：检查 API Token 和代理是否传递 Authorization。
- 404/HTML：填到了网页地址或路径前缀不匹配。
- 没有持久化幂等能力：先升级/补齐 Agent API，不能禁用客户端检查。
- 识别失败：检查 Hermes 的 STT 后端与音频格式，不要修改微信账号。
- 麦克风不可用：检查 MarginNote/系统麦克风权限；也可通过＋选择已有音频文件。
- 回复慢：查询同一 run 状态；不要重复提交原消息。

请仅在 Issue 中提交脱敏的版本号、HTTP 状态和问题描述。不要上传 Token、聊天记录、个人服务器地址、配置备份或账号数据。
