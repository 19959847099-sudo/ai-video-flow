"""Run the unchanged App with read-only widget metadata for desktop acceptance."""
import sys,json
from pathlib import Path
import tkinter as tk
from tkinter import ttk
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.gui import App
from app.ui_widgets import Rows, TextValue
root=Path(__file__).resolve().parents[1]
import socket
network_attempts=[]
def blocked(*args, **kwargs):
 network_attempts.append('blocked socket connection')
 raise RuntimeError('A-05 GUI acceptance forbids networking')
socket.socket.connect=blocked
socket.socket.connect_ex=blocked
socket.create_connection=blocked
app=App(Path(sys.argv[1]) if len(sys.argv)>1 else root/'evidence/A-05/gui-data')
def dump():
 if app.closing:return
 widgets={}
 def info(w):
  d={'handle':w.winfo_id(),'width':w.winfo_width(),'height':w.winfo_height()}
  if isinstance(w,tk.Listbox):d['rows']=[w.bbox(i) for i in range(w.size())]
  if isinstance(w,ttk.Treeview):d['rows']=[w.bbox(i) for i in w.get_children()]
  if isinstance(w,ttk.Notebook):
   d['tab_points']={}
   for x in range(5,w.winfo_width(),5):
    for y in range(5,min(65,w.winfo_height()),5):
     try:
      idx=str(w.index('@%d,%d'%(x,y)))
      if idx not in d['tab_points']:d['tab_points'][idx]=[x+12,y+10]
     except tk.TclError:pass
  return d
 def walk(w):
  widgets[str(w)]=info(w)
  if isinstance(w,ttk.Button):widgets['button:'+w.cget('text')]=info(w)
  if isinstance(w,ttk.Checkbutton):widgets['check:'+str(w)]=info(w)
  for child in w.winfo_children():walk(child)
 walk(app)
 for prefix,obj in [('app',app),('scene',app.scene_editor),('review',app.review_panel)]:
  for name,value in vars(obj).items():
   key=prefix+'.'+name
   if isinstance(value, Rows):value=value.tree
   elif isinstance(value, TextValue):value=value.widget
   if isinstance(value,tk.Widget):
    widgets[key]=info(value)
    if isinstance(value,ttk.Combobox):
     pop=str(app.tk.call('ttk::combobox::PopdownWindow',str(value)))+'.f.l'
     if int(app.tk.call('winfo','exists',pop)):
      size=int(app.tk.call(pop,'size'))
      widgets['popup:'+key]={'handle':int(str(app.tk.call('winfo','id',pop)),0),'width':int(app.tk.call('winfo','width',pop)),'height':int(app.tk.call('winfo','height',pop)),'rows':[app.tk.call(pop,'bbox',i) for i in range(size)]}
   elif isinstance(value,tk.Variable):
    for path in list(widgets):
     if not path.startswith('.') or 'popup' in path:continue
     try:
      widget=app.nametowidget(path)
      if str(widget.cget('textvariable'))==str(value) or str(widget.cget('variable'))==str(value):widgets[key]=info(widget)
     except tk.TclError:pass
 (root/'evidence/A-05/widget-map.json').write_text(json.dumps(widgets),encoding='utf-8')
 app.after(350,dump)
app.after(350,dump)
app.mainloop()
(root/'evidence/A-05/gui-network-audit.json').write_text(json.dumps({'socket_connection_attempts':network_attempts,'api_calls':0}),encoding='utf-8')
