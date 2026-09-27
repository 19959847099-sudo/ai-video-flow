# -*- mode: python ; coding: utf-8 -*-
import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

root = Path(SPEC).resolve().parents[2]
ffmpeg = Path(os.environ["AIGCFLOW_FFMPEG"]).resolve()
ffprobe = Path(os.environ["AIGCFLOW_FFPROBE"]).resolve()
ffmpeg_license = Path(os.environ["AIGCFLOW_FFMPEG_LICENSE"]).resolve()
version_file = os.environ.get("AIGCFLOW_VERSION_FILE")

otio_datas = collect_data_files("opentimelineio")
otio_binaries = []
otio_hiddenimports = (
    collect_submodules("opentimelineio.adapters")
    + collect_submodules("opentimelineio.plugins")
    + collect_submodules("opentimelineio.schema")
)
datas = [
    (str(root / "LICENSE"), "."),
    (str(root / "THIRD_PARTY_NOTICES.md"), "."),
    (str(root / "third_party" / "licenses"), "third_party/licenses"),
    (str(root / "app" / "preparation" / "demo_assets"), "app/preparation/demo_assets"),
    (str(root / "third_party" / "ffmpeg"), "third_party/ffmpeg"),
    (str(ffmpeg_license), "runtime/ffmpeg"),
    (str(root / "packaging" / "windows" / "THIRD_PARTY_NOTICES.md"), "runtime/ffmpeg"),
    (str(root / "packaging" / "windows" / "AI-Video-Flow.ico"), "packaging/windows"),
] + otio_datas
binaries = [
    (str(ffmpeg), "runtime/ffmpeg/bin"),
    (str(ffprobe), "runtime/ffmpeg/bin"),
] + otio_binaries

a = Analysis(
    [str(root / "packaging" / "windows" / "launcher.py")],
    pathex=[str(root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=otio_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets",
        "PySide6.QtWebEngineQuick", "PySide6.QtQuick", "PySide6.QtQml",
        "PySide6.QtDesigner", "PySide6.QtTest",
        "IPython", "jedi", "debugpy", "qt_material", "numpy",
        "pytest", "setuptools",
    ],
    noarchive=False,
)
# Qt Virtual Keyboard is not used by the D shell and is GPL-only in Qt's
# community distribution. Do not ship its DLL or input-context plugin.
a.binaries = [item for item in a.binaries if "virtualkeyboard" not in item[0].casefold()]
a.datas = [item for item in a.datas if "virtualkeyboard" not in item[0].casefold()]
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AIVideoFlow",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    version=version_file,
    icon=str(root / "packaging" / "windows" / "AI-Video-Flow.ico"),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="AIVideoFlow",
)
