"""Build focused real Qt and media evidence for the V0.2 sound production chain."""
from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import opentimelineio as otio
from PySide6.QtCore import QUrl
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.preparation.finishing import ChapterFinishing
from app.preparation.finishing_gui import ChapterFinishingDialog
from app.preparation.production import ProductionService
from app.preparation.sound import SoundProduction
from app.preparation.sound_gui import SoundDialog
from app.preparation.workspace import Workspace
from app.preparation_gui import PreparationWindow
from app.rough_cut import probe

from tests.test_preparation_sound import SCRIPT



def wait(app, milliseconds=120):
    QTest.qWait(milliseconds)
    app.processEvents()


app = QApplication.instance() or QApplication(sys.argv)
out = Path("evidence/V0.2-Sound-Chain")
out.mkdir(parents=True, exist_ok=True)

with TemporaryDirectory() as temporary:
    root = Path(temporary) / "sound-project"
    workspace = Workspace(root)
    parsed = workspace.apply(SCRIPT)
    if not parsed.valid:
        raise RuntimeError(parsed.diagnostics)
    sound = SoundProduction(workspace)
    production = ProductionService(workspace)
    chapter = workspace.script.chapters[0]
    shot = chapter.shots[0]

    voice_requirement = next(r for r in workspace.script.requirements if r.kind == "voice")
    voice_fixture = Path("examples/audio-fixtures/FIXTURE-tone.wav").resolve()
    voice_candidate = production.import_candidate(voice_requirement.id, shot.id, voice_fixture)
    production.review(voice_candidate.id, "green")
    production.bind(voice_candidate.id)

    dialogue_jobs = []
    first_dialogue = shot.dialogues[0]
    request = sound.build_dialogue_request(first_dialogue.id, output_count=3)
    job, _ = sound.runtime.enqueue(request, user_intent="sound chain DEMO")
    sound.runtime.run_until_idle()
    first_job = sound.runtime.job(job.id)
    dialogue_jobs.append(first_job)
    for candidate_id, review in zip(first_job.candidate_ids, ("green", "yellow", "red")):
        production.review(candidate_id, review)
    sound.bind_dialogue(first_job.candidate_ids[0])
    sound.update_state(first_dialogue.id, strategy="independent", start=.28, volume=.82,
                       fade_in=.08, fade_out=.12)
    sound.update_subtitle(first_dialogue.id,
                          display_text=first_dialogue.text.replace("\uff0c", "\uff0c\n", 1),
                          start=.3, end=2.2)

    for dialogue in sound.dialogues(chapter_id=chapter.id):
        if dialogue.id == first_dialogue.id or not dialogue.voice_requirement_id:
            continue
        request = sound.build_dialogue_request(dialogue.id)
        job, _ = sound.runtime.enqueue(request, user_intent="sound chain DEMO")
        sound.runtime.run_until_idle()
        complete = sound.runtime.job(job.id)
        dialogue_jobs.append(complete)
        production.review(complete.candidate_ids[0], "green")
        sound.bind_dialogue(complete.candidate_ids[0])
        sound.update_state(dialogue.id, strategy="independent", start=.35, volume=.78)

    background_jobs = []
    for background in sound.background_items(chapter_id=chapter.id):
        request = sound.build_background_request(background.id)
        job, _ = sound.runtime.enqueue(request, user_intent="sound chain DEMO")
        sound.runtime.run_until_idle()
        complete = sound.runtime.job(job.id)
        background_jobs.append(complete)
        production.review(complete.candidate_ids[0], "green")
        sound.bind_background(complete.candidate_ids[0])
        sound.update_background(background.id, volume=.28, fade_in=.2, fade_out=.3)

    videos = sorted(Path("evidence/A-04/smoke-data/results").glob("*/video.mp4"))
    if len(videos) < len(chapter.shots):
        raise RuntimeError("Missing local fixture videos")
    for item, video_path in zip(chapter.shots, videos):
        candidate = production.import_shot_candidate(item.id, video_path)
        production.review(candidate.id, "green")
        production.bind_shot(candidate.id)

    finishing = ChapterFinishing(workspace, chapter.id)
    resolved = finishing.resolve()
    if resolved["status"] != "Ready":
        raise RuntimeError(resolved["errors"])
    preview = finishing.preview()
    final = finishing.output()
    handoff = finishing.handoff()

    window = PreparationWindow(root)
    window.show()
    while window.worker and window.worker.isRunning():
        wait(app, 30)
    window.resize(1480, 940)
    wait(app, 120)

    sound_dialog = SoundDialog(window, shot.id)
    sound_dialog.show()
    sound_dialog.resize(1240, 820)
    wait(app, 220)
    sound_dialog.grab().save(str(out / "sound-workspace.png"))
    sound_dialog.resize(960, 650)
    wait(app, 180)
    sound_dialog.grab().save(str(out / "sound-workspace-compact.png"))
    sound_dialog.close()

    finishing_dialog = ChapterFinishingDialog(window, chapter.id, shot.id)
    finishing_dialog.show()
    finishing_dialog.resize(1360, 880)
    finishing_dialog.player.setSource(QUrl.fromLocalFile(str(preview)))
    finishing_dialog.player.play()
    wait(app, 550)
    finishing_dialog.grab().save(str(out / "finishing-audio-preview.png"))
    finishing_dialog.player.stop()
    finishing_dialog.player.setSource(QUrl())
    finishing_dialog.close()
    finishing_dialog.deleteLater()
    wait(app, 180)

    stale_script = SCRIPT.replace(first_dialogue.text, first_dialogue.text + "\uff08\u5df2\u4fee\u6539\uff09")
    changed = workspace.apply(stale_script)
    if not changed.valid:
        raise RuntimeError(changed.diagnostics)
    stale_sound = SoundProduction(workspace)
    stale_dialog = SoundDialog(window, shot.id)
    stale_dialog.show()
    stale_dialog.resize(1180, 760)
    wait(app, 180)
    stale_dialog.grab().save(str(out / "stale-after-script-change.png"))
    stale_dialog.close()
    window.close()
    wait(app, 60)

    shutil.copy2(final, out / "chapter-output.mp4")
    shutil.copy2(handoff / "subtitles.srt", out / "subtitles.srt")
    shutil.copy2(handoff / "timeline.otio", out / "timeline.otio")

    timeline = otio.adapters.read_from_file(str(out / "timeline.otio"))
    target_urls = []
    for track in timeline.tracks:
        for item in track:
            reference = getattr(item, "media_reference", None)
            if reference and getattr(reference, "target_url", None):
                target_urls.append(reference.target_url)
    srt_text = (out / "subtitles.srt").read_text(encoding="utf-8")
    timecodes = re.findall(r"(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})", srt_text)
    restored_workspace = Workspace(root)
    restored_sound = SoundProduction(restored_workspace)
    restored_first = restored_workspace.script.chapters[0].shots[0].dialogues[0]

    summary = {
        "label": "DEMO / FIXTURE / ZERO-CALL",
        "project_title": workspace.script.title,
        "dialogue_identity": first_dialogue.id,
        "dialogue_candidates": [
            {"id": cid, "review": workspace.state["candidates"][cid]["review_state"]}
            for cid in first_job.candidate_ids
        ],
        "dialogue_current": workspace.state["dialogue_bindings"][first_dialogue.id],
        "voice_current": workspace.state["bindings"][voice_requirement.id]["candidate_id"],
        "background_current_count": len(workspace.state["background_bindings"]),
        "dialogue_timing": workspace.state["dialogue_states"][first_dialogue.id],
        "subtitle": workspace.state["subtitles"][first_dialogue.id],
        "candidate_stale_after_script_change": stale_sound.candidate_stale(first_job.candidate_ids[0]),
        "restart_current_preserved": restored_sound.current_dialogue(restored_first.id) == first_job.candidate_ids[0],
        "preview": probe(preview, "video"),
        "preview_audio": probe(preview, "audio"),
        "output": probe(final, "video"),
        "output_audio": probe(final, "audio"),
        "srt_entry_count": len(timecodes),
        "srt_timecodes": timecodes,
        "otio_tracks": [track.name for track in timeline.tracks],
        "otio_relative_urls": all(not re.match(r"^[A-Za-z]:|^/", url) for url in target_urls),
        "otio_round_trip": timeline.is_equivalent_to(
            otio.adapters.read_from_string(otio.adapters.write_to_string(timeline))),
        "dialogue_jobs": [job.status for job in dialogue_jobs],
        "background_jobs": [job.status for job in background_jobs],
        "commercial_api_calls": 0,
        "actual_cost": 0,
    }
    (out / "verification.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

(out / "README.md").write_text(
"""# V0.2 Voice / Dialogue / Subtitle Production Chain Evidence

All sound and generated media is explicitly marked DEMO / FIXTURE / ZERO-CALL.

- sound-workspace.png: real PySide6 sound and subtitle workspace with three reviewed takes and explicit Current.
- sound-workspace-compact.png: compact window.
- finishing-audio-preview.png: chapter finishing with real preview and sound workspace entry.
- stale-after-script-change.png: manual subtitle retained after formal dialogue changes.
- chapter-output.mp4: real FFmpeg output with independent dialogue and background audio.
- subtitles.srt: UTF-8 sidecar subtitles.
- timeline.otio: video, native audio, independent dialogue and background audio tracks.
- verification.json: media probe, Current, stale, restart, SRT and OTIO readback facts.

Commercial API calls: 0. Actual cost: 0.
""", encoding="utf-8")
