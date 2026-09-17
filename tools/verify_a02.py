"""Verify the delivered A-02 sample, without submitting jobs or modifying production data."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.core import Character, Scene, Shot, GenerationTask, Store, write_json
from app.production import Execution, Result, Review, MockProviderAdapter, probe_video, run_media, media_tool


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    evidence = ROOT / 'evidence/A-02'
    frozen_before = json.loads((evidence / 'frozen-before.json').read_text(encoding='utf-8'))
    frozen_after = {p.name: digest(p) for p in (ROOT / '重要文档').glob('*.md')}
    assert frozen_before == frozen_after
    baseline = json.loads((evidence / 'a01-data-before.json').read_text(encoding='utf-8'))
    assert all(digest(ROOT / key) == value for key, value in baseline.items())
    for model in [Character, Scene, Shot, GenerationTask, Execution, Result, Review]:
        assert json.loads((ROOT / 'schemas' / f'{model.__name__}.schema.json').read_text(encoding='utf-8')) == model.model_json_schema()

    store = Store(ROOT / 'data')
    provider = MockProviderAdapter(store)
    chars, scenes, shots = store.characters(), store.scenes(), store.shots()
    modern = [s for s in shots if s.schema_version == '0.2']
    assert len(chars) == 1 and len(chars[0].looks) == 2
    assert len(scenes) == 1 and len(scenes[0].states) == 2
    assert len(modern) == 2 and len(shots) == 4
    assert len({s.character_id for s in modern}) == len({s.scene_id for s in modern}) == 1
    assert len({s.scene_state_id for s in modern}) == 2
    assert all(s.is_example for s in shots + chars + scenes)
    assert all(not Path(r.path).is_absolute() and digest(store.path(r.path)) == r.sha256
               for asset in chars + scenes for r in asset.references)

    executions = provider.executions()
    assert len(executions) == 3
    results = []
    for job in executions:
        assert job.status == 'completed' and job.history == ['pending', 'processing', 'completed']
        result, task = provider.trace(job.result_id)
        live_shot = next(s for s in shots if s.id == job.shot_id)
        assert task.shot.model_copy(update={'generation_description': live_shot.generation_description}) == live_shot
        assert task.character.id == live_shot.character_id and task.look.id == live_shot.look_id
        assert task.scene.id == live_shot.scene_id and task.scene_state.id == live_shot.scene_state_id
        assert len(task.references) == len(task.scene_references) == 2
        assert task.final_prompt == '\n'.join(f'{k}: {v}' for k, v in task.prompt_source.items())
        assert 'provider' not in task.model_dump() and task.is_example
        request = json.loads(store.path(f'tasks/{task.id}/mock_request.json').read_text(encoding='utf-8'))
        assert request['input']['text'] == task.final_prompt and not request['api_called']
        assert request['input']['images'] == [dict(asset_path=r.path, sha256=r.sha256)
                                            for r in task.references + task.scene_references]
        media = probe_video(store.path(result.path))
        assert media['codec_name'] == 'h264' and media['duration'] == 3
        run_media([media_tool('ffmpeg'), '-hide_banner', '-loglevel', 'error', '-nostdin',
                   '-i', str(store.path(result.path)), '-f', 'null', '-'])
        assert not Path(result.path).is_absolute()
        results.append({'shot': task.shot.description, 'shot_id': job.shot_id, 'take': job.take_number,
            'execution_id': job.id, 'history': job.history, 'retry_of': job.retry_of, 'task_id': task.id,
            'character': task.character.name, 'look': task.look.name, 'scene': task.scene.name,
            'state': task.scene_state.name, 'character_references': [r.name for r in task.references],
            'scene_references': [r.name for r in task.scene_references], 'result': result.path,
            'media': media, 'full_decode_passed': True})

    day = next(s for s in modern if '白天' in s.description)
    jobs = provider.executions(day.id)
    assert len(jobs) == 2 and jobs[1].retry_of == jobs[0].result_id and jobs[1].task_id != jobs[0].task_id
    review = provider.review(day.id)
    assert review.selected_result_id == jobs[1].result_id and review.rejected[jobs[0].result_id]
    selected, task = provider.trace(review.selected_result_id)
    assert '停顿两秒' in task.final_prompt
    # The selection is explicit; another completed Shot is still awaiting human review.
    other = next(s for s in modern if s.id != day.id)
    assert provider.review(other.id).selected_result_id is None
    snapshot_proof = json.loads((evidence / 'snapshot-proof.json').read_text(encoding='utf-8'))
    assert snapshot_proof['all_7_task_files_byte_unchanged']
    assert all(digest(ROOT / path) == value for path, value in snapshot_proof['hashes_after_edit'].items())
    write_json(evidence / 'frozen-after.json', frozen_after)
    write_json(evidence / 'verification.json', {
        'a01_original_files_byte_unchanged': True, 'frozen_files_byte_unchanged': True,
        'schemas_match_models': True, 'character_count': len(chars), 'scene_count': len(scenes),
        'total_shots': len(shots), 'a02_shots': len(modern), 'results': results,
        'selected_result_id': selected.id, 'selected_task_id': task.id,
        'selected_final_prompt': task.final_prompt, 'snapshot_proof': 'snapshot-proof.json',
        'review_decisions_are_explicit': True,
        'gui_evidence': ['03-scene-two-states.png', '08-playing-real-mp4.png', '10-selected-take.png',
                         '16-restart-scene-day.png', '17-restart-scene-rain.png', '20-restart-selected.png',
                         '21-restart-selected-playback.png'],
        'method': '执行者驱动真实桌面鼠标键盘与原生文件选择器，并检查截图、文件和媒体；非用户本人操作验收。'})
    print('PASS: A-01 preserved; dual assets; 3 decoded MP4s; retry; selected trace; immutable snapshots; frozen docs')


if __name__ == '__main__':
    main()
