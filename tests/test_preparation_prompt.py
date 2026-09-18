"""Focused Prompt Draft contract tests: derived state, Current Binding, edit and staleness."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from PIL import Image

from app.preparation.prompt import context, create_draft, get_draft, save_draft, targets
from app.preparation.production import ProductionService
from app.preparation.workspace import Workspace


SOURCE = """片/名称
01/章节/雨夜
001/入店
林夏/老年/灰色外套/低声
雨夜街角/风声
镜头：
从门内缓慢后退。
动作：
林夏举起【红伞】。
表演：
犹豫后开口。
对白：
林夏：雨还会下吗？
002/离开
街角/-
动作：
离开。
"""


class PromptDraftTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.root = Path(self.temp.name) / 'project'
        self.workspace = Workspace(self.root)
        self.assertTrue(self.workspace.apply(SOURCE).valid)
        self.shots = self.workspace.script.chapters[0].shots
        self.image_req = next(r for r in self.workspace.script.requirements if r.name == '红伞')
        self.voice_req = next(r for r in self.workspace.script.requirements if r.kind == 'voice')

    def tearDown(self):
        self.temp.cleanup()

    def picture(self, name, color):
        path = Path(self.temp.name) / name
        Image.new('RGB', (100, 70), color).save(path)
        return path

    def test_three_media_targets_and_separate_editable_persistent_drafts(self):
        shot = self.shots[0]
        before = deepcopy({k: v for k, v in self.workspace.state.items()
                           if k not in ('prompt_drafts', 'updated_at')})
        image = create_draft(self.workspace, shot.id, 'image', self.image_req.id)
        video = create_draft(self.workspace, shot.id, 'video')
        audio = create_draft(self.workspace, shot.id, 'audio', self.voice_req.id)
        self.assertEqual([d['media'] for d in (image, video, audio)], ['image', 'video', 'audio'])
        self.assertEqual(len({d['key'] for d in (image, video, audio)}), 3)
        self.assertEqual({d['project_id'] for d in (image, video, audio)},
                         {self.workspace.state['project_id']})
        self.assertEqual({d['chapter_id'] for d in (image, video, audio)},
                         {self.workspace.script.chapters[0].id})
        self.assertIn('红伞', image['text'])
        self.assertIn('从门内缓慢后退', video['text'])
        self.assertIn('雨还会下吗', audio['text'])
        self.assertNotIn('灰色外套', audio['text'])
        self.assertEqual(image['source'], 'deterministic')
        self.assertFalse(image['edited'])
        self.assertEqual(before, {k: v for k, v in self.workspace.state.items()
                                  if k not in ('prompt_drafts', 'updated_at')})
        save_draft(self.workspace, shot.id, 'image', self.image_req.id, '人工调整：一把破损红伞', '避免多余人物')
        with self.assertRaisesRegex(ValueError, '明确确认'):
            create_draft(self.workspace, shot.id, 'image', self.image_req.id)
        second = create_draft(self.workspace, self.shots[1].id, 'image')
        self.assertNotEqual(second['key'], image['key'])
        restored = Workspace(self.root)
        draft, _, stale = get_draft(restored, shot.id, 'image', self.image_req.id)
        self.assertEqual(draft['text'], '人工调整：一把破损红伞')
        self.assertEqual(draft['constraints'], '避免多余人物')
        self.assertTrue(draft['edited'])
        self.assertFalse(stale)
        self.assertEqual(get_draft(restored, shot.id, 'video')[0]['text'], video['text'])
        self.assertEqual(get_draft(restored, shot.id, 'audio', self.voice_req.id)[0]['text'], audio['text'])
        self.assertNotEqual(get_draft(restored, self.shots[1].id, 'image')[0]['key'], image['key'])

    def test_current_binding_not_other_green_and_context_change(self):
        shot = self.shots[0]
        service = ProductionService(self.workspace)
        first = service.import_candidate(self.image_req.id, shot.id, self.picture('first.png', 'red'))
        second = service.import_candidate(self.image_req.id, shot.id, self.picture('second.png', 'blue'))
        service.review(first.id, 'green')
        service.review(second.id, 'green')
        service.bind(first.id)
        draft = create_draft(self.workspace, shot.id, 'video')
        self.assertIn(first.media_path, draft['text'])
        self.assertNotIn(second.media_path, draft['text'])
        self.assertEqual([r['candidate_id'] for r in context(self.workspace, shot.id, 'video')['references']
                          if r['requirement_id'] == self.image_req.id], [first.id])
        service.bind(second.id)
        old, _, stale = get_draft(self.workspace, shot.id, 'video')
        self.assertTrue(stale)
        self.assertEqual(old['text'], draft['text'])
        rebuilt = create_draft(self.workspace, shot.id, 'video', replace=True)
        self.assertIn(second.media_path, rebuilt['text'])
        self.assertNotIn(first.media_path, rebuilt['text'])
        self.assertFalse(get_draft(self.workspace, shot.id, 'video')[2])
        media = self.workspace.path(second.media_path)
        Image.new('RGB', (100, 70), 'green').save(media)
        self.workspace.scan()
        changed = context(self.workspace, shot.id, 'video')
        self.assertIn('已变更待确认', '\n'.join(changed['issues']))
        self.assertFalse(any(r['requirement_id'] == self.image_req.id for r in changed['references']))
        self.assertTrue(get_draft(self.workspace, shot.id, 'video')[2])

    def test_free_missing_goal_and_script_change_are_honest(self):
        shot = self.shots[0]
        self.workspace.set_reference_required(self.voice_req.id, False)
        voice = context(self.workspace, shot.id, 'audio', self.voice_req.id)
        self.assertIn('人物音声', '\n'.join(voice['free']))
        self.assertFalse(voice['references'])
        audio = create_draft(self.workspace, shot.id, 'audio', self.voice_req.id)
        self.assertIn('低声', audio['text'])
        self.assertIn('无固定参照素材', audio['text'])
        image = create_draft(self.workspace, shot.id, 'image', self.image_req.id)
        self.assertIn('红伞', image['text'])
        self.assertNotIn('红伞：缺失', image['text'])
        video = create_draft(self.workspace, shot.id, 'video')
        self.assertIn('红伞：缺失', video['text'])
        self.assertIn('不可视作已提供素材', video['text'])
        self.workspace.apply(SOURCE.replace('从门内缓慢后退', '从门内快速后退'))
        self.assertTrue(get_draft(self.workspace, shot.id, 'video')[2])
        self.assertEqual(get_draft(self.workspace, shot.id, 'video')[0]['text'], video['text'])
        self.assertIn((self.image_req.id, '关键物件 · 红伞'), targets(self.workspace, shot.id, 'image'))

class PromptWidgetTests(unittest.TestCase):
    def test_switching_target_saves_the_original_draft(self):
        from unittest.mock import patch
        from PySide6.QtWidgets import QApplication, QMessageBox, QWidget
        from app.preparation.prompt_gui import PromptDialog

        app = QApplication.instance() or QApplication([])
        with TemporaryDirectory() as tmp:
            workspace = Workspace(Path(tmp) / 'project')
            workspace.apply(SOURCE)
            chapter = workspace.script.chapters[0]
            shot = chapter.shots[0]

            class Host(QWidget):
                def __init__(self):
                    super().__init__()
                    self.workspace = workspace
                    self.resize(1250, 850)

                def current_chapter(self):
                    return chapter

            host = Host()
            dialog = PromptDialog(host, shot.id)
            dialog.show()
            dialog.create()
            original_key = dialog.current_key
            dialog.text.setPlainText('第一目标的人工文本')
            with patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.Save):
                dialog.target.setCurrentIndex(1)
            self.assertEqual(workspace.state['prompt_drafts'][original_key]['text'], '第一目标的人工文本')
            self.assertNotEqual(dialog.current_key, original_key)
            dialog.close()
            host.close()
            app.processEvents()

if __name__ == '__main__':
    unittest.main()
