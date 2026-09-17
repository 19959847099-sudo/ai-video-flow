# A-08 Resume Evidence

## Verified

- 将独立生产数据中的人工 Shot 顺序、Selected Video、Selected Dialogue Audio 与当前 Alignment / Subtitle 汇合为可验证 Rough Cut Manifest。
- 接入真实 OpenTimelineIO 0.18.1，构建多轨交换表示，验证 Clip / MediaReference / provenance 和序列化 round-trip。
- 使用 FFmpeg / ffprobe 真实装配 6 秒 H.264 / AAC 粗剪 Preview；验证解码后的镜头顺序、音频区间和字幕裁切。
- 实现面向 Resolve 的相对路径 OTIO / 媒体 / SRT 交接包，复制后验证引用恢复。
- 保留 Human Gate；官方 DSH 工具机械装配，不修改顺序或选择。
- GUI 创建、调整 Shot 顺序、构建、播放、导出及完全重启后的再次播放已实际操作。

## Unverified

真实模型内容质量、真实专业剪辑质量、剪辑节奏 / 故事质量、Resolve 实际人工导入、目标 NLE 之外的软件兼容性、商业成片质量。WhisperX 仍是 Fixture / Contract，字幕不是实际识别结果。

## 可用项目描述

“构建本地 AI 视频生产工作流，将角色/场景/声音、生成任务、人工审核与选中素材通过稳定 ID 和快照关联；采用 OpenTimelineIO、FFmpeg 与 DeepSeek Harness 完成多镜头粗剪和可迁移 NLE 交接，并验证媒体、来源关系及 Human Gate。”

不得写成自动高质量成片、专业自动剪辑或已替代 Resolve / Premiere。阶段 A 的真实作品质量目标仍不因工程骨架闭环自动达成。
