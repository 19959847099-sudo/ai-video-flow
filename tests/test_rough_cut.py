import json,shutil,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import opentimelineio as otio
from app.core import Store,write_json
from app.rough_cut import RoughCutProduction,TimelineDefinition,probe,fingerprint
from app.audio_production import digest
from integrations.production_bridge import execute

ROOT=Path(__file__).resolve().parents[1]
DAY='d8094901e03441f1bb9ad8696bb427c0';OTHER='cda53866e184457587a2b671ff062482';MISSING='da107ac03bf949c0a099b4159fea8701'
class RoughCutTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);shutil.copytree(ROOT/'evidence/A-07/gui-data',self.root/'data');self.store=Store(self.root/'data');self.r=RoughCutProduction(self.store)
        self.d=self.r.save(TimelineDefinition(name='测试粗剪',shot_ids=[OTHER,DAY],allow_missing_audio=True,allow_missing_subtitles=True))
    def tearDown(self):self.temp.cleanup()
    def test_explicit_order_persistence_and_duplicates(self):
        self.d.shot_ids.reverse();self.r.save(self.d);self.assertEqual(RoughCutProduction(Store(self.store.root)).definition(self.d.id).shot_ids,[DAY,OTHER])
        with self.assertRaises(ValueError):self.r.save(self.d.model_copy(update={'shot_ids':[DAY,DAY]}))
    def test_missing_selected_video_blocks_without_candidate_fallback(self):
        self.d.shot_ids=[MISSING];self.r.save(self.d);self.assertEqual(self.r.resolve(self.d.id)['status'],'Blocked')
        with self.assertRaises(ValueError):self.r.build(self.d.id)
    def test_missing_audio_requires_explicit_human_allowance(self):
        self.d.allow_missing_audio=False;self.r.save(self.d);self.assertTrue(self.r.resolve(self.d.id)['errors'])
        self.d.allow_missing_audio=True;self.r.save(self.d);m=self.r.resolve(self.d.id)
        self.assertEqual(m['status'],'Ready');self.assertEqual(len(m['clips'][1]['audios']),1)
        self.assertEqual(m['clips'][1]['audios'][0]['result_id'],'758fb7ebbde74f18a222afdbe1cb3196')
    def test_duration_probe_trim_and_subtitle_provenance(self):
        m=self.r.resolve(self.d.id);c=m['clips'][1];a=c['audios'][0]
        self.assertEqual(a['metadata']['duration'],4);self.assertEqual(a['duration'],3);self.assertTrue(any('trim' in w for w in m['warnings']))
        self.assertTrue(all(x['end']<=m['duration'] for x in c['subtitles']));self.assertTrue(all(x['audio_result_id']==a['result_id'] for x in c['subtitles']))
        self.assertIn('time_base',c['metadata']);self.assertGreater(float(m['rate']),0)
    def test_changed_selection_never_reuses_old_subtitle(self):
        self.r.build(self.d.id);did='5c235da8a53240a789836abacaa80d11';rid='c23104d4d6064d71b22e15ab1251f7cb'
        self.r.audio.select(rid);self.store.record_path('alignments',rid).unlink()
        with self.assertRaisesRegex(ValueError,'STALE'):self.r.current(self.d.id)
        m=self.r.resolve(self.d.id);self.assertFalse(m['clips'][1]['subtitles']);self.assertTrue(any('旧字幕不复用' in w for w in m['warnings']))
        self.d.allow_missing_subtitles=False;self.r.save(self.d);self.assertTrue(self.r.resolve(self.d.id)['errors'])
    def test_mismatched_alignment_and_corrupt_media_block(self):
        rid='758fb7ebbde74f18a222afdbe1cb3196';p=self.store.record_path('alignments',rid);v=json.loads(p.read_text(encoding='utf-8'));v['audio_result_id']='c23104d4d6064d71b22e15ab1251f7cb';write_json(p,v)
        self.assertTrue(self.r.resolve(self.d.id)['errors'])
        selected=self.r.video.review(OTHER).selected_result_id;media=self.store.path(self.r.video.result(selected).path);media.write_bytes(b'broken');self.assertTrue(any(OTHER[:8] in e for e in self.r.resolve(self.d.id)['errors']))
    def test_real_otio_roundtrip_order_metadata_and_references(self):
        folder,m=self.r.build(self.d.id);t=otio.adapters.read_from_file(str(folder/'timeline.otio'))
        self.assertEqual([c.metadata['aigc']['shot_id'] for c in t.video_tracks()[0]],self.d.shot_ids)
        self.assertEqual(len(list(t.audio_tracks()[0].find_clips())),1);self.assertAlmostEqual(t.duration().to_seconds(),m['duration'])
        from urllib.parse import unquote
        for c in t.find_clips():self.assertTrue((folder/unquote(c.media_reference.target_url)).is_file())
        self.assertTrue(t.is_equivalent_to(otio.adapters.read_from_string(otio.adapters.write_to_string(t))))
    def test_preview_real_streams_and_portable_relocation(self):
        with patch('socket.socket.connect',side_effect=AssertionError('NETWORK')):
            self.r.build(self.d.id);folder,m=self.r.preview(self.d.id);package=self.r.export(self.d.id)
        self.assertAlmostEqual(probe(folder/'rough-cut.mp4','video')['duration'],m['duration'],delta=.05);self.assertEqual(probe(folder/'rough-cut.mp4','audio')['channels'],1)
        moved=self.root/'moved';shutil.copytree(package,moved);t=otio.adapters.read_from_file(str(moved/'timeline.otio'))
        from urllib.parse import unquote
        for c in t.find_clips():self.assertEqual(digest(moved/unquote(c.media_reference.target_url)),c.metadata['aigc']['sha256'])
        p=json.loads((moved/'manifest.json').read_text(encoding='utf-8'))
        for c in p['clips']:
            for a in c['audios']:self.assertTrue((moved/a['subtitle_path']).exists())
    def test_manifest_tamper_and_unsaved_current_block(self):
        folder,m=self.r.build(self.d.id);m['clips'][0]['frames']=1;write_json(folder/'manifest.json',m)
        with self.assertRaisesRegex(ValueError,'Manifest'):self.r.current(self.d.id)
    def test_mixed_source_rates_use_real_probe_and_normalize_preview(self):
        from app.production import media_tool,run_media
        selected=self.r.video.review(DAY).selected_result_id;result=self.r.video.result(selected);source=self.store.path(result.path)
        changed=self.root/'thirty.mp4'
        run_media([media_tool('ffmpeg'),'-v','error','-i',str(source),'-r','30','-an','-c:v','libx264',str(changed)])
        shutil.copyfile(changed,source);result.sha256=digest(source);result.duration=999
        write_json(self.store.path(f'results/{result.id}/result.json'),result.model_dump())
        m=self.r.resolve(self.d.id);self.assertEqual(m['rate'],'24');self.assertEqual(m['clips'][1]['metadata']['rate'],'30')
        self.assertEqual(m['duration'],6);self.assertTrue(any('混合帧率' in w for w in m['warnings']))
        self.r.build(self.d.id);folder,_=self.r.preview(self.d.id);self.assertEqual(probe(folder/'rough-cut.mp4','video')['rate'],'24')
    def test_dsh_tool_preserves_all_production_facts(self):
        def state():return {p.relative_to(self.store.root).as_posix():digest(p) for p in self.store.root.rglob('*.json') if not any(x in p.parts for x in ('rough_cut_builds','rough_cut_current'))}
        before=state();out=execute(self.store,'prepare_rough_cut',{'timeline_id':self.d.id});self.assertTrue(out['human_review_required']);self.assertEqual(before,state())
        with self.assertRaises(ValueError):execute(self.store,'select_take',{'timeline_id':self.d.id})
    def test_gui_empty_timeline_and_saved_order(self):
        from app.gui import App
        app=App(self.store.root);app.withdraw()
        try:
            panel=app.rough_panel;panel.refresh();panel.saved.current(0);panel.open();self.assertEqual(panel.order,self.d.shot_ids)
            panel.order_list.selection_set(1);panel.move(-1);panel.save();self.assertEqual(self.r.definition(self.d.id).shot_ids,[DAY,OTHER])
        finally:app.closing=True;app.worker.shutdown(wait=True);app.destroy()
