"""Record portable archive size and checksum without committing the artifact."""
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.version import __version__

archive = Path(sys.argv[1]).resolve()
target = Path(sys.argv[2]).resolve()
digest = hashlib.sha256()
with archive.open("rb") as stream:
    for block in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(block)
payload = {
    "schema": 1,
    "version": __version__,
    "archive": archive.name,
    "bytes": archive.stat().st_size,
    "sha256": digest.hexdigest(),
}
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(json.dumps(payload, indent=2))
