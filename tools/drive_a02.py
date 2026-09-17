import sys,os,time,json
from pathlib import Path
root=Path(__file__).resolve().parents[1];p=root/'.test-tools'
sys.path[:0]=[str(p),str(p/'win32'),str(p/'win32/lib'),str(p/'Pythonwin')]
os.add_dll_directory(str(p/'pywin32_system32'))
from pywinauto import Desktop,mouse,keyboard
import win32clipboard
w=next(w for w in Desktop(backend='win32').windows() if 'A-02' in w.window_text() and 'Mock Take' not in w.window_text())
w.restore();w.set_focus();time.sleep(.4)
def metadata(key):
 for attempt in range(10):
  try:return json.loads((root/'evidence/A-02/widget-map.json').read_text(encoding='utf-8'))[key]
  except (json.JSONDecodeError,KeyError):time.sleep(.1)
 raise ValueError(key)
def rect(key):return Desktop(backend='win32').window(handle=metadata(key)['handle']).rectangle()
def click(key):
 r=rect(key);mouse.click(coords=((r.left+r.right)//2,(r.top+r.bottom)//2))
def row(key,i):
 m=metadata(key);r=rect(key);box=m['rows'][i]
 if isinstance(box,str):box=[int(x) for x in box.split()]
 x,y,bw,bh=box
 mouse.click(coords=(r.left+min(100,int(r.width()/2)),r.top+int((y+bh/2)*r.height()/m['height'])))
def paste(text):
 win32clipboard.OpenClipboard();win32clipboard.EmptyClipboard();win32clipboard.SetClipboardText(text,win32clipboard.CF_UNICODETEXT);win32clipboard.CloseClipboard();keyboard.send_keys('^v')
for a in json.loads(Path(sys.argv[1]).read_text(encoding='utf-8-sig')):
 if a[0]=='click':click(a[1])
 elif a[0]=='fill':click(a[1]);keyboard.send_keys('^a');paste(a[2])
 elif a[0]=='row':row(a[1],a[2])
 elif a[0]=='combo':
  r=rect(a[1]);mouse.click(coords=(r.right-12,(r.top+r.bottom)//2));time.sleep(.6);row('popup:'+a[1],a[2])
 elif a[0]=='xy':
  r=w.rectangle();mouse.click(coords=(r.left+a[1],r.top+a[2]))
 elif a[0]=='keys':keyboard.send_keys(a[1])
 elif a[0]=='wait':time.sleep(a[1])
 elif a[0]=='shot':w.capture_as_image().save(str(root/'evidence/A-02'/a[1]))
 elif a[0]=='file':
  d=next(d for d in Desktop(backend='win32').windows(process=w.process_id()) if d.class_name()=='#32770' and 'Reference' in d.window_text())
  edits=[c for c in d.descendants() if c.class_name()=='Edit' and c.is_visible()]
  edits[-1].set_edit_text(a[1]);d.set_focus();keyboard.send_keys('{ENTER}')
 elif a[0]=='player':
  import win32gui
  handle=0
  for attempt in range(25):
   handle=win32gui.FindWindow(None,'A-02 Mock Take '+str(a[2] if len(a)>2 else 1))
   if handle:break
   time.sleep(.1)
  if not handle:raise ValueError('Player window did not appear')
  player=Desktop(backend='win32').window(handle=handle);player.capture_as_image().save(str(root/'evidence/A-02'/a[1]))
 time.sleep(.6)
print('Desktop actions completed:',len(json.loads(Path(sys.argv[1]).read_text(encoding='utf-8-sig'))))
