"""Neutral image tasks and local image truth. No workflow/node/provider in tasks."""
from datetime import datetime, timezone
import hashlib
import json
from typing import Literal
from PIL import Image
from pydantic import Field, model_validator
from .core import Record, Character, Look, Scene, SceneState, Shot, Reference, FirstFrame, new_id, write_json

Purpose = Literal['CHARACTER_REFERENCE', 'SCENE_REFERENCE', 'SHOT_FIRST_FRAME']

class ImageTask(Record):
    schema_version: Literal['0.1'] = '0.1'
    id: str = Field(default_factory=new_id)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    kind: Literal['image'] = 'image'
    purpose: Purpose
    character: Character | None = None
    look: Look | None = None
    references: list[Reference] = Field(default_factory=list)
    scene: Scene | None = None
    scene_state: SceneState | None = None
    scene_references: list[Reference] = Field(default_factory=list)
    shot: Shot | None = None
    description: str = Field(min_length=1)
    final_prompt: str = Field(min_length=1)
    width: int = Field(default=768, ge=256, le=2048, multiple_of=8)
    height: int = Field(default=512, ge=256, le=2048, multiple_of=8)
    seed: int = Field(default=1, ge=0, le=2**53-1)
    is_example: bool = True
    retry_of: str | None = None

    @model_validator(mode='after')
    def relations(self):
        needs_char = self.purpose != 'SCENE_REFERENCE'
        needs_scene = self.purpose != 'CHARACTER_REFERENCE'
        if needs_char != bool(self.character) or needs_scene != bool(self.scene):
            raise ValueError('图像用途与资产上下文不匹配')
        for asset, variant, refs in [(self.character,self.look,self.references),(self.scene,self.scene_state,self.scene_references)]:
            if asset:
                variants = asset.looks if isinstance(asset,Character) else asset.states
                if variant is None or variant not in variants: raise ValueError('图像变体快照不匹配')
                ids=set(asset.identity_reference_ids+variant.reference_ids)
                if refs != [r for r in asset.references if r.id in ids]: raise ValueError('图像参考图快照不匹配')
            elif variant or refs: raise ValueError('图像资产上下文不完整')
        if self.purpose == 'SHOT_FIRST_FRAME':
            if not self.shot or (self.shot.character_id,self.shot.look_id,self.shot.scene_id,self.shot.scene_state_id) != (self.character.id,self.look.id,self.scene.id,self.scene_state.id):
                raise ValueError('首帧 Shot 与资产不匹配')
        elif self.shot: raise ValueError('Reference 任务不能绑定 Shot')
        return self

class ImageExecution(Record):
    id: str = Field(default_factory=new_id)
    task_id: str
    provider: Literal['comfyui'] = 'comfyui'
    simulation_only: Literal[True] = True
    status: Literal['pending','processing','completed','failed'] = 'pending'
    history: list[str] = Field(default_factory=lambda:['pending'])
    prompt_id: str | None = None
    step: int = 0
    result_id: str | None = None
    error: str = ''
    task_sha256: str
    workflow_sha256: str

class ImageResult(Record):
    id: str
    task_id: str
    execution_id: str
    purpose: Purpose
    path: str
    sha256: str
    width: int
    height: int
    simulation_only: Literal[True] = True

class ImageReview(Record):
    result_id: str
    rejected: bool = False
    reason: str = ''
    promotion: Literal['identity','variant','first_frame'] | None = None
    reference_id: str | None = None


def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()

