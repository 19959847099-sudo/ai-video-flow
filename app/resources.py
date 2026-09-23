"""Runtime, resource and user-data locations that work in source and frozen builds."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import sys

from .version import LEGACY_USER_DATA_DIR


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def bundle_root() -> Path:
    frozen_root = getattr(sys, "_MEIPASS", None)
    return Path(frozen_root).resolve() if frozen_root else Path(__file__).resolve().parents[1]


def resource_path(*parts: str) -> Path:
    return bundle_root().joinpath(*parts)


def user_data_root() -> Path:
    configured = os.environ.get("AIVIDEO_USER_DATA_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local" / "share"))
    return (base / LEGACY_USER_DATA_DIR).resolve()


def default_workspace_root() -> Path:
    return user_data_root() / "Projects" / "workspace-v02"


def session_file() -> Path:
    return user_data_root() / "session-v1.json"


def _tool_filename(name: str) -> str:
    return name + ".exe" if os.name == "nt" and not name.lower().endswith(".exe") else name


def find_media_tool(name: str) -> str | None:
    filename = _tool_filename(name)
    configured = os.environ.get("AIVIDEO_MEDIA_BIN")
    strict = os.environ.get("AIVIDEO_MEDIA_STRICT") == "1"
    candidates = []
    if configured:
        candidates.append(Path(configured) / filename)
    if not (configured and strict):
        candidates.append(resource_path("runtime", "ffmpeg", "bin", filename))
        if is_frozen():
            candidates.append(Path(sys.executable).resolve().parent / "runtime" / "ffmpeg" / "bin" / filename)
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate.resolve())
    if not strict:
        return shutil.which(name)
    return None


def media_tool(name: str) -> str:
    path = find_media_tool(name)
    if not path:
        raise ValueError(
            f"Media tool {name} is unavailable. Reinstall AI Video Flow "
            "or configure AIVIDEO_MEDIA_BIN."
        )
    return path
