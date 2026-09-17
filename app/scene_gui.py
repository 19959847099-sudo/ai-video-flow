"""Scene-specific editor; shares the existing Store image import and persistence."""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageOps, ImageTk
from .core import Scene, SceneState
from .workspace_ui import scene_layout
from .ui_widgets import photo, render_refs


class SceneEditor(ttk.Frame):
    def __init__(self, notebook, host):
        super().__init__(notebook, padding=12)
        self.host = host
        self.store = host.store
        self.scene = None
        self.state_id = None
        self.items = []
        scene_layout(self, host)
        self.card.show(self.store, None, [], "场景")

    def refresh(self):
        self.items = self.store.scenes()
        self.list.delete(0, "end")
        for i, s in enumerate(self.items):
            self.list.insert("end", ("[示例] " if s.is_example else "") + s.name + f"\n{len(s.states)} States · {len(s.references)} 张参考图")
            ref = next((r for r in s.references if r.id in s.identity_reference_ids), next(iter(s.references), None))
            if ref: self.list.image(i, photo(self.store, ref))

    def new(self):
        if not self.host.confirm_discard(): return
        self.scene = None
        for v in [self.name, self.description, self.identity]: v.set("")
        self.example.set(False)
        self.clear_state()
        self.render()
        self.host.dirty = False

    def choose(self):
        sel = self.list.curselection()
        if not sel or not self.host.confirm_discard(): return
        self.scene = self.store.scene(self.items[sel[0]].id)
        self.name.set(self.scene.name)
        self.description.set(self.scene.description)
        self.identity.set(self.scene.identity)
        self.example.set(self.scene.is_example)
        self.clear_state()
        self.render()
        self.host.dirty = False

    def save(self):
        payload = self.scene.model_dump() if self.scene else {}
        payload.update(name=self.name.get(), description=self.description.get(),
                       identity=self.identity.get(), is_example=self.example.get())
        scene = Scene.model_validate(payload)
        if self.state_name.get().strip():
            values = dict(name=self.state_name.get(), description=self.state_description.get(),
                          environment=self.environment.get(),
                          reference_ids=[scene.references[i].id for i in self.state_refs.curselection()])
            if self.state_id: values['id'] = self.state_id
            state = SceneState(**values)
            scene.states = [state if x.id == state.id else x for x in scene.states]
            if not any(x.id == state.id for x in scene.states): scene.states.append(state)
            self.state_id = state.id
        elif self.state_id or self.state_description.get().strip() or self.environment.get().strip():
            raise ValueError("场景状态名称不能为空")
        self.store.save_scene(scene)
        self.scene = scene
        self.host.refresh()
        self.render()
        self.host.dirty = False
        self.host.status.set("场景与状态已保存")

    def render(self):
        self.card.show(self.store, self.scene, self.scene.states if self.scene else [], "场景")
        self.refs.delete(0, "end")
        self.state_refs.delete(0, "end")
        self.picture.configure(image="", text="图片预览")
        self.photo = None
        self.choice['values'] = []
        if not self.scene: return
        state = next((s for s in self.scene.states if s.id == self.state_id), None)
        for i, ref in enumerate(self.scene.references):
            self.refs.insert("end", ("[稳定] " if ref.id in self.scene.identity_reference_ids else "") + ref.name)
            self.state_refs.insert("end", ref.name)
            if state and ref.id in state.reference_ids: self.state_refs.selection_set(i)
        self.choice['values'] = [f"{i+1}. {s.name}" for i, s in enumerate(self.scene.states)]
        if state: self.choice.current(self.scene.states.index(state))
        render_refs(self.refs, self.store, self.scene, self.scene.states, "稳定图")

    def add_refs(self):
        paths = filedialog.askopenfilenames(parent=self, title="添加场景 Reference 图片",
                    filetypes=[("图片", "*.png *.jpg *.jpeg *.webp")])
        if not paths: return
        self.save()
        for path in paths:
            ref = self.store.import_reference(path)
            if not any(r.sha256 == ref.sha256 for r in self.scene.references): self.scene.references.append(ref)
        self.store.save_scene(self.scene)
        self.render()
        self.host.status.set("场景图片已导入并保存；请选择稳定图或关联到状态")

    def selected_ref(self):
        sel = self.refs.curselection()
        if not self.scene or not sel: raise ValueError("请先选择场景图片")
        return self.scene.references[sel[0]]

    def preview(self):
        if not self.refs.curselection(): return
        ref = self.selected_ref()
        self.photo = photo(self.store, ref, (210, 150))
        self.picture.configure(image=self.photo or "", text="" if self.photo else "图片缺失或损坏，请重新导入 Reference")

    def toggle_identity(self):
        ref = self.selected_ref()
        self.save()
        ids = self.scene.identity_reference_ids
        ids.remove(ref.id) if ref.id in ids else ids.append(ref.id)
        self.store.save_scene(self.scene)
        self.render()

    def remove_ref(self):
        ref = self.selected_ref()
        if not messagebox.askyesno("移除场景图片关联", "移除此场景及状态的图片关联？历史任务与原文件保留。", parent=self): return
        self.save()
        self.scene.references = [r for r in self.scene.references if r.id != ref.id]
        self.scene.identity_reference_ids = [i for i in self.scene.identity_reference_ids if i != ref.id]
        for state in self.scene.states: state.reference_ids = [i for i in state.reference_ids if i != ref.id]
        self.store.save_scene(self.scene)
        self.render()

    def clear_state(self):
        self.state_id = None
        self.choice.set("")
        for v in [self.state_name, self.state_description, self.environment]: v.set("")
        self.state_refs.selection_clear(0, "end")

    def new_state(self):
        self.save()
        self.clear_state()

    def choose_state(self):
        idx = self.choice.current()
        if not self.scene or idx < 0: return
        if not self.host.confirm_discard():
            self.render()
            return
        state = self.scene.states[idx]
        self.state_id = state.id
        self.state_name.set(state.name)
        self.state_description.set(state.description)
        self.environment.set(state.environment)
        self.render()
        self.host.dirty = False

    def save_state(self):
        if not self.state_name.get().strip(): raise ValueError("请输入场景状态名称")
        self.save()
