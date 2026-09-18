"""Focused Missing Requirement resolution rules; no provider calls."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from PIL import Image

from app.preparation.production import ProductionService
from app.preparation.workspace import Workspace


SCRIPT = '片/名称\n01/章节/雨夜\n001/入店\n动作：\n【红伞】'


class MissingResolutionTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.root = Path(self.temp.name) / 'project'
        self.workspace = Workspace(self.root)
        self.assertTrue(self.workspace.apply(SCRIPT).valid)
        self.req = self.workspace.script.requirements[0]
        self.shot = self.workspace.script.chapters[0].shots[0]

    def tearDown(self):
        self.temp.cleanup()

    def test_free_preserves_requirement_without_media_and_restores_missing_after_restart(self):
        self.workspace.set_reference_required(self.req.id, False)
        row = self.workspace.report()[0]
        self.assertEqual(row['status'], 'free')
        self.assertIsNone(row['asset'])
        self.assertIsNone(row['binding'])
        self.assertEqual(self.workspace.state['assets'], {})
        self.assertEqual(self.workspace.state['candidates'], {})
        self.assertEqual(self.workspace.state['bindings'], {})
        self.assertEqual(self.workspace.chapter_status(self.workspace.script.chapters[0].id)['free'], 1)
        self.assertTrue(self.workspace.chapter_status(self.workspace.script.chapters[0].id)['ready'])
        self.assertEqual(self.workspace.script.requirements[0].name, '红伞')

        reopened = Workspace(self.root)
        self.assertEqual(reopened.report()[0]['status'], 'free')
        reopened.set_reference_required(self.req.id, True)
        self.assertEqual(reopened.report()[0]['status'], 'missing')
        self.assertFalse(reopened.chapter_status(reopened.script.chapters[0].id)['ready'])
        self.assertEqual([e['current'] for e in reopened.state['events'] if e['kind'] == 'reference_decision'],
                         ['not_required', 'required'])

    def test_free_import_enters_existing_candidate_review_and_binding(self):
        self.workspace.set_reference_required(self.req.id, False)
        source = Path(self.temp.name) / 'umbrella.png'
        Image.new('RGB', (64, 64), 'red').save(source)
        service = ProductionService(self.workspace)
        candidate = service.import_candidate(self.req.id, self.shot.id, source)
        self.assertEqual(self.workspace.report()[0]['status'], 'missing')
        self.assertNotIn(self.req.id, self.workspace.state['reference_decisions'])
        self.assertEqual(candidate.review_state, 'unreviewed')
        self.assertIsNone(service.current(self.req.id))
        service.review(candidate.id, 'green')
        self.assertEqual(self.workspace.report()[0]['status'], 'missing')
        service.bind(candidate.id)
        self.assertEqual(self.workspace.report()[0]['status'], 'resolved')
        with self.assertRaisesRegex(ValueError, '未绑定'):
            self.workspace.set_reference_required(self.req.id, False)
        self.assertTrue(self.workspace.chapter_status(self.workspace.script.chapters[0].id)['ready'])

    def test_free_does_not_auto_bind_matching_file_and_identity_survives_script_reparse(self):
        self.workspace.set_reference_required(self.req.id, False)
        target = self.root / 'library' / 'prop' / '红伞.png'
        Image.new('RGB', (60, 60), 'blue').save(target)
        self.workspace.scan()
        self.assertEqual(self.workspace.report()[0]['status'], 'free')
        self.assertNotIn(self.req.id, self.workspace.state['bindings'])
        self.workspace.apply('片/名称\n01/章节/雨夜\n001/入店\n动作：\n【红伞】在门边。')
        self.assertEqual(self.workspace.report()[0]['status'], 'free')
        self.workspace.apply('片/名称\n01/章节/雨夜\n001/入店\n动作：\n没有固定物件。')
        self.assertEqual(self.workspace.report(), [])
        self.workspace.apply(SCRIPT)
        self.assertEqual(self.workspace.report()[0]['status'], 'free')
        self.workspace.set_reference_required(self.req.id, True)
        self.assertEqual(self.workspace.report()[0]['status'], 'missing')
        asset = next(iter(self.workspace.state['assets'].values()))
        self.workspace.bind(self.req.id, asset['id'])
        self.assertEqual(self.workspace.report()[0]['status'], 'resolved')


if __name__ == '__main__':
    unittest.main()
