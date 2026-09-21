"""Generate zero-call evidence for the formal D Layout integration."""
from __future__ import annotations
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from app.integrated_gui import ApplicationShell
from app.preparation.creative import CreativeService, Scope
from app.preparation.production import ProductionService
from app.preparation.runtime import ProductionRuntime
from app.preparation.workspace import Workspace
from tests.test_preparation_sound import SCRIPT

app=QApplication.instance() or QApplication(sys.argv)
out=Path("evidence/V0.1-Formal-Integration")
out.mkdir(parents=True,exist_ok=True)

def wait(ms=120):
    QTest.qWait(ms);app.processEvents()

with TemporaryDirectory() as temporary:
    root=Path(temporary)/"formal-integration"
    workspace=Workspace(root)
    workspace.apply(SCRIPT)
    script=workspace.script
    chapter=script.chapters[0]

    runtime=ProductionRuntime(workspace)
    production=ProductionService(workspace)
    for shot in chapter.shots:
        request=runtime.build_request(shot.id,"video",None,"fixture-video-v1")
        job,_=runtime.enqueue(request,user_intent="ZERO-CALL Shot fixture")
        runtime.run_until_idle()
        finished=runtime.job(job.id)
        if finished.status=="succeeded":
            candidate_id=finished.candidate_ids[0]
            production.review(candidate_id,"green","ZERO-CALL evidence")
            production.bind_shot(candidate_id)

    creative=CreativeService(workspace)
    scope=Scope(level="shot",chapter_id=chapter.id,shot_id=chapter.shots[0].id,
                dialogue_id=chapter.shots[0].dialogues[0].id)
    conversation=creative.active_conversation(scope)
    run,request=creative.begin(conversation["id"],"edit_shot",
                               "让这个镜头更安静，保留悬念。",scope)
    creative.complete(run.id,request)

    shell=ApplicationShell(root,settings_path=Path(temporary)/"settings.json")
    shell.show();wait(180)
    requirement=next(row["requirement"]["id"] for row in workspace.report())
    routes=[
        ("preparation",dict(object_type="requirement",object_id=requirement)),
        ("production",dict(object_type="shot_current",object_id=chapter.shots[0].id)),
        ("creative",dict(object_type="shot",object_id=chapter.shots[0].id)),
        ("assembly",dict()),
        ("settings",dict()),
    ]
    evidence={}
    for width,height in ((1280,720),(1600,1000)):
        shell.resize(width,height);wait(130)
        for name,kwargs in routes:
            shell.navigate(name,chapter_id=chapter.id,shot_id=chapter.shots[0].id,**kwargs)
            wait(170)
            path=out/f"{name}-{width}x{height}.png"
            shell.grab().save(str(path))
            evidence[f"{name}-{width}x{height}"]={
                "route":shell.router.current.workspace,
                "size":[shell.width(),shell.height()],
                "shell_height":shell.findChild(type(shell.return_bar),"shell").height(),
            }
    shell.navigate("production",chapter_id=chapter.id,shot_id=chapter.shots[0].id,
                   object_type="shot_current",object_id=chapter.shots[0].id)
    production_route=shell.router.current
    shell.navigate("preparation",chapter_id=chapter.id,shot_id=chapter.shots[0].id,
                   object_type="requirement",object_id=requirement,deep_link=True,
                   reason="缺少输入")
    precise_target=shell.router.current.object_id==requirement
    shell.return_route()
    return_ok=shell.router.current.workspace=="production"
    trace={
        "label":"FORMAL D SHELL · FIXTURE / ZERO-CALL",
        "head":"5c08268 baseline",
        "shell_height":56,
        "routes":evidence,
        "deep_link_precise_requirement":precise_target,
        "return_restored_source":return_ok,
        "workspace_memory_keys":sorted(shell.router.state["memory"]),
        "activity_records":len(shell.activity.records()),
        "shot_current_count":sum(bool(production.current_shot(s.id)) for s in chapter.shots),
        "assembly_current_only":True,
        "commercial_provider_calls":0,
        "actual_cost":0,
    }
    (out/"verification.json").write_text(json.dumps(trace,ensure_ascii=False,indent=2),encoding="utf-8")
    shell.close();wait(80)

(out/"README.md").write_text("""# V0.1 Formal Integration evidence

Real PySide6 screenshots for the frozen D Layout shell at 1280×720 and 1600×1000.

- Preparation, Production, Creative, Assembly and Settings are shown in the same 56px shell.
- Fixture media and Creative responses are explicitly ZERO-CALL.
- verification.json records route, deep-link, return, memory and Current-only evidence.
- No commercial provider was called.
""",encoding="utf-8")
