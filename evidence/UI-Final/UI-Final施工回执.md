# UI-Final 施工回执

## 当前任务
把 A-01～A-08 已有生产能力整理为统一、可操作、可用于招聘现场演示的桌面生产界面；不增加生产能力。

## 现场起始状态
A-08 主链与样例完整；施工前 63 项自动测试全部通过（73.553 秒）。已重读三份冻结文件、当前代码/测试、README 和既有回执。建立 376 个文件的 SHA-256 基线和 `A-08-before.zip` 备份。复制 A-08 样例到本轮 gui-data 后才执行写操作。

## Current UI Audit
原界面七个主 Tab 按阶段平铺，声音/对白/审核混在一个入口；Shot 缺少跨环节摘要；Prompt、ID、Handoff JSON 占据正常页面；最小窗口实际约 1674×1169，无法覆盖 1366×768；Timeline 媒体处理在主线程。原 Reference 缩略图、AssetCard 和视频媒体中心结构有价值，沿用并整理。Before 来自实际旧窗口。

## UI Component Research
定向比较原生 ttk、ttkbootstrap、sv-ttk、局部 Composite/Canvas 与 PySide6；检查官方文档、许可、维护/安装、Windows/Python 兼容性、DPI 与控件能力。详见 [组件调研](ui-component-research.md)。未安装未经需要证明的大库，也未声称未安装方案在本机已实测。

## Technology Decision
保留 Tkinter/ttk，使用现有 clam Style、Pillow 和少量组合组件。改进信息层级比换主题/框架收益更直接，且能保留全部现有业务绑定。新增运行依赖为零。详见 [技术决策](ui-technology-decision.md)。

## Information Architecture
四组、九个入口：生产（镜头工作台、对白），资产（角色、场景、声音），审核（图像/首帧、视频选片、音频选片），交付（粗剪/交接）。默认进入 Shot。底层页面对象保留，侧栏和原内部页签同步，不引入新的工作流引擎。

## Visual System
浅灰工作区、白色编辑区、深墨色侧栏、绿色主操作；系统中文字体、统一字号和间距。Selected/Rejected/Candidate/Pending/Blocked/Stale 使用文字与颜色共同表达。按钮按用途分层，窄窗口自动换行；列表、表单和技术文本可滚动，原生键盘焦点保留。

## Assets
Character 显示封面、稳定身份、Look/Reference 数量、当前 Look 和默认声音；Scene 保留同一结构的空间/State/Reference；Voice 显示角色关联、声音描述、默认 Delivery 与映射状态。精确 Provider Voice ID 放入 Advanced。

## Reference UX
复用原导入、哈希去重、相对路径和缩略图体系；列表显示稳定图/Look/State 归属及导入/生成 Fixture 来源。真实预览、文件选择框导入与重复图去重仍成立；16 图容量副本可滚动至末尾。没有第二套文件管理系统。

## Shot Production Workspace
默认生产概览汇总“谁 / 哪里 / 做什么”，以及 Reference、首帧、Selected Video、音频、字幕与所属 Timeline。编辑表单为另一个内部页签；完整 ID/关联留在 Advanced。概览是只读投影，不写独立状态，不改 Production Truth。首帧资产引用变化能派生 Stale 提示。

## Review System
Image、Video、Audio 都保留候选→人工拒绝/重试/选择的入口。视频媒体居中；图像 Prompt 下沉；音频 Retry 设置和技术请求折叠。已实际执行三类审核链：视频 Take 3 拒绝后生成 Take 4 并选择；音频产生新执行、选择并生成 Fixture 对齐；首帧生成、拒绝、重试、采纳。MP4、WAV 与粗剪 MP4 均真实播放。

## Timeline / Rough Cut
保留有序 Shot 列表与既有装配算法；默认突出 Ready/Blocked/Stale、时长、Selected 来源、Warning 与交接状态。设置折叠，原始 manifest/build/handoff path 在 Advanced。GUI 实际 Build、Generate Preview、Open Preview、Export Handoff；两镜头 6 秒；包内 OTIO 回读和相对媒体存在性检查成功。没有增加剪辑器功能。

