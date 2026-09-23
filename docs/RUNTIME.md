# Runtime — 生成、Provider、Creative 与 Assembly

[返回 Project Map](PROJECT_MAP.md) · 业务对象与 transient 执行状态必须分开。

## Production 生成链

```mermaid
flowchart LR
  Script[Formal Script] --> Req[Requirement]
  Req --> Resolve[Asset resolution / Missing / FREE]
  Resolve --> Prompt[Prompt composition]
  Prompt --> Request[ProductionRequest]
  Request --> Capability[ModelManifest capability]
  Capability --> Provider[ProviderAdapter]
  Provider --> Job[RuntimeJob]
  Job -->|success + validated media| Candidate[Candidate]
  Candidate --> Review[Review]
  Review -->|explicit bind| Current[Current]
  Current --> Finishing[ChapterFinishing]
```

`app/preparation/runtime.py` 定义 `ProductionRequest`、`ModelManifest`、`CapabilityReport`、`RuntimeJob`、`ProductionBatch`、`ProviderAdapter`、`ProviderRegistry`、`ProductionRuntime`。Request/Job/Batch 写入 `project.json` 的 `runtime_*`；Provider 工作目录在 `production/runtime/{job-id}`。能力决策区分 native、translated、unsupported；不要把不支持的输入假装已用。Job 有 queued/running/succeeded/failed/canceled 状态。结果先验证和 ingest，经 `ProductionService` 产生 Candidate；失败或取消不生成 Candidate，也不自动设 Current。重试/恢复/取消应保留可观察记录；Candidate 的可用性还要检查媒体 SHA，Stale 不等于删除。`app/preparation/prompt.py` 是 Prompt 组合入口。

### Provider 实况

| 边界 | `CURRENT` | 不能推断 |
| --- | --- | --- |
| 媒体生成 | `default_registry()` 注册 `FixtureProvider`：image、audio（asset/dialogue/background）、video（含 text-only）零调用模型 | 商业 image/video/audio Provider 已交付 |
| Creative 文本 | `creative.py` 的 `FixtureTextProvider` 与可配置 `OpenAICompatibleAdapter`；base URL/model 从 Settings 或环境取，key 从环境取 | 凭据持久化、厂商专项插件 |
| legacy/integration | `app/fal_adapter.py`、`integrations/`、Harness/DSH 测试和旧测试存在 | 它们已接入 D Production default registry |

新媒体 Provider 从 `ProviderAdapter` + `ModelManifest` 的 capability/输出契约接入，再补合同、失败、取消、ingest、GUI 与打包验证；不能仅在下拉框加名字。API key 不写 `project.json`/Settings。真实外部 API 的费用、超时、限流和数据外发需单独产品决策。

## Creative Flow

```mermaid
flowchart LR
  Conversation --> Run[CreativeRun / text provider]
  Run --> Proposal[Proposal + Diff]
  Proposal --> Human[Human Draft]
  Human -->|valid + scope + not stale + explicit Apply| Script[Production Script]
```

`CreativeService` 将 conversation、proposal、run、request 持久化于项目；它们不是 script。`CreativeRuntime` 调文本 Provider；真实 API 调用是可选的。`CreativeService.apply()` 先检查 stale、open、parse valid、scope，再调用 `Workspace.apply()`，记录 revision/事件，并把其他 open proposal 标为 stale。Apply 后正式剧本变更，用户仍可停留在 Creative，路由不是 mutation 边界。Human Draft 即使编辑完成也仍需 Apply。失败 run 不能绕过人类门禁。

## Preparation 与共享需求

