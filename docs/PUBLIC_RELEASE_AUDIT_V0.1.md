# AI Video Flow V0.1 public release audit

> Historical baseline audit. The later provenance-bearing rebuild, current artifact hashes, polished screenshots and final gate are recorded in [Final Release Delta V0.1](PUBLIC_RELEASE_DELTA_V0.1.md).

Audit date: 2026-09-24. Scope: local `master` at baseline `7c0dede641169abaf350fb0df5d68cdd7b0837ec`, the prepared open-source files, current tracked tree and reachable Git history, and the rebuilt Windows v0.1.0-rc.1 artifacts. This is an engineering release gate, not a legal opinion or permission to upload.

**PUBLIC RELEASE GATE = FAIL · READY TO PUBLISH = NO.** The local Installer gate passes, but the exact static GPLv3 FFmpeg/FFprobe build's complete corresponding-source delivery has not been established. Do not publish either Windows binary until that is resolved and checked again.

## Repository inventory

| Class | Content | Decision |
| --- | --- | --- |
| PUBLIC | `app/`, `core/`, `tests/`, `scripts/`, `tools/`, `packaging/`, requirements, product README, Project Map and current architecture/runtime/testing/release docs, license and contribution/security files | Appropriate project source and maintenance material. Legacy `AIGCFlow` identifiers in Python modules/spec/compatibility paths remain implementation details, not current product branding. |
| INTERNAL-BUT-SAFE | Tracked `evidence/` (1,793 paths), historical/frozen docs, small synthetic media and design-validation screenshots already tracked | Useful provenance, but bulky and occasionally contains old local test paths and failed-run logs. Read historical evidence as a record, not a current feature claim. Do not bulk-stage other local design documents. |
| DO-NOT-PUBLISH | Ignored `build/`, `dist/`, `release/` binaries, caches, virtual environments, `.env`/local settings, user projects, temporary screenshot fixture, and pre-existing untracked `design/`, private draft docs and `workspace-1280-reference.png` | Not staged. Installer and ZIP belong only as future GitHub Release attachments, never Git source blobs. |

Current tracked inventory was 2,036 paths before this package; 432 PNG, 119 MP4, 28 WAV, and 8 ZIP paths were historical/synthetic evidence. No `release/`, `dist/`, or `build/` files were tracked. Loose Git objects occupied about 90.28 MiB; largest inspected historical blob was a 6.76 MiB UI-evidence ZIP. This is larger than an ideal source-only repository, but no 100 MB release binary or obvious accidental compiled-app payload was found. History rewrite is not justified by size alone. Eight tracked ZIP archives were inspected for credential-shaped text and sensitive filenames; no hits were found. Inspection of binary image/video pixels cannot prove absence of every private datum.

## Security, privacy and history

- Current tree and reachable history were searched for common OpenAI/GitHub/AWS/Slack-style token signatures and private-key delimiters; no matching secret was found. This is pattern-based detection, not proof that arbitrary secrets cannot exist. There was no reason to rotate a known key or rewrite history.
- Current tracked text contains older `evidence/` tracebacks with a malformed `E:\codex\AIGC…` path and Installer smoke JSON with a local Windows temporary path and account-folder name. They disclose workstation context, not credentials or customer files. The public homepage, screenshots, release notes and new guidance use repository-relative paths and sanitized fixture data. Historical evidence remains classified as safe but noisy; the user may elect to prune it in a separate, carefully scoped cleanup.
- Reachable commit metadata includes a personal-domain author email as well as a `.local` address. GitHub will expose commit authorship if this history is pushed. The account owner should decide whether that address is acceptable publicly; changing it would require a deliberate history rewrite and is not done here.
- No remote or tag existed at audit time. Recent commit subjects describe normal feature, packaging and evidence work; no suspicious secret-bearing subject was identified. We did not squash or rewrite genuine development history.
- `.gitignore` excludes build/release outputs, environments, caches, IDE files, local configuration and logs, while allowing the four public screenshots and docs. The screenshot capture uses a temporary synthetic project and leaves no sample-project compatibility promise.

## Licensing and bundled contents

The project's own code is prepared under Apache-2.0; [`LICENSE`](../LICENSE) is the full text. This provides a permissive source license with an explicit patent grant, while dependencies keep their own terms. Authorship of every historical contribution cannot be legally certified by this engineering audit; the maintainer must be entitled to license the project code.

