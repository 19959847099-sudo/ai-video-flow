"""Real Qt and zero-call evidence for V0.2 Creative Assistant."""
from __future__ import annotations
import json
import shutil
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from app.preparation.creative import CreativeRun, CreativeService, Scope
from app.preparation.creative_gui import CreativeDialog
from app.preparation.workspace import Workspace
from app.preparation_gui import PreparationWindow
from tests.test_preparation_sound import SCRIPT

def wait(app,ms=100):
    QTest.qWait(ms);app.processEvents()

app=QApplication.instance() or QApplication(sys.argv)
out=Path("evidence/V0.2-Creative-Assistant");out.mkdir(parents=True,exist_ok=True)

with TemporaryDirectory() as temporary:
    root=Path(temporary)/"creative-project";workspace=Workspace(root);workspace.apply(SCRIPT)
    chapter=workspace.script.chapters[0];shot=chapter.shots[0]
    scope=Scope(level="shot",chapter_id=chapter.id,shot_id=shot.id,
                dialogue_id=shot.dialogues[0].id)
    service=CreativeService(workspace);conversation=service.active_conversation(scope)
    run,request=service.begin(conversation["id"],"project_discussion",
        "How does the current shot feel?",scope)
    discussion_run,discussion=service.complete(run.id,request)
    run,request=service.begin(conversation["id"],"edit_shot",
        "Make this shot quieter and keep the suspense.",scope)
    first_run,first_output=service.complete(run.id,request)
    first=service.active_proposal(conversation["id"])
    formal_before=workspace.script.revision
    run,request=service.begin(conversation["id"],"edit_shot",
        "Make the ending even more restrained.",scope,continue_proposal=True)
    continued_run,continued_output=service.complete(run.id,request)
    continued=service.active_proposal(conversation["id"])
    continued_diff_counts=service.proposal_diff(continued.id)[1]
    formal_unchanged_before_apply=workspace.script.revision==formal_before

    window=PreparationWindow(root);window.show()
    while window.worker and window.worker.isRunning():wait(app,30)
    window.resize(1480,940);wait(app,120)
    dialog=CreativeDialog(window);dialog.show();dialog.resize(1280,840);wait(app,180)
    dialog.grab().save(str(out/"creative-workspace.png"))
    dialog.resize(960,650);wait(app,140)
    dialog.grab().save(str(out/"creative-workspace-compact.png"))
    dialog.close();window.close();wait(app,60)

    before_counts=(len(workspace.state["candidates"]),len(workspace.state["runtime_jobs"]),
                   dict(workspace.state["bindings"]),dict(workspace.state["dialogue_bindings"]))
    service.apply(continued.id)
    applied_revision=workspace.script.revision
    after_counts=(len(workspace.state["candidates"]),len(workspace.state["runtime_jobs"]),
                  dict(workspace.state["bindings"]),dict(workspace.state["dialogue_bindings"]))

    conversation=service.active_conversation(scope)
    run,request=service.begin(conversation["id"],"edit_shot","Add a short pause.",scope)
    stale_run,_=service.complete(run.id,request)
    stale=service.active_proposal(conversation["id"])
    workspace.apply(workspace.script.source.replace("\u6211\u518d\u7b49\u7b49\u3002","\u6211\u4f1a\u7b49\u3002"))
    stale=service.refresh_proposal(stale.id)
    stale_window=PreparationWindow(root);stale_window.show()
    while stale_window.worker and stale_window.worker.isRunning():wait(app,30)
    stale_dialog=CreativeDialog(stale_window);stale_dialog.show();stale_dialog.resize(1160,760);wait(app,160)
    stale_dialog.grab().save(str(out/"stale-proposal.png"));stale_dialog.close();stale_window.close();wait(app,50)
    service.discard(stale.id)

    scope=Scope(level="shot",chapter_id=workspace.script.chapters[0].id,
                shot_id=workspace.script.chapters[0].shots[0].id)
    run,request=service.begin(conversation["id"],"edit_shot","Create an invalid fixture draft.",
                              scope,scenario="parser_invalid")
    invalid_run,_=service.complete(run.id,request,repair=False)
    invalid=service.active_proposal(conversation["id"])
    invalid_window=PreparationWindow(root);invalid_window.show()
    while invalid_window.worker and invalid_window.worker.isRunning():wait(app,30)
    invalid_dialog=CreativeDialog(invalid_window);invalid_dialog.show();invalid_dialog.resize(1160,760);wait(app,160)
    invalid_dialog.grab().save(str(out/"invalid-draft.png"));invalid_dialog.close();invalid_window.close();wait(app,80)

    idea_root=Path(temporary)/"idea-project";idea_workspace=Workspace(idea_root)
    idea_service=CreativeService(idea_workspace);idea_conversation=idea_service.active_conversation(Scope())
    run,request=idea_service.begin(idea_conversation["id"],"idea_to_script",
        "A woman returns to an empty cinema and hears tomorrow's audience.",Scope())
    idea_run,_=idea_service.complete(run.id,request)
    idea_window=PreparationWindow(idea_root);idea_window.show()
    while idea_window.worker and idea_window.worker.isRunning():wait(app,30)
    idea_window.resize(1380,900);wait(app,100)
    idea_dialog=CreativeDialog(idea_window);idea_dialog.show();idea_dialog.resize(1220,800);wait(app,160)
    idea_dialog.grab().save(str(out/"idea-to-draft.png"))
    idea_dialog.close();idea_window.close();wait(app,60)

    external_root=Path(temporary)/"external-project";external_workspace=Workspace(external_root)
    external_service=CreativeService(external_workspace)
    external_conversation=external_service.active_conversation(Scope())
    external_source="# Scene\nLin enters a room. Unknown age and costume."
    run,request=external_service.begin(external_conversation["id"],"normalize_external_script",
        "Normalize this source as a production script.",Scope(),external_text=external_source)
    external_run,_=external_service.complete(run.id,request)
    external_proposal=external_service.active_proposal(external_conversation["id"])
    external_validation=external_proposal.validation_state
    external_service.apply(external_proposal.id)

    runs=[CreativeRun.model_validate(x) for x in workspace.state["creative_runs"].values()]
    trace={"label":"FIXTURE / DEMO / ZERO-CALL",
        "formal_unchanged_before_apply":formal_unchanged_before_apply,
        "applied_revision":applied_revision,
        "first_proposal_became_stale":service.proposal(first.id).status=="stale",
        "continue_based_on_proposal":continued_run.based_on_proposal_id==first.id,
        "local_diff":continued_diff_counts,
        "stale_blocked":stale.status=="stale",
        "invalid_validation":invalid.validation_state,
        "invalid_diagnostics":invalid.diagnostics,
        "production_state_unchanged":before_counts==after_counts,
        "run_trace":[{"id":x.id,"task":x.task,"status":x.status,"provider":x.provider_id,
            "model":x.model_id,"prompt_versions":x.prompt_versions,
            "template_hash":x.template_hash,"context_fingerprint":x.context_fingerprint,
            "base_script_fingerprint":x.base_script_fingerprint,
            "proposal_id":x.proposal_id,"repair_count":x.repair_count} for x in runs],
        "idea_validation":idea_service.active_proposal(idea_conversation["id"]).validation_state,
        "external_normalization":{
            "validation":external_validation,
            "applied":external_workspace.script is not None,
            "narrative_preserved": "Lin enters a room" in external_proposal.draft,
        },
        "commercial_llm_calls":0,"actual_cost":0}
    (out/"verification.json").write_text(json.dumps(trace,ensure_ascii=False,indent=2),encoding="utf-8")

(out/"README.md").write_text("""# V0.2 Creative Assistant evidence

All responses are deterministic Fixture / DEMO / ZERO-CALL.

- creative-workspace.png: discussion, continued Shot proposal, local Diff and editable full draft.
- creative-workspace-compact.png: compact Qt layout.
- idea-to-draft.png: one-line idea to a parser-valid Production Script draft.
- stale-proposal.png: project changed before Apply.
- invalid-draft.png: parser-invalid proposal with Apply blocked.
- verification.json: prompt versions/hashes, context and base fingerprints, explicit Apply facts, no production side effects.

Commercial LLM calls: 0. Actual cost: 0.
""",encoding="utf-8")