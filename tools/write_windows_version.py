"""Generate Windows PE metadata from app.version."""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.version import PRODUCT_NAME, __version__

match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)-rc\.(\d+)", __version__)
if not match:
    raise SystemExit("Unsupported release version")
parts = tuple(int(item) for item in match.groups())
target = Path(sys.argv[1])
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={parts},
    prodvers={parts},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '080404B0',
        [
          StringStruct('CompanyName', 'Local Creator Tools'),
          StringStruct('FileDescription', '{PRODUCT_NAME} Windows Portable'),
          StringStruct('FileVersion', '{__version__}'),
          StringStruct('InternalName', 'AIGCFlow'),
          StringStruct('OriginalFilename', 'AIGCFlow.exe'),
          StringStruct('ProductName', '{PRODUCT_NAME}'),
          StringStruct('ProductVersion', '{__version__}')
        ])
    ]),
    VarFileInfo([VarStruct('Translation', [2052, 1200])])
  ]
)
""", encoding="utf-8")
