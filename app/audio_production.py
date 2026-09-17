"""Voice, dialogue and audio truth, independent of synthesis/alignment providers."""
from datetime import datetime,timezone
import hashlib,json,shutil,os,subprocess
from pathlib import Path
from typing import Literal
from pydantic import Field,model_validator
from .core import Record,Character,Shot,new_id,write_json
from .production import media_tool,run_media

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def probe_audio(path):
    data=json.loads(run_media([media_tool('ffprobe'),'-v','error','-select_streams','a:0','-show_entries','stream=codec_name,sample_rate,channels:format=duration,format_name','-of','json',str(path)]))
    if not data.get('streams') or float(data.get('format',{}).get('duration',0))<=0:raise ValueError('文件不含有效音频')
    return dict(**data['streams'][0],duration=float(data['format']['duration']),format_name=data['format']['format_name'])

class AudioReference(Record):
    id:str=Field(default_factory=new_id)
    name:str
    path:str
    sha256:str
    duration:float=Field(gt=0)
    is_example:bool=True

class Voice(Record):
    id:str=Field(default_factory=new_id)
    name:str=Field(min_length=1)
    character_id:str
    description:str=Field(min_length=1)
    language:str='zh'
    default_delivery:str='calm'
    notes:str=''
    references:list[AudioReference]=Field(default_factory=list)
    is_example:bool=True

class VoiceMapping(Record):
    voice_id:str
    provider:Literal['minimax']='minimax'
    provider_voice_id:str=Field(min_length=1,max_length=256)
    kind:Literal['system','clone']='system'

class Dialogue(Record):
    id:str=Field(default_factory=new_id)
    character_id:str
    shot_id:str
    order:int=Field(default=1,ge=1)
    text:str=Field(min_length=1,max_length=3000)
    delivery:str='calm'
    is_example:bool=True

class AudioTask(Record):
    id:str=Field(default_factory=new_id)
    created_at:str=Field(default_factory=lambda:datetime.now(timezone.utc).isoformat())
    kind:Literal['audio']='audio'
    audio_role:Literal['dialogue']='dialogue'
    dialogue:Dialogue
    character:Character
    shot:Shot
    voice:Voice
    text:str=Field(min_length=1,max_length=3000)
    delivery:str=Field(min_length=1)
    sample_rate:Literal[32000]=32000
    format:Literal['wav']='wav'
    speed:float=Field(default=1,ge=0.5,le=2,allow_inf_nan=False)
    retry_of:str|None=None
    @model_validator(mode='after')
    def relations(self):
        if self.dialogue.character_id!=self.character.id or self.shot.id!=self.dialogue.shot_id or self.shot.character_id!=self.character.id or self.voice.character_id!=self.character.id:raise ValueError('音频任务 Character / Shot / Voice 关联不匹配')
        return self

class AudioJob(Record):
    id:str=Field(default_factory=new_id)
    task_id:str
    dialogue_id:str
    status:Literal['pending','processing','completed','failed']='pending'
    history:list[str]=Field(default_factory=lambda:['pending'])
    task_sha256:str
    request_sha256:str
    result_id:str|None=None
    trace_id:str|None=None
    error:str=''
    simulation_only:Literal[True]=True

class AudioResult(Record):
    id:str
    task_id:str
    dialogue_id:str
    character_id:str
    shot_id:str
    voice_id:str
    path:str
    sha256:str
    metadata:dict
    simulation_only:Literal[True]=True

class AudioReview(Record):
    dialogue_id:str
    selected_result_id:str|None=None
    rejected:dict[str,str]=Field(default_factory=dict)

