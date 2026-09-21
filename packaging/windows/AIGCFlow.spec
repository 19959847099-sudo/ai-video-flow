# -*- mode: python ; coding: utf-8 -*-
import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

root = Path(SPEC).resolve().parents[2]
ffmpeg = Path(os.environ["AIGCFLOW_FFMPEG"]).resolve()
ffprobe = Path(os.environ["AIGCFLOW_FFPROBE"]).resolve()
ffmpeg_license = Path(os.environ["AIGCFLOW_FFMPEG_LICENSE"]).resolve()
ffmpeg_readme = Path(os.environ["AIGCFLOW_FFMPEG_README"]).resolve()
version_file = os.environ.get("AIGCFLOW_VERSION_FILE")

otio_datas = collect_data_files("opentimelineio")
otio_binaries = []
otio_hiddenimports = (
    collect_submodules("opentimelineio.adapters")
    + collect_submodules("opentimelineio.plugins")
    + collect_submodules("opentimelineio.schema")
)

datas = [
    (str(root / "app" / "preparation" / "demo_assets"), "app/preparation/demo_assets"),
    (str(ffmpeg_license), "runtime/ffmpeg"),
    (str(ffmpeg_readme), "runtime/ffmpeg"),
    (str(root / "packaging" / "windows" / "THIRD_PARTY_NOTICES.md"), "runtime/ffmpeg"),
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
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AIGCFlow",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    version=version_file,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="AIGCFlow",
)
