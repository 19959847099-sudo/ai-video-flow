"""Read-only integrity and GUI-created delivery-data verification for A-05."""
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.core import Store
from app.fal_adapter import ProductionRunner
from app.production import probe_video
from app.ui_presenters import harness_summary, take_state


def main():
    evidence=ROOT/'evidence/A-05'
    baseline=json.loads((evidence/'baseline.json').read_text(encoding='utf-8'))
    protected={p:h for p,h in baseline.items() if p.startswith(('data/','schemas/','integrations/','重要文档/'))
        or p in ('app/core.py','app/production.py','app/fal_adapter.py','requirements.txt','start.cmd')}
    for path,digest in protected.items():
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest,path
    original=ProductionRunner(Store(ROOT/'data'))
    for job in original.executions():
        if job.status=='completed':original.trace(job.result_id)
    runner=ProductionRunner(Store(evidence/'gui-data'))
    shot=next(s for s in runner.store.shots() if s.description=='A-05 示例镜头 雨夜审核')
    assert shot.is_example and shot.scene_id
    jobs=runner.executions(shot.id)
    assert len(jobs)==2 and all(j.status=='completed' and j.provider=='fal' for j in jobs)
    assert jobs[1].retry_of==jobs[0].result_id and jobs[0].task_id!=jobs[1].task_id
    review=runner.review(shot.id)
    assert review.selected_result_id==jobs[1].result_id and jobs[0].result_id in review.rejected
    assert 'A-05' in review.rejected[jobs[0].result_id]
    assert take_state(jobs[1],review)[0]=='SELECTED'
    assert take_state(jobs[0],review)[0]=='REJECTED'
    for job in jobs:
        result,task=runner.trace(job.result_id)
        assert task.shot.id==shot.id and task.character.id==shot.character_id and task.scene.id==shot.scene_id
        assert len(task.references)==len(task.scene_references)==2
        assert task.is_example and job.simulation_only
        media=probe_video(runner.store.path(result.path))
        assert (media['codec_name'],media['width'],media['height'],media['duration'])==('h264',640,360,3)
        exchange=json.loads(runner.store.path(f'tasks/{task.id}/provider_exchange.json').read_text(encoding='utf-8'))
        assert exchange['api_called'] is False
    assert '停顿两秒' in runner.submitted_prompt(jobs[1].task_id)
    # Editing source assets in the GUI copy must not rewrite old task snapshots.
    for path,digest in baseline.items():
        if path.startswith('data/tasks/') and path.endswith('/task.json'):
            assert hashlib.sha256((evidence/'gui-data'/path[5:]).read_bytes()).hexdigest()==digest
    dsh_job=original.execution('6b975d8c237e4c8f97f8d7cee7f91d47')
    assert 'ffprobe' in harness_summary(ROOT,dsh_job)[0]
    print(json.dumps(dict(status='PASS',protected_files_unchanged=len(protected),frozen_documents_unchanged=3,
        original_executions=len(original.executions()),gui_shot_id=shot.id,
        gui_task_ids=[j.task_id for j in jobs],gui_result_ids=[j.result_id for j in jobs],
        selected_result_id=review.selected_result_id,api_calls=0,media=media),indent=2))


if __name__=='__main__':main()
