import json
import shutil
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from pydantic import ValidationError
from app.core import Character, Look, Shot, Store, DummyProviderAdapter


class MainChainTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.store = Store(self.base / "data")
        self.refs = []
        for i, color in enumerate(["red", "blue", "green"]):
            p = self.base / f"{i}.png"
            Image.new("RGB", (40, 40), color).save(p)
            self.refs.append(self.store.import_reference(p))
        self.char = Character(name="测试林夏", identity="稳定身份", is_example=True,
            references=self.refs, identity_reference_ids=[self.refs[0].id],
            looks=[Look(name="日常", reference_ids=[self.refs[1].id]),
                   Look(name="雨夜", reference_ids=[self.refs[2].id])])
        self.store.save_character(self.char)
        self.shots = [Shot(description=f"示例镜头 {i}", character_id=self.char.id,
            look_id=look.id, requirements="中近景", generation_description="看向街道", is_example=True)
            for i, look in enumerate(self.char.looks)]
        for shot in self.shots: self.store.save_shot(shot)

    def tearDown(self):
        self.tmp.cleanup()

    def test_reuse_and_look_reference_isolation(self):
        for i, shot in enumerate(self.shots):
            task, folder = self.store.generate(shot.id, DummyProviderAdapter())
            self.assertEqual(task.character.id, self.char.id)
            self.assertEqual(task.look.id, shot.look_id)
            self.assertEqual([r.id for r in task.references], [self.refs[0].id, self.refs[i+1].id])
            self.assertTrue(json.loads((folder / "dummy_request.json").read_text(encoding="utf-8"))['simulation_only'])
            self.assertNotIn("provider", task.model_dump())

    def test_restart_and_relocation_without_originals(self):
        moved = self.base / "moved"
        shutil.copytree(self.store.root, moved)
        for p in self.base.glob("*.png"): p.unlink()
        other = Store(moved)
        self.assertEqual(len(other.characters()), 1)
        self.assertEqual(len(other.shots()), 2)
        task, _ = other.generate(self.shots[1].id, DummyProviderAdapter())
        self.assertTrue(all(other.path(r.path).exists() for r in task.references))

    def test_dedup(self):
        ref = self.store.import_reference(self.base / "0.png")
        self.assertEqual(ref.path, self.refs[0].path)
        self.assertEqual(len(list(self.store.path("assets").iterdir())), 3)

    def test_invalid_relations_and_input(self):
        invalid = self.shots[0].model_copy(update={"look_id": "wrong"})
        with self.assertRaises(ValueError): self.store.save_shot(invalid)
        with self.assertRaises(ValidationError): Character(name=" ", identity="test")
        payload = self.char.model_dump()
        payload['looks'][0]['reference_ids'] = ['missing']
        with self.assertRaises(ValidationError): Character.model_validate(payload)
        with self.assertRaises(ValueError): self.store.path("../outside")
        with self.assertRaises(ValueError): self.store.character("../outside")

    def test_task_snapshot_survives_character_edits_and_ref_removal(self):
        task, folder = self.store.generate(self.shots[0].id, DummyProviderAdapter())
        original = (folder / "task.json").read_bytes()
        self.char.name = "新名字"
        self.char.references = self.refs[1:]
        self.char.identity_reference_ids = []
        self.store.save_character(self.char)
        self.assertEqual((folder / "task.json").read_bytes(), original)
        self.assertTrue(self.store.path(task.references[0].path).exists())

    def test_missing_or_changed_media_blocks_task(self):
        p = self.store.path(self.refs[0].path)
        p.write_bytes(b"changed")
        with self.assertRaises(ValueError): self.store.task(self.shots[0].id)
        p.unlink()
        with self.assertRaises(FileNotFoundError): self.store.task(self.shots[0].id)

    def test_no_reference_blocks_task(self):
        self.char.identity_reference_ids = []
        self.char.looks[0].reference_ids = []
        self.store.save_character(self.char)
        with self.assertRaises(ValueError): self.store.task(self.shots[0].id)


if __name__ == "__main__":
    unittest.main()

