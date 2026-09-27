# Releasing — AI Video Flow Windows RC1

[返回 Project Map](PROJECT_MAP.md) · 正式对外产品名 **AI Video Flow**（旧工程名 AIGCFlow）。版本来源：`app/version.py` 的 `__version__ = 0.1.0-rc.1`。本页记录 Installer + portable 发行链；不授权自动升级、签名或公开上传。

```mermaid
flowchart LR
  Source --> Tests[Full tests / RC gate]
  Tests --> ReleaseBuild[build_windows_installer.ps1]
  ReleaseBuild --> PortableBuild[build_windows.ps1 / PyInstaller]
  PortableBuild --> Portable[dist/AIVideoFlow]
  Portable --> Clean[clean_env_smoke.py]
  Clean --> ZIP[Portable ZIP]
  ZIP --> Archive[archive_smoke.py]
  Archive --> ISCC[Inno Setup ISCC]
  ISCC --> Setup[Per-user Installer]
  Setup --> Hash[SHA256SUMS.txt]
  Hash --> InstallSmoke[Install / Uninstall / Reinstall smoke]
  InstallSmoke --> RC[RC handoff]
```

## 实际入口与构建

源码 Windows 入口 `start.cmd` → `python -m app.preparation_gui`；portable/Installer 的 `AIVideoFlow.exe` 由 `packaging/windows/launcher.py` 进入同一 `main()`。运行依赖在 `requirements.txt`，PyInstaller 在 `requirements-build.txt`；Inno Setup 仅是构建机依赖。`scripts/build_windows.ps1` 生成 `dist/AIVideoFlow` 与同版本 portable ZIP，运行 `package_report.py`、`clean_env_smoke.py`、`archive_smoke.py`、`finalize_release.py`。其清理范围为受管 `build/windows` 和 `dist/AIVideoFlow`，新 ZIP 按精确文件名覆盖；历史 `dist/AIGCFlow` 与 RC1 evidence 保留，旧 ZIP 已归档到 `release/legacy-AIGCFlow-v0.1.0-rc.1/`。`scripts/build_windows_installer.ps1` 再编译 Installer、生成双产物校验和并运行安装烟测。

在仓库根执行 PowerShell：

```powershell
$env:QT_QPA_PLATFORM = 'offscreen'
python -m unittest discover -s tests -q
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build_windows_installer.ps1
```

脚本运行条件以脚本和 `app/resources.py:media_tool` 为准，不要假定任意开发机 PATH 都可复现。**随包 FFmpeg/FFprobe 不再从构建机 PATH 取得**：`scripts/build_windows.ps1` 只接受按 `third_party/ffmpeg/FFMPEG_PIN.json` 预置在 `.tools/ffmpeg/`（或 `-FFmpegDir` 指定目录）的 `bin/ffmpeg.exe`、`bin/ffprobe.exe` 和 `LICENSE.txt`，并在打包前用 `tools/ffmpeg_provenance.py verify` 比对 SHA-256；不匹配即中止构建。对应源码链与升级步骤见 [FFmpeg provenance](../third_party/ffmpeg/PROVENANCE.md)。PyInstaller、PySide6、OpenTimelineIO、Pillow/Pydantic 的版本见 requirements；升级需重跑 GUI/媒体/packaging 及 frozen smoke。Node 是 Harness/DSH 开发集成依赖，不是 portable 应用运行前提。Creative API 为可选外部服务，key 仅来自环境变量；离线 smoke 不测试商业 API。

## 烟测与证据

`app/package_smoke.py` 在 frozen app 内打开/Apply 剧本，遍历 Preparation/Production/Creative/Assembly/Settings，多次路由切换，检查资源和 FFmpeg/FFprobe，重启核对 Production 恢复。`tools/clean_env_smoke.py` 复制 portable 到干净临时位置、收窄 PATH、不依赖开发 Python/Git/源码，还覆盖坏 Settings、DPI、缺媒体、异常退出恢复。`tools/archive_smoke.py` 从 ZIP 解压到临时位置，由无关 cwd 启动 frozen smoke 并校验归档/源码隔离。`tools/finalize_release.py` 记录 ZIP SHA-256；`tools/release_manifest.py` 记录 ZIP 与 Installer 的双产物 SHA-256。当前证据在 `evidence/V0.1-Windows-Installer/`；[旧 RC1 regression](../evidence/V0.1-Windows-Packaging/final-regression.md) 仅作历史基线。

构建目录 `build/`、`dist/`、`release/` 的二进制/临时产物不作为 Git 源码提交；小型 `evidence/` 文本/报告可留作门禁证据。不要把 ZIP、Installer 或用户项目目录放进版本库。历史 RC1 证据的 166/166 两轮与关键集成 46/46 仍保留，但新 Installer 门禁须以本轮实际测试及新 evidence 为准。

## 发版检查

