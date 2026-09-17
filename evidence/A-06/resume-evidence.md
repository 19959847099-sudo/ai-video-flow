# A-06 能力证明

## Verified

- 在既有角色/场景/Shot 文件生产系统上，增加独立图像任务、有效 Reference 快照、ComfyUI API 图与参数映射。
- 实现可替换 Transport 边界，并以官方形状 Fixture 验证上传、提交、排队、执行、History、二进制图片回收；保存真实可读 PNG。
- 将生成图通过明确人工操作归入 Character / Look 或 Scene / State，保存来源结果；首帧独立绑定 Shot，进入现有 Kling O3 请求的 start_image_url。
- 官方 DSH 运行时实际调用新增生产工具，返回 HumanReviewRequired，不自动 Promote；数据独立于 Harness 与远程 History。
- 真实桌面鼠标/键盘操作、完全重启、图片预览、视频播放、Reject / Retry、历史快照、哈希核验与 41 项自动测试。
- 原 data、冻结文档保持，未新增 Python 依赖，生成 API 调用及费用为 0。

证据：A-06施工回执.md、verification.json、tests.txt、dsh-final/trace.json、screenshots.md。

可用于简历的准确表述：设计并实现角色/场景到 ComfyUI 工作流、图像资产回收、人工审核与视频首帧交接的本地生产链，以官方 API 契约 Fixture 和真实 GUI/媒体验证闭环。

## Unverified

真实远程 ComfyUI 连接、鉴权、服务端校验、模型执行、SLA 和云成本；真实图像质量、角色一致性、场景一致性、首帧生产质量和视频成片质量。没有真实 AI 作品、视觉 Benchmark 或自主 LLM 规划证明。阶段 A 的真实成片目标仍未完成。
