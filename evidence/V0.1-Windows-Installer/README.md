# AI Video Flow Windows Installer V0.1 — validation record

Baseline HEAD before this work: `2e3aad6a063d4167fd1c265885aad1f61e86c7ce`. Version: `0.1.0-rc.1`. This record describes local validation, not a public release, code signature, or third-party legal approval.

## Artifacts and build

- PyInstaller `6.22.3` on Windows 11 / Python `3.13.3`; Inno Setup `7.1.0` command-line compiler.
- Portable: `AI-Video-Flow-0.1.0-rc.1-windows-x64.zip`, `143341044` bytes, SHA-256 `9eac59e26416166d81539c95b3775987977f6612221ca7c409b6411f3c29f6ab`.
- Installer: `AI-Video-Flow-0.1.0-rc.1-windows-x64-setup.exe`, `106192641` bytes, SHA-256 `3240b31796248d458e22e018b51d37619bbb789589265478b8828153323d1907`.
- `release/v0.1.0-rc.1/SHA256SUMS.txt` independently matches both artifact hashes. Built binaries remain Git-ignored.
- Prior AIGCFlow ZIP hash matched historical `evidence/V0.1-Windows-Packaging/release-summary.json` and was moved without deletion to `release/legacy-AIGCFlow-v0.1.0-rc.1/`; old evidence and old `dist/AIGCFlow` remain unchanged.

## Automated smoke

- [Portable clean runtime](portable/clean-environment.json): PASS; no developer Python/Git/source paths, five Workspace routes, Settings, FFmpeg/FFprobe, restart, DPI, missing media, abnormal-exit recovery.
- [Portable ZIP archive](portable/archive-smoke.json): PASS; integrity and source-tree isolation.
- [Installer](installer-smoke.json): PASS; per-user install into a path with spaces, Start Menu/Desktop shortcut targets, Apps & Features version, EXE/Setup metadata, first launch, new project/reopen, same-version reinstall, uninstall with project retained, reinstall/open old project, final uninstall cleanup. The shortcut targets were resolved and the installed target executable was launched in frozen smoke mode; this is not a manual click-through of the wizard.
- Post-smoke: no `AIVideoFlow.exe` process, AI Video Flow uninstall record, Start Menu/Desktop shortcut, or temporary install directory remained.
- Product/Setup PE metadata: Product `AI Video Flow`; app executable `AIVideoFlow.exe`; version `0.1.0-rc.1`; Company/Publisher empty; Authenticode status `NotSigned`.

## Tests

- Packaging contract: 6/6 PASS; D Shell integration: 7/7 PASS; new Installer/release contract: 5/5 PASS; Production Runtime isolated after anomaly: 7/7 PASS.
- First full-suite attempt: 170/171 PASS; `test_production_runtime.RuntimeTests.test_audio_video_and_shot_all_use_runtime_then_explicit_current` observed a failed third local video fixture Job. The failure reason was not captured in that run. No Production Runtime code or assertion was changed.
- Subsequent full-suite attempts: **171/171 PASS, then 171/171 PASS, then 171/171 PASS** (229.177 s, 223.010 s, and 237.923 s). The isolated failure did not reproduce; its root cause is unconfirmed and should be watched in future FFmpeg/runtime changes.
- A post-build combined 18-test spot check once hit a Windows `PermissionError` replacing a temporary integration-test project JSON during GUI teardown; the temporary workspace lock was still held. The integration module then passed 7/7 in isolation, the identical combined set passed 18/18 on rerun, and the subsequent full suite passed 171/171. No application code or assertion was changed for this unconfirmed intermittent failure.

## Boundaries

User projects/settings remain in the legacy `%LOCALAPPDATA%/AI Video Workflow` compatibility path unless explicitly overridden. Installer uninstall never targets it. No updater, file association, account, telemetry, code signature, or public release was created. Interactive visual wizard review and broader third-party notice/license audit are separate follow-up checks; the self-authored icon was inspected at 256 px.

## 2026-09-24 open-source notice rebuild

The release build was rerun after adding project and third-party license material, and after excluding unused GPL-only Qt Virtual Keyboard components. Portable and Installer smoke tests passed, including install/uninstall/reinstall. The local release assets now have these hashes:

- Installer: 106,135,544 bytes; SHA-256 `4bdacf98c78bd4989e4863835088c1b48330619b8d099acce8e61a221c1280c9`.
- Portable ZIP: 143,243,375 bytes; SHA-256 `09aa812ec5f449d6e810d30f7e045542d35fe3656b9ec8edcfe8a4b6ab0c60b9`.

These replace the historical hashes above. The static GPLv3 FFmpeg/FFprobe corresponding-source delivery path still requires confirmation before any binary publication. See `docs/PUBLIC_RELEASE_AUDIT_V0.1.md`; a passed installer smoke is not a passed public-release licensing gate.
