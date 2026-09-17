"""Thin image review: candidates stay candidates until an explicit human action."""
import tkinter as tk
from tkinter import ttk
from PIL import Image,ImageOps,ImageTk
from .image_production import ImageProduction
from .ui_components import ActionBar,Advanced,StatusBadge
from .ui_widgets import Rows,text_field,readonly_text,put_text

class ImagePanel(ttk.Frame):
    def __init__(self,parent,host):
        super().__init__(parent,padding=12);self.host=host;self.production=ImageProduction(host.store);self.target=None;self.current=None;self.items=[]
        left=ttk.Frame(self,width=205);left.pack(side='left',fill='y',padx=(0,14));left.pack_propagate(False)
        ttk.Label(left,text='图像候选 · ZERO-CALL',style='Heading.TLabel').pack(anchor='w')
        self.list=Rows(left,width=185);self.list.pack(fill='both',expand=True)
        self.list.bind('<<ListboxSelect>>',lambda e:host.guard(self.choose))
        right=ttk.Frame(self);right.pack(side='left',fill='both',expand=True)
        self.title=ttk.Label(right,text='从角色 / 场景 / Shot 页面进入图像生产',style='Heading.TLabel');self.title.pack(anchor='w')
        ttk.Label(right,text='ComfyUI Fixture · 本地占位 PNG · 不代表 AI 图像质量 · 采纳由你决定',style='Muted.TLabel').pack(anchor='w',pady=5)
        actions=ActionBar(right);actions.pack(side='bottom',fill='x',pady=8)
        self.accept_identity=host.button(actions,'采纳为稳定参考图',lambda:self.promote('identity'))
        self.accept_variant=host.button(actions,'采纳为当前 Look / State',lambda:self.promote('variant'))
        self.accept_frame=host.button(actions,'用作 Shot 首帧',lambda:self.promote('first_frame'))
        self.reject_button=host.button(actions,'Reject 图像',self.reject)
        self.retry_button=host.button(actions,'Retry 图像',self.retry)
        self.image_badge=StatusBadge(right,text='Candidate');self.image_badge.pack(anchor='w',pady=5)
        self.settings=Advanced(right,'生成 / Retry 设置');self.settings.pack(fill='x')
        self.description=text_field(self.settings.body,'生成描述 / Retry 描述',3)
        generate_bar=ActionBar(self.settings.body);generate_bar.pack(fill='x')
        self.generate_button=host.button(generate_bar,'生成图像 · ZERO-CALL',self.generate)
        self.reason=text_field(self.settings.body,'Reject 原因（可选）',1)
        details_area=Advanced(right);details_area.pack(side='bottom',fill='x')
        self.details=readonly_text(details_area.body,height=4)
        self.original=None
        self.preview=ttk.Label(right,text='选择候选图片预览',anchor='center');self.preview.pack(fill='both',expand=True,pady=8)
        self.preview.bind('<Configure>',lambda event:self.resize_preview())
        self.refresh();self.after(500,self.tick)
    def open(self,purpose,identifier,variant=None):
        task=self.production.build(purpose,identifier,variant)
        self.target=(purpose,identifier,variant);self.current=None
        self.title.configure(text=purpose+' · '+(task.shot.description if task.shot else (task.character or task.scene).name))
        if not self.settings.opened:self.settings.flip()
        self.description.set(task.description);self.reason.set('');self.preview.configure(image='',text='填写描述，然后生成候选图片');self.preview.image=None;self.original=None
        self.host.tabs.select(self);self.buttons();put_text(self.details,task.final_prompt)
    def buttons(self):
        review=self.production.review(self.current.id) if self.current and self.current.result_id else None
        task=self.production.task(self.current.task_id) if self.current else None
        ready=review and not review.rejected and (not review.promotion or (task and task.shot))
        for b,enabled in [(self.generate_button,self.target is not None),(self.accept_identity,ready and task and not task.shot),(self.accept_variant,ready and task and not task.shot),(self.accept_frame,ready and task and task.shot),(self.reject_button,ready and not review.promotion),(self.retry_button,review and review.rejected)]:b.configure(state='normal' if enabled else 'disabled')
    def refresh(self,selected=None):
        selected=selected or (self.current.id if self.current else None)
        self.items=self.production.jobs();self.list.delete(0,'end')
        for i,j in enumerate(self.items):
            t=self.production.task(j.task_id);r=self.production.review(j.id)
            name=t.shot.description if t.shot else (t.character or t.scene).name
            status='已采纳 '+r.promotion if r.promotion else ('REJECTED' if r.rejected else ('CANDIDATE' if j.status=='completed' else j.status.upper()))
            self.list.insert('end',name+'\n'+status+' · FIXTURE')
            if j.id==selected:self.list.selection_set(i);self.current=j
        self.buttons()
    def choose(self):
        selected=self.list.curselection()
        if not selected:return
        self.current=self.items[selected[0]];task=self.production.task(self.current.task_id);review=self.production.review(self.current.id)
        state='selected' if review.promotion else ('rejected' if review.rejected else ('candidate' if self.current.status=='completed' else 'pending'))
        self.image_badge.set(('PROMOTED / 已采纳' if review.promotion else state.upper()),state)
        self.target=None;self.title.configure(text=(task.shot.description if task.shot else (task.character or task.scene).name))
        self.description.set(task.description);self.reason.set(review.reason)
        self.preview.configure(image='',text=self.current.error or '等待图片入库…');self.preview.image=None;self.original=None
        if self.current.result_id:
            result,task=self.production.trace(self.current.result_id)
            with Image.open(self.host.store.path(result.path)) as im:self.original=im.copy()
            self.resize_preview()
        put_text(self.details,task.final_prompt+'\nTask '+task.id+'\nResult '+str(self.current.result_id)+'\nHuman Gate: '+(review.promotion or ('Rejected' if review.rejected else '等待人工审核')))
        self.buttons()
    def resize_preview(self):
        if self.original is None:return
        size=(max(1,min(650,self.preview.winfo_width()-12)),max(1,min(290,self.preview.winfo_height()-12)))
        pic=ImageTk.PhotoImage(ImageOps.contain(self.original,size))
        self.preview.configure(image=pic,text='');self.preview.image=pic

    def generate(self):
        if not self.target:raise ValueError('请从资产页进入图像生成')
        self.current=self.production.submit(*self.target,description=self.description.get());self.target=None
        self.refresh(self.current.id);self.choose();self.host.status.set('ComfyUI Fixture 已提交；没有调用远程服务')
    def promote(self,destination):
        self.production.promote(self.current.result_id,destination)
        # Refresh editors from disk so a later save cannot drop a promoted reference.
        h=self.host
        if h.char:h.char=h.store.character(h.char.id);h.render_assets()
        if h.scene_editor.scene:h.scene_editor.scene=h.store.scene(h.scene_editor.scene.id);h.scene_editor.render()
        h.show_first_frame()
        self.refresh();self.choose();h.status.set('已保存人工采纳关系；历史图像任务保持不变')
    def reject(self):
        self.production.reject(self.current.result_id,self.reason.get());self.refresh();self.choose()
        if not self.settings.opened:self.settings.flip()
    def retry(self):
        self.current=self.production.retry(self.current.result_id,self.description.get());self.refresh(self.current.id);self.choose()
    def tick(self):
        if self.host.closing:return
        try:
            jobs=[j for j in self.production.jobs() if j.status in ('pending','processing')]
            if jobs:
                job=self.production.poll(jobs[0].id);self.refresh()
                if self.current and self.current.id==job.id:self.choose()
        except Exception as exc:self.host.status.set('图像处理失败：'+str(exc))
        self.after(650,self.tick)
