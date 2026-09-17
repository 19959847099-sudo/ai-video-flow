"""WhisperX output contract + explicit fixture alignment; never loads a model."""
import json
from typing import Literal
from pydantic import Field,model_validator
from .core import Record,write_json
from .audio_production import digest

class WordTiming(Record):
    word:str
    start:float|None=Field(default=None,ge=0,allow_inf_nan=False)
    end:float|None=Field(default=None,ge=0,allow_inf_nan=False)
    score:float|None=Field(default=None,ge=0,le=1,allow_inf_nan=False)
    @model_validator(mode='after')
    def timing(self):
        if (self.start is None)!=(self.end is None) or (self.start is not None and self.end<self.start):raise ValueError('词时间无效')
        return self
class Segment(Record):
    start:float=Field(ge=0,allow_inf_nan=False)
    end:float=Field(ge=0,allow_inf_nan=False)
    text:str=Field(min_length=1)
    words:list[WordTiming]=Field(default_factory=list)
    @model_validator(mode='after')
    def timing(self):
        if self.end<=self.start:raise ValueError('Segment 时间无效')
        previous=self.start
        for word in self.words:
            if word.start is not None:
                if word.start<previous or word.end>self.end+0.001:raise ValueError('词时间超出 Segment 或乱序')
                previous=word.end
        return self
class AlignmentResult(Record):
    id:str
    audio_result_id:str
    task_id:str
    dialogue_id:str
    shot_id:str
    audio_sha256:str
    expected_text:str
    transcript:str
    segments:list[Segment]
    engine:Literal['whisperx-contract']='whisperx-contract'
    fixture:Literal[True]=True
    subtitle_path:str
    subtitle_sha256:str

class WhisperXAdapter:
    def request(self,result):
        return dict(operation='transcribe_then_align',audio_path=result.path,audio_sha256=result.sha256,language='zh',
            execution='external-worker-contract',model_configuration='remote-worker-owned; not installed locally',
            output_contract='WhisperX AlignedTranscriptionResult: segments, word_segments')
    def parse(self,body,duration):
        if not isinstance(body,dict) or not isinstance(body.get('segments'),list) or not body['segments']:raise ValueError('WhisperX 输出缺少 segments')
        segments=[];previous=0.0
        for raw in body['segments']:
            segment=Segment.model_validate({k:raw[k] for k in ('start','end','text','words') if k in raw})
            if segment.start<previous or segment.end>duration+0.001:raise ValueError('Segment 乱序或超出音频时长')
            previous=segment.end;segments.append(segment)
        return segments

class AlignmentFixture:
    def execute(self,request):
        if request.get('operation')!='transcribe_then_align':raise ValueError('未知 Alignment 操作')
        # Independently defined transcript, deliberately not copied from Expected Dialogue.
        segments=[]
        for start,end,text in [(0.1,1.7,'这是音频测试。'),(2.1,3.7,'等待人工确认。')]:
            words=[dict(word=char,start=round(start+(end-start)*i/len(text),4),end=round(start+(end-start)*(i+1)/len(text),4)) for i,char in enumerate(text)]
            segments.append(dict(start=start,end=end,text=text,words=words))
        return dict(segments=segments,word_segments=[w for s in segments for w in s['words']])

def timestamp(seconds):
    value=round(seconds*1000);hours,value=divmod(value,3600000);minutes,value=divmod(value,60000);seconds,millis=divmod(value,1000)
    return f'{hours:02}:{minutes:02}:{seconds:02},{millis:03}'

def srt_text(segments):
    return '\n\n'.join(f'{i}\n{timestamp(s.start)} --> {timestamp(s.end)}\n[FIXTURE] {s.text}' for i,s in enumerate(segments,1))+'\n'

class AlignmentProduction:
    def __init__(self,audio):self.audio=audio;self.store=audio.store
    def get(self,identifier):
        path=self.store.record_path('alignments',identifier)
        if not path.exists():return None
        alignment=AlignmentResult.model_validate_json(path.read_text(encoding='utf-8'));result,task=self.audio.trace(identifier)
        if (alignment.id!=identifier or alignment.audio_result_id!=result.id or alignment.task_id!=task.id or alignment.dialogue_id!=result.dialogue_id or alignment.shot_id!=result.shot_id or alignment.audio_sha256!=result.sha256):raise ValueError('Alignment 来源关系不匹配')
        WhisperXAdapter().parse(dict(segments=[s.model_dump() for s in alignment.segments]),result.metadata['duration'])
        if alignment.transcript!=''.join(s.text for s in alignment.segments) or alignment.expected_text!=task.text:raise ValueError('Transcript / Expected Text 不匹配')
        if digest(self.store.path(alignment.subtitle_path))!=alignment.subtitle_sha256:raise ValueError('Subtitle 文件已改变')
        return alignment
    def run(self,identifier):
        existing=self.get(identifier)
        if existing:return existing
        result,task=self.audio.trace(identifier);adapter=WhisperXAdapter();request=adapter.request(result);body=AlignmentFixture().execute(request)
        segments=adapter.parse(body,result.metadata['duration'])
        relative=f'subtitles/{identifier}.srt';file=self.store.path(relative);file.parent.mkdir(exist_ok=True);file.write_text(srt_text(segments),encoding='utf-8')
        alignment=AlignmentResult(id=identifier,audio_result_id=identifier,task_id=task.id,dialogue_id=result.dialogue_id,shot_id=result.shot_id,audio_sha256=result.sha256,expected_text=task.text,transcript=''.join(s.text for s in segments),segments=segments,subtitle_path=relative,subtitle_sha256=digest(file))
        write_json(self.store.record_path('alignments',identifier),alignment.model_dump())
        write_json(self.store.record_path('alignment_exchanges',identifier),dict(request=request,response=body,fixture=True,model_executed=False))
        return alignment
    def regenerate_subtitle(self,identifier):
        # Explicit repair/export from persisted alignment, without rerunning recognition.
        alignment=self.audio.read('alignments',identifier,AlignmentResult);result,task=self.audio.trace(identifier)
        if alignment.audio_result_id!=identifier or alignment.task_id!=task.id:raise ValueError('字幕来源不匹配')
        segments=WhisperXAdapter().parse(dict(segments=[s.model_dump() for s in alignment.segments]),result.metadata['duration'])
        file=self.store.path(alignment.subtitle_path);file.parent.mkdir(exist_ok=True);file.write_text(srt_text(segments),encoding='utf-8');alignment.subtitle_sha256=digest(file)
        write_json(self.store.record_path('alignments',identifier),alignment.model_dump());return alignment
