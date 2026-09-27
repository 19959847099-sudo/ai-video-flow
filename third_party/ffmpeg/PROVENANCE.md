# FFmpeg / FFprobe binary provenance and corresponding source — v0.1.0-rc.1

Status: **corresponding-source chain closed for the exact bundled executables.**
This record describes the binaries AI Video Flow redistributes, the build inputs
that produced them, and how a user obtains and verifies the corresponding source.
It is an engineering provenance record, not a legal opinion.

## Binary identity

| Field | Value |
| --- | --- |
| AI Video Flow release | `0.1.0-rc.1` (`app/version.py`) |
| Distributor | [BtbN/FFmpeg-Builds](https://github.com/BtbN/FFmpeg-Builds) |
| Vendor release (build ID) | [`autobuild-2026-09-26-13-03`](https://github.com/BtbN/FFmpeg-Builds/releases/tag/autobuild-2026-09-26-13-03) |
| Vendor build recipe | `BtbN/FFmpeg-Builds@58cc05f33c20e3ead0ce876b72531ab482d0f981` |
| Vendor CI run that published it | [actions/runs/36241274776](https://github.com/BtbN/FFmpeg-Builds/actions/runs/36241274776) |
| Vendor package | `ffmpeg-n8.1.3-win64-gpl-8.1.zip`, 193,111,781 bytes, SHA-256 `d20ef03f0f4161453b9f46a72471eb5370f56b6410fe8bca14a4b0220c6c924a` |
| Target / variant / addin | `win64` / `gpl` (static) / `8.1` |
| FFmpeg upstream | `FFmpeg/FFmpeg` tag [`n8.1.3`](https://github.com/FFmpeg/FFmpeg/tree/1041abdc962f4cc4f394aa8de9dc5236c0c3b9e7), commit `1041abdc962f4cc4f394aa8de9dc5236c0c3b9e7` |
| Reported version string | `n8.1.3-20260926` (`--extra-version=20260926`) |
| Toolchain | gcc 16.2.0 (crosstool-NG 1.29.0.7_b1a94f6), cross `x86_64-w64-mingw32` |
| `ffmpeg.exe` | 164,747,264 bytes, SHA-256 `a35880a72ca511bbf595a28c6480c85218cdf1d6c1008511a848fc71dbad5527` |
| `ffprobe.exe` | 164,541,440 bytes, SHA-256 `493c63c393a509ab210751252fa70270330ad7413c538dce78b29adddf7ffc85` |
| License | GPL-3.0-or-later (vendor `LICENSE.txt` is byte-identical to [`third_party/licenses/GPL-3.0.txt`](../licenses/GPL-3.0.txt)) |
| Package payload | both executables + vendor `LICENSE.txt` under `_internal/runtime/ffmpeg/`; this record, [`FFMPEG_PIN.json`](FFMPEG_PIN.json) and [`SOURCE_MANIFEST.json`](SOURCE_MANIFEST.json) under `_internal/third_party/ffmpeg/` |

Both executables are the vendor's unmodified files; the hashes above were
recomputed from the packaged copies, not copied from a prior record.

The configure line observed by running the bundled binary is stored verbatim in
`SOURCE_MANIFEST.json → generated_from.observed_configure_line`:

```text
--prefix=/ffbuild/prefix --pkg-config-flags=--static --pkg-config=pkg-config --cross-prefix=x86_64-w64-mingw32- --arch=x86_64 --target-os=mingw32 --enable-gpl --enable-version3 --disable-debug --disable-w32threads --enable-pthreads --enable-iconv --enable-zlib --enable-libxml2 --enable-libvmaf --disable-libxcb --disable-xlib --enable-fontconfig --enable-libharfbuzz --enable-libfreetype --enable-libfribidi --enable-vulkan --enable-libshaderc --enable-libdav1d --enable-libvorbis --enable-librav1e --enable-librsvg --disable-libpulse --enable-gmp --enable-lzma --enable-liblcevc-dec --enable-opencl --enable-amf --enable-libaom --enable-avisynth --enable-chromaprint --enable-libdavs2 --enable-libdvdread --enable-libdvdnav --disable-libfdk-aac --enable-ffnvcodec --enable-cuda-llvm --enable-frei0r --enable-libgme --enable-libkvazaar --enable-libaribb24 --enable-libaribcaption --enable-libass --enable-libbluray --enable-libjxl --enable-libmp3lame --enable-libopus --enable-libplacebo --enable-librist --enable-libssh --enable-libtheora --enable-libvpx --enable-libwebp --enable-libzmq --enable-lv2 --enable-libvpl --enable-openal --enable-liboapv --enable-libopencore-amrnb --enable-libopencore-amrwb --enable-libopenh264 --enable-libopenjpeg --enable-libopenmpt --enable-librubberband --enable-schannel --enable-sdl2 --enable-libsnappy --enable-libsoxr --enable-libsrt --enable-libsvtav1 --enable-libtwolame --enable-libuavs3d --disable-libdrm --enable-vaapi --enable-libvidstab --enable-libvvenc --disable-whisper --enable-libx264 --enable-libx265 --enable-libxavs2 --enable-libxvid --enable-libzimg --enable-libzvbi --extra-cflags=-DLIBTWOLAME_STATIC --extra-cxxflags= --extra-libs=-lgomp --extra-ldflags=-pthread --extra-ldexeflags= --cc=x86_64-w64-mingw32-gcc --cxx=x86_64-w64-mingw32-g++ --ar=x86_64-w64-mingw32-gcc-ar --ranlib=x86_64-w64-mingw32-gcc-ranlib --nm=x86_64-w64-mingw32-gcc-nm --extra-version=20260926
```

## Why this build and not the previous one

The build bundled up to and including the first `v0.1.0-rc.1` packaging runs was
Gyan.dev `8.1-essentials_build`. That chain could not be closed: the distributor
publishes the upstream FFmpeg commit and a library list, but no build recipe, no
patch set and no source bundle, and some listed components are not pinned to an
exact revision at all (`openal-soft latest`). Its `README.txt` lists 42 external
libraries; pointing at one FFmpeg commit URL does not cover the other 41 of them
statically linked into those executables.
See [`docs/PUBLIC_RELEASE_DELTA_V0.1.md`](../../docs/PUBLIC_RELEASE_DELTA_V0.1.md).

BtbN's model is the opposite: every package in the recipe declares its upstream
repository and an exact commit, the whole build is scripted, and each release is
an immutable tagged build with a published `checksums.sha256`. That makes the
binary → build-inputs → corresponding-source relation mechanically derivable
instead of inferred.

## Corresponding source

`SOURCE_MANIFEST.json` is **generated**, not hand-maintained. It is produced from
three inputs, so it cannot silently drift from the binary:

1. the pinned vendor recipe at `58cc05f3…` (the vendor's own `scripts.d/` stages),
2. the configure line the bundled `ffmpeg.exe` actually reports,
3. [`FFMPEG_PIN.json`](FFMPEG_PIN.json) for the exact revisions and hashes.

It resolves the 81 recipe stages that the observed configure line enables, walks
their transitive `ffbuild_depends` graph, and records 117 upstream source
repositories at exact revisions, plus the build recipe itself and the primary
work. It also reports `unclaimed_enable_lib_flags`, which must stay empty: every
`--enable-lib*` flag in the shipped binary must be attributable to exactly one
stage. Regenerate with:

```powershell
python tools/ffmpeg_provenance.py manifest .tools/ffmpeg/bin/ffmpeg.exe
```

Patches applied by the recipe are limited to `patches/aom` (1) and
`patches/aribb24` (3); FFmpeg itself is built unpatched. Both patch directories
travel with the pinned recipe archive. The single target-conditional dependency
in the whole recipe (`libcurl` → OpenSSL, non-`win*` only) is recorded in
`conditional_dependency_declarations` and is correctly excluded here because this
build uses SChannel.

### Obtaining it

The release page for `v0.1.0-rc.1` carries a corresponding-source asset
(`AI-Video-Flow-0.1.0-rc.1-ffmpeg-sources.tar` plus its SHA-256 in
`SHA256SUMS.txt`). Any user can rebuild it independently from the committed
manifest:

```powershell
python tools/ffmpeg_provenance.py fetch <staging-dir>
```

This downloads each pinned archive, writes `FETCH_INDEX.json` (URL, method,
bytes, SHA-256 per component) and `SHA256SUMS.txt`, and is resumable. Large
repositories with no HTTP snapshot endpoint (`libiconv`, `mingw-w64`,
`opencore-amr`, `soxr`) are retrieved with `git archive` at the pinned commit;
the two Subversion-pinned components are listed under `vcs-retrieval-required`
with an exact `svn export` command, because their upstreams publish no HTTP
revision snapshot — see the next section.

## Residual gap, stated plainly

`libmp3lame` (SourceForge SVN r6835) and `xvid` (svn.xvid.org r2204) are pinned
to Subversion revisions. No HTTP endpoint was found that serves those revisions as
an archive, and their official release tarballs are *not* equivalent to the pinned
revisions, so this project does not present them as covered by the mirror. Their
exact revisions, repositories and retrieval commands are recorded in
`SOURCE_MANIFEST.json` and reproduced in `FETCH_INDEX.json`. Of the 119 source
records this binary resolves to (the FFmpeg primary work, the vendor build recipe,
and 117 upstream components), **117 are mirrored and hash-verified and these 2 are
delivered by pinned-revision retrieval instruction** — as stated in the shipped
`RETRIEVAL.md`. Both are separately licensed (LGPL-2.1-or-later and
GPL-2.0-or-later) rather than under GPL-3.0.

If a strictly mirrored set for all 119 records is later required, the options are
to run the `svn export` step on a machine with a Subversion client and add the
resulting archives to the bundle, or to move to a build without those two
encoders.

## Verifying a package yourself

```powershell
# 1. The staged binaries must match the pin.
python tools/ffmpeg_provenance.py verify .tools/ffmpeg/bin/ffmpeg.exe .tools/ffmpeg/bin/ffprobe.exe

# 2. The packaged copies must match the same pin.
python tools/ffmpeg_provenance.py verify `
  dist/AIVideoFlow/_internal/runtime/ffmpeg/bin/ffmpeg.exe `
  dist/AIVideoFlow/_internal/runtime/ffmpeg/bin/ffprobe.exe

# 3. The vendor package the binaries came from is the one the vendor hashed.
#    ffmpeg-n8.1.3-win64-gpl-8.1.zip -> d20ef03f... (vendor checksums.sha256)
```

`scripts/build_windows.ps1` runs step 1 against `FFMPEG_PIN.json` and aborts the
build on mismatch, so a release cannot be produced from an unpinned or silently
substituted FFmpeg. The script no longer takes media tools from `PATH`.

AI Video Flow's own code remains Apache-2.0; it invokes these executables as
separate command-line processes. FFmpeg and FFprobe stay under GPL-3.0, and
Qt Multimedia's own FFmpeg DLLs are a different, separately documented set — see
[`THIRD_PARTY_NOTICES.md`](../../THIRD_PARTY_NOTICES.md).
