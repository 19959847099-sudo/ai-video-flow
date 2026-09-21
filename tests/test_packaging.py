from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import os
import unittest

from app.integration import AppSettingsStore
from app.preparation.workspace import Workspace
from app.resources import (
    default_workspace_root, find_media_tool, media_tool, resource_path,
    session_file, user_data_root,
)


class PackagingContractTests(unittest.TestCase):
    def test_runtime_tool_override_and_strict_missing_are_local(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            filename = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
            tool = root / filename
            tool.write_bytes(b"fixture")
            with patch.dict(os.environ, {
                "AIVIDEO_MEDIA_BIN": str(root),
                "AIVIDEO_MEDIA_STRICT": "1",
            }, clear=False):
                self.assertEqual(Path(find_media_tool("ffmpeg")), tool.resolve())
            tool.unlink()
            with patch.dict(os.environ, {
                "AIVIDEO_MEDIA_BIN": str(root),
                "AIVIDEO_MEDIA_STRICT": "1",
            }, clear=False):
                self.assertIsNone(find_media_tool("ffmpeg"))
                with self.assertRaisesRegex(ValueError, "ffmpeg"):
                    media_tool("ffmpeg")

    def test_user_data_and_session_never_depend_on_cwd(self):
        with TemporaryDirectory() as temporary:
            configured = Path(temporary) / "user data"
            with patch.dict(os.environ, {"AIVIDEO_USER_DATA_DIR": str(configured)}):
                previous = Path.cwd()
                self.assertEqual(user_data_root(), configured.resolve())
                self.assertEqual(default_workspace_root().parent.name, "Projects")
                self.assertEqual(session_file().parent, configured.resolve())
                self.assertEqual(Path.cwd(), previous)

    def test_required_demo_resource_exists(self):
        self.assertTrue(resource_path(
            "app", "preparation", "demo_assets", "convenience-store-night.png"
        ).is_file())

    def test_settings_corruption_and_unknown_version_fall_back(self):
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "settings.json"
            path.write_bytes(b"\xff\xfe invalid")
            corrupted = AppSettingsStore(path)
            self.assertEqual(corrupted.values["layout"], "D")
            self.assertTrue(corrupted.error)
            path.write_text('{"version":999,"settings":{"layout":"C"}}', encoding="utf-8")
            unknown = AppSettingsStore(path)
            self.assertEqual(unknown.values["layout"], "D")
            self.assertTrue(unknown.error)

    def test_unicode_space_long_paths_and_unwritable_targets(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "\u6d4b\u8bd5\u9879\u76ee space" / ("segment-" * 10) / "\u7b2c\u4e00\u96c6"
            workspace = Workspace(project)
            self.assertTrue(workspace.manifest.is_file())

            blocked = root / "blocked"
            blocked.write_text("not a directory", encoding="utf-8")
            store = AppSettingsStore(blocked / "settings.json")
            with self.assertRaises(OSError):
                store.save(layout="D")
            with self.assertRaises(OSError):
                Workspace(blocked / "project")

    def test_packaging_contract_files_exist(self):
        root = Path(__file__).resolve().parents[1]
        for relative in (
            "packaging/windows/AIGCFlow.spec",
            "packaging/windows/launcher.py",
            "packaging/windows/THIRD_PARTY_NOTICES.md",
            "scripts/build_windows.ps1",
            "tools/archive_smoke.py",
            "requirements-build.txt",
        ):
            self.assertTrue((root / relative).is_file(), relative)


if __name__ == "__main__":
    unittest.main()
