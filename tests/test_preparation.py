"""Focused V0.2 risks; no legacy media or full GUI regression."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from uuid import uuid4

from PIL import Image

from app.preparation.script import parse, split_fields, requirement_id
from app.preparation.workspace import Workspace

SAMPLE = '''测试影片/名称
01/章节/雨夜
001/进入
【林夏/-/雨衣】/低声
店员/老年/围裙/-
【便利店/雨夜】/雨声
镜头：
【后退/跟拍】 保持中景。
动作：
拿着【红伞.破损】，桌上有普通水杯。
对白：
林夏：你好。
连续性：
右手有胶布。
002/离开
林夏/-/-/-
清晨街道/-
备注：
输出/原音/不拆/字段
02/集数
001/归还
【林夏/-/雨衣】/-
镜头：
固定镜头。
动作：
留下【红伞.破损】。
'''


class ParserTests(unittest.TestCase):
    def setUp(self): self.pid = uuid4().hex

    def test_frozen_syntax_context_and_natural_language(self):
        parsed = parse(SAMPLE, self.pid)
        self.assertTrue(parsed.valid, parsed.diagnostics)
        shot = parsed.chapters[0].shots[0]
        self.assertEqual(len(shot.cast), 2)
        self.assertEqual(shot.cast[0].complete_visual, '林夏/-/雨衣')
        self.assertEqual(shot.ambience, '雨声')
        requirements = {(r.kind, r.name) for r in parsed.requirements}
        self.assertIn(('voice', '林夏/低声'), requirements)
        self.assertNotIn(('voice', '店员/-'), requirements)
        self.assertIn(('video_reference', '后退/跟拍'), requirements)
        self.assertIn(('prop', '红伞.破损'), requirements)
        self.assertNotIn(('environment', '清晨街道'), requirements)
        self.assertNotIn(('prop', '普通水杯'), requirements)
        self.assertEqual(parsed.chapters[0].shots[1].sections['备注'], '输出/原音/不拆/字段')
        self.assertEqual(split_fields('【便利店/雨夜】/雨声'), ['【便利店/雨夜】', '雨声'])
        self.assertEqual(len(next(r for r in parsed.requirements if r.kind == 'prop').usages), 2)

    def test_same_value_positions_and_no_voice_do_not_disable_ambience(self):
        text = '片/名称\n01/集数\n001/镜\n人物/老年/衣服/老年\n另一个/-/-/-\n街道/雨声'
        p = parse(text, self.pid)
        self.assertTrue(p.valid, p.diagnostics)
        self.assertIn(('age', '人物/老年'), {(r.kind, r.name) for r in p.requirements})
        self.assertIn(('voice', '人物/老年'), {(r.kind, r.name) for r in p.requirements})
        self.assertEqual(p.chapters[0].shots[0].ambience, '雨声')

    def test_ids_survive_title_edits_reorder_and_separate_chapters(self):
        p = parse(SAMPLE, self.pid)
        edited = parse(SAMPLE.replace('001/进入', '001/推门进入'), self.pid)
        self.assertEqual(p.chapters[0].shots[0].id, edited.chapters[0].shots[0].id)
        self.assertNotEqual(p.chapters[0].shots[0].id, p.chapters[1].shots[0].id)
        text = '片/名称\n01/集数\n002/后\n动作：\n走。\n001/前\n动作：\n站。'
        a = parse(text, self.pid)
        b = parse(text.replace('002/后', '003/后'), self.pid)
        self.assertEqual(a.chapters[0].shots[1].id, b.chapters[0].shots[1].id)

    def test_errors_have_source_locations_and_never_guess(self):
        invalid_lines = ['【人/老/衣/声】', '人/老/衣', '【人/老/衣】', '人//衣/声',
                         '【人/老/衣】/声/多余', '【背景/雨夜/extra/voice】/-', '动作：【没闭合',
                         '动作：【【嵌套】】', '动作：【】']
        for line in invalid_lines:
            with self.subTest(line=line):
                parsed = parse('片/名称\n01/集数\n001/镜\n' + line, self.pid)
                self.assertFalse(parsed.valid)
                self.assertIn(4, [d.line for d in parsed.diagnostics])

    def test_duplicate_numbers_and_late_structural_lines_rejected(self):
        for suffix in ['\n001/又一镜', '\n01/集数', '\n动作：\n走。\n人物：人/-/-/-']:
            self.assertFalse(parse('片/名称\n01/集数\n001/镜' + suffix, self.pid).valid)


class MappingTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.root = Path(self.temp.name) / 'project'
        self.w = Workspace(self.root)
        self.w.apply(SAMPLE)
        self.rid = requirement_id('prop', '红伞.破损')

    def tearDown(self): self.temp.cleanup()

    def image(self, relative='prop/红伞.破损.png', color='red'):
        path = self.root / 'library' / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new('RGB', (40, 40), color).save(path)
        return path

    def report(self, rid=None): return next(r for r in self.w.report() if r['requirement']['id'] == (rid or self.rid))

    def test_missing_exact_match_context_isolation_and_shared_usage(self):
        self.assertEqual(self.report()['status'], 'missing')
        self.image('character/红伞.破损.png')
        self.w.scan()
        self.assertEqual(self.report()['status'], 'missing')
        self.image()
        self.w.scan()
        self.assertEqual(self.report()['status'], 'resolved')
        self.assertEqual(len(self.w.affected(self.report()['asset']['id'])), 2)
        self.assertEqual(len(self.w.state['bindings']), 1)

    def test_ambiguous_same_name_requires_explicit_mapping(self):
        self.image()
        self.image('prop/红伞.破损.jpg', 'blue')
        self.w.scan()
        report = self.report()
        self.assertEqual(report['status'], 'unresolved')
        self.assertEqual(len(report['candidates']), 2)
        self.w.bind(self.rid, report['candidates'][1]['id'])
        self.assertEqual(self.report()['status'], 'resolved')
        self.w.scan()
        self.assertEqual(self.report()['status'], 'resolved')

    def test_new_ambiguity_does_not_silently_keep_auto_choice(self):
        self.image()
        self.w.scan()
        self.image('prop/红伞.破损.jpg', 'blue')
        self.w.scan()
        self.assertEqual(self.report()['status'], 'unresolved')

    def test_unique_rename_preserves_identity_binding_and_history(self):
        path = self.image()
        self.w.scan()
        before = self.report()['asset']
        path.rename(path.with_name('改名后的伞.png'))
        self.w.scan()
        after = self.report()['asset']
        self.assertEqual(after['id'], before['id'])
        self.assertEqual(self.report()['status'], 'resolved')
        self.assertIn('改名后的伞', after['aliases'])
        event = next(e for e in self.w.state['events'] if e['kind'] == 'rename')
        self.assertEqual(len(event['shots']), 2)
        self.assertTrue(self.w.path(before['snapshot']).is_file())

    def test_replacement_requires_confirmation_retains_previous_bytes_and_impacts(self):
        self.image()
        self.w.scan()
        old = deepcopy(self.report())
        self.image(color='blue')
        self.w.scan()
        changed = self.report()
        self.assertEqual(changed['status'], 'changed')
        self.assertEqual(changed['binding']['sha256'], old['binding']['sha256'])
        with Image.open(self.w.path(old['asset']['snapshot'])) as snapshot:
            self.assertEqual(snapshot.getpixel((0, 0)), (255, 0, 0))
        self.assertEqual(len(self.w.state['events'][-1]['shots']), 2)
        self.w.bind(self.rid, changed['asset']['id'])
        self.assertEqual(self.report()['status'], 'resolved')
        self.assertEqual(len(self.report()['asset']['versions']), 2)

    def test_ambiguous_rename_never_merges_two_assets(self):
        path = self.image()
        self.w.scan()
        path.rename(path.with_name('a.png'))
        shutil.copy2(path.with_name('a.png'), path.with_name('b.png'))
        self.w.scan()
        self.assertEqual(self.report()['status'], 'unresolved')
        self.assertEqual(len(self.report()['candidates']), 2)
        self.assertTrue(self.report()['asset']['missing'])
        self.assertEqual(len(self.w.state['assets']), 3)

    def test_deleted_and_restored_file_keeps_id_and_binding(self):
        path = self.image()
        self.w.scan()
        aid = self.report()['asset']['id']
        path.unlink()
        self.w.scan()
        self.assertEqual(self.report()['status'], 'missing')
        self.image()
        self.w.scan()
        self.assertEqual(self.report()['status'], 'resolved')
        self.assertEqual(aid, self.report()['asset']['id'])

    def test_invalid_draft_is_saved_but_never_replaces_valid_production(self):
        old = self.w.script.model_dump()
        parsed = self.w.apply(SAMPLE.replace('【林夏/-/雨衣】/低声', '【林夏/-/雨衣/低声】'))
        self.assertFalse(parsed.valid)
        restored = Workspace(self.root)
        self.assertEqual(restored.script.model_dump(), old)
        self.assertFalse(restored.draft_result.valid)
        self.assertFalse(restored.chapter_status(old['chapters'][0]['id'])['ready'])

    def test_relocation_preserves_relations_selection_and_draft(self):
        self.image()
        self.w.scan()
        aid = self.report()['asset']['id']
        self.w.bind(self.rid, aid)
        self.w.set_ui(chapter_id=self.w.script.chapters[0].id, shot_id=self.w.script.chapters[0].shots[0].id)
        dest = Path(self.temp.name) / 'moved'
        shutil.copytree(self.root, dest)
        restored = Workspace(dest)
        restored.scan()
        self.assertEqual(restored.state['bindings'], self.w.state['bindings'])
        self.assertEqual(restored.state['ui'], self.w.state['ui'])
        self.assertEqual(restored.state['draft'], SAMPLE)
        for a in restored.state['assets'].values(): self.assertTrue(restored.path(a['snapshot']).is_file())

    def test_import_auto_names_and_binds_without_manual_file_naming(self):
        external = Path(self.temp.name) / 'arbitrary.png'
        Image.new('RGB', (20, 20), 'green').save(external)
        aid = self.w.import_asset(self.rid, external)
        self.assertEqual(self.report()['asset']['id'], aid)
        self.assertEqual(self.report()['status'], 'resolved')
        external.unlink()
        self.w.scan()
        self.assertEqual(self.report()['status'], 'resolved')
        self.assertEqual(self.report()['asset']['name'], '红伞.破损')

    def test_bad_image_wrong_media_and_changed_between_scan_bind_are_blocked(self):
        path = self.image()
        path.write_bytes(b'not an image')
        self.w.scan()
        self.assertEqual(self.report()['status'], 'unresolved')
        with self.assertRaises(ValueError): self.w.bind(self.rid, self.report()['candidates'][0]['id'])
        self.image()
        self.w.scan()
        aid = self.report()['asset']['id']
        self.image(color='blue')
        with self.assertRaisesRegex(ValueError, '扫描'): self.w.bind(self.rid, aid)
        with self.assertRaises(ValueError): self.w.path('../escape')

    def test_script_change_keeps_archived_usage_and_logs_only_affected_shots(self):
        self.image()
        self.w.scan()
        original = self.w.script.chapters[0].shots[0].id
        self.w.apply(SAMPLE.replace('001/进入', '001/推门'))
        self.assertIn(original, self.w.state['events'][-1]['shots'])
        self.assertEqual(self.w.script.chapters[0].shots[0].id, original)
        self.w.apply(SAMPLE.replace('【红伞.破损】', '一把普通伞'))
        self.image(color='blue')
        self.w.scan()
        self.assertIn(original, self.w.state['events'][-1]['shots'])

    def test_manifest_write_failure_does_not_mutate_committed_state(self):
        before = deepcopy(self.w.state)
        disk = self.w.manifest.read_bytes()
        with patch('app.preparation.workspace.write_json', side_effect=OSError('disk full')):
            with self.assertRaises(OSError): self.w.apply(SAMPLE.replace('进入', '新标题'))
        self.assertEqual(self.w.state, before)
        self.assertEqual(self.w.manifest.read_bytes(), disk)

    def test_scan_failure_and_draft_write_failure_preserve_manifest(self):
        self.image()
        before = deepcopy(self.w.state)
        disk = self.w.manifest.read_bytes()
        with patch.object(self.w, '_inspect', side_effect=OSError('file busy')):
            with self.assertRaises(OSError): self.w.scan()
        self.assertEqual(self.w.state, before)
        self.assertEqual(self.w.manifest.read_bytes(), disk)
        with patch('app.preparation.workspace.write_json', side_effect=OSError('disk full')):
            with self.assertRaises(OSError): self.w.save_draft('new draft')
        self.assertEqual(self.w.state, before)

    def test_unchanged_media_does_not_repeat_media_probe(self):
        from app.preparation.workspace import sha
        path = self.root / 'library' / 'voice' / 'sample.wav'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'fixture-probe-input')
        with patch('app.rough_cut.probe', return_value={'duration': 1}) as probe:
            self.w.scan()
            self.assertEqual(probe.call_count, 1)
            self.w.scan()
            self.assertEqual(probe.call_count, 1)
            path.write_bytes(b'changed-fixture-probe-input')
            self.w.scan()
            self.assertEqual(probe.call_count, 2)

    def test_ready_is_per_chapter_and_unapplied_draft_blocks_it(self):
        self.w.apply('片/名称\n01/集数\n001/无人\n街道/雨声\n镜头：\n固定远景。\n02/集数\n001/物件\n动作：\n【缺失】')
        chapters = self.w.script.chapters
        self.assertTrue(self.w.chapter_status(chapters[0].id)['ready'])
        self.assertFalse(self.w.chapter_status(chapters[1].id)['ready'])
        self.w.save_draft(self.w.state['draft'] + '\n还有修改。')
        self.assertFalse(self.w.chapter_status(chapters[0].id)['ready'])


if __name__ == '__main__': unittest.main()
