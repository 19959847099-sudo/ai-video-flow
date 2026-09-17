"""Small Tk presentation widgets; no production records live here."""
import tkinter as tk
from functools import lru_cache
from tkinter import ttk
from PIL import Image, ImageOps, ImageTk

BG = '#f4f6f8'
INK = '#243342'
MUTED = '#667582'
GREEN = '#17664d'


def theme(root):
    root.configure(background=BG)
    for kind in ('Text', 'Listbox', 'Menu'):
        root.option_add(f'*{kind}.Font', ('Microsoft YaHei UI', 9))
    root.option_add('*Listbox.background', '#ffffff')
    root.option_add('*Listbox.foreground', INK)
    root.option_add('*Listbox.selectBackground', '#d5e9df')
    root.option_add('*Listbox.selectForeground', INK)
    root.option_add('*Listbox.relief', 'flat')
    root.option_add('*Listbox.borderWidth', 0)
    style = ttk.Style(root)
    style.theme_use('clam')
    style.configure('.', background=BG, foreground=INK, font=('Microsoft YaHei UI', 9))
    style.configure('TNotebook', borderwidth=0)
    style.configure('TNotebook.Tab', padding=(12, 6), background='#e5e8e2')
    style.map('TNotebook.Tab', background=[('selected', '#ffffff')], foreground=[('selected', GREEN)])
    style.configure('TButton', padding=(9, 5), borderwidth=0)
    style.configure('Primary.TButton', background=GREEN, foreground='white')
    style.map('Primary.TButton', background=[('active', '#215941'), ('disabled', '#d1d8d3')])
    style.map('TButton', foreground=[('disabled','#9ba5ad')], background=[('active','#e2e8ed')])
    style.configure('Danger.TButton', foreground='#9c3935', background='#f8efed')
    style.configure('Quiet.TButton', foreground=MUTED)
    style.configure('Nav.TFrame',background='#22313c')
    style.configure('NavSection.TLabel',background='#22313c',foreground='#acb8c0',font=('Microsoft YaHei UI',8))
    style.configure('Nav.TButton',background='#22313c',foreground='#dce4e9',anchor='w',padding=(10,3))
    style.map('Nav.TButton',background=[('active','#344956')],foreground=[('active','white')])
    style.configure('NavSelected.TButton',background='#365b57',foreground='white',anchor='w',padding=(10,3))
    style.map('NavSelected.TButton',background=[('active','#3c6860')])
    style.layout('Shell.TNotebook.Tab',[])
    style.configure('Shell.TNotebook',borderwidth=0,tabmargins=0)
    style.map('TCombobox',fieldbackground=[('readonly','white')],selectbackground=[('readonly','white')],selectforeground=[('readonly',INK)])
    style.configure('TEntry', fieldbackground='white', padding=5)
    style.configure('TCombobox', fieldbackground='white', padding=5)
    style.configure('TLabelframe', bordercolor='#dce1da', relief='solid')
    style.configure('TLabelframe.Label', foreground=MUTED)
    style.configure('Title.TLabel', font=('Microsoft YaHei UI', 15, 'bold'))
    style.configure('Heading.TLabel', font=('Microsoft YaHei UI', 12, 'bold'))
    style.configure('Muted.TLabel', foreground=MUTED)
    style.configure('Treeview', background='white', fieldbackground='white', borderwidth=0, rowheight=42)
    style.map('Treeview', background=[('selected', '#d5e9df')], foreground=[('selected', INK)])
    style.configure('Treeview.Heading', padding=7, background='#e6ebe5', relief='flat')
    style.configure('Asset.Treeview', rowheight=64)
    style.configure('Reference.Treeview', rowheight=58)
    style.configure('Shot.Treeview', rowheight=66)


def heading(parent, title, hint=None):
    ttk.Label(parent, text=title, style='Heading.TLabel').pack(anchor='w', pady=(2, 5))
    if hint:
        label = ttk.Label(parent, text=hint, style='Muted.TLabel', wraplength=400)
        label.pack(fill='x', pady=(0, 8))
        label.bind('<Configure>', lambda e: label.configure(wraplength=max(100, e.width)))


