"""Read-only verification of the fixed A-06 delivery example, not user data constraints."""
import json,hashlib,sys,base64
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.core import Store
from app.image_production import ImageProduction,digest
from app.comfy_adapter import WorkflowBuilder
from app.fal_adapter import ProductionRunner
from app.production import probe_video

def verify():
 e=ROOT/'evidence/A-06';baseline=json.loads((e/'baseline.json').read_text(encoding='utf-8'))
 protected={p:h for p,h in baseline.items() if p.startswith(('data/','重要文档/','tests/')) or p in ('requirements.txt','start.cmd')}
 for p,h in protected.items():assert digest(ROOT/p)==h,p
 original=Store(ROOT/'data');runner=ProductionRunner(original)
 for job in runner.executions():
  if job.result_id:runner.trace(job.result_id)
 s=Store(e/'gui-data');images=ImageProduction(s);summary=[]
 for job in images.jobs():
  assert job.status=='completed',job.error
  r,t=images.trace(job.result_id)
  with Image.open(s.path(r.path)) as im:im.verify()
  workflow=json.loads((images.folder(t.id)/'workflow.json').read_text(encoding='utf-8'))
  WorkflowBuilder.validate(workflow['payload']['prompt'])
  assert workflow['payload']['prompt']['6']['inputs']['text']==t.final_prompt
  assert [b['reference_id'] for b in workflow['reference_bindings']]==[r.id for r in t.references+t.scene_references]
  review=images.review(r.id)
  if review.promotion in ('identity','variant'):
   asset=s.character(t.character.id) if t.character else s.scene(t.scene.id)
   ref=next(ref for ref in asset.references if ref.id==review.reference_id)
   assert ref.source_image_result_id==r.id and digest(s.path(ref.path))==r.sha256
  summary.append(dict(purpose=t.purpose,task_id=t.id,result_id=r.id,path=r.path,retry_of=t.retry_of,promotion=review.promotion,rejected=review.rejected))
 assert {x['purpose'] for x in summary}=={'CHARACTER_REFERENCE','SCENE_REFERENCE','SHOT_FIRST_FRAME'}
 snapshot=json.loads((e/'snapshot-check.json').read_text(encoding='utf-8'))
 for path,h in snapshot['image_task_hashes'].items():assert digest(ROOT/path)==h
 for path,h in baseline.items():
  if path.startswith('data/tasks/') and path.endswith('/task.json'):assert digest(s.root/path.removeprefix('data/'))==h
 shot='d8094901e03441f1bb9ad8696bb427c0';task=s.task(shot)
 assert task.first_frame.result_id=='2892d2e785254fc694fc5f754f5a496d'
 video=ProductionRunner(s);result,submitted=video.trace('a9782a10334247d5aec68d48ac3cba3b')
 assert submitted.first_frame==task.first_frame
 request=json.loads(s.path(f'tasks/{submitted.id}/provider_request.json').read_text(encoding='utf-8'))
 assert base64.b64decode(request['body']['start_image_url'].split(',',1)[1])==s.path(task.first_frame.path).read_bytes()
 assert len(request['body']['image_urls'])==4
 assert video.review(shot).selected_result_id=='2cb8df46592b47f5a7284946e73ed280'
 trace=json.loads((e/'dsh-final/trace.json').read_text(encoding='utf-8'));audit=json.loads((e/'dsh-final/network-audit.json').read_text(encoding='utf-8'))
 assert trace['status']=='completed' and trace['result']['human_review_required'] and not audit['network_attempts']
 assert not images.review(trace['result']['result_id']).promotion
 assert [x['tool'] for x in trace['steps']]==['get_shot_context','prepare_shot_first_frame','get_shot_context']
 exchange=json.loads((images.folder(trace['result']['task_id'])/'exchange.json').read_text(encoding='utf-8'))
 assert exchange[0]['request']['files']['image']['local_path']
 assert any(x['path'].startswith('/view?') for x in exchange)
 return dict(status='PASS',protected_files=len(protected),frozen_documents_unchanged=True,original_data_unchanged=True,
  original_counts=dict(characters=len(original.characters()),scenes=len(original.scenes()),shots=len(original.shots()),video_executions=len(runner.executions())),
  image_runs=summary,first_frame=task.first_frame.model_dump(),video_handoff=dict(task_id=submitted.id,result_id=result.id,media=probe_video(s.path(result.path))),
  dsh_result_id=trace['result']['result_id'],human_gate_unchanged=True,api_calls=0,generation_cost=0)

if __name__=='__main__':print(json.dumps(verify(),ensure_ascii=False,indent=2))
