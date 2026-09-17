# A-05 UI Before / After

Before 使用 A-04 已实际保存的 [旧 Review 截图](../A-04/gui-harness-result.png)，没有重新绘制旧界面。After 来自本轮真实 Tk 窗口与生产数据副本；视频与资产仍明确标记为示例 / Fixture。

| 原有问题 | 本轮调整 |
|---|---|
| 角色、场景主要是平级表单 | 封面、身份摘要、Look / State 与参考图数量组成资产概览；详情按身份、变体、参考图分区 |
| Reference 预览小，用途分散 | 缩略图列表直接显示身份图 / 稳定图与所属 Look / State，选择后显示更大预览 |
| Shot 列表只有描述 | 同行显示角色、场景、短 ID、派生状态和 Take 数量；详情按谁 / 在哪里 / 做什么分组 |
| Review 预览和按钮被文本挤占 | 左侧 Take 导航、中间大预览、右侧人工决策，底部上下文分层 |
| Selected 主要依赖一行文字 | 独立颜色标签、列表底色、最终 Take 提示与禁用重复选择按钮共同表达 |
| Task ID、路径与 Prompt 混在同一大文本区 | 默认生产上下文；执行摘要和工程详情单独页签保留 |
| Mock / fal 模型名容易混淆 | 明确显示 MOCK / ZERO-CALL，标注 Fixture 未真实调用，REAL 未启用 |
| 缩小窗口可能隐藏 Retry | 决策区可滚动，Retry 固定在列底部；长文本有独立滚动条 |

本轮未更换 GUI 技术、未新增运行依赖，也未修改 Production Core、Schema、Provider 或 DSH Bridge。界面依然是生产数据的操作与展示层。

## 已保存的实际操作证据

- [角色参考图](character-references.png)
- [场景参考图](scene-references.png)
- [Shot 创建](shot-created.png)
- [Rejected Take](review-rejected.png)
- [Selected Take 重启恢复](review-selected-restarted.png)
- [小窗口 Retry 区域](review-minimum-retry.png)
- [Harness 历史执行摘要](harness-final.png)
- [实际 MP4 播放](playback.png)

最终重启、字体层级与最小窗口补验已完成。Reference 预览最终移至列表右侧，避免挤压列表高度；见 [角色最小窗口](references-resize-final.png) 与 [场景最小窗口](scene-references-resize-final.png)。精选最终版本见 [截图索引](screenshots.md)。
