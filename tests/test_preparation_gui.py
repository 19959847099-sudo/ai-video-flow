"""Representative Qt paths, using real widgets and isolated project files."""
import os
import time
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from PIL import Image
from PySide6.QtCore import Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton, QFileDialog

from app.preparation_gui import PreparationWindow, MappingDialog
from app.preparation.script import requirement_id


class PreparationGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.window = PreparationWindow(self.root / 'project')
        self.window.show()
        self.wait_scan()

    def tearDown(self):
        if self.window:
            self.wait_scan()
            self.window.close()
            self.window.deleteLater()
            QTest.qWait(30)
        self.temp.cleanup()

    def wait_scan(self):
        for _ in range(500):
            QTest.qWait(20)
            time.sleep(0.005)  # Let Python scan workers run while Qt test pumps events.
            if not self.window.worker or not self.window.worker.isRunning():
                QTest.qWait(20)
                return
        self.fail('scan did not finish')

    def click(self, widget):
        QTest.mouseClick(widget, Qt.MouseButton.LeftButton)
        QTest.qWait(30)

    def test_import_script_import_media_ready_and_restart(self):
        source = '测试准备/名称\n01/章节/共享参照\n001/进入\n【人/-/衣】/低声\n镜头：\n【跟拍】\n002/离开\n【人/-/衣】/-\n动作：\n离开。'
        script = self.root / 'script.md'
        script.write_text(source, encoding='utf-8')
        import_button = next(b for b in self.window.findChildren(QPushButton) if b.text() == '＋  导入规范剧本')
        with patch.object(QFileDialog, 'getOpenFileName', return_value=(str(script), '')):
            self.click(import_button)
        self.assertEqual(self.window.shots.count(), 2)
        self.assertEqual(len(self.window.workspace.report()), 3)
        self.assertFalse(self.window.workspace.chapter_status(self.window.chapter_id)['ready'])
        image = self.root / 'external.png'
        Image.new('RGB', (120, 80), '#526654').save(image)
        repo = Path(__file__).resolve().parents[1]
        video = next((repo / 'evidence' / 'UI-Final' / 'gui-data' / 'results').glob('*/video.mp4'))
        audio = repo / 'examples' / 'audio-fixtures' / 'FIXTURE-tone.wav'
        files = {'image': image, 'audio': audio, 'video': video}
        self.window.filter.setCurrentIndex(1)
        for _ in range(3):
            report = next(r for r in self.window.workspace.report() if r['status'] == 'missing')
            action = self.window.findChild(QPushButton, 'map_' + report['requirement']['id'])
            self.assertIsNotNone(action)
            errors = []
            def import_in_dialog():
                try:
                    dialog = self.app.activeModalWidget()
                    self.assertIsInstance(dialog, MappingDialog)
                    with patch.object(QFileDialog, 'getOpenFileName', return_value=(str(files[report['requirement']['media']]), '')):
                        dialog.import_file()
                except Exception as exc:
                    errors.append(exc)
                    self.app.activeModalWidget().reject()
            QTimer.singleShot(0, import_in_dialog)
            action.click()
            self.assertFalse(errors, errors)
        self.assertTrue(self.window.workspace.chapter_status(self.window.chapter_id)['ready'])
        self.assertIn('READY', self.window.ready_label.text())
        self.window.shots.setCurrentRow(1)
        selected = self.window.shot_id
        project = self.window.workspace.root
        self.window.close()
        self.window.deleteLater()
        QTest.qWait(20)
        self.window = PreparationWindow(project)
        self.window.show()
        self.wait_scan()
        self.assertEqual(self.window.shot_id, selected)
        self.assertEqual(self.window.editor.toPlainText(), source)
        self.assertTrue(self.window.workspace.chapter_status(self.window.chapter_id)['ready'])
        self.assertEqual({r['status'] for r in self.window.workspace.report()}, {'resolved'})

    def test_invalid_draft_error_location_and_recovery(self):
        valid = '片/名称\n01/集数\n001/物件\n动作：\n【红伞】'
        self.window.editor.setPlainText(valid)
        self.click(self.window.apply_button)
        revision = self.window.workspace.script.revision
        self.window.editor.setPlainText(valid.replace('【红伞】', '【红伞'))
        self.click(self.window.apply_button)
        self.assertTrue(self.window.diagnostics.isVisible())
        self.assertTrue(self.window.draft_banner.isVisible())
        self.assertEqual(self.window.workspace.script.revision, revision)
        item = self.window.diagnostics.item(0)
        self.window.diagnostics.itemClicked.emit(item)
        self.assertEqual(self.window.editor.textCursor().blockNumber() + 1, 5)
        for action in self.window.findChildren(QPushButton):
            if action.property('mappingAction'): self.assertFalse(action.isEnabled())
        project = self.window.workspace.root
        self.window.close()
        self.window.deleteLater()
        QTest.qWait(20)
        self.window = PreparationWindow(project)
        self.window.show()
        self.wait_scan()
        self.assertIn('【红伞', self.window.editor.toPlainText())
        self.assertFalse(self.window.workspace.draft_result.valid)
        self.window.editor.setPlainText(valid)
        self.click(self.window.apply_button)
        self.assertFalse(self.window.diagnostics.isVisible())
        self.assertFalse(self.window.draft_banner.isVisible())

    def test_ambiguity_and_changed_version_require_explicit_choice(self):
        self.window.editor.setPlainText('片/名称\n01/集数\n001/伞\n动作：\n【红伞】')
        self.click(self.window.apply_button)
        folder = self.window.workspace.root / 'library' / 'prop'
        for name, color in [('红伞.png', 'red'), ('红伞.jpg', 'blue')]:
            Image.new('RGB', (30, 30), color).save(folder / name)
        self.click(self.window.scan_button)
        self.wait_scan()
        report = self.window.workspace.report()[0]
        self.assertEqual(report['status'], 'unresolved')
        dialog = MappingDialog(self.window, report)
        dialog.show()
        dialog.choices.setCurrentRow(0)
        aid = dialog.choices.currentItem().data(Qt.ItemDataRole.UserRole)
        self.click(dialog.confirm)
        self.window.refresh()
        self.assertTrue(self.window.workspace.chapter_status(self.window.chapter_id)['ready'])
        asset = self.window.workspace.state['assets'][aid]
        Image.new('RGB', (30, 30), 'green').save(self.window.workspace.path(asset['path']))
        self.click(self.window.scan_button)
        self.wait_scan()
        report = self.window.workspace.report()[0]
        self.assertEqual(report['status'], 'changed')
        self.assertFalse(self.window.workspace.chapter_status(self.window.chapter_id)['ready'])
        self.assertEqual(self.window.workspace.state['events'][-1]['shots'], [self.window.workspace.script.chapters[0].shots[0].id])
        dialog = MappingDialog(self.window, report)
        dialog.show()
        self.click(dialog.confirm)
        self.window.refresh()
        self.assertTrue(self.window.workspace.chapter_status(self.window.chapter_id)['ready'])

    def test_open_project_persists_launcher_and_restores_cursor(self):
        import json
        self.window.session_path = self.root / 'session.json'
        other = self.root / 'other-project'
        self.window.open_workspace(other)
        self.wait_scan()
        self.assertEqual(json.loads((self.root / 'session.json').read_text(encoding='utf-8'))['last_project'], str(other.resolve()))
        self.window.editor.setPlainText('片/名称\n01/集数\n001/镜头\n动作：\n静止。')
        self.click(self.window.apply_button)
        self.window.editor.go_line(5)
        cursor = self.window.editor.textCursor().position()
        self.window.save_draft()
        self.window.open_workspace(self.root / 'project')
        self.wait_scan()
        self.window.open_workspace(other)
        self.wait_scan()
        self.assertEqual(self.window.editor.textCursor().position(), cursor)

    def test_workspace_lock_and_compact_primary_controls(self):
        with self.assertRaisesRegex(ValueError, '另一个窗口'):
            duplicate = PreparationWindow(self.window.workspace.root)
        self.window.resize(1100, 720)
        QTest.qWait(50)
        for widget in [self.window.apply_button, self.window.scan_button, self.window.open_button, self.window.editor]:
            self.assertTrue(widget.isVisible())
            point = widget.mapTo(self.window, widget.rect().center())
            self.assertTrue(self.window.rect().contains(point))


if __name__ == '__main__': unittest.main()
