"""Measure a portable distribution and write reproducible JSON/Markdown reports."""
from __future__ import annotations

import hashlib
from importlib.metadata import version as package_version
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.version import __version__


def size(path):
    if path.is_file():
        return path.stat().st_size
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def scan_secret(root, secret):
    if not secret or len(secret) < 8:
        return None
    needle = secret.encode("utf-8")
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        with path.open("rb") as stream:
            tail = b""
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                data = tail + block
                if needle in data:
                    return path.relative_to(root).as_posix()
                tail = data[-len(needle):]
    return None


root = Path(sys.argv[1]).resolve()
json_target = Path(sys.argv[2]).resolve()
markdown_target = Path(sys.argv[3]).resolve()
if not (root / "AIGCFlow.exe").is_file():
    raise SystemExit("AIGCFlow.exe not found")

files = [(item.relative_to(root).as_posix(), item.stat().st_size)
         for item in root.rglob("*") if item.is_file()]
files.sort(key=lambda row: row[1], reverse=True)
top = []
for child in root.iterdir():
    top.append({"name": child.name, "bytes": size(child)})
top.sort(key=lambda item: item["bytes"], reverse=True)

ffmpeg = root / "_internal" / "runtime" / "ffmpeg" / "bin" / "ffmpeg.exe"
ffprobe = root / "_internal" / "runtime" / "ffmpeg" / "bin" / "ffprobe.exe"
version_output = subprocess.run(
    [str(ffmpeg), "-version"], capture_output=True, text=True,
    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    timeout=20,
).stdout.splitlines()[0]

for forbidden in ("tests", "design", "evidence", "data"):
    if (root / forbidden).exists() or (root / "_internal" / forbidden).exists():
        raise SystemExit(f"Forbidden release content: {forbidden}")

secret_hit = scan_secret(root, os.environ.get("OPENAI_COMPATIBLE_API_KEY", ""))
report = {
    "schema": 1,
    "version": __version__,
    "artifact": str(root),
    "build_environment": {
        "python": platform.python_version(),
        "PyInstaller": package_version("PyInstaller"),
        "PySide6": package_version("PySide6"),
        "OpenTimelineIO": package_version("OpenTimelineIO"),
        "Pillow": package_version("Pillow"),
        "pydantic": package_version("pydantic"),
    },
    "total_bytes": size(root),
    "file_count": len(files),
    "exe_bytes": (root / "AIGCFlow.exe").stat().st_size,
    "python_runtime_bytes": size(root / "_internal" / "python313.dll"),
    "qt_bytes": size(root / "_internal" / "PySide6"),
    "ffmpeg_bytes": ffmpeg.stat().st_size,
    "ffprobe_bytes": ffprobe.stat().st_size,
    "ffmpeg_version": version_output,
    "ffmpeg_sha256": digest(ffmpeg),
    "ffprobe_sha256": digest(ffprobe),
    "top_level": top,
    "largest_files": [{"path": name, "bytes": value} for name, value in files[:20]],
    "forbidden_content_absent": True,
    "configured_secret_scanned": secret_hit is not None or bool(
        os.environ.get("OPENAI_COMPATIBLE_API_KEY")
    ),
    "secret_hit": secret_hit,
}
if secret_hit:
    raise SystemExit("Configured API secret found in distribution")

json_target.parent.mkdir(parents=True, exist_ok=True)
json_target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
mb = lambda value: f"{value / 1024 / 1024:.1f} MB"
lines = [
    "# Windows packaging build report", "",
    f"- Version: {__version__}",
    f"- Total: {mb(report['total_bytes'])}",
    f"- Executable: {mb(report['exe_bytes'])}",
    f"- Qt: {mb(report['qt_bytes'])}",
    f"- FFmpeg: {mb(report['ffmpeg_bytes'])}",
    f"- FFprobe: {mb(report['ffprobe_bytes'])}",
    f"- Files: {report['file_count']}", "",
    "## Largest files", "",
]
lines.extend(f"- {name}: {mb(value)}" for name, value in files[:20])
markdown_target.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(json.dumps(report, ensure_ascii=False, indent=2))
