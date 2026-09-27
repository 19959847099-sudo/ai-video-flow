# Documentation

Start with the [Project Map](PROJECT_MAP.md). It links the current Architecture, Data Model, Runtime, Testing, and Releasing guides and tells contributors which boundaries and tests a change affects.

- [Release candidate notes](releases/v0.1.0-rc.1.md): user-facing highlights, limits, and download verification.
- [Final release delta](PUBLIC_RELEASE_DELTA_V0.1.md): exact FFmpeg provenance investigation, rebuilt assets, visual checks, and final gate.
- [FFmpeg binary provenance](../third_party/ffmpeg/PROVENANCE.md): exact shipped-binary facts, the generated corresponding-source manifest, and how to verify or re-fetch the source chain.
- [Public release audit](PUBLIC_RELEASE_AUDIT_V0.1.md): source/history privacy, security, licensing, and repository-hygiene checks.
- [Historical design and evidence](../evidence/): useful construction records, not a statement that every earlier UI or provider remains current.

The root [README](../README.md) is the product homepage. Older V0.2 and frozen Chinese documents remain as design history; when they differ from the current RC implementation, use the Project Map and code as the implementation reference.
