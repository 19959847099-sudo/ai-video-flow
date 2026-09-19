from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from PIL import Image

from app.preparation.finishing import ChapterFinishing
from app.preparation.production import ProductionService
from app.preparation.runtime import ProductionRuntime, ProductionInput, match_capability
from app.preparation.workspace import Workspace

SCRIPT = '''统一运行时/名称
01/章节/测试
001/出门
人物：【林/28/深色外套】/低声
环境：【雨夜街口】/-
镜头：【手持跟拍】
动作：林举起【红伞】，走进雨中。
002/回望
人物：【林/28/深色外套】/低声
环境：【雨夜街口】/-
动作：林回头。
'''


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.workspace = Workspace(Path(self.temp.name) / 'project')
        self.assertTrue(self.workspace.apply(SCRIPT).valid)
        self.runtime = ProductionRuntime(self.workspace)
        self.service = ProductionService(self.workspace)
        self.shots = self.workspace.script.chapters[0].shots

    def tearDown(self):
        self.temp.cleanup()

    def requirement(self, media, kind=None):
        return next(r for r in self.workspace.script.requirements
                    if r.media == media and (kind is None or r.kind == kind))

    def request(self, media, requirement=None, **kw):
        model = {'image': 'fixture-image-v1', 'audio': 'fixture-audio-v1',
                 'video': 'fixture-video-v1'}[media]
        return self.runtime.build_request(self.shots[0].id, media,
                                          requirement.id if requirement else None,
                                          model, **kw)

    def test_request_types_model_provider_and_snapshot_are_separate(self):
        image = self.request('image', self.requirement('image'))
        audio = self.request('audio', self.requirement('audio'))
        video_ref = self.request('video', self.requirement('video', 'video_reference'))
        shot = self.request('video')
        self.assertEqual([image.task, audio.task, video_ref.task, shot.task],
                         ['asset_image', 'asset_audio', 'video_reference', 'shot_video'])
        self.assertEqual(shot.provider_id, 'fixture-local')
        self.assertNotEqual(shot.model_id, shot.provider_id)
        job, _ = self.runtime.enqueue(image)
        original = job.request_snapshot['prompt']
        image.prompt = 'changed after submit'
        self.assertEqual(self.runtime.job(job.id).request_snapshot['prompt'], original)
        self.assertEqual(self.runtime.registry.provider_info()[0]['credentials_available'], True)

    def test_capability_never_silently_drops_reference_and_model_switch_is_read_only(self):
        req = self.request('video')
        req.inputs = [ProductionInput(role='reference_image', purpose='character', asset_id='asset',
                                      path='library/x.png', sha256='abc')]
        text_only = self.runtime.registry.model('fixture-video-text-v1')
        report = match_capability(req.model_copy(update={'model_id': text_only.id}), text_only)
        self.assertEqual(report.state, 'UNSUPPORTED')
        self.assertEqual(report.unsupported[0].asset_id, 'asset')
        before = self.workspace.state['bindings'].copy()
        with self.assertRaisesRegex(ValueError, '不会静默丢弃'):
            self.runtime.enqueue(req.model_copy(update={'model_id': text_only.id}))
        self.assertEqual(self.workspace.state['bindings'], before)
        image = self.request('image', self.requirement('image'))
        image.inputs = [ProductionInput(role='source_image', purpose='source', asset_id='source',
                                        path='library/source.png', sha256='def')]
        translated = self.runtime.capability(image)
        self.assertEqual(translated.state, 'TRANSLATED')
        job, _ = self.runtime.enqueue(image)
        provider_request = self.runtime._provider_request(job)
        self.assertEqual(provider_request.inputs[0].role, 'reference_image')
        self.assertEqual(self.runtime.job(job.id).request_snapshot['inputs'][0]['role'], 'source_image')

    def test_multi_output_image_becomes_unreviewed_candidates_only(self):
        req = self.requirement('image')
        request = self.request('image', req, output_count=3)
        job, batch = self.runtime.enqueue(request)
        self.assertEqual(job.status, 'queued')
        jobs = self.runtime.run_until_idle()
        result = next(j for j in jobs if j.id == job.id)
        self.assertEqual(result.status, 'succeeded')
        self.assertEqual(len(result.candidate_ids), 3)
        self.assertEqual(self.runtime.batch(batch.id).summary['succeeded'], 1)
        candidates = self.service.candidates(req.id)
        self.assertEqual({c.review_state for c in candidates}, {'unreviewed'})
        self.assertIsNone(self.service.current(req.id))
        self.assertTrue(all(self.service.available(c.id) for c in candidates))

    def test_audio_video_and_shot_all_use_runtime_then_explicit_current(self):
        audio_req = self.requirement('audio')
        audio_job, _ = self.runtime.enqueue(self.request('audio', audio_req, output_count=2))
        video_req = self.requirement('video', 'video_reference')
        ref_job, _ = self.runtime.enqueue(self.request('video', video_req))
        shot_job, _ = self.runtime.enqueue(self.request('video', output_count=2,
                                                        common={'duration': .5, 'frame_rate': 12}))
        self.runtime.run_until_idle()
        audio_job, ref_job, shot_job = map(lambda j: self.runtime.job(j.id),
                                           (audio_job, ref_job, shot_job))
        self.assertEqual([audio_job.status, ref_job.status, shot_job.status],
                         ['succeeded', 'succeeded', 'succeeded'])
        self.assertEqual(len(audio_job.candidate_ids), 2)
        self.assertEqual(len(shot_job.candidate_ids), 2)
        candidate = self.service.candidate(shot_job.candidate_ids[0])
        self.assertEqual(candidate.kind, 'shot_video')
        self.assertIsNone(self.service.current_shot(self.shots[0].id))
        self.service.review(candidate.id, 'green')
        self.assertIsNone(self.service.current_shot(self.shots[0].id))
        self.service.bind_shot(candidate.id)
        self.assertEqual(self.service.current_shot(self.shots[0].id), candidate.id)
        self.assertEqual(ChapterFinishing(self.workspace, self.workspace.script.chapters[0].id)
                         .resolve()['clips'][0]['candidate_id'], candidate.id)

    def test_failure_invalid_media_retry_cancel_and_no_fake_candidate(self):
        req = self.requirement('image')
        failing = self.request('image', req, model_settings={'fixture_mode': 'failure'})
        job, _ = self.runtime.enqueue(failing)
        self.runtime.run_until_idle()
        failed = self.runtime.job(job.id)
        self.assertEqual(failed.status, 'failed')
        self.assertTrue(failed.retryable)
        self.assertFalse(failed.candidate_ids)
        self.assertFalse(self.service.candidates(req.id))
        retry, _ = self.runtime.retry(job.id, model_settings={'fixture_mode': 'success'})
        self.runtime.run_until_idle()
        self.assertEqual(self.runtime.job(retry.id).status, 'succeeded')
        self.assertEqual(self.runtime.job(retry.id).attempt, 2)
        invalid, _ = self.runtime.enqueue(self.request('image', req,
                                           model_settings={'fixture_mode': 'invalid_media'}))
        self.runtime.run_until_idle()
        self.assertEqual(self.runtime.job(invalid.id).error_code, 'invalid_media')
        delayed, _ = self.runtime.enqueue(self.request('image', req,
                                           model_settings={'fixture_mode': 'delay'}))
        self.runtime.tick()
        self.assertEqual(self.runtime.job(delayed.id).status, 'running')
        self.runtime.cancel(delayed.id)
        self.assertEqual(self.runtime.job(delayed.id).status, 'canceled')

    def test_batch_partial_failure_and_restart_reconciliation(self):
        req = self.requirement('image')
        good = self.request('image', req)
        bad = self.request('image', req, model_settings={'fixture_mode': 'auth'})
        jobs, batch = self.runtime.enqueue_many([good, bad])
        self.runtime.run_until_idle()
        summary = self.runtime.batch(batch.id).summary
        self.assertEqual((summary['succeeded'], summary['failed']), (1, 1))
        self.assertEqual(len(self.service.candidates(req.id)), 1)
        delayed, _ = self.runtime.enqueue(self.request('image', req,
                                           model_settings={'fixture_mode': 'delay'}))
        self.runtime.tick()
        self.assertEqual(self.runtime.job(delayed.id).status, 'running')
        restored = Workspace(self.workspace.root)
        runtime = ProductionRuntime(restored)
        runtime.reconcile()
        runtime.run_until_idle()
        self.assertEqual(runtime.job(delayed.id).status, 'succeeded')
        self.assertIn(delayed.id, restored.state['runtime_jobs'])


    def test_provider_concurrency_failure_matrix_and_asset_rework_preserves_current(self):
        req = self.requirement('image')
        # Establish an explicit Current before rework.
        source = Path(self.temp.name) / 'current.png'
        Image.new('RGB', (80, 60), '#334455').save(source)
        current = self.service.import_candidate(req.id, self.shots[0].id, source)
        self.service.review(current.id, 'green'); self.service.bind(current.id)
        requests = [self.request('image', req, model_settings={'fixture_mode': 'delay'})
                    for _ in range(3)]
        jobs, batch = self.runtime.enqueue_many(requests, user_intent='并发验证')
        self.runtime.tick()
        states = [self.runtime.job(j.id).status for j in jobs]
        self.assertEqual(states.count('running'), 2)
        self.assertEqual(states.count('queued'), 1)
        for job in jobs: self.runtime.cancel(job.id)
        self.assertEqual(self.runtime.batch(batch.id).summary['canceled'], 3)
        for mode, code, retryable in (('auth', 'auth', False), ('timeout', 'timeout', True),
                                      ('download_failure', 'download', True)):
            with self.subTest(mode=mode):
                job, _ = self.runtime.enqueue(self.request('image', req,
                                             model_settings={'fixture_mode': mode}))
                self.runtime.run_until_idle(); result = self.runtime.job(job.id)
                self.assertEqual((result.status, result.error_code, result.retryable),
                                 ('failed', code, retryable))
                self.assertFalse(result.candidate_ids)
        rework, _ = self.runtime.enqueue(self.request('image', req))
        self.runtime.run_until_idle(); rework = self.runtime.job(rework.id)
        self.assertEqual(rework.status, 'succeeded')
        self.assertEqual(self.service.current(req.id), current.id)
        self.assertEqual(self.service.candidate(rework.candidate_ids[0]).review_state, 'unreviewed')



if __name__ == '__main__':
    unittest.main()
