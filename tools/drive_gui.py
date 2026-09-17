import sys,os,time,json
from pathlib import Path
p=Path(__file__).resolve().parents[1]/'.test-tools'
sys.path[:0]=[str(p),str(p/'win32'),str(p/'win32/lib'),str(p/'Pythonwin')]
os.add_dll_directory(str(p/'pywin32_system32'))
from pywinauto import Desktop,mouse,keyboard
w=next(w for w in Desktop(backend='win32').windows() if 'A-01' in w.window_text())
w.restore();w.set_focus();time.sleep(.3)
r=w.rectangle()
for a in json.loads(Path(sys.argv[1]).read_text(encoding='utf-8-sig')):
 if a[0]=='click': mouse.click(coords=(r.left+a[1],r.top+a[2]))
 elif a[0]=='text':
  import win32clipboard
  win32clipboard.OpenClipboard(); win32clipboard.EmptyClipboard(); win32clipboard.SetClipboardText(a[1],win32clipboard.CF_UNICODETEXT); win32clipboard.CloseClipboard(); keyboard.send_keys('^v')
 elif a[0]=='keys': keyboard.send_keys(a[1])
 elif a[0]=='wait': time.sleep(a[1])
 elif a[0]=='shot': w.capture_as_image().save(a[1])
 elif a[0]=='file':
  d=next(d for d in Desktop(backend='win32').windows(process=w.process_id()) if d.class_name()=='#32770' and 'Reference' in d.window_text())
  edits=[c for c in d.descendants() if c.class_name()=='Edit' and c.is_visible()]
  print([(e.handle,e.rectangle()) for e in edits])
  edits[-1].set_edit_text(a[1])
  d.set_focus(); keyboard.send_keys('{ENTER}')
 elif a[0]=='windows':
  for d in Desktop(backend='win32').windows(process=w.process_id()):
   print(repr(d.window_text()),d.class_name(),d.rectangle())
   if d.class_name()=='#32770': print([(c.class_name(),c.window_text()) for c in d.descendants()])
 time.sleep(.25)
