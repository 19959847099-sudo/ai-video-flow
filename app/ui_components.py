"""Small presentation-only composites. No production records or workflow rules."""
import tkinter as tk
from tkinter import ttk

COLORS={'selected':('#e4f2e9','#246046'),'ready':('#e8eff5','#365b75'),'candidate':('#e8eff5','#365b75'),'pending':('#f7efdb','#85611b'),'blocked':('#f8e5e4','#9c3935'),'failed':('#f8e5e4','#9c3935'),'rejected':('#f2e9e4','#805945'),'stale':('#f7efdb','#85611b'),'missing':('#edf0f2','#66727d'),'fixture':('#edf0f2','#52616e')}

class StatusBadge(tk.Label):
    def __init__(self,parent,text='Missing',state='missing',**kwargs):
        super().__init__(parent,padx=8,pady=3,anchor='w',font=('Microsoft YaHei UI',9,'bold'),**kwargs);self.set(text,state)
    def set(self,text,state='missing'):
        bg,fg=COLORS.get(state,COLORS['missing']);self.configure(text=text,background=bg,foreground=fg)

class ActionBar(ttk.Frame):
    """Wrap standard buttons at the available width without changing their commands."""
    def __init__(self,parent,**kwargs):
        super().__init__(parent,**kwargs);self.items=[];self.pending=None;self.bind('<Configure>',self.schedule)
    def add(self,widget):
        self.items.append(widget);self.schedule()
    def schedule(self,event=None):
        if self.pending is None:self.pending=self.after_idle(self.layout)
    def layout(self):
        self.pending=None;width=max(100,self.winfo_width());x=y=0;line=0
        for item in self.items:
            w=item.winfo_reqwidth();h=item.winfo_reqheight()
            if x and x+w+6>width:x=0;y+=line+5;line=0
            item.place(x=x,y=y);x+=w+6;line=max(line,h)
        self.configure(height=y+line+4)

class Advanced(ttk.Frame):
    def __init__(self,parent,title='Advanced · 技术详情'):
        super().__init__(parent);self.opened=False
        self.toggle=ttk.Button(self,text='＋ '+title,style='Quiet.TButton',command=self.flip);self.toggle.pack(anchor='w')
        self.body=ttk.Frame(self,padding=(0,6,0,6));self.title=title
    def flip(self):
        self.opened=not self.opened
        if self.opened:self.body.pack(fill='both',expand=True)
        else:self.body.pack_forget()
        self.toggle.configure(text=('－ ' if self.opened else '＋ ')+self.title)

class Navigation(ttk.Frame):
    routes=[('生产','shots','镜头工作台',2,None),('生产','dialogue','对白',5,1),('资产','characters','角色',0,None),('资产','scenes','场景',1,None),('资产','voices','声音',5,0),('审核','images','图像 / 首帧',4,None),('审核','video','视频选片',3,None),('审核','audio','音频选片',5,2),('交付','timeline','粗剪 / 交接',6,None)]
    def __init__(self,parent,host):
        super().__init__(parent,width=136,style='Nav.TFrame');self.host=host;self.pack_propagate(False);self.buttons={};group=None
        ttk.Label(self,text='WORKFLOW',style='NavSection.TLabel').pack(anchor='w',padx=14,pady=(8,4))
        for category,key,label,idx,sub in self.routes:
            if category!=group:ttk.Label(self,text=category,style='NavSection.TLabel').pack(anchor='w',padx=14,pady=(5,2));group=category
            b=ttk.Button(self,text=label,style='Nav.TButton',command=lambda k=key:self.go(k));b.pack(fill='x',padx=6,pady=1);self.buttons[key]=b
    def go(self,key):
        if self.host.dirty:self.host.status.set('请先保存当前编辑，再切换工作区。');return
        route=next(r for r in self.routes if r[1]==key);_,_,_,idx,sub=route
        if idx==5:self.host.audio_panel.refresh();self.host.audio_panel.tabs.select(sub)
        if idx==6:self.host.rough_panel.refresh()
        self.host.tabs.select(idx);self.sync()
    def sync(self,event=None):
        current=self.host.tabs.index('current');sub=self.host.audio_panel.tabs.index('current') if current==5 else None
        for category,key,label,idx,subidx in self.routes:
            selected=(current,sub)==(idx,subidx);self.buttons[key].configure(style='NavSelected.TButton' if selected else 'Nav.TButton')
            if selected:self.host.breadcrumb.set(category+'  /  '+label)

class ShotOverview(ttk.Frame):
    def __init__(self,parent):
        super().__init__(parent)
        from .ui_widgets import ScrollArea,heading,readonly_text
        area=ScrollArea(self);area.pack(fill='both',expand=True);body=area.body
        self.heading=ttk.Label(body,text='镜头生产概览',style='Heading.TLabel');self.heading.pack(anchor='w',pady=(12,8))
        self.badges=ActionBar(body);self.badges.pack(fill='x',pady=(0,14))
        self.summary=readonly_text(body,9)
        ttk.Label(body,text='状态直接读取已保存的生产记录；选择与最终判断仍由人完成。',style='Muted.TLabel',wraplength=450).pack(anchor='w',pady=12)
        self.advanced=Advanced(body);self.advanced.pack(fill='x');self.details=readonly_text(self.advanced.body,8);self.set_empty()
    def set_empty(self):self.show(dict(empty=True))
    def show(self,data):
        from .ui_widgets import put_text
        import json
        for item in self.badges.items:item.destroy()
        self.badges.items=[]
        for name,value,state in data.get('badges',[]):self.badges.add(StatusBadge(self.badges,text=name+'  '+value,state=state))
        if data.get('empty'):
            self.heading.configure(text='从镜头开始组织生产');put_text(self.summary,'还没有选中的 Shot。\n\n先在资产区创建角色与场景，再用“新建 Shot”保存镜头需求。\n生成的素材在审核区由你 Select，最后进入粗剪交接。');put_text(self.details,'')
        elif data.get('error'):
            self.heading.configure(text='Blocked · 生产数据读取异常');put_text(self.summary,data['error'])
        else:
            self.heading.configure(text=data['title']);put_text(self.summary,'谁\n'+data['who']+'\n\n在哪里\n'+data['where']+'\n\n做什么 / 怎么拍\n'+data['requirements']+'\n\n声音  '+data['voice']+'  ·  '+str(data['dialogues'])+' 句对白')
            put_text(self.details,json.dumps(data['details'],ensure_ascii=False,indent=2))
