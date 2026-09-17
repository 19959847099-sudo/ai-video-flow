"""Read-only selected-media assembly; production facts remain independent of OTIO."""
import json,math,os,shutil,subprocess,hashlib
from pathlib import Path
from fractions import Fraction
from urllib.parse import quote,unquote
from pydantic import Field,model_validator
from .core import Record,new_id,write_json
from .audio_production import AudioProduction,digest
from .alignment import AlignmentProduction,timestamp
from .fal_adapter import ProductionRunner
from .production import media_tool,run_media

class TimelineDefinition(Record):
    id:str=Field(default_factory=new_id)
    name:str=Field(min_length=1)
    shot_ids:list[str]=Field(default_factory=list,max_length=50)
    allow_missing_audio:bool=False
    allow_missing_subtitles:bool=False
    policy:str='video-driven-trim; source-muted; dialogue-sequential; sidecar-srt'
    is_example:bool=True
    @model_validator(mode='after')
    def unique(self):
        if len(set(self.shot_ids))!=len(self.shot_ids):raise ValueError('Shot 顺序不可重复')
        if self.policy!='video-driven-trim; source-muted; dialogue-sequential; sidecar-srt':raise ValueError('未知装配策略')
        return self

def probe(path,kind):
    data=json.loads(run_media([media_tool('ffprobe'),'-v','error','-show_streams','-show_format','-of','json',str(path)]))
    stream=next((s for s in data['streams'] if s['codec_type']==kind),None)
    if not stream:raise ValueError('缺少 '+kind+' stream')
    duration=float(stream.get('duration',data['format'].get('duration',0)))
    if not math.isfinite(duration) or duration<=0:raise ValueError('无效媒体时长')
    result={k:stream[k] for k in ('codec_name','width','height','avg_frame_rate','r_frame_rate','time_base','sample_rate','channels') if k in stream}
    result['duration']=duration
    if kind=='video':
        rate=Fraction(result['avg_frame_rate'])
        if rate<=0 or rate>120:raise ValueError('V0 支持 0～120 fps 媒体')
        result['rate']=str(rate)
    return result

def fingerprint(value):return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True).encode()).hexdigest()

