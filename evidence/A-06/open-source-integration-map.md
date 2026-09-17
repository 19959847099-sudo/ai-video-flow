# Open Source Integration Map · A-06

| 工具 | 决策 | 当前实际状态 | 成本与替换边界 |
|---|---|---|---|
| DeepSeek Harness | INTEGRATE | 已有官方 0.1.5-rc.2 运行时；新增 prepare_shot_first_frame，实际工具事件与 trace | 复用现有 Node / 插件；不引入第二套 Harness；不调用 LLM |
| ComfyUI | INTEGRATE | 官方 API-format 工作流、请求/响应 Adapter、零调用 Fixture、实际 PNG 入库 | 不安装 ComfyUI / 权重 / Custom Nodes；未来远程 Transport 与模型模板可替换 |
| Pillow | USE | 复用已安装库读取、校验、缩放、拼板、生成明确 Fixture PNG | 无新依赖，不自研图片编码 |
| FFmpeg / ffprobe / ffplay | USE | 现有视频编码、媒体核验、实际播放；首帧交接所得 MP4 已验证 | CLI 外围工具，核心数据不依赖其进程 |
| WhisperX | 后续有需要再 USE | 未接入 | 当前无字幕 / 对齐需求 |
| OpenTimelineIO | 后续有需要再 INTEGRATE | 未接入 | 当前无时间线交换需求 |
| AI Movie Studio 2 | LEARN，必要时 EXTRACT | 本轮未集成或抽取代码 | 不作为生产底座 |

本轮自写部分限于任务快照、协议映射、入库和人工审核连接。未复制 ComfyUI 模型执行代码；通过公开契约集成。没有新增开源运行包，已有依赖及许可范围保持。
