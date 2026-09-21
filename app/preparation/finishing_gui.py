"""Focused Chapter Finishing workspace for the V0.2 C visual system."""
from __future__ import annotations

import subprocess
from pathlib import Path

from PySide6.QtCore import Qt, QUrl, QSize, QThread, Signal, QTimer
from PySide6.QtGui import QPixmap, QIcon, QColor, QPainter, QFont
from PySide6.QtWidgets import (
    QDialog, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QFrame,
    QListWidget, QListWidgetItem, QListView, QDoubleSpinBox, QCheckBox,
    QFileDialog, QMessageBox, QApplication, QScrollArea, QStyledItemDelegate, QStyle, QSizePolicy,
)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput, QVideoSink

from app.production import media_tool
from .finishing import ChapterFinishing
from .production import ProductionService
from .production_gui import ReviewDot
from .workspace import EXTENSIONS, sha
from .ui_copy import finishing_message, operation_message
from app.shell_theme import D_STYLE, EMBEDDED_D_STYLE


def button(caption, callback, role='quiet'):
    result = QPushButton(caption)
    result.setObjectName(role)
    result.setCursor(Qt.CursorShape.PointingHandCursor)
    result.clicked.connect(callback)
    return result


def label(caption='', role='muted'):
    result = QLabel(caption)
    result.setObjectName(role)
    return result


def poster(path, seconds=0, width=320):
    if not path:
        return QPixmap()
    try:
        data = subprocess.run([media_tool('ffmpeg'), '-v', 'error', '-ss', str(seconds),
                               '-i', str(path), '-frames:v', '1', '-vf', f'scale={width}:-1',
                               '-f', 'image2pipe', '-vcodec', 'png', '-'],
                              capture_output=True, timeout=20, check=True).stdout
        pix = QPixmap()
        pix.loadFromData(data)
        return pix
    except (ValueError, OSError, subprocess.SubprocessError):
        return QPixmap()


class SegmentDelegate(QStyledItemDelegate):
    def sizeHint(self, option, index):
        return QSize(174, 118)

    def paint(self, painter, option, index):
        number, title, status = index.data(Qt.ItemDataRole.UserRole + 1)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        rect = option.rect.adjusted(2, 2, -3, -2)
        painter.save()
        if selected:
            painter.fillRect(rect, QColor('#2b4358'))
        icon = index.data(Qt.ItemDataRole.DecorationRole)
        pix = icon.pixmap(QSize(150, 68)) if icon else QPixmap()
        if not pix.isNull():
            painter.drawPixmap(rect.left()+9, rect.top()+5, 150, 68, pix)
        else:
            painter.fillRect(rect.left()+9, rect.top()+5, 150, 68, QColor('#101b2a'))
        painter.setFont(QFont('Microsoft YaHei UI', 9))
        painter.setPen(QColor('#e4eef4' if selected else '#c9d9e5'))
        painter.drawText(rect.left()+9, rect.top()+91, f'{number}  {title[:11]}')
        painter.setFont(QFont('Segoe UI', 8))
        painter.setPen(QColor('#d6ae78' if status in ('未选视频', '裁切无效', '文件不可用', '无法使用') else '#90a8ba'))
        painter.drawText(rect.left()+9, rect.top()+108, status)
        painter.restore()


class RenderWorker(QThread):
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, operation):
        super().__init__()
        self.operation = operation

    def run(self):
        try:
            self.done.emit(self.operation())
        except Exception as exc:
            self.failed.emit(str(exc))


