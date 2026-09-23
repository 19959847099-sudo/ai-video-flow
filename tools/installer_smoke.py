"""Per-user install, shortcut, project, reinstall and uninstall release smoke."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import winreg

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.version import EXECUTABLE_NAME, PRODUCT_NAME, __version__

UNINSTALL_ROOT = r"Software\Microsoft\Windows\CurrentVersion\Uninstall"


def powershell(script: str, **variables: str) -> str:
    env = os.environ.copy()
    env.update({f"AIVIDEO_SMOKE_{key.upper()}": str(value) for key, value in variables.items()})
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        env=env, capture_output=True, text=True, timeout=30,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    if result.returncode:
        raise RuntimeError(f"PowerShell probe failed: {result.stderr}")
    return result.stdout.strip()


def known_folder(name: str) -> Path:
    return Path(powershell(f"[Environment]::GetFolderPath('{name}')")).resolve()


def shortcut_target(shortcut: Path) -> Path:
    target = powershell(
        "$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:AIVIDEO_SMOKE_SHORTCUT); "
        "[Console]::Out.Write($s.TargetPath)", shortcut=str(shortcut)
    )
    return Path(target).resolve()


def version_info(path: Path) -> dict:
    output = powershell(
        "$v=(Get-Item -LiteralPath $env:AIVIDEO_SMOKE_FILE).VersionInfo; "
        "@{ProductName=$v.ProductName; FileDescription=$v.FileDescription; "
        "OriginalFilename=$v.OriginalFilename; CompanyName=$v.CompanyName; "
        "ProductVersion=$v.ProductVersion} | ConvertTo-Json -Compress",
        file=str(path),
    )
    return {key: value.strip() if isinstance(value, str) else value
            for key, value in json.loads(output).items()}


def registrations() -> list[dict]:
    found = []
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, UNINSTALL_ROOT) as parent:
        index = 0
        while True:
            try:
                name = winreg.EnumKey(parent, index)
            except OSError:
                break
            index += 1
            with winreg.OpenKey(parent, name) as key:
                try:
                    display = winreg.QueryValueEx(key, "DisplayName")[0]
                except OSError:
                    continue
                if display != PRODUCT_NAME:
                    continue
                values = {"key": name, "DisplayName": display}
                for field in ("InstallLocation", "DisplayVersion", "UninstallString"):
                    try:
                        values[field] = winreg.QueryValueEx(key, field)[0]
                    except OSError:
                        values[field] = ""
                found.append(values)
    return found


def run(command: list[str], log: Path, timeout: int = 300) -> None:
    result = subprocess.run(
        command + [f"/LOG={log}"], capture_output=True, text=True, timeout=timeout,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    if result.returncode:
        raise RuntimeError(
            f"Installer command failed ({result.returncode}): {result.stdout} {result.stderr}; log={log}"
        )


def minimal_environment(root: Path) -> dict[str, str]:
    env = {key: os.environ[key] for key in (
        "SystemRoot", "WINDIR", "COMSPEC", "PATHEXT", "NUMBER_OF_PROCESSORS",
        "PROCESSOR_ARCHITECTURE", "USERNAME",
    ) if key in os.environ}
    windir = Path(os.environ.get("WINDIR", "C:/Windows"))
    env.update({
        "PATH": str(windir / "System32") + os.pathsep + str(windir),
        "TEMP": str(root / "temp"), "TMP": str(root / "temp"),
        "LOCALAPPDATA": str(root / "localappdata"),
        "USERPROFILE": str(root / "profile"),
        "AIVIDEO_USER_DATA_DIR": str(root / "user data"),
        "QT_QPA_PLATFORM": "offscreen",
    })
    for name in ("temp", "localappdata", "profile", "user data"):
        (root / name).mkdir(parents=True, exist_ok=True)
    return env


def app_smoke(exe: Path, root: Path, project: Path, report_name: str) -> dict:
    env = minimal_environment(root)
    settings = root / "corrupt settings.json"
    settings.write_text("{invalid", encoding="utf-8")
    report = root / report_name
    command = [
        str(exe), "--smoke-test", "--smoke-quick", "--data-dir", str(project),
        "--settings-path", str(settings), "--smoke-report", str(report),
    ]
    result = subprocess.run(
        command, cwd=root / "temp", env=env, capture_output=True, timeout=180,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    if result.returncode or not report.is_file():
        raise RuntimeError(f"Installed app smoke failed: {result.returncode} {result.stderr.decode(errors='replace')}")
    payload = json.loads(report.read_text(encoding="utf-8"))
    if not payload.get("passed"):
        raise RuntimeError(f"Installed app smoke failed: {payload}")
    return payload


def uninstall(install_dir: Path, log: Path) -> None:
    uninstaller = install_dir / "unins000.exe"
    if not uninstaller.is_file():
        raise RuntimeError(f"Expected Inno uninstaller missing: {uninstaller}")
    run([str(uninstaller), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"], log)
    for _ in range(60):
        if not install_dir.exists() and not registrations():
            return
        time.sleep(0.5)
    raise RuntimeError("Uninstall left program files or Apps & Features registration")


def smoke(installer: Path, portable: Path, source: Path, evidence: Path) -> dict:
    if os.name != "nt":
        raise RuntimeError("Installer smoke requires Windows")
    installer, portable, source = installer.resolve(), portable.resolve(), source.resolve()
    if not installer.is_file() or not (portable / f"{EXECUTABLE_NAME}.exe").is_file():
        raise FileNotFoundError("Installer and matching portable executable are required")
    if registrations():
        raise RuntimeError("AI Video Flow is already installed for this user; refusing destructive smoke")
    start_link = known_folder("Programs") / f"{PRODUCT_NAME}.lnk"
    desktop_link = known_folder("DesktopDirectory") / f"{PRODUCT_NAME}.lnk"
    if start_link.exists() or desktop_link.exists():
        raise RuntimeError("Existing AI Video Flow shortcut found; refusing to overwrite it")

    temp_parent = Path(tempfile.gettempdir()).resolve()
    root = Path(tempfile.mkdtemp(prefix="AI-Video-Flow-Installer-", dir=temp_parent)).resolve()
    install_dir = root / "installed with space" / PRODUCT_NAME
    project = root / "smoke user project" / "Episode 01"
    result = {"schema": 1, "version": __version__, "passed": False, "install_mode": "per-user"}
    clean = False
    try:
        install_cmd = [str(installer), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART",
                       f"/DIR={install_dir}", "/TASKS=desktopicon"]
        run(install_cmd, root / "install.log")
        exe = install_dir / f"{EXECUTABLE_NAME}.exe"
        if not exe.is_file():
            raise RuntimeError("Installed executable missing")
        records = registrations()
        if len(records) != 1 or records[0]["DisplayVersion"] != __version__:
            raise RuntimeError(f"Apps & Features entry invalid: {records}")
        if not start_link.is_file() or shortcut_target(start_link) != exe.resolve():
            raise RuntimeError("Start Menu shortcut missing or wrong target")
        if not desktop_link.is_file() or shortcut_target(desktop_link) != exe.resolve():
            raise RuntimeError("Desktop shortcut missing or wrong target")
        exe_info = version_info(exe)
        setup_info = version_info(installer)
        if (exe_info.get("ProductName") != PRODUCT_NAME or
                exe_info.get("OriginalFilename") != f"{EXECUTABLE_NAME}.exe" or
                exe_info.get("CompanyName") not in ("", None) or
                setup_info.get("ProductName") != PRODUCT_NAME):
            raise RuntimeError(f"Windows metadata mismatch: exe={exe_info}, setup={setup_info}")
        first = app_smoke(exe, root, project, "first-launch.json")
        project_id = json.loads((project / "project.json").read_text(encoding="utf-8"))["project_id"]
        reopened = app_smoke(exe, root, project, "reopen.json")
        if json.loads((project / "project.json").read_text(encoding="utf-8"))["project_id"] != project_id:
            raise RuntimeError("Project identity changed on reopen")

        run(install_cmd, root / "same-version.log")
        if len(registrations()) != 1 or shortcut_target(start_link) != exe.resolve():
            raise RuntimeError("Same-version reinstall duplicated registration or broke shortcut")
        if len(list(install_dir.glob("unins*.exe"))) != 1:
            raise RuntimeError("Same-version reinstall duplicated uninstaller")
        if hashlib.sha256(exe.read_bytes()).digest() != hashlib.sha256(
                (portable / f"{EXECUTABLE_NAME}.exe").read_bytes()).digest():
            raise RuntimeError("Installed executable differs from portable executable")

        uninstall(install_dir, root / "uninstall.log")
        if start_link.exists() or desktop_link.exists() or not (project / "project.json").is_file():
            raise RuntimeError("Uninstall left shortcuts or deleted user project")
        run(install_cmd, root / "reinstall.log")
        exe = install_dir / f"{EXECUTABLE_NAME}.exe"
        after_reinstall = app_smoke(exe, root, project, "after-reinstall.json")
        if json.loads((project / "project.json").read_text(encoding="utf-8"))["project_id"] != project_id:
            raise RuntimeError("Existing project did not survive reinstall")
        uninstall(install_dir, root / "final-uninstall.log")
        if not (project / "project.json").is_file() or start_link.exists() or desktop_link.exists():
            raise RuntimeError("Final uninstall violated user data or shortcut boundary")

        result.update({
            "start_menu_target": f"{EXECUTABLE_NAME}.exe",
            "desktop_target": f"{EXECUTABLE_NAME}.exe", "apps_and_features": True,
            "install_path_with_spaces": True, "exe_metadata": exe_info,
            "installer_metadata": setup_info, "first_launch": first["passed"],
            "project_reopen": reopened["passed"], "same_version_reinstall": True,
            "uninstall_preserved_project": True, "reinstall_opened_project": after_reinstall["passed"],
            "final_uninstall_clean": True, "source_tree_isolated": all(
                str(source).casefold() not in path.casefold()
                for path in first["checks"]["module_locations"].values()
            ),
        })
        if not result["source_tree_isolated"]:
            raise RuntimeError("Installed app imported from source tree")
        clean = True
        result["passed"] = True
    finally:
        if registrations():
            # Only remove the installation created in this temporary directory.
            if (install_dir / "unins000.exe").is_file():
                try:
                    uninstall(install_dir, root / "emergency-uninstall.log")
                except Exception:
                    pass
        if not registrations() and not install_dir.exists() and root.parent == temp_parent:
            shutil.rmtree(root)
        elif not clean:
            result["cleanup_required"] = str(root)
        evidence.parent.mkdir(parents=True, exist_ok=True)
        evidence.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not result["passed"]:
        raise RuntimeError(f"Installer smoke failed: {result}")
    return result


if __name__ == "__main__":
    if len(sys.argv) != 5:
        raise SystemExit("Usage: installer_smoke.py SETUP_EXE PORTABLE_DIR SOURCE_DIR EVIDENCE_JSON")
    print(json.dumps(smoke(*(Path(value) for value in sys.argv[1:])), ensure_ascii=False, indent=2))
