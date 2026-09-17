"""Read-only audit of the A-07 delivery fixture and preserved earlier data."""
import sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.core import Store
from app.audio_production import AudioProduction,digest,probe_audio
from app.alignment import AlignmentProduction
from app.fal_adapter import ProductionRunner
from app.image_production import ImageProduction

def verify():
 e=ROOT/'evidence/A-07';baseline=json.loads((e/'baseline.json').read_text(encoding='utf-8'))
 allowed={'app/gui.py','app/workspace_ui.py','README.md','integrations/production_bridge.py','integrations/dsh/production-plugin.mjs','tools/run_harness.py'}
 protected={p:h for p,h in baseline.items() if p not in allowed}
 for p,h in protected.items():assert digest(ROOT/p)==h,p
 s=Store(e/'gui-data');a=AudioProduction(s);align=AlignmentProduction(a)
 voice=a.voices()[0];assert a.default_voice(voice.character_id).id==voice.id
 for ref in voice.references:assert digest(s.path(ref.path))==ref.sha256
 assert voice.references and voice.is_example
 d=a.dialogue('5c235da8a53240a789836abacaa80d11');assert [x.order for x in a.dialogues(d.shot_id)]==[1,2]
 jobs=a.jobs(d.id);assert len(jobs)==3
 media=[]
 for j in jobs:
  assert j.history==['pending','processing','completed']
  r,t=a.trace(j.id);al=align.get(r.id);assert al and al.fixture and al.expected_text!=al.transcript
  assert all(w.score is None for seg in al.segments for w in seg.words)
  media.append(dict(result_id=r.id,task_id=t.id,metadata=probe_audio(s.path(r.path)),subtitle=al.subtitle_path))
 first,second,third=jobs;review=a.review(d.id)
 assert first.id in review.rejected and review.selected_result_id==second.id
 assert a.task(second.task_id).retry_of==first.id and a.task(second.task_id).delivery=='whisper'
 assert a.task(second.task_id).text!=a.task(first.task_id).text
 trace=json.loads((e/'dsh-run/trace.json').read_text(encoding='utf-8'))
 assert [x['tool'] for x in trace['steps']]==['prepare_dialogue_audio']
 assert trace['result']['result_id']==third.id and trace['result']['human_gate_unchanged']
 for j in ProductionRunner(s).executions():
  if j.result_id:ProductionRunner(s).trace(j.result_id)
 for j in ImageProduction(s).jobs():
  if j.result_id:ImageProduction(s).trace(j.result_id)
 # Every pre-existing visual production record in the copied workspace remains byte-identical.
 for p in (ROOT/'evidence/A-06/gui-data').rglob('*'):
  if p.is_file():assert digest(s.root/p.relative_to(ROOT/'evidence/A-06/gui-data'))==digest(p),str(p)
 audit=json.loads((e/'gui-network-audit.json').read_text());assert not audit['socket_connection_attempts']
 assert not (e/'gui-stderr.txt').read_text()
 return dict(status='PASS',protected_files=len(protected),voice_id=voice.id,dialogue_id=d.id,selected_audio=second.id,dsh_candidate=third.id,media=media,handoff=a.handoff(d.shot_id),tts_calls=0,comfy_calls=0,kling_calls=0,alignment_model_executed=False)

if __name__=='__main__':print(json.dumps(verify(),ensure_ascii=False,indent=2))
