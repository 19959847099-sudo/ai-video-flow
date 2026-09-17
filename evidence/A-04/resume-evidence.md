# A-04 能力证明

## Verified

- 复用官方 DSH CLI 与工具执行服务，用四个生产工具完成已有 Shot 的上下文读取、任务构建、fal Fixture 推进、ffprobe 探测及回读。真实五次工具调用及五条结果事件见 [trace](production-run/trace.json)。
- Character / Look 与 Scene / State 通过既有快照进入同一 Generation Task；Provider 请求独立保存，结果按稳定 ID 回收。见任务 `data/tasks/c5b47743c2a64392a97ba47c2fb9306a/`（相对项目根目录）。
- 真实生成并播放 3 秒、640×360、H.264 测试 MP4；DSH 退出后原 GUI 正常读取，素材等待人工决定。见 [GUI](gui-harness-result.png)、[播放](gui-harness-playback.png)。
- 27 项自动测试通过，包含官方 DSH CLI 集成测试、数据独立迁移、任务快照与失败边界；95 份原文件（含原数据、核心代码和冻结文档）哈希未变。见 [测试](tests.txt)、[核验](verification.json)。
- 模型与视频 API 调用均为 0，见 [网络审计](production-run/network-audit.json)。

## Unverified

真实角色一致性、真实场景一致性、真实 Provider 成片质量、线上 API 成功率/延迟/费用，均未验证。没有真实短剧成片证明，也没有“已解决角色一致性”的结论。

本轮运行确定顺序的无密钥 Harness 编排，没有调用 DeepSeek 模型，尚未验证 LLM 自主规划和工具选择。ComfyUI、WhisperX、OTIO 未接入；多用户、并发写入、云部署未实现。

## 中文简历候选表述

- 构建面向角色与场景连续生产的本地资产、镜头及任务快照链，保持生产数据独立于 Provider 和外部编排层。
- 集成官方 DeepSeek Harness，封装四个生产工具，通过真实工具执行与事件记录完成零 API 调用的任务编排闭环。
- 适配 fal/Kling 视频接口契约并使用 Fixture 验证异步状态与结果回收，复用 FFmpeg/ffprobe 生成、校验真实测试视频，保留人工审核门。
- 建立自动测试、实际 GUI 播放、重启与文件哈希核验相结合的工程证据；本轮 27 项测试通过，未将模拟结果包装为真实模型质量验证。
