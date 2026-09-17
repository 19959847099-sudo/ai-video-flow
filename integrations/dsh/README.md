# DSH 生产工具接入 V0

使用官方 DeepSeek Harness CLI 0.1.5-rc.2，通过隔离 profile 加载外部插件。没有 fork 或修改 DSH 源码，没有模型调用。官方支持不配置密钥而直接执行注册工具，见 [keyless tool execution](https://deepseek-harness.github.io/deepseek-harness/en/develop/cordis-tutorial/07-into-the-harness)。本轮是确定顺序的真实 Harness 工具编排，尚不是 LLM 自主规划。

## 启动

关闭正在编辑同一数据目录的 GUI，在项目根目录运行：

```powershell
python tools/run_harness.py da107ac03bf949c0a099b4159fea8701
```

这会为现有示例雨夜 Shot 新建一次 fal Fixture 执行并产生候选视频。每次启动会增加一次生成；完成后 DSH 自动退出。然后用原 `start.cmd` 或 `python -m app.gui` 打开 Review，由人决定 Select / Reject / Retry。

可用 `--data-dir <目录>` 指定完整生产数据副本；`--output-dir <新目录>` 指定本次证据目录，禁止覆盖已有证据。默认写入 `evidence/A-04/runs/<uuid>/`。

## 可选运行环境

GUI 不依赖 Node 或 DSH。桥接器使用现有 Python 依赖及 PATH 中的 FFmpeg / ffprobe。

本机系统 Node 20 不符合 DSH 要求，因此使用项目内便携 Node v24.21.0，未更改系统 Node。迁移机器时，从 [Node 官方发行目录](https://nodejs.org/dist/v24.21.0/) 下载 `node-v24.21.0-win-x64.zip`，按该目录的 SHASUMS256.txt 校验，解压到项目 `.tools/`，在 `.tools/node-version.txt` 写入 `v24.21.0`。已下载包与校验文件保留在本机 `.tools/`。

在 PowerShell 临时将便携 Node 加入本进程 PATH，再安装锁定依赖：

```powershell
$env:PATH = "$PWD\.tools\node-v24.21.0-win-x64;" + $env:PATH
Set-Location integrations/dsh
npm ci --ignore-scripts --no-audit --no-fund
```

三个官方包统一固定 `0.1.5-rc.2`，并保留 package-lock。安装依赖需要网络；执行生产链不需要网络。初次采用 rc.1 时遇到预发行 peer dependency 混装冲突，统一版本后解决，没有强制忽略依赖约束。官方完整发行版安装约 213 MiB、518 个 npm 包，是可移除的外部开发运行时；实际 profile 只加载 system-prompt、tools 和本项目插件，不启用模型、数据库或云服务。

## 四个工具

| 工具 | 输入 | 实际行为 |
|---|---|---|
| get_shot_context | shot_id | 读取双资产上下文及审核状态，不持久化查询用临时快照 |
| build_generation_task | shot_id | 复用现有 submit，保存中立 Task、ProviderRequest 和 pending Execution |
| dry_run_generation | execution_id | 推进同一次 fal Fixture 执行，复用现有 Result Ingestion |
| inspect_media | result_id | 验证结果关联与哈希，调用真实 ffprobe 返回媒体属性 |

插件在官方 appReady 后经 `ctx.tools.execute` 执行查询、构建、生成、探测、回读。`tools/result` 事件记录在 trace。Python stdio 协议只接受白名单工具与稳定 ID，不接受任意路径、shell、Provider 或 Prompt 覆盖。没有 Select / Reject / Retry 工具。

已有入库逻辑本身先验证媒体，再保存 Result；随后独立的 inspect_media 工具再次展示可解析属性。无需新建重复的“更新 Truth”接口。生成完成不会选择素材。

## 数据与执行边界

`data/` 保持原 Schema、快照、相对媒体路径和审核关系；其中不引用 DSH 会话。Trace 是旁路证据，删除或替换 DSH 不影响原 GUI 读取生产数据。不要同时让 GUI 与 Harness 写同一目录，当前文件存储不提供多写入者事务。异常中断的 pending 执行可由原 GUI 的恢复机制继续处理。

启动器只传递最小环境，不转发密钥；隔离 DSH_HOME 与工作目录，且不加载模型插件。Node 网络预加载器和 Python socket 限制用于验证本轮零连接；它们不是通用安全沙箱。原 fal Transport 本身没有 HTTP 调用路径。网络审计、启动命令、工具摘要和错误分别保存，不记录思维链或参考图 base64。

DSH 尚处于预发行阶段，升级时须重新验证工具、profile 与退出契约。桥接层是替换入口；无需改变核心生产模型。


## A-06 新增图像工具

新增 prepare_shot_first_frame(shot_id)，调用同一个 Python Bridge、ImageProduction 和 ComfyUI Fixture，返回实际 PNG / Task / Result ID 与 human_review_required=true。无 Promote / Select 工具。

`python tools/run_harness.py <shot_id> --mode first-frame --data-dir <data>` 运行 get_shot_context → prepare_shot_first_frame → get_shot_context。省略 mode 仍执行原 video 链。版本、网络锁与隔离环境保持不变，不调用 LLM 或真实图像/视频 API。

## A-07 对白音频编排

使用 `--mode dialogue` 时首个 ID 是 Dialogue ID：

```powershell
python tools/run_harness.py 5c235da8a53240a789836abacaa80d11 --mode dialogue --data-dir evidence/A-07/gui-data --output-dir evidence/A-07/another-run
```

`prepare_dialogue_audio` 在官方 Harness 中实际调用 Python 生产桥：读取 Voice / Dialogue，创建中立 Audio Task，执行 MiniMax 契约 Fixture，回收 WAV，再执行 Alignment Fixture 和 SRT。每次执行增加候选，不能 Select、切换默认 Voice 或修改已有 Human Gate；运行前关闭同目录 GUI。字幕和音频均为测试，未执行真实 TTS 或 WhisperX 模型。

## A-08 粗剪编排

关闭编辑同目录的 GUI 后执行：

```powershell
python tools/run_harness.py 3bb952d7018548bcbd60b7e8ae9e5297 --mode rough-cut --data-dir evidence/A-08/gui-data --output-dir evidence/A-08/another-run
```

首个参数在 rough-cut 模式中为 Timeline ID。`prepare_rough_cut` 读取人工保存的顺序和缺失允许策略，只使用 Selected Video / Selected Audio，验证当前 Alignment，创建 Manifest、真实 OTIO 和 FFmpeg Preview。工具不修改顺序、选择或 Dialogue，不自动 Export Handoff，并返回 human_review_required。未选视频会阻止构建；不调用任何生成 API。输出目录必须是新目录。实际 NLE 导入仍由人完成。