class ImageProduction:
    def __init__(self,store): self.store=store
    def folder(self,task_id):
        self.store.record_path('image_tasks',task_id)
        return self.store.path(f'image_tasks/{task_id}')
    def task(self,identifier): return ImageTask.model_validate_json((self.folder(identifier)/'task.json').read_text(encoding='utf-8'))
    def job(self,identifier): return ImageExecution.model_validate_json(self.store.record_path('image_executions',identifier).read_text(encoding='utf-8'))
    def jobs(self):
        items=[ImageExecution.model_validate_json(p.read_text(encoding='utf-8')) for p in self.store.path('image_executions').glob('*.json')]
        return sorted(items,key=lambda j:self.task(j.task_id).created_at)
    def review(self,identifier):
        p=self.store.record_path('image_reviews',identifier)
        return ImageReview.model_validate_json(p.read_text(encoding='utf-8')) if p.exists() else ImageReview(result_id=identifier)
    def save_job(self,job): write_json(self.store.record_path('image_executions',job.id),job.model_dump())

    def build(self,purpose,asset_id,variant_id=None,description=None):
        payload=dict(purpose=purpose)
        if purpose=='SHOT_FIRST_FRAME':
            t=self.store.task(asset_id, include_first_frame=False)
            if not t.scene: raise ValueError('首帧任务需要场景和状态')
            payload.update(shot=t.shot,character=t.character,look=t.look,references=t.references,scene=t.scene,scene_state=t.scene_state,scene_references=t.scene_references)
            description=description or t.shot.generation_description
        elif purpose=='CHARACTER_REFERENCE':
            c=self.store.character(asset_id); look=next((x for x in c.looks if x.id==variant_id),None)
            if not look: raise ValueError('请先选择并保存 Look')
            ids=set(c.identity_reference_ids+look.reference_ids)
            payload.update(character=c,look=look,references=[r for r in c.references if r.id in ids])
        elif purpose=='SCENE_REFERENCE':
            s=self.store.scene(asset_id); state=next((x for x in s.states if x.id==variant_id),None)
            if not state: raise ValueError('请先选择并保存场景 State')
            ids=set(s.identity_reference_ids+state.reference_ids)
            payload.update(scene=s,scene_state=state,scene_references=[r for r in s.references if r.id in ids])
        else: raise ValueError('未知图像用途')
        description=description or '生成用于人工审核的参考图'
        lines=[f'Purpose: {purpose}']
        for key in ('character','look','scene','scene_state','shot'):
            obj=payload.get(key)
            if obj:
                values=obj.model_dump()
                lines.append(key+': '+ ' | '.join(str(values[k]) for k in ('name','identity','description','appearance','environment','requirements') if values.get(k)))
        refs=payload.get('references',[])+payload.get('scene_references',[])
        for r in refs:
            if digest(self.store.path(r.path))!=r.sha256: raise ValueError('参考图哈希不匹配')
        lines.append('Generation description: '+description)
        return ImageTask(**payload,description=description,final_prompt='\n'.join(lines),is_example=any(getattr(payload.get(k),'is_example',False) for k in ('character','scene','shot')))

    def submit(self,purpose,asset_id,variant_id=None,description=None,retry_of=None):
        task=self.build(purpose,asset_id,variant_id,description)
        if retry_of:
            _,old=self.trace(retry_of)
            def target(t): return (t.purpose,t.character.id if t.character else None,t.look.id if t.look else None,t.scene.id if t.scene else None,t.scene_state.id if t.scene_state else None,t.shot.id if t.shot else None)
            if not self.review(retry_of).rejected or target(task)!=target(old): raise ValueError('Retry 必须来自同一用途/资产/变体的已 Reject 结果')
            task.retry_of=retry_of
        from .comfy_adapter import WorkflowBuilder
        folder=self.folder(task.id)
        folder.mkdir(parents=True)
        workflow=WorkflowBuilder().prepare(task,self.store,folder)
        write_json(folder/'task.json',task.model_dump());write_json(folder/'workflow.json',workflow)
        job=ImageExecution(task_id=task.id,task_sha256=digest(folder/'task.json'),workflow_sha256=digest(folder/'workflow.json'))
        self.save_job(job)
        return job

    def poll(self,identifier):
        from .comfy_adapter import ComfyAdapter, FixtureTransport
        job=self.job(identifier)
        if job.status in ('completed','failed'): return job
        folder=self.folder(job.task_id)
        exchange_path=folder/'exchange.json'
        events=json.loads(exchange_path.read_text(encoding='utf-8')) if exchange_path.exists() else []
        try:
            if digest(folder/'task.json')!=job.task_sha256 or digest(folder/'workflow.json')!=job.workflow_sha256: raise ValueError('图像任务 / Workflow 快照已被修改')
            task=self.task(job.task_id);workflow=json.loads((folder/'workflow.json').read_text(encoding='utf-8'))
            adapter=ComfyAdapter(FixtureTransport(job.id,task,workflow,self.store))
            if job.step==0:
                job.prompt_id=adapter.submit(workflow,events)
            else:
                state,raw=adapter.poll(job.prompt_id,job.step,events)
                job.status=state
                if raw is not None:
                    result=self.ingest(job,task,raw)
                    job.result_id=result.id;job.status='completed'
            job.step+=1
        except Exception as exc: job.status='failed';job.error=str(exc)
        if job.history[-1]!=job.status:job.history.append(job.status)
        write_json(exchange_path,events);self.save_job(job)
        return job

    def ingest(self,job,task,raw):
        from io import BytesIO
        with Image.open(BytesIO(raw)) as im:
            if im.format!='PNG': raise ValueError('Fixture 输出必须是 PNG')
            im.load();width,height=im.size
        if (width,height)!=(task.width,task.height):raise ValueError('图像输出尺寸不匹配')
        path=f'image_results/{job.id}/image.png';file=self.store.path(path);file.parent.mkdir(parents=True,exist_ok=True);file.write_bytes(raw)
        result=ImageResult(id=job.id,execution_id=job.id,task_id=task.id,purpose=task.purpose,path=path,sha256=digest(file),width=width,height=height)
        write_json(file.parent/'result.json',result.model_dump());return result

    def trace(self,identifier):
        self.store.record_path('image_results',identifier)
        result=ImageResult.model_validate_json(self.store.path(f'image_results/{identifier}/result.json').read_text(encoding='utf-8'))
        job=self.job(result.execution_id);task=self.task(result.task_id);folder=self.folder(task.id)
        if (result.id!=identifier or job.result_id!=result.id or job.task_id!=task.id or job.status!='completed' or result.purpose!=task.purpose):raise ValueError('图像结果关联不匹配')
        if digest(folder/'task.json')!=job.task_sha256 or digest(folder/'workflow.json')!=job.workflow_sha256 or digest(self.store.path(result.path))!=result.sha256:raise ValueError('图像 / 任务 / Workflow 哈希不匹配')
        return result,task

    def reject(self,identifier,reason=''):
        self.trace(identifier);review=self.review(identifier)
        if review.promotion:raise ValueError('已采纳结果不能 Reject；可以另选候选首帧')
        review.rejected=True;review.reason=reason;write_json(self.store.record_path('image_reviews',identifier),review.model_dump())

    def retry(self,identifier,description):
        _,task=self.trace(identifier)
        if task.shot:target,variant=task.shot.id,None
        elif task.character:target,variant=task.character.id,task.look.id
        else:target,variant=task.scene.id,task.scene_state.id
        return self.submit(task.purpose,target,variant,description,retry_of=identifier)

    def promote(self,identifier,destination):
        result,task=self.trace(identifier);review=self.review(identifier)
        if review.rejected:raise ValueError('Reject 结果不能采纳')
        if review.promotion:
            if review.promotion!=destination:raise ValueError('此结果已按另一用途采纳')
            if destination!='first_frame': return review
        if task.shot:
            if destination!='first_frame':raise ValueError('首帧只能关联原 Shot')
            current=Shot.model_validate_json(self.store.record_path('shots',task.shot.id).read_text(encoding='utf-8'))
            if (current.character_id,current.look_id,current.scene_id,current.scene_state_id)!=(task.shot.character_id,task.shot.look_id,task.shot.scene_id,task.shot.scene_state_id):raise ValueError('Shot 已更换资产，请重新生成首帧')
            frame=FirstFrame(result_id=result.id,task_id=task.id,shot_id=task.shot.id,path=result.path,sha256=result.sha256)
            write_json(self.store.record_path('first_frames',task.shot.id),frame.model_dump())
        else:
            if destination not in ('identity','variant'):raise ValueError('请选择稳定 Reference 或当前变体 Reference')
            asset=self.store.character(task.character.id) if task.character else self.store.scene(task.scene.id)
            variants=asset.looks if task.character else asset.states;vid=task.look.id if task.look else task.scene_state.id
            variant=next((v for v in variants if v.id==vid),None)
            if not variant:raise ValueError('原 Look / State 已不存在')
            ref=next((r for r in asset.references if r.sha256==result.sha256),None)
            if ref is None:
                ref=self.store.import_reference(self.store.path(result.path));ref.name='FIXTURE '+task.purpose+' '+result.id[:8];ref.source_image_result_id=result.id;asset.references.append(ref)
            ids=asset.identity_reference_ids if destination=='identity' else variant.reference_ids
            if ref.id not in ids:ids.append(ref.id)
            (self.store.save_character if task.character else self.store.save_scene)(asset)
            review.reference_id=ref.id
        review.promotion=destination
        write_json(self.store.record_path('image_reviews',identifier),review.model_dump());return review
