# AI 视频个人生产工作流 · A-08

本地桌面主链：角色 + 场景 → 图像 / 首帧候选 → 人工采纳 → Shot → 视频任务 → Mock / fal Fixture → Review / Selected Take。全部生成仍为零调用 Fixture。

A-08 新增：Selected Video + Selected Audio + 当前字幕 + 人工 Shot Order → Rough Cut Manifest → 真实 OpenTimelineIO → FFmpeg Preview → Resolve Handoff。粗剪不是最终成片，真实模型与剪辑质量未验证。

## 粗剪与剪辑交接

1. 打开“粗剪 / Timeline”，新建名称，用下拉选择 Shot 并添加；Move Up / Down 调整顺序，点“保存顺序”。顺序不依赖文件名或生成时间。
2. 未选视频始终阻止构建。无音频或无当前字幕时，只有勾选对应允许策略才继续，并保留警告。
3. Validate 查看媒体和关系；Build Timeline 保存 Manifest 和 OTIO；Generate Preview 使用本地 FFmpeg。编码期间等待状态栏完成后再操作。
4. Open Preview 播放实际 MP4；Export Handoff 创建独立便携目录。导入说明在包内 README.txt。目标为 Resolve OTIO，字幕单独 SRT；Resolve 实机导入尚未验证。
5. 视频时长驱动，对白按顺序装配并截短超出部分，视频原音静音。Selection 或顺序变化后旧构建会显示 STALE，需重新 Build。

本轮真实示例与证据位于 `evidence/A-08/`，原 data 未修改：

```powershell
python -m app.gui --data-dir evidence/A-08/gui-data
python tools/verify_a08.py
```

新增依赖只有 `opentimelineio==0.18.1`，正式启动仍为 start.cmd / python -m app.gui。新增模块为 app/rough_cut.py、app/rough_cut_gui.py；新增数据目录为 timelines/、rough_cut_builds/、rough_cut_current/、handoffs/。不需要数据库或额外模型。

[A-08 架构与交接边界](evidence/A-08/timeline-architecture.md) · [A-08 施工回执与当前验收状态](evidence/A-08/A-08施工回执.md)。

A-07 增加 Character → Voice / Dialogue → Audio Task → MiniMax 官方契约 Fixture → 音频审核 → Alignment / SRT。实际 WAV 是测试音调；未调用 TTS，未运行 WhisperX 模型，不代表配音或字幕识别质量。

## 声音、对白与字幕

1. 在角色页点“声音 Voice →”，创建声音、保存并设为角色默认 Voice；可导入参考音频。系统 Voice ID 保存在独立 Provider 映射，参考音频不会被上传或用于自动克隆。
2. 在 Shot 页点“对白 / 音频 →”，填写顺序、对白、Delivery 并保存。同一 Shot 支持多句对白。
3. 点“生成音频 · ZERO-CALL”，在音频审核页试听实际 WAV。由人 Select 或 Reject；Reject 后可改文本、Delivery、语速并 Retry，产生新任务。
4. 点“对齐 + SRT · Fixture”，查看独立的模拟转写、词时间和字幕。SRT 明示 FIXTURE，实际未运行语音识别。Dialogue 页可查看选中音频和字幕的 Shot Handoff。
5. 声音与对白编辑使用各自的保存按钮，切换记录前先保存。全部数据为 JSON 和相对媒体路径，正常操作不需编辑文件。

本轮验收数据独立保存在 `evidence/A-07/gui-data`，原 `data` 未修改。查看完整示例：

```powershell
python -m app.gui --data-dir evidence/A-07/gui-data
```

完整验收见 [A-07 施工回执](evidence/A-07/A-07施工回执.md)。

## 安装与启动

使用带 Tkinter 的 Python 3.11+，以及 PATH 中的 FFmpeg（含 ffmpeg、ffprobe、ffplay）。本机已具备所需工具，已验证 Python 3.13.3、Pillow 12.1.1、Pydantic 2.12.5 和 FFmpeg 8.1。

在项目目录执行：

```powershell
python -m pip install -r requirements.txt
python -m app.gui
```

也可双击 `start.cmd`。启动方式与 A-01 相同。应用不需要网络或 API 密钥，不调用付费服务。一次只打开一个窗口编辑同一数据目录。

## 角色与场景

Characters / Scenes 左侧为带缩略图的资产列表。右侧封面摘要显示稳定身份、Reference 数量和 Look / State；详情分为身份、造型/状态、参考图三个页签。

