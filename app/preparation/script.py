"""Finite, context-aware V0.2 script grammar. No model calls or guessed fields."""
from __future__ import annotations

import hashlib
import re
from uuid import UUID, uuid5
from pydantic import BaseModel, Field


KINDS = {
    'character': '人物视觉', 'age': '年龄状态', 'costume': '服装',
    'character_visual': '完整角色', 'environment': '环境参照',
    'prop': '关键物件', 'voice': '人物音声', 'background_audio': '环境声音',
    'video_reference': '镜头参照',
}
MEDIA = {kind: ('audio' if kind in ('voice', 'background_audio') else 'video' if kind == 'video_reference' else 'image') for kind in KINDS}
SECTIONS = {'镜头', '动作', '表演', '对白', '连续性', '备注'}


class Diagnostic(BaseModel):
    line: int
    column: int = 1
    message: str
    code: str


class Usage(BaseModel):
    chapter_id: str
    shot_id: str
    line: int


class Requirement(BaseModel):
    id: str
    kind: str
    name: str
    media: str
    usages: list[Usage] = Field(default_factory=list)


class Cast(BaseModel):
    person: str
    age: str
    costume: str
    voice: str
    complete_visual: str | None = None
    line: int


class DialogueLine(BaseModel):
    id: str
    speaker: str
    text: str
    order: int
    line: int
    source_fingerprint: str
    voice_requirement_id: str | None = None


class Shot(BaseModel):
    id: str
    number: str
    title: str
    line: int
    end_line: int = 0
    cast: list[Cast] = Field(default_factory=list)
    environment: str = ''
    ambience: str = ''
    environment_reference: bool = False
    sections: dict[str, str] = Field(default_factory=dict)
    dialogues: list[DialogueLine] = Field(default_factory=list)
    text: str = ''
    requirement_ids: list[str] = Field(default_factory=list)


class Chapter(BaseModel):
    id: str
    number: str
    title: str
    line: int
    shots: list[Shot] = Field(default_factory=list)


class Script(BaseModel):
    project_id: str
    title: str = ''
    source: str
    revision: str
    chapters: list[Chapter] = Field(default_factory=list)
    requirements: list[Requirement] = Field(default_factory=list)
    diagnostics: list[Diagnostic] = Field(default_factory=list)

    @property
    def valid(self):
        return not self.diagnostics


def identity(project_id: str, key: str) -> str:
    return uuid5(UUID(project_id), key).hex


def requirement_id(kind: str, name: str) -> str:
    return hashlib.sha256((kind + '\0' + name).encode('utf-8')).hexdigest()[:32]


def split_fields(text: str) -> list[str]:
    """Only slashes outside a complete-asset bracket delimit fields."""
    result, current, inside = [], [], False
    for char in text:
        if char == '【':
            if inside:
                raise ValueError('完整资产引用不能嵌套')
            inside = True
        elif char == '】':
            if not inside:
                raise ValueError('多余的右括号 】')
            inside = False
        if char == '/' and not inside:
            result.append(''.join(current).strip())
            current = []
        else:
            current.append(char)
    if inside:
        raise ValueError('完整资产引用缺少右括号 】')
    result.append(''.join(current).strip())
    return result


def complete(text: str) -> str | None:
    match = re.fullmatch(r'【([^【】]+)】', text)
    return match.group(1).strip() if match else None


