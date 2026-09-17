"""A narrow, keyless JSON-over-stdio boundary for external production tools."""
from __future__ import annotations

import argparse
import json
import socket
import sys

from app.core import Store
from app.fal_adapter import ProductionRunner, MODEL
from app.production import probe_video

TOOLS = {
    'prepare_rough_cut': 'timeline_id',
    'get_shot_context': 'shot_id',
    'build_generation_task': 'shot_id',
    'dry_run_generation': 'execution_id',
    'inspect_media': 'result_id',
    'prepare_shot_first_frame': 'shot_id',
    'prepare_dialogue_audio': 'dialogue_id',
}


def execute(store, tool, arguments):
    if tool not in TOOLS:
        raise ValueError('Tool not allowed; Human Gate and live generation are not exposed')
    key = TOOLS[tool]
    if not isinstance(arguments, dict) or set(arguments) != {key}:
        raise ValueError(f'Tool requires exactly {key}; no provider, prompt override or shell arguments')
    identifier = arguments[key]
    if not isinstance(identifier, str): raise ValueError('ID must be a string')
    store.record_path('shots', identifier)  # Shared stable ID validation; no path input.
    if tool == 'prepare_rough_cut':
        from app.rough_cut import RoughCutProduction
        import hashlib
        def gates():
            return {str(p.relative_to(store.root)):hashlib.sha256(p.read_bytes()).hexdigest() for k in ('timelines','reviews','audio_reviews') for p in store.path(k).glob('*.json')}
        before=gates();rough=RoughCutProduction(store);rough.build(identifier);folder,manifest=rough.preview(identifier)
        if gates()!=before:raise ValueError('Timeline Human Gate changed')
        return dict(timeline_id=identifier,build_id=manifest['build_id'],manifest_path=(folder/'manifest.json').relative_to(store.root).as_posix(),duration=manifest['duration'],human_review_required=True,human_gate_unchanged=True,preview_label=manifest['label'],generation_api_calls=0)
    runner = ProductionRunner(store)
    if tool == 'prepare_dialogue_audio':
        from app.audio_production import AudioProduction
        from app.alignment import AlignmentProduction
        audio = AudioProduction(store)
        before = audio.review(identifier).model_dump()
        dialogue = audio.dialogue(identifier)
        voice_before = audio.default_voice(dialogue.character_id).model_dump()
        job = audio.submit(identifier)
        for _ in range(2): job = audio.poll(job.id)
        if job.status != 'completed': raise ValueError(job.error)
        alignment = AlignmentProduction(audio).run(job.id)
        result, task = audio.trace(job.id)
        if audio.review(identifier).model_dump() != before or audio.default_voice(dialogue.character_id).model_dump() != voice_before:
            raise ValueError('Audio Human Gate changed')
        return dict(dialogue_id=identifier, shot_id=task.shot.id, voice_id=task.voice.id, task_id=task.id,
            result_id=result.id, audio_path=result.path, metadata=result.metadata, alignment_id=alignment.id,
            subtitle_path=alignment.subtitle_path, human_review_required=True, human_gate_unchanged=True,
            fixture=True, tts_api_calls=0, alignment_model_executed=False)
    if tool == 'prepare_shot_first_frame':
        from app.image_production import ImageProduction
        images = ImageProduction(store)
        before = store.record_path('first_frames', identifier)
        original = before.read_bytes() if before.exists() else None
        job = images.submit('SHOT_FIRST_FRAME', identifier)
        for _ in range(4): job = images.poll(job.id)
        if job.status != 'completed': raise ValueError(job.error)
        result, task = images.trace(job.result_id)
        if (before.read_bytes() if before.exists() else None) != original:
            raise ValueError('First frame Human Gate was changed')
        return dict(execution_id=job.id, task_id=task.id, shot_id=identifier, result_id=result.id,
            media_path=result.path, status=job.status, history=job.history,
            human_review_required=True, selected_first_frame_unchanged=True, image_api_calls=0)
    if tool == 'get_shot_context':
        # Reuse the neutral context assembly and validation, without persisting this query.
        task = store.task(identifier)
        review = runner.review(identifier)
        return dict(shot=task.shot.model_dump(), character=task.character.model_dump(),
            look=task.look.model_dump(), scene=task.scene.model_dump() if task.scene else None,
            scene_state=task.scene_state.model_dump() if task.scene_state else None,
            character_references=[r.model_dump() for r in task.references],
            scene_references=[r.model_dump() for r in task.scene_references],
            executions=[j.model_dump() for j in runner.executions(identifier)],
            selected_take=review.selected_result_id, rejected=review.rejected)
    if tool == 'build_generation_task':
        # Existing submission builds/persists the neutral task, request and pending execution.
        # Reusing it avoids a second task builder and avoids rebuilding the snapshot later.
        job = runner.submit(identifier, provider='fal')
        task = runner.task_snapshot(job.task_id)
        return dict(task_id=task.id, execution_id=job.id, shot_id=job.shot_id,
            status=job.status, provider=job.provider, model=job.model, transport='fixture',
            character_id=task.character.id, look_id=task.look.id, scene_id=task.scene.id,
            scene_state_id=task.scene_state.id, reference_count=len(task.references + task.scene_references))
    if tool == 'dry_run_generation':
        job = runner.execution(identifier)
        if job.provider != 'fal' or job.model != MODEL or not job.simulation_only:
            raise ValueError('Only the existing fal zero-call fixture execution is allowed')
        for _ in range(6):
            if job.status in ('completed', 'failed'): break
            job = runner.poll(job.id)
        if job.status != 'completed':
            raise ValueError(job.error or 'Fixture did not complete within its bounded lifecycle')
        result, task = runner.trace(job.result_id)
        return dict(execution_id=job.id, task_id=task.id, shot_id=job.shot_id,
            result_id=result.id, media_path=result.path, status=job.status,
            history=job.history, production_update='ingested by existing Result Ingestion',
            selected_take=runner.review(job.shot_id).selected_result_id,
            simulation_only=True, video_api_calls=0)
    result, task = runner.trace(identifier)
    media = probe_video(store.path(result.path))
    return dict(result_id=result.id, task_id=task.id, shot_id=result.shot_id,
                path=result.path, tool='ffprobe', parseable=True, **media)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-dir', required=True)
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stdin.reconfigure(encoding='utf-8')
    attempts = []
    def deny(*_args, **_kwargs):
        attempts.append('blocked network connection')
        raise RuntimeError('A-04 bridge forbids network access')
    socket.socket.connect = deny
    socket.socket.connect_ex = deny
    socket.create_connection = deny
    try:
        raw = sys.stdin.read(8193)
        if len(raw) > 8192: raise ValueError('Tool input is too large')
        request = json.loads(raw)
        if not isinstance(request, dict) or set(request) != {'tool', 'arguments'}:
            raise ValueError('Expected tool and arguments only')
        output = execute(Store(args.data_dir), request['tool'], request['arguments'])
        print(json.dumps(dict(ok=True, output=output, network_attempts=len(attempts)), ensure_ascii=False))
    except Exception as exc:
        print(json.dumps(dict(ok=False, error=str(exc), network_attempts=len(attempts)), ensure_ascii=False))
        return 1
    return 0


if __name__ == '__main__': raise SystemExit(main())
