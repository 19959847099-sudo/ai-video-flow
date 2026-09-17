"""Minimal Voice / Dialogue / Audio Review UI using the existing workstation widgets."""
import json,os
from tkinter import ttk,filedialog
from .audio_production import AudioProduction,Voice,VoiceMapping,Dialogue
from .alignment import AlignmentProduction
from .tts_adapter import SYSTEM_VOICE,DELIVERIES
from .ui_components import ActionBar,Advanced,StatusBadge
from .ui_widgets import Rows,text_field,readonly_text,put_text,ScrollArea

class AudioPanel(ttk.Frame):
    def __init__(self,parent,host):
        super().__init__(parent,padding=12);self.host=host;self.production=AudioProduction(host.store);self.alignments=AlignmentProduction(self.production)
        self.voice=None;self.dialogue=None;self.current=None;self.voice_items=[];self.dialogue_items=[];self.job_items=[]
        ttk.Label(self,text='声音资产 / 对白生产 / 音频选片',style='Heading.TLabel').pack(anchor='w',pady=(0,8))
        self.tabs=ttk.Notebook(self);self.tabs.pack(fill='both',expand=True)
        self.voice_tab=ttk.Frame(self.tabs,padding=10);self.dialogue_tab=ttk.Frame(self.tabs,padding=10);self.review_tab=ttk.Frame(self.tabs,padding=10)
        for page,title in [(self.voice_tab,'声音 Voice'),(self.dialogue_tab,'对白 Dialogue'),(self.review_tab,'音频审核 / 字幕')]:self.tabs.add(page,text=title)
        self.characters=[];self.shots=[]
        self.voice_ui();self.dialogue_ui();self.review_ui();self.after(650,self.tick)
    def split(self,parent):
        left=ttk.Frame(parent,width=205);left.pack(side='left',fill='y',padx=(0,16));left.pack_propagate(False)
        right=ttk.Frame(parent);right.pack(side='left',fill='both',expand=True);return left,right
    def combo(self,parent,title,values=()):
        ttk.Label(parent,text=title).pack(anchor='w');w=ttk.Combobox(parent,state='readonly',values=values);w.pack(fill='x',pady=(0,8));return w
    def voice_ui(self):
        left,right=self.split(self.voice_tab);self.voice_list=Rows(left,width=185);self.voice_list.pack(fill='both',expand=True);self.voice_list.bind('<<ListboxSelect>>',lambda e:self.host.guard(self.choose_voice))
        self.host.button(left,'新建 Voice',self.new_voice)
        buttons=ActionBar(right);buttons.pack(side='bottom',fill='x')
        self.host.button(buttons,'保存 Voice',self.save_voice);self.host.button(buttons,'设为角色默认 Voice',self.set_default);self.host.button(buttons,'导入参考音频…',self.import_reference)
        area=ScrollArea(right);area.pack(fill='both',expand=True);body=area.body
        self.voice_character=self.combo(body,'关联 Character');self.voice_name=self.host.field(body,'声音名称 *');self.voice_description=text_field(body,'稳定声音描述 *',3)
        self.voice_delivery=self.combo(body,'默认 Delivery',DELIVERIES);self.voice_delivery.set('calm')
        self.mapping_status=ttk.Label(body,text='Provider 映射：MiniMax 系统声音 · ZERO-CALL',style='Muted.TLabel');self.mapping_status.pack(anchor='w',pady=8)
        self.voice_advanced=Advanced(body,'Advanced · Provider Mapping');self.voice_advanced.pack(fill='x')
        self.provider_voice=self.host.field(self.voice_advanced.body,'MiniMax 系统 Voice ID');self.provider_voice.set(SYSTEM_VOICE)
        self.voice_notes=text_field(body,'备注',2);self.voice_references=ttk.Label(body,text='参考音频：无',wraplength=740);self.voice_references.pack(fill='x',pady=12)
        ttk.Label(body,text='系统声音模式不会上传参考音频或执行克隆；导入文件仅保存为身份参考。',style='Muted.TLabel').pack(anchor='w')
    def dialogue_ui(self):
        left,right=self.split(self.dialogue_tab);self.dialogue_list=Rows(left,width=185);self.dialogue_list.pack(fill='both',expand=True);self.dialogue_list.bind('<<ListboxSelect>>',lambda e:self.host.guard(self.choose_dialogue));self.host.button(left,'新建 Dialogue',self.new_dialogue)
        buttons=ActionBar(right);buttons.pack(side='bottom',fill='x')
        self.host.button(buttons,'保存 Dialogue',self.save_dialogue);self.host.button(buttons,'生成音频 · ZERO-CALL',self.generate);self.host.button(buttons,'查看音频候选',self.open_review)
        area=ScrollArea(right);area.pack(fill='both',expand=True);right=area.body
        self.dialogue_shot=self.combo(right,'关联 Shot');self.dialogue_shot.bind('<<ComboboxSelected>>',lambda e:self.update_speaker())
        self.speaker=ttk.Label(right,text='选择 Shot 后显示角色与默认声音');self.speaker.pack(anchor='w',pady=8)
        self.dialogue_order=self.host.field(right,'对白顺序（同一 Shot 内唯一）');self.dialogue_order.set('1')
        self.dialogue_text=text_field(right,'预期对白文本 *',6);self.dialogue_delivery=self.combo(right,'Delivery',DELIVERIES);self.dialogue_delivery.set('calm')
        self.handoff_summary=ttk.Label(right,text='保存对白后可生成音频候选',style='Muted.TLabel',wraplength=500);self.handoff_summary.pack(fill='x',pady=10)
        self.handoff_advanced=Advanced(right,'Advanced · Shot Audio Handoff');self.handoff_advanced.pack(fill='x');self.handoff=readonly_text(self.handoff_advanced.body,height=5)
    def review_ui(self):
        left,right=self.split(self.review_tab);self.result_list=Rows(left,width=185);self.result_list.pack(fill='both',expand=True);self.result_list.bind('<<ListboxSelect>>',lambda e:self.host.guard(self.choose_result))
        actions=ActionBar(right);actions.pack(side='bottom',fill='x')
        self.play_button=self.host.button(actions,'试听实际 WAV',self.play);self.select_button=self.host.button(actions,'Select Audio',self.select);self.reject_button=self.host.button(actions,'Reject Audio',self.reject);self.retry_button=self.host.button(actions,'Retry Audio',self.retry);self.align_button=self.host.button(actions,'对齐 + SRT · Fixture',self.align)
        self.review_scroll=ScrollArea(right);self.review_scroll.pack(fill='both',expand=True);right=self.review_scroll.body
        self.result_title=ttk.Label(right,text='选择音频候选',style='Heading.TLabel');self.result_title.pack(anchor='w')
        ttk.Label(right,text='音频为低音量测试音调；转写与时间均为 Fixture，未运行 WhisperX 模型。',style='Muted.TLabel').pack(anchor='w',pady=5)
        self.audio_badge=StatusBadge(right,text='Candidate');self.audio_badge.pack(anchor='w',pady=6)
        self.retry_settings=Advanced(right,'Retry 设置 / 拒绝原因');self.retry_settings.pack(fill='x',pady=6)
        retry_body=self.retry_settings.body
        self.retry_text=text_field(retry_body,'当次请求文本 / Retry 文本',3);self.retry_delivery=self.combo(retry_body,'当次 Delivery / Retry Delivery',DELIVERIES)
        self.retry_speed=self.host.field(retry_body,'语速（0.5～2；仅影响请求参数，Fixture 不模拟声学质量）');self.retry_speed.set('1')
        self.reason=text_field(retry_body,'Reject 原因（可选）',1)
        notebook=ttk.Notebook(right);notebook.pack(fill='both',expand=True,pady=8)
        context=ttk.Frame(notebook);timing=ttk.Frame(notebook);details=ttk.Frame(notebook)
        notebook.add(context,text='声音与任务');notebook.add(timing,text='转写 / Timing / SRT');notebook.add(details,text='Advanced');self.review_details_tabs=notebook
        self.context=readonly_text(context,height=8);self.timing=readonly_text(timing,height=8);self.details=readonly_text(details,height=8)
    def refresh(self):
        self.characters=self.host.store.characters();self.shots=self.host.store.shots()
        self.voice_character['values']=[c.name for c in self.characters];self.dialogue_shot['values']=[s.description for s in self.shots]
        self.voice_items=self.production.voices();self.voice_list.delete(0,'end')
        for voice in self.voice_items:
            try:default=self.production.default_voice(voice.character_id).id==voice.id
            except ValueError:default=False
            self.voice_list.insert('end',voice.name+'\n'+('默认 Voice' if default else 'Voice')+' · '+voice.default_delivery)
        self.dialogue_items=self.production.dialogues();self.dialogue_list.delete(0,'end')
        for d in self.dialogue_items:self.dialogue_list.insert('end',f'{d.order}. {d.text[:26]}\n{d.delivery} · 对白')
        self.refresh_results()
    def new_voice(self):
        self.voice=None;self.voice_name.set('');self.voice_description.set('');self.voice_notes.set('');self.provider_voice.set(SYSTEM_VOICE);self.voice_delivery.set('calm');self.voice_references.configure(text='参考音频：无')
        if self.characters:self.voice_character.current(0)
    def choose_voice(self):
        selection=self.voice_list.curselection()
        if not selection:return
        self.voice=self.production.voice(self.voice_items[selection[0]].id);v=self.voice
        self.voice_character.current(next(i for i,c in enumerate(self.characters) if c.id==v.character_id));self.voice_name.set(v.name);self.voice_description.set(v.description);self.voice_notes.set(v.notes);self.voice_delivery.set(v.default_delivery);self.provider_voice.set(self.production.mapping(v.id).provider_voice_id)
        self.voice_references.configure(text='参考音频：'+(', '.join(r.name for r in v.references) or '无'))
    def save_voice(self):
        if self.voice_character.current()<0:raise ValueError('请选择 Character')
        data=self.voice.model_dump() if self.voice else {};data.update(name=self.voice_name.get(),character_id=self.characters[self.voice_character.current()].id,description=self.voice_description.get(),default_delivery=self.voice_delivery.get(),notes=self.voice_notes.get())
        voice=Voice(**data);self.production.save_voice(voice,VoiceMapping(voice_id=voice.id,provider_voice_id=self.provider_voice.get()));self.voice=voice;self.refresh();self.host.status.set('Voice 与外围 Provider 映射已保存')
    def set_default(self):
        self.save_voice();self.production.set_default(self.voice.character_id,self.voice.id);self.refresh();self.host.status.set('角色默认 Voice 已明确关联')
    def import_reference(self):
        if not self.voice:raise ValueError('请先保存 Voice')
        filename=filedialog.askopenfilename(parent=self,title='导入参考音频',filetypes=[('音频','*.wav *.mp3 *.m4a *.flac')])
        if not filename:return
        ref=self.production.import_reference(filename)
        if not any(r.sha256==ref.sha256 for r in self.voice.references):self.voice.references.append(ref)
        self.save_voice();self.voice_references.configure(text='参考音频：'+', '.join(r.name for r in self.voice.references))
    def new_dialogue(self):
        self.dialogue=None;self.dialogue_text.set('');self.dialogue_delivery.set('calm')
        if self.shots and self.dialogue_shot.current()<0:self.dialogue_shot.current(0)
        if self.dialogue_shot.current()>=0:self.dialogue_order.set(str(max((d.order for d in self.production.dialogues(self.shots[self.dialogue_shot.current()].id)),default=0)+1));self.update_speaker()
    def update_speaker(self):
        if self.dialogue_shot.current()<0:return
        shot=self.shots[self.dialogue_shot.current()];char=self.host.store.character(shot.character_id)
        try:voice=self.production.default_voice(char.id).name
        except ValueError:voice='尚未设置默认声音'
        self.speaker.configure(text=char.name+' / '+voice)
        handoff=self.production.handoff(shot.id);items=handoff['dialogues']
        self.handoff_summary.configure(text=f'{len(items)} 句对白 · '+str(sum(bool(x['selected_audio_result']) for x in items))+' 条 Selected Audio；完整关联见 Advanced。')
        put_text(self.handoff,json.dumps(handoff,ensure_ascii=False,indent=2))
    def choose_dialogue(self):
        selected=self.dialogue_list.curselection()
        if not selected:return
        self.dialogue=self.production.dialogue(self.dialogue_items[selected[0]].id);d=self.dialogue
        self.dialogue_shot.current(next(i for i,s in enumerate(self.shots) if s.id==d.shot_id));self.dialogue_order.set(str(d.order));self.dialogue_text.set(d.text);self.dialogue_delivery.set(d.delivery);self.update_speaker()
    def save_dialogue(self):
        if self.dialogue_shot.current()<0:raise ValueError('请选择 Shot')
        shot=self.shots[self.dialogue_shot.current()];data=self.dialogue.model_dump() if self.dialogue else {}
        data.update(character_id=shot.character_id,shot_id=shot.id,order=int(self.dialogue_order.get()),text=self.dialogue_text.get(),delivery=self.dialogue_delivery.get());d=Dialogue(**data);self.production.save_dialogue(d);self.dialogue=d;self.refresh();self.update_speaker();self.host.status.set('Dialogue 已保存')
    def generate(self):
        self.save_dialogue();self.current=self.production.submit(self.dialogue.id);self.refresh_results(self.current.id);self.tabs.select(self.review_tab);self.show_result()
    def open_review(self):self.refresh_results();self.tabs.select(self.review_tab)
    def refresh_results(self,selected=None):
        selected=selected or (self.current.id if self.current else None);self.job_items=self.production.jobs();self.result_list.delete(0,'end')
        for i,j in enumerate(self.job_items):
            task=self.production.task(j.task_id);review=self.production.review(j.dialogue_id);status='SELECTED' if review.selected_result_id==j.id else ('REJECTED' if j.id in review.rejected else ('CANDIDATE' if j.status=='completed' else j.status.upper()))
            self.result_list.insert('end',task.text[:24]+'\n'+status+' · FIXTURE')
            if j.id==selected:self.current=j;self.result_list.selection_set(i)
        self.buttons()
    def choose_result(self):
        selection=self.result_list.curselection()
        if selection:self.current=self.job_items[selection[0]];self.show_result()
    def buttons(self):
        ready=self.current and self.current.status=='completed';review=self.production.review(self.current.dialogue_id) if self.current else None
        rejected=ready and self.current.id in review.rejected
        for button,enabled in [(self.play_button,ready),(self.select_button,ready and not rejected),(self.reject_button,ready and not rejected),(self.retry_button,rejected),(self.align_button,ready)]:button.configure(state='normal' if enabled else 'disabled')
    def show_result(self):
        if not self.current:return
        job=self.production.job(self.current.id);self.current=job;task=self.production.task(job.task_id);review=self.production.review(job.dialogue_id)
        state='selected' if review.selected_result_id==job.id else ('rejected' if job.id in review.rejected else ('candidate' if job.status=='completed' else ('blocked' if job.status=='failed' else 'pending')))
        self.audio_badge.set(state.upper(),state)
        self.result_title.configure(text=task.voice.name+' / '+task.delivery)
        self.retry_text.set(task.text);self.retry_delivery.set(task.delivery);self.retry_speed.set(str(task.speed));self.reason.set(review.rejected.get(job.id,''))
        put_text(self.context,f'Voice: {task.voice.name}\nCharacter: {task.character.name}\nShot: {task.shot.description}\n预期对白: {task.dialogue.text}\n当次提交文本: {task.text}\nDelivery: {task.delivery}\n'+job.error)
        request=json.loads((self.production.folder(task.id)/'provider_request.json').read_text(encoding='utf-8'));put_text(self.details,'Audio Task: '+task.id+'\nResult: '+str(job.result_id)+'\n'+json.dumps(request,ensure_ascii=False,indent=2))
        put_text(self.timing,'尚未生成 Alignment / SRT。点“对齐 + SRT · Fixture”。')
        if job.result_id:
            result,_=self.production.trace(job.result_id);alignment=self.alignments.get(result.id)
            if alignment:put_text(self.timing,'FIXTURE · 未运行 WhisperX 模型\nExpected: '+alignment.expected_text+'\n模拟 Actual Transcript: '+alignment.transcript+'\n\n'+self.host.store.path(alignment.subtitle_path).read_text(encoding='utf-8')+'\nWord timing:\n'+json.dumps([s.model_dump() for s in alignment.segments],ensure_ascii=False,indent=2))
        self.buttons()
    def play(self):self.host.players.append(self.production.play(self.current.id));self.host.status.set('正在播放实际 Fixture WAV（测试音调，不是真实配音）')
    def select(self):self.production.select(self.current.id);self.refresh_results();self.show_result();self.host.status.set('Selected Audio 已保存；字幕仍需人工检查')
    def reject(self):
        self.production.reject(self.current.id,self.reason.get());self.refresh_results();self.show_result()
        if not self.retry_settings.opened:self.retry_settings.flip()
    def retry(self):
        self.current=self.production.submit(self.current.dialogue_id,text=self.retry_text.get(),delivery=self.retry_delivery.get(),speed=float(self.retry_speed.get()),retry_of=self.current.id);self.refresh_results(self.current.id);self.show_result()
    def align(self):self.alignments.run(self.current.id);self.show_result();self.review_details_tabs.select(1);self.host.status.set('Alignment Fixture 与 SRT 已落盘，未执行语音模型')
    def open_character(self,character_id):
        self.refresh();self.new_voice();self.voice_character.current(next(i for i,c in enumerate(self.characters) if c.id==character_id))
        for i,v in enumerate(self.voice_items):
            if v.character_id==character_id:self.voice_list.selection_set(i);self.choose_voice();break
        self.tabs.select(self.voice_tab)
    def open_shot(self,shot_id):
        self.refresh();self.dialogue_shot.current(next(i for i,s in enumerate(self.shots) if s.id==shot_id));self.new_dialogue();self.tabs.select(self.dialogue_tab)
    def tick(self):
        if self.host.closing:return
        try:
            pending=[j for j in self.production.jobs() if j.status in ('pending','processing')]
            if pending:
                job=self.production.poll(pending[0].id);self.refresh_results()
                if self.current and self.current.id==job.id:self.show_result()
        except Exception as exc:self.host.status.set('音频处理失败：'+str(exc))
        self.after(650,self.tick)