def parse(source: str, project_id: str) -> Script:
    source = source.replace('\r\n', '\n').replace('\r', '\n')
    result = Script(project_id=project_id, source=source, revision=hashlib.sha256(source.encode()).hexdigest())
    chapter, shot, section = None, None, '动作'
    structural = True
    requirements = {}
    lines = source.splitlines()

    def error(line, message, code='syntax'):
        result.diagnostics.append(Diagnostic(line=line, message=message, code=code))

    def need(kind, name, line):
        if not name or name == '-':
            return
        rid = requirement_id(kind, name)
        req = requirements.setdefault(rid, Requirement(id=rid, kind=kind, name=name, media=MEDIA[kind]))
        use = Usage(chapter_id=chapter.id, shot_id=shot.id, line=line)
        if use not in req.usages:
            req.usages.append(use)
        if rid not in shot.requirement_ids:
            shot.requirement_ids.append(rid)

    def finish(end):
        if shot:
            shot.end_line = end
            shot.text = '\n'.join(lines[shot.line - 1:end])

    for line_no, raw in enumerate(lines, 1):
        text = raw.strip()
        if not text or text.startswith('//'):
            continue
        try:
            fields = split_fields(text)
        except ValueError as exc:
            error(line_no, str(exc), 'brackets')
            continue
        if any(not m.strip() for m in re.findall(r'【([^【】]*)】', text)):
            error(line_no, '完整资产名不能为空', 'asset_name')
            continue
        if len(fields) == 2 and fields[1] == '名称':
            if result.title or chapter:
                error(line_no, '一份剧本只能声明一个影片，且必须放在开头', 'project')
            elif not fields[0]:
                error(line_no, '影片名称不能为空', 'project')
            else:
                result.title = fields[0]
            continue
        if len(fields) in (2, 3) and fields[1] in ('集数', '章节'):
            finish(line_no - 1)
            if not result.title:
                error(line_no, '请先写“影片名/名称”', 'project')
            if not re.fullmatch(r'\d+', fields[0]) or (len(fields) == 3 and not fields[2]):
                error(line_no, '章节格式：01/集数，或 01/章节/章节名', 'chapter')
                continue
            number = str(int(fields[0]))
            if any(c.number == number for c in result.chapters):
                error(line_no, '章节编号重复', 'duplicate_chapter')
                continue
            chapter = Chapter(id=identity(project_id, 'chapter:' + number), number=number,
                              title=fields[2] if len(fields) == 3 else f'第 {number} 章', line=line_no)
            result.chapters.append(chapter)
            shot = None
            continue
        if len(fields) == 2 and re.fullmatch(r'\d{3,}', fields[0]):
            finish(line_no - 1)
            if chapter is None:
                error(line_no, '镜头必须位于章节内', 'shot')
                continue
            number = str(int(fields[0])).zfill(3)
            if any(s.number == number for s in chapter.shots):
                error(line_no, '当前章节内镜头编号重复', 'duplicate_shot')
                continue
            if not fields[1]:
                error(line_no, '镜头标题不能为空', 'shot')
            shot = Shot(id=identity(project_id, f'shot:{chapter.number}:{number}'),
                        number=number, title=fields[1], line=line_no)
            chapter.shots.append(shot)
            structural, section = True, '动作'
            continue
        if shot is None:
            error(line_no, '内容必须位于镜头内；镜头使用三位及以上编号，例如 001/推门进入', 'context')
            continue
        header = re.match(r'^(镜头|动作|表演|对白|连续性|备注)[：:](.*)$', text)
        if header:
            section, text = header.groups()
            text = text.strip()
            structural = False
            if not text:
                continue
        explicit_cast = text.startswith(('人物：', '人物:'))
        explicit_env = text.startswith(('环境：', '环境:'))
        if explicit_cast or explicit_env:
            if not structural:
                error(line_no, '人物与环境行请放在自然语言创作区之前', 'structure_order')
                continue
            text = text[3:].strip()
            fields = split_fields(text)
        visual = complete(fields[0]) if fields else None
        visual_parts = visual.split('/') if visual else []
        is_cast = structural and (explicit_cast or len(fields) == 4 or
                                    (len(fields) == 2 and len(visual_parts) >= 3))
        if is_cast:
            if shot.environment:
                error(line_no, '人物行应在环境行之前', 'structure_order')
                continue
            if visual:
                if len(fields) != 2 or len(visual_parts) != 3:
                    error(line_no, '完整角色格式为【人物/年龄/服装】/音声；声音不能放入视觉括号', 'cast')
                    continue
                parts = [p.strip() for p in visual_parts] + [fields[1]]
            else:
                parts = fields
            if len(parts) != 4 or any(not p for p in parts) or parts[0] == '-' or any('【' in p or '】' in p for p in parts):
                error(line_no, '人物必须为四个位置：人物/年龄/服装/音声；空位使用 -', 'cast')
                continue
            person, age, costume, voice = parts
            if any(c.person == person for c in shot.cast):
                error(line_no, '同一镜头的人物重复声明', 'duplicate_cast')
                continue
            shot.cast.append(Cast(person=person, age=age, costume=costume, voice=voice,
                                  complete_visual=visual, line=line_no))
            if visual:
                need('character_visual', visual, line_no)
            else:
                need('character', person, line_no)
                if age != '-': need('age', f'{person}/{age}', line_no)
                if costume != '-': need('costume', f'{person}/{costume}', line_no)
            if voice != '-': need('voice', f'{person}/{voice}', line_no)
            continue
        if structural and (explicit_env or (len(fields) == 2 and not shot.environment)):
            if len(fields) != 2 or not all(fields):
                error(line_no, '环境格式为 环境/背景音，空位使用 -', 'environment')
                continue
            if shot.environment:
                error(line_no, '同一镜头只能声明一个环境行', 'environment')
                continue
            if visual and len(visual_parts) > 2:
                error(line_no, '角色视觉不能包含音声；请使用【人物/年龄/服装】/音声', 'cast')
                continue
            if ('【' in fields[0] or '】' in fields[0]) and visual is None:
                error(line_no, '环境参照必须是完整的【资产名】', 'environment')
                continue
            shot.environment = visual if visual is not None else fields[0]
            shot.ambience = fields[1]
            shot.environment_reference = visual is not None
            if visual: need('environment', visual, line_no)
            continue
        if structural and (len(fields) > 1 or (visual and len(visual_parts) >= 3)):
            error(line_no, '结构行位置数不正确；正文中使用 / 时请先写“动作：”或“备注：”', 'field_count')
            continue
        structural = False
        shot.sections[section] = (shot.sections.get(section, '') + '\n' + text).strip()
        if section == '对白':
            dialogue = re.fullmatch(r'([^：:]+)[：:](.+)', text)
            if not dialogue:
                error(line_no, '对白格式：角色：内容', 'dialogue')
            else:
                speaker, words = (part.strip() for part in dialogue.groups())
                cast_item = next((item for item in shot.cast if item.person == speaker), None)
                if not cast_item:
                    error(line_no, f'对白角色未在当前镜头人物中声明：{speaker}', 'dialogue_speaker')
                else:
                    order = len(shot.dialogues) + 1
                    voice_id = requirement_id('voice', f'{speaker}/{cast_item.voice}') if cast_item.voice != '-' else None
                    semantic = hashlib.sha256(f'{speaker}\0{words}'.encode('utf-8')).hexdigest()
                    shot.dialogues.append(DialogueLine(
                        id=identity(project_id, f'dialogue:{shot.id}:{order}'), speaker=speaker,
                        text=words, order=order, line=line_no, source_fingerprint=semantic,
                        voice_requirement_id=voice_id))
        for name in re.findall(r'【([^【】]+)】', text):
            need('video_reference' if section == '镜头' else 'prop', name.strip(), line_no)
    finish(len(lines))
    if not result.title: error(1, '缺少影片名/名称', 'project')
    if not result.chapters: error(1, '至少需要一个章节', 'chapter')
    for item in result.chapters:
        if not item.shots: error(item.line, '章节内至少需要一个镜头', 'shot')
    result.requirements = list(requirements.values())
    return result
