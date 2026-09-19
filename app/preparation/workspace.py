"""A single atomic manifest, open media folders, explicit mappings and history."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import re
import shutil
from pathlib import Path
from uuid import uuid4

from PIL import Image

from app.core import write_json
from .script import KINDS, MEDIA, Script, parse

EXTENSIONS = {
    'image': {'.png', '.jpg', '.jpeg', '.webp', '.bmp'},
    'audio': {'.wav', '.mp3', '.m4a', '.flac', '.ogg'},
    'video': {'.mp4', '.mov', '.webm', '.mkv'},
}


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(path: Path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


class Workspace:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.manifest = self.root / 'project.json'
        if self.manifest.exists():
            self.state = json.loads(self.manifest.read_text(encoding='utf-8'))
            if self.state.get('version') != 'preparation-0.2':
                raise ValueError('不是 V0.2 准备工作区，未修改原数据')
            if self.state.get('script'):
                Script.model_validate(self.state['script'])
        else:
            self.state = dict(version='preparation-0.2', project_id=uuid4().hex,
                              draft='', script=None, assets={}, bindings={}, history=[],
                              events=[], revisions=[], ui={}, updated_at=now(),
                              candidates={}, runtime_requests={}, runtime_jobs={},
                              runtime_batches={}, unbound_requirements=[],
                              reference_decisions={}, prompt_drafts={}, shot_bindings={}, assemblies={})
            self._save()
        # Additive V0.2 production records keep existing Preparation projects readable.
        self.state.setdefault('candidates', {})
        self.state.setdefault('runtime_requests', {})
        self.state.setdefault('runtime_jobs', {})
        self.state.setdefault('runtime_batches', {})
        self.state.setdefault('unbound_requirements', [])
        self.state.setdefault('reference_decisions', {})
        self.state.setdefault('prompt_drafts', {})
        self.state.setdefault('shot_bindings', {})
        self.state.setdefault('assemblies', {})
        for kind in (*KINDS, 'shot_video'):
            (self.root / 'library' / kind).mkdir(parents=True, exist_ok=True)

    def _save(self):
        self.state['updated_at'] = now()
        write_json(self.manifest, self.state)

    def path(self, relative):
        path = (self.root / relative).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError('文件路径超出工作区')
        return path

    @property
    def script(self):
        return Script.model_validate(self.state['script']) if self.state['script'] else None

    @property
    def draft_result(self):
        return parse(self.state['draft'], self.state['project_id'])

    def save_draft(self, source):
        before = deepcopy(self.state)
        try:
            self.state['draft'] = source
            self._save()
        except Exception:
            self.state = before
            raise

    def apply(self, source):
        parsed = parse(source, self.state['project_id'])
        before = deepcopy(self.state)
        try:
            self.state['draft'] = parsed.source
            if parsed.valid:
                old = self.script
                if old and old.revision != parsed.revision:
                    old_shots = {s.id: s for c in old.chapters for s in c.shots}
                    new_shots = {s.id: s for c in parsed.chapters for s in c.shots}
                    affected = [sid for sid, shot in old_shots.items()
                                if sid not in new_shots or shot.text != new_shots[sid].text]
                    self._event('script', '剧本已更新', affected, revision=old.revision)
                self.state['script'] = parsed.model_dump()
                if not any(r['revision'] == parsed.revision for r in self.state['revisions']):
                    self.state['revisions'].append(dict(revision=parsed.revision, source=parsed.source, at=now()))
                self._resolve(record=True)
            self._save()
        except Exception:
            self.state = before
            raise
        return parsed

    def _event(self, kind, message, shots, **details):
        self.state['events'].append(dict(id=uuid4().hex, at=now(), kind=kind, message=message,
                                         shots=sorted(set(shots)), **details))

    def affected(self, asset_id):
        return sorted({u['shot_id'] for h in self.state['history'] if h['asset_id'] == asset_id for u in h['usages']})

    def _snapshot(self, path, checksum):
        target = self.path(f'.history/media/{checksum}{path.suffix.lower()}')
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            shutil.copy2(path, target)
        # Detect files changed during scanning/copying before accepting a revision.
        if sha(target) != checksum or sha(path) != checksum:
            raise ValueError(f'文件扫描过程中发生变化，请重新扫描：{path.name}')
        return target.relative_to(self.root).as_posix()

    def _inspect(self, path, kind):
        media = 'video' if kind == 'shot_video' else MEDIA[kind]
        if path.suffix.lower() not in EXTENSIONS[media]:
            return None
        name = path.relative_to(self.root / 'library' / kind).with_suffix('').as_posix()
        checksum = sha(path)
        previous = next((a for a in self.state['assets'].values() if a['path'] == path.relative_to(self.root).as_posix() and a['sha256'] == checksum and not a['problem']), None)
        if previous:
            snapshot = self._snapshot(path, checksum)
            return dict(path=path.relative_to(self.root).as_posix(), name=name, kind=kind, media=media, sha256=checksum, problem='', snapshot=snapshot)
        problem = ''
        if path.stat().st_size == 0:
            problem = '文件为空'
        elif media == 'image':
            try:
                with Image.open(path) as image:
                    image.verify()
            except (OSError, ValueError, Image.DecompressionBombError):
                problem = '图片损坏或格式不受支持'
        else:
            # Reuse the existing, validated media probe; do not invent an extension-only gate.
            from app.rough_cut import probe
            try:
                probe(path, media)
            except (ValueError, OSError, KeyError, TypeError) as exc:
                problem = f'媒体无法读取：{exc}'
        snapshot = self._snapshot(path, checksum) if not problem else None
        return dict(path=path.relative_to(self.root).as_posix(), name=name, kind=kind,
                    media=media, sha256=checksum, problem=problem, snapshot=snapshot)

    def scan(self):
        """Reconcile by path, then unique missing/new checksum pairs. Never guess a rename."""
        before = deepcopy(self.state)
        try:
            discovered = {}
            for kind in (*KINDS, 'shot_video'):
                for path in sorted((self.root / 'library' / kind).rglob('*')):
                    if not path.is_file():
                        continue
                    if not path.resolve().is_relative_to(self.root / 'library'):
                        continue
                    found = self._inspect(path, kind)
                    if found:
                        discovered[found['path']] = found
            assets = self.state['assets']
            known_paths = {a['path']: a for a in assets.values()}
            absent = [a for a in assets.values() if a['path'] not in discovered]
            new_files = [f for p, f in discovered.items() if p not in known_paths]
            for asset in absent:
                matches = [f for f in new_files if f['sha256'] == asset['sha256'] and f['kind'] == asset['kind']]
                old_matches = [a for a in absent if a['sha256'] == asset['sha256'] and a['kind'] == asset['kind']]
                if len(matches) == len(old_matches) == 1:
                    found = matches[0]
                    old_path = asset['path']
                    asset.update(path=found['path'], missing=False)
                    if found['name'] not in asset['aliases']:
                        asset['aliases'].append(found['name'])
                    new_files.remove(found)
                    known_paths[found['path']] = asset
                    self._event('rename', f'文件改名：{old_path} → {found["path"]}', self.affected(asset['id']), asset_id=asset['id'])
                elif not asset.get('missing'):
                    asset['missing'] = True
                    self._event('missing', f'文件缺失：{asset["name"]}', self.affected(asset['id']), asset_id=asset['id'])
            for found in discovered.values():
                asset = known_paths.get(found['path'])
                if asset is None:
                    aid = uuid4().hex
                    assets[aid] = dict(id=aid, **found, aliases=[found['name']], missing=False,
                                       versions=[dict(sha256=found['sha256'], snapshot=found['snapshot'], at=now())])
                    continue
                changed = found['sha256'] != asset['sha256']
                if changed:
                    asset['versions'].append(dict(sha256=found['sha256'], snapshot=found['snapshot'], at=now()))
                    self._event('replace', f'素材已替换：{asset["name"]}', self.affected(asset['id']),
                                asset_id=asset['id'], old_sha256=asset['sha256'], new_sha256=found['sha256'])
                elif asset.get('missing'):
                    self._event('restore', f'文件已恢复：{asset["name"]}', self.affected(asset['id']), asset_id=asset['id'])
                asset.update(sha256=found['sha256'], snapshot=found['snapshot'], problem=found['problem'], missing=False)
            for candidate in self.state['candidates'].values():
                asset = assets.get(candidate['asset_id'])
                if asset:
                    candidate['media_path'] = asset['path']
            report = self._resolve(record=True)
            self._save()
            return report
        except Exception:
            self.state = before
            raise

    def _remember(self, req, asset, binding):
        record = dict(revision=self.script.revision, requirement_id=req.id, asset_id=asset['id'],
                      sha256=binding['sha256'], usages=[u.model_dump() for u in req.usages])
        if record not in self.state['history']:
            self.state['history'].append(record)

    def _resolve(self, record=False):
        script = self.script
        if not script:
            return []
        rows = []
        candidate_assets = {c['asset_id'] for c in self.state['candidates'].values()}
        for req in script.requirements:
            decision = self.state['reference_decisions'].get(req.id)
            matches = [a for a in self.state['assets'].values() if a['kind'] == req.kind and
                       req.name in a['aliases'] and not a.get('missing') and a['id'] not in candidate_assets
                       and not re.fullmatch(r'take_\d{3}_[0-9a-f]{8}', a['name'])]
            binding = self.state['bindings'].get(req.id)
            if not binding and not decision and req.id not in self.state['unbound_requirements'] and len(matches) == 1 and not matches[0]['problem'] and record:
                binding = dict(asset_id=matches[0]['id'], sha256=matches[0]['sha256'], mode='auto')
                self.state['bindings'][req.id] = binding
            if decision and not binding:
                rows.append(dict(requirement=req.model_dump(), status='free',
                                 reason='已决定不需要固定素材；剧本需求仍参与后续生产',
                                 asset=None, candidates=[deepcopy(a) for a in matches], binding=None))
                continue
            asset = self.state['assets'].get(binding['asset_id']) if binding else None
            status, reason = 'missing', '素材库中还没有对应文件'
            if binding and binding['mode'] == 'auto' and len(matches) > 1:
                status, reason = 'unresolved', '同一需求有多个同名素材，请明确选择'
            elif asset:
                if asset.get('missing'):
                    status, reason = 'missing', '已绑定文件丢失；不会自动改绑其他文件'
                    possible = [a for a in self.state['assets'].values() if a['kind'] == req.kind and a['sha256'] == asset['sha256'] and not a.get('missing')]
                    if possible:
                        status, reason = 'unresolved', '存在内容相同的文件，但改名关系不唯一，请明确选择'
                        matches = list({a['id']: a for a in matches + possible}.values())
                elif asset['problem']:
                    status, reason = 'unresolved', asset['problem']
                elif asset['sha256'] != binding['sha256']:
                    status, reason = 'changed', '内容已替换，确认后才使用新版本；历史版本保留'
                else:
                    status, reason = 'resolved', ('已选用 Green Candidate' if binding['mode'] == 'candidate'
                                             else '已明确绑定' if binding['mode'] == 'manual'
                                             else '按类型与完整名称匹配')
            elif req.id in self.state['unbound_requirements']:
                status, reason = 'missing', '当前绑定已解除；请选择一个可用 Candidate 或素材'
            elif len(matches) > 1:
                status, reason = 'unresolved', '同一需求有多个同名素材，请明确选择'
            elif len(matches) == 1:
                status, reason = ('unresolved', matches[0]['problem']) if matches[0]['problem'] else ('resolved', '按类型与完整名称匹配')
                asset = matches[0]
            if binding and binding.get('candidate_id'):
                candidate = self.state['candidates'].get(binding['candidate_id'])
                if status == 'resolved' and (not candidate or candidate['review_state'] != 'green'):
                    status, reason = 'unresolved', '当前 Candidate 不再是 Green，请重新审核或更换绑定'
            if record and asset and status == 'resolved' and binding:
                self._remember(req, asset, binding)
            rows.append(dict(requirement=req.model_dump(), status=status, reason=reason,
                             asset=deepcopy(asset), candidates=[deepcopy(a) for a in matches], binding=deepcopy(binding)))
        return rows

    def report(self):
        return self._resolve()

    def set_reference_required(self, requirement_id, required):
        req = next((r for r in self.script.requirements if r.id == requirement_id), None) if self.script else None
        if not req:
            raise ValueError('当前剧本中没有此需求')
        decision = self.state['reference_decisions'].get(requirement_id)
        if required:
            if not decision:
                raise ValueError('当前需求未设置为不需要固定素材')
        elif decision or self.state['bindings'].get(requirement_id) or next(
                r for r in self.report() if r['requirement']['id'] == requirement_id)['status'] != 'missing':
            raise ValueError('仅可对未绑定的缺失需求选择不需要固定素材')
        before = deepcopy(self.state)
        try:
            if required:
                del self.state['reference_decisions'][requirement_id]
                # Explicit restoration must return to Missing, never silently auto-map.
                if requirement_id not in self.state['unbound_requirements']:
                    self.state['unbound_requirements'].append(requirement_id)
            else:
                self.state['reference_decisions'][requirement_id] = dict(
                    policy='not_required', kind=req.kind, name=req.name, at=now())
            self._event('reference_decision',
                        f'{"恢复固定素材要求" if required else "不需要固定素材"}：{req.name}',
                        [u.shot_id for u in req.usages], requirement_id=requirement_id,
                        previous='not_required' if required else 'required',
                        current='required' if required else 'not_required')
            self._save()
        except Exception:
            self.state = before
            raise

    def bind(self, requirement_id, asset_id, candidate_id=None):
        req = next((r for r in self.script.requirements if r.id == requirement_id), None) if self.script else None
        asset = self.state['assets'].get(asset_id)
        if req is None or asset is None or asset['kind'] != req.kind or asset.get('missing') or asset['problem']:
            raise ValueError('不可绑定：需求、素材类型或文件状态不匹配')
        if sha(self.path(asset['path'])) != asset['sha256']:
            raise ValueError('文件已变化，请先重新扫描')
        if not candidate_id and any(c['asset_id'] == asset_id for c in self.state['candidates'].values()):
            raise ValueError('Candidate 需先审核为 Green，再明确绑定')
        if candidate_id:
            candidate = self.state['candidates'].get(candidate_id)
            if (not candidate or candidate['requirement_id'] != requirement_id
                    or candidate['asset_id'] != asset_id or candidate['sha256'] != asset['sha256']
                    or candidate['review_state'] != 'green'):
                raise ValueError('仅可绑定当前需求下有效的 Green Candidate')
        before = deepcopy(self.state)
        try:
            old = self.state['bindings'].get(req.id)
            self.state['bindings'][req.id] = dict(asset_id=asset_id, sha256=asset['sha256'],
                                                  mode='candidate' if candidate_id else 'manual',
                                                  **({'candidate_id': candidate_id} if candidate_id else {}))
            self.state['reference_decisions'].pop(req.id, None)
            if req.id in self.state['unbound_requirements']:
                self.state['unbound_requirements'].remove(req.id)
            previous_candidate = old.get('candidate_id') if old else None
            if previous_candidate and previous_candidate != candidate_id:
                previous = self.state['candidates'].get(previous_candidate)
                if previous:
                    previous['history'].append(dict(at=now(), event='unbound',
                                                    replaced_by=candidate_id))
            if candidate_id and previous_candidate != candidate_id:
                self.state['candidates'][candidate_id]['history'].append(
                    dict(at=now(), event='bound', previous_candidate_id=previous_candidate))
            if old != self.state['bindings'][req.id]:
                self._event('binding', f'已确认新的参照：{req.name}', [u.shot_id for u in req.usages],
                            requirement_id=req.id, previous=old, current=deepcopy(self.state['bindings'][req.id]))
            self._resolve(record=True)
            self._save()
        except Exception:
            self.state = before
            raise

    def unbind_candidate(self, requirement_id):
        binding = self.state['bindings'].get(requirement_id)
        req = next((r for r in self.script.requirements if r.id == requirement_id), None) if self.script else None
        if not req or not binding or not binding.get('candidate_id'):
            raise ValueError('当前需求没有 Candidate 绑定')
        before = deepcopy(self.state)
        try:
            del self.state['bindings'][requirement_id]
            if requirement_id not in self.state['unbound_requirements']:
                self.state['unbound_requirements'].append(requirement_id)
            previous = self.state['candidates'].get(binding['candidate_id'])
            if previous:
                previous['history'].append(dict(at=now(), event='unbound', replaced_by=None))
            self._event('binding', f'已解除当前 Candidate：{req.name}',
                        [u.shot_id for u in req.usages], requirement_id=requirement_id,
                        previous=binding, current=None)
            self._save()
        except Exception:
            self.state = before
            raise

    def import_asset(self, requirement_id, filename):
        req = next((r for r in self.script.requirements if r.id == requirement_id), None) if self.script else None
        if req is None:
            raise ValueError('需求不存在，请先解析剧本')
        source = Path(filename).resolve()
        if not source.is_file() or source.suffix.lower() not in EXTENSIONS[req.media]:
            raise ValueError('文件类型与需求不匹配')
        # Never overwrite an existing asset. Name and association are system-managed.
        target = self.path(f'library/{req.kind}/{uuid4().hex[:12]}{source.suffix.lower()}')
        shutil.copy2(source, target)
        self.scan()
        asset = next(a for a in self.state['assets'].values() if a['path'] == target.relative_to(self.root).as_posix())
        if asset['problem']:
            raise ValueError(asset['problem'])
        asset['name'] = req.name
        asset['aliases'] = [req.name]
        self.bind(req.id, asset['id'])
        return asset['id']

    def set_ui(self, **values):
        before = deepcopy(self.state)
        try:
            self.state['ui'].update(values)
            self._save()
        except Exception:
            self.state = before
            raise

    def chapter_status(self, chapter_id):
        script = self.script
        chapter = next((c for c in script.chapters if c.id == chapter_id), None) if script else None
        if chapter is None:
            return dict(ready=False, resolved=0, free=0, total=0, missing=0, unresolved=0, changed=0)
        rids = {rid for shot in chapter.shots for rid in shot.requirement_ids}
        rows = [r for r in self.report() if r['requirement']['id'] in rids]
        counts = {status: sum(r['status'] == status for r in rows) for status in ('resolved', 'free', 'missing', 'unresolved', 'changed')}
        applied = self.draft_result.revision == script.revision and self.draft_result.valid
        return dict(ready=applied and all(r['status'] in ('resolved', 'free') for r in rows), total=len(rows), **counts)
