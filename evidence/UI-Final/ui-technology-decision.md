# UI 技术决策

结论：保留 Tkinter / ttk，沿用现有 clam Style，整理共享组件和导航；不新增依赖，不改 start.cmd，不重写业务页面或核心 Production Truth。

## 现场审计

实际浏览了资产、参考图、Shot、图像、视频审核、Voice、Dialogue、音频审核、Timeline 与工程详情。Before 截图来自 A-08 应用和完整副本。主要问题：

- 7 个主 Tab 按施工阶段平铺，资产、审核和交付职责混杂；Voice / Dialogue / Audio 藏在共同标签内。
- Shot 表单有谁/哪里/动作，但首屏缺少首帧、视频、音频、字幕、Timeline 的统一生产摘要。
- Image 主画面直接展示长 Prompt / ID；Audio 及 Dialogue 默认含原始任务或 Handoff 文本；Timeline ID / build path 混入生产摘要。
- Review 的 Selected 和其他页面 Completed / 已采纳命名不统一，按钮层级有差异。
- 最小窗口被 1100×740 逻辑尺寸限制，在当前 Windows 缩放下约 1674×1169 物理像素，不能覆盖 1366×768。
- A-05 Reference 的列表+旁侧预览已有效，保留结构；视频 Review 媒体中心结构也保留，不全面推倒。
- Timeline 校验和 FFmpeg 在 GUI 主线程，切页/装配可能卡顿；只优化 UI 调用方式，不改装配算法。

## 方案

使用分组侧栏：生产（镜头、对白），资产（角色、场景、声音），审核（图像、视频、音频），交付（粗剪）。保留底层 Notebook 的页面对象与原 select API，通过 UI 路由同步导航，避免重写业务绑定。默认进入 Shot；无数据时提示先建资产。

视觉采用浅灰工作区、白色编辑面、深墨色导航、单一绿色主操作；警告/错误保留文字状态；字体用系统 Microsoft YaHei UI / Segoe UI fallback，不装字体或图标。统一缩略图、按钮层级、状态 Badge、折叠 Advanced 与可换行操作栏。控件继续来自 ttk，少量复合组件不演化为框架。

核心 models、providers、persistence、schemas、DSH 和历史测试文件不修改。只读展示派生状态，任何缺失/错误不写回生产状态。所有实际操作用 UI-Final/gui-data 副本。
