"""Derive, verify and fetch the corresponding source for the bundled FFmpeg build."""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIN_PATH = ROOT / "third_party" / "ffmpeg" / "FFMPEG_PIN.json"
MANIFEST_PATH = ROOT / "third_party" / "ffmpeg" / "SOURCE_MANIFEST.json"
CACHE_DIR = ROOT / ".tools" / "ffmpeg-provenance"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_pin() -> dict:
    return json.loads(PIN_PATH.read_text(encoding="utf-8"))


def http_get(url: str, dest: Path, attempts: int = 4) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    partial = dest.with_suffix(dest.suffix + ".part")
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "ai-video-flow-source-manifest"})
            with urllib.request.urlopen(request, timeout=300) as response:
                with partial.open("wb") as stream:
                    shutil.copyfileobj(response, stream, 1024 * 1024)
            partial.replace(dest)
            return dest
        except Exception as error:  # noqa: BLE001 - retried, then reported
            last_error = error
            if attempt < attempts:
                time.sleep(2 * attempt)
    raise RuntimeError(f"GET {url} failed after {attempts} attempts: {last_error}")


def fetch_recipe(pin: dict) -> Path:
    """Return an extracted copy of the vendor build recipe at the pinned commit."""
    commit = pin["vendor_recipe_commit"]
    target = CACHE_DIR / f"recipe-{commit}"
    if (target / "scripts.d").is_dir():
        return target
    owner, repo = pin["vendor"].split("/")
    archive = CACHE_DIR / f"{repo}-{commit}.tar.gz"
    if not archive.is_file():
        http_get(f"https://codeload.github.com/{owner}/{repo}/tar.gz/{commit}", archive)
    staged = CACHE_DIR / f".extract-{commit}"
    if staged.exists():
        shutil.rmtree(staged)
    staged.mkdir(parents=True)
    with tarfile.open(archive, "r:gz") as tar:
        tar.extractall(staged, filter="data")
    extracted = next(p for p in staged.iterdir() if (p / "scripts.d").is_dir())
    extracted.replace(target)
    shutil.rmtree(staged, ignore_errors=True)
    return target


def _function_body(text: str, name: str) -> list[str]:
    match = re.search(rf"^{name}\(\)\s*\{{\n(.*?)^\}}", text, re.M | re.S)
    return match.group(1).splitlines() if match else []


def _flags(body: list[str]) -> list[str]:
    return re.findall(r"--\S+", "\n".join(line for line in body if line.strip().startswith("echo ")))


def _stage_key(script: Path, root: Path) -> str:
    """Mirror the vendor's own stage naming: a directory is one stage."""
    anchor = script.stem if script.parent == root else script.parent.name
    return re.sub(r"^\d+-", "", anchor)


def parse_scripts(recipe: Path) -> tuple[dict[str, dict], list[str]]:
    root = recipe.joinpath("scripts.d")
    packages: dict[str, dict] = {}
    conditional: list[str] = []
    for path in sorted(root.rglob("*.sh")):
        text = path.read_text(encoding="utf-8", errors="replace")
        name = _stage_key(path, root)
        record = packages.setdefault(name, {"package": name, "sources": [], "configure_flags": [], "depends": []})
        repo = re.search(r'^SCRIPT_REPO="([^"]+)"', text, re.M)
        if repo:
            commit = re.search(r'^SCRIPT_COMMIT="([^"]+)"', text, re.M)
            revision = re.search(r'^SCRIPT_REV="([^"]+)"', text, re.M)
            branch = re.search(r'^SCRIPT_BRANCH="([^"]+)"', text, re.M)
            record["sources"].append({
                "script": path.relative_to(recipe).as_posix(),
                "repository": repo.group(1),
                "revision": commit.group(1) if commit else (revision.group(1) if revision else (branch.group(1) if branch else "")),
                "revision_kind": "git-commit" if commit else ("svn-revision" if revision else "git-branch"),
            })
        for line in _function_body(text, "ffbuild_depends"):
            stripped = line.strip()
            if stripped.startswith("echo ") and "&&" not in stripped:
                record["depends"].append(stripped.split(None, 1)[1])
            elif "&& echo " in stripped:
                conditional.append(f"{path.name}: {stripped}")
        record["configure_flags"] += _flags(_function_body(text, "ffbuild_configure"))
    for record in packages.values():
        for key in ("depends", "configure_flags"):
            record[key] = sorted(set(record[key]))
    return packages, conditional


