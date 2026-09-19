"""Rule-based Production Truth → editable Prompt Draft. No provider or model calls."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import re

from .script import KINDS
from .workspace import now


MEDIA_NAMES = {'image': '图片', 'video': '视频', 'audio': '声音'}


def _plain(value: str) -> str:
    return re.sub(r'【([^【】]+)】', r'\1', value).strip()


def targets(workspace, shot_id, media):
    if media not in MEDIA_NAMES:
        raise ValueError('不支持的媒体类型')
    script = workspace.script
    if not script or not script.valid:
        raise ValueError('请先应用有效的 Production Script')
    for chapter in script.chapters:
        for shot in chapter.shots:
            if shot.id == shot_id:
                reqs = {r.id: r for r in script.requirements}
                choices = [(rid, f'{KINDS[reqs[rid].kind]} · {reqs[rid].name}')
                           for rid in shot.requirement_ids if reqs[rid].media == media]
                if media == 'video':
                    return [(None, f'SHOT {shot.number} · {shot.title}'), *choices]
                return choices or [(None, '镜头首帧' if media == 'image' else '镜头声音')]
    raise ValueError('当前剧本中没有此镜头')


def context(workspace, shot_id, media, requirement_id=None):
    choices = targets(workspace, shot_id, media)
    if requirement_id not in {rid for rid, _ in choices}:
        raise ValueError('目标需求不属于当前镜头或媒体类型')
    script = workspace.script
    chapter, shot = next((c, s) for c in script.chapters for s in c.shots if s.id == shot_id)
    reqs = {r.id: r for r in script.requirements}
    goal = reqs.get(requirement_id)
    rows = {r['requirement']['id']: r for r in workspace.report()}
    references, free, issues = [], [], []
    target_state = rows[requirement_id]['status'] if requirement_id else None
    relevant = [rid for rid in shot.requirement_ids if
                media == 'video' or reqs[rid].media == media]
    for rid in relevant:
        row = rows[rid]
        req = reqs[rid]
        # A missing goal is the asset to be made, rather than an invented dependency.
        if rid == requirement_id and row['status'] != 'resolved':
            if row['status'] == 'free':
                free.append(f'{KINDS[req.kind]} · {req.name}')
            continue
        if row['status'] == 'free':
            free.append(f'{KINDS[req.kind]} · {req.name}')
        elif row['status'] == 'resolved' and row['binding'] and row['asset']:
            asset = row['asset']
            references.append(dict(requirement_id=rid, kind=req.kind, name=req.name,
                                   asset_id=asset['id'], path=asset['path'],
                                   sha256=row['binding']['sha256'],
                                   candidate_id=row['binding'].get('candidate_id')))
        elif row['status'] == 'resolved':
            # A read-only report may find one matching file before a recorded auto-binding.
            # It is not a Current Binding yet and must not become a formal reference here.
            issues.append(f'{KINDS[req.kind]} · {req.name}：尚无正式绑定')
        else:
            state = {'missing': '缺失', 'unresolved': '待确认', 'changed': '已变更待确认'}[row['status']]
            issues.append(f'{KINDS[req.kind]} · {req.name}：{state}')
    facts = dict(project_id=script.project_id, project=script.title,
                 chapter_id=chapter.id, chapter=f'{chapter.number} {chapter.title}',
                 shot_id=shot.id, shot=f'{shot.number} {shot.title}', media=media,
                 requirement_id=requirement_id, target=goal.name if goal else choices[0][1],
                 target_kind=KINDS[goal.kind] if goal else '', target_state=target_state,
                 cast=[c.model_dump(exclude={'line'}) for c in shot.cast],
                 environment=shot.environment, ambience=shot.ambience,
                 sections=shot.sections, references=references, free=free, issues=issues,
                 current_shot_result=(workspace.state.get('shot_bindings', {}).get(shot_id)
                                      if media == 'video' else None))
    fingerprint = hashlib.sha256(json.dumps(facts, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()
    return dict(**facts, fingerprint=fingerprint)


def compose(facts):
    media = facts['media']
    lines = [f"{MEDIA_NAMES[media]} · {facts['target'].replace('SHOT ', '镜头 ')}"]
    if media == 'image':
        if facts['target_kind']:
            lines.append(f"制作目标：{facts['target_kind']}「{facts['target']}」的视觉素材。")
        else:
            lines.append(f"制作镜头「{facts['shot']}」的视觉首帧。")
        if facts['cast']:
            people = [f"{c['person']}" + (f"，{c['age']}" if c['age'] != '-' else '') +
                      (f"，{c['costume']}" if c['costume'] != '-' else '') for c in facts['cast']]
            lines.append('人物：' + '；'.join(people) + '。')
        if facts['environment'] and facts['environment'] != '-':
            lines.append('环境：' + facts['environment'] + '。')
        for key in ('动作', '镜头', '连续性'):
            if facts['sections'].get(key):
                lines.append(f'{key}：{_plain(facts["sections"][key])}')
    elif media == 'video':
        lines.append(f"制作正式镜头：{facts['shot']}。")
        if facts['cast']:
            lines.append('人物：' + '；'.join(
                c['person'] + (f" / {c['age']}" if c['age'] != '-' else '') +
                (f" / {c['costume']}" if c['costume'] != '-' else '') for c in facts['cast']) + '。')
        if facts['environment'] and facts['environment'] != '-':
            lines.append('场景：' + facts['environment'] + '。')
        for key in ('镜头', '动作', '表演', '对白', '连续性'):
            if facts['sections'].get(key):
                lines.append(f'{key}：{_plain(facts["sections"][key])}')
        if facts['ambience'] and facts['ambience'] != '-':
            lines.append('环境声：' + facts['ambience'] + '。')
    else:
        lines.append(f"制作镜头「{facts['shot']}」相关音声。")
        if facts['target_kind']:
            lines.append(f"音声目标：{facts['target']}。")
        voices = [f"{c['person']}：{c['voice']}" for c in facts['cast'] if c['voice'] != '-']
        if voices:
            lines.append('角色音声：' + '；'.join(voices) + '。')
        for key in ('对白', '表演'):
            if facts['sections'].get(key):
                lines.append(f'{key}：{_plain(facts["sections"][key])}')
        if facts['ambience'] and facts['ambience'] != '-':
            lines.append('环境声：' + facts['ambience'] + '。')
    if facts['free']:
        lines.append('无固定参照素材：' + '；'.join(facts['free']) + '。')
    if facts['references']:
        lines.append('参考素材：')
        lines.extend(f"· {r['name']} — {r['path']}" for r in facts['references'])
    if facts['issues']:
        lines.append('待补充参考素材（尚未提供）：')
        lines.extend(f'· {item}' for item in facts['issues'])
    return '\n\n'.join(lines)


def draft_key(shot_id, media, requirement_id=None):
    return f'{shot_id}:{media}:{requirement_id or "shot"}'


def get_draft(workspace, shot_id, media, requirement_id=None):
    facts = context(workspace, shot_id, media, requirement_id)
    record = workspace.state['prompt_drafts'].get(draft_key(shot_id, media, requirement_id))
    return deepcopy(record), facts, bool(record and record['context_fingerprint'] != facts['fingerprint'])


def create_draft(workspace, shot_id, media, requirement_id=None, *, replace=False):
    facts = context(workspace, shot_id, media, requirement_id)
    key = draft_key(shot_id, media, requirement_id)
    if key in workspace.state['prompt_drafts'] and not replace:
        raise ValueError('Draft 已存在；重建需要明确确认')
    old = workspace.state['prompt_drafts'].get(key)
    record = dict(key=key, project_id=facts['project_id'], chapter_id=facts['chapter_id'],
                  shot_id=shot_id, media=media, requirement_id=requirement_id,
                  target=facts['target'], text=compose(facts), constraints='',
                  source='deterministic', edited=False,
                  context_fingerprint=facts['fingerprint'],
                  created_at=old['created_at'] if old else now(), updated_at=now())
    before = deepcopy(workspace.state)
    try:
        workspace.state['prompt_drafts'][key] = record
        workspace._save()
    except Exception:
        workspace.state = before
        raise
    return deepcopy(record)


def save_draft(workspace, shot_id, media, requirement_id, text, constraints=''):
    key = draft_key(shot_id, media, requirement_id)
    record = workspace.state['prompt_drafts'].get(key)
    if not record:
        raise ValueError('请先创建 Prompt Draft')
    if record['project_id'] != workspace.state['project_id']:
        raise ValueError('Draft 所属项目与当前项目不一致')
    before = deepcopy(workspace.state)
    try:
        record['text'] = text
        record['constraints'] = constraints
        record['edited'] = True
        record['updated_at'] = now()
        workspace._save()
    except Exception:
        workspace.state = before
        raise
    return deepcopy(record)
