"""V0.2 requirement-led production, candidate review, and explicit binding."""
from __future__ import annotations

from copy import deepcopy
import os
from pathlib import Path
import shutil
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from .workspace import EXTENSIONS, Workspace, now, sha


ReviewState = Literal['unreviewed', 'green', 'yellow', 'red']
SourceType = Literal['generated', 'imported']
JobStatus = Literal['queued', 'running', 'completed', 'failed']


class Candidate(BaseModel):
    id: str
    project_id: str
    requirement_id: str | None
    dialogue_id: str | None = None
    background_id: str | None = None
    chapter_id: str
    shot_id: str
    kind: str
    media: Literal['image', 'audio', 'video']
    take_number: int
    media_path: str
    snapshot_path: str
    asset_id: str
    sha256: str
    created_at: str
    source_type: SourceType
    provider: str | None = None
    job_id: str | None = None
    provider_metadata: dict = Field(default_factory=dict)
    generation_metadata: dict = Field(default_factory=dict)
    review_state: ReviewState = 'unreviewed'
    note: str = ''
    history: list[dict] = Field(default_factory=list)


class ProductionJob(BaseModel):
    id: str
    project_id: str
    requirement_id: str
    chapter_id: str
    shot_id: str
    media: Literal['image', 'audio', 'video']
    provider: str
    status: JobStatus
    created_at: str
    history: list[dict] = Field(default_factory=list)
    candidate_id: str | None = None
    error: str = ''
    provider_metadata: dict = Field(default_factory=dict)



