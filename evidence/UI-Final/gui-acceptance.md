# UI-Final 真实 GUI 验收

所有写操作使用隔离 Fixture 副本。桌面操作由鼠标/键盘驱动完成，widget map 只读取布局和状态；不直接调用 GUI 业务方法冒充点击。原 start.cmd 验收只读原 data。

| Case | 验收项 | 结果 | 实际证据 |
|---|---|---|---|
| 1 | 正常启动 | 通过 | 原 start.cmd 真实启动/关闭；start-log.txt、start-cmd.png。 |
| 2 | 默认入口 | 通过 | 默认镜头工作台；空项目显示建资产→建 Shot 的引导；empty-shot-audit.json。 |
| 3 | 一级导航 | 通过 | 九个入口均经真实鼠标切换，分类为生产/资产/审核/交付；browse、minimum、demo 日志。 |
| 4 | Character | 通过 | 角色卡片、默认声音、Look 选择、保存与参考图均可操作；after-character.png。 |
| 5 | Scene | 通过 | 场景、两个 State 与参考图归属可读；scene-demo-audit.json。 |
| 6 | Voice | 通过 | 默认声音、描述、Delivery、参考音频及 Advanced Mapping；实际保存原 Voice；voice-demo-audit.json。 |
| 7 | References Preview | 通过 | 实际选图预览；原图通过文件选择框重复导入，沿用哈希去重；demo-log.txt。 |
| 8 | Shot | 通过 | 角色/Look、场景/State、需求、首帧及审核链摘要可读；实际保存；after-shot.png。 |
| 9 | First Frame | 通过 | 由 Shot 进入，生成→Reject→Retry→人工采纳首帧，重启保持；media-log.txt。 |
| 10 | Image Review | 通过 | 候选、Rejected、Promoted 与可用/禁用按钮可区分；after-image.png。 |
| 11 | Video Review / Playback | 通过 | 四个 Take 可浏览；实际 FFplay 播放 MP4；playback-video.png。 |
| 12 | Audio Review / Playback | 通过 | 四个候选可浏览；实际 FFplay 播放 WAV；playback-audio.png。 |
| 13 | Reject / Retry / Select | 通过 | 视频 Take 3 Reject→Take 4→Select；音频与图像也实际完成新执行和人工选择；日志及 final-chain-verification.json。 |
| 14 | Fixture / Zero-call | 通过 | 全局与媒体页明确标记；应用验收禁用 socket 连接；无真实 API。 |
| 15 | Dialogue | 通过 | 关联 Shot/默认声音、顺序、长文本和音频 Handoff 摘要；demo、stress 日志。 |
| 16 | Alignment / Subtitle | 通过 | 对新 Selected Audio 实际生成 Alignment Fixture/SRT，Expected/模拟 Transcript/Timing 分开；after-audio.png。 |
| 17 | Timeline / Rough Cut | 通过 | 两镜头顺序、视频/对白/字幕、时长和策略可读；GUI Build 生成并回读 OTIO；after-timeline.png。 |
| 18 | Preview Playback | 通过 | GUI 实际装配并播放 6 秒 Preview；playback-rough.png、media-log.txt。 |
| 19 | Handoff | 通过 | GUI Export 导出 Portable Handoff；包内 OTIO 与相对媒体引用回读检查成功；final-chain-verification.json。 |
| 20 | Advanced / Technical | 通过 | Shot、Video、Voice、Audio、Image、Timeline 的技术内容保留；实际展开 Shot/Video/Voice/Timeline 并记录 audit。 |
| 21 | Empty State | 通过 | 独立空数据副本逐页操作；无 Shot/Take 时有引导，审核按钮按条件禁用；empty-*-audit.json。 |
| 22 | Blocked / Warning / Stale | 通过 | 缺失 Selected Take 显示 Blocked；选片变化显示 Stale；对白缺失/截短保留 Warning；blocked、stale、handoff audit。 |
| 23 | 最小窗口 | 通过 | 实际 1366×768；全部侧栏可达，主按钮可达/换行，长区域滚动；minimum-*-audit.json、after-small.png。 |
| 24 | 1920×1080 | 通过 | 主要资产、审核、粗剪和演练均在此尺寸实际操作；最终截图。 |
| 25 | 当前桌面 | 通过 | 真实最大化操作并记录窗口边界；desktop-audit.json、desktop-environment.json。 |
| 26 | 长文本 | 通过 | 独立压力副本的第 20 句长对白可到文末；字段支持换行/滚动；stress-dialogue-audit.json。 |
| 27 | 多 Reference | 通过 | 16 张图，真实滚动/End 到末尾并预览；stress-references-audit.json。 |
| 28 | 多个 Take | 通过 | 同一 Shot 四个视频 Take；可切换、播放、拒绝/选择，状态不混淆。 |
| 29 | 多个 Dialogue | 通过 | 同一 Shot 20 句测试对白，实际浏览首尾；stress-fixture-summary.json。 |
| 30 | 多个 Timeline Shot | 通过 | 两个 Shot 的顺序/Selected 视频/时长均正确；两镜头共 6 秒。 |
| 31 | 关闭重启 | 通过 | 应用/播放器退出后重新启动，最终版再完整关闭；final-restart-log.txt，stderr 无异常。 |
| 32 | 重启保持 | 通过 | Selected Take 4、Selected Audio、首帧、Alignment、Timeline/Handoff 仍明确；final-restart-*-audit.json。 |
| 33 | 原业务操作 | 通过 | 保留原业务方法和入口；参考图导入、Look/State 切换、保存、各类生成/审核、字幕、Build/Preview/Export 实际操作；全部历史测试回归。并未声称本轮逐按钮重复所有历史阶段的人工用例。 |
| 34 | Production Truth | 通过 | 无模型/Schema/核心持久化改动，无迁移；原 data 与 A-08 证据文件哈希不变。 |
| 35 | 历史 63 项测试 | 通过 | 完整套件 68/68，其中原 63 项文件未改，新增 5 项界面语义与生命周期测试。 |