1. 新建角色或场景，填写名称、稳定身份并保存；示例数据应勾选“测试 / 示例数据”。
2. 在参考图页用“添加图片…”或“添加场景图片…”导入 PNG、JPEG、WebP。系统复制到项目、按 SHA-256 去重，正常操作不用填写内部路径。
3. 选择图片可预览；用途显示在缩略图下方。身份图 / 稳定图用于全部 Look / State，其他图片在造型或状态页关联，点击多选。
4. 在 Looks / States 页新建变体并保存。底部“保存角色 / 场景”也会保存当前变体编辑。
5. “移除关联”只移除资产及变体关系，保留历史任务可能使用的媒体。缺失或损坏图片显示提示。

## Shot、生成与审核

Shots 左侧按真实记录显示角色、场景、短 ID、状态和 Take 数量；右侧按“谁 / 在哪里 / 做什么、怎么拍”编辑。状态是已有执行与人工选择的展示，不是新状态机。

1. 新建 Shot，选择 Character / Look、Scene / State，填写镜头需求与生成描述并保存。长文本可换行和滚动。
2. 选择 **MOCK · 本地占位视频** 或 **ZERO-CALL · fal / Kling O3**，点 **生成视频 →**。两者均生成本地测试 MP4，**REAL 未启用**。
3. 在 Review 选择 Shot 和 Take。左侧显示多 Take 状态，中间预览实际结果；点 **播放实际视频** 调用 FFplay，播放结束自动关闭。
4. 右侧 **Select · 选为最终素材** 保存明确的 Selected Take。独立标签和列表状态显示选择，系统不会自动选择最新素材。
5. 不采用时填写可选原因，点 **Reject**。可修改 Retry 描述，再点 **Retry · 创建新 Take**；新任务保留原历史，不覆盖原 Take。生成中或未 Reject 时 Retry 不可用。
6. 右侧内容在小窗口下可滚动，Retry 按钮固定在列底部。Select 与 Reject 分区，避免误触。
7. 下方默认显示当次角色、场景、参考图和最终描述；“执行摘要”显示 Provider 状态与可匹配的历史 DSH 工具步骤；“工程详情”保留 Task / Execution ID、请求、路径和 Trace。内嵌 base64 只做摘要，完整请求文件保留。

编辑后先保存再切换页面。退出等待媒体操作收尾；异常中断的 pending / processing 执行在重启后恢复。一次只允许一个程序写同一数据目录，不要同时用 GUI 与 DSH 修改它。

状态栏提供当前操作反馈。没有资产、Shot、Take 或 Selected 时会提示下一步；缺少 FFmpeg / ffplay 或读取数据失败时会明确报错。DSH 无需运行，生产数据仍可独立读取和审核。

## A-01 兼容

A-01 的角色、Look、Reference、两个旧 Shot 和四份历史任务保留。旧 Shot 没有场景时仍可读取、编辑并执行 **生成任务（Dummy 验证）**，不会被自动补造场景或批量重写。

要让旧 Shot 生成 Mock 视频，在 GUI 中为它选择场景和状态并保存即可。新 Shot 必须具备双资产引用。旧 0.1 任务照常读取；新双资产任务标为 0.2。历史任务 JSON 不随资产编辑更新。

## 文件与追溯

```text
app/core.py          Character / Scene / Shot / Task 与共用文件存储
app/gui.py           主窗口与角色、Shot 操作
app/scene_gui.py     场景编辑
app/production.py    Mock 生命周期、媒体入库与 Review 记录
app/fal_adapter.py   fal 契约映射、本地 Fixture 与两条明确执行路线
app/fixtures/        按官方契约构造的响应样本
app/review_gui.py    视频预览、人工 Select / Reject / Retry
schemas/             从 Pydantic 导出的 JSON Schema

data/characters/    Character JSON，内含 Look 与 Reference 关系
data/scenes/        Scene JSON，内含 State 与 Reference 关系
data/shots/         稳定 ID 引用双资产，保留旧 Shot 兼容
data/assets/        内容哈希命名的参考图
data/tasks/<id>/    不变的 task.json，以及独立 Provider 请求
data/executions/    执行 ID、状态、Take 编号、结果关联、retry_of
data/results/<id>/  video.mp4、poster.png、result.json
data/reviews/       每个 Shot 的 selected_result_id 与 Reject 原因
data/mock_outputs/  生成期间临时中间文件，成功后清理
```

Selected Take → Result → Execution / Task → 最终 Prompt、Shot 快照、Character / Look、Scene / State，可以完整追溯。Provider 名称位于执行和结果记录，核心角色、场景与任务不绑定 Provider。`prepare(task, asset_root)` 边界保留，Mock 另实现 submit / poll。

备份和迁移请复制整个 `data/`；其中媒体路径均相对于该目录。可用 `python -m app.gui --data-dir <目录>` 打开其他数据目录，正常操作不需要手写路径。原导入图片可移走，不影响已复制资产。

