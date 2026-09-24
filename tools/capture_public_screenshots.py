"""Capture current D-shell screenshots from a disposable zero-call demo project."""
from __future__ import annotations

import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from PySide6.QtGui import QFont
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.integrated_gui import ApplicationShell
from app.preparation.creative import CreativeService, Scope
from app.preparation.production import ProductionService
from app.preparation.runtime import ProductionRuntime
from app.preparation.workspace import Workspace
from tests.test_preparation_sound import SCRIPT


def settle(app: QApplication, milliseconds: int = 150) -> None:
    QTest.qWait(milliseconds)
    app.processEvents()


def main() -> None:
    output = ROOT / "docs" / "assets" / "screenshots"
    output.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication(sys.argv)
    app.setFont(QFont("Microsoft YaHei UI", 10))

    with TemporaryDirectory(prefix="ai-video-flow-public-demo-") as temporary:
        project = Path(temporary) / "zero-call-demo"
        workspace = Workspace(project)
        workspace.apply(SCRIPT)
        chapter = workspace.script.chapters[0]
        runtime = ProductionRuntime(workspace)
        production = ProductionService(workspace)
        for shot in chapter.shots:
            request = runtime.build_request(shot.id, "video", None, "fixture-video-v1")
            job, _ = runtime.enqueue(request, user_intent="Public zero-call screenshot demo")
            runtime.run_until_idle()
            completed = runtime.job(job.id)
            if completed.status != "succeeded" or not completed.candidate_ids:
                raise RuntimeError(f"Demo video fixture failed: {completed.status}")
            candidate = completed.candidate_ids[0]
            production.review(candidate, "green", "Public zero-call screenshot demo")
            production.bind_shot(candidate)

        shot = chapter.shots[0]
        scope = Scope(level="shot", chapter_id=chapter.id, shot_id=shot.id,
                      dialogue_id=shot.dialogues[0].id)
        creative = CreativeService(workspace)
        conversation = creative.active_conversation(scope)
        run, request = creative.begin(conversation["id"], "edit_shot",
                                      "Keep this shot quieter while preserving the suspense.", scope)
        creative.complete(run.id, request)

        shell = ApplicationShell(project, settings_path=Path(temporary) / "settings.json")
        try:
            shell.resize(1600, 1000)
            shell.show()
            settle(app, 250)
            requirement = workspace.report()[0]["requirement"]["id"]
            routes = (
                ("production", {"object_type": "shot_current", "object_id": shot.id}),
                ("preparation", {"object_type": "requirement", "object_id": requirement}),
                ("creative", {"object_type": "shot", "object_id": shot.id}),
                ("assembly", {}),
            )
            for name, target in routes:
                shell.navigate(name, chapter_id=chapter.id, shot_id=shot.id, **target)
                settle(app, 220)
                path = output / f"{name}-1600x1000.png"
                if not shell.grab().save(str(path)):
                    raise OSError(f"Could not save {path}")
                print(f"{name}: {path.stat().st_size} bytes")
        finally:
            shell.close()
            settle(app)


if __name__ == "__main__":
    main()
