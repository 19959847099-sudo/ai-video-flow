from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from app.preparation.production_gui import ReviewDot
from app.preparation.sound_gui import SoundDialog
from app.preparation.workspace import Workspace
from tests.test_preparation_sound import SCRIPT


class SoundGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp=TemporaryDirectory(); self.workspace=Workspace(Path(self.temp.name)/'project'); self.workspace.apply(SCRIPT)
        self.chapter=self.workspace.script.chapters[0]
        class Host(QWidget):
            pass
        self.host=Host();self.host.workspace=self.workspace;self.host.current_chapter=lambda:self.chapter;self.host.refresh=lambda:None;self.host.resize(1300,860)

    def tearDown(self):self.host.close();self.temp.cleanup()

    def test_dialogue_generate_review_current_timing_subtitle_and_restart(self):
        dialog=SoundDialog(self.host,self.chapter.shots[0].id);dialog.show();QTest.qWait(30)
        self.assertIn('林夏',dialog.speaker.text());self.assertIn('这把伞',dialog.words.text())
        dialog.generate_current();self.assertIsNotNone(dialog.worker);self.assertTrue(dialog.worker.wait(20000));self.app.processEvents();dialog.refresh_items()
        self.assertEqual(dialog.candidates.count(),3)
        cid=dialog.selected_candidate();dialog.production.review(cid,'green');dialog.selection_changed();dialog.bind()
        row=dialog.selected();self.assertEqual(dialog.sound.current_dialogue(row[1]),cid)
        dialog.strategy.setCurrentIndex(dialog.strategy.findData('independent'))
        dialog.start.setValue(.6);dialog.volume.setValue(.75);dialog.apply_audio_settings()
        dialog.subtitle_text.setText('这把伞，\n有人找过吗？');dialog.subtitle_start.setValue(.65);dialog.subtitle_end.setValue(1.8);dialog.save_subtitle()
        restored=SoundDialog(self.host,self.chapter.shots[0].id)
        state=restored.sound.state(row[1]);subtitle=restored.sound.subtitle(row[1])
        self.assertEqual(state.strategy,'independent');self.assertAlmostEqual(state.start,.6)
        self.assertTrue(subtitle.manual_text);self.assertIn('有人找过吗',subtitle.display_text)
        restored.close();dialog.close()

    def test_background_and_review_signal_colors(self):
        dialog=SoundDialog(self.host,self.chapter.shots[0].id);dialog.show();QTest.qWait(20)
        for index in range(dialog.items.count()):
            if str(dialog.items.item(index).data(256)).startswith('background:'):
                dialog.items.setCurrentRow(index);break
        self.assertEqual(dialog.speaker.text(),'背景音');self.assertFalse(dialog.strategy.isVisible())
        self.assertEqual(ReviewDot.COLORS,{'green':'#42d684','yellow':'#f2b83f','red':'#f0645d'})
        self.assertTrue(all(dot.toolTip()=='' for dot in dialog.dots.values()))
        dialog.close()


if __name__=='__main__':unittest.main()
