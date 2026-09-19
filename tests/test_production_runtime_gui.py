from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from app.preparation.prompt_gui import PromptDialog
from app.preparation.workspace import Workspace

SCRIPT = '生成台/名称\n01/章节/雨夜\n001/入店\n动作：\n举起【红伞】。'


class RuntimeGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = TemporaryDirectory()
        self.workspace = Workspace(Path(self.temp.name) / 'project')
        self.workspace.apply(SCRIPT)
        self.chapter = self.workspace.script.chapters[0]
        self.shot = self.chapter.shots[0]
        self.host = QWidget(); self.host.workspace = self.workspace
        self.host.current_chapter = lambda: self.chapter
        self.host.refresh = lambda: None
        self.host.resize(1280, 840)

    def tearDown(self):
        self.host.close(); self.temp.cleanup()

    def test_generate_workspace_model_capability_queue_and_result(self):
        requirement = self.workspace.script.requirements[0]
        dialog = PromptDialog(self.host, self.shot.id, media='image', requirement_id=requirement.id)
        dialog.show(); QTest.qWait(30)
        self.assertEqual(dialog.model.currentData(), 'fixture-image-v1')
        self.assertIn('原生支持', dialog.capability_label.text())
        dialog.output_count.setValue(2)
        dialog.submit_generation()
        self.assertTrue(dialog.worker is not None)
        self.assertTrue(dialog.worker.isRunning() or self.workspace.state['runtime_jobs'])
        self.assertTrue(dialog.worker.wait(20000))
        self.app.processEvents()
        self.assertFalse(dialog.worker.isRunning())
        self.assertEqual(dialog.queue.count(), 1)
        job = dialog.selected_job()
        self.assertEqual(job.status, 'succeeded')
        self.assertEqual(len(job.candidate_ids), 2)
        self.assertTrue(all(self.workspace.state['candidates'][cid]['review_state'] == 'unreviewed'
                            for cid in job.candidate_ids))
        self.assertNotIn(requirement.id, self.workspace.state['bindings'])
        dialog.close()

    def test_model_switch_recomputes_without_mutating_project(self):
        dialog = PromptDialog(self.host, self.shot.id, media='video')
        dialog.show(); QTest.qWait(20)
        before = self.workspace.state['bindings'].copy()
        index = dialog.model.findData('fixture-video-text-v1')
        self.assertGreaterEqual(index, 0)
        dialog.model.setCurrentIndex(index)
        self.app.processEvents()
        self.assertTrue(dialog.generate_button.isEnabled())
        self.assertEqual(self.workspace.state['bindings'], before)
        self.assertFalse(self.workspace.state['runtime_jobs'])
        dialog.close()


if __name__ == '__main__': unittest.main()