## Fixture / Real Status
全局显示 FIXTURE · ZERO-CALL；视频/图像/音频/对齐继续明确说明模拟边界，REAL 未启用。验收 App 禁止 socket 连接，无真实生成请求、无 API 费用。媒体像素里原有 Fixture/Task 标记原样保留，没有伪装为真实模型作品。

## Advanced / Technical Details
Shot 原记录、视频 Execution/Task/Request/Hash、Voice Mapping、音频请求和 Handoff、图像 Prompt/Task、Timeline manifest 与导出路径均可访问。实际展开并检查；工程细节没有删除，也不再占据主要操作区域。

## Empty / Warning / Error
空项目有“先建资产/镜头、再生成候选”的指引；不可执行的审核操作禁用。一般操作错误显示在应用状态区，完整技术信息仍可查看。缺失选片的 Timeline 实际显示 Blocked；改变人工选片后实际显示 Stale；允许缺失音频和视频驱动截短保留 Warning，未把 Ready 描述为毫无问题。

## Responsive / Window Behavior
真实操作了 1366×768 目标尺寸、1920×1080 和当前 2560×1600 桌面最大化。当前 Windows 150% 缩放存在 1 像素舍入，小窗口截图实际为 1367×768；最小允许窗口更小，所有主入口仍可达。修复侧栏底部入口截断、粗剪列表被表单挤没、视频上下文占满小窗口等问题。所有一级入口和主要按钮可达；小窗口使用滚动与换行。保留既有 Windows DPI 机制，未声称跨显示器 Per-Monitor V2 已验证。

## Performance
缩略图解码采用最多 96 项缓存，文件修改时间变化会失效；窗口缩放不重新读盘生成媒体。粗剪检查、Build/Preview/Export 通过现有 worker 执行，Tk 线程只更新界面；过期检查结果不覆盖新页面，重复媒体操作受保护。未增加线程池框架。销毁时统一取消 Tcl 定时回调，覆盖正常退出和历史测试的直接 destroy 路径。

## Before / After
[四组真实对照](before-after.md)：Shot、视频审核、Timeline、小窗口。主截图只保留 8 张最终界面；见 [精选截图](screenshots.md)。

## Demo Walkthrough
实际演练 2026-09-17 02:14:43～02:20:24，5 分 41 秒、97 个鼠标/键盘/查看操作，完整走过资产→Shot→图像→视频→对白/音频/字幕→粗剪交接。见 [演示脚本](demo-walkthrough.md)、`demo-log.txt`、`demo-timing.json`。这不是对招聘人员开展过的用户研究。

## 实际 GUI 验收

