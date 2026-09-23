# Testing — Change → Verification

[返回 Project Map](PROJECT_MAP.md) · 测试是语义保护网，不因 flaky 或新功能而削弱断言。

## 命令与层

在仓库根、安装 `requirements.txt` 和测试所需环境后，PowerShell 全量命令：

```powershell
$env:QT_QPA_PLATFORM = 'offscreen'
python -m unittest discover -s tests -q
```

定向运行真实文件，例如 `python -m unittest discover -s tests -p 'test_chapter_finishing.py' -q`。仓库的 `tests/` 没有 `__init__.py`，不要依赖 `tests.test_chapter_finishing` 模块导入形式。Node/DSH 相关测试按 `tests/test_harness.py` 和 `integrations/` 的条件执行。不要把本地零调用 fixture 结果表述为商业 Provider 在线验证。

| 层 | 真实测试模块（`tests/` 下） | 守护重点 |
| --- | --- | --- |
| Domain / persistence | `test_preparation.py`, `test_core.py`, `test_asset_rework.py`, `test_missing_resolution.py` | parser、project、素材身份、missing/stale |
| Production / runtime / provider | `test_preparation_production.py`, `test_production_runtime.py`, `test_production_runtime_gui.py`, `test_production.py`, `test_fal.py`, `test_harness.py` | Candidate/Review/Current、能力与失败；旧桥接单独看 |
| Creative / prompt | `test_preparation_creative.py`, `test_preparation_creative_gui.py`, `test_preparation_prompt.py` | Proposal/Apply/scope/stale |
| Sound / media / Assembly | `test_preparation_sound.py`, `test_preparation_sound_gui.py`, `test_audio.py`, `test_images.py`, `test_rough_cut.py`, `test_chapter_finishing.py` | 声音 Current、媒体、输出/OTIO |
| Workspace / GUI / integration | `test_preparation_gui.py`, `test_ui.py`, `test_ui_final.py`, `test_integration_shell.py` | D Shell、路由、深链、Return、视图状态 |
| Packaging / frozen / Installer | `test_packaging.py`, `test_installer_release.py` + `tools/clean_env_smoke.py`, `archive_smoke.py`, `installer_smoke.py` | frozen 资源、双产物命名/校验和、隔离、安装/卸载/重装 |

## 最低变更验证矩阵

| 变更边界 | 最低定向测试 | 再加 |
| --- | --- | --- |
| Project schema / 新字段 | `test_preparation`, `test_asset_rework`, `test_integration_shell` | 旧项目兼容样本、全量、packaging/frozen |
| Script parser / Apply | `test_preparation`, `test_preparation_creative`, `test_integration_shell` | 全量；冻结剧本样本 |
| Asset rename / Missing / FREE | `test_asset_rework`, `test_missing_resolution`, `test_preparation` | 全量 |
| Candidate / Review / Current | `test_preparation_production`, `test_production_runtime`, `test_chapter_finishing` | `test_preparation_sound`、全量 |
| Provider / model capability | `test_production_runtime`, `test_preparation_production`, 对应媒体测试 | GUI、失败/取消、全量、frozen 如随包交付 |
| Creative proposal / Apply | `test_preparation_creative`, `test_preparation_creative_gui`, `test_preparation` | integration、全量 |
| Shell / Router / Settings | `test_integration_shell`, `test_ui_final`, `test_preparation_gui` | `test_packaging`、全量/frozen |
| Assembly / Output / OTIO | `test_chapter_finishing`, `test_missing_resolution`, `test_preparation_sound` | 全量、clean/ZIP smoke |
| FFmpeg / PySide6 / packaging | `test_packaging`, `test_installer_release` + 涉及 GUI/媒体模块 | 全量、clean-runtime、ZIP、Installer install/uninstall/reinstall smoke、人工 UI |

完整 22 场景的 Start/Likely Touch/DNT/Truth/Test/Impact 见 [Project Map](PROJECT_MAP.md#change-map先定位再施工)。上表是测试路由，不是目录重构建议。关键语义断言：Green/Selected 不自动 Current、Creative 只显式 Apply、Failed Job 无 Candidate、Assembly Current-only、Asset rename 身份、Missing/FREE、router return、frozen source isolation。新增功能必须加对应正反例，不删除或放宽旧断言来取得绿色。

## Release Gate 与 flaky 纪律

历史 [RC1 final regression](../evidence/V0.1-Windows-Packaging/final-regression.md) 记录 166/166 连续两轮通过、关键集成 46/46。当前 Installer V0.1 须重新跑全量、Packaging/Integration 定向集、portable clean/ZIP 与 install/uninstall/reinstall smoke；人工 GUI 项仍按 [RC manual smoke](RC_MANUAL_SMOKE.md) 独立留证。历史门禁不能替代新发行验证。

若出现 flaky：保存 seed、系统环境、完整失败日志和复现命令，先定位异步/媒体/平台隔离；不得静默跳过、扩大超时或削弱断言后宣称通过。Fixture 生成须保持零调用、临时项目隔离、无凭据外泄。外部真实 Provider 验证独立标注，不混入可离线复现的 RC 数字。

## 10 个反向导航试题

从 [Change Map](PROJECT_MAP.md#change-map先定位再施工) 反向抽取十项，均能给出起点、影响与最低验证；高风险另跑全量/发布烟测。

| 真实任务 | 起点 → 受影响边界 | 最低验证 |
| --- | --- | --- |
| 新增视频 Provider | `app/preparation/runtime.py` → capability/Job、Production ingest、Assembly 消费 | `test_production_runtime`, `test_production_runtime_gui`, `test_chapter_finishing` |
| 改 Current marker UI | `app/preparation/production_gui.py` → Selected/Review/Current 展示，不改绑定语义 | `test_preparation_production`, `test_production_runtime_gui`, `test_integration_shell` |
| 新增 Project 字段 | `app/preparation/workspace.py` → schema/旧项目加载、序列化 | `test_preparation`, `test_integration_shell`, `test_packaging` + 旧项目样本 |
| 升级 FFmpeg | `app/resources.py`、构建脚本 → 探测/渲染/portable 二进制 | `test_chapter_finishing`, `test_audio`, `test_rough_cut`, `test_packaging` + clean/ZIP smoke |
| 改 Creative Apply | `app/preparation/creative.py` → scope/stale/Workspace.apply | `test_preparation_creative`, `test_preparation_creative_gui`, `test_preparation` |
| 改 Asset rename | `app/preparation/workspace.py:scan` → Asset identity、bindings、历史 | `test_asset_rework`, `test_missing_resolution`, `test_preparation` |
| 新增 export | `app/preparation/finishing.py` → Current-only、OTIO/Output | `test_chapter_finishing`, `test_missing_resolution`, `test_packaging` |
| 改 Router | `app/integration.py:WorkspaceRouter` → deep link、return、memory | `test_integration_shell`, `test_ui_final`, `test_packaging` |
| 新增 Settings | `app/integration.py:AppSettingsStore` → SettingsPage/本机配置 | `test_integration_shell`, `test_packaging` |
| 改 Packaging / Installer | `scripts/build_windows_installer.ps1` → portable、Installer、快捷方式、项目数据边界、SHA-256 | `test_packaging`, `test_installer_release` + clean/ZIP/install/uninstall/reinstall smoke |

若任一任务不能说清 Truth Boundary，应先补地图再施工。
