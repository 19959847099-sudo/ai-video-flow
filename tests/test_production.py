import hashlib
import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from app.core import Character, Look, Scene, SceneState, Shot, Store, GenerationTask, DummyProviderAdapter
from app.production import MockProviderAdapter, probe_video


class ProductionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = Store(self.root / 'data')
        refs = []
        for i in range(6):
            path = self.root / f'{i}.png'
            Image.new('RGB', (40, 40), (i * 35, 50, 90)).save(path)
            refs.append(self.store.import_reference(path))
        self.char = Character(name='测试角色', identity='身份', is_example=True,
            references=refs[:3], identity_reference_ids=[refs[0].id],
            looks=[Look(name='日常', reference_ids=[refs[1].id]), Look(name='雨夜', reference_ids=[refs[2].id])])
        self.scene = Scene(name='测试场景', identity='门口朝北', is_example=True,
            references=refs[3:], identity_reference_ids=[refs[3].id],
            states=[SceneState(name='白天', environment='阳光', reference_ids=[refs[4].id]),
                    SceneState(name='雨夜', environment='雨水', reference_ids=[refs[5].id])])
        self.store.save_character(self.char)
        self.store.save_scene(self.scene)
        self.shots = [Shot(schema_version='0.2', description=f'测试镜头 {i}', character_id=self.char.id,
            look_id=self.char.looks[i].id, scene_id=self.scene.id, scene_state_id=self.scene.states[i].id,
            requirements='中近景', generation_description='转头', is_example=True) for i in range(2)]
        for shot in self.shots: self.store.save_shot(shot)
        self.provider = MockProviderAdapter(self.store)

    def tearDown(self):
        self.temp.cleanup()

    def complete(self, shot_id, **kwargs):
        job = self.provider.submit(shot_id, **kwargs)
        self.assertEqual(job.status, 'pending')
        self.assertEqual(self.provider.poll(job.id).status, 'processing')
        job = self.provider.poll(job.id)
        self.assertEqual(job.status, 'completed', job.error)
        self.assertEqual(job.history, ['pending', 'processing', 'completed'])
        return job

    def test_scene_references_and_neutral_prompt(self):
        for i, shot in enumerate(self.shots):
            task = self.store.task(shot.id)
            self.assertEqual(task.scene_state, self.scene.states[i])
            self.assertEqual([r.id for r in task.scene_references],
                [self.scene.references[0].id, self.scene.references[i + 1].id])
            self.assertEqual(len(task.references), 2)
            self.assertIn(self.scene.states[i].environment, task.final_prompt)
            self.assertIn(shot.generation_description, task.final_prompt)
            request = DummyProviderAdapter().prepare(task, self.store.root)
            self.assertEqual(len(request['input']['images']), 4)
            self.assertNotIn('provider', task.model_dump())

    def test_scene_invalid_relations_block_save(self):
        with self.assertRaises(ValueError):
            Shot.model_validate({**self.shots[0].model_dump(), 'scene_state_id': None})
        with self.assertRaises(ValueError):
            self.store.save_shot(self.shots[0].model_copy(update={'scene_state_id': 'wrong'}))
        broken = self.scene.model_dump()
        broken['states'][0]['reference_ids'] = ['wrong']
        with self.assertRaises(ValueError): Scene.model_validate(broken)
        self.scene.references[0].path = '../outside.png'
        with self.assertRaises(ValueError): self.store.save_scene(self.scene)

    def test_historical_snapshots_survive_source_edit(self):
        task, folder = self.store.generate(self.shots[0].id, DummyProviderAdapter())
        before = (folder / 'task.json').read_bytes()
        self.char.description = '修改角色描述'
        self.scene.description = '修改场景描述'
        self.store.save_character(self.char)
        self.store.save_scene(self.scene)
        self.assertEqual((folder / 'task.json').read_bytes(), before)
        restored = self.provider.task_snapshot(task.id)
        self.assertNotEqual(restored.scene.description, self.scene.description)
        self.assertNotEqual(restored.character.description, self.char.description)

    def test_media_retry_selection_trace_and_relocation(self):
        first = self.complete(self.shots[0].id)
        self.assertIsNone(self.provider.review(first.shot_id).selected_result_id)
        result, task = self.provider.trace(first.result_id)
        self.assertGreater(probe_video(self.store.path(result.path))['duration'], 0)
        self.provider.reject(first.shot_id, result.id, '测试动作不合适')
        second = self.complete(first.shot_id, retry_of=result.id, generation_description='再次转头并停顿')
        self.assertNotEqual(first.task_id, second.task_id)
        self.assertEqual(second.retry_of, first.result_id)
        self.assertEqual(second.take_number, 2)
        self.provider.select(second.shot_id, second.result_id)
        moved = self.root / 'moved'
        shutil.copytree(self.store.root, moved)
        provider = MockProviderAdapter(Store(moved))
        selected = provider.review(second.shot_id).selected_result_id
        self.assertEqual(selected, second.result_id)
        result, task = provider.trace(selected)
        self.assertEqual(task.shot.generation_description, '再次转头并停顿')
        self.assertIn('再次转头并停顿', task.final_prompt)
        self.assertEqual(task.scene.id, self.scene.id)
        self.assertTrue((moved / result.path).is_file())
        self.assertEqual(len(provider.executions(second.shot_id)), 2)

    def test_invalid_select_retry_and_duplicate_submit(self):
        job = self.provider.submit(self.shots[0].id)
        with self.assertRaises(ValueError): self.provider.submit(job.shot_id)
        self.provider.poll(job.id)
        job = self.provider.poll(job.id)
        with self.assertRaises(ValueError): self.provider.select(self.shots[1].id, job.result_id)
        with self.assertRaises(ValueError): self.provider.submit(job.shot_id, retry_of=job.result_id)
        self.provider.select(job.shot_id, job.result_id)
        self.provider.reject(job.shot_id, job.result_id)
        self.assertIsNone(self.provider.review(job.shot_id).selected_result_id)

    def test_pending_processing_restart_and_failure(self):
        job = self.provider.submit(self.shots[0].id)
        self.provider = MockProviderAdapter(Store(self.store.root))
        self.provider.poll(job.id)
        self.provider = MockProviderAdapter(Store(self.store.root))
        with patch.object(self.provider, 'make_video', side_effect=ValueError('测试编码失败')):
            job = self.provider.poll(job.id)
        self.assertEqual(job.status, 'failed')
        self.assertIn('测试编码失败', job.error)
        self.assertIsNone(job.result_id)
        # The failed execution remains counted, and a new execution can be submitted.
        next_job = self.provider.submit(job.shot_id)
        self.assertEqual(next_job.take_number, 2)

    def test_legacy_records_load_without_migration(self):
        legacy = self.shots[0].model_dump()
        legacy.pop('scene_id')
        legacy.pop('scene_state_id')
        legacy['schema_version'] = '0.1'
        shot = Shot.model_validate(legacy)
        self.store.save_shot(shot)
        task, _ = self.store.generate(shot.id, DummyProviderAdapter())
        self.assertIsNone(task.scene)
        with self.assertRaises(ValueError): self.provider.submit(shot.id)

    def test_scene_missing_image_and_invalid_snapshot(self):
        task = self.store.task(self.shots[0].id)
        broken = task.model_dump()
        broken['scene_state'] = self.scene.states[1].model_dump()
        with self.assertRaises(ValueError): GenerationTask.model_validate(broken)
        self.store.path(self.scene.references[0].path).unlink()
        with self.assertRaises(FileNotFoundError): self.store.task(self.shots[0].id)


if __name__ == '__main__':
    unittest.main()
