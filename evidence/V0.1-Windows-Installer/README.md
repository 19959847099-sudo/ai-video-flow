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

## 2026-09-24 provenance-bearing rebuild (latest local candidate)

The formal `third_party/ffmpeg/PROVENANCE.md` was added to the onedir bundle and linked from the distributed notice. The exact same Gyan FFmpeg/FFprobe executables remain; no media/runtime code changed. The portable clean-runtime/ZIP extraction and Installer install/reinstall/uninstall smoke all passed again. These local artifacts supersede both earlier hash pairs:

- Installer: 106,133,421 bytes; SHA-256 `a2b173e6dd92a9910b59b6b79d0ad4d5359c42d5fdda1fc8a01404935186e6a4`.
- Portable ZIP: 143,248,001 bytes; SHA-256 `83d09a1d8386c48c44c3c2b6a497119fa1524241ddb1e7a247c288238788d01a`.

`release/v0.1.0-rc.1/SHA256SUMS.txt` lists this pair. Corresponding-source delivery is still unresolved, so **do not publish the binaries**. The Installer wizard's controls were inspected as far as automation allowed, but reliable visual captures of every page were not obtained; interactive presentation review remains open.

## 2026-09-27 FFmpeg replacement rebuild (latest local candidate)

The bundled media tools were replaced: Gyan.dev `8.1-essentials_build` is no longer
shipped. The package now carries BtbN/FFmpeg-Builds `n8.1.3` `win64-gpl` static
executables from immutable release `autobuild-2026-09-26-13-03`, verified against
`third_party/ffmpeg/FFMPEG_PIN.json` before packaging
(`ffmpeg.exe` `a35880a7…`, `ffprobe.exe` `493c63c3…`). See
[`third_party/ffmpeg/FFMPEG_PIN.json`](../../third_party/ffmpeg/FFMPEG_PIN.json)
and the rewritten
[`third_party/ffmpeg/PROVENANCE.md`](../../third_party/ffmpeg/PROVENANCE.md).

`scripts/build_windows.ps1` no longer discovers FFmpeg from `PATH`; it reads the
staged pinned copy and aborts on any hash mismatch. The vendor `README.txt` is gone
because that vendor publishes none — the generated
`SOURCE_MANIFEST.json` now travels instead.

Gates re-run on this rebuild, all green:

- Focused media with the new executables: `test_rough_cut` 12/12,
  `test_chapter_finishing` 10/10, `test_audio` 10/10, `test_preparation_sound` 9/9.
- Full suite against the **packaged** binaries (`AIVIDEO_MEDIA_BIN` pointed at
  `dist/AIVideoFlow/_internal/runtime/ffmpeg/bin`): **172/172 OK** in 130.10s,
  0 failures / 0 errors.
- Clean-environment portable runtime, ZIP extraction, FFmpeg/FFprobe discovery and
  source-tree isolation: see `portable/clean-environment.json`,
  `portable/archive-smoke.json`.
- Installer install → first launch → project reopen → same-version reinstall →
  uninstall preserves project → reinstall reopens project → clean uninstall:
  `installer-smoke.json`.

New local artifacts, superseding the 2026-09-24 pair above and two interim rebuilds
from earlier on 2026-09-27 (installers `4db1d68b…` and `f3bcccb2…`, which packaged
provenance documents still under edit):

- Installer: 145,188,342 bytes; SHA-256 `85aac4dfd425c1ff711b1599487dae150c3a0be68d99d3787b12035a3048ac36`.
- Portable ZIP: 196,880,641 bytes; SHA-256 `1dd25ec9f0de7523c6114873dd58b707c37491fe32700a6ee02b9ea252faaaf2`.
- Corresponding-source asset: 1,003,499,520 bytes; SHA-256 `9ab196f73dd610cb7d2ba07f0db41f26579425397873f742c7db85bf692e912e`.

All three were recomputed independently with `sha256sum -c` against
`release/v0.1.0-rc.1/SHA256SUMS.txt` and matched. The packaged copies of
`THIRD_PARTY_NOTICES.md`, `runtime/ffmpeg/THIRD_PARTY_NOTICES.md`,
`third_party/ffmpeg/PROVENANCE.md`, `FFMPEG_PIN.json` and `SOURCE_MANIFEST.json`
were byte-compared with the repository copies after this final build and all five
matched. The vendor `LICENSE.txt` ships under `runtime/ffmpeg/`; the former
`runtime/ffmpeg/README.txt` is gone because this vendor publishes none. Size grew
because this build reports a much larger enabled-component set than Essentials.

The FFmpeg corresponding-source gate is now closed: the mirror resolves this
binary to 119 source records and 117 of them are downloaded and hash-verified
(`sha256sum -c` clean); `libmp3lame` and `xvid` remain pinned-revision retrieval
instructions, documented as a residual in
`third_party/ffmpeg/PROVENANCE.md`. The Git author-email question is now **closed
as accepted** by the account owner: the existing history publishes with
`19959847099@163.com` intact and no rewrite, author amendment or object cleanup
was performed. One manual item remains open and is not a technical gate: the
Installer wizard and installed-app visual sign-off.