| Case | 项目 | 结果 / 证据 |
|---|---|---|
| 1 | 正常启动 | 通过：原 start.cmd 真实启动/关闭；start-log.txt、start-cmd.png。 |
| 2 | 默认入口 | 通过：默认镜头工作台；空项目显示建资产→建 Shot 的引导；empty-shot-audit.json。 |
| 3 | 一级导航 | 通过：九个入口均经真实鼠标切换，分类为生产/资产/审核/交付；browse、minimum、demo 日志。 |
| 4 | Character | 通过：角色卡片、默认声音、Look 选择、保存与参考图均可操作；after-character.png。 |
| 5 | Scene | 通过：场景、两个 State 与参考图归属可读；scene-demo-audit.json。 |
| 6 | Voice | 通过：默认声音、描述、Delivery、参考音频及 Advanced Mapping；实际保存原 Voice；voice-demo-audit.json。 |
| 7 | References Preview | 通过：实际选图预览；原图通过文件选择框重复导入，沿用哈希去重；demo-log.txt。 |
| 8 | Shot | 通过：角色/Look、场景/State、需求、首帧及审核链摘要可读；实际保存；after-shot.png。 |
| 9 | First Frame | 通过：由 Shot 进入，生成→Reject→Retry→人工采纳首帧，重启保持；media-log.txt。 |
| 10 | Image Review | 通过：候选、Rejected、Promoted 与可用/禁用按钮可区分；after-image.png。 |
| 11 | Video Review / Playback | 通过：四个 Take 可浏览；实际 FFplay 播放 MP4；playback-video.png。 |
| 12 | Audio Review / Playback | 通过：四个候选可浏览；实际 FFplay 播放 WAV；playback-audio.png。 |
| 13 | Reject / Retry / Select | 通过：视频 Take 3 Reject→Take 4→Select；音频与图像也实际完成新执行和人工选择；日志及 final-chain-verification.json。 |
| 14 | Fixture / Zero-call | 通过：全局与媒体页明确标记；应用验收禁用 socket 连接；无真实 API。 |
| 15 | Dialogue | 通过：关联 Shot/默认声音、顺序、长文本和音频 Handoff 摘要；demo、stress 日志。 |
| 16 | Alignment / Subtitle | 通过：对新 Selected Audio 实际生成 Alignment Fixture/SRT，Expected/模拟 Transcript/Timing 分开；after-audio.png。 |
| 17 | Timeline / Rough Cut | 通过：两镜头顺序、视频/对白/字幕、时长和策略可读；GUI Build 生成并回读 OTIO；after-timeline.png。 |
| 18 | Preview Playback | 通过：GUI 实际装配并播放 6 秒 Preview；playback-rough.png、media-log.txt。 |
| 19 | Handoff | 通过：GUI Export 导出 Portable Handoff；包内 OTIO 与相对媒体引用回读检查成功；final-chain-verification.json。 |
| 20 | Advanced / Technical | 通过：Shot、Video、Voice、Audio、Image、Timeline 的技术内容保留；实际展开 Shot/Video/Voice/Timeline 并记录 audit。 |
| 21 | Empty State | 通过：独立空数据副本逐页操作；无 Shot/Take 时有引导，审核按钮按条件禁用；empty-*-audit.json。 |
| 22 | Blocked / Warning / Stale | 通过：缺失 Selected Take 显示 Blocked；选片变化显示 Stale；对白缺失/截短保留 Warning；blocked、stale、handoff audit。 |
| 23 | 最小窗口 | 通过：实际 1366×768；全部侧栏可达，主按钮可达/换行，长区域滚动；minimum-*-audit.json、after-small.png。 |
| 24 | 1920×1080 | 通过：主要资产、审核、粗剪和演练均在此尺寸实际操作；最终截图。 |
| 25 | 当前桌面 | 通过：真实最大化操作并记录窗口边界；desktop-audit.json、desktop-environment.json。 |
| 26 | 长文本 | 通过：独立压力副本的第 20 句长对白可到文末；字段支持换行/滚动；stress-dialogue-audit.json。 |
| 27 | 多 Reference | 通过：16 张图，真实滚动/End 到末尾并预览；stress-references-audit.json。 |
| 28 | 多个 Take | 通过：同一 Shot 四个视频 Take；可切换、播放、拒绝/选择，状态不混淆。 |
| 29 | 多个 Dialogue | 通过：同一 Shot 20 句测试对白，实际浏览首尾；stress-fixture-summary.json。 |
| 30 | 多个 Timeline Shot | 通过：两个 Shot 的顺序/Selected 视频/时长均正确；两镜头共 6 秒。 |
| 31 | 关闭重启 | 通过：应用/播放器退出后重新启动，最终版再完整关闭；final-restart-log.txt，stderr 无异常。 |
| 32 | 重启保持 | 通过：Selected Take 4、Selected Audio、首帧、Alignment、Timeline/Handoff 仍明确；final-restart-*-audit.json。 |
| 33 | 原业务操作 | 通过：保留原业务方法和入口；参考图导入、Look/State 切换、保存、各类生成/审核、字幕、Build/Preview/Export 实际操作；全部历史测试回归。并未声称本轮逐按钮重复所有历史阶段的人工用例。 |
| 34 | Production Truth | 通过：无模型/Schema/核心持久化改动，无迁移；原 data 与 A-08 证据文件哈希不变。 |
| 35 | 历史 63 项测试 | 通过：完整套件 68/68，其中原 63 项文件未改，新增 5 项界面语义与生命周期测试。 |

