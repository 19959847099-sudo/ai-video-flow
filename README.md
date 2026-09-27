# AI Video Flow

An open-source AI video production workflow for Windows.

> **Early stage.** `v0.1.0-rc.1` is the first public engineering baseline: real, packaged and tested, but not a polished or production-ready application.

AI generation is one stage in a longer production process.

It keeps the parts of an AI video project that usually drift apart connected — script, shared asset requirements, generated or imported takes, human review, the chosen take for each shot, creative revisions, chapter assembly — in one desktop application.

![The Production workspace in the current D layout, with two reviewed Candidates and a selected clip](docs/assets/screenshots/production-1600x1000.png)

*From a disposable demo project: one clip was encoded locally from the bundled demo scene image, the other Candidate came from a zero-call fixture. Neither is a commercial model result.*

![Workflow overview: preparation, production, creative revision, assembly and output](docs/assets/workflow-overview.svg)

## What works today

A PySide6 Windows app arranged as four workspaces — Preparation, Production, Creative, Assembly — over project / chapter / shot state, with asset requirements, candidate review, an explicit **Current** take per shot, FFmpeg media handling, chapter preview and output, and OpenTimelineIO handoff. The Installer and portable ZIP are both built and smoke-tested.

The product keeps several things deliberately separate: a green review does not select a take; a proposal changes the script only when applied; assembly reads *Current* media only. See [Data Model](docs/DATA_MODEL.md).

## Current limitations

- Media providers are **local zero-call fixtures**. Commercial image/video/audio integration is limited; Creative text can optionally use a configured OpenAI-compatible API.
- UI and interaction are not final; the installer works but is basic; internationalisation is incomplete.
- Not yet validated through broad real-world use.
- Builds are unsigned (SmartScreen may warn), there is no updater or credential store, and project formats are not yet migrated between versions — back up important projects.

## Download and run

Download either form from this repository's GitHub Releases, under the `v0.1.0-rc.1` pre-release, and verify it against the published `SHA256SUMS.txt`.

- **Installer** `AI-Video-Flow-0.1.0-rc.1-windows-x64-setup.exe` — per-user install; uninstalling does not delete your projects.
- **Portable** `AI-Video-Flow-0.1.0-rc.1-windows-x64.zip` — extract and run `AIVideoFlow.exe`.

To run from source: Windows, Python 3.11+, FFmpeg/FFprobe on `PATH`, then

```powershell
python -m pip install -r requirements.txt
python -m app.preparation_gui
```

## Documentation

[Project Map](docs/PROJECT_MAP.md) is the entry point — how it is arranged, what to change, what to run. Also [Architecture](docs/ARCHITECTURE.md), [Data Model](docs/DATA_MODEL.md), [Testing](docs/TESTING.md), [Releasing](docs/RELEASING.md), [release notes](docs/releases/v0.1.0-rc.1.md), [Contributing](CONTRIBUTING.md) and [Security](SECURITY.md).

## Development status

Further V0.1 changes are expected to focus on bug, security and release fixes. **The next major cycle is V0.2**, where architecture, extensibility, provider integration and usability are all expected to move substantially — none of that is implemented today, and it is not described here as a current capability.

## License

AI Video Flow's own code is [Apache-2.0](LICENSE). Bundled third-party components keep their own licenses; see [Third-Party Notices](THIRD_PARTY_NOTICES.md).
