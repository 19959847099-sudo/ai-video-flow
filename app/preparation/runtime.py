"""Unified V0.2 production runtime: intent, capability, execution and Candidate merge.

The runtime is deliberately provider-neutral.  Adapters receive an immutable request
snapshot and never inspect Production Script or decide review/current state.
"""
from __future__ import annotations

from copy import deepcopy
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import time
import wave
from typing import Any, Literal, Protocol
from uuid import uuid4

from PIL import Image, ImageDraw, ImageFont
from pydantic import BaseModel, Field

from app.production import media_tool
from .production import ProductionService
from .prompt import context as prompt_context, compose, get_draft
from .workspace import now

MediaType = Literal['image', 'audio', 'video']
TaskType = Literal['asset_image', 'asset_audio', 'video_reference', 'shot_video']
InputRole = Literal['reference_image', 'source_image', 'start_frame', 'end_frame',
                    'reference_video', 'source_video', 'reference_audio', 'source_audio',
                    'voice_identity', 'mask', 'style_reference', 'character_reference']
CapabilityState = Literal['NATIVE', 'TRANSLATED', 'UNSUPPORTED']
JobStatus = Literal['queued', 'running', 'succeeded', 'failed', 'canceled']


class ProductionInput(BaseModel):
    role: InputRole
    purpose: str = 'reference'
    asset_id: str
    path: str
    sha256: str


class ProductionRequest(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    project_id: str
    chapter_id: str
    shot_id: str
    requirement_id: str | None = None
    task: TaskType
    media: MediaType
    prompt: str
    constraints: str = ''
    provider_id: str
    model_id: str
    output_count: int = Field(default=1, ge=1, le=8)
    output_format: str
    aspect_ratio: str | None = None
    resolution: str | None = None
    duration: float | None = Field(default=None, gt=0)
    frame_rate: int | None = Field(default=None, gt=0)
    seed: int | None = None
    inputs: list[ProductionInput] = Field(default_factory=list)
    model_settings: dict[str, Any] = Field(default_factory=dict)
    source_context_fingerprint: str
    created_at: str = Field(default_factory=now)


class ModelManifest(BaseModel):
    id: str
    display_name: str
    provider_id: str
    tasks: set[TaskType]
    accepted_input_roles: set[InputRole] = Field(default_factory=set)
    required_input_roles: set[InputRole] = Field(default_factory=set)
    translations: dict[InputRole, InputRole] = Field(default_factory=dict)
    max_inputs: int = 8
    output_media: MediaType
    common_controls: set[str] = Field(default_factory=set)
    limits: dict[str, Any] = Field(default_factory=dict)
    model_settings: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class CapabilityReport(BaseModel):
    state: CapabilityState
    accepted: list[ProductionInput] = Field(default_factory=list)
    translated: list[ProductionInput] = Field(default_factory=list)
    unsupported: list[ProductionInput] = Field(default_factory=list)
    missing_roles: list[InputRole] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)


class RuntimeOutput(BaseModel):
    path: str
    media: MediaType
    metadata: dict[str, Any] = Field(default_factory=dict)


