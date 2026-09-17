# A-06 GUI 证据索引

均为本机 Tk 应用真实鼠标、键盘与窗口操作截图，使用 evidence/A-06/gui-data 示例副本。采纳与 Reject 只用于工程验收，不代表真实模型画质评价。

| 截图 | 证明 |
|---|---|
| character-image-preview.png | 角色图像任务与实际 Fixture PNG 预览 |
| character-promotion.png | 人工采纳为当前 Look Reference |
| scene-promotion.png | 人工采纳为当前 State Reference |
| first-frame-preview.png | 原 Shot 首帧候选 |
| first-frame-selected.png | Reject / Retry 后人工选定第二张首帧 |
| first-frame-restarted.png | 完全重启后人工关系保留 |
| character-reference-restarted.png / scene-reference-restarted.png | Reference 回到原资产，重启可见 |
| shot-first-frame-final.png | Shot 显示明确首帧 ID，与 Selected Take 分离 |
| video-handoff-final.png | 新视频 Take 的首帧快照；原 Take 2 仍为 Selected |
| handoff-playback.png | 真实 FFplay 播放 Fixture MP4 |
| dsh-candidate-after-exit.png | Harness 退出后 GUI 可读候选，未自动采纳 |
| image-review-minimum-final.png | 最小窗口：预览、追溯文本与操作可见 |

normal 截图物理尺寸 2064×1409；最小补验 1674×1169，对应当前 Windows DPI。image-review-minimum.png 是修复前诊断，不作为最终布局证据。小窗口预览缩小以保留追溯文本，可放大窗口查看。

验收辅助：tools/run_a06_probe.py 仅采集控件位置并阻止网络；tools/drive_a06.py 用 pywinauto 驱动真实桌面，不直接调用生产业务方法。两次辅助脚本控件别名修正已解决，不是应用失败；GUI stderr 均为空。最终应用与 DSH 均已退出，见 final-process-state.json。
