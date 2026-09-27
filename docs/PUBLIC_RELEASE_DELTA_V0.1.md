# Final Release Polish & Compliance Gate V0.1 — delta review

Date: 2026-09-24. Baseline: [`PUBLIC_RELEASE_AUDIT_V0.1.md`](PUBLIC_RELEASE_AUDIT_V0.1.md), local `master` at `babde0aea41c2bdef4ada10d0c580541bf620810`. This report covers only changes and rechecks since that audit. It does not authorize a GitHub repository, push, tag, Release or binary upload.

**PUBLIC RELEASE GATE = FAIL · READY TO PUBLISH = NO.** The known GPLv3 static FFmpeg/FFprobe corresponding-source blocker remains. Visual improvements and passing installation smoke cannot waive it.

> **Superseded on 2026-09-27 for the FFmpeg blocker only.** See
> [FFmpeg corresponding-source round (2026-09-27)](#ffmpeg-corresponding-source-round-2026-09-27)
> at the end of this file. The Gyan binaries described throughout this 2026-09-24
> review are no longer shipped and the artifact hashes below are historical. The
> two manual sign-off items reported here are still open.

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

---

# FFmpeg corresponding-source round (2026-09-27)

Scope: the single confirmed release blocker from this review — complete
corresponding source for the bundled GPLv3 static FFmpeg/FFprobe. No product,
UI, screenshot or demo work. Baseline `master` at `c32438b`.

## Why the previous binaries could not be kept

The Gyan.dev chain was re-tested against primary sources rather than assumed
stale. [gyan.dev/ffmpeg/builds](https://www.gyan.dev/ffmpeg/builds/) publishes
download links, per-package `.sha256` files and a link to the upstream FFmpeg
commit; it publishes **no** build script, recipe, patch set or source bundle, and
[issues @ github](https://github.com/GyanD/codexffmpeg/issues) is a discussion
tracker, not a recipe archive. The bundled `README.txt` lists external library
versions at mixed precision and includes entries with no revision at all
(`openal-soft latest`). A binary whose build inputs are partly unpinned by
construction cannot be given a verifiable corresponding-source record, so
**CURRENT GYAN SOURCE CHAIN = INSUFFICIENT**. That is an evidence finding about
what is published, not an allegation of vendor noncompliance.

## Options compared

| Option | Provenance quality | Long-term maintenance | UX / product impact | Verdict |
| --- | --- | --- | --- | --- |
| Keep Gyan, complete the chain | No recipe, patches or source published; some components unpinned | Would require the vendor to start publishing | None | Cannot close |
| **BtbN/FFmpeg-Builds pinned release** | Every package pinned to an exact commit in a public version-controlled recipe; immutable per-build tags; vendor `checksums.sha256` | Fetch/manifest script only; no toolchain owned | Binary swap, same static self-contained behaviour | **Adopted** |
| Self-build a minimal FFmpeg | Best possible: we would own recipe and inputs | Own a Windows cross-compile toolchain and rebuild for every security fix | Estimated, not measured: roughly 15–30 MB binaries and a roughly 15–25 MB source set | Rejected: highest maintenance; CI is `DEFERRED` |
| Unbundle FFmpeg | No GPL object code conveyed | Low | Breaks install/unzip-and-run; needs a product decision | Rejected: product degradation |

The product needs exactly one non-native encoder, `libx264` (its four call sites:
`app/production.py:165`, `app/rough_cut.py:157`, `app/preparation/runtime.py:357`,
`app/preparation/finishing.py:336`), and H.264 output has no LGPL-only path in
FFmpeg. GPL therefore stays; the answer had to be a conveyable source chain, not
license avoidance.

## What changed

The package now ships BtbN `ffmpeg-n8.1.3-win64-gpl-8.1.zip` from immutable
release `autobuild-2026-09-26-13-03`, produced by recipe commit
`58cc05f33c20e3ead0ce876b72531ab482d0f981` (CI run 36241274776), built from
FFmpeg tag `n8.1.3` / commit `1041abdc96…`. The vendor package hash
`d20ef03f…` was recomputed locally and matches the vendor's own published
`checksums.sha256`.

`third_party/ffmpeg/SOURCE_MANIFEST.json` is generated, not authored: it reads the
vendor recipe at the pinned commit, resolves the 81 stages that the shipped
binary's own reported configure line enables, walks their transitive dependency
graph, and records 117 upstream repositories at exact revisions plus the recipe
and patch directories. It reports `unclaimed_enable_lib_flags`, which is **empty**
— every `--enable-lib*` in the binary is attributable to exactly one pinned
stage — and `conservatively_included_stages` (`pulseaudio`, `x11`), which are
included although this build disables them, so the manifest over-covers rather
than under-covers.

`scripts/build_windows.ps1` no longer discovers FFmpeg from `PATH`. It packages
the staged copy under `.tools/ffmpeg/` and aborts unless
`tools/ffmpeg_provenance.py verify` reproduces the pinned SHA-256, so a silent
substitution cannot reach a release. The negative path was exercised: the old
Gyan executables fail the gate.

## Corresponding source delivery

`python tools/ffmpeg_provenance.py fetch <dir>` downloads each pinned archive
(HTTP snapshot, or `git archive` at the pinned commit for the four hosts that
publish none), hash-verifies every file, and writes `FETCH_INDEX.json` and
`SHA256SUMS.txt`; it is resumable and was run to completion here: **117 of 119
records fetched, 0 failures**, ~1.00 GB of archives, every one re-verified with
`sha256sum -c`. The bundle ships those archives plus the manifest, pin, this
provenance record and `RETRIEVAL.md`, and is archived as
`AI-Video-Flow-0.1.0-rc.1-ffmpeg-sources.tar` (1,003,499,520 bytes, SHA-256
`9ab196f73dd610cb7d2ba07f0db41f26579425397873f742c7db85bf692e912e`) and uploaded
to the same GitHub Release as the two binaries, so object code and source are
offered from the same place. Nothing is committed to Git history.

The bundle is large relative to the app because a static GPL build links a lot:
the manifest covers 81 vendor stages / 117 source repositories, and AMD's AMF SDK
alone contributes ~381 MB of that total. This is the real cost of the chosen
option; the alternative that would shrink it (owning a minimal self-build) is the
higher-maintenance path rejected above.

**Residual, not hidden:** `libmp3lame` (SourceForge SVN r6835) and `xvid`
(svn.xvid.org r2204) are pinned to Subversion revisions for which no HTTP
revision snapshot was found, and whose official release tarballs are *not*
equivalent to those revisions. Of the 119 source records this binary resolves to,
117 are mirrored and hash-verified; these two are delivered with their exact
repository, revision and `svn export` command recorded in the manifest, in
`FETCH_INDEX.json` and in a `RETRIEVAL.md` shipped inside the bundle. Both are
separately licensed (LGPL-2.1-or-later, GPL-2.0-or-later) rather than GPL-3.0.
Closing this last pair needs a Subversion client at bundle-build time, or a build
without those two codecs.

## Rebuild, regression and artifacts

Runtime changed, so the full chain was re-run rather than sampled: focused media
tests with the new executables (`test_rough_cut` 12, `test_chapter_finishing` 10,
`test_audio` 10, `test_preparation_sound` 9) all pass; **full suite 172/172 OK in
130.10 s against the packaged binaries**, 0 failures / 0 errors; clean portable
runtime, ZIP extraction, FFmpeg/FFprobe discovery and source-tree isolation pass;
Installer install → launch → project reopen → same-version reinstall → uninstall
preserves project → reinstall reopens project → clean uninstall passes.

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `…-windows-x64-setup.exe` | 145,188,342 | `85aac4dfd425c1ff711b1599487dae150c3a0be68d99d3787b12035a3048ac36` |
| `…-windows-x64.zip` | 196,880,641 | `1dd25ec9f0de7523c6114873dd58b707c37491fe32700a6ee02b9ea252faaaf2` |
| `…-ffmpeg-sources.tar` | 1,003,499,520 | `9ab196f73dd610cb7d2ba07f0db41f26579425397873f742c7db85bf692e912e` |

All three recomputed independently with `sha256sum -c` and matched
`SHA256SUMS.txt`. Two interim rebuilds during this round packaged provenance files
that were still being edited and are superseded; the final package was byte-compared
against the repository copies of `THIRD_PARTY_NOTICES.md`, the runtime notice,
`PROVENANCE.md`, `FFMPEG_PIN.json` and `SOURCE_MANIFEST.json`, and all five matched.
The ~39 MB installer growth is the price of this option: the BtbN GPL build enables
far more components than Essentials. No product behaviour changed — the application
still invokes the same command lines against the same H.264/AAC/MP4 capability set.

`THIRD_PARTY_NOTICES.md`, the packaged runtime notice, `PROVENANCE.md`,
`RELEASING.md`, `TESTING.md`, `PROJECT_MAP.md` and the RC release notes now match
the shipped binaries. The previous Gyan hashes survive only as history in the
evidence index. Project license is unchanged: AI Video Flow code stays Apache-2.0,
FFmpeg stays GPL-3.0; nothing here required touching the top-level license.

## Gate

- **FFMPEG SOURCE GATE = PASS.** Binary identified and hash-verified against the
  vendor's own checksums; license state known; build provenance sufficient;
  external static components enumerated at exact revisions; corresponding source
  delivery reproducible from a committed generated manifest; documentation
  updated; runtime and packaging regression green; no known blocker to
  distribution. The two Subversion components above are the one disclosed
  limitation of the mirror, not an unknown.
- **PUBLIC RELEASE TECHNICAL GATE = PASS.** BLOCKER = 0, REGRESSION = 0.

Still outside the technical gate and deliberately not decided here: manual
Installer/installed-app visual sign-off, the Git author-email publication
decision, and a real private vulnerability-reporting route once a remote exists.
