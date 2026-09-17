import json,shutil,unittest
from pathlib import Path
from unittest.mock import patch
import test_production as fixtures
from app.core import Store
from app.audio_production import AudioProduction,Voice,VoiceMapping,Dialogue,probe_audio
from app.tts_adapter import MiniMaxAdapter,SYSTEM_VOICE
from app.alignment import AlignmentProduction,WhisperXAdapter,srt_text
from integrations.production_bridge import execute

class AudioTests(unittest.TestCase):
    def setUp(self):
        fixtures.ProductionTests.setUp(self)
        self.audio=AudioProduction(self.store)
        self.voice=Voice(name='示例声音',character_id=self.char.id,description='稳定声音身份，非实际合成质量',default_delivery='calm')
        self.audio.save_voice(self.voice,VoiceMapping(voice_id=self.voice.id,provider_voice_id=SYSTEM_VOICE));self.audio.set_default(self.char.id,self.voice.id)
        self.dialogue=Dialogue(character_id=self.char.id,shot_id=self.shots[0].id,text='你好，这是剧本预期内容。',delivery='calm');self.audio.save_dialogue(self.dialogue)
    tearDown=fixtures.ProductionTests.tearDown
    def complete_audio(self,**kwargs):
        job=self.audio.submit(self.dialogue.id,**kwargs)
        self.assertEqual(self.audio.poll(job.id).status,'processing');job=self.audio.poll(job.id);self.assertEqual(job.status,'completed',job.error);return job
    def test_voice_default_dialogue_persistence_and_invalid_relations(self):
        restored=AudioProduction(Store(self.store.root));self.assertEqual(restored.default_voice(self.char.id),self.voice)
        self.assertEqual(restored.dialogue(self.dialogue.id),self.dialogue)
        duplicate=self.dialogue.model_copy(update={'id':'a'*32})
        with self.assertRaises(ValueError):self.audio.save_dialogue(duplicate)
        mapping=VoiceMapping(voice_id='b'*32,provider_voice_id=SYSTEM_VOICE)
        with self.assertRaises(ValueError):self.audio.save_voice(self.voice,mapping)
    def test_task_and_real_request_keep_provider_at_edge(self):
        task=self.audio.build(self.dialogue.id,delivery='whisper',speed=0.8)
        request=MiniMaxAdapter().prepare(task,self.audio.mapping(task.voice.id))
        self.assertNotIn('provider',task.model_dump_json());self.assertNotIn(SYSTEM_VOICE,task.model_dump_json())
        self.assertEqual(request['body']['voice_setting']['voice_id'],SYSTEM_VOICE)
        self.assertEqual(request['body']['voice_setting']['emotion'],'whisper');self.assertEqual(request['body']['voice_setting']['speed'],0.8)
        self.assertEqual(request['body']['text'],task.text);self.assertFalse(request['body']['stream']);self.assertEqual(request['body']['audio_setting']['format'],'wav')
        self.assertNotIn('Authorization',request['headers'])
        with self.assertRaises(ValueError):self.audio.submit(self.dialogue.id,delivery='crying')
    def test_zero_network_audio_media_trace_and_reference_import(self):
        with patch('socket.socket.connect',side_effect=AssertionError('NETWORK')):job=self.complete_audio()
        result,task=self.audio.trace(job.id);self.assertEqual(job.history,['pending','processing','completed']);self.assertGreater(probe_audio(self.store.path(result.path))['duration'],0)
        ref=self.audio.import_reference(self.store.path(result.path));self.voice.references=[ref];self.audio.save_voice(self.voice,self.audio.mapping(self.voice.id))
        self.assertEqual(self.audio.import_reference(self.store.path(result.path)).sha256,ref.sha256)
        self.assertEqual(self.audio.build(self.dialogue.id).voice.references[0],ref)
    def test_retry_selection_snapshot_restart_and_relocation(self):
        first=self.complete_audio();old=(self.audio.folder(first.task_id)/'task.json').read_bytes()
        with self.assertRaises(ValueError):self.complete_audio(retry_of=first.id)
        self.audio.reject(first.id,'test');self.dialogue.text='剧本后续修改';self.audio.save_dialogue(self.dialogue)
        second=self.complete_audio(retry_of=first.id,text='第二次提交文本',delivery='angry',speed=1.2)
        self.assertNotEqual(first.task_id,second.task_id);self.assertEqual((self.audio.folder(first.task_id)/'task.json').read_bytes(),old)
        self.audio.select(second.id);relocated=self.root/'moved';shutil.copytree(self.store.root,relocated);restored=AudioProduction(Store(relocated))
        self.assertEqual(restored.review(self.dialogue.id).selected_result_id,second.id);self.assertEqual(restored.trace(second.id)[1].text,'第二次提交文本')
        with self.assertRaises(ValueError):restored.select(first.id)
    def test_alignment_expected_actual_separation_srt_and_handoff(self):
        job=self.complete_audio();alignment=AlignmentProduction(self.audio).run(job.id)
        self.assertNotEqual(alignment.expected_text,alignment.transcript);self.assertEqual(alignment.expected_text,self.dialogue.text)
        self.assertTrue(all(w.score is None for s in alignment.segments for w in s.words))
        subtitle=self.store.path(alignment.subtitle_path);self.assertIn('00:00:00,100 --> 00:00:01,700',subtitle.read_text(encoding='utf-8'))
        self.assertIn('[FIXTURE]',subtitle.read_text(encoding='utf-8'));raw=subtitle.read_bytes();subtitle.unlink();AlignmentProduction(self.audio).regenerate_subtitle(job.id);self.assertEqual(raw,subtitle.read_bytes())
        self.audio.select(job.id);handoff=self.audio.handoff(self.shots[0].id);self.assertEqual(handoff['dialogues'][0]['subtitle_path'],alignment.subtitle_path)
    def test_official_errors_and_bad_timing_rejected(self):
        adapter=MiniMaxAdapter()
        for status,body in [(401,{'base_resp':{'status_code':2049}}),(200,{'base_resp':{'status_code':0},'data':{'status':1}}),(200,{'base_resp':{'status_code':0},'trace_id':'x','data':{'status':2,'audio':'invalid'}})]:
            with self.assertRaises(ValueError):adapter.parse(status,body)
        for body in [{'segments':[]},{'segments':[{'start':1,'end':8,'text':'a'}]},{'segments':[{'start':0,'end':1,'text':'a','words':[{'word':'a','start':0,'end':2}]}]}]:
            with self.assertRaises(ValueError):WhisperXAdapter().parse(body,4)
    def test_task_tamper_and_failed_generation_never_select(self):
        job=self.audio.submit(self.dialogue.id);(self.audio.folder(job.task_id)/'provider_request.json').write_text('{}',encoding='utf-8');job=self.audio.poll(job.id)
        self.assertEqual(job.status,'failed');self.assertIsNone(job.result_id);self.assertIsNone(self.audio.review(self.dialogue.id).selected_result_id)
    def test_ordered_multiple_dialogues_and_harness_gate(self):
        second=Dialogue(character_id=self.char.id,shot_id=self.shots[0].id,text='第二句',order=2,delivery='sad');self.audio.save_dialogue(second)
        output=execute(self.store,'prepare_dialogue_audio',{'dialogue_id':self.dialogue.id});self.assertTrue(output['human_review_required']);self.assertIsNone(self.audio.review(self.dialogue.id).selected_result_id)
        self.assertEqual([x['order'] for x in self.audio.handoff(self.shots[0].id)['dialogues']],[1,2])
        with self.assertRaises(ValueError):execute(self.store,'select_audio',{'dialogue_id':self.dialogue.id})
    def test_official_dsh_audio_execution(self):
        from tools.run_harness import launch
        if not Path('integrations/dsh/node_modules/@deepseek-ai/dsh/lib/bin.js').is_file():self.skipTest('Optional DSH runtime absent')
        path=launch(self.dialogue.id,self.store.root,self.root/'audio-dsh',mode='dialogue');trace=json.loads((path/'trace.json').read_text(encoding='utf-8'))
        self.assertEqual([s['tool'] for s in trace['steps']],['prepare_dialogue_audio']);self.assertTrue(trace['result']['human_review_required']);self.assertIsNone(self.audio.review(self.dialogue.id).selected_result_id)
    def test_audio_gui_review_and_empty_state(self):
        from app.gui import App
        job=self.complete_audio();app=App(self.store.root);app.withdraw()
        try:
            panel=app.audio_panel;panel.refresh_results(job.id);panel.show_result()
            self.assertEqual(str(panel.play_button.cget('state')),'normal');self.assertEqual(str(panel.retry_button.cget('state')),'disabled')
            panel.reject();self.assertEqual(str(panel.select_button.cget('state')),'disabled');self.assertEqual(str(panel.retry_button.cget('state')),'normal')
        finally:app.closing=True;app.worker.shutdown(wait=True);app.destroy()