def observe_configure(ffmpeg_exe: Path) -> str:
    output = subprocess.run(
        [str(ffmpeg_exe), "-version"], capture_output=True, text=True, check=True
    ).stdout
    for line in output.splitlines():
        if line.startswith("configuration:"):
            return line.split(":", 1)[1].strip()
    raise RuntimeError(f"No configuration line reported by {ffmpeg_exe}")


def resolve_closure(packages: dict[str, dict], configure_line: str) -> tuple[list[str], list[str], list[str]]:
    flags = set(configure_line.split())
    enabled = {name for name, rec in packages.items() if rec["configure_flags"] and flags & set(rec["configure_flags"])}
    required: set[str] = set()
    frontier = list(enabled)
    while frontier:
        current = frontier.pop()
        for dep in packages.get(current, {}).get("depends", []):
            if dep not in required:
                required.add(dep)
                frontier.append(dep)
    unclaimed = sorted(
        flag
        for flag in flags
        if flag.startswith("--enable-lib") and not any(flag in rec["configure_flags"] for rec in packages.values())
    )
    # A stage can be pulled in as a dependency yet be disabled by the vendor for
    # this target. Keeping those makes the manifest over-cover rather than
    # under-cover, so they are reported instead of silently dropped.
    conservative = sorted(
        name
        for name in required - enabled
        if any(f"--disable-{f.removeprefix('--enable-')}" in flags for f in packages[name]["configure_flags"])
    )
    return sorted(enabled | required), unclaimed, conservative


def archive_url(source: dict) -> str | None:
    repo, revision = source["repository"], source["revision"]
    if source["revision_kind"] == "git-branch":
        return None
    if source["revision_kind"] == "git-commit":
        match = re.match(r"https://([^/]+)/(.+?)(?:\.git)?/?$", repo)
        if not match:
            return None
        host, path = match.group(1), match.group(2)
        if host == "github.com":
            owner, project = path.split("/", 1)
            return f"https://codeload.github.com/{owner}/{project}/tar.gz/{revision}"
        if host in {"code.videolan.org", "gitlab.freedesktop.org", "gitlab.com"}:
            return f"https://{host}/{path}/-/archive/{revision}/{path.split('/')[-1]}-{revision}.tar.gz"
        if host.endswith("googlesource.com"):
            return f"https://{host}/{path}/+archive/{revision}.tar.gz"
    return None


