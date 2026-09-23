"""Semantic UI regression tests, without screenshot/pixel assertions."""
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from app.ui_presenters import take_state, shot_state, mode, harness_summary


class PresentationTests(unittest.TestCase):
    def test_selected_rejected_and_pending_are_derived_without_writes(self):
        shot=SimpleNamespace(scene_id='scene')
        job=SimpleNamespace(result_id='result', status='completed', provider='fal', simulation_only=True)
        review=SimpleNamespace(selected_result_id=None,rejected={})
        self.assertEqual(take_state(job,review),('待审核','ready'))
        self.assertEqual(shot_state(shot,[job],review),'待审核')
        review.rejected['result']='motion'
        self.assertEqual(take_state(job,review),('REJECTED','rejected'))
        self.assertEqual(shot_state(shot,[job],review),'可重试')
        review.selected_result_id='result'
        self.assertEqual(take_state(job,review),('SELECTED','selected'))
        self.assertEqual(shot_state(shot,[job],review),'已选定')
        self.assertEqual(mode(job),'ZERO-CALL')
        job.provider='local-mock'; self.assertEqual(mode(job),'MOCK')

    def test_harness_requires_all_corresponding_ids_and_handles_missing_trace(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); folder=root/'evidence/A-04/production-run';folder.mkdir(parents=True)
            job=SimpleNamespace(id='exec',task_id='task',shot_id='shot')
            trace={'shot_id':'other','result':{'execution_id':'exec','task_id':'task'},'steps':[]}
            path=folder/'trace.json';path.write_text(json.dumps(trace))
            self.assertIsNone(harness_summary(root,job)[1])
            trace['shot_id']='shot';trace['steps']=[{'tool':'inspect_media','status':'completed'}]
            path.write_text(json.dumps(trace))
            self.assertIn('ffprobe',harness_summary(root,job)[0])
            path.write_text('invalid json')
            self.assertIsNone(harness_summary(root,job)[1])

    def test_multiline_binding_empty_review_and_human_gate_buttons(self):
        from app.gui import App
        with tempfile.TemporaryDirectory() as d:
            app=App(Path(d));app.withdraw()
            try:
                app.sgen.set('第一行\n第二行'+('长描述'*300))
                self.assertIn('\n',app.sgen.get())
                app.review_panel.refresh()
                from app.ui_widgets import photo
                self.assertIsNone(photo(app.store, SimpleNamespace(path='assets/missing.png')))
                self.assertIn('尚无 Shot',app.review_panel.summary.get())
                self.assertEqual(str(app.review_panel.select_button['state']),'disabled')
                self.assertEqual(str(app.review_panel.retry_button['state']),'disabled')
                with patch('app.review_gui.shutil.which',return_value=None):
                    app.review_panel.buttons(ready=True,rejected=True)
                self.assertEqual(str(app.review_panel.play_button['state']),'disabled')
                self.assertEqual(str(app.review_panel.retry_button['state']),'normal')
                app.review_panel.buttons(ready=True,rejected=True,busy=True)
                self.assertEqual(str(app.review_panel.retry_button['state']),'disabled')
                app.dirty=False
                app.mark_dirty(SimpleNamespace(widget=app.sgen.widget,keysym='Left',state=0))
                self.assertFalse(app.dirty)
                app.mark_dirty(SimpleNamespace(widget=app.sgen.widget,keysym='a',state=0))
                self.assertTrue(app.dirty)
            finally:
                app.dirty=False;app.close()

    def test_invalid_data_keeps_error_state_and_ffmpeg_failure_is_actionable(self):
        from app.gui import App
        from app.production import media_tool
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'characters').mkdir()
            (root/'characters/broken.json').write_text('{')
            app=App(root);app.withdraw()
            try:
                self.assertIn('数据读取失败',app.status.get())
                with patch.dict(os.environ, {'AIVIDEO_MEDIA_BIN': str(root/'missing-media-bin'),
                                             'AIVIDEO_MEDIA_STRICT': '1'}):
                    with self.assertRaisesRegex(ValueError, 'ffmpeg.*AIVIDEO_MEDIA_BIN'):
                        media_tool('ffmpeg')
            finally:app.dirty=False;app.close()


if __name__=='__main__':unittest.main()