## 验证与证据

```powershell
python -m unittest discover -s tests -v
python tools/verify_a05.py
```

第二条是本轮已交付示例数据的验收核验，不是约束用户今后的生产数据必须保持不变。当前保留 1 个角色、2 个 Look、1 个场景、2 个 State、6 张参考图，以及 2 个 A-01 旧 Shot、2 个 A-02 示例 Shot 和 2 个 A-03 示例 Shot。

`evidence/A-02/` 保存实际桌面截图、操作记录、视频核验、历史快照与冻结文件哈希。`A-01-before.zip` 是施工前代码、Schema、测试及数据备份；不是运行依赖。原 `tools/verify_delivery.py` 是 A-01 当时的固定示例验收脚本，当前使用上面的 A-05 入口。

`tools/run_a03_probe.py` / `tools/drive_a03.py` 是本轮测试辅助（A-02 工具也保留）：只读控件位置后驱动真实桌面鼠标、键盘及文件选择器，不替代业务逻辑。它们使用隔离的 `.test-tools/pywinauto`，不属于应用运行依赖。用户启动时不需要这些工具。

## 当前边界

视频是明确标注 MOCK / 测试的占位卡片，不是真实 AI 作品；Select / Reject 演示也仅针对测试素材，不是审美结论。没有真实收费 API、自动审美、数据库、云服务、第三类资产、剪辑器或完整 Attempt Ledger。角色与场景一致性尚未经过真实模型验证，阶段 A 尚未完成。A-04 已增加可选 DSH 外部执行入口，见下文。

本轮直接复用本机 FFmpeg CLI 做编码、探测、缩略图与播放；Python 只组织数据与流程。没有新增 Python 运行依赖，也没有复制 FFmpeg 二进制到项目；迁移机器需安装对应工具。


## A-03：fal 官方契约的零调用接入

首个 Provider 为 fal.ai，模型为 Kling O3 Standard Reference-to-Video。角色与场景参考图映射为 image_urls 和 @Image 引用，实际最终描述保存于任务目录的 provider_request.json。Review 可读取该描述及模拟 request_id；核心 GenerationTask 保持 Provider-independent。

目前只有本地 Fixture Transport。没有 HTTP 客户端、API Key 读取或真实调用开关；即使环境中有密钥，也不会使用。Fixture 是按官方契约构造的样本响应，不是线上录制；占位视频使用 FFmpeg 生成，不能作为 Kling 画质或连续性证明。详细契约与边界见 [A-03 Provider 契约](evidence/A-03/provider-contract.md)。

每次 fal 生成经过提交响应、IN_QUEUE、IN_PROGRESS、COMPLETED、视频回收；响应保存在 provider_exchange.json。COMPLETED 带错误时判为失败。错误与缺失媒体不会自动 Select，也不自动重新提交。Retry 沿用被 Reject 结果的 Provider。

当前 fal V0 限制：最多 4 张有效参考图、单图 10 MB、最终描述 2500 字符；固定 3 秒、16:9、无音频。这是本轮适配预算。超限会明确报错，不会偷偷省略生产输入。

新增 GUI 验收示例：白天镜头使用 fal Fixture 生成两条 Take，第一条 Reject，第二条 Selected；雨夜镜头复用角色与场景、切换 Look / State，用于回归本地 Mock。所有这些都是测试数据。

验证：`python -m unittest discover -s tests -v`；交付数据检查：`python tools/verify_a03.py`。A-01 / A-02 的固定示例验收脚本和历史回执保留，当前新增数据请使用 A-03 检查脚本。正式启动仍为 `python -m app.gui` 或 `start.cmd`。

正式回执：[A-03 施工回执](evidence/A-03/A-03施工回执.md)。

## A-04：DSH 外部编排与能力证明

官方 DeepSeek Harness 0.1.5-rc.2 通过四个生产工具读取已有 Shot、构建任务、执行 fal Fixture、调用 ffprobe 并回读结果。使用无密钥、确定顺序的工具编排，没有调用 DeepSeek 模型，也不代表已验证自主 Agent 规划。

关闭正在编辑同一数据目录的 GUI，在根目录执行：

```powershell
python tools/run_harness.py da107ac03bf949c0a099b4159fea8701
```

每次执行会新建一个候选 Take，DSH 完成后退出。再用原 GUI 进行播放及人工审核；A-04 当时未修改 GUI；A-05 已整理为生产工作台。数据不依赖 DSH 进程或 trace，原启动方式与 Python 依赖不变。不要同时运行多个写入者。

