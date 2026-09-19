from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPlainTextEdit, QWidget

from app.preparation.creative_gui import CreativeDialog
from app.preparation.workspace import Workspace
from tests.test_preparation_sound import SCRIPT

class Host(QWidget):
    def __init__(self, workspace):
        super().__init__();self.workspace=workspace;self.loading=False
        self.editor=QPlainTextEdit();self.editor.setPlainText(workspace.state["draft"])
        script=workspace.script
        self.chapter_id=script.chapters[0].id if script else None
        self.shot_id=script.chapters[0].shots[0].id if script else None
        self.refresh_count=0;self.resize(1480,940)
    def current_chapter(self):
        return next((c for c in self.workspace.script.chapters if c.id==self.chapter_id),None) if self.workspace.script else None
    def refresh(self):self.refresh_count+=1

class CreativeGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        self.temp=TemporaryDirectory();self.workspace=Workspace(Path(self.temp.name)/"project")
        self.workspace.apply(SCRIPT);self.host=Host(self.workspace)
    def tearDown(self):self.host.close();self.temp.cleanup()
    def wait_worker(self,dialog):
        self.assertIsNotNone(dialog.worker);self.assertTrue(dialog.worker.wait(10000))
        self.app.processEvents();dialog.refresh()
    def test_discussion_edit_continue_diff_and_apply(self):
        dialog=CreativeDialog(self.host);dialog.show();QTest.qWait(30)
        revision=self.workspace.script.revision
        dialog.task.setCurrentIndex(dialog.task.findData("project_discussion"))
        dialog.input.setPlainText("How is the pacing?");dialog.send();self.wait_worker(dialog)
        self.assertIsNone(dialog.service.active_proposal(dialog.conversation["id"]))
        self.assertEqual(self.workspace.script.revision,revision)
        dialog.task.setCurrentIndex(dialog.task.findData("edit_shot"))
        dialog.input.setPlainText("Make this shot quieter");dialog.send();self.wait_worker(dialog)
        first=dialog.service.active_proposal(dialog.conversation["id"])
        self.assertIsNotNone(first);self.assertIn("FIXTURE",dialog.diff.toPlainText())
        dialog.input.setPlainText("Make the ending restrained");dialog.continue_editing();self.wait_worker(dialog)
        second=dialog.service.active_proposal(dialog.conversation["id"])
        self.assertNotEqual(first.id,second.id);self.assertIn("Make this shot quieter",second.draft)
        dialog.apply()
        self.assertNotEqual(self.workspace.script.revision,revision)
        self.assertGreater(self.host.refresh_count,0)
        self.assertEqual(len(self.workspace.state["runtime_jobs"]),0)
        dialog.resize(960,650);QTest.qWait(20)
        self.assertGreaterEqual(dialog.width(),960);dialog.close()
    def test_idea_new_project_and_fixture_label(self):
        workspace=Workspace(Path(self.temp.name)/"new");host=Host(workspace)
        dialog=CreativeDialog(host);dialog.show();QTest.qWait(20)
        self.assertEqual(dialog.task.currentData(),"idea_to_script")
        self.assertIn("ZERO-CALL",dialog.model.currentText())
        dialog.input.setPlainText("A quiet encounter at midnight");dialog.send();self.wait_worker(dialog)
        proposal=dialog.service.active_proposal(dialog.conversation["id"])
        self.assertEqual(proposal.validation_state,"valid");self.assertIsNone(workspace.script)
        dialog.apply();self.assertIsNotNone(workspace.script)
        dialog.close();host.close()

if __name__=="__main__":unittest.main()