class ScrollArea(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.canvas = tk.Canvas(self, highlightthickness=0, background=BG, width=100)
        bar = ttk.Scrollbar(self, command=self.canvas.yview)
        bar.pack(side='right', fill='y')
        self.canvas.pack(fill='both', expand=True)
        self.canvas.configure(yscrollcommand=bar.set)
        self.body = ttk.Frame(self.canvas, padding=(2, 0, 12, 10))
        self.window = self.canvas.create_window(0, 0, window=self.body, anchor='nw')
        self.body.bind('<Configure>', lambda e: self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.canvas.bind('<Configure>', lambda e: self.canvas.itemconfigure(self.window, width=e.width))
        # Binding is scoped to this area, never overrides text/list scrolling elsewhere.
        self.bind_all('<MouseWheel>', self.wheel, add=True)

    def wheel(self, event):
        widget = event.widget
        if isinstance(widget, (tk.Text, tk.Listbox, ttk.Treeview, ttk.Combobox)): return
        while widget is not None:
            if widget == self:
                self.canvas.yview_scroll(-int(event.delta / 120), 'units')
                break
            widget = getattr(widget, 'master', None)


class TextValue:
    """StringVar-like interface for existing form methods, with multiline editing."""
    def __init__(self, parent, height=3):
        frame = ttk.Frame(parent)
        frame.pack(fill='x')
        self.widget = tk.Text(frame, height=height, wrap='word', width=20, undo=True,
                              relief='flat', borderwidth=0, padx=8, pady=6, background='white', foreground=INK)
        scroll = ttk.Scrollbar(frame, command=self.widget.yview)
        scroll.pack(side='right', fill='y')
        self.widget.pack(fill='x', expand=True)
        self.widget.configure(yscrollcommand=scroll.set)

    def get(self): return self.widget.get('1.0', 'end-1c')
    def set(self, value):
        self.widget.delete('1.0', 'end')
        self.widget.insert('1.0', value)


def text_field(parent, label, height=3):
    ttk.Label(parent, text=label).pack(anchor='w', pady=(8, 3))
    return TextValue(parent, height)


def readonly_text(parent, height=5):
    box = TextValue(parent, height).widget
    box.configure(state='disabled')
    return box


def put_text(widget, text):
    widget.configure(state='normal')
    widget.delete('1.0', 'end')
    widget.insert('1.0', text)
    widget.configure(state='disabled')


@lru_cache(maxsize=96)
def _thumbnail(path, mtime, size):
    with Image.open(path) as original:
        image=ImageOps.exif_transpose(original)
        image.thumbnail(size)
        return image.copy()


def photo(store, ref, size=(64, 48)):
    try:
        path=store.path(ref.path)
        return ImageTk.PhotoImage(_thumbnail(str(path),path.stat().st_mtime_ns,size))
    except (OSError, ValueError):return None


class Rows(ttk.Frame):
    """Scrollable visual rows with a small Listbox-compatible selection surface."""
    def __init__(self, parent, width=260, height=6, style='Asset.Treeview', columns=()):
        super().__init__(parent, width=width)
        self.tree = ttk.Treeview(self, show='tree headings' if columns else 'tree',
                                columns=columns, height=height, style=style, selectmode='browse')
        self.tree.column('#0', width=width, minwidth=120, stretch=True)
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=90, minwidth=65, stretch=False)
        bar = ttk.Scrollbar(self, command=self.tree.yview)
        bar.pack(side='right', fill='y')
        self.tree.pack(fill='both', expand=True)
        self.tree.configure(yscrollcommand=bar.set)
        self.images = {}
        self.empty=ttk.Label(self,text='暂无记录 · 使用新建或生成操作开始',style='Muted.TLabel',wraplength=160,justify='center')
        self.empty.place(relx=.5,rely=.45,anchor='center')

    def bind(self, event, callback, add=None):
        return self.tree.bind('<<TreeviewSelect>>' if event == '<<ListboxSelect>>' else event, callback, add)

    def delete(self, first, last=None):
        self.tree.delete(*self.tree.get_children())
        self.images.clear()
        self.empty.place(relx=.5,rely=.45,anchor='center')

    def insert(self, index, text):
        self.empty.place_forget()
        return self.tree.insert('', 'end', text=text)
    def curselection(self):
        children = self.tree.get_children()
        return tuple(children.index(i) for i in self.tree.selection() if i in children)
    def selection_set(self, index):
        children = self.tree.get_children()
        if 0 <= int(index) < len(children):
            self.tree.selection_set(children[int(index)])
            self.tree.see(children[int(index)])
    def selection_clear(self, *args): self.tree.selection_remove(*self.tree.selection())
    def size(self): return len(self.tree.get_children())
    def item(self, index, **kwargs):
        self.tree.item(self.tree.get_children()[index], **kwargs)
    def image(self, index, picture):
        if picture:
            self.images[index] = picture
            self.item(index, image=picture)


def render_refs(rows, store, asset, variants, stable_label):
    if not asset: return
    for i, ref in enumerate(asset.references):
        labels = ([stable_label] if ref.id in asset.identity_reference_ids else [])
        labels += [v.name for v in variants if ref.id in v.reference_ids]
        labels += ['生成 · FIXTURE' if getattr(ref,'source_image_result_id',None) else '导入 · '+('示例' if getattr(asset,'is_example',False) else '用户素材')]
        picture = photo(store, ref)
        rows.item(i, text=ref.name + '\n' + (' / '.join(labels) or '未分配用途') + ('' if picture else ' · 图片缺失或损坏'))
        rows.image(i, picture)


class AssetCard(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent, padding=12)
        self.cover = ttk.Label(self, text='暂无封面', anchor='center', width=14)
        self.cover.pack(side='left', padx=(0, 15))
        copy = ttk.Frame(self)
        copy.pack(fill='both', expand=True)
        self.title = ttk.Label(copy, style='Heading.TLabel')
        self.title.pack(anchor='w')
        self.info = ttk.Label(copy, style='Muted.TLabel', wraplength=400)
        self.info.pack(fill='x', pady=(5, 0))
        self.info.bind('<Configure>', lambda e: self.info.configure(wraplength=max(100, e.width)))

    def show(self, store, asset, variants, kind):
        self.picture = None
        self.title.configure(text=('[示例] ' if asset and asset.is_example else '') + (asset.name if asset else f'新建{kind}'))
        if asset:
            ref = next((r for r in asset.references if r.id in asset.identity_reference_ids), next(iter(asset.references), None))
            if ref: self.picture = photo(store, ref, (120, 88))
            identity = asset.identity[:160] + ('…' if len(asset.identity) > 160 else '')
            names = ' / '.join(v.name for v in variants)
            self.info.configure(text=identity + '\n' + f'{len(asset.references)} 张参考图 · ' + names[:140] + ('…' if len(names) > 140 else ''))
        else: self.info.configure(text=f'填写{kind}身份，导入参考图，再保存可复用的生产资产。')
        self.cover.configure(image=self.picture or '', text='' if self.picture else '暂无可用封面')


class StatusText(tk.StringVar):
    def set(self, value):
        value = ' '.join(str(value).split())
        super().set(value[:180] + ('…' if len(value) > 180 else ''))
