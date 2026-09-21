# Dependency audit

## Release runtime

- CPython 3.13 runtime frozen by PyInstaller.
- PySide6 6.10.2: Qt Core, GUI, Widgets, SVG and Multimedia used by the desktop UI.
- Pillow 12.1.1: image validation and local fixture rendering.
- pydantic 2.12.5: persisted production models.
- OpenTimelineIO 0.18.1: assembly interchange export.
- FFmpeg and FFprobe 8.1 Gyan Essentials: bundled command-line runtime with license and distributor README.

## Build-only

- PyInstaller 6.22.3 and its hook/runtime dependencies.
- Test modules, preview scripts, design material and evidence are not included.

## Excluded

- QtWebEngine and QtDesigner are unused.
- IPython, Jedi, debugpy, qt-material, pytest, setuptools and NumPy are excluded from the release graph.
- Commercial credentials, project data, Codex runtimes and source-tree assets are not bundled.

FFmpeg is an unmodified GPL-configured external program. See
packaging/windows/THIRD_PARTY_NOTICES.md for source and distribution details.
