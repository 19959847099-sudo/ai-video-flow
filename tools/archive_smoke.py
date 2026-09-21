"""Verify the released ZIP, then run its frozen executable outside the source tree."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import zipfile


archive = Path(sys.argv[1]).resolve()
source = Path(sys.argv[2]).resolve()
target = Path(sys.argv[3]).resolve()
with TemporaryDirectory(prefix="AIGCFlow-Zip-") as temporary:
    root = Path(temporary)
    with zipfile.ZipFile(archive) as package:
        bad = package.testzip()
        if bad:
            raise RuntimeError(f"Corrupt ZIP entry: {bad}")
        package.extractall(root)
    env = {key: os.environ[key] for key in (
        "SystemRoot", "WINDIR", "COMSPEC", "PATHEXT", "USERNAME"
    ) if key in os.environ}
    env.update({
        "PATH": str(Path(os.environ.get("WINDIR", "C:/Windows")) / "System32")
                + os.pathsep + os.environ.get("WINDIR", "C:/Windows"),
        "TEMP": str(root / "temp"), "TMP": str(root / "temp"),
        "LOCALAPPDATA": str(root / "localappdata"),
        "USERPROFILE": str(root / "profile"),
        "AIVIDEO_USER_DATA_DIR": str(root / "userdata"),
        "QT_QPA_PLATFORM": "offscreen",
    })
    for name in ("temp", "localappdata", "profile", "userdata"):
        (root / name).mkdir()
    settings = root / "settings.json"
    settings.write_text("{bad", encoding="utf-8")
    report = root / "report.json"
    command = [
        str(root / "AIGCFlow.exe"), "--smoke-test", "--smoke-quick",
        "--data-dir", str(root / "\u5f52\u6863 \u9879\u76ee"),
        "--settings-path", str(settings), "--smoke-report", str(report),
    ]
    result = subprocess.run(
        command, cwd=root / "temp", env=env, capture_output=True, timeout=180,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    if result.returncode:
        raise RuntimeError((result.stdout + result.stderr).decode(errors="replace"))
    payload = json.loads(report.read_text(encoding="utf-8"))
    if not payload.get("passed"):
        raise RuntimeError(f"Archive smoke failed: {payload}")
    payload["archive_integrity"] = True
    payload["source_tree_isolated"] = all(
        str(source).casefold() not in path.casefold()
        for path in payload["checks"]["module_locations"].values()
    )
    if not payload["source_tree_isolated"]:
        raise RuntimeError("Archive resolved a module from the source tree")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
print(target)
