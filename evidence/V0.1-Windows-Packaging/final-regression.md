# Final RC regression

Date: 2026-09-21
Candidate: 0.1.0-rc.1

## Source regression

Commands:

    python -m py_compile app/resources.py app/version.py app/package_smoke.py app/preparation_gui.py app/integrated_gui.py app/production.py tools/clean_env_smoke.py tools/archive_smoke.py tools/package_report.py tools/finalize_release.py tools/write_windows_version.py tests/test_packaging.py tests/test_integration_shell.py
    python -m unittest tests.test_packaging tests.test_integration_shell tests.test_preparation_creative tests.test_preparation_creative_gui tests.test_production_runtime tests.test_production_runtime_gui tests.test_chapter_finishing -v

Result: PASS. The main focused suite passed 44 tests. A final 17-test integration and Assembly run also passed after adding two release-boundary cases.

Release boundaries confirmed:

- A running in-session worker blocks application close with a clear message.
- A missing bound media file blocks Assembly locally without crashing or invalidating the remaining clips.
- Simulated OpenTimelineIO unavailability blocks handoff only; the rendered preview remains usable.
- Portable OTIO export and round-trip remain passing when OpenTimelineIO is present.
- Commercial provider calls: 0.

## Frozen release

- Clean runtime simulation: PASS.
- ZIP extraction and frozen smoke: PASS.
- Source-tree isolation: PASS.
- Microsoft Defender local scan: PASS; no threats reported.
- BLOCKER: 0.
- Packaging regression: 0.