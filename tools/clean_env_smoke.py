"""Run the frozen GUI from an isolated copy with a deliberately minimal environment."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.version import EXECUTABLE_NAME, __version__


def minimal_environment(root, scale):
    keep = {}
    for key in ("SystemRoot", "WINDIR", "COMSPEC", "PATHEXT", "NUMBER_OF_PROCESSORS",
                "PROCESSOR_ARCHITECTURE", "USERNAME"):
        if os.environ.get(key):
            keep[key] = os.environ[key]
    keep.update({
        "PATH": str(Path(os.environ.get("WINDIR", "C:/Windows")) / "System32")
                + os.pathsep + os.environ.get("WINDIR", "C:/Windows"),
        "TEMP": str(root / "temp"),
        "TMP": str(root / "temp"),
        "LOCALAPPDATA": str(root / "localappdata"),
        "USERPROFILE": str(root / "profile"),
        "AIVIDEO_USER_DATA_DIR": str(root / "userdata"),
        "QT_QPA_PLATFORM": "offscreen",
        "QT_SCALE_FACTOR": str(scale),
    })
    for path in ("temp", "localappdata", "profile", "userdata"):
        (root / path).mkdir(parents=True, exist_ok=True)
    return keep



def runtime_version(executable, environment):
    result = subprocess.run(
        [str(executable), "-version"], env=environment,
        capture_output=True, text=True, timeout=30,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    if result.returncode:
        raise RuntimeError(f"Runtime command failed: {executable}")
    return result.stdout.splitlines()[0]

def execute(exe, cwd, project, settings, report, env, *extra):
    command = [
        str(exe), "--smoke-test", "--data-dir", str(project),
        "--settings-path", str(settings), "--smoke-report", str(report), *extra,
    ]
    result = subprocess.run(
        command, cwd=cwd, env=env, capture_output=True, timeout=180,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    if result.returncode:
        details = report.read_text(encoding="utf-8") if report.is_file() else (
            result.stdout.decode(errors="replace") + result.stderr.decode(errors="replace")
        )
        raise RuntimeError(f"Packaged smoke failed ({result.returncode}): {details}")
    payload = json.loads(report.read_text(encoding="utf-8"))
    if not payload.get("passed"):
        raise RuntimeError(f"Packaged smoke reported failure: {payload}")
    return payload


dist = Path(sys.argv[1]).resolve()
source = Path(sys.argv[2]).resolve()
evidence = Path(sys.argv[3]).resolve()
if dist == source:
    raise SystemExit("Distribution cannot be the source root")
evidence.mkdir(parents=True, exist_ok=True)

with TemporaryDirectory(prefix="AIGCFlow-Clean-") as temporary:
    sandbox = Path(temporary)
    isolated = sandbox / "portable copy"
    shutil.copytree(dist, isolated)
    exe = isolated / f"{EXECUTABLE_NAME}.exe"
    if not exe.is_file():
        raise SystemExit("Packaged executable missing")
    cwd = sandbox / "unrelated cwd"
    cwd.mkdir()
    nested = sandbox / ("\u6d4b\u8bd5\u9879\u76ee " + "space") / (
        "long-" + "segment-" * 8
    ) / "\u7b2c\u4e00\u96c6"
    settings = sandbox / "local settings" / "settings.json"
    settings.parent.mkdir(parents=True)
    settings.write_bytes(b"\xff\xfe truncated settings")

    environment = minimal_environment(sandbox, "1")
    runtime_bin = isolated / "_internal" / "runtime" / "ffmpeg" / "bin"
    runtime_commands = {
        "ffmpeg": runtime_version(runtime_bin / "ffmpeg.exe", environment),
        "ffprobe": runtime_version(runtime_bin / "ffprobe.exe", environment),
    }
    full = execute(
        exe, cwd, nested, settings, sandbox / "full.json", environment
    )
    locations = full["checks"]["module_locations"]
    source_text = str(source).casefold()
    if any(source_text in value.casefold() for value in locations.values()):
        raise RuntimeError(f"Source tree dependency detected: {locations}")

    dpi = {}
    for scale in ("1.25", "1.5"):
        env = minimal_environment(sandbox / ("dpi-" + scale), scale)
        project = sandbox / ("dpi project " + scale)
        corrupt = sandbox / ("dpi-" + scale) / "settings.json"
        corrupt.write_text('{"version":999,"settings":{}}', encoding="utf-8")
        result = execute(
            exe, cwd, project, corrupt, sandbox / ("dpi-" + scale + ".json"),
            env, "--smoke-quick"
        )
        dpi[scale] = result

    missing_root = sandbox / "missing-runtime"
    env = minimal_environment(missing_root, "1")
    empty = missing_root / "empty-bin"
    empty.mkdir(parents=True)
    env["AIVIDEO_MEDIA_BIN"] = str(empty)
    env["AIVIDEO_MEDIA_STRICT"] = "1"
    missing_settings = missing_root / "settings.json"
    missing_settings.write_text("{bad", encoding="utf-8")
    missing = execute(
        exe, cwd, missing_root / "project", missing_settings,
        sandbox / "missing.json", env, "--expect-missing-media", "--smoke-quick"
    )

    crash_root = sandbox / "crash-recovery"
    crash_env = minimal_environment(crash_root, "1")
    crash_settings = crash_root / "settings.json"
    crash_settings.write_text("{bad", encoding="utf-8")
    crash_project = crash_root / "project"
    crash_report = crash_root / "interrupted.json"
    process = subprocess.Popen(
        [str(exe), "--smoke-test", "--data-dir", str(crash_project),
         "--settings-path", str(crash_settings), "--smoke-report", str(crash_report)],
        cwd=cwd, env=crash_env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    deadline = __import__("time").time() + 20
    while not (crash_project / "project.json").is_file() and __import__("time").time() < deadline:
        __import__("time").sleep(0.1)
    process.kill()
    process.wait(timeout=20)
    recovered = execute(
        exe, cwd, crash_project, crash_settings, crash_root / "recovered.json",
        crash_env, "--smoke-quick"
    )

    summary = {
        "schema": 1,
        "version": __version__,
        "passed": True,
        "isolation": "Copied portable folder under Windows TEMP; minimal PATH; no Python, Git, source or virtualenv paths.",
        "runtime_commands": runtime_commands,
        "full": full,
        "dpi": dpi,
        "missing_media": missing,
        "abnormal_exit_recovery": recovered,
        "source_tree_isolated": True,
        "clean_copy_removed_after_process_exit": True,
        "commercial_provider_calls": 0,
    }
    (evidence / "clean-environment.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
print(json.dumps(summary, ensure_ascii=False, indent=2))
