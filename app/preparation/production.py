"""V0.2 requirement-led production, candidate review, and explicit binding."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
from typing import Literal
from uuid import uuid4

from PIL import Image, ImageDraw, ImageFont
from pydantic import BaseModel, Field

from .script import MEDIA
from .workspace import EXTENSIONS, Workspace, now, sha


ReviewState = Literal['unreviewed', 'green', 'yellow', 'red']
SourceType = Literal['generated', 'imported']
JobStatus = Literal['queued', 'running', 'completed', 'failed']


class Candidate(BaseModel):
    id: str
    project_id: str
    requirement_id: str
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


class LocalFixtureProvider:
    """Zero-call image fixture. Its output is visibly marked as non-AI demo media."""
    name = 'local-fixture'

    def produce(self, job: ProductionJob, requirement: dict, output: Path) -> dict:
        output.parent.mkdir(parents=True, exist_ok=True)
        image = Image.new('RGB', (960, 600), '#202d3b')
        draw = ImageDraw.Draw(image)
        colors = ['#698ca0', '#988072', '#69887d', '#8c7893']
        accent = colors[int(job.id[:2], 16) % len(colors)]
        draw.rectangle((50, 50, 910, 550), outline=accent, width=2)
        draw.rectangle((50, 50, 910, 152), fill='#172330')
        draw.ellipse((515, 205, 795, 485), outline=accent, width=18)
        draw.line((114, 475, 508, 240), fill=accent, width=23)
        draw.line((245, 500, 540, 325), fill='#304d5d', width=28)
        font_path = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts' / 'msyh.ttc'
        font = ImageFont.truetype(str(font_path), 31) if font_path.exists() else ImageFont.load_default(size=31)
        small = ImageFont.truetype(str(font_path), 21) if font_path.exists() else ImageFont.load_default(size=21)
        draw.text((80, 82), 'LOCAL FIXTURE  /  NOT AI GENERATED', font=small, fill='#d6e3ea')
        draw.text((80, 209), requirement['name'][:35], font=font, fill='#edf3f6')
        draw.text((80, 257), 'PRODUCTION STUDY  ·  REVIEW REQUIRED', font=small, fill='#a9becd')
        draw.text((80, 502), f'JOB {job.id[:8]}  /  ZERO API CALLS', font=small, fill='#9cafbd')
        image.save(output)
        return {'width': image.width, 'height': image.height, 'simulation_only': True,
                'api_called': False, 'fixture': 'local-card-v0'}


class ProductionService:
    def __init__(self, workspace: Workspace):
        self.workspace = workspace
        self.providers = {'local-fixture': LocalFixtureProvider()}

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
                provider=job.provider if job else None, job_id=job.id if job else None,
                provider_metadata=provider_metadata or {},
                generation_metadata=generation_metadata or {},
                history=[{'at': stamp, 'event': 'created', 'source_type': source_type}]
            )
            self.workspace.state['candidates'][candidate.id] = candidate.model_dump()
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

    def create_job(self, requirement_id: str, shot_id: str, provider='local-fixture'):
        req, chapter, shot = self.context(requirement_id, shot_id)
        if provider not in self.providers or req.media != 'image':
            raise ValueError('当前本地 Fixture 仅支持图像；音频和视频可导入为 Candidate')
        stamp = now()
        job = ProductionJob(
            id=uuid4().hex, project_id=self.workspace.state['project_id'],
            requirement_id=req.id, chapter_id=chapter.id, shot_id=shot.id,
            media=req.media, provider=provider, status='queued', created_at=stamp,
            history=[{'at': stamp, 'status': 'queued'}],
            provider_metadata={'simulation_only': True, 'api_called': False}
        )
        before = deepcopy(self.workspace.state)
        try:
            self.workspace.state['production_jobs'][job.id] = job.model_dump()
            self.workspace._save()
        except Exception:
            self.workspace.state = before
            raise
        return job

    def job(self, job_id: str):
        value = self.workspace.state['production_jobs'].get(job_id)
        if not value:
            raise ValueError('Production Job 不存在')
        return ProductionJob.model_validate(value)

    def poll_job(self, job_id: str):
        job = self.job(job_id)
        if job.status == 'queued':
            job.status = 'running'
            job.history.append({'at': now(), 'status': 'running'})
            self.workspace.state['production_jobs'][job.id] = job.model_dump()
            self.workspace._save()
            return job
        if job.status != 'running':
            return job
        req, _, _ = self.context(job.requirement_id, job.shot_id)
        output = self.workspace.path(f'production/jobs/{job.id}/result.png')
        try:
            metadata = self.providers[job.provider].produce(job, req.model_dump(), output)
            candidate = self._ingest(job.requirement_id, job.shot_id, output, 'generated',
                                     job=job, provider_metadata=job.provider_metadata,
                                     generation_metadata=metadata)
            job.candidate_id = candidate.id
            job.status = 'completed'
            output.unlink(missing_ok=True)
        except Exception as exc:
            job.status = 'failed'
            job.error = str(exc)
        job.history.append({'at': now(), 'status': job.status,
                            **({'error': job.error} if job.error else {})})
        self.workspace.state['production_jobs'][job.id] = job.model_dump()
        self.workspace._save()
        return job

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
