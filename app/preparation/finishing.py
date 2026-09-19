"""V0.2 chapter assembly: non-destructive edits over explicit current Shot videos."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
from uuid import uuid4

from app.core import write_json
from app.production import media_tool
from app.rough_cut import probe
from .production import ProductionService
from .sound import SoundProduction, write_srt
from .workspace import Workspace, sha


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()


class ChapterFinishing:
    def __init__(self, workspace: Workspace, chapter_id: str):
        self.workspace = workspace
        self.service = ProductionService(workspace)
        self.sound = SoundProduction(workspace)
        self.chapter_id = chapter_id
        self._probe_cache = {}
        self.chapter()
        self._ensure()

    def chapter(self):
        script = self.workspace.script
        result = next((c for c in script.chapters if c.id == self.chapter_id), None) if script else None
        if not result:
            raise ValueError('当前剧本中没有此章节')
        return result

    def _ensure(self):
        state = self.workspace.state['assemblies']
        if self.chapter_id not in state:
            state[self.chapter_id] = {'segments': [], 'known_shots': [], 'selected': None, 'version': 1, 'preview': None, 'output': None, 'subtitle_sidecar': True}
        assembly = state[self.chapter_id]
        known = assembly.setdefault('known_shots', list(dict.fromkeys(item['shot_id'] for item in assembly['segments'])))
        for shot in self.chapter().shots:
            if shot.id not in known:
                assembly['segments'].append(self._new_segment(shot.id))
                known.append(shot.id)
        if not assembly['selected'] and assembly['segments']:
            assembly['selected'] = assembly['segments'][0]['id']
        self.workspace._save()

    def _new_segment(self, shot_id, start=0.0, end=None):
        return dict(id=uuid4().hex, shot_id=shot_id, enabled=True, trim_in=start,
                    trim_out=end, volume=1.0, mute=False)

    @property
    def state(self):
        return self.workspace.state['assemblies'][self.chapter_id]

    def segments(self):
        return deepcopy(self.state['segments'])

    def selected(self):
        return self.state['selected']

    def select(self, segment_id):
        if not any(s['id'] == segment_id for s in self.state['segments']):
            raise ValueError('Segment 不存在')
        self.state['selected'] = segment_id
        self.workspace._save()

    def _metadata(self, path):
        key = (str(path), path.stat().st_size, path.stat().st_mtime_ns, 'video')
        if key not in self._probe_cache:
            self._probe_cache[key] = probe(path, 'video')
        return self._probe_cache[key]

    def _source(self, shot_id):
        current = self.service.current_shot(shot_id)
        if not current:
            raise ValueError('没有正式 Current 视频')
        candidate = self.service.candidate(current)
        if (candidate.shot_id != shot_id or candidate.chapter_id != self.chapter_id
                or candidate.kind != 'shot_video'):
            raise ValueError('Current 与镜头不匹配')
        if candidate.review_state != 'green' or not self.service.available(current):
            raise ValueError('Current 已不可用或审核状态改变')
        path = self.workspace.path(candidate.media_path)
        return candidate, path, self._metadata(path)

    def _range(self, segment, duration):
        start = float(segment['trim_in'])
        end = float(segment['trim_out']) if segment['trim_out'] is not None else duration
        if not all(math.isfinite(v) for v in (start, end)) or start < 0 or end > duration + 0.02 or end-start < 0.05:
            raise ValueError('Trim 范围无效或短于 0.05 秒')
        volume = float(segment['volume'])
        if not math.isfinite(volume) or volume < 0 or volume > 2:
            raise ValueError('Volume 只允许 0–200%')
        return start, min(end, duration)

    def update(self, segment_id, **changes):
        permitted = {'enabled', 'trim_in', 'trim_out', 'volume', 'mute'}
        if changes.keys() - permitted:
            raise ValueError('未知轻剪设置')
        before = deepcopy(self.state)
        try:
            segment = next(s for s in self.state['segments'] if s['id'] == segment_id)
            segment.update(changes)
            if segment['trim_out'] is not None and float(segment['trim_out']) <= float(segment['trim_in']):
                raise ValueError('Trim Out 必须晚于 Trim In')
            if float(segment['trim_in']) < 0:
                raise ValueError('Trim In 不能小于零')
            if not 0 <= float(segment['volume']) <= 2:
                raise ValueError('Volume 只允许 0–200%')
            try:
                _, _, info = self._source(segment['shot_id'])
            except ValueError:
                pass
            else:
                self._range(segment, info['duration'])
            self.state['version'] += 1
            self.workspace._save()
        except Exception:
            self.workspace.state['assemblies'][self.chapter_id] = before
            raise

    def move(self, segment_id, offset):
        items = self.state['segments']
        index = next(i for i, item in enumerate(items) if item['id'] == segment_id)
        target = index + offset
        if not 0 <= target < len(items):
            return
        items.insert(target, items.pop(index))
        self.state['version'] += 1
        self.workspace._save()

    def split(self, segment_id, at):
        items = self.state['segments']
        index = next(i for i, item in enumerate(items) if item['id'] == segment_id)
        segment = items[index]
        _, _, info = self._source(segment['shot_id'])
        start, end = self._range(segment, info['duration'])
        at = float(at)
        if at-start < 0.05 or end-at < 0.05:
            raise ValueError('Split 点必须位于有效片段内部')
        second = deepcopy(segment)
        second['id'] = uuid4().hex
        second['trim_in'] = at
        segment['trim_out'] = at
        items.insert(index+1, second)
        self.state['selected'] = second['id']
        self.state['version'] += 1
        self.workspace._save()
        return second['id']

    def remove(self, segment_id):
        items = self.state['segments']
        index = next(i for i, item in enumerate(items) if item['id'] == segment_id)
        items.pop(index)
        self.state['selected'] = items[min(index, len(items)-1)]['id'] if items else None
        self.state['version'] += 1
        self.workspace._save()

    def resolve(self):
        shots = {s.id: s for s in self.chapter().shots}
        errors, warnings, clips = [], [], []
        for index, segment in enumerate(self.state['segments']):
            shot = shots.get(segment['shot_id'])
            if not shot:
                warnings.append(f'{index+1}: 剧本中已移除此镜头；原装配片段仍保留')
                if segment['enabled']:
                    errors.append(f'{index+1}: 镜头已不在当前章节')
                continue
            if not segment['enabled']:
                continue
            try:
                candidate, path, info = self._source(shot.id)
                start, end = self._range(segment, info['duration'])
                has_audio = self._has_audio(path)
                if not has_audio:
                    warnings.append(f'Shot {shot.number}: 源视频无音轨；预览使用静音')
                audio_plan = self.sound.audio_plan(shot.id)
                if audio_plan['mixed_dialogue_sources']:
                    warnings.append(
                        f'Shot {shot.number}: 已启用独立对白；本镜头视频原声音轨关闭以避免重复对白')
                for dialogue in audio_plan['dialogues']:
                    if dialogue['strategy'] == 'independent' and dialogue['enabled'] and not dialogue['path']:
                        errors.append(f'Shot {shot.number}: 独立对白尚未选用音频')
                    if dialogue['strategy'] == 'native' and dialogue['enabled'] and not has_audio:
                        errors.append(f'Shot {shot.number}: 已选择视频原生对白，但视频没有音轨')
                    if dialogue['stale']:
                        warnings.append(f'Shot {shot.number}: 对白音频基于较早的剧本或 Voice')
                for background in audio_plan['backgrounds']:
                    if background['enabled'] and not background['path']:
                        warnings.append(f'Shot {shot.number}: 背景音“{background["text"]}”尚未选用')
                    if background['stale']:
                        warnings.append(f'Shot {shot.number}: 背景音基于较早的环境描述')
                clips.append(dict(segment_id=segment['id'], shot_id=shot.id, shot_number=shot.number,
                                  shot_title=shot.title, shot_text=shot.text, candidate_id=candidate.id,
                                  take_number=candidate.take_number, path=candidate.media_path,
                                  sha256=candidate.sha256, source_in=start, source_out=end,
                                  duration=end-start, volume=float(segment['volume']), mute=bool(segment['mute']),
                                  has_audio=has_audio, audio_plan=audio_plan))
            except (ValueError, OSError, KeyError) as exc:
                errors.append(f'Shot {shot.number}: {exc}')
        if not clips and not errors:
            errors.append('装配没有启用的片段')
        # Reference bindings are upstream facts, not Assembly-owned copies.
        # Include their current state only in the derived build fingerprint.
        reports = {row['requirement']['id']: row for row in self.workspace.report()}
        references = {}
        for clip in clips:
            shot = shots[clip['shot_id']]
            references[shot.id] = [
                dict(requirement_id=rid, status=reports[rid]['status'],
                     asset_id=(reports[rid]['binding'] or {}).get('asset_id'),
                     candidate_id=(reports[rid]['binding'] or {}).get('candidate_id'),
                     sha256=(reports[rid]['binding'] or {}).get('sha256'))
                for rid in shot.requirement_ids if rid in reports]
        cursor = 0.0
        subtitles = []
        for clip in clips:
            for dialogue in clip['audio_plan']['dialogues']:
                subtitle = dialogue['subtitle']
                if subtitle['enabled'] and dialogue['enabled']:
                    local_start = float(subtitle['start']) - clip['source_in']
                    local_end = float(subtitle['end']) - clip['source_in']
                    start = cursor + max(0.0, local_start)
                    end = cursor + min(clip['duration'], local_end)
                    if end > start:
                        subtitles.append(dict(dialogue_id=dialogue['dialogue_id'], speaker=dialogue['speaker'],
                                              text=subtitle['display_text'], start=start, end=end,
                                              stale=subtitle['stale']))
                    if subtitle['stale']:
                        warnings.append(f'Shot {clip["shot_number"]}: 人工字幕对应的正式对白已变化')
            cursor += clip['duration']
        signature = fingerprint(dict(chapter_id=self.chapter_id, segments=self.state['segments'],
                                     clips=clips, references=references, subtitles=subtitles,
                                     subtitle_sidecar=self.state.get('subtitle_sidecar', True)))
        previous = self.state.get('preview')
        return dict(status='Blocked' if errors else 'Ready', errors=errors, warnings=warnings,
                    clips=clips, subtitles=subtitles, fingerprint=signature,
                    stale=bool(previous and previous.get('fingerprint') != signature),
                    duration=sum(c['duration'] for c in clips))

    def _has_audio(self, path):
        key = (str(path), path.stat().st_size, path.stat().st_mtime_ns, 'audio')
        if key not in self._probe_cache:
            try:
                probe(path, 'audio')
                self._probe_cache[key] = True
            except ValueError as exc:
                if '缺少 audio stream' not in str(exc):
                    raise
                self._probe_cache[key] = False
        return self._probe_cache[key]

    def _run(self, command):
        result = subprocess.run(command, capture_output=True, timeout=300,
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        if result.returncode:
            raise ValueError('媒体处理失败：' + result.stderr.decode('utf-8', errors='replace')[-1200:])

    def _render(self, quality):
        resolved = self.resolve()
        if resolved['errors']:
            raise ValueError('\n'.join(resolved['errors']))
        signature = resolved['fingerprint']
        width, height = (960, 540) if quality == 'preview' else (1280, 720)
        folder = self.workspace.path(f'finishing/{self.chapter_id}/{quality}/{signature}')
        target = folder / f'chapter-{quality}.mp4'
        record = self.state.get(quality)
        if record and record.get('fingerprint') == signature and target.is_file() and sha(target) == record.get('sha256'):
            return target
        folder.mkdir(parents=True, exist_ok=True)
        parts = []
        for index, clip in enumerate(resolved['clips']):
            source = self.workspace.path(clip['path'])
            part = folder / f'part-{index:03d}.mp4'
            start, end, duration = clip['source_in'], clip['source_out'], clip['duration']
            inputs = ['-i', str(source)]
            filters = [(f'[0:v]trim=start={start}:end={end},setpts=PTS-STARTPTS,'
                        f'scale={width}:{height}:force_original_aspect_ratio=decrease,'
                        f'pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,fps=24,format=yuv420p[v]')]
            audio_labels = []
            plan = clip['audio_plan']
            if plan['native_audio'] and clip['has_audio'] and not clip['mute']:
                label_name = f'a{len(audio_labels)}'
                filters.append(f'[0:a]atrim=start={start}:end={end},asetpts=PTS-STARTPTS,'
                               f'aresample=48000,volume={clip["volume"]},apad,atrim=duration={duration}[{label_name}]')
                audio_labels.append(label_name)

            def add_audio(item, role):
                if not item.get('path') or not item.get('enabled') or item.get('mute'):
                    return
                placement = float(item.get('start', 0))
                local_start = placement - start
                source_in = max(0.0, -local_start)
                delay = max(0.0, local_start)
                available = max(0.0, min(float(item.get('duration') or 0) - source_in, duration - delay))
                if available <= .01:
                    return
                input_index = len(inputs) // 2
                inputs.extend(['-i', str(self.workspace.path(item['path']))])
                label_name = f'a{len(audio_labels)}'
                chain = (f'[{input_index}:a]atrim=start={source_in}:duration={available},asetpts=PTS-STARTPTS,'
                         f'aresample=48000,volume={float(item.get("volume", 1))}')
                fade_in = min(float(item.get('fade_in', 0)), available / 2)
                fade_out = min(float(item.get('fade_out', 0)), available / 2)
                if fade_in > 0: chain += f',afade=t=in:st=0:d={fade_in}'
                if fade_out > 0: chain += f',afade=t=out:st={max(0, available-fade_out)}:d={fade_out}'
                milliseconds = round(delay * 1000)
                chain += f',adelay={milliseconds}|{milliseconds},apad,atrim=duration={duration}[{label_name}]'
                filters.append(chain); audio_labels.append(label_name)

            for dialogue in plan['dialogues']:
                if dialogue['strategy'] == 'independent': add_audio(dialogue, 'dialogue')
            for background in plan['backgrounds']: add_audio(background, 'background')
            command = [media_tool('ffmpeg'), '-y', '-v', 'error', *inputs]
            if not audio_labels:
                silent_index = len(inputs) // 2
                command.extend(['-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo'])
                filters.append(f'[{silent_index}:a]atrim=duration={duration},asetpts=PTS-STARTPTS[a]')
            elif len(audio_labels) == 1:
                filters.append(f'[{audio_labels[0]}]anull[a]')
            else:
                joined = ''.join(f'[{name}]' for name in audio_labels)
                filters.append(f'{joined}amix=inputs={len(audio_labels)}:duration=longest:normalize=0,'
                               f'atrim=duration={duration}[a]')
            command += ['-filter_complex', ';'.join(filters), '-map', '[v]', '-map', '[a]',
                        '-t', str(duration), '-c:v', 'libx264', '-preset',
                        'ultrafast' if quality == 'preview' else 'medium',
                        '-crf', '23' if quality == 'preview' else '19', '-pix_fmt', 'yuv420p',
                        '-c:a', 'aac', '-ar', '48000', '-ac', '2', '-movflags', '+faststart', str(part)]
            self._run(command); parts.append(part)
        listing = folder / 'concat.txt'
        listing.write_text('\n'.join("file '"+part.name+"'" for part in parts), encoding='utf-8')
        self._run([media_tool('ffmpeg'), '-y', '-v', 'error', '-f', 'concat', '-safe', '1',
                   '-i', str(listing), '-c', 'copy', '-movflags', '+faststart', str(target)])
        info = probe(target, 'video')
        probe(target, 'audio')
        if abs(info['duration']-resolved['duration']) > 0.18 + len(parts)/24:
            raise ValueError('输出时长与装配计划不一致')
        for part in parts:
            part.unlink()
        listing.unlink()
        write_json(folder / 'manifest.json', resolved)
        write_srt(folder / 'subtitles.srt', resolved['subtitles'])
        self.state[quality] = dict(path=target.relative_to(self.workspace.root).as_posix(),
                                   fingerprint=signature, sha256=sha(target))
        self.workspace._save()
        return target

    def preview(self):
        return self._render('preview')

    def output(self):
        return self._render('output')

    def handoff(self):
        import opentimelineio as otio
        resolved = self.resolve()
        if resolved['errors']:
            raise ValueError('\n'.join(resolved['errors']))
        output = self.output()
        folder = self.workspace.path(f'finishing/{self.chapter_id}/handoff/{resolved["fingerprint"]}')
        folder.mkdir(parents=True, exist_ok=True); (folder / 'media').mkdir(exist_ok=True)
        rt = otio.opentime.RationalTime; tr = otio.opentime.TimeRange; rate = 24
        timeline = otio.schema.Timeline(name=self.chapter().title,
            metadata={'aigc': {'chapter_id': self.chapter_id, 'fixture_or_user_media': True,
                               'audio_policy': 'explicit native / independent / none',
                               'subtitles': resolved['subtitles'], 'subtitle_sidecar': 'subtitles.srt'}})
        video = otio.schema.Track(name='Current Shot Video', kind=otio.schema.TrackKind.Video)
        native = otio.schema.Track(name='Native Video Audio', kind=otio.schema.TrackKind.Audio)
        dialogue_track = otio.schema.Track(name='Independent Dialogue', kind=otio.schema.TrackKind.Audio)
        background_track = otio.schema.Track(name='Background Audio', kind=otio.schema.TrackKind.Audio)
        paths = {}; cursors = {'dialogue': 0.0, 'background': 0.0}; timeline_cursor = 0.0

        def portable(path, checksum):
            src = self.workspace.path(path); relative = f'media/{checksum}{src.suffix.lower()}'
            dest = folder / relative
            if not dest.exists() or sha(dest) != checksum: shutil.copy2(src, dest)
            paths[path] = relative; return relative

        def append_at(track, cursor_key, name, relative, start, source_in, duration, metadata):
            cursor = cursors[cursor_key]
            if start > cursor + .001:
                track.append(otio.schema.Gap(source_range=tr(rt(0, rate), rt((start-cursor)*rate, rate))))
            elif start < cursor - .001:
                metadata = deepcopy(metadata); metadata['aigc']['overlap_adjusted_from'] = start
                start = cursor
            track.append(otio.schema.Clip(name=name,
                media_reference=otio.schema.ExternalReference(target_url=relative),
                source_range=tr(rt(source_in*rate, rate), rt(duration*rate, rate)), metadata=metadata))
            cursors[cursor_key] = start + duration

        for clip in resolved['clips']:
            relative = portable(clip['path'], clip['sha256'])
            source_range = tr(rt(clip['source_in']*rate,rate), rt(clip['duration']*rate,rate))
            metadata = {'aigc': {'shot_id': clip['shot_id'], 'segment_id': clip['segment_id'],
                                 'candidate_id': clip['candidate_id'], 'volume': clip['volume'],
                                 'mute': clip['mute'], 'audio_strategy':
                                 [d['strategy'] for d in clip['audio_plan']['dialogues']]}}
            video.append(otio.schema.Clip(name=f'{clip["shot_number"]} {clip["shot_title"]}',
                         media_reference=otio.schema.ExternalReference(target_url=relative),
                         source_range=source_range, metadata=metadata))
            if clip['audio_plan']['native_audio'] and clip['has_audio'] and not clip['mute']:
                native.append(otio.schema.Clip(name=f'{clip["shot_number"]} native audio',
                              media_reference=otio.schema.ExternalReference(target_url=relative),
                              source_range=source_range, metadata=metadata))
            else:
                native.append(otio.schema.Gap(source_range=tr(rt(0,rate),rt(clip['duration']*rate,rate))))
            for item in clip['audio_plan']['dialogues']:
                if item['strategy'] != 'independent' or not item['path'] or not item['enabled'] or item['mute']: continue
                source_in = max(0.0, clip['source_in'] - item['start'])
                start_at = timeline_cursor + max(0.0, item['start'] - clip['source_in'])
                duration = max(0.0, min(item['duration']-source_in, clip['duration']-(start_at-timeline_cursor)))
                if duration <= .01: continue
                candidate = self.service.candidate(item['candidate_id'])
                audio_relative = portable(item['path'], candidate.sha256)
                append_at(dialogue_track, 'dialogue', f'{item["speaker"]} · {item["text"]}', audio_relative,
                          start_at, source_in, duration,
                          {'aigc': {'role': 'dialogue', 'dialogue_id': item['dialogue_id'],
                                    'candidate_id': item['candidate_id'], 'volume': item['volume'],
                                    'fade_in': item['fade_in'], 'fade_out': item['fade_out']}})
            for item in clip['audio_plan']['backgrounds']:
                if not item['path'] or not item['enabled'] or item['mute']: continue
                source_in = max(0.0, clip['source_in'] - item['start'])
                start_at = timeline_cursor + max(0.0, item['start'] - clip['source_in'])
                duration = max(0.0, min(item['duration']-source_in, clip['duration']-(start_at-timeline_cursor)))
                if duration <= .01: continue
                candidate = self.service.candidate(item['candidate_id'])
                audio_relative = portable(item['path'], candidate.sha256)
                append_at(background_track, 'background', item['text'], audio_relative, start_at, source_in, duration,
                          {'aigc': {'role': 'background', 'background_id': item['background_id'],
                                    'candidate_id': item['candidate_id'], 'volume': item['volume'],
                                    'fade_in': item['fade_in'], 'fade_out': item['fade_out']}})
            timeline_cursor += clip['duration']
        for track, key in ((dialogue_track, 'dialogue'), (background_track, 'background')):
            if cursors[key] < resolved['duration']:
                track.append(otio.schema.Gap(source_range=tr(rt(0,rate),rt((resolved['duration']-cursors[key])*rate,rate))))
        timeline.tracks.extend([video, native, dialogue_track, background_track])
        otio.adapters.write_to_file(timeline, str(folder / 'timeline.otio'))
        restored = otio.adapters.read_from_file(str(folder / 'timeline.otio'))
        if not timeline.is_equivalent_to(restored): raise ValueError('OTIO 回读不一致')
        shutil.copy2(output, folder / 'chapter-output.mp4')
        write_srt(folder / 'subtitles.srt', resolved['subtitles'])
        write_json(folder / 'manifest.json', dict(chapter_id=self.chapter_id,
                   fingerprint=resolved['fingerprint'], clips=resolved['clips'],
                   subtitles=resolved['subtitles'], paths=paths, round_trip=True,
                   model_calls=0, model_cost=0))
        (folder / 'README.txt').write_text(
            'V0.2 Chapter Finishing / local media\n'
            'timeline.otio contains video, native audio, independent dialogue and background tracks.\n'
            'subtitles.srt is UTF-8 and derived from Production Script dialogue with saved manual edits.\n'
            'chapter-output.mp4 is the authoritative rendered playback for this assembly.\n'
            'Clip volume, mute and fades are recorded in aigc metadata; verify routing in the NLE.\n'
            'Actual Resolve/Premiere import is not verified. No AI model call or paid generation.\n',
            encoding='utf-8')
        return folder
