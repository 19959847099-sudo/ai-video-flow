# Final RC regression

Date: 2026-09-21
Candidate: 0.1.0-rc.1

## Source regression

Commands:

    python -m py_compile app/resources.py app/version.py app/package_smoke.py app/preparation_gui.py app/integrated_gui.py app/production.py tools/clean_env_smoke.py tools/archive_smoke.py tools/package_report.py tools/finalize_release.py tools/write_windows_version.py tests/test_packaging.py tests/test_integration_shell.py
    python -m unittest tests.test_packaging tests.test_integration_shell tests.test_preparation_creative tests.test_preparation_creative_gui tests.test_production_runtime tests.test_production_runtime_gui tests.test_chapter_finishing -v

Result: PASS. The main focused suite passed 44 tests. A final 17-test integration and Assembly run also passed after adding two release-boundary cases.

Release boundaries confirmed:

- A running in-session worker blocks application close with a clear message.
- A missing bound media file blocks Assembly locally without crashing or invalidating the remaining clips.
- Simulated OpenTimelineIO unavailability blocks handoff only; the rendered preview remains usable.
- Portable OTIO export and round-trip remain passing when OpenTimelineIO is present.
- Commercial provider calls: 0.

## Frozen release

- Clean runtime simulation: PASS.
- ZIP extraction and frozen smoke: PASS.
- Source-tree isolation: PASS.
- Microsoft Defender local scan: PASS; no threats reported.
- BLOCKER: 0.
- Packaging regression: 0.
## 2026-09-23 full-suite RC1 gate

Baseline HEAD: `f182164169580d1ea43d6f2a04aa7e140dadd914`; tracked worktree clean before repair. The initial full run was 166 tests in 203.150 s: 2 FAIL, 4 ERROR, 0 SKIP.

| Original exception | Classification | Root cause |
|---|---|---|
| `test_fal.FalTests.test_zero_network_full_chain_restart_retry_and_relocation` | REAL REGRESSION | `app.production.ingest()` referenced `shutil` after the packaging commit removed its import; job failed instead of completing. |
| `test_harness.HarnessToolsTests.test_context_snapshot_result_media_and_human_gate` | REAL REGRESSION | The bridge surfaced the same failed ingestion as `ValueError: name 'shutil' is not defined`. |
| `test_harness.HarnessToolsTests.test_official_dsh_cli_tool_events_network_lock_and_independence` | REAL REGRESSION | The isolated DSH subprocess exited 1 when its video bridge reached the same failed ingestion. |
| `test_production.ProductionTests.test_invalid_select_retry_and_duplicate_submit` | REAL REGRESSION (downstream) | Failed ingestion left `job.result_id = None`; the next select produced `TypeError` instead of exercising the intended invalid cross-shot selection. This case passed after the import fix, without changing ID validation. |
| `test_production.ProductionTests.test_media_retry_selection_trace_and_relocation` | REAL REGRESSION | Mock video ingestion failed at `shutil.copyfile`. |
| `test_ui.PresentationTests.test_invalid_data_keeps_error_state_and_ffmpeg_failure_is_actionable` | TEST REGRESSION | The test asserted the pre-packaging FFmpeg message and mocked the old lookup location; the current resource resolver reports `ffmpeg` and `AIVIDEO_MEDIA_BIN`. |

All six original cases failed on three isolated repeats before the fixes. The Fal/Harness cases were run with the test directory on `PYTHONPATH`, matching unittest discovery; no order dependence was observed. Production tests used temporary media projects and FFmpeg; the DSH case also ran Node/Python subprocesses. The UI case used Tk, not Qt, and did not launch FFmpeg. The complete baseline ran Qt tests with `QT_QPA_PLATFORM=offscreen`.

Minimal changes: restore `import shutil` in `app/production.py`; update the UI test to set `AIVIDEO_MEDIA_BIN` to a missing directory with `AIVIDEO_MEDIA_STRICT=1`, and assert the current actionable error. No Truth or business-state semantics changed.

Verification:

- Affected Production/Fal/Harness/UI/Packaging modules: 30/30 PASS.
- Complete suite, first pass: 166/166 PASS in 208.038 s; FAIL 0, ERROR 0, SKIP 0.
- Complete suite, second consecutive pass: 166/166 PASS in 217.309 s; FAIL 0, ERROR 0, SKIP 0.
- Formal RC integration subset: 46/46 PASS in 47.473 s.
- No AIGCFlow, unittest Python, FFmpeg or FFprobe subprocess remained after tests or package smoke.

Fresh official build: `powershell -ExecutionPolicy Bypass -File scripts/build_windows.ps1` PASS. Portable `dist/AIGCFlow`: 364,829,863 bytes and 236 files (7 bytes above the previous candidate, matching the added import). ZIP `release/v0.1.0-rc.1/AIGCFlow-0.1.0-rc.1-windows-x64.zip`: 143,330,460 bytes (136.7 MiB), SHA-256 `11e398425fcbf063e765b1766e1297a7ec5a9c0901329388f3de4d906e1887a4`.

Clean runtime and extracted ZIP smokes: PASS. The copied portable ran with minimal PATH, no source/Python/Git dependency, navigated Preparation/Production/Creative/Assembly/Settings, created and reopened a project, recovered corrupt settings, located bundled FFmpeg/FFprobe, and exited cleanly. The archive passed integrity and source-isolation checks. The earlier 2026-09-21 Defender scan was not repeated for this rebuild.

BLOCKER = 0; REGRESSION = 0; RC RELEASE GATE = PASS. This is a source/build gate only; no tag, push or GitHub Release was created.
