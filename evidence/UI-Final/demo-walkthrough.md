# 现场演示路径（5～8 分钟）

使用 `python -m app.gui --data-dir evidence/UI-Final/gui-data` 启动已经审核过的测试副本。常规原数据入口仍为 `start.cmd`。不需要 API Key。

开场说明：这是一套本地连续生产工作流。本轮展示真实文件、任务关系和人工审核闭环；视频、图像、音频及对齐内容均为 Fixture，不证明真实模型质量。

| 时间 | 操作 | 要传达的生产语义 |
|---|---|---|
| 0:00–0:35 | 默认 Shot，选择 A-03 白天门口镜头 | 谁、哪里、做什么与当前生产状态集中可见；状态来自保存的生产事实 |
| 0:35–1:15 | 角色 → Look → Reference 缩略图；查看场景与雨夜 State | 角色和场景跨镜头复用；图片有明确归属，不是手填路径 |
| 1:15–1:50 | 声音资产，展开 Provider Mapping，再收起 | 稳定声音与角色关联，Provider ID 保留在 Advanced |
| 1:50–2:30 | Shot 的镜头需求页与生产概览 | Shot 以稳定 ID 引用资产；概览不迁移、不复制生产真相 |
| 2:30–3:05 | 图像审核，选择最后一个已采纳首帧 | 生成结果先是候选，人工采纳才进入资产链；已采纳与被拒绝明确区分 |
| 3:05–3:55 | 视频选片，查看 Take 1/3 Rejected、Take 4 Selected；播放 MP4；展开 Advanced | Retry 是新的执行，最终选择明确可追溯；任务快照不跟着资产编辑改变 |
| 3:55–4:45 | 对白 → 音频选片 → 播放 WAV → Timing/SRT | 音频独立 Human Gate；Expected 与模拟 Transcript 分开，Fixture 标记明确 |
| 4:45–5:35 | 粗剪，查看两镜头顺序、6 秒时长、Warning；播放 Preview；Advanced 看 Handoff | 汇合人工选定视频/对白/字幕；缺失与截短可见，便携 OTIO/媒体包供后续 NLE 接手 |
| 5:35–6:15 | 缩到 1366×768、最大化当前桌面，回到 Shot | 同一界面可在不同窗口下使用；最后强调零真实 API、无自动审美选片 |

实际演练操作与时间戳见 `demo-actions.json`、`demo-log.txt`，最终时长见 `demo-timing.json`。演练包含原参考图的 GUI 重复导入去重、保存既有 Voice/Shot、真实媒体播放、Advanced 展开和重启后的状态读取。生成与 Reject/Retry/Select 在之前的 `select-audio-log.txt` / `media-log.txt` / `gates-log.txt` 中实际执行；演讲现场可用已有结果保持节奏。

结束后不进入真实生成、Resolve 自动化、README 总收官或下一阶段施工。Resolve 实机导入尚未验证，应单独说明。
