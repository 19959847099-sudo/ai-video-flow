"""Read-only A-08 delivery audit, including decoded media order and audio policy."""
import json,sys,shutil,tempfile,math,array
from pathlib import Path
from urllib.parse import unquote
from fractions import Fraction
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import opentimelineio as otio
from app.core import Store
from app.audio_production import digest
from app.rough_cut import RoughCutProduction,probe
from app.production import media_tool,run_media
ID='3bb952d7018548bcbd60b7e8ae9e5297'

def verify():
 e=ROOT/'evidence/A-08';baseline=json.loads((e/'baseline.json').read_text(encoding='utf-8'))
 allowed={'app/gui.py','README.md','requirements.txt','integrations/production_bridge.py','integrations/dsh/production-plugin.mjs','tools/run_harness.py'}
 protected={p:h for p,h in baseline.items() if p not in allowed}
 for p,h in protected.items():assert digest(ROOT/p)==h,p
 s=Store(e/'gui-data');r=RoughCutProduction(s);folder,m=r.current(ID)
 for p in (ROOT/'evidence/A-07/gui-data').rglob('*'):
  if p.is_file():assert digest(s.root/p.relative_to(ROOT/'evidence/A-07/gui-data'))==digest(p),str(p)
 assert m['timeline']['shot_ids']==['d8094901e03441f1bb9ad8696bb427c0','cda53866e184457587a2b671ff062482']
 t=otio.adapters.read_from_file(str(folder/'timeline.otio'));assert len(t.video_tracks()[0])==2
 assert len(list(t.audio_tracks()[0].find_clips()))==1
 assert abs(t.duration().to_seconds()-6)<1e-8
 for c in t.find_clips():assert digest(folder/unquote(c.media_reference.target_url))==c.metadata['aigc']['sha256']
 video=probe(folder/'rough-cut.mp4','video');audio=probe(folder/'rough-cut.mp4','audio')
 assert video['duration']==6 and video['rate']=='24'
 # Decode actual pixels at each shot midpoint; compare against the expected selected source.
 def pixels(path,second):return run_media([media_tool('ffmpeg'),'-v','error','-ss',str(second),'-i',str(path),'-frames:v','1','-vf','scale=160:90','-f','rawvideo','-pix_fmt','rgb24','-'])
 visual=[]
 for c in m['clips']:
  preview=pixels(folder/'rough-cut.mp4',c['timeline_in']/float(Fraction(m['rate']))+.5);source=pixels(s.path(c['path']),.5)
  assert len(preview)==len(source)==160*90*3
  error=sum(abs(x-y) for x,y in zip(preview,source))/len(source);assert error<5,error
  visual.append(dict(shot_id=c['shot_id'],mean_pixel_error=error))
 raw=run_media([media_tool('ffmpeg'),'-v','error','-i',str(folder/'rough-cut.mp4'),'-vn','-f','f32le','-ac','1','-ar','48000','-']);samples=array.array('f');samples.frombytes(raw)
 def rms(start,end):
  values=samples[int(start*48000):int(end*48000)];return math.sqrt(sum(x*x for x in values)/len(values))
 voiced=rms(.3,1.3);silent=rms(3.5,5.5);assert voiced>.02 and silent<.0001,(voiced,silent)
 trace=json.loads((e/'dsh-run/trace.json').read_text(encoding='utf-8'));assert trace['result']['human_gate_unchanged'] and trace['result']['human_review_required']
 assert trace['result']['build_id']==m['build_id']
 # GUI exported a package before the later DSH rebuild. That immutable package remains valid.
 package=s.path(json.loads((folder/'handoff.json').read_text(encoding='utf-8'))['path'])
 with tempfile.TemporaryDirectory() as td:
  moved=Path(td)/'relocated-handoff';shutil.copytree(package,moved);timeline=otio.adapters.read_from_file(str(moved/'timeline.otio'))
  for c in timeline.find_clips():assert digest(moved/unquote(c.media_reference.target_url))==c.metadata['aigc']['sha256']
  assert probe(moved/'rough-cut.mp4','video')['duration']==6
  pm=json.loads((moved/'manifest.json').read_text(encoding='utf-8'))
  for c in pm['clips']:
   for a in c['audios']:assert digest(moved/a['subtitle_path'])==a['subtitle_sha256']
  assert '00:00:02,100 --> 00:00:03,000' in (moved/'subtitles.srt').read_text(encoding='utf-8')
 audit=json.loads((e/'gui-network-audit.json').read_text(encoding='utf-8'));assert not audit['socket_connection_attempts']
 assert not (e/'gui-stderr.txt').read_text(encoding='utf-8')
 return dict(status='PASS',protected_files=len(protected),timeline_id=ID,build_id=m['build_id'],otio_version=otio.__version__,manifest=str(folder.relative_to(ROOT)/'manifest.json'),handoff=str(package.relative_to(ROOT)),video=video,audio=audio,decoded_shot_order=visual,audio_policy_rms=dict(dialogue=voiced,silence=silent),portable_relocation=True,human_gate_unchanged=True,real_api_calls=0,generation_cost=0)

if __name__=='__main__':print(json.dumps(verify(),ensure_ascii=False,indent=2))
