"""Read-only delivery verification against A-02 baseline and GUI-created examples."""
import base64
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.core import Store, GenerationTask
from app.fal_adapter import ProductionRunner, MODEL
from app.production import probe_video


def main():
    evidence = ROOT / 'evidence/A-03'
    baseline = json.loads((evidence/'baseline.json').read_text(encoding='utf-8'))
    protected = {p: h for p, h in baseline.items() if p.startswith(('data/', '重要文档/')) or p in ('app/core.py', 'start.cmd', 'requirements.txt')}
    for path, sha in protected.items():
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest() == sha, path
    store = Store(ROOT/'data'); runner = ProductionRunner(store)
    tasks = [GenerationTask.model_validate_json(p.read_text(encoding='utf-8')) for p in store.path('tasks').glob('*/task.json')]
    for job in runner.executions():
        if job.status == 'completed': runner.trace(job.result_id)
    day = next(s for s in store.shots() if s.description == 'A-03 示例镜头 fal 白天门口')
    rain = next(s for s in store.shots() if s.description == 'A-03 示例镜头 雨夜回归')
    assert day.is_example and rain.is_example
    assert (day.character_id, day.scene_id) == (rain.character_id, rain.scene_id)
    assert (day.look_id, day.scene_state_id) != (rain.look_id, rain.scene_state_id)
    jobs = runner.executions(day.id)
    assert len(jobs) == 2 and all(j.provider == 'fal' and j.status == 'completed' for j in jobs)
    assert jobs[1].retry_of == jobs[0].result_id and jobs[0].task_id != jobs[1].task_id
    review = runner.review(day.id)
    assert review.selected_result_id == jobs[1].result_id and jobs[0].result_id in review.rejected
    for job in jobs:
        result, task = runner.trace(job.result_id)
        folder = store.path(f'tasks/{task.id}')
        request = json.loads((folder/'provider_request.json').read_text(encoding='utf-8'))
        exchange = json.loads((folder/'provider_exchange.json').read_text(encoding='utf-8'))
        assert request['model'] == MODEL and request['transport'] == 'fixture'
        assert exchange['api_called'] is False and exchange['request_id'] == job.id
        states = [e['body'].get('status') for e in exchange['events'][1:4]]
        assert states == ['IN_QUEUE', 'IN_PROGRESS', 'COMPLETED']
        assert len(exchange['events']) == 5 and exchange['ready']
        assert request['body']['prompt'].startswith(task.final_prompt)
        for encoded, ref in zip(request['body']['image_urls'], task.references + task.scene_references, strict=True):
            assert hashlib.sha256(base64.b64decode(encoded.split(',',1)[1])).hexdigest() == ref.sha256
        media = probe_video(store.path(result.path))
        assert (media['codec_name'], media['width'], media['height'], media['duration']) == ('h264',640,360,3)
    assert '停顿两秒' in runner.submitted_prompt(jobs[1].task_id)
    assert runner.executions(rain.id)[0].provider == 'local-mock'
    assert runner.review(rain.id).selected_result_id is None
    for name in ('gui-network-audit-session1.json', 'gui-network-audit-session2.json'):
        audit = json.loads((evidence/name).read_text(encoding='utf-8'))
        assert audit == {'socket_connection_attempts':[], 'api_calls':0}
    print(json.dumps(dict(status='PASS', protected_files_unchanged=len(protected),
        characters=len(store.characters()), scenes=len(store.scenes()), shots=len(store.shots()),
        tasks=len(tasks), executions=len(runner.executions()), fal_results=len(jobs),
        selected_fal_result=review.selected_result_id, gui_network_attempts=0), indent=2))


if __name__ == '__main__': main()
