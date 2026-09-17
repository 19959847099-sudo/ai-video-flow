import contextlib
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

from app.core import Store, write_json
from app.fal_adapter import ProductionRunner
from app.production import MockProviderAdapter
from integrations.production_bridge import execute
import test_production

ROOT = Path(__file__).resolve().parents[1]


class HarnessToolsTests(unittest.TestCase):
    setUp = test_production.ProductionTests.setUp
    tearDown = test_production.ProductionTests.tearDown

    def test_context_snapshot_result_media_and_human_gate(self):
        shot = self.shots[0]
        context = execute(self.store, 'get_shot_context', {'shot_id':shot.id})
        self.assertEqual(context['scene_state']['id'], shot.scene_state_id)
        self.assertEqual(len(context['character_references']), 2)
        self.assertEqual(len(context['scene_references']), 2)
        built = execute(self.store, 'build_generation_task', {'shot_id':shot.id})
        snapshot = self.store.path(f"tasks/{built['task_id']}/task.json").read_bytes()
        self.char.description = 'changed after building task'
        self.store.save_character(self.char)
        result = execute(self.store, 'dry_run_generation', {'execution_id':built['execution_id']})
        self.assertEqual(result['task_id'], built['task_id'])
        self.assertEqual(self.store.path(f"tasks/{built['task_id']}/task.json").read_bytes(), snapshot)
        media = execute(self.store, 'inspect_media', {'result_id':result['result_id']})
        self.assertEqual((media['duration'],media['width'],media['height'],media['codec_name']), (3,640,360,'h264'))
        self.assertIsNone(ProductionRunner(self.store).review(shot.id).selected_result_id)
        self.assertEqual(execute(self.store, 'dry_run_generation', {'execution_id':built['execution_id']}), result)

    def test_safety_allowlist_rejects_human_gate_live_mode_and_paths(self):
        for tool in ('select','reject','retry','shell','live_generation'):
            with self.subTest(tool=tool), self.assertRaises(ValueError): execute(self.store, tool, {})
        for args in ({'shot_id':self.shots[0].id,'provider':'live'}, {'shot_id':'../escape'},
                     {'shot_id':self.shots[0].id,'generation_description':'override'}):
            with self.assertRaises(ValueError): execute(self.store, 'build_generation_task', args)
        self.assertEqual(ProductionRunner(self.store).executions(), [])

    def test_missing_reference_and_wrong_execution_are_rejected(self):
        job = MockProviderAdapter(self.store).submit(self.shots[0].id)
        with self.assertRaisesRegex(ValueError, 'Only'):
            execute(self.store, 'dry_run_generation', {'execution_id':job.id})
        self.assertEqual(MockProviderAdapter(self.store).execution(job.id).status, 'pending')
        self.store.path(self.char.references[0].path).unlink()
        with self.assertRaises(OSError): execute(self.store, 'build_generation_task', {'shot_id':self.shots[1].id})

    def test_provider_failure_stops_chain_without_selection(self):
        built = execute(self.store, 'build_generation_task', {'shot_id':self.shots[0].id})
        write_json(self.store.path(f"tasks/{built['task_id']}/provider_exchange.json"),
                   dict(transport='fixture',api_called=False,step=0,scenario='missing_video',events=[]))
        with self.assertRaises(ValueError): execute(self.store, 'dry_run_generation', {'execution_id':built['execution_id']})
        runner = ProductionRunner(self.store)
        self.assertEqual(runner.execution(built['execution_id']).status, 'failed')
        self.assertIsNone(runner.review(self.shots[0].id).selected_result_id)

    def test_stdio_rejects_unknown_request_and_returns_structured_error(self):
        result = subprocess.run([sys.executable,'-m','integrations.production_bridge','--data-dir',str(self.store.root)],
            input=json.dumps({'tool':'select','arguments':{}}), capture_output=True, text=True, encoding='utf-8', cwd=ROOT)
        self.assertEqual(result.returncode, 1)
        reply = json.loads(result.stdout)
        self.assertFalse(reply['ok']); self.assertEqual(reply['network_attempts'],0)

    @unittest.skipUnless((ROOT/'integrations/dsh/node_modules/@deepseek-ai/dsh/lib/bin.js').is_file(), 'optional DSH runtime not installed')
    def test_official_dsh_cli_tool_events_network_lock_and_independence(self):
        from tools.run_harness import launch
        with contextlib.redirect_stdout(io.StringIO()):
            output = launch(self.shots[0].id, self.store.root, self.root/'dsh-evidence')
        trace = json.loads((output/'trace.json').read_text(encoding='utf-8'))
        self.assertEqual(trace['status'],'completed')
        self.assertEqual([s['tool'] for s in trace['steps']], [
            'get_shot_context','build_generation_task','dry_run_generation','inspect_media','get_shot_context'])
        self.assertEqual(len(trace['observed_tool_results']),5)
        self.assertTrue(trace['result']['human_gate_unchanged'])
        self.assertEqual(json.loads((output/'network-audit.json').read_text())['network_attempts'], [])
        moved = self.root/'standalone-data'; shutil.copytree(self.store.root,moved)
        result, task = ProductionRunner(Store(moved)).trace(trace['result']['result_id'])
        self.assertEqual(task.shot.id,self.shots[0].id)
        self.assertTrue((moved/result.path).is_file())


if __name__ == '__main__': unittest.main()