class ShotCandidateDialog(QDialog):
    def __init__(self, host, shot_id, integrated=False):
        super().__init__(host)
        self.host = host
        self.integrated = integrated
        self.service = ProductionService(host.workspace)
        self.preview_source = QPixmap()
        self.chapter, self.shot = self.service.shot_context(shot_id)
        self.setWindowTitle(f'镜头 {self.shot.number} · 视频')
        self.resize(760, 610)
        self.setMinimumSize(650, 520)
        self.setStyleSheet(host.styleSheet() + """
            QDialog { background:#101a28; color:#dae6ef; }
            QLabel#candidateHero { font-size:23px; color:#eef4f8; }
            QLabel#candidateMuted { color:#91a8ba; font-size:11px; }
            QListWidget#shotCandidates { background:#162536; border:0; padding:7px; }
            QListWidget#shotCandidates::item { min-height:46px; padding:8px; }
            QListWidget#shotCandidates::item:selected { background:#263c52; color:#eef4f8; }
        """)
        if self.integrated:
            self.setStyleSheet(D_STYLE + EMBEDDED_D_STYLE)
        root = QVBoxLayout(self)
        root.setContentsMargins(26, 21, 26, 18)
        root.setSpacing(13)
        root.addWidget(label(f'{self.shot.number}  {self.shot.title}', 'candidateHero'))
        root.addWidget(label('未配置视频生成服务', 'candidateMuted'))
        self.current_text = label('', 'candidateMuted')
        root.addWidget(self.current_text)
        self.preview = QLabel('尚无镜头视频')
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumHeight(210)
        self.preview.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
        self.preview.setStyleSheet('background:#0c1725; color:#829aae; border-radius:4px;')
        root.addWidget(self.preview, 1)
        actions = QHBoxLayout()
        self.import_button = button('导入视频  ↗', self.import_media, 'tool')
        actions.addWidget(self.import_button)
        actions.addWidget(button('打开媒体  ↗', self.open_media, 'quiet'))
        actions.addStretch()
        self.dots = {}
        for state in ('green', 'yellow', 'red'):
            dot = ReviewDot(state)
            dot.clicked.connect(lambda checked=False, value=state: self.review(value))
            actions.addWidget(dot)
            self.dots[state] = dot
        actions.addSpacing(10)
        self.bind_button = button('设为当前  ↗', self.bind, 'primary')
        actions.addWidget(self.bind_button)
        root.addLayout(actions)
        self.list = QListWidget()
        self.list.setObjectName('shotCandidates')
        self.list.currentItemChanged.connect(lambda *_: self.selection_changed())
        root.addWidget(self.list)
        root.addWidget(button('返回来源  ↗', self.go_back, 'quiet'))
        self.refresh()

    def go_back(self):
        if self.integrated and getattr(self.host, "shell", None):
            self.host.shell.return_route()
        else:
            self.accept()

    def selected_id(self):
        item = self.list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def guard(self, operation):
        try:
            return operation()
        except Exception as exc:
            QMessageBox.warning(self, '操作未完成', finishing_message(operation_message(str(exc))))
            return None

    def refresh(self, prefer=None):
        candidates = self.service.shot_candidates(self.shot.id)
        current = self.service.current_shot(self.shot.id)
        self.current_text.setText(
            f'当前使用 · 版本 {self.service.candidate(current).take_number:02d}' if current else
            '尚未选用视频')
        self.list.blockSignals(True)
        self.list.clear()
        for candidate in candidates:
            item = QListWidgetItem(f'版本 {candidate.take_number:02d}')
            item.setData(Qt.ItemDataRole.UserRole, candidate.id)
            color = ReviewDot.COLORS.get(candidate.review_state, '#91a6b9')
            pix = QPixmap(11, 11)
            pix.fill(Qt.GlobalColor.transparent)
            from PySide6.QtGui import QPainter, QColor
            painter = QPainter(pix)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setBrush(QColor(color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(1, 1, 9, 9)
            painter.end()
            item.setIcon(QIcon(pix))
            self.list.addItem(item)
        index = next((i for i in range(self.list.count())
                      if self.list.item(i).data(Qt.ItemDataRole.UserRole) == prefer), 0)
        self.list.setCurrentRow(index if self.list.count() else -1)
        self.list.blockSignals(False)
        self.selection_changed()

    def selection_changed(self):
        candidate_id = self.selected_id()
        if not candidate_id:
            self.preview.clear()
            self.preview.setText('尚无镜头视频')
            self.bind_button.setEnabled(False)
            for dot in self.dots.values(): dot.setEnabled(False)
            return
        candidate = self.service.candidate(candidate_id)
        path = self.service.preview_path(candidate_id)
        pix = poster(path, width=700)
        self.preview_source = pix
        self.fit_preview()
        for state, dot in self.dots.items():
            dot.setEnabled(True)
            dot.setChecked(state == candidate.review_state)
        self.bind_button.setEnabled(candidate.review_state == 'green' and
            self.service.available(candidate_id) and candidate_id != self.service.current_shot(self.shot.id))

    def fit_preview(self):
        if self.preview_source.isNull():
            self.preview.setPixmap(QPixmap())
            self.preview.setText('媒体不可预览')
        else:
            self.preview.setPixmap(self.preview_source.scaled(
                self.preview.size(), Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'preview_source') and hasattr(self, 'preview'):
            self.fit_preview()

    def import_media(self):
        filters = ' '.join('*'+suffix for suffix in sorted(EXTENSIONS['video']))
        path, _ = QFileDialog.getOpenFileName(self, '导入镜头视频', '', f'视频 ({filters})')
        if path:
            result = self.guard(lambda: self.service.import_shot_candidate(self.shot.id, path))
            if result: self.refresh(result.id)

    def review(self, state):
        candidate_id = self.selected_id()
        if candidate_id and self.guard(lambda: self.service.review(candidate_id, state)):
            self.refresh(candidate_id)

    def bind(self):
        candidate_id = self.selected_id()
        if candidate_id and self.guard(lambda: self.service.bind_shot(candidate_id)):
            self.refresh(candidate_id)

    def open_media(self):
        candidate_id = self.selected_id()
        if candidate_id:
            path = self.service.preview_path(candidate_id)
            if path:
                from PySide6.QtGui import QDesktopServices
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))


class ChapterFinishingDialog(QDialog):
    def __init__(self, host, chapter_id, selected_shot_id=None, integrated=False):
        super().__init__(host)
        self.host = host
        self.integrated = integrated
        self.finishing = ChapterFinishing(host.workspace, chapter_id)
        self.worker = None
        self._updating = False
        self._posters = {}
        self.poster_source = QPixmap()
        self.live_source = QPixmap()
        self.show_video = False
        self.setWindowTitle('章节轻剪  ·  '+self.finishing.chapter().title)
        self.resize(min(1380, max(1000, host.width()-38)), min(900, max(660, host.height()-28)))
        self.setMinimumSize(970, 635)
        self.setStyleSheet(host.styleSheet() + """
            QDialog { background:#101b2b; color:#dce8f1; }
            QLabel#finishingTitle { font-size:25px; font-weight:500; color:#eef4f8; }
            QLabel#finishingMuted { font-size:11px; color:#92aabd; }
            QLabel#finishingShot { font-size:18px; color:#e9f1f7; }
            QFrame#finishingInspector { background:#182737; border-radius:5px; }
            QListWidget#segmentStrip { background:#152333; border:0; padding:7px; }
            QListWidget#segmentStrip::item { padding:0; margin:0; border-radius:3px; }
            QListWidget#segmentStrip::item:selected { background:#2b4358; color:#f3f7fa; }
            QLabel#previewPoster { background:#0b1522; color:#8ea5b8; }
            QDoubleSpinBox { background:#101c2b; color:#e3edf4; border:1px solid #34495a;
                             padding:6px; border-radius:3px; }
            QCheckBox { color:#cad8e3; spacing:7px; }
        """)
        if self.integrated:
            self.setStyleSheet(D_STYLE + EMBEDDED_D_STYLE)
        self.build()
        segments = self.finishing.segments()
        chosen = next((s['id'] for s in segments if s['shot_id'] == selected_shot_id),
                      self.finishing.selected())
        self.refresh(chosen)

    def build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(26, 18, 26, 16)
        root.setSpacing(12)
        top = QHBoxLayout()
        chapter = self.finishing.chapter()
        title = QVBoxLayout()
        title.addWidget(label(f'第 {chapter.number} 章', 'finishingMuted'))
        title.addWidget(label(chapter.title, 'finishingTitle'))
        top.addLayout(title, 1)
        self.status = label('', 'finishingMuted')
        top.addWidget(self.status, 0, Qt.AlignmentFlag.AlignVCenter)
        top.addWidget(button('返回来源  ↗', self.go_back, 'quiet'))
        root.addLayout(top)
        body = QHBoxLayout()
        body.setSpacing(18)
        media = QVBoxLayout()
        media.setSpacing(10)
        self.poster = QLabel('当前章节尚无可播放预览')
        self.poster.setObjectName('previewPoster')
        self.poster.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.poster.setMinimumHeight(250)
        self.poster.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.sink = QVideoSink(self)
        self.player.setAudioOutput(self.audio)
        self.player.setVideoSink(self.sink)
        self.sink.videoFrameChanged.connect(self._video_frame)
        self.player.mediaStatusChanged.connect(self._media_status)
        media.addWidget(self.poster, 1)
        self.caption = label('选择片段，查看当前镜头结果', 'finishingMuted')
        media.addWidget(self.caption)
        controls = QHBoxLayout()
        controls.addWidget(button('播放 / 暂停', self.play, 'tool'))
        controls.addWidget(button('从头播放', self.restart, 'quiet'))
        controls.addStretch()
        self.preview_button = button('生成预览  ↗', self.build_preview, 'primary')
        controls.addWidget(self.preview_button)
        media.addLayout(controls)
        body.addLayout(media, 3)
        inspector = QFrame()
        inspector.setObjectName('finishingInspector')
        inspector.setMinimumWidth(278)
        side = QVBoxLayout(inspector)
        side.setContentsMargins(18, 16, 18, 14)
        side.setSpacing(9)
        side.addWidget(label('当前镜头', 'finishingMuted'))
        self.shot_title = label('选择片段', 'finishingShot')
        side.addWidget(self.shot_title)
        self.take = label('', 'finishingMuted')
        side.addWidget(self.take)
        side.addWidget(button('对白、声音与字幕  ↗', self.open_sound, 'tool'))
        side.addSpacing(10)
        side.addWidget(label('起点 / 终点', 'finishingMuted'))
        ranges = QHBoxLayout()
        self.trim_in = QDoubleSpinBox()
        self.trim_out = QDoubleSpinBox()
        for control in (self.trim_in, self.trim_out):
            control.setRange(0, 9999)
            control.setDecimals(2)
            control.setSingleStep(.1)
            control.setSuffix(' s')
            ranges.addWidget(control)
        self.trim_out.setSpecialValueText('片尾')
        side.addLayout(ranges)
        side.addWidget(button('应用裁切', self.apply_trim, 'tool'))
        side.addSpacing(8)
        side.addWidget(label('切分 / 声音', 'finishingMuted'))
        splitrow = QHBoxLayout()
        self.split_at = QDoubleSpinBox()
        self.split_at.setRange(0, 9999)
        self.split_at.setDecimals(2)
        self.split_at.setSuffix(' s')
        splitrow.addWidget(self.split_at)
        splitrow.addWidget(button('切分', self.split, 'quiet'))
        side.addLayout(splitrow)
        volume = QHBoxLayout()
        self.volume = QDoubleSpinBox()
        self.volume.setRange(0, 2)
        self.volume.setDecimals(2)
        self.volume.setSingleStep(.1)
        self.volume.setSuffix(' ×')
        volume.addWidget(self.volume)
        volume.addWidget(button('应用音量', self.apply_volume, 'quiet'))
        side.addLayout(volume)
        self.mute = QCheckBox('静音')
        self.enabled = QCheckBox('包含在章节中')
        self.mute.toggled.connect(lambda value: self.apply_toggle('mute', value))
        self.enabled.toggled.connect(lambda value: self.apply_toggle('enabled', value))
        side.addWidget(self.mute)
        side.addWidget(self.enabled)
        side.addSpacing(10)
        side.addWidget(button('更换视频  ↗', self.open_candidate, 'tool'))
        side.addWidget(button('修改提示词  ↗', self.open_prompt, 'quiet'))
        side.addWidget(button('修改镜头  ↗', self.open_script, 'quiet'))
        side.addStretch()
        self.inspector_scroll = QScrollArea()
        self.inspector_scroll.setWidgetResizable(True)
        self.inspector_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.inspector_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.inspector_scroll.setFixedWidth(302)
        self.inspector_scroll.setWidget(inspector)
        body.addWidget(self.inspector_scroll)
        root.addLayout(body, 1)
        strip_head = QHBoxLayout()
        strip_head.addWidget(label('本章镜头', 'finishingMuted'))
        strip_head.addStretch()
        strip_head.addWidget(button('向前', lambda: self.move(-1), 'quiet'))
        strip_head.addWidget(button('向后', lambda: self.move(1), 'quiet'))
        strip_head.addWidget(button('移出章节', self.remove, 'quiet'))
        root.addLayout(strip_head)
        self.strip = QListWidget()
        self.strip.setObjectName('segmentStrip')
        self.strip.setViewMode(QListView.ViewMode.IconMode)
        self.strip.setFlow(QListView.Flow.LeftToRight)
        self.strip.setWrapping(False)
        self.strip.setMovement(QListView.Movement.Static)
        self.strip.setGridSize(QSize(174, 118))
        self.strip.setIconSize(QSize(150, 68))
        self.strip.setItemDelegate(SegmentDelegate(self.strip))
        self.strip.setFixedHeight(129)
        self.strip.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.strip.currentItemChanged.connect(lambda *_: self.selection_changed())
        root.addWidget(self.strip)
        foot = QHBoxLayout()
        self.message = label('', 'finishingMuted')
        foot.addWidget(self.message, 1)
        self.output_button = button('导出成片  ↗', self.build_output, 'tool')
        foot.addWidget(self.output_button)
        self.handoff_button = button('交给专业剪辑  ↗', self.build_handoff, 'quiet')
        foot.addWidget(self.handoff_button)
        root.addLayout(foot)

    def selected_segment(self):
        item = self.strip.currentItem()
        if not item:
            return None
        sid = item.data(Qt.ItemDataRole.UserRole)
        return next((s for s in self.finishing.segments() if s['id'] == sid), None)

    def guard(self, operation):
        try:
            return operation()
        except Exception as exc:
            QMessageBox.warning(self, '操作未完成', finishing_message(operation_message(str(exc))))
            return None

    def refresh(self, prefer=None):
        resolved = self.finishing.resolve()
        if resolved['stale']:
            self.player.stop()
            self.player.setSource(QUrl())
            self.show_video = False
        clips = {c['segment_id']: c for c in resolved['clips']}
        shots = {s.id: s for s in self.finishing.chapter().shots}
        self.strip.blockSignals(True)
        self.strip.clear()
        for segment in self.finishing.segments():
            shot = shots.get(segment['shot_id'])
            clip = clips.get(segment['id'])
            number = shot.number if shot else '—'
            title = shot.title if shot else '剧本已移除'
            if not segment['enabled']:
                status = '已移出'
            elif clip:
                status = f'版本 {clip["take_number"]:02d}  ·  {clip["duration"]:.1f}秒'
            else:
                problem = next((message for message in resolved['errors']
                                if message.startswith(f'Shot {number}:')), '')
                status = ('未选视频' if '没有正式 Current 视频' in problem else
                          '裁切无效' if 'Trim' in problem else
                          '文件不可用' if '不可用' in problem or '不存在' in problem else
                          '无法使用')
            item = QListWidgetItem(f'{number}  {title[:10]}\n{status}')
            item.setData(Qt.ItemDataRole.UserRole, segment['id'])
            item.setData(Qt.ItemDataRole.UserRole + 1, (number, title, status))
            if clip:
                key = (clip['candidate_id'], clip['source_in'])
                if key not in self._posters:
                    self._posters[key] = poster(self.host.workspace.path(clip['path']), clip['source_in'], 154)
                if not self._posters[key].isNull():
                    item.setIcon(QIcon(self._posters[key]))
            self.strip.addItem(item)
        target = prefer or self.finishing.selected()
        index = next((i for i in range(self.strip.count())
                      if self.strip.item(i).data(Qt.ItemDataRole.UserRole) == target), 0)
        self.strip.setCurrentRow(index if self.strip.count() else -1)
        self.strip.blockSignals(False)
        self.status.setText(f'{len(clips)} 段  ·  {resolved["duration"]:.1f}秒'
                            + ('  ·  无法预览' if resolved['errors'] else '')
                            + ('  ·  预览待更新' if resolved['stale'] and not resolved['errors'] else ''))
        self.preview_button.setEnabled(not resolved['errors'])
        self.output_button.setEnabled(not resolved['errors'])
        self.handoff_button.setEnabled(not resolved['errors'])
        self.selection_changed()
        if resolved['errors']:
            self.message.setText('  /  '.join(list(dict.fromkeys(finishing_message(item) for item in resolved['errors']))[:2]))
        elif resolved['warnings']:
            self.message.setText('  /  '.join(list(dict.fromkeys(finishing_message(item) for item in resolved['warnings']))[:2]))
        else:
            self.message.setText('')

    def selection_changed(self):
        segment = self.selected_segment()
        self._updating = True
        if not segment:
            self.shot_title.setText('选择片段')
            self.take.setText('')
            self._updating = False
            return
        self.finishing.select(segment['id'])
        shot = next((s for s in self.finishing.chapter().shots if s.id == segment['shot_id']), None)
        self.shot_title.setText(f'{shot.number}  {shot.title}' if shot else '历史镜头')
        clip = next((c for c in self.finishing.resolve()['clips'] if c['segment_id'] == segment['id']), None)
        self.take.setText(f'版本 {clip["take_number"]:02d}' if clip else
                          '尚未选用视频' if not self.finishing.service.current_shot(segment['shot_id']) else '视频不可用')
        self.trim_in.setValue(float(segment['trim_in']))
        self.trim_out.setValue(float(segment['trim_out'] or 0))
        self.split_at.setValue((float(segment['trim_in']) + (clip['source_out'] if clip else 0))/2
                               if clip else 0)
        self.volume.setValue(float(segment['volume']))
        self.mute.setChecked(bool(segment['mute']))
        self.enabled.setChecked(bool(segment['enabled']))
        if clip:
            pix = poster(self.host.workspace.path(clip['path']), clip['source_in'], 900)
            self.poster_source = pix
            self.fit_poster()
            self.caption.setText(f'{clip["source_in"]:.2f}–{clip["source_out"]:.2f}秒')
        else:
            self.poster_source = QPixmap()
            self.poster.setPixmap(QPixmap())
            self.poster.setText('尚未选用视频' if not self.finishing.service.current_shot(segment['shot_id']) else '视频不可用')
            self.caption.setText('')
        self.show_video = False
        self.player.stop()
        self._updating = False

    def fit_poster(self):
        source = self.live_source if self.show_video and not self.live_source.isNull() else self.poster_source
        if not source.isNull():
            self.poster.setPixmap(source.scaled(
                self.poster.size(), Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))

    def _video_frame(self, frame):
        if self.show_video and frame.isValid():
            image = frame.toImage()
            if not image.isNull():
                self.live_source = QPixmap.fromImage(image)
                self.fit_poster()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'poster') and hasattr(self, 'poster_source'):
            QTimer.singleShot(0, self.fit_poster)

    def _edit(self, operation, selected=None):
        result = self.guard(operation)
        self.refresh(selected)
        return result

    def apply_trim(self):
        segment = self.selected_segment()
        if segment:
            self._edit(lambda: self.finishing.update(segment['id'], trim_in=self.trim_in.value(),
                       trim_out=self.trim_out.value() or None), segment['id'])

    def apply_volume(self):
        segment = self.selected_segment()
        if segment:
            self._edit(lambda: self.finishing.update(segment['id'], volume=self.volume.value()), segment['id'])

    def apply_toggle(self, field, value):
        if self._updating:
            return
        segment = self.selected_segment()
        if segment:
            self._edit(lambda: self.finishing.update(segment['id'], **{field: value}), segment['id'])

    def split(self):
        segment = self.selected_segment()
        if segment:
            result = self.guard(lambda: self.finishing.split(segment['id'], self.split_at.value()))
            self.refresh(result)

    def move(self, offset):
        segment = self.selected_segment()
        if segment:
            self._edit(lambda: self.finishing.move(segment['id'], offset), segment['id'])

    def remove(self):
        segment = self.selected_segment()
        if segment:
            self._edit(lambda: self.finishing.remove(segment['id']))

    def open_sound(self):
        segment = self.selected_segment()
        if segment:
            from .sound_gui import SoundDialog
            SoundDialog(self.host, segment['shot_id']).exec()
            self.refresh(segment['id'])

    def open_candidate(self):
        segment = self.selected_segment()
        if segment and self.integrated and getattr(self.host, "shell", None):
            self.host.shell.navigate("production", chapter_id=self.finishing.chapter_id,
                shot_id=segment["shot_id"], object_type="shot_current",
                object_id=segment["shot_id"], deep_link=True, reason="成片缺少 Current")
        elif segment:
            ShotCandidateDialog(self.host, segment['shot_id']).exec()
            self.host.refresh()
            self.refresh(segment['id'])

    def open_prompt(self):
        segment = self.selected_segment()
        if segment:
            from .prompt_gui import PromptDialog
            PromptDialog(self.host, segment['shot_id'], media='video').exec()
            self.refresh(segment['id'])

    def open_script(self):
        segment = self.selected_segment()
        if not segment:
            return
        shot = next((s for s in self.finishing.chapter().shots if s.id == segment['shot_id']), None)
        if shot and self.integrated and getattr(self.host, "shell", None):
            self.host.shell.navigate("creative", chapter_id=self.finishing.chapter_id,
                shot_id=shot.id, object_type="shot", object_id=shot.id,
                deep_link=True, reason="从成片修改镜头")
        elif shot:
            self.host.chapter_id = self.finishing.chapter_id
            self.host.shot_id = shot.id
            self.host.refresh()
            self.host.show_source_line(shot.line)
            self.accept()

    def _start(self, caption, operation, callback):
        if self.worker and self.worker.isRunning():
            return
        self.message.setText(caption)
        self.preview_button.setEnabled(False)
        self.output_button.setEnabled(False)
        self.handoff_button.setEnabled(False)
        QApplication.processEvents()
        self.worker = RenderWorker(operation)
        self.worker.done.connect(lambda result: self._done(result, callback))
        self.worker.failed.connect(self._failed)
        self.worker.start()

    def _done(self, result, callback):
        self.refresh(self.finishing.selected())
        callback(Path(result))

    def _failed(self, reason):
        QMessageBox.warning(self, '媒体构建未完成', finishing_message(reason))
        self.refresh(self.finishing.selected())

    def build_preview(self):
        self._start('正在生成预览…', self.finishing.preview, self._preview_ready)

    def _preview_ready(self, path):
        self.player.setSource(QUrl.fromLocalFile(str(path)))
        self.show_video = True
        self.player.play()
        self.message.setText('预览已生成')

    def build_output(self):
        self._start('正在输出章节…', self.finishing.output,
                    lambda path: self.message.setText('成片已导出'))

    def build_handoff(self):
        self._start('正在准备剪辑交接…', self.finishing.handoff,
                    lambda path: self.message.setText('剪辑交接文件已创建'))

    def play(self):
        if self.player.source().isEmpty():
            record = self.finishing.state.get('preview')
            if not record or record.get('fingerprint') != self.finishing.resolve()['fingerprint']:
                self.build_preview()
                return
            path = self.host.workspace.path(record['path'])
            if not path.is_file() or sha(path) != record.get('sha256'):
                self.build_preview()
                return
            self.player.setSource(QUrl.fromLocalFile(str(path)))
        self.show_video = True
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def restart(self):
        if self.player.source().isEmpty():
            self.play()
        else:
            self.show_video = True
            self.player.setPosition(0)
            self.player.play()

    def _media_status(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.player.pause()

    def go_back(self):
        if self.integrated and getattr(self.host, "shell", None):
            self.host.shell.return_route()
        else:
            self.accept()

    def accept(self):
        if self.worker and self.worker.isRunning():
            self.message.setText('媒体构建完成后再返回准备。')
            return
        self.player.stop()
        super().accept()

    def reject(self):
        if self.worker and self.worker.isRunning():
            self.message.setText('媒体构建完成后再返回准备。')
            return
        self.player.stop()
        super().reject()

    def closeEvent(self, event):
        self.player.stop()
        if self.worker and self.worker.isRunning():
            event.ignore()
            return
        super().closeEvent(event)
