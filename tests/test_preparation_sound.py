from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.preparation.production import ProductionService
from app.preparation.finishing import ChapterFinishing
from app.rough_cut import probe
import opentimelineio as otio
from app.preparation.runtime import ModelManifest, ProductionRuntime
from app.preparation.sound import SoundProduction
from app.preparation.workspace import Workspace

SCRIPT = '''声音链/名称
01/章节/雨夜
001/门前
人物：林夏/-/-/低声
人物：店员/-/-/-
环境：便利店/雨声、冰柜低鸣
表演：林夏迟疑，压低声音。
对白：林夏：这把伞，是不是有人来找过？
店员：没有。
连续性：雨声持续。
002/窗边
人物：林夏/-/-/低声
环境：便利店/雨声
对白：林夏：我再等等。
'''


class SoundProductionTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(); self.workspace = Workspace(Path(self.temp.name) / 'project')
        result = self.workspace.apply(SCRIPT); self.assertTrue(result.valid, result.diagnostics)
        self.sound = SoundProduction(self.workspace); self.production = ProductionService(self.workspace)
        self.chapter = self.workspace.script.chapters[0]; self.shot = self.chapter.shots[0]
        self.dialogue = self.shot.dialogues[0]

    def tearDown(self): self.temp.cleanup()

    def generate(self, dialogue_id=None, count=1, **settings):
        request = self.sound.build_dialogue_request(dialogue_id or self.dialogue.id,
                                                    output_count=count, **settings)
        job, _ = self.sound.runtime.enqueue(request); self.sound.runtime.run_until_idle()
        return self.sound.runtime.job(job.id)

    def test_dialogue_parse_identity_speaker_no_voice_and_background(self):
        self.assertEqual([(d.order, d.speaker, d.text) for d in self.shot.dialogues],
                         [(1, '林夏', '这把伞，是不是有人来找过？'), (2, '店员', '没有。')])
        self.assertEqual(self.shot.dialogues[0].voice_requirement_id,
                         next(r.id for r in self.workspace.script.requirements if r.kind == 'voice'))
        self.assertIsNone(self.shot.dialogues[1].voice_requirement_id)
        with self.assertRaisesRegex(ValueError, '无音声'):
            self.sound.build_dialogue_request(self.shot.dialogues[1].id)
        background = self.sound.background_items(shot_id=self.shot.id)[0]
        self.assertEqual(background.text, '雨声、冰柜低鸣')
        self.assertNotIn(background.id, [r.id for r in self.workspace.script.requirements])

    def test_voice_reference_dialogue_multi_candidate_current_and_rework(self):
        voice = next(r for r in self.workspace.script.requirements if r.kind == 'voice')
        fixture = Path(__file__).resolve().parents[1] / 'examples/audio-fixtures/FIXTURE-tone.wav'
        voice_candidate = self.production.import_candidate(voice.id, self.shot.id, fixture)
        self.production.review(voice_candidate.id, 'green'); self.production.bind(voice_candidate.id)
        request = self.sound.build_dialogue_request(self.dialogue.id, output_count=3)
        self.assertEqual(request.inputs[0].role, 'reference_audio')
        job, batch = self.sound.runtime.enqueue(request); self.sound.runtime.run_until_idle()
        job = self.sound.runtime.job(job.id)
        self.assertEqual(job.status, 'succeeded'); self.assertEqual(len(job.candidate_ids), 3)
        self.assertEqual({c.review_state for c in self.sound.dialogue_candidates(self.dialogue.id)}, {'unreviewed'})
        first = self.production.review(job.candidate_ids[0], 'green')
        self.assertIsNone(self.sound.current_dialogue(self.dialogue.id))
        self.sound.bind_dialogue(first.id); self.assertEqual(self.sound.current_dialogue(self.dialogue.id), first.id)
        rework = self.generate(count=2)
        self.assertEqual(self.sound.current_dialogue(self.dialogue.id), first.id)
        self.assertEqual(len(rework.candidate_ids), 2)
        external = self.sound.import_dialogue(self.dialogue.id, fixture)
        self.production.review(external.id, 'green')
        self.assertEqual(self.sound.current_dialogue(self.dialogue.id), first.id)
        self.sound.bind_dialogue(external.id)
        self.assertEqual(self.sound.current_dialogue(self.dialogue.id), external.id)
        self.assertEqual(self.sound.runtime.batch(batch.id).summary['succeeded'], 1)

    def test_provider_voice_identity_background_import_and_explicit_current(self):
        voice = next(r for r in self.workspace.script.requirements if r.kind == 'voice')
        identity = self.sound.set_voice_identity(voice.id, 'fixture-local', 'voice-demo-001', '林夏低声')
        request = self.sound.build_dialogue_request(self.dialogue.id)
        self.assertEqual((request.inputs[0].role, request.inputs[0].value), ('voice_identity', 'voice-demo-001'))
        self.assertNotIn('key', request.inputs[0].metadata)
        background = self.sound.background_items(shot_id=self.shot.id)[0]
        job_request = self.sound.build_background_request(background.id, output_count=2)
        job, _ = self.sound.runtime.enqueue(job_request); self.sound.runtime.run_until_idle()
        result = self.sound.runtime.job(job.id); self.assertEqual(result.status, 'succeeded')
        chosen = self.production.review(result.candidate_ids[1], 'green')
        self.sound.bind_background(chosen.id)
        self.assertEqual(self.sound.current_background(background.id), chosen.id)
        self.assertEqual(self.workspace.state['voice_identity_bindings'][voice.id], identity.id)

    def test_voice_change_marks_existing_dialogue_stale_and_unsupported_input_is_blocked(self):
        voice = next(r for r in self.workspace.script.requirements if r.kind == 'voice')
        fixture = Path(__file__).resolve().parents[1] / 'examples/audio-fixtures/FIXTURE-tone.wav'
        first_voice = self.production.import_candidate(voice.id, self.shot.id, fixture)
        self.production.review(first_voice.id, 'green'); self.production.bind(first_voice.id)
        dialogue_job = self.generate()
        dialogue_take = self.production.review(dialogue_job.candidate_ids[0], 'green')
        self.sound.bind_dialogue(dialogue_take.id)
        second_voice = self.production.import_candidate(voice.id, self.shot.id, fixture)
        self.production.review(second_voice.id, 'green'); self.production.bind(second_voice.id)
        self.assertEqual(self.production.current(voice.id), second_voice.id)
        self.assertTrue(self.sound.candidate_stale(dialogue_take.id))
        self.assertEqual(self.sound.current_dialogue(self.dialogue.id), dialogue_take.id)

        self.sound.runtime.registry.register_model(ModelManifest(
            id='audio-without-voice', display_name='No voice input', provider_id='fixture-local',
            tasks={'dialogue_audio'}, accepted_input_roles=set(), output_media='audio',
            model_settings={'language': True, 'performance': True, 'speed': [0.5, 2.0]}))
        blocked = self.sound.build_dialogue_request(self.dialogue.id, model_id='audio-without-voice')
        with self.assertRaisesRegex(ValueError, '不会静默丢弃'):
            self.sound.runtime.enqueue(blocked)

    def test_unedited_subtitle_syncs_and_invalid_import_creates_no_candidate(self):
        original_count = len(self.sound.dialogue_candidates(self.dialogue.id))
        invalid = Path(self.temp.name) / 'not-audio.wav'
        invalid.write_text('not media', encoding='utf-8')
        with self.assertRaises(Exception):
            self.sound.import_dialogue(self.dialogue.id, invalid)
        self.assertEqual(len(self.sound.dialogue_candidates(self.dialogue.id)), original_count)

        changed = SCRIPT.replace('这把伞，是不是有人来找过？', '这把伞，真的有人来找过吗？')
        self.assertTrue(self.workspace.apply(changed).valid)
        restored = SoundProduction(Workspace(self.workspace.root))
        subtitle = restored.subtitle(self.dialogue.id)
        self.assertFalse(subtitle.manual_text)
        self.assertFalse(subtitle.stale)
        self.assertEqual(subtitle.display_text, '这把伞，真的有人来找过吗？')

    def test_strategy_timing_subtitle_stale_and_script_truth_protected(self):
        job = self.generate(); candidate = self.production.review(job.candidate_ids[0], 'green')
        self.sound.bind_dialogue(candidate.id)
        self.sound.update_state(self.dialogue.id, strategy='independent', start=.7, volume=.8)
        self.sound.update_subtitle(self.dialogue.id, display_text='这把伞，\n有人找过吗？', start=.8, end=1.9)
        before_script = self.workspace.state['draft']
        changed = SCRIPT.replace('这把伞，是不是有人来找过？', '这把伞，真的有人来找过吗？')
        self.assertTrue(self.workspace.apply(changed).valid)
        restored = SoundProduction(Workspace(self.workspace.root))
        subtitle = restored.subtitle(self.dialogue.id)
        self.assertTrue(subtitle.stale); self.assertTrue(subtitle.manual_text)
        self.assertEqual(subtitle.display_text, '这把伞，\n有人找过吗？')
        acknowledged = restored.update_subtitle(self.dialogue.id, display_text='这把伞，真的有人来找过吗？')
        self.assertFalse(acknowledged.stale)
        self.assertEqual(acknowledged.source_fingerprint, restored.dialogue(self.dialogue.id).source_fingerprint)
        self.assertTrue(restored.candidate_stale(candidate.id))
        self.assertNotEqual(before_script, restored.workspace.state['draft'])
        self.assertEqual(restored.current_dialogue(self.dialogue.id), candidate.id)

    def test_audio_first_video_conditioning_and_batch(self):
        job = self.generate(); candidate = self.production.review(job.candidate_ids[0], 'green')
        self.sound.bind_dialogue(candidate.id)
        self.sound.update_state(self.dialogue.id, strategy='independent')
        request = ProductionRuntime(self.workspace).build_request(self.shot.id, 'video', None,
                                                                  'fixture-video-v1')
        dialogue_input = next(item for item in request.inputs if item.purpose == 'dialogue')
        self.assertEqual(dialogue_input.metadata['dialogue_id'], self.dialogue.id)
        requests = [self.sound.build_dialogue_request(item.id) for item in self.sound.dialogues(chapter_id=self.chapter.id)
                    if item.voice_requirement_id]
        jobs, batch = self.sound.runtime.enqueue_many(requests, user_intent='补齐本章对白')
        self.sound.runtime.run_until_idle()
        self.assertEqual(self.sound.runtime.batch(batch.id).summary['succeeded'], len(jobs))
        self.assertFalse(self.sound.audio_plan(self.shot.id)['native_audio'])

    def test_audio_failure_retry_and_cancel_use_unified_runtime(self):
        background = self.sound.background_items(shot_id=self.shot.id)[0]
        failed_request = self.sound.build_background_request(background.id, fixture_mode='failure')
        failed, _ = self.sound.runtime.enqueue(failed_request)
        self.sound.runtime.run_until_idle()
        self.assertEqual(self.sound.runtime.job(failed.id).status, 'failed')
        retried, _ = self.sound.runtime.retry(failed.id, model_settings={'fixture_mode': 'success'})
        self.sound.runtime.run_until_idle()
        self.assertEqual(self.sound.runtime.job(retried.id).status, 'succeeded')
        self.assertTrue(self.sound.runtime.job(retried.id).candidate_ids)

        queued, _ = self.sound.runtime.enqueue(self.sound.build_dialogue_request(self.dialogue.id))
        canceled = self.sound.runtime.cancel(queued.id)
        self.assertEqual(canceled.status, 'canceled')
        self.assertFalse(canceled.candidate_ids)

    def test_real_assembly_preview_output_srt_otio_and_restart(self):
        fixtures = sorted((Path(__file__).resolve().parents[1] / 'evidence/A-04/smoke-data/results').glob('*/video.mp4'))
        for index, shot in enumerate(self.chapter.shots):
            video = self.production.import_shot_candidate(shot.id, fixtures[index])
            self.production.review(video.id, 'green'); self.production.bind_shot(video.id)
        for dialogue in self.sound.dialogues(chapter_id=self.chapter.id):
            if not dialogue.voice_requirement_id: continue
            request = self.sound.build_dialogue_request(dialogue.id, output_count=2)
            job, _ = self.sound.runtime.enqueue(request); self.sound.runtime.run_until_idle()
            candidate = self.production.review(self.sound.runtime.job(job.id).candidate_ids[0], 'green')
            self.sound.bind_dialogue(candidate.id)
            self.sound.update_state(dialogue.id, strategy='independent', start=.25, volume=.85)
        for background in self.sound.background_items(chapter_id=self.chapter.id):
            request = self.sound.build_background_request(background.id)
            job, _ = self.sound.runtime.enqueue(request); self.sound.runtime.run_until_idle()
            candidate = self.production.review(self.sound.runtime.job(job.id).candidate_ids[0], 'green')
            self.sound.bind_background(candidate.id)
        finishing = ChapterFinishing(self.workspace, self.chapter.id)
        resolved = finishing.resolve()
        self.assertEqual(resolved['status'], 'Ready')
        self.assertGreaterEqual(len(resolved['subtitles']), 3)
        preview = finishing.preview(); output = finishing.output(); handoff = finishing.handoff()
        self.assertGreater(probe(preview, 'audio')['duration'], 0)
        self.assertGreater(probe(output, 'audio')['duration'], 0)
        srt = (handoff / 'subtitles.srt').read_text(encoding='utf-8')
        self.assertIn('00:00:00,', srt); self.assertIn('这把伞', srt)
        timeline = otio.adapters.read_from_file(str(handoff / 'timeline.otio'))
        self.assertEqual([track.name for track in timeline.tracks],
                         ['Current Shot Video', 'Native Video Audio', 'Independent Dialogue', 'Background Audio'])
        self.assertTrue(timeline.is_equivalent_to(otio.adapters.read_from_string(
            otio.adapters.write_to_string(timeline))))
        restored = SoundProduction(Workspace(self.workspace.root))
        self.assertEqual(restored.current_dialogue(self.dialogue.id),
                         self.sound.current_dialogue(self.dialogue.id))
        self.assertAlmostEqual(restored.state(self.dialogue.id).start, .25)
        self.assertEqual(restored.subtitle(self.dialogue.id).display_text, self.dialogue.text)



if __name__ == '__main__': unittest.main()