class RuntimeJob(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    project_id: str
    chapter_id: str
    shot_id: str
    requirement_id: str | None = None
    task: TaskType
    media: MediaType
    provider_id: str
    model_id: str
    request_id: str
    request_snapshot: dict[str, Any]
    status: JobStatus = 'queued'
    created_at: str = Field(default_factory=now)
    started_at: str | None = None
    finished_at: str | None = None
    attempt: int = 1
    retry_of: str | None = None
    provider_job_id: str | None = None
    poll_count: int = 0
    outputs: list[RuntimeOutput] = Field(default_factory=list)
    candidate_ids: list[str] = Field(default_factory=list)
    error: str = ''
    error_code: str = ''
    retryable: bool = False
    cost_metadata: dict[str, Any] = Field(default_factory=dict)
    source_context_fingerprint: str
    history: list[dict[str, Any]] = Field(default_factory=list)


class ProductionBatch(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    job_ids: list[str]
    created_at: str = Field(default_factory=now)
    user_intent: str
    source_context: dict[str, Any] = Field(default_factory=dict)
    summary: dict[str, int] = Field(default_factory=dict)


class ProviderError(RuntimeError):
    def __init__(self, message: str, code='provider_error', retryable=True):
        super().__init__(message)
        self.code = code
        self.retryable = retryable


class ProviderAdapter(Protocol):
    id: str
    display_name: str
    concurrency_limit: int
    enabled: bool
    credential_env: str | None
    def submit(self, request: ProductionRequest, job_dir: Path) -> str: ...
    def poll(self, provider_job_id: str, request: ProductionRequest, job_dir: Path,
             poll_count: int) -> tuple[str, list[RuntimeOutput]]: ...
    def download(self, output: RuntimeOutput, job_dir: Path) -> RuntimeOutput: ...
    def cancel(self, provider_job_id: str) -> None: ...
    def normalize_error(self, exc: Exception) -> ProviderError: ...


class ProviderRegistry:
    def __init__(self):
        self._providers: dict[str, ProviderAdapter] = {}
        self._models: dict[str, ModelManifest] = {}

    def register_provider(self, provider: ProviderAdapter):
        self._providers[provider.id] = provider

    def register_model(self, model: ModelManifest):
        if model.provider_id not in self._providers:
            raise ValueError(f'Provider 未注册：{model.provider_id}')
        self._models[model.id] = model

    def provider(self, provider_id: str):
        provider = self._providers.get(provider_id)
        if not provider or not provider.enabled:
            raise ValueError('生成服务不可用')
        if provider.credential_env and not os.environ.get(provider.credential_env):
            raise ValueError('生成服务尚未配置凭据')
        return provider

    def model(self, model_id: str):
        model = self._models.get(model_id)
        if not model or not model.enabled:
            raise ValueError('模型不可用')
        return model

    def models_for(self, task: TaskType, media: MediaType):
        return [m for m in self._models.values() if m.enabled and task in m.tasks and m.output_media == media]

    def provider_info(self):
        return [dict(id=p.id, display_name=p.display_name, enabled=p.enabled,
                     credentials_available=not p.credential_env or bool(os.environ.get(p.credential_env)),
                     models=[m.id for m in self._models.values() if m.provider_id == p.id])
                for p in self._providers.values()]


def match_capability(request: ProductionRequest, manifest: ModelManifest) -> CapabilityReport:
    reasons: list[str] = []
    if request.provider_id != manifest.provider_id:
        reasons.append('所选模型与生成服务不匹配')
    if request.output_count > int(manifest.limits.get('output_count', [1, 8])[-1]):
        reasons.append('输出数量超过模型上限')
    if request.task not in manifest.tasks or request.media != manifest.output_media:
        return CapabilityReport(state='UNSUPPORTED', reasons=['当前模型不支持此生产目标'])
    accepted, translated, unsupported = [], [], []
    for item in request.inputs:
        if item.role in manifest.accepted_input_roles:
            accepted.append(item)
        elif item.role in manifest.translations:
            mapped = item.model_copy(update={'role': manifest.translations[item.role]})
            translated.append(mapped)
        else:
            unsupported.append(item)
    supplied = {item.role for item in accepted + translated}
    missing = sorted(manifest.required_input_roles - supplied)
    if len(accepted) + len(translated) > manifest.max_inputs:
        reasons.append(f'参照数量超过模型上限 {manifest.max_inputs}')
    if unsupported:
        reasons.append('存在模型不能使用的参照；系统不会静默丢弃')
    if missing:
        reasons.append('缺少模型必需输入：' + '、'.join(missing))
    used_controls = {name for name in ('aspect_ratio', 'resolution', 'duration', 'frame_rate', 'seed')
                     if getattr(request, name) is not None}
    unsupported_controls = sorted(used_controls - manifest.common_controls)
    if unsupported_controls:
        reasons.append('当前模型不支持设置：' + '、'.join(unsupported_controls))
    if reasons:
        return CapabilityReport(state='UNSUPPORTED', accepted=accepted, translated=translated,
                                unsupported=unsupported, missing_roles=missing, reasons=reasons)
    state: CapabilityState = 'TRANSLATED' if translated else 'NATIVE'
    return CapabilityReport(state=state, accepted=accepted, translated=translated)


class FixtureProvider:
    """Deterministic zero-call adapter used by the same runtime contract as real providers."""
    id = 'fixture-local'
    display_name = '本地 Fixture · ZERO-CALL'
    concurrency_limit = 2
    enabled = True
    credential_env = None

    def submit(self, request: ProductionRequest, job_dir: Path) -> str:
        job_dir.mkdir(parents=True, exist_ok=True)
        return 'fixture-' + uuid4().hex

    def poll(self, provider_job_id: str, request: ProductionRequest, job_dir: Path,
             poll_count: int) -> tuple[str, list[RuntimeOutput]]:
        mode = str(request.model_settings.get('fixture_mode', 'success'))
        if mode == 'delay' and poll_count < 3:
            return 'running', []
        failures = {
            'auth': ('Fixture 模拟：凭据无效', 'auth', False),
            'timeout': ('Fixture 模拟：请求超时', 'timeout', True),
            'failure': ('Fixture 模拟：服务执行失败', 'provider_error', True),
            'download_failure': ('Fixture 模拟：结果下载失败', 'download', True),
        }
        if mode in failures:
            raise ProviderError(*failures[mode])
        outputs = []
        for index in range(request.output_count):
            suffix = {'image': '.png', 'audio': '.wav', 'video': '.mp4'}[request.media]
            path = job_dir / f'output-{index + 1:02d}{suffix}'
            if mode == 'invalid_media':
                path.write_text('invalid fixture output', encoding='utf-8')
            elif request.media == 'image':
                self._image(path, request, index)
            elif request.media == 'audio':
                self._audio(path, request, index)
            else:
                self._video(path, request, index)
            outputs.append(RuntimeOutput(path=path.as_posix(), media=request.media,
                                         metadata={'fixture': True, 'zero_call': True,
                                                   'output_index': index + 1}))
        return 'succeeded', outputs

    def download(self, output: RuntimeOutput, job_dir: Path) -> RuntimeOutput:
        # Fixture outputs already live in the job directory; remote adapters download here.
        return output

    def cancel(self, provider_job_id: str) -> None:
        return None

    def normalize_error(self, exc: Exception) -> ProviderError:
        return exc if isinstance(exc, ProviderError) else ProviderError(str(exc))

    def _font(self, size):
        path = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts' / 'msyh.ttc'
        return ImageFont.truetype(str(path), size) if path.exists() else ImageFont.load_default()

    def _card(self, request, index):
        colors = ['#6b95b8', '#8678a7', '#4f978e', '#ac7b69']
        image = Image.new('RGB', (960, 540), '#0d1826')
        draw = ImageDraw.Draw(image)
        accent = colors[index % len(colors)]
        draw.rectangle((0, 0, 960, 540), fill='#0d1826')
        draw.ellipse((560, -180, 1080, 340), fill='#142b42')
        draw.rectangle((48, 48, 912, 492), outline='#294158', width=2)
        draw.text((70, 68), 'LOCAL FIXTURE  /  ZERO-CALL', font=self._font(20), fill='#91a9bd')
        draw.text((70, 175), request.prompt[:38] or 'Production output', font=self._font(30), fill='#edf4f9')
        draw.text((70, 228), f'{request.task} · OUTPUT {index + 1:02d}', font=self._font(18), fill=accent)
        draw.text((70, 444), 'DEMO MEDIA · REVIEW REQUIRED', font=self._font(18), fill='#7f95a8')
        return image

    def _image(self, path, request, index):
        self._card(request, index).save(path)

    def _audio(self, path, request, index):
        rate, seconds, frequency = 24000, 1.25, 330 + index * 55
        with wave.open(str(path), 'wb') as stream:
            stream.setnchannels(1); stream.setsampwidth(2); stream.setframerate(rate)
            frames = bytearray()
            for n in range(int(rate * seconds)):
                envelope = min(1.0, n / 800, (rate * seconds - n) / 800)
                value = int(8000 * envelope * math.sin(2 * math.pi * frequency * n / rate))
                frames += value.to_bytes(2, 'little', signed=True)
            stream.writeframes(frames)

    def _video(self, path, request, index):
        card = path.with_suffix('.png')
        self._card(request, index).save(card)
        command = [media_tool('ffmpeg'), '-hide_banner', '-loglevel', 'error', '-nostdin', '-y',
                   '-loop', '1', '-i', str(card), '-t', str(request.duration or 1.5),
                   '-r', str(request.frame_rate or 24), '-c:v', 'libx264', '-preset', 'ultrafast',
                   '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(path)]
        try:
            result = subprocess.run(command, capture_output=True, timeout=90,
                                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            if result.returncode:
                raise ProviderError('Fixture 视频生成失败：' + result.stderr.decode(errors='replace')[-500:])
        finally:
            card.unlink(missing_ok=True)


class ProductionRuntime:
    def __init__(self, workspace, registry: ProviderRegistry | None = None):
        self.workspace = workspace
        self.production = ProductionService(workspace)
        self.registry = registry or default_registry()

    def request(self, request_id):
        value = self.workspace.state['runtime_requests'].get(request_id)
        if not value: raise ValueError('Production Request 不存在')
        return ProductionRequest.model_validate(value)

    def job(self, job_id):
        value = self.workspace.state['runtime_jobs'].get(job_id)
        if not value: raise ValueError('Production Job 不存在')
        return RuntimeJob.model_validate(value)

    def batch(self, batch_id):
        value = self.workspace.state['runtime_batches'].get(batch_id)
        if not value: raise ValueError('Production Batch 不存在')
        batch = ProductionBatch.model_validate(value)
        batch.summary = self._summary(batch.job_ids)
        return batch

    def capability(self, request: ProductionRequest):
        return match_capability(request, self.registry.model(request.model_id))

    def build_request(self, shot_id: str, media: MediaType, requirement_id: str | None,
                      model_id: str, *, output_count=1, prompt_text=None, constraints=None,
                      common=None, model_settings=None):
        facts = prompt_context(self.workspace, shot_id, media, requirement_id)
        draft, _, _ = get_draft(self.workspace, shot_id, media, requirement_id)
        if not draft:
            draft = {'text': compose(facts), 'constraints': ''}
        manifest = self.registry.model(model_id)
        if manifest.provider_id != 'fixture-local':
            self.registry.provider(manifest.provider_id)
        task: TaskType
        if requirement_id:
            req = next(r for r in self.workspace.script.requirements if r.id == requirement_id)
            task = 'video_reference' if req.kind == 'video_reference' else ('asset_audio' if media == 'audio' else 'asset_image')
        else:
            task = 'shot_video' if media == 'video' else ('asset_audio' if media == 'audio' else 'asset_image')
        role_for = {'image': 'reference_image', 'audio': 'reference_audio', 'video': 'reference_video'}
        inputs = [ProductionInput(role=role_for[next(r.media for r in self.workspace.script.requirements
                                                     if r.id == item['requirement_id'])],
                                  purpose=item['kind'], asset_id=item['asset_id'], path=item['path'],
                                  sha256=item['sha256']) for item in facts['references']]
        settings = dict(model_settings or {})
        common = common or {}
        request = ProductionRequest(
            project_id=facts['project_id'], chapter_id=facts['chapter_id'], shot_id=shot_id,
            requirement_id=requirement_id, task=task, media=media,
            prompt=prompt_text if prompt_text is not None else draft['text'],
            constraints=constraints if constraints is not None else draft['constraints'],
            provider_id=manifest.provider_id, model_id=model_id, output_count=output_count,
            output_format=common.get('output_format', {'image': 'png', 'audio': 'wav', 'video': 'mp4'}[media]),
            aspect_ratio=common.get('aspect_ratio'), resolution=common.get('resolution'),
            duration=common.get('duration'), frame_rate=common.get('frame_rate'), seed=common.get('seed'),
            inputs=inputs, model_settings=settings, source_context_fingerprint=facts['fingerprint'])
        return request

    def enqueue(self, request: ProductionRequest, *, user_intent='生成', batch_id=None):
        report = self.capability(request)
        if report.state == 'UNSUPPORTED':
            raise ValueError('；'.join(report.reasons))
        snapshot = request.model_dump(mode='json')
        job = RuntimeJob(project_id=request.project_id, chapter_id=request.chapter_id,
                         shot_id=request.shot_id, requirement_id=request.requirement_id,
                         task=request.task, media=request.media, provider_id=request.provider_id,
                         model_id=request.model_id, request_id=request.id, request_snapshot=deepcopy(snapshot),
                         source_context_fingerprint=request.source_context_fingerprint,
                         history=[{'at': now(), 'status': 'queued'}])
        self.workspace.state['runtime_requests'][request.id] = deepcopy(snapshot)
        self.workspace.state['runtime_jobs'][job.id] = job.model_dump(mode='json')
        if batch_id:
            batch = self.batch(batch_id); batch.job_ids.append(job.id)
        else:
            batch = ProductionBatch(job_ids=[job.id], user_intent=user_intent,
                                    source_context={'project_id': request.project_id,
                                                    'chapter_id': request.chapter_id,
                                                    'shot_id': request.shot_id})
        batch.summary = self._summary(batch.job_ids)
        self.workspace.state['runtime_batches'][batch.id] = batch.model_dump(mode='json')
        self.workspace._save()
        return job, batch

    def enqueue_many(self, requests: list[ProductionRequest], *, user_intent='批量生成'):
        if not requests: raise ValueError('Batch 至少需要一个任务')
        for request in requests:
            report = self.capability(request)
            if report.state == 'UNSUPPORTED':
                raise ValueError('；'.join(report.reasons))
        batch = ProductionBatch(job_ids=[], user_intent=user_intent,
                                source_context={'project_id': self.workspace.state['project_id']})
        self.workspace.state['runtime_batches'][batch.id] = batch.model_dump(mode='json')
        jobs = []
        for request in requests:
            job, batch = self.enqueue(request, user_intent=user_intent, batch_id=batch.id)
            jobs.append(job)
        return jobs, self.batch(batch.id)

    def tick(self):
        jobs = [self.job(jid) for jid in self.workspace.state['runtime_jobs']]
        running_by_provider: dict[str, int] = {}
        for job in jobs:
            if job.status == 'running': running_by_provider[job.provider_id] = running_by_provider.get(job.provider_id, 0) + 1
        for job in jobs:
            if job.status != 'queued': continue
            try:
                provider = self.registry.provider(job.provider_id)
            except Exception as exc:
                self._fail(job, ProviderError(str(exc), 'provider_config', False)); continue
            if running_by_provider.get(job.provider_id, 0) >= provider.concurrency_limit: continue
            self._start(job, provider); running_by_provider[job.provider_id] = running_by_provider.get(job.provider_id, 0) + 1
        for job in [self.job(jid) for jid in self.workspace.state['runtime_jobs']]:
            if job.status == 'running': self._poll(job)
        self._refresh_batches()
        return [self.job(jid) for jid in self.workspace.state['runtime_jobs']]

    def run_until_idle(self, max_ticks=30):
        for _ in range(max_ticks):
            jobs = self.tick()
            if all(job.status not in ('queued', 'running') for job in jobs): return jobs
            time.sleep(0.08)
        return [self.job(jid) for jid in self.workspace.state['runtime_jobs']]

    def _provider_request(self, job):
        request = ProductionRequest.model_validate(job.request_snapshot)
        report = match_capability(request, self.registry.model(job.model_id))
        if report.state == 'UNSUPPORTED':
            raise ProviderError('；'.join(report.reasons), 'capability', False)
        # Conversion is explicit and only affects the provider payload, never the saved intent.
        return request.model_copy(update={'inputs': [*report.accepted, *report.translated]})

    def _start(self, job, provider):
        request = ProductionRequest.model_validate(job.request_snapshot)
        report = match_capability(request, self.registry.model(job.model_id))
        if report.state == 'UNSUPPORTED':
            return self._fail(job, ProviderError('；'.join(report.reasons), 'capability', False))
        try:
            request = self._provider_request(job)
            job.provider_job_id = provider.submit(request, self.workspace.path(f'production/runtime/{job.id}'))
            job.status = 'running'; job.started_at = now(); job.history.append({'at': now(), 'status': 'running'})
            self._save_job(job)
        except Exception as exc:
            self._fail(job, provider.normalize_error(exc))

    def _poll(self, job):
        try:
            provider = self.registry.provider(job.provider_id)
        except Exception as exc:
            return self._fail(job, ProviderError(str(exc), 'provider_config', False))
        try:
            request = self._provider_request(job)
            job.poll_count += 1
            status, outputs = provider.poll(job.provider_job_id, request,
                                            self.workspace.path(f'production/runtime/{job.id}'), job.poll_count)
            if status == 'running':
                self._save_job(job); return
            if status != 'succeeded': raise ProviderError('Provider 返回未知状态', 'provider_state', True)
            outputs = [provider.download(item, self.workspace.path(f'production/runtime/{job.id}'))
                       for item in outputs]
            validated = [self._validate(Path(item.path), job.media) for item in outputs]
            candidates = []
            for item, metadata in zip(outputs, validated):
                candidate = self.production.ingest_generated(
                    item.path, job,
                    provider_metadata={'provider_job_id': job.provider_job_id,
                                       'fixture': job.provider_id == 'fixture-local', 'api_called': False},
                    generation_metadata={**item.metadata, **metadata, 'model_id': job.model_id,
                                         'request_id': job.request_id,
                                         'context_fingerprint': job.source_context_fingerprint})
                candidates.append(candidate.id)
            portable = []
            for item in outputs:
                path = Path(item.path).resolve()
                stored = path.relative_to(self.workspace.root).as_posix() if path.is_relative_to(self.workspace.root) else path.as_posix()
                portable.append(item.model_copy(update={'path': stored}))
            job.outputs = portable; job.candidate_ids = candidates; job.status = 'succeeded'
            job.finished_at = now(); job.cost_metadata = {'currency': None, 'amount': 0}
            job.history.append({'at': now(), 'status': 'succeeded', 'candidate_ids': candidates})
            self._save_job(job)
        except Exception as exc:
            self._fail(job, provider.normalize_error(exc))

    def _validate(self, path: Path, media: MediaType):
        if not path.is_file(): raise ProviderError('结果文件不存在', 'download', True)
        if media == 'image':
            try:
                with Image.open(path) as image:
                    image.verify(); width, height = image.size
                if width < 1 or height < 1: raise ValueError
                return {'width': width, 'height': height}
            except Exception: raise ProviderError('生成结果不是有效图片', 'invalid_media', True)
        command = [media_tool('ffprobe'), '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)]
        result = subprocess.run(command, capture_output=True, timeout=45,
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        try: data = json.loads(result.stdout or b'{}')
        except Exception: data = {}
        streams = data.get('streams', [])
        wanted = 'audio' if media == 'audio' else 'video'
        if result.returncode or not any(s.get('codec_type') == wanted for s in streams):
            raise ProviderError(f'生成结果不包含有效{media}', 'invalid_media', True)
        duration = float(data.get('format', {}).get('duration') or 0)
        if duration <= 0: raise ProviderError('生成结果缺少有效时长', 'invalid_media', True)
        return {'duration': duration, 'codec': next(s.get('codec_name') for s in streams if s.get('codec_type') == wanted)}

    def cancel(self, job_id):
        job = self.job(job_id)
        if job.status not in ('queued', 'running'): return job
        if job.status == 'running' and job.provider_job_id:
            try: self.registry.provider(job.provider_id).cancel(job.provider_job_id)
            except Exception: pass
        job.status = 'canceled'; job.finished_at = now(); job.history.append({'at': now(), 'status': 'canceled'})
        self._save_job(job); self._refresh_batches(); return job

    def retry(self, job_id, *, model_settings=None):
        old = self.job(job_id)
        if old.status not in ('failed', 'canceled'): raise ValueError('仅失败或已取消任务可重试')
        request = ProductionRequest.model_validate(deepcopy(old.request_snapshot))
        request.id = uuid4().hex; request.created_at = now()
        if model_settings is not None:
            request.model_settings = deepcopy(model_settings)
        job, batch = self.enqueue(request, user_intent='重试')
        job.attempt = old.attempt + 1; job.retry_of = old.id
        job.history[0]['retry_of'] = old.id; self._save_job(job)
        return job, batch

    def reconcile(self):
        """Persisted fixture jobs resume; unrecoverable providers become explicit failures."""
        for job_id in list(self.workspace.state['runtime_jobs']):
            job = self.job(job_id)
            if job.status == 'running':
                if job.provider_id in self.registry._providers and job.provider_job_id:
                    try:
                        self._poll(job)
                    except Exception as exc:
                        self._fail(job, ProviderError(str(exc), 'reconcile', True))
                else:
                    self._fail(job, ProviderError('应用重启后无法恢复 Provider 状态，请重试', 'reconcile', True))
        self._refresh_batches()

    def _fail(self, job, error: ProviderError):
        job.status = 'failed'; job.finished_at = now(); job.error = str(error)
        job.error_code = error.code; job.retryable = error.retryable
        job.history.append({'at': now(), 'status': 'failed', 'code': error.code, 'error': str(error)})
        self._save_job(job); return job

    def _save_job(self, job):
        self.workspace.state['runtime_jobs'][job.id] = job.model_dump(mode='json')
        self.workspace._save()

    def _summary(self, job_ids):
        summary = {key: 0 for key in ('queued', 'running', 'succeeded', 'failed', 'canceled')}
        for job_id in job_ids:
            value = self.workspace.state['runtime_jobs'].get(job_id)
            if value: summary[value['status']] += 1
        return summary

    def _refresh_batches(self):
        for batch_id, value in list(self.workspace.state['runtime_batches'].items()):
            batch = ProductionBatch.model_validate(value); batch.summary = self._summary(batch.job_ids)
            self.workspace.state['runtime_batches'][batch_id] = batch.model_dump(mode='json')
        self.workspace._save()


def default_registry():
    registry = ProviderRegistry(); registry.register_provider(FixtureProvider())
    all_refs = {'reference_image', 'source_image', 'start_frame', 'end_frame', 'reference_video',
                'source_video', 'reference_audio', 'source_audio', 'voice_identity',
                'style_reference', 'character_reference'}
    registry.register_model(ModelManifest(
        id='fixture-image-v1', display_name='Fixture Image · 本地零调用', provider_id='fixture-local',
        tasks={'asset_image'}, accepted_input_roles=all_refs - {'reference_video', 'source_video', 'source_image'},
        translations={'source_image': 'reference_image'}, output_media='image', common_controls={'output_count', 'aspect_ratio', 'resolution', 'seed'},
        limits={'output_count': [1, 8]}))
    registry.register_model(ModelManifest(
        id='fixture-audio-v1', display_name='Fixture Audio · 本地零调用', provider_id='fixture-local',
        tasks={'asset_audio'}, accepted_input_roles={'reference_audio', 'source_audio', 'voice_identity'},
        output_media='audio', common_controls={'output_count', 'duration', 'seed'}))
    registry.register_model(ModelManifest(
        id='fixture-video-v1', display_name='Fixture Video · 本地零调用', provider_id='fixture-local',
        tasks={'video_reference', 'shot_video'}, accepted_input_roles=all_refs,
        output_media='video', common_controls={'output_count', 'aspect_ratio', 'resolution', 'duration', 'frame_rate', 'seed'}))
    registry.register_model(ModelManifest(
        id='fixture-video-text-v1', display_name='Fixture Video · 仅文本', provider_id='fixture-local',
        tasks={'video_reference', 'shot_video'}, accepted_input_roles=set(), output_media='video',
        common_controls={'output_count', 'duration'}))
    return registry
