import base64
import hashlib
import json
import shutil
import socket
import unittest
from unittest.mock import patch

from app.core import Store, write_json
from app.fal_adapter import FalAdapter, FixtureTransport, ProductionRunner, MODEL, ENDPOINT
from app.production import probe_video
import test_production


class FalTests(unittest.TestCase):
    setUp = test_production.ProductionTests.setUp
    tearDown = test_production.ProductionTests.tearDown

    def run_job(self, runner, job):
        for _ in range(8):
            job = runner.poll(job.id)
            if job.status in ('completed', 'failed'): return job
        self.fail('Fixture did not terminate')

    def test_request_preserves_all_inputs_and_reference_bytes(self):
        task = self.store.task(self.shots[0].id)
        before = task.model_dump_json()
        request = FalAdapter().prepare(task, self.store.root)
        self.assertEqual(request['url'], ENDPOINT)
        self.assertEqual(request['model'], MODEL)
        self.assertEqual(request['body']['duration'], '3')
        self.assertFalse(request['body']['generate_audio'])
        self.assertTrue(request['body']['prompt'].startswith(task.final_prompt))
        self.assertNotIn('Authorization', request['headers'])
        for i, ref in enumerate(task.references + task.scene_references):
            raw = base64.b64decode(request['body']['image_urls'][i].split(',', 1)[1])
            self.assertEqual(hashlib.sha256(raw).hexdigest(), ref.sha256)
            self.assertEqual(request['reference_bindings'][i]['reference_id'], ref.id)
            self.assertIn(f'@Image{i+1}', request['body']['prompt'])
        self.assertEqual(task.model_dump_json(), before)

    def test_zero_network_full_chain_restart_retry_and_relocation(self):
        with patch.object(socket.socket, 'connect', side_effect=AssertionError('Network forbidden')) as connect, \
             patch('socket.create_connection', side_effect=AssertionError('Network forbidden')) as connection:
            runner = ProductionRunner(self.store)
            job = runner.submit(self.shots[0].id, provider='fal')
            self.assertEqual(runner.poll(job.id).status, 'pending')  # submit ID persisted
            self.assertEqual(runner.poll(job.id).status, 'pending')  # IN_QUEUE
            self.assertEqual(runner.poll(job.id).status, 'processing')
            folder = self.store.path(f'tasks/{job.task_id}')
            before = (folder/'task.json').read_bytes(), (folder/'provider_request.json').read_bytes()
            self.char.description = 'changed after submit'
            self.scene.description = 'changed scene after submit'
            self.store.save_character(self.char); self.store.save_scene(self.scene)
            runner = ProductionRunner(Store(self.store.root))
            job = self.run_job(runner, job)
            self.assertEqual(job.status, 'completed', job.error)
            self.assertEqual(job.history, ['pending', 'processing', 'completed'])
            self.assertIsNone(runner.review(job.shot_id).selected_result_id)
            result, task = runner.trace(job.result_id)
            self.assertEqual(probe_video(self.store.path(result.path))['duration'], 3)
            self.assertEqual(before, ((folder/'task.json').read_bytes(), (folder/'provider_request.json').read_bytes()))
            exchange = json.loads((folder/'provider_exchange.json').read_text(encoding='utf-8'))
            self.assertEqual(len(exchange['events']), 5)
            self.assertFalse(exchange['api_called'])
            runner.reject(job.shot_id, result.id, 'test motion')
            retry = runner.submit(job.shot_id, retry_of=result.id, generation_description='Pause two seconds', provider='local-mock')
            self.assertEqual(retry.provider, 'fal')  # Independent of current GUI selection.
            retry = self.run_job(runner, retry)
            self.assertEqual(retry.status, 'completed', retry.error)
            self.assertNotEqual(job.task_id, retry.task_id)
            self.assertEqual(retry.retry_of, result.id)
            self.assertIn('Pause two seconds', runner.submitted_prompt(retry.task_id))
            runner.select(job.shot_id, retry.result_id)
            relocated = self.root/'relocated'
            shutil.copytree(self.store.root, relocated)
            restored = ProductionRunner(Store(relocated))
            self.assertEqual(restored.review(job.shot_id).selected_result_id, retry.result_id)
            self.assertEqual(restored.trace(retry.result_id)[1].scene.id, self.scene.id)
            connect.assert_not_called(); connection.assert_not_called()

    def test_failure_fixtures_never_create_results_or_select(self):
        runner = ProductionRunner(self.store)
        for scenario in ('unauthorized', 'validation', 'rate_limit', 'timeout', 'generation_error', 'missing_video'):
            with self.subTest(scenario=scenario):
                job = runner.submit(self.shots[0].id, provider='fal')
                path = self.store.path(f'tasks/{job.task_id}/provider_exchange.json')
                write_json(path, dict(transport='fixture', api_called=False, step=0, scenario=scenario, events=[]))
                job = self.run_job(runner, job)
                self.assertEqual(job.status, 'failed', scenario)
                self.assertTrue(job.error)
                self.assertIsNone(job.result_id)
                self.assertIsNone(runner.review(job.shot_id).selected_result_id)
                before = path.read_bytes()
                self.assertEqual(runner.poll(job.id), job)
                self.assertEqual(path.read_bytes(), before)  # Terminal; never auto-resubmit.

    def test_malformed_status_result_and_cross_request_rejected(self):
        adapter = FalAdapter()
        for body in ({'status':'UNKNOWN', 'request_id':'x'}, {'status':'COMPLETED', 'request_id':'other'}):
            with self.assertRaises(ValueError): adapter.status(200, body, 'x')
        with self.assertRaises(ValueError):
            adapter.submission(200, dict(request_id='x', status_url=ENDPOINT+'/requests/other/status', response_url=ENDPOINT+'/requests/x/response'))
        for body in ({}, {'video':{'url':'file:///tmp/x'}}, {'video':{'url':'https://x/a', 'content_type':'image/png'}}):
            with self.assertRaises(ValueError): adapter.result(200, body)
        with self.assertRaises(ValueError):
            FixtureTransport('x').download('https://real-provider.example/video.mp4', lambda: self.fail('Must not download'))

    def test_limits_and_changed_reference_are_explicit_errors(self):
        task = self.store.task(self.shots[0].id)
        task.final_prompt = 'a' * 2501
        with self.assertRaisesRegex(ValueError, '2500'): FalAdapter().prepare(task, self.store.root)
        task = self.store.task(self.shots[0].id)
        self.store.path(task.references[0].path).write_bytes(b'changed')
        with self.assertRaises(ValueError): FalAdapter().prepare(task, self.store.root)

    def test_submitted_request_change_stops_execution(self):
        runner = ProductionRunner(self.store)
        job = runner.submit(self.shots[1].id, provider='fal')
        runner.poll(job.id)
        path = self.store.path(f'tasks/{job.task_id}/provider_request.json')
        request = json.loads(path.read_text(encoding='utf-8'))
        self.assertIn(self.scene.states[1].name, request['body']['prompt'])
        self.assertEqual(request['reference_bindings'][-1]['reference_id'], self.scene.references[2].id)
        request['body']['prompt'] = 'silently changed'
        write_json(path, request)
        failed = runner.poll(job.id)
        self.assertEqual(failed.status, 'failed')
        self.assertIsNone(failed.result_id)


if __name__ == '__main__': unittest.main()
