import sys,os,time,json
from pathlib import Path
root=Path(__file__).resolve().parents[1];p=root/'.test-tools'
sys.path[:0]=[str(p),str(p/'win32'),str(p/'win32/lib'),str(p/'Pythonwin')]
os.add_dll_directory(str(p/'pywin32_system32'))
from pywinauto import Desktop,mouse,keyboard
import win32clipboard
w=next(w for w in Desktop(backend='win32').windows() if ('UI-Final' in w.window_text() or 'A-08 生产工作台' in w.window_text()) and 'Mock Take' not in w.window_text())
w.restore();w.set_focus();time.sleep(.4)
def metadata(key):
 for attempt in range(10):
  try:return json.loads((root/'evidence/UI-Final/widget-map.json').read_text(encoding='utf-8'))[key]
  except (json.JSONDecodeError,KeyError):time.sleep(.1)
 raise ValueError(key)
def rect(key):return Desktop(backend='win32').window(handle=metadata(key)['handle']).rectangle()
def click(key):
 for attempt in range(100):
  m=metadata(key)
  if m.get('mapped',True) and 'disabled' not in m.get('state',[]):break
  time.sleep(.2)
 else:raise ValueError('Control not ready: '+key)
 r=rect(key);mouse.click(coords=((r.left+r.right)//2,(r.top+r.bottom)//2))
def row(key,i):
 for attempt in range(30):
  m=metadata(key)
  box=m['rows'][i] if i<len(m.get('rows',[])) else []
  if m.get('mapped',True) and box:break
  time.sleep(.2)
 else:raise ValueError('Row is not visible: '+key+' '+str(i))
 r=rect(key)
 if isinstance(box,str):box=[int(x) for x in box.split()]
 x,y,bw,bh=box
 mouse.click(coords=(r.left+min(100,int(r.width()/2)),r.top+int((y+bh/2)*r.height()/m['height'])))
def paste(text):
 win32clipboard.OpenClipboard();win32clipboard.EmptyClipboard();win32clipboard.SetClipboardText(text,win32clipboard.CF_UNICODETEXT);win32clipboard.CloseClipboard();keyboard.send_keys('^v')
for a in json.loads(Path(sys.argv[1]).read_text(encoding='utf-8-sig')):
 print(time.strftime('%H:%M:%S'),a,flush=True)
 if a[0]=='mark':pass
 elif a[0]=='click':click(a[1])
 elif a[0]=='fill':click(a[1]);keyboard.send_keys('^a');paste(a[2])
 elif a[0]=='row':row(a[1],a[2])
 elif a[0]=='combo':
  r=rect(a[1]);mouse.click(coords=(r.right-12,(r.top+r.bottom)//2));time.sleep(.6);row('popup:'+a[1],a[2])
 elif a[0]=='xy':
  r=w.rectangle();mouse.click(coords=(r.left+a[1],r.top+a[2]))
 elif a[0]=='keys':keyboard.send_keys(a[1])
 elif a[0]=='close':w.close()
 elif a[0]=='maximize':w.maximize()
 elif a[0]=='audit':
  from datetime import datetime
  record={'time':datetime.now().isoformat(),'window':[w.rectangle().left,w.rectangle().top,w.rectangle().right,w.rectangle().bottom],'widgets':json.loads((root/'evidence/UI-Final/widget-map.json').read_text(encoding='utf-8'))}
  (root/'evidence/UI-Final'/a[1]).write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
 elif a[0]=='resize':w.move_window(x=20,y=20,width=a[1],height=a[2],repaint=True)
 elif a[0]=='tab':
  r=rect(a[1]);m=metadata(a[1]);x,y=m['tab_points'][str(a[2])];mouse.click(coords=(r.left+int(x*r.width()/m['width']),r.top+int(y*r.height()/m['height'])));time.sleep(.3)
 elif a[0]=='scroll':
  r=rect(a[1]);mouse.scroll(coords=(r.right-8,(r.top+r.bottom)//2),wheel_dist=a[2])
 elif a[0]=='wait':time.sleep(a[1])
 elif a[0]=='shot':w.capture_as_image().save(str(root/'evidence/UI-Final'/a[1]))
 elif a[0]=='file':
  d=next(d for d in Desktop(backend='win32').windows(process=w.process_id()) if d.class_name()=='#32770' and ('Reference' in d.window_text() or '图片' in d.window_text() or '音频' in d.window_text()))
  for attempt in range(40):
   edits=[c for c in d.descendants() if c.class_name()=='Edit' and c.is_visible()]
   if edits:break
   time.sleep(.15)
  edits[-1].set_edit_text(a[1]);next(c for c in d.descendants() if c.class_name()=='Button' and c.control_id()==1).click_input()
 elif a[0]=='rough_player':
  import win32gui
  handle=0
  for attempt in range(25):
   handle=win32gui.FindWindow(None,'A-08 ROUGH CUT PREVIEW')
   if handle:break
   time.sleep(.1)
  if not handle:raise ValueError('Rough Cut player window did not appear')
  time.sleep(.5);Desktop(backend='win32').window(handle=handle).capture_as_image().save(str(root/'evidence/UI-Final'/a[1]))
 elif a[0]=='audio_player':
  import win32gui
  handle=0
  for attempt in range(25):
   handle=win32gui.FindWindow(None,'A-07 FIXTURE Audio')
   if handle:break
   time.sleep(.1)
  if not handle:raise ValueError('Audio player window did not appear')
  Desktop(backend='win32').window(handle=handle).capture_as_image().save(str(root/'evidence/UI-Final'/a[1]))
 elif a[0]=='player':
  import win32gui
  handle=0
  for attempt in range(25):
   handle=win32gui.FindWindow(None,'fal Fixture Take '+str(a[2] if len(a)>2 else 1))
   if handle:break
   time.sleep(.1)
  if not handle:raise ValueError('Player window did not appear')
  time.sleep(.6);player=Desktop(backend='win32').window(handle=handle);player.capture_as_image().save(str(root/'evidence/UI-Final'/a[1]))
 time.sleep(1.0)
print('Desktop actions completed:',len(json.loads(Path(sys.argv[1]).read_text(encoding='utf-8-sig'))))
