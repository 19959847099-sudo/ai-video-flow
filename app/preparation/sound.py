"""V0.2 sound production truth derived from Production Script.

Voice identities are reusable inputs. Dialogue/background media remain ordinary Candidates,
with explicit Current bindings. Subtitle text is an output-layer derivative and never edits Script.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Literal
from uuid import uuid4, uuid5, UUID

from pydantic import BaseModel, Field

from app.rough_cut import probe
from .production import Candidate, ProductionService
from .runtime import ProductionInput, ProductionRequest, ProductionRuntime
from .workspace import now

AudioStrategy = Literal['native', 'independent', 'none']


def _fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()


def _stable(project_id, value):
    return uuid5(UUID(project_id), value).hex


class BackgroundItem(BaseModel):
    id: str
    chapter_id: str
    shot_id: str
    text: str
    source_fingerprint: str


class DialogueState(BaseModel):
    dialogue_id: str
    strategy: AudioStrategy
    start: float = Field(default=0, ge=0)
    volume: float = Field(default=1, ge=0, le=2)
    mute: bool = False
    enabled: bool = True
    fade_in: float = Field(default=0, ge=0, le=3)
    fade_out: float = Field(default=0, ge=0, le=3)
    updated_at: str = Field(default_factory=now)


class BackgroundState(BaseModel):
    background_id: str
    start: float = Field(default=0, ge=0)
    volume: float = Field(default=.35, ge=0, le=2)
    mute: bool = False
    enabled: bool = True
    fade_in: float = Field(default=.15, ge=0, le=3)
    fade_out: float = Field(default=.25, ge=0, le=3)
    updated_at: str = Field(default_factory=now)


class SubtitleItem(BaseModel):
    dialogue_id: str
    display_text: str
    start: float = Field(default=0, ge=0)
    end: float = Field(default=2.5, gt=0)
    enabled: bool = True
    manual_text: bool = False
    manual_timing: bool = False
    source_fingerprint: str
    stale: bool = False
    updated_at: str = Field(default_factory=now)


class VoiceIdentity(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    requirement_id: str
    label: str
    provider_id: str
    provider_voice_id: str
    language: str = 'zh'
    created_at: str = Field(default_factory=now)


class SoundProduction:
    def __init__(self, workspace):
        self.workspace = workspace
        self.production = ProductionService(workspace)
        self.runtime = ProductionRuntime(workspace)
        self.sync()

    def dialogues(self, shot_id=None, chapter_id=None):
        script = self.workspace.script
        if not script: return []
        result = []
        for chapter in script.chapters:
            if chapter_id and chapter.id != chapter_id: continue
            for shot in chapter.shots:
                if shot_id and shot.id != shot_id: continue
                result.extend(shot.dialogues)
        return result

    def dialogue(self, dialogue_id):
        result = next((item for item in self.dialogues() if item.id == dialogue_id), None)
        if not result: raise ValueError('当前剧本中没有此对白')
        return result

    def shot(self, shot_id):
        return self.production.shot_context(shot_id)[1]

    def background_items(self, shot_id=None, chapter_id=None):
        script = self.workspace.script
        if not script: return []
        result = []
        for chapter in script.chapters:
            if chapter_id and chapter.id != chapter_id: continue
            for shot in chapter.shots:
                if shot_id and shot.id != shot_id: continue
                if shot.ambience and shot.ambience != '-':
                    result.append(BackgroundItem(
                        id=_stable(script.project_id, 'background:' + shot.id), chapter_id=chapter.id,
                        shot_id=shot.id, text=shot.ambience,
                        source_fingerprint=_fingerprint({'shot': shot.id, 'ambience': shot.ambience})))
        return result

    def background(self, background_id):
        result = next((item for item in self.background_items() if item.id == background_id), None)
        if not result: raise ValueError('当前剧本中没有此背景音')
        return result

    def sync(self):
        changed = False
        shot_cursors = {}
        for dialogue in self.dialogues():
            shot_id = next(s.id for c in self.workspace.script.chapters for s in c.shots if dialogue in s.dialogues)
            cursor = shot_cursors.get(shot_id, 0.0)
            state = self.workspace.state['dialogue_states'].get(dialogue.id)
            if not state:
                state = DialogueState(dialogue_id=dialogue.id, start=cursor,
                    strategy='native' if dialogue.voice_requirement_id else 'none').model_dump()
                self.workspace.state['dialogue_states'][dialogue.id] = state
                changed = True
            shot_cursors[shot_id] = max(cursor, float(state.get('start', 0))) + 2.7
            subtitle = self.workspace.state['subtitles'].get(dialogue.id)
            if not subtitle:
                current = DialogueState.model_validate(self.workspace.state['dialogue_states'][dialogue.id])
                self.workspace.state['subtitles'][dialogue.id] = SubtitleItem(
                    dialogue_id=dialogue.id, display_text=dialogue.text, start=current.start,
                    end=current.start + 2.5, source_fingerprint=dialogue.source_fingerprint).model_dump()
                changed = True
            elif subtitle['source_fingerprint'] != dialogue.source_fingerprint:
                if subtitle.get('manual_text'):
                    subtitle['stale'] = True
                else:
                    subtitle.update(display_text=dialogue.text,
                                    source_fingerprint=dialogue.source_fingerprint, stale=False,
                                    updated_at=now())
                changed = True
        for item in self.background_items():
            if item.id not in self.workspace.state['background_states']:
                self.workspace.state['background_states'][item.id] = BackgroundState(background_id=item.id).model_dump()
                changed = True
        if changed: self.workspace._save()

    def state(self, dialogue_id):
        self.dialogue(dialogue_id)
        return DialogueState.model_validate(self.workspace.state['dialogue_states'][dialogue_id])

    def update_state(self, dialogue_id, **changes):
        permitted = {'strategy', 'start', 'volume', 'mute', 'enabled', 'fade_in', 'fade_out'}
        if changes.keys() - permitted: raise ValueError('未知对白声音设置')
        state = self.state(dialogue_id).model_copy(update={**changes, 'updated_at': now()})
        DialogueState.model_validate(state)
        self.workspace.state['dialogue_states'][dialogue_id] = state.model_dump()
        subtitle = self.workspace.state['subtitles'][dialogue_id]
        if 'start' in changes and not subtitle.get('manual_timing'):
            duration = self.current_duration(dialogue_id) or max(.1, subtitle['end'] - subtitle['start'])
            subtitle.update(start=state.start, end=state.start + duration, updated_at=now())
        self.workspace._save(); return state

    def update_background(self, background_id, **changes):
        permitted = {'start', 'volume', 'mute', 'enabled', 'fade_in', 'fade_out'}
        if changes.keys() - permitted: raise ValueError('未知背景音设置')
        self.background(background_id)
        current = BackgroundState.model_validate(self.workspace.state['background_states'][background_id])
        current = current.model_copy(update={**changes, 'updated_at': now()})
        BackgroundState.model_validate(current)
        self.workspace.state['background_states'][background_id] = current.model_dump()
        self.workspace._save(); return current

    def subtitle(self, dialogue_id):
        self.dialogue(dialogue_id)
        return SubtitleItem.model_validate(self.workspace.state['subtitles'][dialogue_id])

    def update_subtitle(self, dialogue_id, *, display_text=None, start=None, end=None, enabled=None):
        item = self.subtitle(dialogue_id); values = item.model_dump()
        if display_text is not None:
            values['display_text'] = display_text.strip(); values['manual_text'] = True
            if not values['display_text']: raise ValueError('字幕文本不能为空')
            values['source_fingerprint'] = self.dialogue(dialogue_id).source_fingerprint
            values['stale'] = False
        if start is not None or end is not None:
            values['start'] = item.start if start is None else float(start)
            values['end'] = item.end if end is None else float(end)
            values['manual_timing'] = True
        if enabled is not None: values['enabled'] = bool(enabled)
        values['updated_at'] = now()
        result = SubtitleItem.model_validate(values)
        if result.end <= result.start: raise ValueError('字幕结束时间必须晚于开始时间')
        self.workspace.state['subtitles'][dialogue_id] = result.model_dump()
        self.workspace._save(); return result

    def set_voice_identity(self, requirement_id, provider_id, provider_voice_id, label='', language='zh'):
        if not provider_id.strip() or not provider_voice_id.strip(): raise ValueError('Voice Provider 与 Voice ID 不能为空')
        if not any(r.id == requirement_id and r.kind == 'voice' for r in self.workspace.script.requirements):
            raise ValueError('Voice Requirement 不存在')
        identity = VoiceIdentity(requirement_id=requirement_id, provider_id=provider_id.strip(),
                                 provider_voice_id=provider_voice_id.strip(),
                                 label=label.strip() or provider_voice_id.strip(), language=language)
        self.workspace.state['voice_identities'][identity.id] = identity.model_dump()
        previous = self.workspace.state['voice_identity_bindings'].get(requirement_id)
        self.workspace.state['voice_identity_bindings'][requirement_id] = identity.id
        self.workspace._event('voice_current', f'当前声音 → {identity.label}', [],
                              requirement_id=requirement_id, identity_id=identity.id, previous=previous)
        self.workspace._save(); return identity

    def voice_context(self, dialogue):
        rid = dialogue.voice_requirement_id
        if not rid: return None, None
        candidate_id = self.production.current(rid)
        if candidate_id:
            candidate = self.production.candidate(candidate_id)
            if self.production.available(candidate_id):
                return ProductionInput(role='reference_audio', purpose='voice_identity',
                    asset_id=candidate.asset_id, path=candidate.media_path, sha256=candidate.sha256,
                    metadata={'candidate_id': candidate.id}), {'kind': 'reference', 'id': candidate.id, 'sha256': candidate.sha256}
        identity_id = self.workspace.state['voice_identity_bindings'].get(rid)
        identity = self.workspace.state['voice_identities'].get(identity_id)
        if identity:
            return ProductionInput(role='voice_identity', purpose='voice_identity', value=identity['provider_voice_id'],
                metadata={'provider_id': identity['provider_id'], 'identity_id': identity_id,
                          'language': identity['language']}), {'kind': 'provider', 'id': identity_id,
                                                               'provider': identity['provider_id'],
                                                               'voice_id': identity['provider_voice_id']}
        return None, {'kind': 'described', 'requirement_id': rid}

    def context(self, dialogue_id):
        dialogue = self.dialogue(dialogue_id); chapter, shot = self.production.shot_context(
            next(s.id for c in self.workspace.script.chapters for s in c.shots if dialogue in s.dialogues))
        voice_input, voice = self.voice_context(dialogue)
        facts = {'project_id': self.workspace.state['project_id'], 'chapter_id': chapter.id,
                 'shot_id': shot.id, 'dialogue_id': dialogue.id, 'speaker': dialogue.speaker,
                 'text': dialogue.text, 'order': dialogue.order,
                 'performance': shot.sections.get('表演', ''),
                 'continuity': shot.sections.get('连续性', ''), 'voice': voice}
        return facts, voice_input, _fingerprint(facts)

    def prompt(self, dialogue_id):
        facts, _, context_fp = self.context(dialogue_id)
        key = 'dialogue:' + dialogue_id
        record = self.workspace.state['sound_prompts'].get(key)
        if not record:
            parts = [f"对白音频 · {facts['speaker']}", f"台词：{facts['text']}"]
            if facts['performance']: parts.append('表演：' + facts['performance'])
            if facts['continuity']: parts.append('连续性：' + facts['continuity'])
            record = {'key': key, 'text': '\n\n'.join(parts), 'constraints': '', 'edited': False,
                      'context_fingerprint': context_fp, 'created_at': now(), 'updated_at': now()}
            self.workspace.state['sound_prompts'][key] = record; self.workspace._save()
        return deepcopy(record), record['context_fingerprint'] != context_fp

    def save_prompt(self, dialogue_id, text, constraints=''):
        record, _ = self.prompt(dialogue_id); record.update(text=text.strip(), constraints=constraints.strip(),
                                                             edited=True, updated_at=now())
        self.workspace.state['sound_prompts'][record['key']] = record; self.workspace._save(); return record

    def build_dialogue_request(self, dialogue_id, model_id='fixture-audio-v1', output_count=1,
                               *, prompt_text=None, constraints=None, speed=1.0, fixture_mode='success'):
        dialogue = self.dialogue(dialogue_id)
        if not dialogue.voice_requirement_id:
            raise ValueError('当前角色声明为无音声，不创建对白生成任务')
        facts, voice_input, context_fp = self.context(dialogue_id)
        prompt, _ = self.prompt(dialogue_id)
        manifest = self.runtime.registry.model(model_id)
        return ProductionRequest(
            project_id=facts['project_id'], chapter_id=facts['chapter_id'], shot_id=facts['shot_id'],
            dialogue_id=dialogue.id, task='dialogue_audio', purpose='dialogue', media='audio',
            speaker=dialogue.speaker, text=dialogue.text, language='zh',
            performance=facts['performance'], prompt=prompt_text if prompt_text is not None else prompt['text'],
            constraints=constraints if constraints is not None else prompt['constraints'],
            provider_id=manifest.provider_id, model_id=model_id, output_count=output_count,
            output_format='wav', inputs=[voice_input] if voice_input else [],
            model_settings={'speed': speed, 'fixture_mode': fixture_mode},
            source_context_fingerprint=context_fp)

    def build_background_request(self, background_id, model_id='fixture-audio-v1', output_count=1,
                                 *, fixture_mode='success'):
        item = self.background(background_id); manifest = self.runtime.registry.model(model_id)
        return ProductionRequest(
            project_id=self.workspace.state['project_id'], chapter_id=item.chapter_id, shot_id=item.shot_id,
            background_id=item.id, task='background_audio', purpose='ambient', media='audio',
            text=item.text, language='zh', prompt='环境声音：' + item.text,
            provider_id=manifest.provider_id, model_id=model_id, output_count=output_count,
            output_format='wav', model_settings={'fixture_mode': fixture_mode},
            source_context_fingerprint=item.source_fingerprint)

    def dialogue_candidates(self, dialogue_id): return self.production.dialogue_candidates(dialogue_id)
    def background_candidates(self, background_id): return self.production.background_candidates(background_id)
    def current_dialogue(self, dialogue_id): return self.workspace.state['dialogue_bindings'].get(dialogue_id)
    def current_background(self, background_id): return self.workspace.state['background_bindings'].get(background_id)

    def import_dialogue(self, dialogue_id, source):
        dialogue = self.dialogue(dialogue_id); _, shot = self.production.shot_context(
            next(s.id for c in self.workspace.script.chapters for s in c.shots if dialogue in s.dialogues))
        probe(Path(source), 'audio')
        return self.production.ingest_audio_target(shot.id, 'dialogue_audio', dialogue.id, source, 'imported',
            generation_metadata={'context_fingerprint': self.context(dialogue_id)[2],
                                 'speaker': dialogue.speaker, 'text': dialogue.text})

    def import_background(self, background_id, source):
        item = self.background(background_id); probe(Path(source), 'audio')
        return self.production.ingest_audio_target(item.shot_id, 'background_audio', item.id, source, 'imported',
            generation_metadata={'context_fingerprint': item.source_fingerprint, 'text': item.text})

    def bind_dialogue(self, candidate_id):
        candidate = self.production.candidate(candidate_id)
        if not candidate.dialogue_id or candidate.review_state != 'green' or not self.production.available(candidate_id):
            raise ValueError('仅可选用仍然有效的 Green 对白版本')
        previous = self.current_dialogue(candidate.dialogue_id)
        self.workspace.state['dialogue_bindings'][candidate.dialogue_id] = candidate.id
        self.workspace.state['candidates'][candidate.id]['history'].append(
            {'at': now(), 'event': 'bound', 'previous_candidate_id': previous})
        duration = probe(self.workspace.path(candidate.media_path), 'audio')['duration']
        subtitle = self.workspace.state['subtitles'][candidate.dialogue_id]
        state = self.state(candidate.dialogue_id)
        if not subtitle.get('manual_timing'):
            subtitle.update(start=state.start, end=state.start + duration, updated_at=now())
        self.workspace._event('dialogue_current', f'对白当前版本 → Take {candidate.take_number:02d}',
                              [candidate.shot_id], dialogue_id=candidate.dialogue_id,
                              candidate_id=candidate.id, previous=previous)
        self.workspace._save(); return candidate

    def bind_background(self, candidate_id):
        candidate = self.production.candidate(candidate_id)
        if not candidate.background_id or candidate.review_state != 'green' or not self.production.available(candidate_id):
            raise ValueError('仅可选用仍然有效的 Green 背景音版本')
        previous = self.current_background(candidate.background_id)
        self.workspace.state['background_bindings'][candidate.background_id] = candidate.id
        self.workspace.state['candidates'][candidate.id]['history'].append(
            {'at': now(), 'event': 'bound', 'previous_candidate_id': previous})
        self.workspace._event('background_current', f'背景音当前版本 → Take {candidate.take_number:02d}',
                              [candidate.shot_id], background_id=candidate.background_id,
                              candidate_id=candidate.id, previous=previous)
        self.workspace._save(); return candidate

    def current_duration(self, dialogue_id):
        candidate_id = self.current_dialogue(dialogue_id)
        if not candidate_id: return None
        candidate = self.production.candidate(candidate_id)
        if not self.production.available(candidate_id): return None
        return probe(self.workspace.path(candidate.media_path), 'audio')['duration']

    def candidate_stale(self, candidate_id):
        candidate = self.production.candidate(candidate_id)
        expected = (self.context(candidate.dialogue_id)[2] if candidate.dialogue_id
                    else self.background(candidate.background_id).source_fingerprint)
        return candidate.generation_metadata.get('context_fingerprint') != expected

    def audio_plan(self, shot_id):
        dialogues = []
        for item in self.dialogues(shot_id=shot_id):
            state = self.state(item.id); current = self.current_dialogue(item.id)
            candidate = self.production.candidate(current) if current else None
            path = candidate.media_path if candidate and self.production.available(candidate.id) else None
            dialogues.append({'dialogue_id': item.id, 'speaker': item.speaker, 'text': item.text,
                'strategy': state.strategy, 'start': state.start, 'volume': state.volume,
                'mute': state.mute, 'enabled': state.enabled, 'fade_in': state.fade_in,
                'fade_out': state.fade_out, 'candidate_id': current, 'path': path,
                'duration': self.current_duration(item.id) if path else None,
                'stale': self.candidate_stale(current) if current else False,
                'subtitle': self.subtitle(item.id).model_dump()})
        backgrounds = []
        for item in self.background_items(shot_id=shot_id):
            state = BackgroundState.model_validate(self.workspace.state['background_states'][item.id])
            current = self.current_background(item.id)
            candidate = self.production.candidate(current) if current else None
            path = candidate.media_path if candidate and self.production.available(candidate.id) else None
            duration = probe(self.workspace.path(path), 'audio')['duration'] if path else None
            backgrounds.append({'background_id': item.id, 'text': item.text, **state.model_dump(),
                                'candidate_id': current, 'path': path, 'duration': duration,
                                'stale': self.candidate_stale(current) if current else False})
        independent = any(d['strategy'] == 'independent' and d['enabled'] and not d['mute'] for d in dialogues)
        native = not independent and any(d['strategy'] == 'native' and d['enabled'] for d in dialogues)
        if not dialogues: native = True
        mixed_dialogue_sources = independent and any(
            d['strategy'] == 'native' and d['enabled'] and not d['mute'] for d in dialogues)
        return {'shot_id': shot_id, 'native_audio': native,
                'mixed_dialogue_sources': mixed_dialogue_sources,
                'dialogues': dialogues, 'backgrounds': backgrounds}

    def srt_entries(self, chapter_id, clip_offsets):
        entries = []
        for dialogue in self.dialogues(chapter_id=chapter_id):
            shot_id = next(s.id for c in self.workspace.script.chapters for s in c.shots if dialogue in s.dialogues)
            if shot_id not in clip_offsets: continue
            subtitle = self.subtitle(dialogue.id); state = self.state(dialogue.id)
            if not subtitle.enabled or not state.enabled: continue
            base = clip_offsets[shot_id]
            entries.append({'dialogue_id': dialogue.id, 'speaker': dialogue.speaker,
                            'text': subtitle.display_text, 'start': base + subtitle.start,
                            'end': base + subtitle.end, 'stale': subtitle.stale})
        return sorted(entries, key=lambda item: (item['start'], item['end']))


def srt_time(seconds):
    milliseconds = max(0, round(float(seconds) * 1000))
    hours, milliseconds = divmod(milliseconds, 3600000)
    minutes, milliseconds = divmod(milliseconds, 60000)
    secs, milliseconds = divmod(milliseconds, 1000)
    return f'{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}'


def write_srt(path, entries):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for index, item in enumerate(entries, 1):
        if item['end'] <= item['start']: raise ValueError('字幕时间无效')
        lines.extend([str(index), f"{srt_time(item['start'])} --> {srt_time(item['end'])}", item['text'], ''])
    path.write_text('\n'.join(lines), encoding='utf-8')
    return path
