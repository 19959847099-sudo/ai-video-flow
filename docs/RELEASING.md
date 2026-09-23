# Releasing — Windows RC1 portable

[返回 Project Map](PROJECT_MAP.md) · 版本来源：`app/version.py` 的 `__version__ = 0.1.0-rc.1`。本页记录当前发布链，不授权自动升级或商业发布。

```mermaid
flowchart LR
  Source --> Tests[Full tests / RC gate]
  Tests --> Build[build_windows.ps1]
  Build --> PyInstaller
  PyInstaller --> Portable[dist/AIGCFlow]
  Portable --> Clean[clean_env_smoke.py]
  Clean --> ZIP[RC ZIP]
  ZIP --> Archive[archive_smoke.py]
  Archive --> Hash[SHA-256 / report]
  Hash --> RC[RC handoff]
```

## 实际入口与构建

源码 Windows 入口 `start.cmd` → `python -m app.preparation_gui`；portable 入口 `packaging/windows/launcher.py` → 同一 `main()`。运行依赖在 `requirements.txt`，打包依赖在 `requirements-build.txt`。正式脚本 `scripts/build_windows.ps1` 调 PyInstaller onedir，打包 app/resources 与 FFmpeg/FFprobe，生成 `dist/AIGCFlow`、`release/v0.1.0-rc.1` ZIP/报告，并运行 `tools/package_report.py`、`tools/clean_env_smoke.py`、`tools/archive_smoke.py`、`tools/finalize_release.py`。脚本会清理其**受管** build/dist/release 路径；执行前先读脚本、核对目标且保护用户文件。此文档任务没有重建包。

在仓库根执行 PowerShell：

```powershell
$env:QT_QPA_PLATFORM = 'offscreen'
python -m unittest discover -s tests -q
powershell -ExecutionPolicy Bypass -File scripts/build_windows.ps1
```

脚本运行条件及 FFmpeg 发现方式以脚本和 `app/resources.py:media_tool` 为准，不要假定任意开发机 PATH 都可复现。PyInstaller、PySide6、OpenTimelineIO、Pillow/Pydantic 的版本见 requirements；升级需重跑 GUI/媒体/packaging 及 frozen smoke。Node 是 Harness/DSH 开发集成依赖，不是 portable 应用运行前提。Creative API 为可选外部服务，key 仅来自环境变量；离线 smoke 不测试商业 API。

## 烟测与证据

`app/package_smoke.py` 在 frozen app 内打开/Apply 剧本，遍历 Preparation/Production/Creative/Assembly/Settings，多次路由切换，检查资源和 FFmpeg/FFprobe，重启核对 Production 恢复。`tools/clean_env_smoke.py` 复制 portable 到干净临时位置、收窄 PATH、不依赖开发 Python/Git/源码，还覆盖坏 Settings、DPI、缺媒体、异常退出恢复。`tools/archive_smoke.py` 从 ZIP 解压到临时位置，由无关 cwd 启动 frozen smoke 并校验归档/源码隔离。`tools/finalize_release.py`/报告生成 SHA-256 与最终证据；结果以产出的报告和 [RC1 final regression](../evidence/V0.1-Windows-Packaging/final-regression.md) 为准。

构建目录 `build/`、`dist/`、`release/` 的二进制/临时产物不作为 Git 源码提交；小型 `evidence/` 文本/报告可留作门禁证据。不要把 ZIP 或用户项目目录放进版本库。RC1 上轮证据：全量 166/166 连续两次、关键集成 46/46、portable/clean/ZIP smoke 通过；此页不是新一次门禁记录。

## 发版检查

1. 确认 Git HEAD、工作区和版本号；冻结语义没有被无意修改。
2. 定向测试、全量测试、RC 关键集成通过；失败/跳过有独立记录，不能模糊成 PASS。
3. 运行 Windows 构建及 clean-runtime/ZIP smoke，核对 FFmpeg/FFprobe、源码隔离、坏设置/缺媒体恢复。
4. 按 [RC manual smoke](RC_MANUAL_SMOKE.md) 做人工 GUI、视觉几何、实际媒体/输出/OTIO 检查；人工结果需单独留证。
5. 核对报告、ZIP、SHA-256 与最终交付目录；发布动作、签名/上传/对外宣布需另获明确授权。

`CURRENT` 是 portable RC；`PLANNED/DEFERRED`：Installer、Updater、CI/CD、自动签名与 Credential Store 均未建立。脚本自动化不等于人工手验、真实商业 Provider 验证或公开分发已经完成。
