# Hermes API 接入约定

心流把Hermes作为远程助手连接，与本地Agent的文字模型配置分开。用户在「Lab → Hermes」填写显示名称、服务器地址与API Token，保存后检测连接。服务器地址是Agent API入口，例如 https://example.com/hermes/v1；Token由该服务器提供。模型、工具与记忆在自己的Hermes服务器管理。

服务部署后先核对以下兼容要求；缺少接口的版本需要启用对应Agent API或增加适配。本文描述当前插件要求。

## 认证与能力

请求使用JSON和 `Authorization: Bearer <Token>`。调用者只能操作自己拥有的会话和运行。

`GET /v1/capabilities` 至少返回：

```json
{"features":{"run_submission":true,"run_status":true,"run_stop":true,"runs_idempotency":{"supported":true,"durable":true,"retention_seconds":86400},"run_steer":true}}
```

`run_steer` 用于回复过程中继续发消息。检测连接只GET能力，不提交模型提问。

## 运行接口

- `POST /v1/runs`：接收 `input` 文字、客户端生成的 `session_id`、连接的Agent别名 `model`。接受 `Idempotency-Key`，同键同请求返回原运行，去重记录需持久化；同键不同请求拒绝。
- 提交返回 `run_id`、`session_id`、`status`。插件会话使用独立 `xinflow-` 身份，微信会话标识不会放进请求。
- `GET /v1/runs/{run_id}`：返回原身份、状态和最终 `output` 文字。终态为 `completed`、`failed`、`cancelled` 或 `incomplete`；失败需保留原因。`last_event` 可说明仍在执行工具。
- `POST /v1/runs/{run_id}/stop`：只停止指定运行；客户端继续查询真实终态。
- `POST /v1/runs/{run_id}/steer`：接收 `{"input":"补充消息"}`，返回 `{"run_id":"原运行","accepted":true}`。已结束或不再接收的运行返回409，客户端核对后接到下一轮；连接不确定时保留输入，不自动重复发送。
- 若已接受的补充输入尚未消费，终态用 `pending_steer` 返回原文字数组。客户端只续接可与自己原始消息对应的内容，并沿用原消息编号，保留现有气泡。

Hermes模式不请求内部提供商模型目录，不发送provider或思考强度覆盖。普通AI模型和思考设置只属于本地Agent。

## 图片和音频边界

文字接口与媒体扩展分别声明能力。未提供媒体扩展的部署仍可使用文字；完整媒体请求见下文。

## 媒体扩展 v1

能力：`features.xinflow_media={"version":1,"images":true,"audio_input":true,"audio_output":true,"max_bytes":6291456}`。

`POST /v1/runs` 图片消息的 input 是 `[{"role":"user","content":[{"type":"text","text":"图片说明"},{"type":"image_url","image_url":{"url":"data:image/png;base64,..."}}]}]`。

终态 `GET /v1/runs/{id}` 可增加 `media:[{"type":"image"|"audio","name":"文件名","dataUrl":"data:image/png;base64,..."}]`；`output` 保留正文。只返回该认证主体原运行的实际附件；不接受客户端指定任意服务器文件路径。

`POST /v1/media/transcribe` 接收 `{"operationId":"稳定编号","dataUrl":"data:audio/wav;base64,..."}`，返回 `{"text":"识别结果"}`。

`POST /v1/media/speech` 接收 `{"operationId":"稳定编号","text":"原回复正文"}`，返回 `{"media":[{"type":"audio","name":"reply.mp3","dataUrl":"data:audio/mpeg;base64,..."}]}`。

媒体操作需认证、大小/类型校验、同编号同参数去重；同编号不同参数拒绝。结果未知不能自动换编号重复生成。媒体可以独立适配，不必重启现有微信 gateway。连续 steer 只发送文字；图片/音频待当前运行结束后发送，附件与草稿持久化保留。
