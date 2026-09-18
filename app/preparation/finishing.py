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
from .workspace import Workspace, sha


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()


class ChapterFinishing:
    def __init__(self, workspace: Workspace, chapter_id: str):
        self.workspace = workspace
        self.service = ProductionService(workspace)
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
            state[self.chapter_id] = {'segments': [], 'known_shots': [], 'selected': None, 'version': 1, 'preview': None, 'output': None}
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
                clips.append(dict(segment_id=segment['id'], shot_id=shot.id, shot_number=shot.number,
                                  shot_title=shot.title, shot_text=shot.text, candidate_id=candidate.id,
                                  take_number=candidate.take_number, path=candidate.media_path,
                                  sha256=candidate.sha256, source_in=start, source_out=end,
                                  duration=end-start, volume=float(segment['volume']), mute=bool(segment['mute']),
                                  has_audio=has_audio))
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
        signature = fingerprint(dict(chapter_id=self.chapter_id, segments=self.state['segments'],
                                     clips=clips, references=references))
        previous = self.state.get('preview')
        return dict(status='Blocked' if errors else 'Ready', errors=errors, warnings=warnings,
                    clips=clips, fingerprint=signature,
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
            vf = (f'[0:v]trim=start={start}:end={end},setpts=PTS-STARTPTS,'
                  f'scale={width}:{height}:force_original_aspect_ratio=decrease,'
                  f'pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,fps=24,format=yuv420p[v]')
            if clip['has_audio'] and not clip['mute']:
                af = (f'[0:a]atrim=start={start}:end={end},asetpts=PTS-STARTPTS,'
                      f'aresample=48000,volume={clip["volume"]},apad,atrim=duration={duration}[a]')
                command = [media_tool('ffmpeg'), '-y', '-v', 'error', '-i', str(source)]
            else:
                af = f'[1:a]atrim=duration={duration},asetpts=PTS-STARTPTS[a]'
                command = [media_tool('ffmpeg'), '-y', '-v', 'error', '-i', str(source),
                           '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo']
            command += ['-filter_complex', vf+';'+af, '-map', '[v]', '-map', '[a]',
                        '-t', str(duration), '-c:v', 'libx264', '-preset',
                        'ultrafast' if quality == 'preview' else 'medium',
                        '-crf', '23' if quality == 'preview' else '19',
                        '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-ar', '48000', '-ac', '2',
                        '-movflags', '+faststart', str(part)]
            self._run(command)
            parts.append(part)
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
        folder.mkdir(parents=True, exist_ok=True)
        media_folder = folder / 'media'
        media_folder.mkdir(exist_ok=True)
        rt = otio.opentime.RationalTime
        tr = otio.opentime.TimeRange
        timeline = otio.schema.Timeline(name=self.chapter().title,
            metadata={'aigc': {'chapter_id': self.chapter_id, 'fixture_or_user_media': True,
                               'audio_policy': 'embedded source; inspect track routing in NLE'}})
        video = otio.schema.Track(name='Current Shot Video', kind=otio.schema.TrackKind.Video)
        audio = otio.schema.Track(name='Source Audio', kind=otio.schema.TrackKind.Audio)
        paths = {}
        for clip in resolved['clips']:
            src = self.workspace.path(clip['path'])
            relative = f'media/{clip["sha256"]}{src.suffix.lower()}'
            dest = folder / relative
            if not dest.exists() or sha(dest) != clip['sha256']:
                shutil.copy2(src, dest)
            paths[clip['path']] = relative
            source_range = tr(rt(clip['source_in']*24,24), rt(clip['duration']*24,24))
            ref = otio.schema.ExternalReference(target_url=relative)
            metadata = {'aigc': {'shot_id': clip['shot_id'], 'segment_id': clip['segment_id'],
                                 'candidate_id': clip['candidate_id'], 'volume': clip['volume'],
                                 'mute': clip['mute']}}
            video.append(otio.schema.Clip(name=f'{clip["shot_number"]} {clip["shot_title"]}',
                                         media_reference=ref, source_range=source_range, metadata=metadata))
            if clip['has_audio'] and not clip['mute']:
                audio.append(otio.schema.Clip(name=f'{clip["shot_number"]} audio',
                                             media_reference=otio.schema.ExternalReference(target_url=relative),
                                             source_range=source_range, metadata=metadata))
            else:
                audio.append(otio.schema.Gap(source_range=tr(rt(0,24),rt(clip['duration']*24,24))))
        timeline.tracks.extend([video,audio])
        otio.adapters.write_to_file(timeline, str(folder / 'timeline.otio'))
        restored = otio.adapters.read_from_file(str(folder / 'timeline.otio'))
        if not timeline.is_equivalent_to(restored):
            raise ValueError('OTIO 回读不一致')
        shutil.copy2(output, folder / 'chapter-output.mp4')
        write_json(folder / 'manifest.json', dict(chapter_id=self.chapter_id,
                   fingerprint=resolved['fingerprint'], clips=resolved['clips'], paths=paths,
                   round_trip=True, model_calls=0, model_cost=0))
        (folder / 'README.txt').write_text(
            'V0.2 Chapter Finishing / local media\n'
            'Open timeline.otio in an NLE with OTIO support; media/ uses relative paths.\n'
            'chapter-output.mp4 is the authoritative rendered playback for this assembly.\n'
            'For source audio, mute embedded audio on the video track and use Source Audio.\n'
            'Clip volume and mute are recorded in aigc metadata; verify audio routing and levels in the NLE.\n'
            'Actual Resolve/Premiere import is not verified. No AI model call or paid generation.\n',
            encoding='utf-8')
        return folder