class AudioProduction:
    def __init__(self,store):self.store=store
    def read(self,kind,identifier,model):return model.model_validate_json(self.store.record_path(kind,identifier).read_text(encoding='utf-8'))
    def records(self,kind,model):return [model.model_validate_json(p.read_text(encoding='utf-8')) for p in sorted(self.store.path(kind).glob('*.json'))]
    def voices(self):return self.records('voices',Voice)
    def voice(self,identifier):return self.read('voices',identifier,Voice)
    def dialogues(self,shot_id=None):return sorted([d for d in self.records('dialogues',Dialogue) if shot_id is None or d.shot_id==shot_id],key=lambda d:(d.shot_id,d.order))
    def dialogue(self,identifier):return self.read('dialogues',identifier,Dialogue)
    def mapping(self,identifier):
        mapping=self.read('voice_mappings',identifier,VoiceMapping)
        if mapping.voice_id!=identifier:raise ValueError('Voice Provider Mapping 不匹配')
        return mapping
    def save_voice(self,voice,mapping):
        voice=Voice.model_validate(voice.model_dump());mapping=VoiceMapping.model_validate(mapping.model_dump())
        self.store.character(voice.character_id)
        if mapping.voice_id!=voice.id:raise ValueError('Voice Mapping 不匹配')
        old=self.store.record_path('voices',voice.id)
        if old.exists() and self.voice(voice.id).character_id!=voice.character_id:raise ValueError('已有 Voice 不可改属另一角色，请新建')
        for ref in voice.references:
            if digest(self.store.path(ref.path))!=ref.sha256:raise ValueError('Voice Reference 已改变')
        write_json(old,voice.model_dump());write_json(self.store.record_path('voice_mappings',voice.id),mapping.model_dump())
    def set_default(self,character_id,voice_id):
        self.store.character(character_id)
        if self.voice(voice_id).character_id!=character_id:raise ValueError('Voice 不属于此 Character')
        write_json(self.store.record_path('character_voices',character_id),dict(character_id=character_id,voice_id=voice_id))
    def default_voice(self,character_id):
        p=self.store.record_path('character_voices',character_id)
        if not p.exists():raise ValueError('请为角色设置默认 Voice')
        value=json.loads(p.read_text(encoding='utf-8'));voice=self.voice(value['voice_id'])
        if value.get('character_id')!=character_id or voice.character_id!=character_id:raise ValueError('默认 Voice 关系错误')
        return voice
    def import_reference(self,filename,is_example=True):
        source=Path(filename)
        if source.stat().st_size>20*1024*1024:raise ValueError('音频参考文件上限 20 MB')
        metadata=probe_audio(source)
        if source.suffix.lower() not in ('.wav','.mp3','.m4a','.flac'):raise ValueError('请选择 WAV / MP3 / M4A / FLAC')
        h=digest(source);relative='audio_assets/'+h+source.suffix.lower();destination=self.store.path(relative);destination.parent.mkdir(exist_ok=True)
        if not destination.exists():shutil.copyfile(source,destination)
        return AudioReference(name=source.name,path=relative,sha256=h,duration=metadata['duration'],is_example=is_example)
    def save_dialogue(self,dialogue):
        d=Dialogue.model_validate(dialogue.model_dump());self.store.character(d.character_id)
        shot=self.read('shots',d.shot_id,Shot)
        if shot.character_id!=d.character_id:raise ValueError('Dialogue 角色与 Shot 不匹配')
        if any(x.order==d.order and x.id!=d.id for x in self.dialogues(d.shot_id)):raise ValueError('同一 Shot 对白顺序不能重复')
        old=self.store.record_path('dialogues',d.id)
        if old.exists():
            previous=self.dialogue(d.id)
            if (previous.character_id,previous.shot_id)!=(d.character_id,d.shot_id):raise ValueError('已有 Dialogue 不可更换角色/Shot，请新建')
        write_json(old,d.model_dump())
    def folder(self,identifier):
        self.store.record_path('audio_tasks',identifier);return self.store.path('audio_tasks/'+identifier)
    def task(self,identifier):return AudioTask.model_validate_json((self.folder(identifier)/'task.json').read_text(encoding='utf-8'))
    def job(self,identifier):return self.read('audio_jobs',identifier,AudioJob)
    def jobs(self,dialogue_id=None):return sorted([j for j in self.records('audio_jobs',AudioJob) if dialogue_id is None or j.dialogue_id==dialogue_id],key=lambda j:self.task(j.task_id).created_at)
    def review(self,identifier):
        p=self.store.record_path('audio_reviews',identifier)
        return AudioReview.model_validate_json(p.read_text(encoding='utf-8')) if p.exists() else AudioReview(dialogue_id=identifier)
    def build(self,identifier,text=None,delivery=None,speed=1,retry_of=None):
        d=self.dialogue(identifier);voice=self.default_voice(d.character_id)
        for ref in voice.references:
            if digest(self.store.path(ref.path))!=ref.sha256:raise ValueError('Voice Reference 内容已变化')
        return AudioTask(dialogue=d,character=self.store.character(d.character_id),shot=self.read('shots',d.shot_id,Shot),voice=voice,text=text if text is not None else d.text,delivery=delivery or d.delivery or voice.default_delivery,speed=speed,retry_of=retry_of)
    def submit(self,identifier,text=None,delivery=None,speed=1,retry_of=None):
        from .tts_adapter import MiniMaxAdapter
        if retry_of:
            result,_=self.trace(retry_of)
            if result.dialogue_id!=identifier or retry_of not in self.review(identifier).rejected:raise ValueError('Retry 必须来自当前 Dialogue 已 Reject 的结果')
        if any(j.status in ('pending','processing') for j in self.jobs(identifier)):raise ValueError('当前对白已有进行中的生成')
        task=self.build(identifier,text,delivery,speed,retry_of);request=MiniMaxAdapter().prepare(task,self.mapping(task.voice.id))
        folder=self.folder(task.id);write_json(folder/'task.json',task.model_dump());write_json(folder/'provider_request.json',request)
        job=AudioJob(task_id=task.id,dialogue_id=identifier,task_sha256=digest(folder/'task.json'),request_sha256=digest(folder/'provider_request.json'))
        write_json(self.store.record_path('audio_jobs',job.id),job.model_dump());return job
    def poll(self,identifier):
        from .tts_adapter import MiniMaxAdapter,TTSFixtureTransport
        job=self.job(identifier)
        if job.status in ('completed','failed'):return job
        try:
            folder=self.folder(job.task_id)
            if digest(folder/'task.json')!=job.task_sha256 or digest(folder/'provider_request.json')!=job.request_sha256:raise ValueError('音频快照 / 请求被修改')
            if job.status=='pending':job.status='processing'
            else:
                request=json.loads((folder/'provider_request.json').read_text(encoding='utf-8'))
                code,response=TTSFixtureTransport().execute(request,job.id)
                response_summary=json.loads(json.dumps(response))
                if isinstance(response_summary,dict) and isinstance(response_summary.get('data'),dict) and 'audio' in response_summary['data']:
                    response_summary['data']['audio']='[hex audio stored as result WAV after validation]'
                write_json(folder/'provider_exchange.json',dict(http_status=code,response=response_summary,api_called=False))
                raw,trace_id=MiniMaxAdapter().parse(code,response)
                task=self.task(job.task_id);path=f'audio_results/{job.id}/fixture.wav';file=self.store.path(path);file.parent.mkdir(parents=True,exist_ok=True);file.write_bytes(raw)
                metadata=probe_audio(file)
                if metadata['sample_rate']!=str(task.sample_rate) or metadata['channels']!=1 or metadata['format_name']!='wav':raise ValueError('结果音频参数不匹配')
                result=AudioResult(id=job.id,task_id=task.id,dialogue_id=task.dialogue.id,character_id=task.character.id,shot_id=task.shot.id,voice_id=task.voice.id,path=path,sha256=digest(file),metadata=metadata)
                write_json(self.store.record_path('audio_results',result.id),result.model_dump());job.result_id=result.id;job.trace_id=trace_id;job.status='completed'
        except Exception as exc:job.status='failed';job.error=str(exc)
        job.history.append(job.status);write_json(self.store.record_path('audio_jobs',job.id),job.model_dump());return job
    def trace(self,identifier):
        result=self.read('audio_results',identifier,AudioResult);job=self.job(identifier);task=self.task(result.task_id);folder=self.folder(task.id)
        if (result.id!=identifier or job.status!='completed' or job.result_id!=result.id or job.task_id!=task.id or result.dialogue_id!=task.dialogue.id or result.shot_id!=task.shot.id or result.character_id!=task.character.id or result.voice_id!=task.voice.id):raise ValueError('Audio Result 关联不匹配')
        if digest(self.store.path(result.path))!=result.sha256 or digest(folder/'task.json')!=job.task_sha256 or digest(folder/'provider_request.json')!=job.request_sha256:raise ValueError('Audio / Task / Request 哈希不匹配')
        return result,task
    def select(self,identifier):
        result,task=self.trace(identifier);current=self.dialogue(result.dialogue_id)
        if (current.character_id,current.shot_id)!=(result.character_id,result.shot_id):raise ValueError('对白归属已改变')
        review=self.review(result.dialogue_id)
        if identifier in review.rejected:raise ValueError('Reject 结果不能 Select')
        review.selected_result_id=identifier;write_json(self.store.record_path('audio_reviews',review.dialogue_id),review.model_dump())
    def reject(self,identifier,reason=''):
        result,_=self.trace(identifier);review=self.review(result.dialogue_id)
        review.rejected[identifier]=reason
        if review.selected_result_id==identifier:review.selected_result_id=None
        write_json(self.store.record_path('audio_reviews',review.dialogue_id),review.model_dump())
    def play(self,identifier):
        result,_=self.trace(identifier)
        return subprocess.Popen([media_tool('ffplay'),'-autoexit','-loglevel','error','-showmode','waves','-window_title','A-07 FIXTURE Audio',str(self.store.path(result.path))],creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    def handoff(self,shot_id):
        items=[]
        for d in self.dialogues(shot_id):
            selected=self.review(d.id).selected_result_id;item=dict(dialogue_id=d.id,order=d.order,character_id=d.character_id,expected_dialogue=d.text,selected_audio_result=selected)
            if selected:
                result,task=self.trace(selected);item.update(audio_path=result.path,task_id=task.id,voice_id=task.voice.id,submitted_text=task.text,delivery=task.delivery)
                from .alignment import AlignmentProduction
                alignment=AlignmentProduction(self).get(selected)
                if alignment:item.update(alignment_id=alignment.id,subtitle_path=alignment.subtitle_path,fixture=alignment.fixture)
            items.append(item)
        return dict(shot_id=shot_id,dialogues=items)
