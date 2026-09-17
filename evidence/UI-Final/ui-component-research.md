# UI 组件窄调研（2026-09-16）

| 方案 | 维护 / 许可 / 兼容性 | 组件与代价 | 决策 |
|---|---|---|---|
| A 原生 ttk + Style | Python 标准库持续维护；随 Python/Tcl/Tk 许可；本机 Python 3.13 已真实运行 | 原生 Treeview、Notebook、Panedwindow、Dialog、Progress；侧栏/Card/Badge/空态是少量组合；无新增体积 | 采用 |
| B ttkbootstrap | 官方仓库活跃，PyPI 发布；MIT；当前仓库声明 Python 3.10+、纯 Python + Pillow | 可渐进混用 ttk；主题、表格、对话框、tooltip等成熟。2.x 有迁移变化；不能直接解决业务信息架构，需要额外样式兼容核验 | 不安装，当前已有 Style 足够 |
| B sv-ttk / Sun Valley | 官方仓库与 PyPI 可用；MIT；Tcl 主题包，Windows 风格 | ttk 渐进主题，非 ttk Text/Listbox 仍需单独处理；圆角/主题收益不能替代结构整理；未声称本机 Python 3.13 已实测 | 不安装 |
| C 局部 Composite / Canvas | 复用现有 ScrollArea、AssetCard、Rows；新增少量组合可受现有测试约束 | Badge / ActionBar / 导航路由；Canvas 只用于已有滚动区域，避免自绘所有控件/焦点/键盘 | 采用少量 Composite |
| D PySide6 / Qt | 官方持续维护，Windows 支持；LGPLv3/GPLv3/商业许可；含 Qt 二进制 | Widget丰富、DPI成熟，但需重写 Tk 页面、变量、事件与 GUI 测试，部署负担明显增大 | 无结构性必要，不迁移 |

共享能力映射：侧栏、卡片、状态、空态用 ttk Label/Frame/Button 组合；滚动与缩略图沿用现有 ScrollArea/Rows/Pillow；分栏 ttk.Panedwindow；表格 Treeview；Tabs Notebook；Progress ttk.Progressbar；Dialog 使用 Tk；图标不新增下载，文字始终可读。DPI 和 resize 通过本机实际窗口验证，而非主题截图推断。Thumbnail 缓存和异步媒体操作属于本轮 UI 性能范围。

官方依据：

- [Python ttk](https://docs.python.org/3/library/tkinter.ttk.html)
- [ttkbootstrap 官方仓库与迁移说明](https://github.com/israel-dryer/ttkbootstrap)
- [ttkbootstrap PyPI](https://pypi.org/project/ttkbootstrap/)
- [Sun Valley 官方仓库](https://github.com/rdbende/Sun-Valley-ttk-theme)
- [sv-ttk PyPI](https://pypi.org/project/sv-ttk/)
- [Qt for Python 官方许可与安装](https://doc.qt.io/qtforpython-6)
- [Qt 官方平台支持](https://doc.qt.io/qtforpython-6/overviews/qtdoc-supported-platforms.html)

没有根据第三方截图宣称 Windows 稳定性，也没有为了调研强行装库。最终判断是布局和信息层级问题可在现有 ttk 上解决，迁移收益低于风险。
