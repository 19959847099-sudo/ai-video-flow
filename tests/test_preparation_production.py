"""Focused V0.2 Missing → Candidate → Review → Bind tests."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from PIL import Image

from app.preparation.production import ProductionService
from app.preparation.workspace import Workspace, sha


SCRIPT = '片/名称\n01/章节/雨夜\n001/入店\n动作：\n【红伞】\n002/离店\n动作：\n【红伞】'


class ProductionLoopTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.root = Path(self.temp.name) / 'project'
        self.workspace = Workspace(self.root)
        self.assertTrue(self.workspace.apply(SCRIPT).valid)
        self.service = ProductionService(self.workspace)
        self.req = self.workspace.script.requirements[0]
        self.shot = self.workspace.script.chapters[0].shots[0]
        self.assertEqual(self.workspace.report()[0]['status'], 'missing')

    def tearDown(self):
        self.temp.cleanup()

    def picture(self, name, color):
        path = Path(self.temp.name) / name
        Image.new('RGB', (90, 64), color).save(path)
        return path

    def test_fixture_import_review_multi_green_bind_reopen_and_regenerate(self):
        job = self.service.create_job(self.req.id, self.shot.id)
        self.assertEqual(job.status, 'queued')
        self.assertEqual(self.service.poll_job(job.id).status, 'running')
        job = self.service.poll_job(job.id)
        self.assertEqual(job.status, 'completed')
        first = self.service.candidate(job.candidate_id)
        self.assertEqual(first.source_type, 'generated')
        self.assertEqual(first.review_state, 'unreviewed')
        self.assertTrue(self.service.available(first.id))
        self.assertEqual(sha(self.workspace.path(first.media_path)), first.sha256)
        self.assertIn('take_001_', first.media_path)
        self.assertEqual(self.workspace.report()[0]['status'], 'missing')
        with self.assertRaisesRegex(ValueError, 'Candidate'):
            self.workspace.bind(self.req.id, first.asset_id)

        second = self.service.import_candidate(self.req.id, self.shot.id, self.picture('other.png', '#8a6367'))
        self.assertEqual(second.take_number, 2)
        self.assertEqual(second.source_type, 'imported')
        self.assertIn('take_002_', second.media_path)
        self.service.review(first.id, 'red', '第一版不合适')
        self.service.review(second.id, 'yellow')
        self.assertEqual(self.workspace.report()[0]['status'], 'missing')
        self.service.review(first.id, 'green')
        self.service.review(second.id, 'green')
        self.assertEqual([c.review_state for c in self.service.candidates(self.req.id)], ['green', 'green'])
        self.assertIsNone(self.service.current(self.req.id))
        self.service.bind(second.id)
        self.assertEqual(self.service.current(self.req.id), second.id)
        self.assertEqual(self.workspace.report()[0]['status'], 'resolved')
        self.assertEqual(self.workspace.state['bindings'][self.req.id]['candidate_id'], second.id)
        self.service.bind(first.id)
        self.assertEqual(self.workspace.state['events'][-1]['previous']['candidate_id'], second.id)
        self.service.bind(second.id)

        restored = Workspace(self.root)
        service = ProductionService(restored)
        self.assertEqual(service.current(self.req.id), second.id)
        self.assertEqual(restored.report()[0]['status'], 'resolved')
        self.assertEqual(service.candidate(first.id).history[1]['to'], 'red')
        job2 = service.create_job(self.req.id, self.shot.id)
        service.poll_job(job2.id)
        third = service.candidate(service.poll_job(job2.id).candidate_id)
        self.assertEqual(third.take_number, 3)
        self.assertEqual(third.review_state, 'unreviewed')
        self.assertEqual(service.current(self.req.id), second.id)
        self.assertEqual(len(service.candidates(self.req.id)), 3)

        service.review(second.id, 'red')
        self.assertEqual(restored.report()[0]['status'], 'unresolved')
        self.assertEqual(service.current(self.req.id), second.id)
        service.unbind(self.req.id)
        self.assertEqual(restored.report()[0]['status'], 'missing')
        service.bind(first.id)
        self.assertEqual(restored.report()[0]['status'], 'resolved')
        self.assertTrue(any(e['kind'] == 'binding' and e.get('previous', {}).get('candidate_id') == second.id
                            for e in restored.state['events'] if e.get('previous')))

    def test_candidate_identity_survives_rename_and_changed_media_blocks_binding(self):
        candidate = self.service.import_candidate(self.req.id, self.shot.id, self.picture('source.png', 'red'))
        self.service.review(candidate.id, 'green')
        self.service.bind(candidate.id)
        source = self.workspace.path(candidate.media_path)
        moved = source.with_name('renamed.png')
        source.rename(moved)
        self.workspace.scan()
        self.assertEqual(self.service.candidate(candidate.id).media_path,
                         moved.relative_to(self.root).as_posix())
        self.assertEqual(self.workspace.report()[0]['status'], 'resolved')
        self.assertEqual(self.service.current(self.req.id), candidate.id)
        Image.new('RGB', (90, 64), 'blue').save(moved)
        self.workspace.scan()
        self.assertEqual(self.workspace.report()[0]['status'], 'changed')
        self.assertFalse(self.service.available(candidate.id))
        self.assertTrue(self.service.preview_path(candidate.id).is_file())
        with self.assertRaises(ValueError):
            self.service.bind(candidate.id)

    def test_queued_fixture_job_resumes_after_reopening_project(self):
        job = self.service.create_job(self.req.id, self.shot.id)
        self.assertEqual(self.service.poll_job(job.id).status, 'running')
        restored = Workspace(self.root)
        service = ProductionService(restored)
        result = service.poll_job(job.id)
        self.assertEqual(result.status, 'completed')
        self.assertTrue(service.available(result.candidate_id))
        self.assertEqual(restored.report()[0]['status'], 'missing')

    def test_audio_and_video_import_share_candidate_review_binding(self):
        repo = Path(__file__).resolve().parents[1]
        source = ('片/名称\n01/章节/雨夜\n001/镜头\n'
                  '人物/-/-/低声\n镜头：\n【门内跟拍】')
        self.assertTrue(self.workspace.apply(source).valid)
        service = ProductionService(self.workspace)
        shot = self.workspace.script.chapters[0].shots[0]
        files = {
            'audio': repo / 'examples/audio-fixtures/FIXTURE-tone.wav',
            'video': next((repo / 'evidence/UI-Final/gui-data/results').glob('*/video.mp4')),
        }
        for req in self.workspace.script.requirements:
            if req.media not in files:
                continue
            candidate = service.import_candidate(req.id, shot.id, files[req.media])
            self.assertEqual(candidate.media, req.media)
            self.assertEqual(candidate.review_state, 'unreviewed')
            service.review(candidate.id, 'green')
            service.bind(candidate.id)
            report = next(r for r in self.workspace.report() if r['requirement']['id'] == req.id)
            self.assertEqual(report['status'], 'resolved')
            self.assertEqual(service.current(req.id), candidate.id)
        self.assertEqual({c['media'] for c in self.workspace.state['candidates'].values()},
                         {'audio', 'video'})


if __name__ == '__main__':
    unittest.main()