def build_manifest(pin: dict, ffmpeg_exe: Path) -> dict:
    recipe = fetch_recipe(pin)
    packages, conditional = parse_scripts(recipe)
    configure_line = observe_configure(ffmpeg_exe)
    closure, unclaimed, conservative = resolve_closure(packages, configure_line)
    components = []
    for name in closure:
        record = packages[name]
        sources = []
        for source in record["sources"]:
            entry = dict(source)
            entry["source_archive"] = archive_url(source)
            sources.append(entry)
        components.append({
            "package": name,
            "configure_flags": record["configure_flags"],
            "depends": record["depends"],
            "sources": sources,
            "build_input_only": not sources,
        })
    owner, repo = pin["vendor"].split("/")
    owner, repo = pin["vendor"].split("/")
    return {
        "schema": 1,
        "generated_from": {
            "vendor_pin": "third_party/ffmpeg/FFMPEG_PIN.json",
            "vendor_recipe_commit": pin["vendor_recipe_commit"],
            "observed_configure_line": configure_line,
        },
        "build_recipe": {
            "package": "ffmpeg-builds",
            "role": "scripts, package pins and patches that control the build",
            "repository": f"https://github.com/{owner}/{repo}",
            "revision": pin["vendor_recipe_commit"],
            "revision_kind": "git-commit",
            "source_archive": f"https://codeload.github.com/{owner}/{repo}/tar.gz/{pin['vendor_recipe_commit']}",
            "patch_directories": ["patches/aom", "patches/aribb24"],
            "vendor_release_tag": pin["vendor_release_tag"],
            "vendor_ci_run": pin["vendor_ci_run"],
        },
        "build_recipe": {
            "package": "ffmpeg-builds",
            "role": "scripts, package pins and patches used to control the build",
            "repository": f"https://github.com/{owner}/{repo}",
            "revision": pin["vendor_recipe_commit"],
            "revision_kind": "git-commit",
            "source_archive": f"https://codeload.github.com/{owner}/{repo}/tar.gz/{pin['vendor_recipe_commit']}",
            "patches": ["patches/aom", "patches/aribb24"],
            "vendor_release_tag": pin["vendor_release_tag"],
            "vendor_ci_run": pin["vendor_ci_run"],
        },
        "primary_work": {
            "package": "ffmpeg",
            "repository": pin["upstream"]["repository"],
            "revision": pin["upstream"]["commit"],
            "revision_kind": "git-commit",
            "release_tarball": pin["upstream"]["release_tarball"],
            "version_string": pin["upstream"]["version_string"],
        },
        "component_count": len(components),
        "components": components,
        "unclaimed_enable_lib_flags": unclaimed,
        "conservatively_included_stages": conservative,
        "conditional_dependency_declarations": conditional,
    }


def git_archive(repository: str, revision: str, dest: Path) -> Path:
    """Fetch a revision from a host that exposes no HTTP snapshot endpoint.

    Prefers a single-commit fetch; falls back to a bare clone because not every
    server allows fetching an arbitrary SHA.
    """
    workspace = CACHE_DIR / "git-archive"
    workspace.mkdir(parents=True, exist_ok=True)
    bare = workspace / f"{dest.stem}.git"
    if bare.exists():
        shutil.rmtree(bare)
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(["git", "init", "--bare", "--quiet", str(bare)], check=True, timeout=120)
        subprocess.run(["git", "--git-dir", str(bare), "remote", "add", "origin", repository], check=True, timeout=120)
        shallow = subprocess.run(
            ["git", "--git-dir", str(bare), "fetch", "--depth", "1", "--no-tags", "--quiet", "origin", revision],
            capture_output=True, text=True, timeout=3600,
        )
        if shallow.returncode:
            subprocess.run(
                ["git", "--git-dir", str(bare), "fetch", "--no-tags", "--quiet", "origin", "HEAD:refs/heads/provenance"],
                check=True, capture_output=True, text=True, timeout=5400,
            )
        subprocess.run(
            ["git", "--git-dir", str(bare), "archive", "--format=tar.gz", f"--output={dest}", revision],
            check=True, capture_output=True, text=True, timeout=3600,
        )
    finally:
        shutil.rmtree(bare, ignore_errors=True)
    return dest


