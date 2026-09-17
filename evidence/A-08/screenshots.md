# A-08 桌面验收截图

主验收对象：3bb952d7018548bcbd60b7e8ae9e5297。使用真实 Tk 窗口、鼠标、键盘与 FFplay；操作序列见 actions-create.json、actions-finish.json、actions-restart.json。

- [未选视频明确阻断](blocked-missing-selected.png)
- [人工顺序与 Ready / Warning](timeline-ready.png)
- [编码完成后的 Timeline](timeline-preview-completed.png)
- [首次实际播放](preview-playback.png)
- [GUI Export Handoff](handoff-created.png)
- [完全重启后的顺序](restart-timeline.png)
- [小窗口布局](minimum-timeline.png)
- [重启后的实际播放](restart-playback.png)
- [重启与 DSH 结束后再次导出](restart-handoff.png)

预览不是 Final Master；字幕与音频仍为 Fixture。最初 timeline-built.png 捕获时 FFmpeg 尚在编码，实际完成证据使用 timeline-preview-completed.png，不把早期截图作为播放通过证明。重启验收曾因桌面锁定暂停，用户恢复桌面后已经重新完成。
