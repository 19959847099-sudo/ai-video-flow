from __future__ import annotations

import argparse
import json
import os
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageOps, ImageTk

from .core import Character, Look, Shot, Store, DummyProviderAdapter
from .fal_adapter import ProductionRunner
from .scene_gui import SceneEditor
from .review_gui import ReviewPanel
from .image_gui import ImagePanel
from .audio_gui import AudioPanel
from .rough_cut_gui import RoughCutPanel
from .ui_widgets import theme, photo, render_refs, StatusText
from .ui_presenters import shot_state
from .workspace_ui import char_layout, shot_layout
from .ui_components import Navigation, ActionBar, StatusBadge
from .ui_presenters import shot_overview


class App(tk.Tk):
    def __init__(self, data_root):
        super().__init__()
        self.title("AI 视频工作流 · UI-Final 生产工作台")
        theme(self)
        self.geometry("1280x800")
        self.minsize(880, 460)
        self.store = Store(data_root)
        self.provider = ProductionRunner(self.store)
        self.worker = ThreadPoolExecutor(max_workers=1)
        self.pending_work = None
        self.players = []
        self.closing = False
        self.char = None
        self.shot = None
        self.look_id = None
        self.dirty = False
        self.status = StatusText(value="本地文件 · 零 API 费用 · Mock 占位视频 · 最终 Take 由你决定")
        self.protocol("WM_DELETE_WINDOW", self.close)
        ttk.Label(self, textvariable=self.status, wraplength=1100).pack(side="bottom", fill="x", padx=14, pady=8)
        header = ttk.Frame(self, padding=(16, 10, 16, 8));header.pack(fill="x")
        ttk.Label(header, text="AI 视频生产工作台", style="Title.TLabel").pack(side="left")
        self.breadcrumb=tk.StringVar(value="生产 / 镜头工作台")
        ttk.Label(header,textvariable=self.breadcrumb,style="Muted.TLabel").pack(side="left",padx=20)
        StatusBadge(header,text="FIXTURE · ZERO-CALL",state="fixture").pack(side="right")
        shell=ttk.Frame(self);shell.pack(fill="both",expand=True)
        self.nav_mount=ttk.Frame(shell);self.nav_mount.pack(side="left",fill="y")
        self.tabs=ttk.Notebook(shell,style="Shell.TNotebook");self.tabs.pack(side="left",fill="both",expand=True,padx=(0,8),pady=(0,4))
        self.ctab = ttk.Frame(self.tabs, padding=12)
        self.stab = ttk.Frame(self.tabs, padding=12)
        self.tabs.add(self.ctab, text="角色 Characters")
        self.scene_editor = SceneEditor(self.tabs, self)
        self.tabs.add(self.scene_editor, text="场景 Scenes")
        self.tabs.add(self.stab, text="镜头 Shots")
        self.build_char()
        self.build_shot()
        self.review_panel = ReviewPanel(self.tabs, self)
        self.tabs.add(self.review_panel, text="审核 Review")
        self.image_panel = ImagePanel(self.tabs, self)
        self.tabs.add(self.image_panel, text="图像 / 首帧")
        self.audio_panel = AudioPanel(self.tabs, self)
        self.tabs.add(self.audio_panel, text="声音 / 对白")
        self.rough_panel = RoughCutPanel(self.tabs, self)
        self.tabs.add(self.rough_panel, text="粗剪 / Timeline")
        self.navigation=Navigation(self.nav_mount,self);self.navigation.pack(fill="both",expand=True)
        self.audio_panel.tabs.bind("<<NotebookTabChanged>>",self.navigation.sync,add=True)
        self.active_tab = 0
        self.tabs.bind("<<NotebookTabChanged>>", self.tab_changed)
        self.bind_all("<KeyRelease>", self.mark_dirty, add=True)
        self.chars, self.scenes, self.shots = [], [], []
        try:
            self.refresh()
            self.audio_panel.refresh()
            self.rough_panel.refresh()
            self.tabs.select(self.stab)
            if self.shots:
                self.shot_list.selection_set(next((i for i,x in enumerate(self.shots) if self.provider.review(x.id).selected_result_id),0));self.select_shot()
            else:self.shot_overview.set_empty()
            if self.chars:
                self.char_list.selection_set(0)
            else:
                self.new_char()
                self.status.set("开始生产：新建角色并导入参考图，再建立场景和 Shot。")
        except Exception as exc:
            self.status.set("数据读取失败，请检查数据文件后重启：" + str(exc))
            self.after(100, lambda error=str(exc): messagebox.showerror("数据读取失败", error, parent=self))
        self.after(600, self.poll_jobs)

    def poll_jobs(self):
        if self.closing: return
        try:
            if self.pending_work is not None:
                if self.pending_work.done():
                    job = self.pending_work.result()
                    self.pending_work = None
                    self.status.set(f"{job.provider} Take {job.take_number} · {job.status}" + (f" · {job.error}" if job.error else ""))
                    self.review_panel.refresh()
            else:
                jobs = [j for j in self.provider.executions() if j.status in ("pending", "processing")]
                if jobs: self.pending_work = self.worker.submit(self.provider.poll, jobs[0].id)
        except Exception as exc:
            self.pending_work = None
            self.status.set("生成状态读取失败：" + str(exc))
        self.after(600, self.poll_jobs)

    def tab_changed(self, event=None):
        current = self.tabs.index("current")
        if current == self.active_tab:
            self.navigation.sync();return
        if self.dirty:
            messagebox.showinfo("请先保存", "请先保存当前页的编辑，再切换页面。", parent=self)
            self.tabs.select(self.active_tab)
            return
        self.active_tab = current
        self.navigation.sync()
        if self.tabs.select() == str(self.image_panel): self.image_panel.refresh()
        elif self.tabs.select() == str(self.review_panel): self.review_panel.refresh()
        elif self.tabs.select() == str(self.stab):
            self.guard(self.refresh)
            if self.shot:
                state = shot_state(self.shot, self.provider.executions(self.shot.id), self.provider.review(self.shot.id))
                self.shot_heading.configure(text=f"{state}  ·  {self.shot.description}")
                self.update_shot_overview()
        elif self.tabs.select() == str(self.scene_editor) and self.scene_editor.scene is None and self.scene_editor.items:
            self.scene_editor.list.selection_set(0)

    def mark_dirty(self, event=None):
        if event is not None and hasattr(self, "rough_panel") and str(event.widget).startswith(str(self.rough_panel)):
            return
        if event is not None and hasattr(self, "audio_panel") and str(event.widget).startswith(str(self.audio_panel)):
            return
        if event is not None and hasattr(self, "image_panel") and str(event.widget).startswith(str(self.image_panel)):
            return
        if event is not None and (event.keysym in ('Left', 'Right', 'Up', 'Down', 'Home', 'End', 'Prior', 'Next', 'Tab', 'Escape', 'Shift_L', 'Shift_R', 'Control_L', 'Control_R', 'Alt_L', 'Alt_R')
                                  or (event.state & 4 and event.keysym.lower() in ('a', 'c'))):
            return
        if event is None or (isinstance(event.widget, (ttk.Entry, tk.Text))
                             and str(event.widget.cget("state")) == "normal"):
            self.dirty = True

    def guard(self, action):
        try:
            action()
        except Exception as exc:
            self.status.set("操作失败：" + str(exc))
            # Inline feedback keeps the production workspace visible; no new state is persisted.
            self.bell()

    def button(self, parent, text, command):
        style="Danger.TButton" if any(x in text for x in ("Reject","移除")) else ("Primary.TButton" if any(x in text for x in ("保存", "Select", "采纳", "用作")) else "TButton")
        result = ttk.Button(parent, text=text, style=style, command=lambda: self.guard(command))
        if isinstance(parent,ActionBar):parent.add(result)
        else:result.pack(side="left", padx=3, pady=4)
        return result

    def field(self, parent, label):
        ttk.Label(parent, text=label).pack(anchor="w", pady=(5, 1))
        var = tk.StringVar()
        ttk.Entry(parent, textvariable=var).pack(fill="x")
        return var

    def confirm_discard(self):
        return not self.dirty or messagebox.askyesno("尚未保存", "放弃未保存的编辑并继续？", parent=self)

    def close(self):
        if self.confirm_discard():
            self.closing = True
            for process in self.players:
                if process.poll() is None: process.terminate()
            self.worker.shutdown(wait=True)
            self.destroy()

    def destroy(self):
        # Tests and embedded callers can destroy the root without using WM_DELETE_WINDOW.
        # Cancel Tcl timers here; each owning widget then removes its own Python command.
        for timer in self.tk.call('after','info'):
            self.tk.call('after','cancel',timer)
        super().destroy()

    def build_char(self):
        char_layout(self)

    def build_shot(self):
        shot_layout(self)

    def open_audio(self, target):
        if self.dirty: raise ValueError("请先保存当前编辑")
        if target == "character":
            if not self.char: raise ValueError("请先保存角色")
            self.audio_panel.open_character(self.char.id)
        else:
            if not self.shot: raise ValueError("请先选择并保存 Shot")
            self.audio_panel.open_shot(self.shot.id)
        self.tabs.select(self.audio_panel)

    def open_images(self, purpose):
        if self.dirty: raise ValueError("请先保存当前资产编辑")
        if purpose == "CHARACTER_REFERENCE":
            if not self.char: raise ValueError("请先保存角色")
            self.image_panel.open(purpose, self.char.id, self.look_id)
        elif purpose == "SCENE_REFERENCE":
            editor = self.scene_editor
            if not editor.scene: raise ValueError("请先保存场景")
            self.image_panel.open(purpose, editor.scene.id, editor.state_id)
        else:
            if not self.shot: raise ValueError("请先选择并保存 Shot")
            self.image_panel.open(purpose, self.shot.id)

    def open_review(self):
        if not self.shot: raise ValueError("请先选择或保存 Shot")
        if self.dirty: raise ValueError("请先保存镜头编辑")
        self.review_panel.refresh(shot_id=self.shot.id)
        self.tabs.select(self.review_panel)

    def refresh(self):
        selected_char = self.chars[self.sc.current()].id if hasattr(self, 'chars') and self.sc.current() >= 0 else None
        selected_scene = self.scenes[self.ss.current()].id if hasattr(self, 'scenes') and self.ss.current() >= 0 else None
        self.chars = self.store.characters()
        self.scenes = self.store.scenes()
        self.shots = self.store.shots()
        self.char_list.delete(0, "end")
        self.shot_list.delete(0, "end")
        for i, c in enumerate(self.chars):
            self.char_list.insert("end", ("[示例] " if c.is_example else "") + c.name + f"\n{len(c.looks)} Looks · {len(c.references)} 张参考图")
            ref = next((r for r in c.references if r.id in c.identity_reference_ids), next(iter(c.references), None))
            if ref: self.char_list.image(i, photo(self.store, ref))
        for i, s in enumerate(self.shots):
            char = next((c.name for c in self.chars if c.id == s.character_id), '角色缺失')
            scene = next((p.name for p in self.scenes if p.id == s.scene_id), '尚未选择场景')
            jobs = self.provider.executions(s.id)
            state = shot_state(s, jobs, self.provider.review(s.id))
            self.shot_list.insert("end", ("[示例] " if s.is_example else "") + s.description + f"\n{char} / {scene}\n{state} · {len(jobs)} Takes")
        self.sc["values"] = [f"{i+1}. {c.name}" for i, c in enumerate(self.chars)]
        self.ss["values"] = [f"{i+1}. {s.name}" for i, s in enumerate(self.scenes)]
        if selected_char:
            self.sc.current(next(i for i, c in enumerate(self.chars) if c.id == selected_char))
        if selected_scene:
            self.ss.current(next(i for i, s in enumerate(self.scenes) if s.id == selected_scene))
        self.scene_editor.refresh()

    def new_char(self):
        if not self.confirm_discard(): return
        self.char = None
        for v in [self.cname, self.cdesc, self.cidentity]: v.set("")
        self.cexample.set(False)
        self.clear_look()
        self.render_assets()
        self.dirty = False

    def select_char(self):
        sel = self.char_list.curselection()
        if not sel or not self.confirm_discard(): return
        self.char = self.store.character(self.chars[sel[0]].id)
        self.cname.set(self.char.name)
        self.cdesc.set(self.char.description)
        self.cidentity.set(self.char.identity)
        self.cexample.set(self.char.is_example)
        self.clear_look()
        self.render_assets()
        self.dirty = False

    def read_char(self):
        payload = self.char.model_dump() if self.char else {}
        payload.update(name=self.cname.get(), description=self.cdesc.get(),
                       identity=self.cidentity.get(), is_example=self.cexample.get())
        return Character.model_validate(payload)

    def commit_look(self, char):
        if not self.lname.get().strip():
            if self.look_id or self.ldesc.get().strip() or self.lappearance.get().strip():
                raise ValueError("Look 名称不能为空")
            return
        values = dict(name=self.lname.get(), description=self.ldesc.get(),
                      appearance=self.lappearance.get(),
                      reference_ids=[char.references[i].id for i in self.look_refs.curselection()])
        if self.look_id: values["id"] = self.look_id
        look = Look(**values)
        char.looks = [look if x.id == look.id else x for x in char.looks]
        if not any(x.id == look.id for x in char.looks): char.looks.append(look)
        self.look_id = look.id

    def save_char(self):
        char = self.read_char()
        self.commit_look(char)
        self.store.save_character(char)
        self.char = char
        self.refresh()
        self.render_assets()
        self.dirty = False
        self.status.set("角色与 Look 已保存")

    def render_assets(self):
        self.char_card.show(self.store, self.char, self.char.looks if self.char else [], "角色")
        voice='未设置'
        if self.char:
            try:voice=self.audio_panel.production.default_voice(self.char.id).name
            except ValueError:pass
        current=next((x for x in self.char.looks if x.id==self.look_id),None) if self.char else None
        self.char_summary.configure(text='当前 Look：'+(current.name if current else '未选择')+'   ·   默认声音：'+voice)
        self.ref_list.delete(0, "end")
        self.look_refs.delete(0, "end")
        self.preview_label.configure(image="", text="图片预览")
        self.preview_image = None
        if not self.char:
            self.look_choice["values"] = []
            return
        current = next((x for x in self.char.looks if x.id == self.look_id), None)
        for i, r in enumerate(self.char.references):
            self.ref_list.insert("end", ("[身份] " if r.id in self.char.identity_reference_ids else "") + r.name)
            self.look_refs.insert("end", r.name)
            if current and r.id in current.reference_ids: self.look_refs.selection_set(i)
        self.look_choice["values"] = [f"{i+1}. {x.name}" for i, x in enumerate(self.char.looks)]
        if current: self.look_choice.current(self.char.looks.index(current))
        render_refs(self.ref_list, self.store, self.char, self.char.looks, "身份图")

    def add_ref(self):
        filenames = filedialog.askopenfilenames(parent=self, title="添加本地 Reference 图片",
                      filetypes=[("图片", "*.png *.jpg *.jpeg *.webp")])
        if not filenames: return
        self.save_char()
        for filename in filenames:
            ref = self.store.import_reference(filename)
            if not any(x.sha256 == ref.sha256 for x in self.char.references):
                self.char.references.append(ref)
        self.store.save_character(self.char)
        self.render_assets()
        self.status.set("Reference 已复制到项目并保存；请选择身份图或关联到 Look")

    def selected_ref(self):
        sel = self.ref_list.curselection()
        if not self.char or not sel: raise ValueError("请先选择一张 Reference")
        return self.char.references[sel[0]]

    def preview(self):
        if not self.ref_list.curselection(): return
        ref = self.selected_ref()
        self.preview_image = photo(self.store, ref, (210, 150))
        self.preview_label.configure(image=self.preview_image or "", text="" if self.preview_image else "图片缺失或损坏，请重新导入 Reference")

    def toggle_identity(self):
        ref = self.selected_ref()
        self.save_char()
        ids = self.char.identity_reference_ids
        ids.remove(ref.id) if ref.id in ids else ids.append(ref.id)
        self.store.save_character(self.char)
        self.render_assets()
        self.status.set("身份参考图关系已保存")

    def remove_ref(self):
        ref = self.selected_ref()
        if not messagebox.askyesno("删除 Reference 关联", "从角色及其 Look 移除此图？已有任务快照与图片文件保留。", parent=self): return
        self.save_char()
        self.char.references = [x for x in self.char.references if x.id != ref.id]
        self.char.identity_reference_ids = [x for x in self.char.identity_reference_ids if x != ref.id]
        for look in self.char.looks:
            look.reference_ids = [x for x in look.reference_ids if x != ref.id]
        self.store.save_character(self.char)
        self.render_assets()
        self.status.set("Reference 关联已删除；历史任务引用的媒体仍保留")

    def clear_look(self):
        self.look_id = None
        self.look_choice.set("")
        for v in [self.lname, self.ldesc, self.lappearance]: v.set("")
        self.look_refs.selection_clear(0, "end")

    def new_look(self):
        self.save_char()
        self.clear_look()
        self.status.set("填写新 Look 后，点击保存 Look 和角色")

    def select_look(self):
        idx = self.look_choice.current()
        if not self.char or idx < 0: return
        if not self.confirm_discard():
            self.render_assets()
            return
        look = self.char.looks[idx]
        self.look_id = look.id
        self.lname.set(look.name)
        self.ldesc.set(look.description)
        self.lappearance.set(look.appearance)
        self.render_assets()
        self.dirty = False

    def save_look(self):
        if not self.lname.get().strip(): raise ValueError("请输入 Look 名称")
        self.save_char()

    def change_shot_char(self):
        idx = self.sc.current()
        self.shot_char = self.store.character(self.chars[idx].id) if idx >= 0 else None
        self.sl["values"] = [f"{i+1}. {x.name}" for i, x in enumerate(self.shot_char.looks)] if self.shot_char else []
        self.sl.set("")
        self.mark_dirty()

    def change_shot_scene(self):
        idx = self.ss.current()
        self.shot_scene = self.store.scene(self.scenes[idx].id) if idx >= 0 else None
        self.sstate['values'] = [f"{i+1}. {s.name}" for i, s in enumerate(self.shot_scene.states)] if self.shot_scene else []
        self.sstate.set("")
        self.mark_dirty()

    def new_shot(self):
        if not self.confirm_discard(): return
        self.refresh()
        self.shot = None
        self.shot_heading.configure(text="新建 Shot · 选择角色与场景后保存")
        self.shot_detail_tabs.select(1)
        self.shot_overview.set_empty()
        for v in [self.sdesc, self.sreq, self.sgen]: v.set("")
        self.sc.set("")
        self.sl.set("")
        self.sl["values"] = []
        self.ss.set("")
        self.sstate.set("")
        self.sstate['values'] = []
        self.sexample.set(False)
        self.show_result("")
        self.dirty = False

    def show_first_frame(self):
        self.update_shot_overview()

    def update_shot_overview(self):
        data=shot_overview(self.store,self.shot)
        frame=next((b[1] for b in data.get('badges',[]) if b[0]=='首帧'),'Missing')
        self.first_frame_label.set('首帧：'+frame+'（与视频 Take 独立）')
        self.shot_overview.show(data)

    def select_shot(self):
        sel = self.shot_list.curselection()
        if not sel or not self.confirm_discard(): return
        self.shot = self.shots[sel[0]]
        self.show_first_frame()
        state = shot_state(self.shot, self.provider.executions(self.shot.id), self.provider.review(self.shot.id))
        self.shot_heading.configure(text=f"{state}  ·  {self.shot.description}")
        self.sdesc.set(self.shot.description)
        self.sreq.set(self.shot.requirements)
        self.sgen.set(self.shot.generation_description)
        self.sexample.set(self.shot.is_example)
        self.sc.current(next(i for i, c in enumerate(self.chars) if c.id == self.shot.character_id))
        self.change_shot_char()
        self.sl.current(next(i for i, x in enumerate(self.shot_char.looks) if x.id == self.shot.look_id))
        self.ss.set("")
        self.sstate.set("")
        self.sstate['values'] = []
        if self.shot.scene_id:
            self.ss.current(next(i for i, s in enumerate(self.scenes) if s.id == self.shot.scene_id))
            self.change_shot_scene()
            self.sstate.current(next(i for i, s in enumerate(self.shot_scene.states) if s.id == self.shot.scene_state_id))
        self.show_result("")
        self.dirty = False

    def save_shot(self):
        if self.sc.current() < 0 or self.sl.current() < 0: raise ValueError("请选择角色和 Look")
        char = self.store.character(self.chars[self.sc.current()].id)
        # Resolve by the displayed list's stable ID, not by a potentially stale index.
        look_id = self.shot_char.looks[self.sl.current()].id
        payload = dict(description=self.sdesc.get(), character_id=char.id, look_id=look_id,
                       requirements=self.sreq.get(), generation_description=self.sgen.get(),
                       is_example=self.sexample.get())
        if self.shot: payload["id"] = self.shot.id
        if self.ss.current() >= 0:
            if self.sstate.current() < 0: raise ValueError("请选择场景状态")
            payload.update(schema_version="0.2", scene_id=self.scenes[self.ss.current()].id,
                           scene_state_id=self.shot_scene.states[self.sstate.current()].id)
        elif not self.shot or self.shot.schema_version == "0.2":
            raise ValueError("新 Shot 必须选择场景与状态；已有 A-01 Shot 仍可原样保存")
        shot = Shot(**payload)
        self.store.save_shot(shot)
        self.shot = shot
        self.refresh()
        self.dirty = False
        self.status.set("Shot 已保存；复用角色与 Look 引用")
        self.update_shot_overview()

    def show_result(self, text):
        self.result.configure(state="normal")
        self.result.delete("1.0", "end")
        self.result.insert("1.0", text)
        self.result.configure(state="disabled")

    def generate(self):
        self.save_shot()
        task, folder = self.store.generate(self.shot.id, DummyProviderAdapter())
        self.show_result("成功：统一任务与 Dummy 模拟请求已保存。\n未调用 API，未生成视频。\n"
                         + str(folder) + "\n\n" + json.dumps(task.model_dump(), ensure_ascii=False, indent=2))
        self.status.set(f"任务验证成功 · {task.character.name} / {task.look.name} · {len(task.references)} 张参考图")

    def generate_mock(self):
        self.save_shot()
        job = self.provider.submit(self.shot.id, provider="fal" if self.provider_choice.current() == 1 else "local-mock")
        self.review_panel.refresh(shot_id=self.shot.id, job_id=job.id)
        self.tabs.select(self.review_panel)
        self.status.set(f"{job.provider} 已提交 · Take {job.take_number} · pending · 零 API 调用")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path(__file__).resolve().parents[1] / "data")
    args = parser.parse_args()
    app = App(args.data_dir)
    app.mainloop()


if __name__ == "__main__":
    main()
