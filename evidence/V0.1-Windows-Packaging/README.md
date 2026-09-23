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
- SHA-256: `11e398425fcbf063e765b1766e1297a7ec5a9c0901329388f3de4d906e1887a4`
- Clean runtime simulation: PASS
- Extracted archive smoke: PASS
- Source-tree isolation: PASS
- Local Microsoft Defender scan: PASS for the previous 2026-09-21 artifact; not repeated for this rebuild
- BLOCKER: 0
- Packaging regression: 0

See `final-regression.md` for the 2026-09-23 full-suite RC release gate.

The clean-environment harness copies the onedir package to Windows TEMP, removes
Python, Git, source, virtualenv and Codex runtime paths from the child
environment, starts from an unrelated working directory, and exercises Chinese,
spaced and long project paths. See the JSON reports for measured runtime facts.

This evidence does not replace validation on a separate Windows machine, code
signing, non-Defender AV coverage, or real commercial-provider testing.