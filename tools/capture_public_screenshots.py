"""Capture current D-shell screenshots from a disposable zero-call demo project."""
from __future__ import annotations

import sys
import subprocess
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
SCRIPT = '''雨夜来信/名称
01/章节/最后一班
001/雨中的便利店
人物：林夏/-/深色风衣/低声
人物：店员/-/-/-
环境：【街角便利店】/夜雨、冰柜低鸣
表演：林夏握着一把旧伞，在明亮的店门口迟疑。
对白：林夏：昨晚有人把这把伞留在这里吗？
店员：有人来过，但没有进门。
连续性：雨声与店内暖光贯穿本章。
002/玻璃窗前
人物：林夏/-/深色风衣/低声
环境：【街角便利店】/夜雨
表演：林夏隔着雨水望向空荡的街道。
对白：林夏：那我再等一会儿。
'''


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
        scene = ROOT / "app" / "preparation" / "demo_assets" / "convenience-store-night.png"
        scene_clip = Path(temporary) / "rainy-convenience-store.mp4"
        subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-loop", "1",
             "-framerate", "25", "-i", str(scene), "-t", "4",
             "-vf", "scale=960:540:force_original_aspect_ratio=increase,crop=960:540,format=yuv420p",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
             "-movflags", "+faststart", str(scene_clip)],
            check=True,
        )
        environment = next(r for r in workspace.script.requirements if r.kind == "environment")
        environment_take = production.import_candidate(environment.id, chapter.shots[0].id, scene)
        production.review(environment_take.id, "green", "Public synthetic scene reference")
        production.bind(environment_take.id)
        hero_candidate_id = None
        for shot in chapter.shots:
            request = runtime.build_request(shot.id, "video", None, "fixture-video-v1")
            job, _ = runtime.enqueue(request, user_intent="Public zero-call screenshot demo")
            runtime.run_until_idle()
            completed = runtime.job(job.id)
            if completed.status != "succeeded" or not completed.candidate_ids:
                raise RuntimeError(f"Demo video fixture failed: {completed.status}")
            candidate = completed.candidate_ids[0]
            production.review(candidate, "green", "Public zero-call screenshot demo")
            imported = production.import_shot_candidate(shot.id, scene_clip)
            production.review(imported.id, "green", "Local photo-based demo clip")
            production.bind_shot(imported.id)

            if shot.id == chapter.shots[0].id:
                hero_candidate_id = imported.id
        shot = chapter.shots[0]
        scope = Scope(level="shot", chapter_id=chapter.id, shot_id=shot.id,
                      dialogue_id=shot.dialogues[0].id)
        creative = CreativeService(workspace)
        conversation = creative.active_conversation(scope)
        run, request = creative.begin(conversation["id"], "edit_shot",
                                      "Make the pause at the door longer, keeping the rain and the quiet tension.", scope)
        creative.complete(run.id, request)

        shell = ApplicationShell(project, settings_path=Path(temporary) / "settings.json")
        try:
            shell.resize(1600, 1000)
            shell.show()
            settle(app, 250)
            requirement = environment.id
            routes = (
                ("production", {"object_type": "shot_current", "object_id": shot.id}),
                ("preparation", {"object_type": "requirement", "object_id": requirement}),
                ("creative", {"object_type": "shot", "object_id": shot.id}),
                ("assembly", {}),
            )
            for name, target in routes:
                shell.navigate(name, chapter_id=chapter.id, shot_id=shot.id, **target)
                if name == "production":
                    shell.stack.currentWidget().refresh(hero_candidate_id)
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
