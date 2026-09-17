"""Read-only UI-Final acceptance and protection receipt."""
import hashlib,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.core import Store
from app.fal_adapter import ProductionRunner
from app.audio_production import AudioProduction
from app.image_production import ImageProduction
from app.rough_cut import RoughCutProduction,probe
from app.alignment import AlignmentProduction
root=Path(__file__).resolve().parents[1];out=root/'evidence/UI-Final'
baseline=json.loads((out/'baseline.json').read_text(encoding='utf-8'))
allowed={'app/audio_gui.py','app/gui.py','app/image_gui.py','app/review_gui.py','app/rough_cut_gui.py','app/ui_presenters.py','app/ui_widgets.py','app/workspace_ui.py'}
changed=[p for p,h in baseline.items() if not (root/p).is_file() or hashlib.sha256((root/p).read_bytes()).hexdigest()!=h]
protection=dict(baseline_files=len(baseline),changed=changed,unexpected_changes=sorted(set(changed)-allowed),frozen_documents_unchanged=all(p not in changed for p in baseline if p.startswith('重要文档/')),original_data_unchanged=all(p not in changed for p in baseline if p.startswith('data/')),a08_evidence_unchanged=all(p not in changed for p in baseline if p.startswith('evidence/A-08/')),old_tests_unchanged=all(p not in changed for p in baseline if p.startswith('tests/')),requirements_and_start_unchanged=all(p not in changed for p in ('requirements.txt','start.cmd')),production_modules_unchanged=all(p not in changed for p in baseline if p.startswith('app/') and p not in allowed))
assert not protection['unexpected_changes'],protection
(out/'data-protection.json').write_text(json.dumps(protection,ensure_ascii=False,indent=2),encoding='utf-8')
s=Store(out/'gui-data');sid='d8094901e03441f1bb9ad8696bb427c0';video=ProductionRunner(s);audio=AudioProduction(s);rough=RoughCutProduction(s)
selected=video.review(sid).selected_result_id;vr,vt=video.trace(selected)
frame=json.loads(s.record_path('first_frames',sid).read_text(encoding='utf-8'));fr,ft=ImageProduction(s).trace(frame['result_id'])
selected_audio=[]
for d in audio.dialogues(sid):
 rid=audio.review(d.id).selected_result_id
 if rid:
  ar,at=audio.trace(rid);alignment=AlignmentProduction(audio).get(rid)
  selected_audio.append(dict(dialogue_id=d.id,result_id=rid,task_id=at.id,alignment_id=alignment.id if alignment else None,media=probe(s.path(ar.path),'audio')))
folder,manifest=rough.current('3bb952d7018548bcbd60b7e8ae9e5297')
handoff=json.loads((folder/'handoff.json').read_text(encoding='utf-8'));package=s.path(handoff['path'])
import opentimelineio as otio
timeline=otio.adapters.read_from_file(str(package/'timeline.otio'))
for clip in timeline.find_clips():
 from urllib.parse import unquote
 assert (package/unquote(clip.media_reference.target_url)).is_file()
summary=dict(character_count=len(s.characters()),scene_count=len(s.scenes()),shot_count=len(s.shots()),video_take_count=len(video.executions(sid)),selected_video=dict(result_id=vr.id,task_id=vt.id,take_number=vr.take_number,character=vt.character.name,look=vt.look.name,scene=vt.scene.name,state=vt.scene_state.name,final_prompt=video.submitted_prompt(vt.id),media=probe(s.path(vr.path),'video')),selected_first_frame=frame,selected_audio=selected_audio,timeline=dict(id=manifest['timeline']['id'],build_id=manifest['build_id'],status=manifest['status'],duration=manifest['duration'],shot_order=manifest['timeline']['shot_ids'],preview=probe(folder/'rough-cut.mp4','video'),package=str(package),otio_readable=True,portable_media_exist=True),api_calls=0,truth='UI-Final isolated fixture copy, not original production data')
(out/'final-chain-verification.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(protected=protection,selected_video_take=vr.take_number,selected_audio_count=len(selected_audio),timeline_duration=manifest['duration'],handoff=str(package)),ensure_ascii=False,indent=2))