`script.py` 解析剧本声明 Chapter/Shot/Requirement；剧本不负责文件管理。`Workspace` 扫描 `library`，依 requirement 对文件/绑定作 resolution：exact match、missing、unresolved、changed、resolved、FREE。现有 exact-match 可在唯一、非 Candidate 的素材上形成自动引用；**这不是自动 Current Candidate**。Requirement/Asset 共享使跨 Shot/Chapter 的角色/场景/声音资源只需准备一次。Generate 走 ProductionRuntime，Import 走 Workspace/ProductionService；FREE 仅是无需参照的决定，仍保留需求。Prompt/生成消费 resolved reference，不应把 missing 渲染为已完成。

## Assembly Flow

`app/preparation/finishing.py:ChapterFinishing` 读取正式 Chapter/Shot 和 Current 的 shot video；`SoundProduction` 提供对白 Current、环境音 Current 与字幕计划。可编辑 segment 有稳定身份及 trim/move/split/remove；编辑持久化到 `assemblies[chapter_id]`。`resolve()` 报告缺失/错误，**没有 Current 的 Shot 保留其真实序列位置**；不以别的 Candidate 或占位物假装完成。`preview()`/`output()` 用 FFmpeg 渲染，FFprobe/媒体工具确认输入；`handoff()` 使用 OpenTimelineIO，附带字幕 sidecar 与媒体。输出在 `finishing/{chapter-id}/{quality-or-handoff}/{fingerprint}`，对应文件 SHA/指纹记录可复用已验证结果，状态变化不应无故重建昂贵媒体。

## 后台、失败与关闭

GUI 的 worker 采用现有 Qt 线程/回调，不存在独立的全局分布式 Job 服务。`ActivityAdapter` 从持久 Job/Creative Run/Assembly 输出聚合只读活动；后台结束不自动切换 Workspace。Shell 关闭时会阻止/处理活跃 worker、保存草稿和 session；换项目/异常退出需按现有测试检验。外部 API 错误、媒体丢失、损坏设置、取消、Provider 不支持输入要局部失败并可恢复，不得扩大为伪 Candidate/伪 Output。

`app/resources.py:media_tool` 查找打包 FFmpeg/FFprobe（可用 `AIVIDEO_MEDIA_BIN` 指定）及开发 PATH；portable 的二进制打包由 [Releasing](RELEASING.md) 校验。`OpenTimelineIO` 是 Python 运行依赖；Node 仅用于 Harness/DSH 特定测试/集成，不是正式 GUI 启动依赖。
## 外部依赖与升级验证

| 依赖 | 用途 / 类别 / 交付方式 | 缺失或失败 | 升级验证 |
| --- | --- | --- | --- |
| Python 3.11+ | 源码运行与构建；开发机外部，portable 内嵌解释器 | 源码无法启动/构建 | 全量 + PyInstaller frozen smoke |
| PySide6 6.10.2 | GUI runtime；随 portable 打包 | Shell/页面无法启动或几何变化 | GUI、integration、D 人工视觉、clean/ZIP smoke |
| Pillow 12.1.1、Pydantic 2.x | 图像处理、模型验证；runtime 打包 | 素材/项目模型失败 | domain、媒体、project 兼容 |
| PyInstaller 6.22.3 | 构建期，非用户机外部要求 | 无 portable 产物 | packaging、clean/ZIP smoke |
| FFmpeg / FFprobe | 渲染与探测；构建时取外部分发，portable 内捆绑 | 预览/输出/探测局部失败 | 媒体测试、授权文件、clean/ZIP smoke |
| OpenTimelineIO 0.18.1 | OTIO handoff；runtime 打包 | 交接导出失败 | `test_chapter_finishing`、portable handoff |
| Node / DSH | Harness/DSH 开发测试集成；不随普通 GUI 必需 | 特定桥接测试失败 | `test_harness`、对应 integrations |
| OpenAI-compatible API | 可选 Creative 文本外部服务；凭据环境变量 | Creative 真实请求失败，fixture/项目仍应可用 | text contract/失败/取消；独立在线验收 |

版本从 `requirements.txt`、`requirements-build.txt`、构建脚本核对；上表不是自动升级承诺。