1. 确认 Git HEAD、工作区和版本号；冻结语义没有被无意修改。
2. 定向测试、全量测试、RC 关键集成通过；失败/跳过有独立记录，不能模糊成 PASS。
3. 运行 Windows 双发行构建、clean-runtime/ZIP 与 install/uninstall/reinstall smoke，核对 FFmpeg/FFprobe、源码隔离、坏设置/缺媒体恢复和用户项目保留。
4. 按 [RC manual smoke](RC_MANUAL_SMOKE.md) 做人工 GUI、视觉几何、实际媒体/输出/OTIO 检查；人工结果需单独留证。
5. 核对 ZIP、Installer、`SHA256SUMS.txt` 与证据；发布动作、签名/上传/对外宣布需另获明确授权。

`CURRENT`：per-user Installer + portable RC，均未签名；`DEFERRED`：Updater、CI/CD、自动签名与 Credential Store。脚本自动化不等于人工手验、真实商业 Provider 验证或公开分发已经完成。

## Installer 技术与安装边界

- 采用 [Inno Setup 7.1.0](https://jrsoftware.org/isdl.php)：成熟的单 EXE 安装器、版本控制的 `.iss`、`ISCC.exe` 命令行、快捷方式及卸载支持；比为当前 onedir 应用引入 MSI/WiX 更轻。构建机固定 7.1.0，普通用户运行时不需要 ISCC。[官方许可说明](https://jrsoftware.org/isorder.php)说明非商业使用无需购买，商业使用者被请求购买许可；若用途变化应复核。
- 配置在 `packaging/windows/AI-Video-Flow.iss`：稳定 AppId `42ede151-81cb-5573-8ee0-547ad09a3c83`（后续版本不得随机换）；`PrivilegesRequired=lowest`，默认 `%LOCALAPPDATA%\Programs\AI Video Flow`，安装路径可更改。开始菜单 `AI Video Flow` 必建，桌面同名快捷方式是默认不选的可选任务。
- `AIVideoFlow.exe`、安装器、快捷方式、已安装应用条目共用 `packaging/windows/AI-Video-Flow.ico` 的自有 V0.1 几何图标。Product Name 为 `AI Video Flow`，版本 `0.1.0-rc.1`，描述为 `AI video production workflow for Windows`；没有正式公司主体，因此 Company/Publisher 留空，不伪造版权或签名。
- 卸载只删除安装目录、快捷方式和卸载项；不会删除项目、素材、输出或设置。兼容用户目录仍是 `%LOCALAPPDATA%\AI Video Workflow`，不因品牌更名迁移。安装器不做文件关联、账户、遥测或自动更新。

## 双产物、命令与证据

正式入口：`powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build_windows_installer.ps1`。脚本先完整构建/烟测 portable，再用 Inno 编译安装器，调用 `tools/release_manifest.py` 生成确定性的 `SHA256SUMS.txt`，最后运行 `tools/installer_smoke.py`。仅调试已有同版本 portable 时可用 `-SkipPortableBuild`；`-SkipInstallerSmoke` 的结果不能作为发行门禁 PASS。

```text
release/v0.1.0-rc.1/
├─ AI-Video-Flow-0.1.0-rc.1-windows-x64.zip
├─ AI-Video-Flow-0.1.0-rc.1-windows-x64-setup.exe
└─ SHA256SUMS.txt
```

随包媒体工具的对应源码是第三个发布资产，不进入上表的构建产物链，由清单按需生成：

```powershell
python tools/ffmpeg_provenance.py manifest .tools/ffmpeg/bin/ffmpeg.exe
python tools/ffmpeg_provenance.py fetch   <staging-dir>
```

`fetch` 写出 `FETCH_INDEX.json`（每个组件的 URL、方式、字节数、SHA-256）与
`SHA256SUMS.txt`；打包该目录即得
`AI-Video-Flow-0.1.0-rc.1-ffmpeg-sources.tar`，其 SHA-256 追加进 `SHA256SUMS.txt`
后与双产物一起上传到同一个 GitHub Release，使二进制与对应源码在同一位置提供。

`tools/installer_smoke.py` 先拒绝覆盖已有同名用户安装，在独立临时目录静默安装；验证开始菜单/可选桌面 `.lnk` 目标、Apps & Features、PE metadata、无源码依赖的首次启动与五个 Workspace/Settings、项目关闭重开、同版重装、卸载保留项目、卸载后重装打开旧项目，最后卸载并检查清理。详见 `evidence/V0.1-Windows-Installer/`；该目录是本轮证据，旧 `evidence/V0.1-Windows-Packaging/` 不被覆盖。

当前构建无代码签名证书，Windows SmartScreen 可能提示；不采用自签名或来路不明 packer。重新构建的双产物包含根目录 `LICENSE`、`THIRD_PARTY_NOTICES.md`、`third_party/licenses/`、[FFmpeg provenance](../third_party/ffmpeg/PROVENANCE.md) 以及生成的 `FFMPEG_PIN.json` / `SOURCE_MANIFEST.json`。随包 GPLv3 静态 FFmpeg/FFprobe 的对应源码链已按 [provenance 记录](../third_party/ffmpeg/PROVENANCE.md) 建立并可独立复算；仍须复核 [Public Release Audit](PUBLIC_RELEASE_AUDIT_V0.1.md) 与 [Delta Review](PUBLIC_RELEASE_DELTA_V0.1.md) 中列出的人工签收项。最终下载文件名、SHA-256 与 Release 草稿见 [v0.1.0-rc.1](releases/v0.1.0-rc.1.md)。