外部运行时安装、四个工具语义和版本约束见 [DSH 接入说明](integrations/dsh/README.md)。A-04 历史交付核验入口为 `python tools/verify_a04.py`（包含当时 GUI 哈希；A-05 使用新核验入口）；完整自动测试仍为 `python -m unittest discover -s tests -v`。该交付核验针对本轮固定示例，后续人工选择或编辑数据后不要求继续保持这一基线。

本轮实际运行新增一条雨夜 fal Fixture 候选视频，未自动 Select。模型与视频 API 调用均为 0。ComfyUI、WhisperX、OTIO 未接入。

交付：[A-04 施工回执](evidence/A-04/A-04施工回执.md)、[架构](evidence/A-04/architecture.md)、[开源集成图](evidence/A-04/open-source-integration-map.md)、[能力证明与简历候选](evidence/A-04/resume-evidence.md)。

## A-05：生产工作台整理

继续使用 Tkinter / ttk，未增加运行依赖。Production Core、Schema、原 data、Provider Adapter、DSH Bridge 和三份冻结文档保持不变。

操作验收使用完整数据副本，新增 A-05 示例 Shot，并实际执行生成、Reject、Retry、Select。原 data 保持原样。要打开这份验收副本：

```powershell
python -m app.gui --data-dir evidence/A-05/gui-data
```

测试：`python -m unittest discover -s tests -v`。本轮固定交付数据核验：`python tools/verify_a05.py`；未来用户正常编辑数据后无需保持这一固定基线。

[UI 审计与边界](evidence/A-05/ui-audit.md) · [Before / After 与截图](evidence/A-05/UI-before-after.md)。A-05 已完成真实 GUI 主链、重启与窗口补验，31 项自动测试通过。正式交付见 [A-05 施工回执](evidence/A-05/A-05施工回执.md) 和 [精选截图](evidence/A-05/screenshots.md)。

## A-06：ComfyUI 图像与首帧生产

无需安装 ComfyUI 或模型，不需要 API Key；仅通过官方 API 契约的本地 Fixture 验证工程链。默认远程模型槽尚未配置，REAL 不可用。

1. 角色页先保存角色、选择 Look，点“生成角色参考图 →”；场景页选择 State，点“生成场景参考图 →”。
2. 图像 / 首帧页填写描述，点“生成图像 · ZERO-CALL”。完成后预览真实 PNG，图片明确标注 FIXTURE / MOCK。
3. 可人工“采纳为稳定参考图”或“采纳为当前 Look / State”；不采纳时 Reject，可调整描述 Retry。不会自动加入资产。
4. 在 Shot 页点“生成 Shot 首帧 →”，人工选择“用作 Shot 首帧”。该关系独立于视频 Selected Take。
5. 后续生成 fal Fixture 视频时，首帧快照进入 Video Task，并映射 start_image_url；原 Character / Scene Reference 仍保留。Review 显示当次首帧输入。
6. 图像、任务、工作流、Retry 与采纳关系均随 data 持久化。关闭并重新启动仍可读取；已选首帧对应的 Shot 资产变更后，会要求重新生成并选定首帧。

新增关键位置：app/image_production.py、app/comfy_adapter.py、app/image_gui.py；数据为 image_tasks/、image_executions/、image_results/、image_reviews/、first_frames/。Reference 增加可选 source_image_result_id；Video Task 增加可选 first_frame；旧 JSON 无需批量迁移，原 data 未改。

普通生成仍可用 start.cmd。查看本轮完整验收副本：

```powershell
python -m app.gui --data-dir evidence/A-06/gui-data
```

关闭编辑同一数据目录的 GUI 后，可用已有 DSH 执行首帧候选生产：

```powershell
python tools/run_harness.py d8094901e03441f1bb9ad8696bb427c0 --data-dir evidence/A-06/gui-data --mode first-frame
```

DSH 只产生候选，不采纳。执行会增加图像任务；不要与 GUI 同时写入同一目录。原 video 模式保持。

验证：`python -m unittest discover -s tests -v`（41 项）；本轮固定验收数据：`python tools/verify_a06.py`。正常用户修改数据后不必保持交付副本基线。

[正式回执](evidence/A-06/A-06施工回执.md) · [接口与限制](evidence/A-06/comfyui-integration.md) · [工作流和三种 Dry Run](evidence/A-06/workflow-mapping.md) · [截图](evidence/A-06/screenshots.md) · [架构](evidence/A-06/architecture.md) · [能力证明](evidence/A-06/resume-evidence.md)。

已验证工程链；真实 ComfyUI / Kling 生成、模型图像质量、一致性、首帧质量与成片质量尚未验证。参考图拼板 img2img 模板不是经过质量验证的连续角色生产方案。
