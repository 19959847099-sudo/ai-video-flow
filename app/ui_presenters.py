"""Read-only UI projections. No extra persistent status machine."""
import json
from pathlib import Path


def take_state(job, review):
    if job.result_id and job.result_id == review.selected_result_id: return 'SELECTED', 'selected'
    if job.result_id and job.result_id in review.rejected: return 'REJECTED', 'rejected'
    return {'completed':('待审核', 'ready'), 'pending':('排队中', 'pending'),
            'processing':('生成中', 'pending'), 'failed':('执行失败', 'failed')}[job.status]


def shot_state(shot, jobs, review):
    if review.selected_result_id: return '已选定'
    if any(j.status in ('pending', 'processing') for j in jobs): return '生成中'
    if any(j.result_id and j.result_id not in review.rejected for j in jobs): return '待审核'
    if any(j.result_id in review.rejected for j in jobs): return '可重试'
    if any(j.status == 'failed' for j in jobs): return '执行失败'
    return '可生成' if shot.scene_id else '待补场景'


def mode(job):
    if not job.simulation_only: return 'REAL'
    return 'ZERO-CALL' if job.provider == 'fal' else 'MOCK'


def harness_summary(root, job):
    """Only match explicit IDs; missing sidecar never blocks production access."""
    candidates = [Path(root)/'evidence/A-04/production-run/trace.json']
    candidates += sorted((Path(root)/'evidence/A-04/runs').glob('*/trace.json'))
    for path in candidates:
        try:
            trace = json.loads(path.read_text(encoding='utf-8'))
            result = trace.get('result', {})
            if (result.get('execution_id'), result.get('task_id'), trace.get('shot_id')) != (job.id, job.task_id, job.shot_id): continue
            lines = [f"DSH {trace.get('version', '')} · 历史执行 {trace.get('status', '未知')}"]
            names = {'get_shot_context':'读取 Shot', 'build_generation_task':'构建生成任务',
                     'dry_run_generation':'Kling O3 Dry Run / 结果入库', 'inspect_media':'ffprobe 媒体探测'}
            for step in trace.get('steps', []):
                lines.append(('✓ ' if step.get('status') == 'completed' else '· ') + names.get(step.get('tool'), '工具') + ' · ' + step.get('status', '未知'))
            lines.append('这是历史记录，不表示 DSH 当前正在运行。')
            return '\n'.join(lines), str(path)
        except (OSError, ValueError, TypeError, AttributeError): continue
    return '没有匹配的 Harness 记录。此结果可独立读取和审核，无需启动 DSH。', None

def shot_overview(store,shot):
    """Read-only compact projection; no ffprobe, media scan, or production writes."""
    if shot is None:return dict(empty=True)
    from .audio_production import AudioProduction
    from .fal_adapter import ProductionRunner
    from .rough_cut import RoughCutProduction
    audio=AudioProduction(store);video=ProductionRunner(store)
    try:
        character=store.character(shot.character_id);look=next(x for x in character.looks if x.id==shot.look_id)
        scene=store.scene(shot.scene_id) if shot.scene_id else None
        state=next((x for x in scene.states if x.id==shot.scene_state_id),None) if scene else None
        dialogues=audio.dialogues(shot.id);selected_audio=[audio.review(d.id).selected_result_id for d in dialogues]
        selected_count=sum(bool(x) for x in selected_audio);aligned=0
        for rid in selected_audio:
            if rid:
                p=store.record_path('alignments',rid)
                if p.exists():
                    v=json.loads(p.read_text(encoding='utf-8'))
                    if v.get('audio_result_id')==rid and store.path(v['subtitle_path']).is_file():aligned+=1
        review=video.review(shot.id);jobs=video.executions(shot.id);selected=next((j for j in jobs if j.result_id==review.selected_result_id and j.result_id),None)
        frame=store.record_path('first_frames',shot.id);has_frame=frame.exists()
        if has_frame:
            binding=json.loads(frame.read_text(encoding='utf-8'));has_frame=bool(binding.get('result_id'))
        frame_state='selected' if has_frame else 'missing'
        if has_frame:
            from .image_production import ImageProduction
            snapshot=ImageProduction(store).task(binding['task_id']).shot
            fields=('id','character_id','look_id','scene_id','scene_state_id')
            if snapshot is None or any(getattr(snapshot,f)!=getattr(shot,f) for f in fields):frame_state='stale'
            elif not store.path(binding['path']).is_file():frame_state='blocked'
        timelines=[x for x in RoughCutProduction(store).definitions() if shot.id in x.shot_ids]
        try:voice=audio.default_voice(character.id).name
        except ValueError:voice='尚未设置默认声音'
        badges=[('Reference',f'{len(character.references)+(len(scene.references) if scene else 0)} 张','ready'),('首帧',frame_state.title(),frame_state),('视频',f'Take {selected.take_number} · Selected' if selected else shot_state(shot,jobs,review),'selected' if selected else 'pending'),('音频',f'{selected_count}/{len(dialogues)} Selected','selected' if dialogues and selected_count==len(dialogues) else 'missing'),('字幕',f'{aligned} Ready','ready' if aligned else 'missing'),('Timeline',f'已列入 {len(timelines)} 条','ready' if timelines else 'missing')]
        return dict(empty=False,title=shot.description,who=character.name+' / '+look.name,where=(scene.name+' / '+state.name) if scene and state else 'Missing · 尚未选择场景',voice=voice,requirements=shot.requirements,dialogues=len(dialogues),badges=badges,details=dict(shot=shot.model_dump(),selected_video=review.selected_result_id,selected_audio=selected_audio,first_frame=json.loads(frame.read_text(encoding='utf-8')) if frame.exists() else None,timelines=[x.id for x in timelines]))
    except (ValueError,OSError,KeyError,StopIteration) as exc:return dict(empty=False,error=str(exc),badges=[('数据','Blocked','blocked')])
