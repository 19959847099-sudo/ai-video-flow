# FFmpeg / FFprobe binary provenance — v0.1.0-rc.1

Status: **verified binary identity, incomplete corresponding-source chain**. This record is for the exact local Windows release candidate, not an assertion that binary redistribution is cleared. Do not publish Installer or portable ZIP while the source-delivery gate below is open.

## Binary identity

| Field | Value / evidence |
| --- | --- |
| Distributor | [Gyan.dev FFmpeg builds](https://www.gyan.dev/ffmpeg/builds/), WinGet package `Gyan.FFmpeg.Essentials` |
| Package/build | `ffmpeg-8.1-essentials_build`, version string `8.1-essentials_build-www.gyan.dev` |
| Architecture/toolchain | Windows x64 static; GCC 15.2.0 Rev11 / MSYS2 per `ffmpeg -version` |
| FFmpeg source | Distributor `README.txt` points to [FFmpeg commit `9047fa1b08`](https://github.com/FFmpeg/FFmpeg/commit/9047fa1b08); no local source archive is supplied |
| `ffmpeg.exe` SHA-256 | `1a65d5b0b10d8d9a81d2824a3538046a40ed3607c906b335a166add87613f705` |
| `ffprobe.exe` SHA-256 | `54b944d6095c4588d7548424d7acd5118390a9d4f01b1c92f841547fc9a7429c` |
| License mode | GPLv3: `--enable-gpl --enable-version3 --enable-static`, with `libx264` and `libx265` enabled |
| Package payload | The two executables, distributor `LICENSE` (GPLv3), distributor `README.txt`, and local runtime notice are copied under `_internal/runtime/ffmpeg/` in the onedir app |

The exact `ffmpeg -version` configure line begins:

```text
--enable-gpl --enable-version3 --enable-static --disable-w32threads --disable-autodetect --enable-cairo --enable-fontconfig --enable-iconv --enable-gnutls --enable-libxml2 --enable-gmp --enable-bzlib --enable-lzma --enable-zlib --enable-libsrt --enable-libssh --enable-libzmq --enable-avisynth --enable-sdl2 --enable-libwebp --enable-libx264 --enable-libx265 --enable-libxvid --enable-libaom --enable-libopenjpeg --enable-libvpx --enable-mediafoundation --enable-libass --enable-libfreetype --enable-libfribidi --enable-libharfbuzz --enable-libvidstab --enable-libvmaf --enable-libzimg --enable-amf --enable-cuda-llvm --enable-cuvid --enable-dxva2 --enable-d3d11va --enable-d3d12va --enable-ffnvcodec --enable-libvpl --enable-nvdec --enable-nvenc --enable-vaapi --enable-openal --enable-libgme --enable-libopenmpt --enable-libopencore-amrwb --enable-libmp3lame --enable-libtheora --enable-libvo-amrwbenc --enable-libgsm --enable-libopencore-amrnb --enable-libopus --enable-libspeex --enable-libvorbis --enable-librubberband
```

The distributor README lists external libraries (not necessarily all static source obligations): AviSynth+, cairo, aom, ass, freetype, fribidi, harfbuzz, gme, gsm, lame, OpenCORE-AMR NB/WB, openjpeg, openmpt, opus, rubberband, speex, srt, ssh, theora, vidstab, vmaf, vo-amrwbenc, vorbis, vpx, webp, x264, x265, xvid, zimg, zmq, OpenAL, SDL2, and hardware-acceleration headers/libraries. It also lists some version identifiers—for example aom `v3.13.1-302-g935aaa9b71`, x264 `v0.165.3223`, x265 `4.1-240-g8be7dbf81`, and zimg `release-3.0.6-213-gbf3f425`—but not a uniform exact revision and fetch URL for every enabled component. The installed distribution has binaries, docs, presets, `LICENSE` and `README.txt`; no dependency source archives or complete build recipe were found.

## Corresponding-source gate

The [vendor page](https://www.gyan.dev/ffmpeg/builds/) confirms all regular builds are static GPLv3 and links the FFmpeg source commit. It does not, in the inspected material, publish a matching complete build recipe and source set for this exact 8.1 essentials package. The [vendor support repository](https://github.com/GyanD/codexffmpeg) is an issue/support repository, not an identified recipe archive for this binary. This is a documented evidence gap, **not proof that the distributor violates a license**. [FFmpeg's legal guidance](https://ffmpeg.org/legal.html) and the [GNU GPL FAQ](https://www.gnu.org/licenses/gpl-faq.en.html) explain why exact corresponding source matters when redistributing binaries.

There is currently **no verified corresponding-source artifact or URL** for these two exact executable hashes. A link to the FFmpeg commit alone does not cover the enabled statically linked libraries and build scripts. Do not represent `third_party/licenses/GPL-3.0.txt` or this manifest as a substitute for source delivery.

Minimum closure evidence, before publication:

1. Obtain the complete source inputs and build-control scripts/patches for this exact package from the distributor, or adopt another binary whose exact source/build chain can be verified.
2. Record every relevant source archive/commit and SHA-256, the build recipe revision, any patches, and how they correspond to the observed configure line and executable hashes. Independently spot-check the archive contents and dependency inventory.
3. Make that corresponding source reasonably accessible alongside the downloadable binaries (a separate GitHub Release source asset or an equivalent explicit, durable source location), and include its hash in `SHA256SUMS.txt` if it is an asset.
4. Rebuild the AI Video Flow Installer/ZIP if the binary or packaged notice changes; rerun media, portable, Installer and checksum gates. Update this manifest, notices and release notes with the actual final strategy.

## Alternatives investigated

- **Retain Gyan:** lowest regression risk, but currently fails the source-chain gate above. It is retained locally, not approved for publication.
- **BtbN/FFmpeg-Builds:** [build scripts, package recipes and patch directories](https://github.com/BtbN/FFmpeg-Builds) are public, and tagged Windows builds exist. This is a promising replacement candidate, but no exact archived binary + script revision + complete source-delivery package was fetched and verified in this audit. Merely pointing to a moving branch would repeat the same gap. Replacement also requires the full media and Installer gates.
- **Self-build or external dependency:** not adopted. A pinned minimal build could reduce enabled libraries but creates a Windows build-maintenance obligation. Requiring users to install FFmpeg separately would materially degrade the portable/Installer experience and needs a separate product decision.

The project's Apache-2.0 license covers its own code only. FFmpeg/FFprobe retain their GPLv3 terms. Qt Multimedia's separate FFmpeg DLLs are documented in [`THIRD_PARTY_NOTICES.md`](../../THIRD_PARTY_NOTICES.md) and must not be conflated with these command-line executables.
