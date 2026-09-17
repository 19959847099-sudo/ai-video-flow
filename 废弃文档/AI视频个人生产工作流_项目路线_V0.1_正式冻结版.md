# AI 视频个人生产工作流｜项目路线 V0.1 正式冻结版

**版本：V0.1**  
**冻结日期：2026-09-14**  
**状态：正式冻结**  
**上位依据：`项目定义 V0.1`**  
**本文件负责：规定大致技术路线、阶段结果、施工方向与阶段升级逻辑。**

---

## 1. 路线原则

本项目路线不采用传统“功能清单式 Roadmap”。

不写成：

```text
数据库
↓
API
↓
UI
↓
Dashboard
↓
Agent
```

本路线以：

> **获得新的、可验证的生产能力**

作为阶段划分依据。

技术模块只是实现阶段结果的手段。

---

## 2. 结果导向原则

每个大阶段必须明确回答：

1. 本阶段结束后，项目新获得什么能力？
2. 什么真实结果可以证明该能力存在？
3. 最小施工是什么？
4. 什么算完成？
5. 这一阶段完成后能展示什么能力？
6. 下一阶段由什么真实事实触发？

因此：

> **路线规定结果，不提前冻结尚未被真实需求证明的具体实现。**

---

## 3. 总体技术路线

项目长期采用：

> **本地优先 + 核心数据独立 + 现成工具复用 + 薄控制层。**

整体结构：

```text
Human / LLM
↓
标准化 Story / Script / Shot / Asset
↓
Production Truth
↓
薄 Control / Glue Layer
↓
Provider / Open-source Tool / Existing UI
↓
Attempts
↓
Review / Retry / Selected
↓
Audio / Timeline / NLE
↓
Final Film + Metrics
```

### 3.1 Production Truth

核心生产事实应独立保存。

初期可以是：

- Markdown；
- YAML；
- JSON；
- CSV；
- 文件系统。

当真实查询与状态管理需求出现后，可升级为 SQLite。

### 3.2 Control / Glue Layer

只负责真正需要统一的部分，例如：

- Shot / Attempt 状态；
- Provider 调用；
- Prompt 编译；
- 文件入库；
- Review 状态；
- Retry 上下文；
- Metrics；
- 展示层。

不负责重新实现成熟生成器、播放器或 NLE。

### 3.3 Peripheral Tools

外围工具允许随时替换，包括 ChatGPT / LLM、图像模型、视频模型、ComfyUI、TTS、WhisperX、OpenTimelineIO、CapCut / Resolve / Premiere、开源 UI、浏览器播放器组件。

---

## 4. 默认技术选型原则

以下为路线级默认倾向，不视为永久锁死。

### 数据与文本

优先：

```text
Markdown / Fountain
YAML
JSON
CSV
```

需要真实状态查询后：

```text
SQLite
```

### Glue / Control

优先：

```text
Python
Pydantic / JSON Schema
Typer / argparse
Jinja2
HTTP / SDK adapters
```

### 媒体处理

优先：

```text
FFmpeg / ffprobe
现成播放器组件
OpenTimelineIO（出现时间线交换需求时）
WhisperX / Forced Alignment（出现字幕/对齐需求时）
```

### UI

优先顺序：

1. 现成工具 UI；
2. 原生浏览器能力；
3. 极薄本地 Web UI；
4. 只有真实摩擦证明需要时再扩大。

不预设必须建设完整 Studio。

---

## 5. 开源复用路线

### AI Movie Studio 2

路线定位：**LEARN 为主，必要时 EXTRACT。**

重点学习：Shot / Asset / Continuity、Provider Driver、Generation Recipe、Take / Retake、Timeline / Export、数据结构与 UI 组织方式。

不默认将其作为整个项目底座。

### ComfyUI

路线定位：**有本地生成或图工作流需求时 USE / INTEGRATE。**

不把它当作生产管理系统。

### WhisperX

路线定位：**需要字幕 / 对齐时直接 USE。**

不自研同类基础能力。

### FFmpeg / ffprobe

路线定位：**基础媒体处理直接 USE。**

承担元数据、技术 QA、转码、缩略图和基础媒体操作。

### OpenTimelineIO

路线定位：**真实出现自动粗剪 / Timeline 交换需求时 INTEGRATE。**

不提前为了“架构完整”接入。

### 其他大型 Production Tracker / VFX Pipeline

例如 Kitsu、AYON 等工作室级 Production 系统：**LEARN 为主，不默认部署。**

---

## 6. 阶段 A：建立真实生产基线

