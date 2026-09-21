"""Focused Chapter Finishing tests over explicit V0.2 Current bindings."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import builtins
from unittest.mock import patch
import re
import subprocess

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

import opentimelineio as otio
from PIL import Image

from app.preparation.finishing import ChapterFinishing
from app.preparation.production import ProductionService
from app.preparation.production_gui import ReviewDot
from app.preparation.prompt import create_draft, get_draft
from app.preparation.workspace import Workspace, sha
from app.rough_cut import probe


SCRIPT = '测试章节/名称\n01/章节/夜行\n001/门前\n动作：\n抬头。\n002/街角\n动作：\n转身。\n003/路灯\n动作：\n停下。'
FIXTURES = sorted((Path(__file__).resolve().parents[1] / 'evidence/A-04/smoke-data/results').glob('*/video.mp4'))[:4]


class ChapterFinishingTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.workspace = Workspace(Path(self.temp.name) / 'project')
        self.assertTrue(self.workspace.apply(SCRIPT).valid)
        self.chapter = self.workspace.script.chapters[0]
        self.service = ProductionService(self.workspace)
        self.finishing = ChapterFinishing(self.workspace, self.chapter.id)

    def tearDown(self):
        self.temp.cleanup()

    def add(self, shot_index, fixture_index, review='green', bind=False):
        shot = self.chapter.shots[shot_index]
        candidate = self.service.import_shot_candidate(shot.id, FIXTURES[fixture_index])
        if review != 'unreviewed':
            self.service.review(candidate.id, review)
        if bind:
            self.service.bind_shot(candidate.id)
        return candidate

    def ready(self):
        return [self.add(i, i, bind=True) for i in range(3)]

    def test_script_order_and_missing_current_are_explicit(self):
        self.assertEqual([s['shot_id'] for s in self.finishing.segments()],
                         [shot.id for shot in self.chapter.shots])
        self.assertEqual(self.finishing.resolve()['status'], 'Blocked')
        alternate = self.add(0, 0)
        self.assertFalse(self.finishing.resolve()['clips'])
        with self.assertRaises(ValueError):
            self.service.bind_shot(self.add(1, 1, review='yellow').id)
        self.service.bind_shot(alternate.id)
        resolved = self.finishing.resolve()
        self.assertEqual([c['candidate_id'] for c in resolved['clips']], [alternate.id])
        self.assertEqual(len(resolved['errors']), 2)

    def test_missing_bound_media_blocks_locally_without_crashing(self):
        originals = self.ready()
        self.workspace.path(originals[0].media_path).unlink()
        resolved = self.finishing.resolve()
        self.assertEqual(resolved['status'], 'Blocked')
        self.assertTrue(any('不存在' in message or '不可用' in message
                            for message in resolved['errors']))
        self.assertEqual(len(resolved['clips']), 2)

    def test_otio_unavailable_only_blocks_handoff(self):
        self.ready()
        preview = self.finishing.preview()
        original_import = builtins.__import__

        def without_otio(name, *args, **kwargs):
            if name == 'opentimelineio':
                raise ModuleNotFoundError('simulated missing OpenTimelineIO')
            return original_import(name, *args, **kwargs)

        with patch('builtins.__import__', side_effect=without_otio):
            with self.assertRaisesRegex(ModuleNotFoundError, 'simulated missing'):
                self.finishing.handoff()
        self.assertEqual(self.finishing.preview(), preview)
    def test_current_not_latest_and_prompt_stale_after_explicit_switch(self):
        first = self.add(0, 0, bind=True)
        shot = self.chapter.shots[0]
        draft = create_draft(self.workspace, shot.id, 'video')
        second = self.add(0, 1)
        self.assertEqual(self.finishing.resolve()['clips'][0]['candidate_id'], first.id)
        self.assertEqual(self.service.current_shot(shot.id), first.id)
        self.assertFalse(get_draft(self.workspace, shot.id, 'video')[2])
        self.service.bind_shot(second.id)
        self.assertEqual(self.finishing.resolve()['clips'][0]['candidate_id'], second.id)
        record, _, stale = get_draft(self.workspace, shot.id, 'video')
        self.assertTrue(stale)
        self.assertEqual(record['text'], draft['text'])
        self.assertTrue(self.service.available(first.id))

    def test_edits_restore_without_changing_production_truth(self):
        originals = self.ready()
        segment = self.finishing.segments()[0]
        before = sha(self.workspace.path(originals[0].media_path))
        self.finishing.update(segment['id'], trim_in=.4, trim_out=2.2, volume=.55, mute=True)
        new_segment = self.finishing.split(segment['id'], 1.3)
        self.finishing.move(new_segment, 2)
        self.finishing.update(self.finishing.segments()[1]['id'], enabled=False)
        self.finishing.remove(self.finishing.segments()[1]['id'])
        selected = self.finishing.selected()
        restored = ChapterFinishing(Workspace(self.workspace.root), self.chapter.id)
        self.assertEqual(restored.segments(), self.finishing.segments())
        self.assertEqual(restored.selected(), selected)
        self.assertEqual([s.id for s in restored.chapter().shots],
                         [s.id for s in self.chapter.shots])
        self.assertEqual(sha(self.workspace.path(originals[0].media_path)), before)
        self.assertEqual(self.service.current_shot(self.chapter.shots[0].id), originals[0].id)
        self.assertEqual(restored.resolve()['status'], 'Ready')

    def test_reference_binding_change_marks_assembly_stale(self):
        with TemporaryDirectory() as temp:
            workspace = Workspace(Path(temp) / 'project')
            self.assertTrue(workspace.apply('片/名称\n01/章节/章\n001/镜头\n动作：\n举起【红伞】。').valid)
            chapter = workspace.script.chapters[0]
            shot = chapter.shots[0]
            service = ProductionService(workspace)
            candidate = service.import_shot_candidate(shot.id, FIXTURES[0])
            service.review(candidate.id, 'green')
            service.bind_shot(candidate.id)
            finishing = ChapterFinishing(workspace, chapter.id)
            before = finishing.resolve()['fingerprint']
            finishing.state['preview'] = {'fingerprint': before}
            workspace._save()
            asset = workspace.path('library/prop/红伞.png')
            asset.parent.mkdir(parents=True, exist_ok=True)
            Image.new('RGB', (64, 64), '#ab4d43').save(asset)
            workspace.scan()
            resolved = finishing.resolve()
            self.assertNotEqual(resolved['fingerprint'], before)
            self.assertTrue(resolved['stale'])

    def test_invalid_trim_blocks_and_does_not_save(self):
        self.ready()
        segment = self.finishing.segments()[0]
        with self.assertRaisesRegex(ValueError, 'Trim'):
            self.finishing.update(segment['id'], trim_in=2.7, trim_out=1.0)
        with self.assertRaisesRegex(ValueError, 'Trim'):
            self.finishing.update(segment['id'], trim_in=2.7, trim_out=4.0)
        self.assertEqual(self.finishing.segments()[0]['trim_in'], 0)
        self.assertEqual(ChapterFinishing(Workspace(self.workspace.root), self.chapter.id).segments()[0]['trim_out'], None)

    def test_audio_volume_and_mute_are_rendered(self):
        shot = self.chapter.shots[0]
        source = Path(__file__).resolve().parents[1] / 'evidence/V02-chapter-finishing/fixture-audio-video.mp4'
        candidate = self.service.import_shot_candidate(shot.id, source)
        self.service.review(candidate.id, 'green')
        self.service.bind_shot(candidate.id)
        for segment in self.finishing.segments()[1:]:
            self.finishing.update(segment['id'], enabled=False)
        segment = self.finishing.segments()[0]
        self.finishing.update(segment['id'], volume=.5)
        audible = self.finishing.preview()
        self.finishing.update(segment['id'], mute=True)
        silent = self.finishing.preview()
        def maximum(path):
            result = subprocess.run(['ffmpeg', '-hide_banner', '-v', 'info', '-i', str(path),
                                     '-vn', '-af', 'volumedetect', '-f', 'null', 'NUL'],
                                    capture_output=True, text=True, timeout=30)
            return float(re.search(r'max_volume: (-?\d+(?:\.\d+)?) dB', result.stderr).group(1))
        self.assertLess(maximum(silent), maximum(audible)-30)
        self.assertTrue(probe(silent, 'audio'))

    def test_real_preview_output_and_portable_otio(self):
        originals = self.ready()
        segments = self.finishing.segments()
        self.finishing.move(segments[2]['id'], -1)
        self.finishing.update(segments[0]['id'], trim_in=.5, trim_out=2.0)
        self.finishing.update(segments[1]['id'], enabled=False)
        preview = self.finishing.preview()
        output = self.finishing.output()
        self.assertTrue(preview.is_file())
        self.assertTrue(output.is_file())
        self.assertAlmostEqual(probe(preview, 'video')['duration'], 4.5, delta=.15)
        self.assertAlmostEqual(probe(output, 'video')['duration'], 4.5, delta=.15)
        self.assertEqual(probe(output, 'audio')['channels'], 2)
        package = self.finishing.handoff()
        timeline = otio.adapters.read_from_file(str(package / 'timeline.otio'))
        self.assertEqual([c.metadata['aigc']['shot_id'] for c in timeline.video_tracks()[0]],
                         [self.chapter.shots[0].id, self.chapter.shots[2].id])
        self.assertAlmostEqual(timeline.video_tracks()[0][0].source_range.start_time.to_seconds(), .5)
        self.assertTrue((package / 'chapter-output.mp4').is_file())
        self.assertTrue(all((package / c.media_reference.target_url).is_file()
                            for c in timeline.video_tracks()[0]))
        self.assertEqual([self.service.current_shot(s.id) for s in self.chapter.shots],
                         [c.id for c in originals])
        self.assertEqual(self.finishing.preview(), preview)


class ReviewDotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_three_pure_dots_have_no_text_or_tooltips_and_accept_clicks(self):
        for state in ('green', 'yellow', 'red'):
            dot = ReviewDot(state)
            called = []
            dot.clicked.connect(lambda *_: called.append(True))
            dot.show()
            QTest.mouseClick(dot, Qt.MouseButton.LeftButton)
            self.assertEqual(called, [True])
            self.assertEqual(dot.text(), '')
            self.assertEqual(dot.toolTip(), '')
            self.assertTrue(dot.isChecked())
            dot.close()


if __name__ == '__main__':
    unittest.main()
