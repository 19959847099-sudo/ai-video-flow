"""Validate the two Windows release artifacts and write deterministic checksums."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.version import __version__


def artifact_names(version: str = __version__) -> tuple[str, str]:
    stem = f"AI-Video-Flow-{version}-windows-x64"
    return f"{stem}.zip", f"{stem}-setup.exe"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def create_manifest(release: Path, evidence: Path) -> dict:
    release = release.resolve()
    if release.name != f"v{__version__}":
        raise ValueError(f"Release directory must be v{__version__}")
    artifacts = []
    for name in artifact_names():
        path = release / name
        if not path.is_file() or path.stat().st_size == 0:
            raise FileNotFoundError(f"Missing or empty release artifact: {path}")
        artifacts.append({"name": name, "bytes": path.stat().st_size, "sha256": sha256(path)})
    sums = "".join(f"{item['sha256']}  {item['name']}\n" for item in artifacts)
    checksum_path = release / "SHA256SUMS.txt"
    temporary = checksum_path.with_suffix(".tmp")
    temporary.write_text(sums, encoding="ascii")
    temporary.replace(checksum_path)
    result = {"schema": 1, "version": __version__, "artifacts": artifacts}
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Usage: release_manifest.py RELEASE_DIR EVIDENCE_JSON")
    print(json.dumps(create_manifest(Path(sys.argv[1]), Path(sys.argv[2])), indent=2))