### 阶段目标

不是“把系统做出来”。

而是：

> **用当前最小工作流完成一条真实 AI 视频作品，并留下足够完整的生产事实。**

### 必须得到的结果

至少包括：

```text
真实成片
Story / Script
Shot 列表
核心 Asset
真实 Attempts
Selected Takes
Failure / Retry 记录
基本时间记录
基本 Friction Log
```

### 最小施工

只建立足以支撑真实生产的：

- 文件结构；
- 命名；
- Script / Shot / Attempt 最小格式；
- Failure 最小分类；
- Selected Take 表达；
- Friction Log。

允许大量手工操作。

### 不要求

本阶段不要求 Web UI、Provider API、自动 Queue、SQLite、自动 QA、Prompt Compiler、自动 Timeline、Dashboard。

### 验收

阶段完成必须满足：

> **真实作品已经完成，且能够从记录中还原主要生产过程。**

只有文件存在、但没有真实作品，不算完成。

### 本阶段展示能力

证明：能完整完成 AI 视频生产；理解 Shot / Attempt / Asset / Retry；能进行生产记录；能从真实过程发现问题。

---

## 7. 阶段 B：找出并消灭最大的真实摩擦

### 阶段入口

阶段 A 完成后，根据真实 Friction Log 和生产记录选出：

> **当前最值得消灭的高频摩擦。**

优先级参考：

> **发生频率 × 摩擦程度 × 可消除程度**

### 阶段目标

> **让一类真实高频操作显著变少。**

### 可能方向

候选包括但不限于：Prompt / Reference 重复搬运、API 提交、下载与命名、Shot / Attempt 状态、Review、Reject / Select、Regenerate、文件查找、Metrics、技术 QA。

路线不提前指定必须解决哪一项。

### 验收

必须满足：

1. 该摩擦来自阶段 A 真实生产；
2. 有明确“改前”状态；
3. 新方案确实减少步骤、时间或状态恢复成本；
4. 没有引入更大的维护摩擦。

### 本阶段展示能力

证明：能发现真实瓶颈；能做 Build / Reuse / Integrate 判断；能用工程手段解决实际生产问题；不为了开发而开发。

---

## 8. 阶段 C：形成高价值生产闭环

### 阶段入口

当阶段 B 的真实数据表明某一组相邻摩擦高度集中时，才进入本阶段。

当前已知的高潜在闭环之一是：

```text
Shot
↓
Generate
↓
Wait / Result
↓
Review
↓
Select / Reject
↓
Failure
↓
Retry / Regenerate
```

但这不是强制实现内容。

### 阶段目标

> **把一个高频、多次切换上下文的生产链压缩成连续、低摩擦的闭环。**

### 可能实现

如果真实数据支持，可采用：

```text
Provider API
+
Attempt State
+
自动入库
+
现成播放器 / 浏览器 Video
+
Select / Reject
+
Failure Code
+
Regenerate
```

允许使用现成项目 UI、嵌入现成播放器、跳转外部 UI、自建极薄 Review 页面。

### 关键要求

不自建视频解码器、专业 NLE、大型 Review 平台。只统一真正需要统一的生产状态。

### 验收

必须能够通过真实 Shot 完成：

> **生成 → 审核 → 决策 → 返工 → 最终选用**

并且明显减少手工恢复上下文。

### 本阶段展示能力

证明：API 接入、状态管理、媒体处理、UI / Workflow 集成、Retry 逻辑、真实生产闭环设计。

---

## 9. 阶段 D：形成可展示的能力证明层

### 阶段目标

不是“把 UI 做漂亮”。

而是：

> **让招聘方在几分钟内看懂工作流、真实生产事实和能力价值。**

### 可展示内容

推荐至少支持展示：

```text
Final Film
Shot List
某个 Shot 的多个 Attempts
Failure / Retry
Selected Take
Model / Provider
时间
成本
摩擦变化
```

### UI 定位

展示层可以比内部工具更整洁。

但展示页面只是：

> **Production Evidence Viewer**

而不是新建一个假想 SaaS。

### 验收

一个不了解项目的人能够在较短时间内理解：

1. 作品是什么；
2. 生产怎么跑；
3. 哪里会失败；
4. 工作流解决了什么；
5. 哪些判断仍由人完成；
6. 项目体现了哪些能力。

### 本阶段展示能力

证明：能把复杂工程信息转成清晰表达；能做轻量产品化呈现；能用真实证据展示能力。

---

## 10. 阶段 E：数据驱动的二次优化

### 进入条件

