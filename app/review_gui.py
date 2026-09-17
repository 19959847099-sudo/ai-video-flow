"""Media-centred Human Gate. Production state stays in ProductionRunner."""
import json
import shutil
import tkinter as tk
from pathlib import Path
from tkinter import ttk
from PIL import Image, ImageTk
from .ui_widgets import Rows, ScrollArea, heading, text_field, readonly_text, put_text
from .ui_presenters import take_state, mode, harness_summary
from .ui_components import Advanced


class ReviewPanel(ttk.Frame):
    def __init__(self, notebook, host):
        super().__init__(notebook, padding=12)
        self.host, self.provider = host, host.provider
        self.shot_id = self.job_id = None
        self.items, self.jobs = [], []
        self.poster = self.photo = None
        heading(self, '审核与选片', '候选视频由你判断。Select 保存最终选择；Reject 后可以创建新的 Take。')
        self.shot_choice = ttk.Combobox(self, state='readonly')
        self.shot_choice.pack(fill='x', pady=(0, 10))
        self.shot_choice.bind('<<ComboboxSelected>>', lambda e: host.guard(self.choose_shot))
        body = ttk.Frame(self); body.pack(fill='both', expand=True)
        left = ttk.Frame(body, width=150); left.pack(side='left', fill='y', padx=(0, 14)); left.pack_propagate(False)
        heading(left, 'Takes')
        self.selected_label = ttk.Label(left, text='尚未选定最终素材', wraplength=140)
        self.selected_label.pack(fill='x', pady=(0, 8))
        self.list = Rows(left, width=135, height=6, style='Asset.Treeview')
        self.list.pack(fill='both', expand=True)
        self.list.bind('<<ListboxSelect>>', lambda e: host.guard(self.choose_job))
        for tag, color in [('selected','#dcefe3'),('rejected','#eee5e0'),('ready','#f5f5ed'),('pending','#e8edf0'),('failed','#f7dddd')]:
            self.list.tree.tag_configure(tag, background=color)
        decisions = ttk.Frame(body, width=200); decisions.pack(side='right', fill='y', padx=(14, 0)); decisions.pack_propagate(False)
        self.retry_button = ttk.Button(decisions, text='Retry · 创建新 Take', command=lambda:host.guard(self.retry)); self.retry_button.pack(side='bottom', fill='x', pady=(8, 0))
        self.decision_scroll = ScrollArea(decisions); self.decision_scroll.pack(fill='both', expand=True)
        right = self.decision_scroll.body
        heading(right, '人工决策')
        self.badge = tk.Label(right, text='尚无 Take', anchor='w', padx=12, pady=12, font=('Microsoft YaHei UI',10,'bold'))
        self.badge.pack(fill='x', pady=(0, 10))
        self.mode_label = ttk.Label(right, text='MOCK / ZERO-CALL', style='Heading.TLabel'); self.mode_label.pack(anchor='w')
        self.provider_label = ttk.Label(right, text='REAL 未启用', wraplength=185, style='Muted.TLabel'); self.provider_label.pack(fill='x', pady=(4, 14))
        self.select_button = ttk.Button(right, text='Select · 选为最终素材', style='Primary.TButton', command=lambda:host.guard(self.select)); self.select_button.pack(fill='x')
        ttk.Label(right, text='保存明确选择，重启后保持。', style='Muted.TLabel').pack(anchor='w', pady=(5, 18))
        ttk.Separator(right).pack(fill='x', pady=(0, 8))
        self.reason = text_field(right, '不采用的原因（可选）', 2)
        self.reject_button = ttk.Button(right, text='Reject · 不采用此 Take', style='Danger.TButton', command=lambda:host.guard(self.reject)); self.reject_button.pack(fill='x', pady=(8, 14))
        self.retry_prompt = text_field(right, 'Retry 生成描述（可选）', 3)
        ttk.Label(right, text='留空沿用当前 Shot 描述。创建新 Take，保留原历史。', wraplength=185, style='Muted.TLabel').pack(fill='x', pady=6)
        center = ttk.Frame(body); center.pack(fill='both', expand=True)
        self.summary = tk.StringVar(value='选择 Shot，查看候选 Take。')
        label = ttk.Label(center, textvariable=self.summary, style='Heading.TLabel', wraplength=500)
        label.pack(fill='x', pady=(0, 8)); label.bind('<Configure>', lambda e:label.configure(wraplength=max(100,e.width)))
        self.preview = tk.Label(center, text='尚无候选视频\n在 Shots 页面生成后回到这里', background='#202d29', foreground='#dbe4de', anchor='center')
        self.preview.pack(fill='both', expand=True); self.preview.bind('<Configure>', self.resize_preview)
        self.play_button = ttk.Button(center, text='▶ 播放实际视频', command=lambda:host.guard(self.play)); self.play_button.pack(anchor='w', pady=8)
        self.context_advanced=Advanced(center,'生成上下文 / Advanced');self.context_advanced.pack(fill='x')
        self.context_tabs = ttk.Notebook(self.context_advanced.body); self.context_tabs.pack(fill='x')
        production = ttk.Frame(self.context_tabs, padding=10); execution = ttk.Frame(self.context_tabs, padding=10); debug = ttk.Frame(self.context_tabs, padding=10)
        self.context_tabs.add(production, text='生成上下文'); self.context_tabs.add(execution, text='执行摘要'); self.context_tabs.add(debug, text='Advanced')
        self.context = readonly_text(production, 4); self.execution_summary = readonly_text(execution, 4); self.details = readonly_text(debug, 4)
        self.clear()

    def buttons(self, ready=False, selected=False, rejected=False, busy=False):
        self.play_button.configure(state='normal' if ready and shutil.which('ffplay') else 'disabled')
        self.select_button.configure(state='normal' if ready and not selected else 'disabled')
        self.reject_button.configure(state='normal' if ready and not rejected else 'disabled')
        self.retry_button.configure(state='normal' if ready and rejected and not busy else 'disabled')

    def clear(self, message='尚无 Take · 请先在 Shots 页面生成视频'):
        self.poster = self.photo = None
        self.preview.configure(image='', text=message)
        self.summary.set(message)
        self.badge.configure(text='尚无 Take', background='#e6eae4', foreground='#45564c')
        self.mode_label.configure(text='MOCK / ZERO-CALL'); self.provider_label.configure(text='REAL 未启用')
        self.selected_label.configure(text='尚未选定最终素材')
        for box in (self.context,self.execution_summary,self.details): put_text(box, '')
        self.buttons()

    def refresh(self, shot_id=None, job_id=None):
        self.items = self.host.store.shots()
        self.shot_choice['values'] = [('示例 · ' if s.is_example else '') + s.description for s in self.items]
        if shot_id is not None: self.shot_id = shot_id
        if job_id is not None: self.job_id = job_id
        if not self.shot_id and self.items: self.shot_id = self.items[0].id
        idx = next((i for i, s in enumerate(self.items) if s.id == self.shot_id), None)
        self.list.delete(0, 'end')
        if idx is None:
            self.jobs=[]; self.job_id=None; self.clear('尚无 Shot · 先建立角色、场景与镜头'); return
        self.shot_choice.current(idx)
        self.jobs = self.provider.executions(self.shot_id)
        review = self.provider.review(self.shot_id)
        selected = next((j for j in self.jobs if j.result_id and j.result_id == review.selected_result_id), None)
        self.selected_label.configure(text=f'✓ 最终素材：Take {selected.take_number}' if selected else '尚未选定最终素材')
        for i, job in enumerate(self.jobs):
            state, tag = take_state(job, review)
            self.list.insert('end', f'Take {job.take_number:02}   {state}\n{mode(job)}'); self.list.item(i, tags=(tag,))
        idx = next((i for i, j in enumerate(self.jobs) if j.id == self.job_id), None)
        if idx is None and self.jobs:
            idx = self.jobs.index(selected) if selected else len(self.jobs)-1
            self.job_id = self.jobs[idx].id
        if idx is not None:
            self.list.selection_set(idx); self.show_job()
        else:
            self.job_id=None; self.clear()

    def choose_shot(self):
        if self.shot_choice.current() < 0: return
        if not self.host.confirm_discard(): self.refresh(); return
        self.shot_id=self.items[self.shot_choice.current()].id; self.job_id=None
        self.reason.set(''); self.retry_prompt.set(''); self.host.dirty=False
        self.refresh()

    def choose_job(self):
        selection=self.list.curselection()
        if not selection: return
        next_id=self.jobs[selection[0]].id
        if next_id != self.job_id:
            if not self.host.confirm_discard(): self.refresh(); return
            self.reason.set(''); self.retry_prompt.set(''); self.host.dirty=False
        self.job_id=next_id; self.show_job()

    def set_details(self, text): put_text(self.details, text)

    def resize_preview(self, event=None):
        if self.poster is None: return
        width=max(80,self.preview.winfo_width()-20); height=max(60,self.preview.winfo_height()-16)
        image=self.poster.copy(); image.thumbnail((width,height))
        self.photo=ImageTk.PhotoImage(image); self.preview.configure(image=self.photo, text='')

    def show_job(self):
        job=self.provider.execution(self.job_id); review=self.provider.review(self.shot_id)
        state,tag=take_state(job,review)
        if tag == 'rejected' and not self.reason.get() and not self.host.dirty:
            self.reason.set(review.rejected[job.result_id])
        colors={'selected':('#dcefe3','#17664d'),'rejected':('#eee5e0','#815b45'),'ready':('#edf0df','#5c6733'),'pending':('#e8edf0','#42627b'),'failed':('#f7dddd','#933f3f')}
        self.badge.configure(text=f'Take {job.take_number:02}\n{state}',background=colors[tag][0],foreground=colors[tag][1])
        self.mode_label.configure(text=mode(job))
        self.provider_label.configure(text=('fal / Kling O3\nFixture · 未真实调用视频 API' if job.provider=='fal' else '本地 Mock\nFFmpeg 占位视频')+'\nREAL 未启用')
        self.summary.set(f'Take {job.take_number:02} · {state}'); self.buttons()
        self.poster=self.photo=None
        self.preview.configure(image='',text='等待视频完成' if job.status!='failed' else '生成失败，请查看执行摘要')
        put_text(self.context,'生成完成后显示当次生产上下文。')
        harness,path=harness_summary(Path(__file__).resolve().parents[1],job)
        put_text(self.execution_summary,'Provider：'+job.provider+'\n模式：'+mode(job)+'\n'+' → '.join(job.history)+'\n'+(job.error+'\n' if job.error else '')+'\n'+harness)
        self.set_details(f'Execution：{job.id}\nTask：{job.task_id}\nShot：{job.shot_id}\nModel：{job.model}\nRetry of：{job.retry_of or "无"}\nTrace：{path or "无匹配旁路记录"}')
        if job.status != 'completed': return
        try:
            result,task=self.provider.trace(job.result_id)
        except Exception as exc:
            self.preview.configure(text='结果文件无法读取\n请检查工程详情')
            self.set_details(self.details.get('1.0','end')+'\n\n读取错误：'+str(exc)); return
        try:
            with Image.open(self.host.store.path(result.poster_path)) as image:self.poster=image.copy()
            self.resize_preview()
        except (OSError,ValueError):self.preview.configure(text='缩略图缺失，仍可尝试播放实际视频')
        self.summary.set(f'Take {job.take_number:02} · {state} · {result.duration:g} 秒')
        self.buttons(True,tag=='selected',tag=='rejected',any(j.status in ('pending','processing') for j in self.jobs))
        scene=f'{task.scene.name} / {task.scene_state.name}' if task.scene else '旧任务未设置场景'
        text=(f'角色  {task.character.name} / {task.look.name}\n场景  {scene}\n镜头  {task.shot.description}\n角色参考图  '+', '.join(r.name for r in task.references)+'\n场景参考图  '+', '.join(r.name for r in task.scene_references)+'\n\n最终生成描述\n'+self.provider.submitted_prompt(task.id))
        if task.first_frame: text = "首帧输入 · 已绑定（当次任务快照；ID 见 Advanced）\n" + text
        put_text(self.context,text)
        request_path=self.host.store.path(f'tasks/{task.id}/'+('provider_request.json' if job.provider=='fal' else 'mock_request.json'))
        request=json.loads(request_path.read_text(encoding='utf-8')) if request_path.is_file() else {}
        if isinstance(request.get('body'),dict) and 'image_urls' in request['body']:
            request['body']['image_urls']=[f'[参考图 {i+1}，完整内容见请求文件]' for i,_ in enumerate(request['body']['image_urls'])]
        if isinstance(request.get('body'),dict) and request['body'].get('start_image_url'):
            request['body']['start_image_url']='[首帧图片，完整内容见请求文件]'
        self.set_details(self.details.get('1.0','end')+f'\n素材：{result.path}\nSHA256：{result.sha256}\nRequest：{request_path}\n\n'+json.dumps(request,ensure_ascii=False,indent=2))
        if not shutil.which('ffplay'): self.host.status.set('未找到 ffplay：请安装 FFmpeg 并加入 PATH 后重启。仍可查看已保存结果。')

    def current_result(self):
        if not self.job_id: raise ValueError('请选择一个已完成的 Take')
        job=self.provider.execution(self.job_id)
        if job.status!='completed' or job.shot_id!=self.shot_id: raise ValueError('请选择当前 Shot 已完成的 Take')
        return job.result_id

    def play(self):
        self.host.players.append(self.provider.play(self.current_result()))
        self.host.status.set('正在用 FFplay 播放实际 MP4；播放完自动关闭。')

    def select(self):
        self.provider.select(self.shot_id,self.current_result())
        self.reason.set(''); self.retry_prompt.set(''); self.host.dirty=False
        self.refresh(); self.host.status.set('已保存最终 Selected Take，重启后保持。')

    def reject(self):
        self.provider.reject(self.shot_id,self.current_result(),self.reason.get())
        self.host.dirty=bool(self.retry_prompt.get().strip())
        self.refresh(); self.host.status.set('已 Reject 并保存原因；可调整描述后 Retry，原历史保留。')

    def retry(self):
        job=self.provider.submit(self.shot_id,retry_of=self.current_result(),generation_description=self.retry_prompt.get().strip() or None)
        self.reason.set(''); self.retry_prompt.set(''); self.host.dirty=False
        self.refresh(job_id=job.id)
        self.host.status.set(f'Retry 已创建新任务 · Take {job.take_number} · 排队中。原 Take 未覆盖。')
