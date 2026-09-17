"""UI-Final tests focus on routing, read-only projections and background work."""
import json
from pathlib import Path
import tempfile,threading,time,unittest
from unittest.mock import patch
from app.core import Store
from app.ui_presenters import shot_overview

ROOT=Path(__file__).resolve().parents[1]
class UIFinalTests(unittest.TestCase):
    def test_summary_reads_existing_selected_context_and_detects_changed_frame_assets(self):
        store=Store(ROOT/'evidence/A-08/gui-data')
        shot=next(s for s in store.shots() if s.id=='d8094901e03441f1bb9ad8696bb427c0')
        with patch('app.core.write_json',side_effect=AssertionError('UI projection must not write')):
            data=shot_overview(store,shot)
            self.assertIn('林夏',data['who']);self.assertEqual(data['dialogues'],2)
            self.assertEqual(data['details']['selected_video'],'2cb8df46592b47f5a7284946e73ed280')
            self.assertIn(('首帧','Selected','selected'),data['badges'])
            changed=shot.model_copy(update={'scene_state_id':'8c3bc5fb50ce4dbf83941cede21cddae'})
            self.assertIn(('首帧','Stale','stale'),shot_overview(store,changed)['badges'])

    def test_navigation_dirty_guard_and_advanced_are_presentation_only(self):
        from app.gui import App
        with tempfile.TemporaryDirectory() as d:
            app=App(Path(d));app.withdraw()
            try:
                app.update_idletasks();self.assertEqual(app.tabs.index('current'),2)
                self.assertFalse(app.shot_overview.advanced.opened)
                app.dirty=True;app.navigation.go('voices');self.assertEqual(app.tabs.index('current'),2)
                self.assertIn('保存',app.status.get())
                app.dirty=False;app.navigation.go('voices');app.update()
                self.assertEqual(app.tabs.index('current'),5);self.assertEqual(app.audio_panel.tabs.index('current'),0)
                app.navigation.go('dialogue');app.update();self.assertEqual(app.audio_panel.tabs.index('current'),1)
                self.assertEqual(list(Path(d).rglob('*.json')),[])
            finally:app.dirty=False;app.close()

    def test_media_inspection_does_not_block_tk_and_obsolete_report_is_ignored(self):
        from app.gui import App
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as d:
            app=App(Path(d));app.withdraw();started=threading.Event();release=threading.Event()
            def slow(identifier):
                started.set();release.wait(3)
                return dict(clips=[],errors=[],warnings=[],duration=0,rate='24')
            panel=app.rough_panel;panel.current=SimpleNamespace(id='old')
            try:
                with patch.object(panel.production,'resolve',side_effect=slow),patch.object(panel.production,'current',side_effect=ValueError('Draft')):
                    panel.report();self.assertTrue(started.wait(1))
                    observed=[];app.after(0,lambda:observed.append(True));app.update()
                    self.assertEqual(observed,[True]);panel.new();release.set()
                    deadline=time.monotonic()+.4
                    while time.monotonic()<deadline:app.update();time.sleep(.02)
                    self.assertIn('DRAFT',panel.badge.cget('text'))
            finally:release.set();app.close()

    def test_direct_destroy_cancels_child_timers_as_well_as_normal_close(self):
        from app.gui import App
        with tempfile.TemporaryDirectory() as d:
            app=App(Path(d));app.withdraw()
            self.assertTrue(app.tk.call('after','info'))
            app.closing=True;app.worker.shutdown(wait=True);app.destroy()
            self.assertFalse(app.tk.call('after','info'))

    def test_inline_failure_and_duplicate_media_operation_do_not_change_records(self):
        from app.gui import App
        with tempfile.TemporaryDirectory() as d:
            app=App(Path(d));app.withdraw()
            try:
                app.guard(lambda:(_ for _ in ()).throw(ValueError('请选择 Shot')))
                self.assertIn('请选择 Shot',app.status.get())
                app.rough_panel.busy=True
                with self.assertRaisesRegex(ValueError,'媒体操作'):app.rough_panel.save()
                self.assertEqual(list(Path(d).rglob('*.json')),[])
            finally:app.close()

if __name__=='__main__':unittest.main()