def fetch_sources(manifest: dict, output: Path) -> dict:
    index = []
    recipe = manifest["build_recipe"]
    primary = manifest["primary_work"]
    entries = [
        (recipe["package"], recipe["source_archive"], None),
        (primary["package"], primary["release_tarball"], None),
    ]
    seen: dict[str, int] = {}
    for component in manifest["components"]:
        for source in component["sources"]:
            package = component["package"]
            revision = re.sub(r"[^A-Za-z0-9.]+", "-", source["revision"][:10]).strip("-.")
            slug = revision if revision.lower().startswith(package.lower()) else f"{package}-{revision}"
            seen[slug] = seen.get(slug, 0) + 1
            if seen[slug] > 1:
                slug = f"{slug}-{seen[slug]}"
            entries.append((slug, source["source_archive"], source))
    for name, url, source in entries:
        dest = output / "sources" / f"{name}.tar.gz"
        cached = dest.is_file() and dest.stat().st_size > 0
        try:
            if cached:
                pass
            elif url:
                http_get(url, dest)
            elif source and source["revision_kind"] == "git-commit":
                git_archive(source["repository"], source["revision"], dest)
            else:
                index.append({
                    "package": name,
                    "status": "vcs-retrieval-required",
                    "repository": (source or {}).get("repository"),
                    "revision": (source or {}).get("revision"),
                    "revision_kind": (source or {}).get("revision_kind"),
                    "retrieval": f"svn export -r {(source or {}).get('revision')} {(source or {}).get('repository')}",
                })
                continue
            index.append({
                "package": name,
                "status": "fetched",
                "archive": f"sources/{name}.tar.gz",
                "url": url or source["repository"],
                "method": "cached" if cached else ("http-snapshot" if url else "git-archive"),
                "bytes": dest.stat().st_size,
                "sha256": sha256(dest),
            })
        except Exception as error:  # noqa: BLE001 - recorded and reported, not swallowed
            index.append({"package": name, "status": "failed", "url": url, "error": str(error)})
    (output / "FETCH_INDEX.json").write_text(
        json.dumps(index, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    fetched = [item for item in index if item["status"] == "fetched"]
    lines = "".join(f"{item['sha256']}  {item['archive']}\n" for item in fetched)
    (output / "SHA256SUMS.txt").write_text(lines, encoding="utf-8", newline="\n")
    return {
        "fetched": len(fetched),
        "total": len(index),
        "bytes": sum(item["bytes"] for item in fetched),
        "outstanding": [item for item in index if item["status"] != "fetched"],
    }


def verify_binaries(pin: dict, ffmpeg_exe: Path, ffprobe_exe: Path) -> dict:
    expected = {item["path"].split("/")[-1]: item for item in pin["bundled_files"]}
    result = {}
    for name, path in (("ffmpeg.exe", ffmpeg_exe), ("ffprobe.exe", ffprobe_exe)):
        record = expected[name]
        digest = sha256(path)
        result[name] = {
            "expected_sha256": record["sha256"],
            "actual_sha256": digest,
            "expected_bytes": record["size_bytes"],
            "actual_bytes": path.stat().st_size,
            "match": digest == record["sha256"] and path.stat().st_size == record["size_bytes"],
        }
    return result


def main(argv: list[str]) -> int:
    command = argv[1] if len(argv) > 1 else "manifest"
    pin = load_pin()
    if command == "verify":
        ffmpeg_exe, ffprobe_exe = Path(argv[2]), Path(argv[3])
        result = verify_binaries(pin, ffmpeg_exe, ffprobe_exe)
        print(json.dumps(result, indent=2))
        return 0 if all(item["match"] for item in result.values()) else 1
    if command == "manifest":
        ffmpeg_exe = Path(argv[2]) if len(argv) > 2 else ROOT / "dist" / "AIVideoFlow" / "_internal" / "runtime" / "ffmpeg" / "bin" / "ffmpeg.exe"
        manifest = build_manifest(pin, ffmpeg_exe)
        MANIFEST_PATH.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
        )
        print(f"components={manifest['component_count']} unclaimed={len(manifest['unclaimed_enable_lib_flags'])}")
        if manifest["unclaimed_enable_lib_flags"]:
            print("UNCLAIMED:", " ".join(manifest["unclaimed_enable_lib_flags"]))
            print("A shipped --enable-lib* flag is not attributable to a pinned recipe stage.")
            return 1
        if manifest["conservatively_included_stages"]:
            print("note, over-covered stages:", " ".join(manifest["conservatively_included_stages"]))
        return 0
    if command == "fetch":
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        output = Path(argv[2])
        print(json.dumps(fetch_sources(manifest, output), indent=2))
        return 0
    raise SystemExit("Usage: ffmpeg_provenance.py [verify|manifest|fetch] [args]")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
