import sys, os
from pathlib import Path
p=Path('.test-tools').resolve()
sys.path[:0]=[str(p),str(p/'win32'),str(p/'win32/lib'),str(p/'Pythonwin')]
os.add_dll_directory(str(p/'pywin32_system32'))
from pywinauto import Desktop
for w in Desktop(backend='win32').windows():
 if 'A-01' in w.window_text():
  w.restore(); w.set_focus(); __import__("time").sleep(1)
  print(w.handle,w.window_text(),w.rectangle())
  for c in w.descendants():
   print(c.handle,repr(c.window_text()),c.class_name(),c.rectangle())
  w.capture_as_image().save('evidence/gui-initial.png')