class ProductionService:
    def __init__(self, workspace: Workspace):
        self.workspace = workspace

    def context(self, requirement_id: str, shot_id: str | None = None):
        script = self.workspace.script
        if not script:
            raise ValueError('请先应用有效剧本')
        req = next((r for r in script.requirements if r.id == requirement_id), None)
        if not req:
            raise ValueError('当前剧本中没有此需求')
        chosen = shot_id or req.usages[0].shot_id
        for chapter in script.chapters:
            for shot in chapter.shots:
                if shot.id == chosen and requirement_id in shot.requirement_ids:
                    return req, chapter, shot
        raise ValueError('需求与镜头上下文不匹配')

    def candidates(self, requirement_id: str):
        return sorted((Candidate.model_validate(value) for value in self.workspace.state['candidates'].values()
                       if value['requirement_id'] == requirement_id),
                      key=lambda c: c.take_number)

    def dialogue_candidates(self, dialogue_id: str):
        return sorted((Candidate.model_validate(value) for value in self.workspace.state['candidates'].values()
                       if value.get('dialogue_id') == dialogue_id), key=lambda candidate: candidate.take_number)

    def background_candidates(self, background_id: str):
        return sorted((Candidate.model_validate(value) for value in self.workspace.state['candidates'].values()
                       if value.get('background_id') == background_id), key=lambda candidate: candidate.take_number)

    def shot_context(self, shot_id: str):
        script = self.workspace.script
        if script:
            for chapter in script.chapters:
                for shot in chapter.shots:
                    if shot.id == shot_id:
                        return chapter, shot
        raise ValueError('当前剧本中没有此镜头')

    def shot_candidates(self, shot_id: str):
        self.shot_context(shot_id)
        return sorted((Candidate.model_validate(value) for value in self.workspace.state['candidates'].values()
                       if value.get('kind') == 'shot_video' and value['shot_id'] == shot_id),
                      key=lambda candidate: candidate.take_number)

    def current_shot(self, shot_id: str):
        return self.workspace.state['shot_bindings'].get(shot_id)

    def import_shot_candidate(self, shot_id: str, source):
        return self._ingest_shot(shot_id, Path(source), 'imported')

    def _ingest_shot(self, shot_id: str, source: Path, source_type: SourceType,
                     *, job=None, provider_metadata=None, generation_metadata=None):
        chapter, shot = self.shot_context(shot_id)
        source = Path(source).resolve()
        if not source.is_file() or source.suffix.lower() not in EXTENSIONS['video']:
            raise ValueError('请选择可读取的视频文件')
        take = max((c.take_number for c in self.shot_candidates(shot_id)), default=0) + 1
        candidate_id = uuid4().hex
        target = self.workspace.path(f'library/shot_video/{shot.number}_take_{take:03d}_{candidate_id[:8]}{source.suffix.lower()}')
        partial = target.with_name(target.name + '.partial')
        before = deepcopy(self.workspace.state)
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, partial)
            os.replace(partial, target)
            checksum = sha(target)
            self.workspace.scan()
            asset = next((a for a in self.workspace.state['assets'].values()
                          if a['path'] == target.relative_to(self.workspace.root).as_posix()), None)
            if not asset or asset['problem'] or asset['sha256'] != checksum:
                raise ValueError(asset['problem'] if asset else '镜头结果入库失败')
            stamp = now()
            candidate = Candidate(
                id=candidate_id, project_id=self.workspace.state['project_id'], requirement_id=None,
                chapter_id=chapter.id, shot_id=shot.id, kind='shot_video', media='video', take_number=take,
                media_path=asset['path'], snapshot_path=asset['snapshot'], asset_id=asset['id'],
                sha256=checksum, created_at=stamp, source_type=source_type,
                provider=(getattr(job, 'provider_id', None) or getattr(job, 'provider', None)) if job else None,
                job_id=job.id if job else None, provider_metadata=provider_metadata or {},
                generation_metadata=generation_metadata or {},
                history=[{'at': stamp, 'event': 'created', 'source_type': source_type}])
            self.workspace.state['candidates'][candidate.id] = candidate.model_dump()
            self.workspace._event('candidate', f'Shot {shot.number} Take {take:02d} 已归档',
                                  [shot.id], candidate_id=candidate.id)
            self.workspace._save()
            return candidate
        except Exception:
            partial.unlink(missing_ok=True)
            target.unlink(missing_ok=True)
            self.workspace.state = before
            self.workspace._save()
            raise

    def bind_shot(self, candidate_id: str):
        candidate = self.candidate(candidate_id)
        if candidate.kind != 'shot_video' or candidate.review_state != 'green' or not self.available(candidate_id):
            raise ValueError('仅可选用仍然有效的镜头视频 Candidate')
        chapter, _ = self.shot_context(candidate.shot_id)
        if candidate.chapter_id != chapter.id or candidate.project_id != self.workspace.state['project_id']:
            raise ValueError('Candidate 与当前项目镜头不匹配')
        before = deepcopy(self.workspace.state)
        try:
            previous = self.current_shot(candidate.shot_id)
            if previous and previous != candidate.id and previous in self.workspace.state['candidates']:
                self.workspace.state['candidates'][previous]['history'].append(
                    {'at': now(), 'event': 'unbound', 'replaced_by': candidate.id})
            if previous != candidate.id:
                self.workspace.state['candidates'][candidate.id]['history'].append(
                    {'at': now(), 'event': 'bound', 'previous_candidate_id': previous})
            self.workspace.state['shot_bindings'][candidate.shot_id] = candidate.id
            self.workspace._event('shot_current', f'Shot 当前结果 → Take {candidate.take_number:02d}',
                                  [candidate.shot_id], candidate_id=candidate.id, previous=previous)
            self.workspace._save()
        except Exception:
            self.workspace.state = before
            raise
        return candidate

    def candidate(self, candidate_id: str):
        value = self.workspace.state['candidates'].get(candidate_id)
        if not value:
            raise ValueError('Candidate 不存在')
        return Candidate.model_validate(value)

    def current(self, requirement_id: str):
        return self.workspace.state['bindings'].get(requirement_id, {}).get('candidate_id')

    def available(self, candidate_id: str):
        candidate = self.candidate(candidate_id)
        asset = self.workspace.state['assets'].get(candidate.asset_id)
        if not asset or asset.get('missing') or asset['problem'] or asset['sha256'] != candidate.sha256:
            return False
        path = self.workspace.path(asset['path'])
        return path.is_file() and sha(path) == candidate.sha256

    def preview_path(self, candidate_id: str):
        candidate = self.candidate(candidate_id)
        if self.available(candidate_id):
            asset = self.workspace.state['assets'][candidate.asset_id]
            return self.workspace.path(asset['path'])
        snapshot = self.workspace.path(candidate.snapshot_path)
        return snapshot if snapshot.is_file() and sha(snapshot) == candidate.sha256 else None

    def _next_take(self, requirement_id: str):
        return max((c.take_number for c in self.candidates(requirement_id)), default=0) + 1

    def _ingest(self, requirement_id: str, shot_id: str, source: Path, source_type: SourceType,
                *, job: ProductionJob | None = None, provider_metadata=None, generation_metadata=None):
        req, chapter, shot = self.context(requirement_id, shot_id)
        source = Path(source).resolve()
        suffix = source.suffix.lower()
        if not source.is_file() or suffix not in EXTENSIONS[req.media]:
            raise ValueError('结果文件不存在或媒体类型与需求不匹配')
        candidate_id = uuid4().hex
        take = self._next_take(requirement_id)
        target = self.workspace.path(f'library/{req.kind}/take_{take:03d}_{candidate_id[:8]}{suffix}')
        partial = target.with_name(target.name + '.partial')
        before = deepcopy(self.workspace.state)
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, partial)
            os.replace(partial, target)
            checksum = sha(target)
            self.workspace.scan()
            asset = next((a for a in self.workspace.state['assets'].values()
                          if a['path'] == target.relative_to(self.workspace.root).as_posix()), None)
            if not asset or asset['problem'] or asset['sha256'] != checksum:
                raise ValueError(asset['problem'] if asset else '结果入库失败')
            stamp = now()
            candidate = Candidate(
                id=candidate_id, project_id=self.workspace.state['project_id'],
                requirement_id=req.id, chapter_id=chapter.id, shot_id=shot.id,
                kind=req.kind, media=req.media, take_number=take,
                media_path=asset['path'], snapshot_path=asset['snapshot'],
                asset_id=asset['id'], sha256=checksum, created_at=stamp, source_type=source_type,
                provider=((getattr(job, 'provider_id', None) or getattr(job, 'provider', None))
                          if job else None), job_id=job.id if job else None,
                provider_metadata=provider_metadata or {},
                generation_metadata=generation_metadata or {},
                history=[{'at': stamp, 'event': 'created', 'source_type': source_type}]
            )
            self.workspace.state['candidates'][candidate.id] = candidate.model_dump()
            if self.workspace.state['reference_decisions'].pop(req.id, None):
                # A successful import reopens the fixed-reference path; review/binding remain explicit.
                if req.id not in self.workspace.state['unbound_requirements']:
                    self.workspace.state['unbound_requirements'].append(req.id)
                self.workspace._event('reference_decision', f'恢复固定素材要求：{req.name}',
                                      [u.shot_id for u in req.usages], requirement_id=req.id,
                                      previous='not_required', current='required')
            self.workspace._event('candidate', f'Take {take:02d} 已归档：{req.name}', [shot.id],
                                  requirement_id=req.id, candidate_id=candidate.id)
            self.workspace._save()
            return candidate
        except Exception:
            partial.unlink(missing_ok=True)
            target.unlink(missing_ok=True)
            self.workspace.state = before
            self.workspace._save()
            raise

    def import_candidate(self, requirement_id: str, shot_id: str, source):
        return self._ingest(requirement_id, shot_id, Path(source), 'imported')

    def ingest_generated(self, source, job, provider_metadata=None, generation_metadata=None):
        """Merge a validated runtime output into the existing Candidate model."""
        if getattr(job, 'dialogue_id', None):
            return self.ingest_audio_target(job.shot_id, 'dialogue_audio', job.dialogue_id, source,
                                            'generated', job=job, provider_metadata=provider_metadata,
                                            generation_metadata=generation_metadata)
        if getattr(job, 'background_id', None):
            return self.ingest_audio_target(job.shot_id, 'background_audio', job.background_id, source,
                                            'generated', job=job, provider_metadata=provider_metadata,
                                            generation_metadata=generation_metadata)
        if job.requirement_id:
            return self._ingest(job.requirement_id, job.shot_id, Path(source), 'generated',
                                job=job, provider_metadata=provider_metadata,
                                generation_metadata=generation_metadata)
        return self._ingest_shot(job.shot_id, Path(source), 'generated', job=job,
                                 provider_metadata=provider_metadata,
                                 generation_metadata=generation_metadata)

    def ingest_audio_target(self, shot_id: str, target_kind: str, target_id: str, source,
                            source_type: SourceType, *, job=None, provider_metadata=None,
                            generation_metadata=None):
        if target_kind not in ('dialogue_audio', 'background_audio'):
            raise ValueError('未知声音生产目标')
        chapter, shot = self.shot_context(shot_id)
        source = Path(source).resolve()
        if not source.is_file() or source.suffix.lower() not in EXTENSIONS['audio']:
            raise ValueError('请选择可读取的音频文件')
        existing = (self.dialogue_candidates(target_id) if target_kind == 'dialogue_audio'
                    else self.background_candidates(target_id))
        take = max((item.take_number for item in existing), default=0) + 1
        candidate_id = uuid4().hex
        target = self.workspace.path(f'library/{target_kind}/{target_id}/take_{take:03d}_{candidate_id[:8]}{source.suffix.lower()}')
        partial = target.with_name(target.name + '.partial')
        before = deepcopy(self.workspace.state)
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, partial); os.replace(partial, target)
            checksum = sha(target); self.workspace.scan()
            asset = next((a for a in self.workspace.state['assets'].values()
                          if a['path'] == target.relative_to(self.workspace.root).as_posix()), None)
            if not asset or asset['problem'] or asset['sha256'] != checksum:
                raise ValueError(asset['problem'] if asset else '声音结果入库失败')
            stamp = now()
            candidate = Candidate(
                id=candidate_id, project_id=self.workspace.state['project_id'], requirement_id=None,
                dialogue_id=target_id if target_kind == 'dialogue_audio' else None,
                background_id=target_id if target_kind == 'background_audio' else None,
                chapter_id=chapter.id, shot_id=shot.id, kind=target_kind, media='audio',
                take_number=take, media_path=asset['path'], snapshot_path=asset['snapshot'],
                asset_id=asset['id'], sha256=checksum, created_at=stamp, source_type=source_type,
                provider=((getattr(job, 'provider_id', None) or getattr(job, 'provider', None)) if job else None),
                job_id=job.id if job else None, provider_metadata=provider_metadata or {},
                generation_metadata=generation_metadata or {},
                history=[{'at': stamp, 'event': 'created', 'source_type': source_type}])
            self.workspace.state['candidates'][candidate.id] = candidate.model_dump()
            self.workspace._event('candidate', f'{target_kind} Take {take:02d} 已归档', [shot.id],
                                  candidate_id=candidate.id, target_id=target_id)
            self.workspace._save(); return candidate
        except Exception:
            partial.unlink(missing_ok=True); target.unlink(missing_ok=True)
            self.workspace.state = before; self.workspace._save(); raise

    def _legacy_job(self, runtime_job):
        status = {'queued': 'queued', 'running': 'running', 'succeeded': 'completed',
                  'failed': 'failed', 'canceled': 'failed'}[runtime_job.status]
        return ProductionJob(
            id=runtime_job.id, project_id=runtime_job.project_id,
            requirement_id=runtime_job.requirement_id, chapter_id=runtime_job.chapter_id,
            shot_id=runtime_job.shot_id, media=runtime_job.media,
            provider=runtime_job.provider_id, status=status, created_at=runtime_job.created_at,
            history=deepcopy(runtime_job.history),
            candidate_id=runtime_job.candidate_ids[0] if runtime_job.candidate_ids else None,
            error=runtime_job.error,
            provider_metadata={'provider_job_id': runtime_job.provider_job_id,
                               'simulation_only': runtime_job.provider_id == 'fixture-local',
                               'api_called': False})

    def create_job(self, requirement_id: str, shot_id: str, provider='fixture-local'):
        """Compatibility facade; all execution is owned by ProductionRuntime."""
        from .runtime import ProductionRuntime
        req, _, _ = self.context(requirement_id, shot_id)
        if req.media != 'image' or provider not in ('fixture-local', 'local-fixture'):
            raise ValueError('兼容入口仅支持本地 Fixture 图像；请使用统一生成工作面')
        runtime = ProductionRuntime(self.workspace)
        request = runtime.build_request(shot_id, req.media, requirement_id, 'fixture-image-v1')
        job, _ = runtime.enqueue(request, user_intent='兼容生成入口')
        return self._legacy_job(job)

    def job(self, job_id: str):
        from .runtime import ProductionRuntime
        return self._legacy_job(ProductionRuntime(self.workspace).job(job_id))

    def poll_job(self, job_id: str):
        from .runtime import ProductionRuntime
        runtime = ProductionRuntime(self.workspace)
        job = runtime.job(job_id)
        if job.status == 'queued':
            runtime._start(job, runtime.registry.provider(job.provider_id))
        elif job.status == 'running':
            runtime._poll(job)
        return self._legacy_job(runtime.job(job_id))

    def review(self, candidate_id: str, state: ReviewState, note=''):
        if state not in ('green', 'yellow', 'red'):
            raise ValueError('审核状态必须为 Green / Yellow / Red')
        candidate = self.candidate(candidate_id)
        before = deepcopy(self.workspace.state)
        try:
            value = self.workspace.state['candidates'][candidate_id]
            old = value['review_state']
            value['review_state'] = state
            value['note'] = note.strip()
            value['history'].append({'at': now(), 'event': 'review', 'from': old,
                                     'to': state, 'note': note.strip()})
            self.workspace._event('candidate_review',
                                  f'Take {candidate.take_number:02d} → {state.upper()}',
                                  [candidate.shot_id], requirement_id=candidate.requirement_id,
                                  candidate_id=candidate_id)
            self.workspace._save()
        except Exception:
            self.workspace.state = before
            raise
        return self.candidate(candidate_id)

    def bind(self, candidate_id: str):
        candidate = self.candidate(candidate_id)
        if candidate.review_state != 'green' or not self.available(candidate_id):
            raise ValueError('仅可绑定仍然有效的 Green Candidate')
        self.context(candidate.requirement_id, candidate.shot_id)
        self.workspace.bind(candidate.requirement_id, candidate.asset_id, candidate_id=candidate.id)
        return self.workspace.report()

    def unbind(self, requirement_id: str):
        self.workspace.unbind_candidate(requirement_id)
        return self.workspace.report()
