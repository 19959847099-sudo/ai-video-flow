# Final Release Polish & Compliance Gate V0.1 — delta review

Date: 2026-09-24. Baseline: [`PUBLIC_RELEASE_AUDIT_V0.1.md`](PUBLIC_RELEASE_AUDIT_V0.1.md), local `master` at `babde0aea41c2bdef4ada10d0c580541bf620810`. This report covers only changes and rechecks since that audit. It does not authorize a GitHub repository, push, tag, Release or binary upload.

**PUBLIC RELEASE GATE = FAIL · READY TO PUBLISH = NO.** The known GPLv3 static FFmpeg/FFprobe corresponding-source blocker remains. Visual improvements and passing installation smoke cannot waive it.

## FFmpeg and distribution strategy

The exact bundled executables remain Gyan.dev `8.1-essentials_build-www.gyan.dev`, `ffmpeg.exe` SHA-256 `1a65d5b0b10d8d9a81d2824a3538046a40ed3607c906b335a166add87613f705` and `ffprobe.exe` SHA-256 `54b944d6095c4588d7548424d7acd5118390a9d4f01b1c92f841547fc9a7429c`. The installed README identifies FFmpeg commit [`9047fa1b08`](https://github.com/FFmpeg/FFmpeg/commit/9047fa1b08), lists the configure line and many external library versions. `ffmpeg -version` confirms GCC 15.2.0/MSYS2, `--enable-gpl --enable-version3 --enable-static`, and x264/x265. Upstream FFmpeg 8.1 was [announced 2026-03-16](https://ffmpeg.org/); the exact Gyan binary's build/publication date was not independently established. See the bundled [provenance record](../third_party/ffmpeg/PROVENANCE.md) for the complete observed flags, dependency inventory and verification boundary.

The installed package and inspected [vendor build page](https://www.gyan.dev/ffmpeg/builds/) expose the FFmpeg commit and distributor README, **not** a verified complete recipe, patches and accessible corresponding source for every statically linked component of these exact binary hashes. Some dependency versions are listed, but not a uniformly pinned source chain. This is an evidence gap, not an allegation of vendor noncompliance. [FFmpeg's legal guidance](https://ffmpeg.org/legal.html) and the [GNU GPL FAQ](https://www.gnu.org/licenses/gpl-faq.en.html) explain why the source must correspond to redistributed binaries. No complete source artifact or compliant access path has been verified; none is invented in the release notes or checksums.

Strategy: retain the tested Gyan binaries **locally only**, with publication blocked. [BtbN's public build scripts and package recipes](https://github.com/BtbN/FFmpeg-Builds) are a promising replacement route, but an exact binary + recipe revision + corresponding-source package has not been fetched and verified here; swapping on that evidence would merely replace one unresolved chain with another and require new media/Installer QA. A minimal self-build is higher maintenance; unbundling FFmpeg would degrade install-and-run behavior and requires a separate product decision. The smallest next step is to obtain the exact Gyan source/build chain from the distributor, or verify and package a pinned alternative's complete corresponding source, then rerun the affected gate.

The project's Apache-2.0 license still covers only its own code. FFmpeg and FFprobe remain GPLv3. No media dependency or executable changed; the distributed [`THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md) now links the exact-binary provenance record, which is bundled at `_internal/third_party/ffmpeg/PROVENANCE.md` and byte-identical to the repository copy. Previously audited Qt/PySide6, Qt Multimedia FFmpeg DLLs, OpenTimelineIO, PyInstaller, Inno Setup, CPython, Pillow and pydantic notices remain unchanged. Qt Virtual Keyboard remains excluded. Exact Qt module/source attribution should be rechecked before public binary publication, as noted in the baseline audit.

## Presentation assets

The [four screenshots](assets/screenshots/) were recaptured from the same real D-shell build with one disposable synthetic project, “雨夜来信”. The scene reference is the existing bundled rainy-store demo image. A local four-second H.264 clip was encoded from it and imported through the application's actual Candidate path; the other Production Candidate came from the zero-call fixture. The imported, green-reviewed clip was explicitly bound as Current and selected for the hero. Assembly consumes those Current clips. Creative displays a local fixture Proposal/Diff; no paid model was called. No demo project or generated clip is committed.

The [README](../README.md) now identifies the selected media as a local import rather than claiming it is a fixture result. The five-stage [workflow SVG](assets/workflow-overview.svg) is editable and accessible. The standalone 1280×640 [social preview](assets/social-preview.png) uses the actual Production screenshot, not a mock UI. It is prepared for a future GitHub Social Preview setting but has not been uploaded or configured. [Asset regeneration notes](assets/README.md) document the logical viewport, source media and commands. Four physical screenshots are 2400×1500 due to 150% DPI; the social PNG is 1280×640. All were visually inspected after recapture. No screenshot contains a desktop, debug window, personal project or old user-visible product name.

Installer presentation: the compiled Inno script and automated smoke report product/shortcut/PE name **AI Video Flow**, no Publisher fabrication, and successful install/uninstall/reinstall. A bounded attempt to capture the interactive wizard exposed its destination-page text and expected per-user path, but the desktop capture API returned the wrong window. That image was not committed, the test wizard was cancelled, and no setup process or installation was left running. **Welcome, tasks, install, finish and taskbar appearance have not been reliably visually signed off.** This is a remaining manual presentation check, not a claimed pass.

## Rebuilt local artifacts

The notice/provenance payload changed, so both Windows artifacts were rebuilt. Clean portable runtime, ZIP extraction, FFmpeg/FFprobe discovery, Installer install/launch/project-reopen/same-version-reinstall/uninstall-preserves-project/reinstall all passed. The executable identities did not change. Independent `Get-FileHash` recomputation matched `release/v0.1.0-rc.1/SHA256SUMS.txt`:

| Local artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `AI-Video-Flow-0.1.0-rc.1-windows-x64-setup.exe` | 106,133,421 | `a2b173e6dd92a9910b59b6b79d0ad4d5359c42d5fdda1fc8a01404935186e6a4` |
| `AI-Video-Flow-0.1.0-rc.1-windows-x64.zip` | 143,248,001 | `83d09a1d8386c48c44c3c2b6a497119fa1524241ddb1e7a247c288238788d01a` |

No source artifact exists because an adequate corresponding-source set has not been established. Both binaries and the checksum file remain local, Git-ignored and **not for public distribution**. [RC release notes](releases/v0.1.0-rc.1.md) and the Installer evidence index identify these as the latest local hashes, with older hashes retained only as history.

## Delta security and regression

- New/changed public text was scanned for common OpenAI/GitHub/AWS token shapes, private-key delimiters and personal drive paths: no hits. The four screenshots embed only DPI metadata; the social preview has no embedded metadata. The fixture project/clip lived in a temporary directory and was removed.
- Existing historical author-email visibility and older evidence paths are unchanged. Author email public exposure still needs the account owner's decision; no history rewrite was attempted.
- New SVG parsed as XML; README relative links/images, Markdown fences and the bundled provenance link passed the final local validation. No release binary, source archive or temporary wizard capture is staged.
- Focused packaging contract: **7/7 PASS**. Final full suite: **172/172 PASS** in 192.495 seconds. No product runtime, Candidate/Current semantics, workspace layout or actual FFmpeg executable changed.

## Remaining gate items

1. **Release blocker:** establish, inspect and distribute complete corresponding source for the exact shipped static GPLv3 FFmpeg/FFprobe binaries, or adopt a pinned alternative with a verified source package; then rebuild/retest/rehash as required. Recheck the final Qt attribution at the same time.
2. Manual presentation: review Welcome, destination, additional tasks, install and finish pages, then launch the installed app via Start Menu and check title/taskbar/icon/settings for user-visible old branding. The present environment did not provide a reliable visual capture.
3. Account-owner decision: confirm whether the personal-domain Git author email in reachable history may be public. Do not rewrite history implicitly.
4. When a remote is finally created, enable a real private vulnerability-reporting route and update `SECURITY.md` before announcing the project.

Remote creation, push, tag, prerelease, asset upload and Social Preview account configuration remain deliberately unperformed. **BLOCKER = 1 confirmed compliance blocker; REGRESSION = 0 in completed automated gates; PUBLIC RELEASE GATE = FAIL; READY TO PUBLISH = NO.**
