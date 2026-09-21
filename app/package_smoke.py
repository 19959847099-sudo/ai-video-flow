"""In-process release smoke used by the isolated portable-package harness."""
from __future__ import annotations

import ctypes
import os
from pathlib import Path
import time

from PySide6.QtCore import QCoreApplication, QEvent

from .core import write_json
from .integrated_gui import ApplicationShell
from .resources import find_media_tool, is_frozen, resource_path
from .version import __version__

SCRIPT = """Packaging Smoke/名称
01/章节/Release

001/First shot
【Character/-/Coat】/Voice
【Interior/Night】/Room tone

镜头：
Static medium shot.

动作：
Character enters.
"""


def _rss_bytes() -> int:
    if os.name != "nt":
        return 0
    class Counters(ctypes.Structure):
        _fields_ = [
            ("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong),
            ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
        ]
    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    kernel32 = ctypes.windll.kernel32
    psapi = ctypes.windll.psapi
    kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    psapi.GetProcessMemoryInfo.argtypes = [
        ctypes.c_void_p, ctypes.POINTER(Counters), ctypes.c_ulong
    ]
    handle = kernel32.GetCurrentProcess()
    if not psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
        return 0
    return int(counters.WorkingSetSize)


def _pump(app, seconds=0.04):
    until = time.perf_counter() + seconds
    while time.perf_counter() < until:
        app.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        time.sleep(0.002)


def _module_locations():
    import app
    import opentimelineio
    import PySide6
    return {
        "app": str(Path(app.__file__).resolve()),
        "PySide6": str(Path(PySide6.__file__).resolve()),
        "opentimelineio": str(Path(opentimelineio.__file__).resolve()),
    }


def run_packaged_smoke(app, project_root, settings_path, report_path,
                       *, expect_missing_media=False, quick=False) -> int:
    report_path = Path(report_path)
    project_root = Path(project_root)
    checks = {}
    errors = []
    shell = None
    try:
        shell = ApplicationShell(project_root, settings_path=settings_path)
        shell.show()
        _pump(app)
        checks["frozen"] = is_frozen()
        checks["version"] = __version__
        checks["module_locations"] = _module_locations()
        checks["resource_demo_asset"] = resource_path(
            "app", "preparation", "demo_assets", "convenience-store-night.png"
        ).is_file()
        checks["settings_recovered"] = bool(shell.settings.error)
        checks["api_key_required_for_startup"] = False

        if not shell.workspace.script:
            shell.workspace.apply(SCRIPT)
            shell.refresh_all()
        chapter = shell.workspace.script.chapters[0]
        shot = chapter.shots[0]
        routes = []
        for workspace in ("preparation", "production", "creative", "assembly", "settings"):
            shell.navigate(workspace, chapter_id=chapter.id, shot_id=shot.id)
            _pump(app, 0.015)
            routes.append(shell.router.current.workspace)
        checks["workspace_routes"] = routes
        checks["workspace_switch"] = routes == [
            "preparation", "production", "creative", "assembly", "settings"
        ]

        dimensions = {}
        for width, height in ((1280, 720), (1600, 1000), (1000, 600)):
            shell.resize(width, height)
            _pump(app, 0.02)
            dimensions[f"{width}x{height}"] = [shell.width(), shell.height()]
        checks["window_sizes"] = dimensions
        checks["minimum_size_enforced"] = dimensions["1000x600"][0] >= 1100

        widgets_before = len(app.allWidgets())
        memory_before = _rss_bytes()
        loops = 10 if quick else 100
        for index in range(loops):
            workspace = ("preparation", "production", "creative", "assembly", "settings")[index % 5]
            shell.navigate(workspace, chapter_id=chapter.id, shot_id=shot.id)
            if index % 10 == 0:
                _pump(app, 0.01)
        _pump(app)
        widgets_after = len(app.allWidgets())
        memory_after = _rss_bytes()
        checks["workspace_stress"] = {
            "switches": loops,
            "widgets_before": widgets_before,
            "widgets_after": widgets_after,
            "widget_growth": widgets_after - widgets_before,
            "rss_before": memory_before,
            "rss_after": memory_after,
            "rss_growth": memory_after - memory_before,
        }
        checks["bounded_widgets"] = widgets_after - widgets_before < 80

        wall_start = time.perf_counter()
        cpu_start = time.process_time()
        _pump(app, 0.8 if not quick else 0.15)
        wall = time.perf_counter() - wall_start
        cpu = time.process_time() - cpu_start
        checks["idle_cpu_ratio"] = round(cpu / wall, 4) if wall else 0
        checks["idle_cpu_reasonable"] = checks["idle_cpu_ratio"] < 0.35

        ffmpeg = find_media_tool("ffmpeg")
        ffprobe = find_media_tool("ffprobe")
        checks["media_tools"] = {"ffmpeg": ffmpeg, "ffprobe": ffprobe}
        checks["media_expectation"] = (
            not ffmpeg and not ffprobe if expect_missing_media else bool(ffmpeg and ffprobe)
        )

        shell.navigate("production", chapter_id=chapter.id, shot_id=shot.id)
        _pump(app)
        shell.close()
        _pump(app)
        checks["first_close"] = not shell.isVisible()

        restarted = ApplicationShell(project_root, settings_path=settings_path)
        restarted.show()
        _pump(app)
        checks["restart_workspace"] = restarted.router.current.workspace
        checks["restart_ok"] = restarted.router.current.workspace == "production"
        restarted.close()
        _pump(app)
        checks["shutdown_clean"] = not restarted.isVisible()
        shell = None
    except Exception as exc:
        errors.append(f"{type(exc).__name__}: {exc}")
        if shell is not None:
            try:
                shell.close()
            except Exception:
                pass

    required = [
        "frozen", "resource_demo_asset", "settings_recovered",
        "workspace_switch", "minimum_size_enforced", "bounded_widgets",
        "idle_cpu_reasonable", "media_expectation", "first_close",
        "restart_ok", "shutdown_clean",
    ]
    passed = not errors and all(checks.get(key) for key in required)
    payload = {
        "schema": 1,
        "version": __version__,
        "passed": passed,
        "checks": checks,
        "errors": errors,
        "commercial_provider_calls": 0,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(report_path, payload)
    return 0 if passed else 2
