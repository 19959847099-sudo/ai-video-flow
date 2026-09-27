# Third-party runtime notice

The Windows portable package includes ffmpeg.exe and ffprobe.exe from the
BtbN/FFmpeg-Builds `n8.1.3` `win64-gpl` static build, release
`autobuild-2026-09-26-13-03`.

- Upstream: https://ffmpeg.org/
- Windows build recipe: https://github.com/BtbN/FFmpeg-Builds
- Built from FFmpeg tag n8.1.3
  (commit 1041abdc962f4cc4f394aa8de9dc5236c0c3b9e7)
- This build reports a GPL v3 configuration. The unmodified executables are
  distributed as separate command-line programs.
- The vendor LICENSE.txt is copied into runtime/ffmpeg/ in the portable
  package.
- SHA-256 of the two shipped executables, the vendor package they came from,
  and the full corresponding-source chain (vendor build recipe revision, every
  statically linked upstream component at its exact pinned revision, patches,
  and how to fetch and verify them) are recorded in
  third_party/ffmpeg/PROVENANCE.md, third_party/ffmpeg/FFMPEG_PIN.json and
  the generated third_party/ffmpeg/SOURCE_MANIFEST.json inside this package.

PySide6 is distributed under its applicable Qt for Python licensing terms.
OpenTimelineIO and other Python dependencies retain their own licenses.
