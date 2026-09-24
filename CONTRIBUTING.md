# Contributing to AI Video Flow

Thanks for helping. This is a Windows-first RC desktop project; small, testable changes are easiest to review.

1. For any substantial change, read the [Project Map](docs/PROJECT_MAP.md), choose its relevant **Change Map** row, and follow the linked [Architecture](docs/ARCHITECTURE.md), [Data Model](docs/DATA_MODEL.md), or [Runtime](docs/RUNTIME.md) boundary before editing code.
2. Use Python 3.11+ on Windows. Install `requirements.txt`; FFmpeg and FFprobe on `PATH` are needed for media tests. Start the source app with `python -m app.preparation_gui`.
3. Preserve Product Truth: Green review and UI selection do not imply Current; a Creative Proposal is not the production script until explicit Apply; Assembly consumes Current rather than picking a Candidate itself. Do not weaken tests to make a change pass.
4. Run the targeted modules in [Testing](docs/TESTING.md). For a release-sensitive change, run `python -m unittest discover -s tests -q`; packaging/dependency changes also need the frozen, ZIP, and Installer smoke gates in [Releasing](docs/RELEASING.md).
5. Open a focused pull request explaining what changed, why, the truth boundary, and the tests actually run. Note fixture/zero-call results as such; do not claim live commercial-provider validation.

Never commit API keys, local projects, user media, `build/`, `dist/`, or `release/` binaries. For security reports, follow [SECURITY.md](SECURITY.md) rather than posting secrets in a public issue. The repository's own code uses [Apache-2.0](LICENSE); bundled dependencies have [separate notices](THIRD_PARTY_NOTICES.md).
