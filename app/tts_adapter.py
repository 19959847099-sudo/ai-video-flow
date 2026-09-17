"""MiniMax synchronous T2A contract. The only transport generates local tone fixtures."""
import io,math,struct,wave
MODEL='speech-2.6-hd'
ENDPOINT='https://api.minimax.io/v1/t2a_v2'
SYSTEM_VOICE='Chinese (Mandarin)_Warm_Girl'
DELIVERIES=('calm','angry','sad','happy','fearful','disgusted','surprised','whisper')

class MiniMaxAdapter:
    def prepare(self,task,mapping):
        if mapping.voice_id!=task.voice.id:raise ValueError('Provider Voice 与任务 Voice 不匹配')
        if task.delivery not in DELIVERIES:raise ValueError('当前 MiniMax 模型不支持此 Delivery：'+task.delivery)
        if task.voice.language!='zh':raise ValueError('当前适配只启用中文')
        if mapping.kind=='clone':raise ValueError('本轮不启用克隆 Voice；请使用系统声音映射')
        return dict(provider='minimax',model=MODEL,method='POST',url=ENDPOINT,headers={'Content-Type':'application/json'},
            auth_requirement='Bearer API key required for real API; omitted, never read in fixture mode',simulation_only=True,
            body=dict(model=MODEL,text=task.text,stream=False,output_format='hex',language_boost='Chinese',
                voice_setting=dict(voice_id=mapping.provider_voice_id,speed=task.speed,vol=1,pitch=0,emotion=task.delivery),
                audio_setting=dict(sample_rate=task.sample_rate,format=task.format,channel=1)),
            voice_mapping=mapping.model_dump(),reference_policy='Reference audio retained as identity evidence; system-voice TTS does not accept reference audio. No upload or cloning.',
            voice_reference_ids=[r.id for r in task.voice.references])
    def parse(self,http_status,body):
        if not isinstance(body,dict):raise ValueError('MiniMax 响应必须是 JSON 对象')
        if not 200<=http_status<300 or body.get('base_resp',{}).get('status_code')!=0:raise ValueError('MiniMax 调用失败：'+str(body.get('base_resp',http_status)))
        data=body.get('data',{})
        if data.get('status')!=2 or not body.get('trace_id'):raise ValueError('同步音频响应不完整')
        try:raw=bytes.fromhex(data['audio'])
        except (ValueError,KeyError,TypeError) as exc:raise ValueError('MiniMax audio 不是有效 hex') from exc
        if len(raw)>20*1024*1024:raise ValueError('音频结果超过本轮 20 MB 上限')
        try:
            with wave.open(io.BytesIO(raw),'rb') as w:
                if w.getnframes()==0 or w.getcomptype()!='NONE':raise ValueError('无有效 PCM 音频')
        except (wave.Error,EOFError) as exc:raise ValueError('响应不是可读取 WAV') from exc
        return raw,str(body['trace_id'])

class TTSFixtureTransport:
    def execute(self,request,identifier):
        if request.get('method')!='POST' or request.get('url')!=ENDPOINT or not request.get('simulation_only'):raise ValueError('仅允许 MiniMax 本地 Fixture')
        body=request['body']
        if body.get('model')!=MODEL or body.get('stream') is not False or body.get('output_format')!='hex' or body.get('audio_setting',{}).get('format')!='wav':raise ValueError('Fixture 请求不匹配')
        rate=body['audio_setting']['sample_rate'];duration=4;freq=330+int(identifier[:4],16)%150
        # Audible but quiet tones separated by silence; no claim of generated speech.
        samples=bytearray()
        for i in range(rate*duration):
            t=i/rate;envelope=0.0 if (1.7<t<2.1 or t<0.1 or t>3.7) else 0.12
            samples.extend(struct.pack('<h',int(32767*envelope*math.sin(2*math.pi*freq*t))))
        stream=io.BytesIO()
        with wave.open(stream,'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(rate);w.writeframes(samples)
        raw=stream.getvalue()
        return 200,dict(data=dict(audio=raw.hex(),status=2),extra_info=dict(audio_length=4000,audio_sample_rate=rate,audio_size=len(raw),audio_format='wav',audio_channel=1),trace_id=identifier,base_resp=dict(status_code=0,status_msg='success'))
