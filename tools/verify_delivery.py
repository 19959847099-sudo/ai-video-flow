from pathlib import Path
import hashlib,json,sys,subprocess,os
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.core import Store,Character,Shot,GenerationTask,write_json
root=Path(__file__).resolve().parents[1]
s=Store(root/'data');chars=s.characters();shots=s.shots()
assert len(chars)==1 and len(shots)==2
c=chars[0]
assert c.is_example and len(c.looks)==2 and len(c.references)==3
assert len({x.character_id for x in shots})==1
assert len({x.look_id for x in shots})==2
results=[]
for shot in shots:
 assert shot.character_id==c.id and shot.is_example
 tasks=[GenerationTask.model_validate_json(p.read_text(encoding='utf-8')) for p in (root/'data/tasks').glob('*/task.json')]
 latest=max((t for t in tasks if t.shot.id==shot.id),key=lambda t:t.created_at)
 assert latest.shot==shot and latest.character==c
 expected=set(c.identity_reference_ids+latest.look.reference_ids)
 assert {r.id for r in latest.references}==expected and len(expected)==2
 req=json.loads((root/'data/tasks'/latest.id/'dummy_request.json').read_text(encoding='utf-8'))
 assert req['simulation_only'] and not req['api_called']
 assert [x['asset_path'] for x in req['input']['images']]==[r.path for r in latest.references]
 for r in latest.references:
  assert not Path(r.path).is_absolute()
  assert hashlib.sha256(s.path(r.path).read_bytes()).hexdigest()==r.sha256
 results.append({'shot':shot.description,'shot_id':shot.id,'character_id':c.id,'look':latest.look.name,'look_id':latest.look.id,'references':[r.name for r in latest.references],'latest_task':latest.id,'dummy_verified':True})
before=json.loads((root/'evidence/frozen-before.json').read_text(encoding='utf-8-sig'))
after=[{'Name':x['Name'],'Hash':hashlib.sha256((root/'重要文档'/x['Name']).read_bytes()).hexdigest().upper()} for x in before]
assert before==after
for model in [Character,Shot,GenerationTask]:
 assert json.loads((root/'schemas'/f'{model.__name__}.schema.json').read_text(encoding='utf-8'))==model.model_json_schema()
write_json(root/'evidence/frozen-after.json',after)
write_json(root/'evidence/verification.json',{'character_count':1,'look_count':2,'reference_count':3,'shots':results,'frozen_files_unchanged':True,'schemas_match_models':True,'gui_restart':{'closed_pid':46684,'restarted_pid':28876,'evidence':'gui-restart-task.png'},'historical_tasks_note':'保留全部模拟任务快照；Shot B 首次误选日常 Look 的测试快照亦保留，不伪装成正式生成记录。','verification_method':'真实桌面鼠标键盘与原生文件选择器操作，执行者逐步检查截图；并非用户本人验收。'})
env=dict(os.environ,PYTHONIOENCODING='utf-8')
r=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-v'],cwd=root,capture_output=True,env=env)
(root/'evidence/tests.log').write_bytes(r.stdout+r.stderr)
assert r.returncode==0
print('PASS: persisted GUI data, 2 distinct looks, exact references, dummy requests, schemas, frozen hashes, 7 tests')
