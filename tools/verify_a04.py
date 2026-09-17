"""Read-only verification of the delivered A-04 example and preserved baseline."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.core import Store
from app.fal_adapter import ProductionRunner
from app.production import probe_video


def main():
    evidence = ROOT/'evidence/A-04'
    read = lambda p: json.loads(p.read_text(encoding='utf-8-sig'))
    baseline = read(evidence/'baseline.json')
    protected = {p: h for p, h in baseline.items() if p != 'README.md'}
    for path, digest in protected.items():
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest() == digest, path
    trace = read(evidence/'production-run/trace.json')
    names = ['get_shot_context', 'build_generation_task', 'dry_run_generation', 'inspect_media', 'get_shot_context']
    assert trace['status'] == 'completed' and trace['version'] == '0.1.5-rc.2'
    assert [s['tool'] for s in trace['steps']] == names
    assert [s['tool'] for s in trace['observed_tool_results']] == names
    assert all(s['status'] == 'completed' for s in trace['steps'])
    audit = read(evidence/'production-run/network-audit.json')
    assert audit['network_attempts'] == []
    assert audit['video_api_calls'] == audit['model_api_calls'] == 0
    runner = ProductionRunner(Store(ROOT/'data'))
    result, task = runner.trace(trace['result']['result_id'])
    job = runner.execution(result.id)
    assert task.id == trace['result']['task_id'] and result.shot_id == trace['shot_id']
    assert job.history == ['pending', 'processing', 'completed'] and job.simulation_only
    assert len(task.references) == len(task.scene_references) == 2
    assert task.character.id == task.shot.character_id and task.look.id == task.shot.look_id
    assert task.scene.id == task.shot.scene_id and task.scene_state.id == task.shot.scene_state_id
    assert task.final_prompt and runner.submitted_prompt(task.id).startswith(task.final_prompt)
    assert runner.review(result.shot_id).selected_result_id is None
    assert trace['result']['human_gate_unchanged']
    exchange = read(ROOT/f'data/tasks/{task.id}/provider_exchange.json')
    assert exchange['api_called'] is False and exchange['request_id'] == job.id
    media = probe_video(ROOT/'data'/result.path)
    assert (media['codec_name'], media['width'], media['height'], media['duration']) == ('h264', 640, 360, 3)
    for previous in runner.executions():
        if previous.status == 'completed': runner.trace(previous.result_id)
    assert read(evidence/'dsh-stopped.json')['dsh_process_count'] == 0
    assert not (evidence/'gui.stderr.txt').read_text().strip()
    for name in ('gui-harness-result.png', 'gui-harness-playback.png'):
        assert (evidence/name).stat().st_size > 1000
    print(json.dumps(dict(status='PASS', protected_files_unchanged=len(protected),
        frozen_documents_unchanged=3, official_dsh_tool_calls=5, video_api_calls=0,
        model_api_calls=0, result_id=result.id, task_id=task.id, media=media,
        human_gate_unchanged=True, executions=len(runner.executions())), indent=2))


if __name__ == '__main__': main()