## 自动测试
最终 **68/68 通过，117.424 秒**。原 63 项完整保留，新增 5 项覆盖只读概览/首帧 Stale、导航与未保存保护、后台检查与过期结果、重复操作/错误无写入、直接销毁回调清理。最终日志 `final-tests.txt` 无 Tk callback 异常。测试通过之外，以上 GUI、文件、媒体和重启验证均已执行。

## Data Protection
376 文件基线中仅 8 个既有 UI/展示文件发生预期变化；没有其他基线变化。三份冻结文档、原 data、A-08 全部基线证据、历史测试、核心模型、Provider/生产模块、Schema、README、requirements 与 start.cmd 保持原哈希。新增只有 UI 组合组件、测试/验收工具与本轮证据。详见 `data-protection.json`。全部生成/选择/容量操作属于明确的独立测试副本。

## Dependency / Start
不新增运行依赖；原 `start.cmd` 已真实启动并关闭。测试副本可用 `python -m app.gui --data-dir evidence/UI-Final/gui-data` 打开；原 data 入口不变。pywinauto 仅用于既有本地桌面验收工具，不进入产品依赖。

## Evidence
- [35 项 GUI 验收](gui-acceptance.md)、[技术决策](ui-technology-decision.md)、[组件调研](ui-component-research.md)
- [Before / After](before-after.md)、[精选截图](screenshots.md)、[Demo Walkthrough](demo-walkthrough.md)
- `final-tests.txt`、`data-protection.json`、`final-chain-verification.json`
- `final-restart-log.txt`、`final-restart-*-audit.json`、`gui-network-audit.json`
- `gui-data/`：完整演示副本；`stress-data/` / `empty-data/`：独立验收副本
- 关键新 UI 模块：`app/ui_components.py`；其余修改集中在原 GUI、widgets、presenters、workspace layout。

## Done 判断
**已完成。** 35 项验收记录成立；原生产能力、Human Gate 和启动保持；零新增依赖、零真实 API；68 项自动测试和真实媒体/GUI/重启/演练全部通过。最终界面达到本项目所需的专业内部生产工具呈现标准；不等同商业产品设计或用户研究结论。

## 边界判断
完全在 UI-Final 范围内。没有数据库、Web/SaaS、Provider 扩展、真实模型调用、生产数据迁移、剪辑器或下一阶段施工。三份冻结文档未修改。未做 README 总收官、Portfolio 或网站。

## 遗留 / 风险
- 所有生成/对齐仍为 Fixture；不能据此评价真实图像、视频、音色或识别质量。
- Resolve 实机导入仍未验证；本轮只验证 OTIO 回读、可迁移媒体包和真实 Preview。
- 性能与 DPI 验收限当前 Windows/Python 3.13 环境和本地小媒体；未宣称大规模媒体库或跨显示器 DPI 已验证。
- 演示应使用本轮 gui-data；原 data 刻意保留，内容可能少于演示副本。

## 当前最终 UI 能力
用户可通过统一桌面界面管理角色、场景和声音，围绕 Shot 查看生产进度，生成本地 Fixture 候选并执行人工审核，查看对白/音频/字幕，构建播放粗剪并导出交接包。无需手改 JSON 或输入内部 ID；需要时仍能恢复完整生成上下文和关联。

## 下一步入口
交回主协调者。可另行安排项目收官、README/Architecture/Demo/Resume/Portfolio，或必要的 Resolve 实机导入验证；本轮不施工。
