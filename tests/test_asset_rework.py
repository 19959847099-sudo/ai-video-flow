"""Focused Asset Rework Entry tests around Current, Candidate and Prompt stale."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from PIL import Image

from app.preparation.prompt import create_draft, get_draft, save_draft
from app.preparation.production import ProductionService
from app.preparation.workspace import Workspace


SCRIPT = '片/名称\n01/章节/雨夜\n001/进门\n动作：\n拿起【红伞】。'


class ReworkSemanticsTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.root = Path(self.temp.name) / 'project'
        self.workspace = Workspace(self.root)
        self.assertTrue(self.workspace.apply(SCRIPT).valid)
        self.req = self.workspace.script.requirements[0]
        self.shot = self.workspace.script.chapters[0].shots[0]
        self.service = ProductionService(self.workspace)

    def tearDown(self):
        self.temp.cleanup()

    def picture(self, name, color):
        path = Path(self.temp.name) / name
        Image.new('RGB', (96, 72), color).save(path)
        return path

    def test_append_review_switch_and_reopen_keep_old_current_until_explicit_bind(self):
        old = self.service.import_candidate(self.req.id, self.shot.id, self.picture('old.png', 'red'))
        self.service.review(old.id, 'green')
        self.service.bind(old.id)
        draft = create_draft(self.workspace, self.shot.id, 'video')
        save_draft(self.workspace, self.shot.id, 'video', None, draft['text'] + '\n人工保留段落')
        old_binding = dict(self.workspace.state['bindings'][self.req.id])
        new = self.service.import_candidate(self.req.id, self.shot.id, self.picture('new.png', 'blue'))
        self.assertEqual(new.review_state, 'unreviewed')
        for state in ('red', 'yellow', 'green'):
            self.assertEqual(self.workspace.chapter_status(self.workspace.script.chapters[0].id)['ready'], True)
            self.assertEqual(self.workspace.state['bindings'][self.req.id], old_binding)
            self.assertFalse(get_draft(self.workspace, self.shot.id, 'video')[2])
            self.service.review(new.id, state)
        self.assertEqual({c.review_state for c in self.service.candidates(self.req.id)}, {'green'})
        self.assertEqual(self.service.current(self.req.id), old.id)
        self.assertEqual(self.workspace.state['bindings'][self.req.id], old_binding)
        self.assertFalse(get_draft(self.workspace, self.shot.id, 'video')[2])
        self.service.bind(new.id)
        self.assertEqual(self.service.current(self.req.id), new.id)
        self.assertEqual(self.service.candidate(old.id).review_state, 'green')
        self.assertTrue(self.service.available(old.id))
        self.assertTrue(get_draft(self.workspace, self.shot.id, 'video')[2])
        self.assertIn('人工保留段落', get_draft(self.workspace, self.shot.id, 'video')[0]['text'])
        restored = Workspace(self.root)
        self.assertEqual(ProductionService(restored).current(self.req.id), new.id)
        self.assertEqual(len(restored.state['candidates']), 2)
        self.assertTrue(get_draft(restored, self.shot.id, 'video')[2])
        self.assertEqual(restored.state['events'][-1]['previous']['candidate_id'], old.id)


class ReworkGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_ready_entry_routes_to_targeted_prompt_without_provider_or_state_change(self):
        from PySide6.QtTest import QTest
        from app.preparation_gui import PreparationWindow, ApiCapabilityDialog
        from app.preparation.prompt_gui import PromptDialog

        with TemporaryDirectory() as tmp:
            root = Path(tmp) / 'project'
            workspace = Workspace(root)
            workspace.apply(SCRIPT)
            service = ProductionService(workspace)
            req = workspace.script.requirements[0]
            shot = workspace.script.chapters[0].shots[0]
            image = Path(tmp) / 'current.png'
            Image.new('RGB', (96, 72), 'red').save(image)
            current = service.import_candidate(req.id, shot.id, image)
            service.review(current.id, 'green')
            service.bind(current.id)
            window = PreparationWindow(root)
            window.show()
            try:
                for _ in range(450):
                    QTest.qWait(20)
                    if window.production_stages[0].isEnabled():
                        break
                report = next(r for r in window.workspace.report() if r['requirement']['id'] == req.id)
                window.select_media(report)
                self.assertTrue(window.rework_bar.isVisible())
                self.assertTrue(window.rework_generate_button.isVisible())
                self.assertTrue(window.rework_import_button.isVisible())
                self.assertFalse(window.resolution_bar.isVisible())
                captured = []
                def inspect(dialog):
                    captured.append((dialog.media, dialog.shot_id, dialog.current_requirement,
                                     dialog.rework_context, dialog.provider_hint.isHidden()))
                    with patch.object(ApiCapabilityDialog, 'exec', lambda api: captured.append(api.capability)):
                        dialog.show_add_api()
                    return 0
                before = dict(window.workspace.state['bindings'][req.id])
                with patch.object(PromptDialog, 'exec', inspect):
                    window.rework_generate_button.click()
                self.assertEqual(captured, [('image', shot.id, req.id, True, False), 'image'])
                self.assertEqual(window.workspace.state['bindings'][req.id], before)
                self.assertEqual(len(window.workspace.state['candidates']), 1)
                with patch.object(window, 'open_production') as route:
                    window.rework_import_button.click()
                    route.assert_called_once_with(req.id, import_now=True)
                self.assertEqual(window.workspace.state['bindings'][req.id], before)
                window.workspace.state['is_example'] = True
                with patch.object(window, 'open_production') as fixture_route:
                    window.rework_generate_button.click()
                    fixture_route.assert_called_once_with(req.id)
                current_file = window.workspace.path(window.workspace.state['assets'][current.asset_id]['path'])
                Image.new('RGB', (96, 72), 'blue').save(current_file)
                window.workspace.scan()
                window.refresh()
                changed = next(r for r in window.workspace.report() if r['requirement']['id'] == req.id)
                self.assertEqual(changed['status'], 'changed')
                self.assertFalse(window.rework_bar.isVisible())
            finally:
                window.close()
                window.deleteLater()
                QTest.qWait(60)


if __name__ == '__main__':
    unittest.main()