只有完成至少一轮真实“改前 / 改后”生产，才进入。

### 阶段目标

> **用真实数据证明至少一个工作流优化确实有效。**

### 重点指标

优先：

- Human Time / Finished Minute；
- Attempts / Accepted Shot；
- First-pass Acceptance；
- Rejected Generation Cost；
- Retry Rate；
- Prompt / File / State 恢复时间；
- 高频 Friction 总次数。

### 可能扩展

只有数据证明值得，才考虑：Prompt Compiler、Rule-based Router、自动 Technical QA、VLM Flag、自动 Rough Cut、OTIO Export、Retry Advisor、更多 Provider Adapter、更完整 Review UI。

### 验收

不能只说“更快”。必须有真实对比。

---

## 11. 候选能力池

以下功能进入候选池，但不进入强制路线：

```text
Prompt Compiler
Rule-based Model Router
Provider API adapters
Generation Queue
Attempt Ledger UI
Review UI
Failure Classification UI
Regenerate
Technical QA
VLM QA Flag
TTS / Alignment
OpenTimelineIO Rough Cut
Metrics Dashboard
Agent / MCP
```

升级为正式阶段能力的条件是：

> **真实生产已经证明它足以解决明显摩擦，或显著增强项目核心能力展示。**

---

## 12. API 路线

API 接入不被固定为“后期高级功能”。

是否提前接入由真实摩擦决定。

如果人工平台操作已经成为高频摩擦，则可以提前进入。

第一批 API 应遵守：

1. 只接真实会用的 Provider；
2. 优先 1 个跑通，再考虑第二个；
3. 核心数据不绑定 Provider；
4. Adapter 保持薄；
5. Provider 变化不应迫使核心数据迁移。

不建设十几家 Provider 的统一大网关。

---

## 13. UI 路线

UI 施工顺序：

1. 使用现有 UI；
2. 将已有 UI / 播放器 / CLI 拼入工作流；
3. 只为高频状态交互写极薄界面；
4. 只有展示或真实使用证明有价值，才进一步整理视觉与交互。

本项目允许最终仍然是一套：

> **多个现成 UI + 一个薄 Control Page + CLI**

的组合。

---

## 14. 数据路线

### 初始

优先简单透明：

```text
filesystem
Markdown
YAML
JSON
CSV
```

### 升级条件

出现以下真实需求后再进入 SQLite：

- Attempt 数量开始难管理；
- 需要跨 Shot 查询；
- 需要计算 Metrics；
- 需要 UI 持续读写状态；
- CSV 开始出现同步困难。

### 不做

除非出现明确事实，不引入 PostgreSQL、Redis、MQ、Vector DB、云对象存储、微服务。

---

## 15. 施工方法

每一阶段内部按照：

```text
结果目标
↓
最小设计
↓
开源 / 现成工具审计
↓
决定 USE / INTEGRATE / EXTRACT / LEARN / BUILD
↓
最小施工
↓
真实验证
↓
验收
↓
记录新摩擦
```

不得反过来：

```text
看到一个技术
↓
想办法把它塞进项目
```

---

## 16. 阶段升级原则

阶段升级不以日期或代码量为依据。

满足：

> **当前阶段结果已经真实存在，并且主链稳定。**

即可收口。

不因追求“再完善一点”无限延长阶段。

新阶段必须来自：

> **项目定义 + 当前真实状态 + 已观察到的摩擦 / 展示需求。**

---

## 17. 路线调整原则

本路线允许调整具体施工顺序。

但任何调整必须至少满足其一：

1. 真实生产发现了更大的摩擦；
2. 新开源项目显著降低施工成本；
3. Provider / API 现实发生变化；
4. 当前技术方案产生明显维护负担；
5. 能力展示需要出现更高价值的真实证据。

不得因为“技术看起来更先进”改路线。

---

## 18. 最终路线摘要

```text
A：真实跑通并留下生产事实
↓
B：找到最大的真实摩擦
↓
C：建立高价值生产闭环
↓
D：把真实生产能力清楚展示出来
↓
E：用数据继续优化

每一步：
真实结果 > 功能数量
最小施工 > 架构完整
复用 > 重写
生产事实 > 演示幻觉
```

---

## 19. 路线成功标准

项目路线成功不是“按计划写完所有模块”。

而是最终形成：

> **一条真的能跑的 AI 视频生产链，至少解决若干高频生产摩擦，同时能够通过真实作品、真实 Attempts、真实失败与真实数据，清楚展示本人在 AI 视频生产与 AI Workflow Engineering 上的综合能力。**
