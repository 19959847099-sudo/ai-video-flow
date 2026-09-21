"""Formal integration coverage for D Shell, routing, memory, activity and truth boundaries."""
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.integration import ActivityAdapter, AppSettingsStore, WorkspaceRouter
from app.integrated_gui import ApplicationShell
from app.preparation.creative import CreativeService, Scope
from app.preparation.finishing import ChapterFinishing
from app.preparation.production import ProductionService
from app.preparation.runtime import ProductionRuntime
from app.preparation.workspace import Workspace
from tests.test_preparation_sound import SCRIPT


class IntegrationContractTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory()
        self.root=Path(self.temp.name)/"project"
        self.workspace=Workspace(self.root)
        self.workspace.apply(SCRIPT)
        self.chapter=self.workspace.script.chapters[0]
        self.shot=self.chapter.shots[0]

    def tearDown(self):
        self.temp.cleanup()

    def test_router_deep_link_return_degrade_and_restart_memory(self):
        router=WorkspaceRouter(self.workspace)
        self.assertEqual(router.current.workspace,"production")
        router.navigate("preparation",chapter_id=self.chapter.id,shot_id=self.shot.id)
        router.remember("preparation",selected_requirement="R1",scroll_y=118,
                        selection={"requirement":"R1"},scroll={"items":118})
        linked=router.navigate("production",chapter_id=self.chapter.id,shot_id=self.shot.id,
                               object_type="requirement",object_id="R1",deep_link=True,
                               reason="missing")
        self.assertEqual(linked.return_point.workspace,"preparation")
        returned=router.return_to_origin()
        self.assertEqual(returned.workspace,"preparation")
        self.assertEqual(router.memory("preparation")["scroll_y"],118)
        self.assertEqual(router.state["return_stack"],[])

        restored=WorkspaceRouter(Workspace(self.root))
        self.assertEqual(restored.current.workspace,"preparation")
        broken=restored.navigate("production",chapter_id="deleted",shot_id="deleted")
        self.assertEqual(broken.chapter_id,self.chapter.id)
        self.assertTrue(restored.notice)

    def test_settings_are_versioned_recoverable_and_not_project_truth(self):
        path=Path(self.temp.name)/"config"/"settings.json"
        before=json.dumps(self.workspace.state,ensure_ascii=False,sort_keys=True)
        store=AppSettingsStore(path)
        self.assertEqual(store.values["layout"],"D")
        store.save(layout="C",text_base_url="https://example.test/v1",text_model="mock")
        loaded=AppSettingsStore(path)
        self.assertEqual(loaded.values["layout"],"C")
        self.assertNotIn("api",path.read_text(encoding="utf-8").lower())
        self.assertEqual(before,json.dumps(self.workspace.state,ensure_ascii=False,sort_keys=True))
        path.write_text("{bad",encoding="utf-8")
        recovered=AppSettingsStore(path)
        self.assertEqual(recovered.values["layout"],"D")
        self.assertTrue(recovered.error)

    def test_activity_adapts_existing_runtimes_without_owning_results(self):
        runtime=ProductionRuntime(self.workspace)
        requirement=next(r for r in self.workspace.script.requirements if r.media=="image")
        request=runtime.build_request(self.shot.id,"image",requirement.id,"fixture-image-v1")
        job,_=runtime.enqueue(request)
        records=ActivityAdapter(self.workspace).records()
        record=next(item for item in records if item["id"]==job.id)
        self.assertEqual(record["route"]["workspace"],"production")
        self.assertEqual(record["route"]["shot_id"],self.shot.id)
        self.assertEqual(record["state"],"queued")

        service=CreativeService(self.workspace)
        conversation=service.active_conversation(Scope(level="shot",chapter_id=self.chapter.id,
                                                        shot_id=self.shot.id))
        run,_=service.begin(conversation["id"],"project_discussion","question",
                            Scope(level="shot",chapter_id=self.chapter.id,shot_id=self.shot.id))
        creative=next(item for item in ActivityAdapter(self.workspace).records()
                      if item["id"]==run.id)
        self.assertEqual(creative["route"]["workspace"],"creative")
        self.assertIn(creative["state"],("queued","running"))

    def test_integrated_truth_boundaries_remain_explicit(self):
        service=ProductionService(self.workspace)
        requirement=next(r for r in self.workspace.script.requirements if r.media=="image")
        fixture=Path(__file__).resolve().parents[1]/"app/preparation/demo_assets/convenience-store-night.png"
        candidate=service.import_candidate(requirement.id,self.shot.id,fixture)
        service.review(candidate.id,"green")
        self.assertIsNone(service.current(requirement.id))
        service.bind(candidate.id)
        self.assertEqual(service.current(requirement.id),candidate.id)

        asset_count=len(self.workspace.state["assets"])
        free_requirement=next(row["requirement"]["id"] for row in self.workspace.report()
                              if row["status"]=="missing" and row["requirement"]["id"]!=requirement.id)
        self.workspace.set_reference_required(free_requirement,False)
        self.assertEqual(len(self.workspace.state["assets"]),asset_count)

        creative=CreativeService(self.workspace)
        conversation=creative.active_conversation(Scope(level="shot",chapter_id=self.chapter.id,
                                                          shot_id=self.shot.id))
        formal=self.workspace.script.revision
        run,request=creative.begin(conversation["id"],"edit_shot","quieter",
                                   Scope(level="shot",chapter_id=self.chapter.id,shot_id=self.shot.id))
        creative.complete(run.id,request)
        self.assertEqual(self.workspace.script.revision,formal)

        assembly=ChapterFinishing(self.workspace,self.chapter.id)
        shots_before=[s.id for s in self.workspace.script.chapters[0].shots]
        segment=assembly.segments()[0]
        assembly.remove(segment["id"])
        self.assertEqual([s.id for s in self.workspace.script.chapters[0].shots],shots_before)


class IntegratedShellGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp=TemporaryDirectory()
        self.root=Path(self.temp.name)/"project"
        Workspace(self.root).apply(SCRIPT)
        self.shell=ApplicationShell(self.root,settings_path=Path(self.temp.name)/"settings.json")
        self.shell.show()
        QTest.qWait(80)

    def tearDown(self):
        self.shell.close()
        QTest.qWait(50)
        self.temp.cleanup()

    def test_workspace_chain_precise_return_settings_and_memory(self):
        self.assertEqual(self.shell.router.current.workspace,"production")
        self.assertEqual(self.shell.findChild(type(self.shell.return_bar),"shell").height(),56)
        self.shell.resize(1280,720)
        QTest.qWait(50)
        self.assertEqual(self.shell.size().width(),1280)
        self.shell.navigate("preparation")
        rows=self.shell.preparation_page.scoped_reports()
        self.assertTrue(rows)
        self.assertTrue(all(row["use_count"] > 0 for row in rows))
        requirement=rows[0]["requirement"]["id"]
        self.shell.preparation_page.selected_id=requirement
        self.shell.preparation_page.search.setText("")
        self.shell.open_requirement(requirement)
        self.assertEqual(self.shell.router.current.workspace,"production")
        self.assertEqual(self.shell.router.current.object_id,requirement)
        self.assertIsNotNone(self.shell.router.current.return_point)
        self.shell.return_route()
        self.assertEqual(self.shell.router.current.workspace,"preparation")
        self.assertEqual(self.shell.preparation_page.selected_id,requirement)

        self.shell.navigate("production")
        self.shell.navigate("creative",deep_link=True,reason="test")
        self.assertEqual(self.shell.router.current.workspace,"creative")
        self.shell.current_workspace_widget.input.setPlainText("unsent draft")
        self.shell.return_route()
        self.shell.navigate("creative")
        self.assertEqual(self.shell.current_workspace_widget.input.toPlainText(),"unsent draft")

        self.shell.navigate("assembly",deep_link=True,reason="chapter")
        self.assertEqual(self.shell.router.current.workspace,"assembly")
        self.shell.navigate("settings",deep_link=True,reason="settings")
        self.assertEqual(self.shell.router.current.workspace,"settings")
        self.shell.return_route()
        self.assertEqual(self.shell.router.current.workspace,"assembly")
        QTest.qWait(10)
        dynamic=[key for key in self.shell.pages if ":" in key]
        self.assertLessEqual(len(dynamic),1)

        self.shell.resize(1600,1000)
        QTest.qWait(50)
        self.assertEqual(self.shell.size().width(),1600)

    def test_new_project_starts_in_preparation(self):
        self.shell.close()
        root=Path(self.temp.name)/"empty"
        self.shell=ApplicationShell(root,settings_path=Path(self.temp.name)/"empty-settings.json")
        self.assertEqual(self.shell.router.current.workspace,"preparation")
        self.assertIs(self.shell.stack.currentWidget(),self.shell.preparation_page)
    def test_close_is_blocked_while_a_session_worker_is_running(self):
        busy=SimpleNamespace(worker=SimpleNamespace(isRunning=lambda: True))
        self.shell.pages["busy:test"]=busy
        try:
            with patch("app.integrated_gui.QMessageBox.information") as information:
                self.assertFalse(self.shell.close())
                self.assertTrue(self.shell.isVisible())
                information.assert_called_once()
        finally:
            self.shell.pages.pop("busy:test",None)


if __name__=="__main__":
    unittest.main()