[`THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md) records exact observed versions, roles, upstream sources and bundled license copies. The Windows build includes project `LICENSE`, notices and ten texts in `_internal/third_party/licenses/`. The exact shipped Qt Virtual Keyboard DLL/plugin was excluded because it is unused and Qt lists the module as GPL-only. Remaining PySide6/Qt 6.10.2 libraries are separate onedir files under LGPL/GPL community terms; Qt Multimedia's dynamically bundled FFmpeg DLLs are distinct from the static command-line executables. OpenTimelineIO's Apache license and NOTICE, Pillow's license/notices, CPython's license, pydantic-core MIT, PyInstaller bootloader exception, and Inno Setup license text were copied or referenced as appropriate. Inno's compiler is a build dependency, while its setup/uninstall runtime is redistributed.

**Publication blocker:** the bundled Gyan FFmpeg/FFprobe 8.1 essentials executables are static GPLv3 builds (`--enable-gpl --enable-version3 --enable-static`, including x264/x265). Their distributor README points to an FFmpeg commit and build configuration, but that alone does not demonstrate accessible, complete corresponding source for the exact binaries and statically linked components, including build scripts and patches as applicable. Before distributing the binaries, obtain and document an adequate corresponding-source package or compliant source-access arrangement for these exact checksums; independently inspect it against the build configuration. Rebuild or change the bundled binaries if necessary, then rerun binary, notice and hash gates. Qt's exact binary/source provenance and remaining module notices should be checked at the same time. Do not interpret this report as a claim of full legal compliance.

## Product presentation and documentation

The root English [`README`](../README.md) is a concise product homepage and distinguishes the RC's fixture-oriented image/audio/video generation from the optional OpenAI-compatible Creative text API. The first screenshot and three additional images were captured from the actual PySide6 D shell at a 1600×1000 logical viewport using synthetic data; high-DPI capture produced 2400×1500 PNGs. All four were visually inspected for legibility, old branding, debug windows and private paths. The PNGs are 74–229 KB each. No fake UI or private demo project was staged. An additional Chinese README is deferred to avoid two drifting homepages; current Chinese engineering navigation remains in the Project Map.

`CONTRIBUTING.md`, `SECURITY.md`, minimal issue/PR templates, [`docs/README.md`](README.md), and user-facing [RC release notes](releases/v0.1.0-rc.1.md) are present. The Security page deliberately does not claim a private GitHub reporting channel already exists. Enable that channel when creating the repository and update its actual route before announcing the public project. Existing frozen docs may use old internal naming; the homepage and release identity use **AI Video Flow**. Automated installation smoke verified PE metadata, shortcut targets and five Workspace routes, but the interactive Welcome/path/tasks/finish wizard and taskbar icon still need a human visual pass. Do not mark that manual review complete by inference.

README relative links/images and new Markdown structure must be validated after staging; no local drive path is intentionally part of public-facing new docs. The Project Map remains the architecture/truth/test/release navigation entry, not a duplicated marketing page.

## Release artifacts and regression

The 2026-09-24 notice-bearing rebuild completed portable clean-environment smoke, ZIP extraction smoke, Installer installation, same-version reinstall, uninstall-preserves-project, and reinstall-open-old-project smoke. [`evidence/V0.1-Windows-Installer/README.md`](../evidence/V0.1-Windows-Installer/README.md) labels its older 2026-09-23 hashes as historical. Final files remain local and Git-ignored:

| Asset | Bytes | Independently recalculated SHA-256 |
| --- | ---: | --- |
| `AI-Video-Flow-0.1.0-rc.1-windows-x64-setup.exe` | 106,135,544 | `4bdacf98c78bd4989e4863835088c1b48330619b8d099acce8e61a221c1280c9` |
| `AI-Video-Flow-0.1.0-rc.1-windows-x64.zip` | 143,243,375 | `09aa812ec5f449d6e810d30f7e045542d35fe3656b9ec8edcfe8a4b6ab0c60b9` |

Both hashes match local `release/v0.1.0-rc.1/SHA256SUMS.txt`. The full regression suite passed **172/172** in 223.280 seconds after the packaging-license change. No GitHub release, upload, tag or remote change was made.

## Gate checklist

- [x] Product README, four real screenshots, Project Map link, contribution/security guidance and GitHub templates prepared.
- [x] License and third-party notice material included in rebuilt Windows packages.
- [x] Installer/portable smoke and artifact checksums verified.
- [x] Current/history credential-pattern and large-object checks completed; no known secret or release binary in Git source history.
- [ ] Complete corresponding-source delivery for the exact static GPLv3 FFmpeg/FFprobe build; recheck Qt provenance/notices.
- [ ] Human review of the interactive Installer wizard and installed-app presentation.
- [ ] Decide whether the historical author email is acceptable for a public Git history.
- [ ] Enable a real private vulnerability-reporting route and update `SECURITY.md` when the GitHub repository is created.
- [ ] Create GitHub repository, add remote, push source, create/push `v0.1.0-rc.1` tag, create pre-release, upload Installer, portable ZIP and `SHA256SUMS.txt`. These are explicitly out of scope for this local preparation turn.

Until the licensing blocker is resolved, **BLOCKER ≥ 1; PUBLIC RELEASE GATE = FAIL; READY TO PUBLISH = NO**.