class RoughCutProduction:
    def __init__(self,store):self.store=store;self.video=ProductionRunner(store);self.audio=AudioProduction(store)
    def definitions(self):return [TimelineDefinition.model_validate_json(p.read_text(encoding='utf-8')) for p in sorted(self.store.path('timelines').glob('*.json'))]
    def definition(self,identifier):return TimelineDefinition.model_validate_json(self.store.record_path('timelines',identifier).read_text(encoding='utf-8'))
    def save(self,value):
        value=TimelineDefinition.model_validate(value.model_dump())
        for sid in value.shot_ids:
            if not self.store.record_path('shots',sid).is_file():raise ValueError('Shot 不存在')
        write_json(self.store.record_path('timelines',value.id),value.model_dump());return value
    def resolve(self,identifier):
        definition=self.definition(identifier);errors=[];warnings=[];clips=[];rate=None;cursor=0
        if not definition.shot_ids:errors.append('没有 Shot：请明确添加并保存顺序')
        for sid in definition.shot_ids:
            try:
                shot=next(s for s in self.store.shots() if s.id==sid);review=self.video.review(sid)
                if not review.selected_result_id:raise ValueError('Missing Selected Take；不会使用候选')
                result,task=self.video.trace(review.selected_result_id)
                if result.shot_id!=sid or result.id!=review.selected_result_id or result.id in review.rejected:raise ValueError('Selected Video 关联不匹配')
                metadata=probe(self.store.path(result.path),'video');source_rate=Fraction(metadata['rate']);rate=rate or source_rate
                frames=int(Fraction(str(metadata['duration']))*rate+Fraction(1,100000))
                if frames<1:raise ValueError('视频不足一个时间线帧')
                duration=float(frames/rate)
                if source_rate!=rate:warnings.append(sid[:8]+': 混合帧率，Preview 转为 '+str(rate)+' fps；原帧率保留')
                audios=[];subtitles=[];audio_cursor=0.0;dialogues=self.audio.dialogues(sid)
                if not dialogues:
                    (warnings if definition.allow_missing_audio else errors).append(sid[:8]+': 无 Dialogue，需人工允许无音频 Shot')
                for d in dialogues:
                    selected=self.audio.review(d.id).selected_result_id
                    if not selected:
                        (warnings if definition.allow_missing_audio else errors).append(d.id[:8]+': audio missing / pending human selection')
                        continue
                    ar,at=self.audio.trace(selected)
                    if ar.dialogue_id!=d.id or ar.shot_id!=sid or selected in self.audio.review(d.id).rejected:raise ValueError('Selected Audio 关联错误')
                    am=probe(self.store.path(ar.path),'audio');used=max(0,min(am['duration'],duration-audio_cursor))
                    if used<am['duration']:warnings.append(d.id[:8]+f': video-driven trim {am["duration"]:.3f}s → {used:.3f}s')
                    alignment=AlignmentProduction(self.audio).get(selected)
                    if alignment is None:
                        (warnings if definition.allow_missing_subtitles else errors).append(d.id[:8]+': 当前 Selected Audio 没有字幕；旧字幕不复用')
                    if used>0:
                        a=dict(dialogue_id=d.id,result_id=ar.id,task_id=at.id,voice_id=ar.voice_id,path=ar.path,sha256=ar.sha256,metadata=am,source_in=0,source_out=used,offset=audio_cursor,duration=used)
                        if alignment:
                            a.update(alignment_id=alignment.id,subtitle_path=alignment.subtitle_path,subtitle_sha256=alignment.subtitle_sha256)
                            for seg in alignment.segments:
                                start=max(0,seg.start);end=min(used,seg.end)
                                if end>start:subtitles.append(dict(start=float(cursor/rate)+audio_cursor+start,end=float(cursor/rate)+audio_cursor+end,text='[FIXTURE] '+seg.text,audio_result_id=ar.id,alignment_id=alignment.id))
                        audios.append(a)
                    audio_cursor+=used
                clips.append(dict(shot_id=sid,name=shot.description,result_id=result.id,task_id=task.id,take_number=result.take_number,path=result.path,sha256=result.sha256,metadata=metadata,source_in=0,source_out=duration,timeline_in=cursor,timeline_out=cursor+frames,frames=frames,audios=audios,subtitles=subtitles))
                cursor+=frames
            except (ValueError,OSError,StopIteration,KeyError) as exc:errors.append(sid[:8]+': '+str(exc))
        return dict(timeline=definition.model_dump(),status='Blocked' if errors else 'Ready',errors=errors,warnings=warnings,rate=str(rate or 1),duration_frames=cursor,duration=float(cursor/(rate or 1)),clips=clips,label='ROUGH CUT / FIXTURE SOURCE MEDIA / NOT FINAL MASTER')
    def folder(self,build_id):
        self.store.record_path('rough_cut_builds',build_id);return self.store.path('rough_cut_builds/'+build_id)
    def current(self,identifier):
        p=self.store.record_path('rough_cut_current',identifier)
        if not p.exists():raise ValueError('Draft：请先 Build Timeline')
        build_id=json.loads(p.read_text(encoding='utf-8'))['build_id'];folder=self.folder(build_id)
        manifest=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
        if manifest['timeline']['id']!=identifier or manifest['build_id']!=build_id:raise ValueError('Timeline build 关联错误')
        current=self.resolve(identifier)
        if fingerprint(current)!=manifest['source_fingerprint']:raise ValueError('STALE：顺序 / Selection / 来源已变化，请重新 Build')
        if fingerprint({k:v for k,v in manifest.items() if k not in ('build_id','source_fingerprint')})!=manifest['source_fingerprint']:raise ValueError('Manifest 内容已改变，请重新 Build')
        return folder,manifest
    def build(self,identifier):
        m=self.resolve(identifier)
        if m['errors']:raise ValueError('\n'.join(m['errors']))
        source_fingerprint=fingerprint(m);build_id=new_id();folder=self.folder(build_id);folder.mkdir(parents=True)
        m.update(build_id=build_id,source_fingerprint=source_fingerprint)
        write_json(folder/'manifest.json',m);self.write_otio(m,folder)
        self.write_srt(m,folder/'subtitles.srt')
        write_json(self.store.record_path('rough_cut_current',identifier),dict(build_id=build_id))
        return folder,m
    def write_srt(self,m,path):
        entries=[s for c in m['clips'] for s in c['subtitles']]
        path.write_text('\n\n'.join(f'{i}\n{timestamp(s["start"])} --> {timestamp(s["end"])}\n{s["text"]}' for i,s in enumerate(entries,1))+'\n',encoding='utf-8')
    def write_otio(self,m,folder,paths=None):
        import opentimelineio as otio
        rate=float(Fraction(m['rate']));rt=otio.opentime.RationalTime;tr=otio.opentime.TimeRange
        timeline=otio.schema.Timeline(name=m['timeline']['name'],global_start_time=rt(0,rate),metadata={'aigc':dict(timeline_id=m['timeline']['id'],build_id=m['build_id'],label=m['label'],policy=m['timeline']['policy'])})
        video=otio.schema.Track(name='Selected Video — MUTE SOURCE AUDIO IN NLE',kind=otio.schema.TrackKind.Video)
        audio=otio.schema.Track(name='Selected Dialogue',kind=otio.schema.TrackKind.Audio)
        def clip(item,duration,kind):
            target=paths[item['path']] if paths else Path(os.path.relpath(self.store.path(item['path']),folder)).as_posix()
            ref=otio.schema.ExternalReference(target_url=quote(target,safe='/.:_-'),available_range=tr(rt(0,rate),rt(item['metadata']['duration']*rate,rate)))
            metadata={k:item[k] for k in ('shot_id','dialogue_id','result_id','task_id','sha256') if k in item};metadata.update(source_metadata=item['metadata'],kind=kind)
            return otio.schema.Clip(name=item.get('name',item['result_id']),media_reference=ref,source_range=tr(rt(0,rate),rt(duration*rate,rate)),metadata={'aigc':metadata})
        audio_end=0.0
        for c in m['clips']:
            video.append(clip(c,c['frames']/rate,'video'))
            for a in c['audios']:
                start=c['timeline_in']/rate+a['offset']
                if start>audio_end:audio.append(otio.schema.Gap(source_range=tr(rt(0,rate),rt((start-audio_end)*rate,rate))))
                audio.append(clip(dict(a,shot_id=c['shot_id']),a['duration'],'audio'));audio_end=start+a['duration']
        if audio_end<m['duration']:audio.append(otio.schema.Gap(source_range=tr(rt(0,rate),rt((m['duration']-audio_end)*rate,rate))))
        timeline.tracks.extend([video,audio]);otio.adapters.write_to_file(timeline,str(folder/'timeline.otio'))
        restored=otio.adapters.read_from_file(str(folder/'timeline.otio'))
        if not timeline.is_equivalent_to(restored):raise ValueError('OTIO round-trip 语义不一致')
        write_json(folder/'otio-inspection.json',dict(version=otio.__version__,video_clips=len(restored.video_tracks()[0]),audio_clips=len(list(restored.audio_tracks()[0].find_clips())),duration=restored.duration().to_seconds(),shot_order=[c.metadata['aigc']['shot_id'] for c in restored.video_tracks()[0]],round_trip=True))
    def preview(self,identifier):
        folder,m=self.current(identifier);rate=m['rate'];first=m['clips'][0]['metadata'];width=min(960,first['width']);width-=width%2;height=round(width*first['height']/first['width']/2)*2
        parts=[];commands=[]
        for i,c in enumerate(m['clips']):
            duration=c['frames']/float(Fraction(rate));output=folder/f'part-{i}.mp4';cmd=[media_tool('ffmpeg'),'-y','-v','error','-i',str(self.store.path(c['path']))]
            for a in c['audios']:cmd+=['-i',str(self.store.path(a['path']))]
            vf=f'[0:v]scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,fps={rate},tpad=stop_mode=clone:stop_duration=1,trim=duration={duration},setpts=PTS-STARTPTS[v]'
            filters=[vf];labels=[];cursor=0.0;idx=0
            for j,a in enumerate(c['audios'],1):
                gap=a['offset']-cursor
                if gap>0:
                    filters.append(f'anullsrc=r=48000:cl=mono,atrim=duration={gap}[g{idx}]');labels.append(f'[g{idx}]');idx+=1
                filters.append(f'[{j}:a]atrim=duration={a["duration"]},asetpts=PTS-STARTPTS,aresample=48000,aformat=channel_layouts=mono[a{j}]');labels.append(f'[a{j}]');cursor=a['offset']+a['duration']
            if duration-cursor>0.000001 or not labels:
                filters.append(f'anullsrc=r=48000:cl=mono,atrim=duration={max(duration-cursor,0.000001)}[silence]');labels.append('[silence]')
            filters.append(''.join(labels)+f'concat=n={len(labels)}:v=0:a=1[a]')
            cmd+=['-filter_complex',';'.join(filters),'-map','[v]','-map','[a]','-t',str(duration),'-c:v','libx264','-preset','ultrafast','-crf','18','-pix_fmt','yuv420p','-c:a','aac','-ar','48000','-ac','1',str(output)]
            commands.append(cmd);run_media(cmd);parts.append(output)
        # Safe generated basenames, never interpolate external filenames into concat syntax.
        listing=folder/'concat.txt';listing.write_text('\n'.join("file '"+p.name+"'" for p in parts),encoding='utf-8')
        out=folder/'rough-cut.mp4';cmd=[media_tool('ffmpeg'),'-y','-v','error','-f','concat','-safe','1','-i',str(listing),'-c:v','copy','-c:a','aac','-t',str(m['duration']),'-movflags','+faststart',str(out)];run_media(cmd);commands.append(cmd)
        vm=probe(out,'video');am=probe(out,'audio')
        if abs(vm['duration']-m['duration'])>1/float(Fraction(rate))+0.01:raise ValueError('Preview 时长不匹配')
        write_json(folder/'preview.json',dict(path='rough-cut.mp4',sha256=digest(out),video=vm,audio=am,label=m['label']))
        # Commands are audit output, not an executable shell script.
        write_json(folder/'assembly-plan.json',dict(policy=m['timeline']['policy'],commands=commands))
        for part in parts:part.unlink()
        listing.unlink();return folder,m
    def export(self,identifier):
        folder,m=self.current(identifier)
        if not (folder/'preview.json').exists():raise ValueError('请先 Generate Preview')
        preview=json.loads((folder/'preview.json').read_text(encoding='utf-8'))
        if digest(folder/'rough-cut.mp4')!=preview['sha256']:raise ValueError('Preview 已改变')
        package=self.store.path('handoffs/'+new_id());package.mkdir(parents=True);(package/'media').mkdir();paths={}
        for c in m['clips']:
            for item in [c]+c['audios']:
                relative='media/'+item['sha256']+Path(item['path']).suffix.lower();paths[item['path']]=relative
                destination=package/relative
                if not destination.exists():shutil.copyfile(self.store.path(item['path']),destination)
                if item.get('subtitle_path'):
                    subtitle='media/'+item['subtitle_sha256']+'.srt';paths[item['subtitle_path']]=subtitle
                    if not (package/subtitle).exists():shutil.copyfile(self.store.path(item['subtitle_path']),package/subtitle)
        self.write_otio(m,package,paths);self.write_srt(m,package/'subtitles.srt')
        portable=json.loads(json.dumps(m))
        for c in portable['clips']:
            for item in [c]+c['audios']:
                item['production_path']=item['path'];item['path']=paths[item['path']]
                if item.get('subtitle_path'):
                    item['production_subtitle_path']=item['subtitle_path'];item['subtitle_path']=paths[item['subtitle_path']]
        portable['package_media_root']='.';write_json(package/'manifest.json',portable)
        shutil.copyfile(folder/'rough-cut.mp4',package/'rough-cut.mp4')
        (package/'README.txt').write_text('DaVinci Resolve OTIO handoff\nROUGH CUT / FIXTURE SOURCE MEDIA / NOT FINAL MASTER\nImport timeline.otio in a Resolve version with OTIO import support (18.5+).\nRelink media/ if relative references are not resolved automatically.\nIMPORTANT: mute embedded source-video audio; use Selected Dialogue track only.\nImport subtitles.srt separately at timeline start 00:00:00.\nVideo-driven trim: dialogue beyond each video duration is trimmed; missing approved dialogue is silence.\nVerify duration, rate, order, audio and subtitles before editing.\nOTIO read/write and portable files verified; actual Resolve GUI import NOT verified.\nNo guarantee of custom metadata, track audio routing or subtitle styles in NLE.\n',encoding='utf-8')
        write_json(folder/'handoff.json',dict(path=package.relative_to(self.store.root).as_posix()))
        return package
    def play(self,identifier):
        folder,m=self.current(identifier);info=json.loads((folder/'preview.json').read_text(encoding='utf-8'))
        if digest(folder/'rough-cut.mp4')!=info['sha256']:raise ValueError('Preview 哈希不匹配')
        return subprocess.Popen([media_tool('ffplay'),'-autoexit','-loglevel','error','-window_title','A-08 ROUGH CUT PREVIEW',str(folder/'rough-cut.mp4')],creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
