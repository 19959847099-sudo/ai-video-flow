# Data Model — Truth、身份与持久化

[返回 Project Map](PROJECT_MAP.md) · `CURRENT` 实现以 `app/preparation/workspace.py`、`script.py`、`production.py`、`sound.py`、`creative.py`、`finishing.py` 为准。

## Truth ownership map

| 对象 | Owner / 落盘 | 允许 mutation | 消费者 / 是否正式 Truth |
| --- | --- | --- | --- |
| Production Script | `Workspace.apply`；`project.json.script` | 有效显式 Apply（Preparation 或 Creative） | Requirement/Production/Assembly；**正式** |
| Script draft | `Workspace.save_draft`；`project.json.draft` | 编辑器 | Apply 输入；非正式 |
| Requirement | `script.py` 从正式剧本派生；引用/决策在项目状态 | 剧本 Apply、Preparation 决策 | Resolution/Prompt/Production；派生业务事实 |
| Asset | `Workspace.scan/import_asset`；`project.json.assets` + `library/{kind}` | 扫描、导入、绑定 | Requirement、Prompt；素材事实，不等于 Candidate |
| Candidate | `ProductionService`；`project.json.candidates` + 项目内媒体 | 成功 ingest、导入、review | Production/Current；正式候选，但非 Current |
| Review | `ProductionService.review`；Candidate 记录 | 用户审核 | 绑定门禁；Green 非 Current |
| Current Binding | `ProductionService.bind/bind_shot`、`SoundProduction`；`bindings/shot_bindings/dialogue_bindings/background_bindings` | 用户显式绑定 | Assembly/Prompt；**正式选择** |
| Selected | UI/route memory；`ui` 或窗口临时状态 | 用户导航 | 展示；非 Current |
| Missing / unresolved / changed | `Workspace` resolution 计算 + 检测事件 | 扫描、文件变化、决策 | actionable 诊断；非虚构素材 |
| FREE | `Workspace.set_reference_required` 的需求决策 | 用户显式设定 | 放弃素材依赖，不创建 Asset |
| Creative Conversation | `CreativeService`；`creative_conversations` | 用户/Creative 流程 | 上下文记录；非剧本 |
| Creative Proposal / Diff | `CreativeService`；`creative_proposals` 等 | AI 生成、Human Edit、stale/apply 标记 | 供审阅；非剧本 |
| Human Draft | Proposal 的可编辑 draft | 人编辑 | Apply 输入；仍非正式 |
| Assembly Edit | `ChapterFinishing`；`assemblies[chapter_id]` | 用户 trim/move/split/remove | 渲染计划；项目内正式编辑状态，非 Production Current |
| Runtime Job | `ProductionRuntime`；`runtime_requests/jobs/batches` | 提交、轮询、取消、重试/恢复 | Activity/Production；过程记录，不等于 Candidate |
| Application Settings | `AppSettingsStore`；本机 `settings-v1.json` | Settings 页/显式保存 | Shell/Provider config；系统状态，非项目 Truth |
| Workspace memory | `WorkspaceRouter`；`project.json.ui.integration_v1` | 导航、记忆/Return | UI；非领域 Truth |
| Output artifact | `ChapterFinishing`；`finishing/...` + `assemblies` 记录 | preview/output/handoff | 交付派生物；不改 Current |

**不可混同**：Green ≠ Current；Selected ≠ Current；FREE ≠ Asset；Proposal/Human Draft ≠ Production Truth；Global Default ≠ Project Truth；Failed Job 不生成 Candidate；Stale 保留记录；Missing 是正常可处理状态。准确的消费链见 [Runtime](RUNTIME.md)。

## 身份与媒体定位

