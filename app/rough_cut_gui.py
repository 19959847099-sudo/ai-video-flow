"""Explicit ordered-shot handoff, not a timeline editor."""
import json,tkinter as tk
from tkinter import ttk
from .rough_cut import RoughCutProduction,TimelineDefinition
from .ui_widgets import Rows,readonly_text,put_text
from .ui_components import ActionBar,Advanced,StatusBadge

class RoughCutPanel(ttk.Frame):
    def __init__(self,parent,host):
        super().__init__(parent,padding=12);self.host=host;self.production=RoughCutProduction(host.store);self.current=None;self.order=[];self.items=[];self.shots=[]
        self.busy=False;self.report_serial=0
        self.badge=StatusBadge(self,text='DRAFT · 添加镜头并保存');self.badge.pack(anchor='w')
        ttk.Label(self,text='粗剪交接 · FIXTURE 素材 · 非最终成片',style='Heading.TLabel').pack(anchor='w',pady=(6,0))
        top=ttk.Frame(self);top.pack(fill='x',pady=8)
        self.saved=ttk.Combobox(top,state='readonly');self.saved.pack(side='left',fill='x',expand=True);self.saved.bind('<<ComboboxSelected>>',lambda e:host.guard(self.open))
        host.button(top,'新建 Timeline',self.new);host.button(top,'刷新 Timeline',self.refresh)
        self.settings=Advanced(self,'Timeline 名称 / 允许策略');self.settings.pack(fill='x',pady=4)
        self.name=host.field(self.settings.body,'Timeline 名称 *')
        policy=ttk.Frame(self.settings.body);policy.pack(fill='x',pady=8)
        self.allow_audio=tk.BooleanVar(value=False);self.allow_subtitles=tk.BooleanVar(value=False)
        ttk.Checkbutton(policy,text='允许缺失对白 / 无音频 Shot（静音）',variable=self.allow_audio).pack(side='left')
        ttk.Checkbutton(policy,text='允许当前音频没有字幕',variable=self.allow_subtitles).pack(side='left')
        ttk.Label(self.settings.body,text='策略：视频时长驱动；对白依序排列并截短超出部分；视频原音静音；字幕单独 SRT。',style='Muted.TLabel').pack(anchor='w')
        bottom=ActionBar(self);bottom.pack(side='bottom',fill='x',pady=8)
        for label,method in [('保存顺序',self.save),('Validate',self.validate),('Build Timeline',self.build),('Generate Preview',self.preview),('Open Preview',self.play),('Export Handoff',self.export)]:host.button(bottom,label,method)
        content=ttk.Panedwindow(self,orient='horizontal');content.pack(fill='both',expand=True,pady=8)
        left=ttk.Frame(content);right=ttk.Frame(content);content.add(left,weight=1);content.add(right,weight=2)
        add_row=ttk.Frame(left);add_row.pack(fill='x')
        self.available=ttk.Combobox(add_row,state='readonly');self.available.pack(side='left',fill='x',expand=True);host.button(add_row,'添加 Shot',self.add)
        controls=ActionBar(left);controls.pack(fill='x')
        host.button(controls,'Move Up',lambda:self.move(-1));host.button(controls,'Move Down',lambda:self.move(1));host.button(controls,'移出顺序',self.remove)
        self.order_list=Rows(left,width=240);self.order_list.pack(fill='both',expand=True)
        self.info_tabs=ttk.Notebook(right);self.info_tabs.pack(fill='both',expand=True)
        summary=ttk.Frame(self.info_tabs);technical=ttk.Frame(self.info_tabs)
        self.info_tabs.add(summary,text='生产检查');self.info_tabs.add(technical,text='Advanced')
        self.details=readonly_text(summary,height=12);self.technical=readonly_text(technical,height=12)
        put_text(self.details,'选择一个已保存的 Timeline，或新建顺序。\n\n仅使用人工 Selected 素材；缺失视频会阻止构建。')
    def refresh(self):
        self.items=self.production.definitions();self.shots=self.host.store.shots();self.saved['values']=[x.name for x in self.items];self.available['values']=[s.description for s in self.shots]
        if self.shots:self.available.current(0)
    def new(self):
        self.refresh();self.current=None;self.report_serial+=1;self.order=[];self.name.set('');self.settings.flip() if not self.settings.opened else None;self.allow_audio.set(False);self.allow_subtitles.set(False);self.render();self.badge.set('DRAFT · 尚未保存');put_text(self.details,'Draft：添加 Shot，明确允许策略，再保存。');put_text(self.technical,'')
    def open(self):
        if self.saved.current()<0:return
        self.current=self.production.definition(self.items[self.saved.current()].id);d=self.current;self.order=list(d.shot_ids);self.name.set(d.name);self.allow_audio.set(d.allow_missing_audio);self.allow_subtitles.set(d.allow_missing_subtitles);self.render();self.report()
    def render(self,selection=None):
        self.report_serial+=1;self.badge.set('DRAFT · 顺序更改后请保存并检查','pending')
        self.order_list.delete(0,'end')
        for i,sid in enumerate(self.order):
            s=next(s for s in self.shots if s.id==sid);selected=self.production.video.review(sid).selected_result_id
            self.order_list.insert('end',f'{i+1}. {s.description}\nVideo '+('SELECTED' if selected else 'MISSING · 请先选片'))
        if selection is not None:self.order_list.selection_set(selection)
    def add(self):
        if self.available.current()<0:raise ValueError('请选择 Shot')
        sid=self.shots[self.available.current()].id
        if sid in self.order:raise ValueError('Shot 已在顺序中')
        self.order.append(sid);self.render(len(self.order)-1)
    def move(self,delta):
        selected=self.order_list.curselection()
        if not selected:return
        i=selected[0];j=i+delta
        if 0<=j<len(self.order):self.order[i],self.order[j]=self.order[j],self.order[i];self.render(j)
    def remove(self):
        selected=self.order_list.curselection()
        if selected:self.order.pop(selected[0]);self.render()
    def save(self):
        if self.busy:raise ValueError('媒体操作进行中，请完成后再保存顺序')
        d=dict(name=self.name.get(),shot_ids=self.order,allow_missing_audio=self.allow_audio.get(),allow_missing_subtitles=self.allow_subtitles.get())
        if self.current:d['id']=self.current.id
        self.current=self.production.save(TimelineDefinition(**d));self.report_serial+=1;self.badge.set('SAVED · 请检查当前生产状态','pending');self.refresh();self.host.status.set('Timeline 顺序与允许策略已保存');return self.current
    def report(self):
        identifier=self.current.id;self.report_serial+=1;serial=self.report_serial
        self.badge.set('CHECKING · 正在读取媒体','pending')
        def inspect():
            m=self.production.resolve(identifier);artifact={}
            try:
                folder,_=self.production.current(identifier)
                artifact=dict(build=str(folder),preview=(folder/'preview.json').exists(),handoff=(folder/'handoff.json').exists())
                if artifact['handoff']:artifact['handoff_path']=str(self.host.store.path(json.loads((folder/'handoff.json').read_text(encoding='utf-8'))['path']))
            except ValueError as exc:artifact['notice']=str(exc)
            return m,artifact
        future=self.host.worker.submit(inspect)
        def finish():
            if self.host.closing or serial!=self.report_serial:return
            if not future.done():self.after(100,finish);return
            try:
                m,artifact=future.result();notice=artifact.get('notice','');state='blocked' if m['errors'] else ('stale' if 'STALE' in notice else 'ready')
                self.badge.set(state.upper()+f' · {len(m["clips"])} 镜头 · {m["duration"]:.2f}s',state)
                lines=[f'{m["rate"]} fps · {m["duration"]:.2f}s · 视频时长驱动']
                for c in m['clips']:lines.append(f'\n{c["name"]}\nSELECTED VIDEO · {c["metadata"]["duration"]:.2f}s · 对白 {len(c["audios"])} 段 · 字幕 {len(c["subtitles"])} 段')
                names={s.id[:8]:s.description for s in self.shots}
                names.update({d.id[:8]:'对白 '+str(d.order) for d in self.production.audio.dialogues()})
                def readable(message):
                    prefix,sep,rest=message.partition(':')
                    return names.get(prefix,prefix)+sep+rest
                lines+=['\nBLOCKED: '+readable(x) for x in m['errors']]+['\nWARNING: '+readable(x) for x in m['warnings']]
                lines+=['\n'+notice] if notice else ['\nTimeline 已构建','Preview '+('READY' if artifact['preview'] else '待生成'),'Handoff '+('READY' if artifact['handoff'] else '待导出')]
                put_text(self.details,'\n'.join(lines));put_text(self.technical,json.dumps(dict(manifest=m,artifacts=artifact),ensure_ascii=False,indent=2))
            except Exception as exc:self.badge.set('BLOCKED · 检查失败','blocked');put_text(self.details,str(exc))
        self.after(100,finish)
    def run_operation(self,label,operation):
        if self.busy:raise ValueError('当前媒体操作尚未完成，请稍候')
        self.busy=True;self.report_serial+=1;identifier=self.current.id
        self.badge.set(label+' · PROCESSING','pending');self.host.status.set(label+'，可以继续浏览其他工作区。')
        future=self.host.worker.submit(operation,identifier)
        def finish():
            if self.host.closing:return
            if not future.done():self.after(100,finish);return
            self.busy=False
            try:
                result=future.result();self.host.status.set(label+' 完成'+('：'+str(result) if label=='导出交接' else ''))
                if self.current and self.current.id==identifier:self.report()
            except Exception as exc:self.badge.set('BLOCKED · 操作失败','blocked');put_text(self.details,str(exc));self.host.status.set('操作失败：'+str(exc))
        self.after(100,finish)
    def validate(self):self.save();self.report()
    def build(self):
        if self.busy:raise ValueError('请等待当前媒体操作完成')
        self.save();self.run_operation('构建 Timeline',self.production.build)
    def preview(self):
        if not self.current:raise ValueError('请先保存并 Build')
        self.require_saved();self.run_operation('生成粗剪 Preview',self.production.preview)
    def require_saved(self):
        d=self.production.definition(self.current.id)
        if (d.name,d.shot_ids,d.allow_missing_audio,d.allow_missing_subtitles)!=(self.name.get(),self.order,self.allow_audio.get(),self.allow_subtitles.get()):raise ValueError('有未保存的顺序 / 策略；请先保存并重新 Build')
    def play(self):
        if not self.current:raise ValueError('请先 Build / Generate Preview')
        self.require_saved();self.host.players.append(self.production.play(self.current.id))
    def export(self):
        if not self.current:raise ValueError('请先 Build / Generate Preview')
        self.require_saved();self.run_operation('导出交接',self.production.export)
