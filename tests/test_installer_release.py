"""Release identity, installer script and checksum contracts (offline tests)."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json
import os
import subprocess
import sys
import unittest

from PIL import Image

from app.resources import user_data_root
from app.version import EXECUTABLE_NAME, LEGACY_USER_DATA_DIR, PRODUCT_NAME, __version__
from tools.release_manifest import artifact_names, create_manifest

ROOT = Path(__file__).resolve().parents[1]


class InstallerReleaseTests(unittest.TestCase):
    def test_public_identity_keeps_legacy_user_data(self):
        self.assertEqual(PRODUCT_NAME, "AI Video Flow")
        self.assertEqual(EXECUTABLE_NAME, "AIVideoFlow")
        self.assertEqual(LEGACY_USER_DATA_DIR, "AI Video Workflow")
        with TemporaryDirectory() as temporary:
            with patch.dict(os.environ, {"LOCALAPPDATA": temporary}, clear=False):
                self.assertEqual(user_data_root(), (Path(temporary) / LEGACY_USER_DATA_DIR).resolve())

    def test_owned_icon_has_windows_sizes(self):
        path = ROOT / "packaging" / "windows" / "AI-Video-Flow.ico"
        with Image.open(path) as icon:
            self.assertTrue({(16, 16), (32, 32), (48, 48), (256, 256)} <= icon.info["sizes"])

    def test_inno_script_is_per_user_and_data_preserving(self):
        script = (ROOT / "packaging" / "windows" / "AI-Video-Flow.iss").read_text(encoding="utf-8")
        for contract in (
            '#define AppIdValue "{{42ede151-81cb-5573-8ee0-547ad09a3c83}"',
            "AppId={#AppIdValue}",
            "AppName={#AppName}", "PrivilegesRequired=lowest",
            "DefaultDirName={localappdata}\\Programs\\AI Video Flow",
            'Name: "desktopicon"', 'Name: "{userprograms}\\{#AppName}"',
            'Name: "{userdesktop}\\{#AppName}"',
            "UninstallDisplayIcon={app}\\{#AppExe}",
        ):
            self.assertIn(contract, script)
        self.assertNotIn("[UninstallDelete]", script)
        self.assertNotIn("AI Video Workflow", script)
        self.assertTrue((ROOT / "scripts" / "build_windows_installer.ps1").is_file())

    def test_windows_metadata_does_not_invent_publisher(self):
        with TemporaryDirectory() as temporary:
            target = Path(temporary) / "version.txt"
            subprocess.run(
                [sys.executable, str(ROOT / "tools" / "write_windows_version.py"), str(target)],
                check=True, capture_output=True,
            )
            text = target.read_text(encoding="utf-8")
            self.assertIn("AI Video Flow", text)
            self.assertIn("AIVideoFlow.exe", text)
            self.assertNotIn("CompanyName", text)
            self.assertNotIn("Local Creator Tools", text)

    def test_release_names_and_checksums_are_deterministic(self):
        portable, installer = artifact_names()
        self.assertEqual(portable, f"AI-Video-Flow-{__version__}-windows-x64.zip")
        self.assertEqual(installer, f"AI-Video-Flow-{__version__}-windows-x64-setup.exe")
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            release = root / f"v{__version__}"
            release.mkdir()
            evidence = root / "evidence.json"
            with self.assertRaises(FileNotFoundError):
                create_manifest(release, evidence)
            (release / portable).write_bytes(b"portable fixture")
            (release / installer).write_bytes(b"installer fixture")
            result = create_manifest(release, evidence)
            first = (release / "SHA256SUMS.txt").read_bytes()
            self.assertEqual(result["version"], __version__)
            self.assertEqual(len(result["artifacts"]), 2)
            self.assertEqual([item["name"] for item in result["artifacts"]], [portable, installer])
            self.assertEqual(len(first.decode("ascii").splitlines()), 2)
            create_manifest(release, evidence)
            self.assertEqual((release / "SHA256SUMS.txt").read_bytes(), first)
            self.assertEqual(json.loads(evidence.read_text(encoding="utf-8")), result)


if __name__ == "__main__":
    unittest.main()