`project_id` 是 UUID；`script.py:identity()` 用 project UUID + 稳定 key 生成 Chapter/Shot 身份，`requirement_id(kind,name)` 由类型和名称哈希派生。Asset 是独立 UUID，不用路径作身份；`Workspace.scan()` 用校验和、重命名唯一配对、历史快照追踪媒体变化。重命名不应任意改变 Asset identity，但内容变更可能让引用变为 changed/stale；不是删掉记录。Candidate 是独立 UUID，保存关联的 project/requirement/dialogue/background/chapter/shot、SHA、来源、Provider/Job、Review 等。Assembly segment 独立 UUID；对白按 shot + ordinal 派生的身份在脚本文本重排时更脆弱，是已知兼容观察点。

项目内媒体路径由 `Workspace.path()` 限定在项目根内；`library/{kind}`、`.history/media/{sha}.{ext}`、`production/runtime/{job-id}` 和 `finishing/...` 是实际目录。移动**整个**项目根而保留相对结构可继续定位项目内媒体；外部引用、上次项目绝对路径及 Settings 不保证自动重定位，需实测，不要承诺无条件 relocation。

## project.json 与 schema

`Workspace` 初始化 `<project>/project.json`，当前格式标签严格为 `preparation-0.2`。根对象包含 `project_id`、`draft`、`script`、`assets`、`bindings`、`history/events/revisions`、`ui`、`candidates`、`runtime_requests/jobs/batches`、`dialogue_*`、`background_*`、`voice_*`、`subtitles`、`sound_prompts`、`creative_*`、`reference_decisions`、`prompt_drafts`、`shot_bindings`、`assemblies` 等。旧同版本文件由 `setdefault` 填缺省字段；写入借用 `app.core.write_json` 的原子写法。字段存在不代表跨版本迁移已保证。

`CURRENT`：无迁移注册表、备份事务、正式兼容政策；未知版本不会被透明迁移。`PLANNED`：ProjectRepository/Migration 作为小型边界，先定义升级/回滚/备份及兼容样本，再动持久化。新增字段需讨论旧项目加载、新项目默认、序列化、旧/新 RC 可否往返，不可只追加 `setdefault` 后宣称兼容。

## 项目外状态

`app/resources.py` 默认项目路径是 `%LOCALAPPDATA%/AI Video Workflow/Projects/workspace-v02`；`session-v1.json` 记上次项目位置，`integration.py:AppSettingsStore` 默认保存 `%LOCALAPPDATA%/AI Video Workflow/settings-v1.json`。`AIVIDEO_CONFIG_PATH` 可改变设置位置；启动参数 `--data-dir`、`--settings-path` 可覆盖。设置 v1 含布局、reduced motion、resume、默认项目路径、文本 base URL/model；坏文件/不支持版本回到默认并记录错误。API key 只从 `OPENAI_COMPATIBLE_API_KEY` 环境读取，不落设置文件；**没有 Credential Store**。

## Mutation 边界

| 动作 | 写入路径 | 禁止捷径 |
| --- | --- | --- |
| 剧本编辑 / Creative Apply | `Workspace.apply` 验证成功才更新 `script`/revision | 直接覆写 `script` 或以 Proposal 代替 |
| 素材导入/扫描/引用 | `Workspace.import_asset/scan/bind/set_reference_required` | 用文件名假定身份；FREE 伪造 Asset |
| 生成与审核 | `ProductionRuntime` → `ProductionService` | 失败 Job 落 Candidate；Green 自动 Current |
| Current | `ProductionService` / `SoundProduction` 显式绑定 | 用 UI Selected 或默认值代替 |
| 章节编辑与输出 | `ChapterFinishing` | 输出回写 Production Current |
| 路由与系统偏好 | `WorkspaceRouter` / `AppSettingsStore` | 把全局默认塞入项目 Truth |

对冻结语义有疑问时读 [正式项目定义](../重要文档/AI视频个人生产工作流_项目定义_V0.2_正式冻结版.md)；实现与冻结文字差异见 [Project Map](PROJECT_MAP.md#现状与冻结文档的阅读警示)。
