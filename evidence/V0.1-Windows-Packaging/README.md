# V0.1 Windows Packaging evidence

Candidate: `0.1.0-rc.1`

Build command:

    powershell -ExecutionPolicy Bypass -File scripts/build_windows.ps1

The build produces a windowed PyInstaller onedir package, runs the clean-runtime
harness, creates the ZIP, then extracts and smoke-tests that archive. Portable
binaries remain under `dist/` and `release/` and are excluded from Git.

Final artifact: `AIGCFlow-0.1.0-rc.1-windows-x64.zip`

- Portable folder: 347.9 MB, 236 files
- ZIP: 136.7 MB
- SHA-256: `0539eca21c9df35c293bf74379fac33974080b3f8f376c79f33f712f29844d27`
- Clean runtime simulation: PASS
- Extracted archive smoke: PASS
- Source-tree isolation: PASS
- Local Microsoft Defender scan: PASS
- BLOCKER: 0
- Packaging regression: 0

The clean-environment harness copies the onedir package to Windows TEMP, removes
Python, Git, source, virtualenv and Codex runtime paths from the child
environment, starts from an unrelated working directory, and exercises Chinese,
spaced and long project paths. See the JSON reports for measured runtime facts.

This evidence does not replace validation on a separate Windows machine, code
signing, non-Defender AV coverage, or real commercial-provider testing.