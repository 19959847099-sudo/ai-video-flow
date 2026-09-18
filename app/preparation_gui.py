"""V0.2 chapter preparation workspace. Run: python -m app.preparation_gui."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from PySide6.QtCore import Qt, QTimer, QThread, Signal, QUrl, QLockFile, QSize
from PySide6.QtGui import QFont, QPixmap, QDesktopServices, QShortcut, QKeySequence, QIcon
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame, QLabel, QPushButton, QVBoxLayout,
    QHBoxLayout, QSplitter, QComboBox, QListWidget, QListWidgetItem, QScrollArea,
    QFileDialog, QMessageBox, QDialog, QDialogButtonBox, QSizePolicy,
)

from .core import write_json
from .preparation.script import KINDS, parse
from .preparation.workspace import Workspace, EXTENSIONS
from .preparation.visuals import STYLE, ScriptEditor, Atmosphere, FilmMark, ShotDelegate

STATUS = {'resolved': ('就绪', '#9bcbbd'), 'missing': ('缺失', '#d7b782'),
          'unresolved': ('待确认', '#e3a9a6'), 'changed': ('已变更', '#baa9de')}
SYMBOLS = {'image': '▧', 'audio': '≋', 'video': '▷'}


def label(text='', name=None, wrap=False):
    widget = QLabel(text)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    if name: widget.setObjectName(name)
    widget.setWordWrap(wrap)
    return widget


def button(text, action, name=None):
    widget = QPushButton(text)
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    if name: widget.setObjectName(name)
    widget.clicked.connect(action)
    return widget


def row(*widgets, spacing=10):
    box = QHBoxLayout()
    box.setContentsMargins(0, 0, 0, 0)
    box.setSpacing(spacing)
    for widget in widgets:
        if widget is None: box.addStretch()
        else: box.addWidget(widget)
    return box


def frame(name, margins=(16, 16, 16, 16), spacing=12):
    widget = QFrame()
    widget.setObjectName(name)
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(*margins)
    layout.setSpacing(spacing)
    return widget, layout


def clear(layout):
    while layout.count():
        item = layout.takeAt(0)
        if item.widget(): item.widget().deleteLater()
        elif item.layout(): clear(item.layout())


class ScanThread(QThread):
    failed = Signal(str)
    def __init__(self, workspace):
        super().__init__()
        self.workspace = workspace
    def run(self):
        try: self.workspace.scan()
        except Exception as exc: self.failed.emit(str(exc))


class MediaDialog(QDialog):
    def __init__(self, parent, asset):
        super().__init__(parent)
        self.setWindowTitle(asset['name'])
        self.resize(820, 560)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.addWidget(label(asset['name'], 'sectionTitle'))
        path = parent.workspace.path(asset['path'])
        self.player = None
        if asset['media'] == 'image':
            view = QLabel()
            view.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pix = QPixmap(str(path))
            view.setPixmap(pix.scaled(760, 420, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            layout.addWidget(view, 1)
        else:
            from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
            from PySide6.QtMultimediaWidgets import QVideoWidget
            self.player = QMediaPlayer(self)
            self.audio = QAudioOutput(self)
            self.player.setAudioOutput(self.audio)
            if asset['media'] == 'video':
                video = QVideoWidget()
                self.player.setVideoOutput(video)
                layout.addWidget(video, 1)
            else:
                waveform = label('≋   音声参照   ≋', 'title')
                waveform.setAlignment(Qt.AlignmentFlag.AlignCenter)
                layout.addWidget(waveform, 1)
            self.player.setSource(QUrl.fromLocalFile(str(path)))
            playback = label('点击播放试听', 'muted')
            self.player.errorOccurred.connect(lambda *_: playback.setText(self.player.errorString()))
            layout.addLayout(row(button('播放', self.player.play, 'primary'), button('暂停', self.player.pause), playback, None))
        layout.addWidget(label(asset['path'], 'muted', True))
        layout.addWidget(button('关闭', self.accept))
        self.finished.connect(lambda *_: self.player.stop() if self.player else None)


class MappingDialog(QDialog):
    def __init__(self, host, report):
        super().__init__(host)
        self.host, self.report = host, report
        req = report['requirement']
        self.setWindowTitle('参照资产 · ' + req['name'])
        self.resize(680, 510)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)
        demo = 'DEMO  ·  ' if host.workspace.state.get('is_example') else ''
        layout.addWidget(label(demo + KINDS[req['kind']] + ' / ' + req['media'].upper(), 'eyebrow'))
        layout.addWidget(label(req['name'], 'title', True))
        layout.addWidget(label(report['reason'], 'muted', True))
        self.preview_image = QLabel()
        self.preview_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_image.setMinimumHeight(145)
        self.preview_image.setMaximumHeight(180)
        self.preview_image.setStyleSheet('background:#0a1929;border:1px solid #365570;border-radius:8px;color:#9ebbd4;font-size:20px;')
        self.preview_image.setText(SYMBOLS[req['media']])
        layout.addWidget(self.preview_image)
        self.choices = QListWidget()
        self.choices.setObjectName('mappingChoices')
        self.choices.setMaximumHeight(158)
        choices = [a for a in host.workspace.state['assets'].values() if a['kind'] == req['kind'] and not a.get('missing')]
        choices.sort(key=lambda a: (a['id'] not in {x['id'] for x in report['candidates']}, a['name']))
        for asset in choices:
            marker = '不可用 · ' if asset['problem'] else ''
            item = QListWidgetItem(f'{marker}{asset["name"]}\n{asset["path"]}')
            item.setData(Qt.ItemDataRole.UserRole, asset['id'])
            item.setToolTip(asset['problem'] or asset['sha256'])
            self.choices.addItem(item)
            if report['asset'] and asset['id'] == report['asset']['id']:
                self.choices.setCurrentItem(item)
        if not choices:
            layout.addWidget(label('素材库还没有此类型的文件。导入后，系统会自动命名并关联当前需求。', 'muted', True))
        layout.addWidget(self.choices)
        self.message = label('', 'error', True)
        layout.addWidget(self.message)
        uses = req['usages']
        names = host.shot_names()
        used = list(dict.fromkeys(names.get(u['shot_id'], u['shot_id'][:8]) for u in uses))
        layout.addWidget(label('引用镜头  ·  ' + '、'.join(used), 'muted', True))
        self.confirm = button('确认使用这个版本', self.bind, 'primary')
        self.confirm.setObjectName('confirmMapping')
        self.confirm.setEnabled(self.choices.currentItem() is not None)
        self.choices.currentItemChanged.connect(lambda current, _: self.confirm.setEnabled(current is not None))
        self.choices.currentItemChanged.connect(self.update_preview)
        self.update_preview(self.choices.currentItem(), None)
        layout.addLayout(row(button('导入新素材…', self.import_file), button('预览', self.preview), None, self.confirm))
        layout.addWidget(button('返回工作区', self.reject, 'quiet'))

    def update_preview(self, current, previous):
        self.preview_image.clear()
        if not current:
            self.preview_image.setText('导入参照，让需求落到真实素材。')
            return
        asset = self.host.workspace.state['assets'][current.data(Qt.ItemDataRole.UserRole)]
        if asset['media'] == 'image' and not asset['problem']:
            pix = QPixmap(str(self.host.workspace.path(asset['path'])))
            self.preview_image.setPixmap(pix.scaled(560, 180, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            self.preview_image.setText(SYMBOLS[asset['media']] + '  ' + ('文件不可用' if asset['problem'] else '点击预览播放媒体'))

    def bind(self):
        current = self.choices.currentItem()
        if not current: return
        try:
            self.host.workspace.bind(self.report['requirement']['id'], current.data(Qt.ItemDataRole.UserRole))
            self.accept()
        except Exception as exc: self.message.setText(str(exc))

    def preview(self):
        current = self.choices.currentItem()
        if current:
            asset = self.host.workspace.state['assets'][current.data(Qt.ItemDataRole.UserRole)]
            if not asset['problem']: MediaDialog(self.host, asset).exec()

    def import_file(self):
        req = self.report['requirement']
        patterns = ' '.join('*' + ext for ext in sorted(EXTENSIONS[req['media']]))
        filename, _ = QFileDialog.getOpenFileName(self, '导入 ' + req['name'], '', f'媒体文件 ({patterns})')
        if not filename: return
        try:
            self.host.workspace.import_asset(req['id'], filename)
            self.accept()
        except Exception as exc: self.message.setText(str(exc))


class ImageMonitor(QLabel):
    """Aspect-fit actual asset pixels, even when production panels resize."""
    def __init__(self, text=''):
        super().__init__(text)
        self.source = None

    def set_source(self, pixmap):
        self.source = pixmap if pixmap and not pixmap.isNull() else None
        self.fit_source()

    def fit_source(self):
        if self.source:
            self.setPixmap(self.source.scaled(max(1, self.width() - 12), max(1, self.height() - 12),
                                             Qt.AspectRatioMode.KeepAspectRatio,
                                             Qt.TransformationMode.SmoothTransformation))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fit_source()


class PreparationWindow(QMainWindow):
    def __init__(self, data_root, session_path=None):
        super().__init__()
        self.session_path = Path(session_path) if session_path else None
        self.workspace = None
        self.lock = None
        self.worker = None
        self.chapter_id = None
        self.shot_id = None
        self.loading = True
        self.setWindowTitle('AI 视频工作流 · V0.2 章节准备')
        self.resize(1480, 940)
        self.setMinimumSize(1100, 720)
        self.setStyleSheet(STYLE)
        self.autosave = QTimer(self)
        self.autosave.setSingleShot(True)
        self.autosave.setInterval(700)
        self.autosave.timeout.connect(lambda: self.guard(self.save_draft))
        self.build()
        self.open_workspace(data_root)
        QShortcut(QKeySequence('Ctrl+S'), self, lambda: self.guard(self.save_draft))
        QShortcut(QKeySequence('Ctrl+Return'), self, self.apply_script)

    def build(self):
        surface = Atmosphere()
        surface.setObjectName('surface')
        root = QVBoxLayout(surface)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.setCentralWidget(surface)
        header, head = frame('header', (21, 11, 21, 11), 0)
        logo = FilmMark()
        self.project_title = label('AI 视频工作流', 'brand')
        self.saved = label('本地保存', 'status')
        self.open_button = button('打开项目', self.choose_workspace, 'quiet')
        self.scan_button = button('同步素材', self.scan, 'quiet')
        self.scan_button.setObjectName('scanLibrary')
        self.apply_button = button('应用剧本  ↗', self.apply_script, 'primary')
        self.apply_button.setToolTip('Ctrl+Enter · 解析有效剧本并更新生产需求')
        head.addLayout(row(logo, label('AIGC 流', 'brand'), label('／', 'muted'), self.project_title,
                           None, self.saved, self.open_button, self.scan_button,
                           self.apply_button, spacing=11))
        root.addWidget(header)
        self.body = QWidget()
        body = QHBoxLayout(self.body)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        root.addWidget(self.body, 1)
        sidebar, side = frame('sidebar', (14, 19, 14, 14), 8)
        sidebar.setFixedWidth(232)
        self.example_badge = label('DEMO  ·  概念参照 / 示意资产', 'muted')
        side.addWidget(self.example_badge)
        side.addWidget(label('章节 / 镜头', 'eyebrow'))
        self.chapters = QComboBox()
        self.chapters.setObjectName('chapterChoice')
        self.chapters.currentIndexChanged.connect(self.chapter_changed)
        side.addWidget(self.chapters)
        self.chapter_all = button('整章视图   ·   全部参照', self.select_chapter, 'chapter')
        side.addWidget(self.chapter_all)
        self.shots = QListWidget()
        self.shots.setObjectName('shots')
        self.shots.setItemDelegate(ShotDelegate(self.shots))
        self.shots.currentItemChanged.connect(self.shot_changed)
        side.addWidget(self.shots, 1)
        side.addWidget(button('素材库   ↗', self.open_library, 'nav'))
        side.addWidget(button('导入剧本   ＋', self.import_script, 'importScript'))
        side.addWidget(button('打开示例项目', self.open_example, 'nav'))
        side.addWidget(button('剧本规则', self.show_help, 'nav'))
        body.addWidget(sidebar)
        workspace = QWidget()
        work = QVBoxLayout(workspace)
        work.setContentsMargins(20, 16, 20, 11)
        work.setSpacing(12)
        body.addWidget(workspace, 1)
        self.chapter_caption = label('PREPARATION  /  CHAPTER', 'eyebrow')
        self.heading = label('从剧本开始，让素材各就其位。', 'title')
        self.ready_label = label('等待剧本', 'readiness')
        work.addWidget(self.chapter_caption)
        work.addLayout(row(self.heading, None, self.ready_label, spacing=12))
        summary, summary_layout = frame('metric', (0, 0, 0, 2), 0)
        self.summary = label('0 / 0 参照就绪', 'sectionTitle')
        self.summary_right = label('先从剧本开始', 'muted')
        summary_layout.addLayout(row(self.summary, None, self.summary_right))
        work.addWidget(summary)
        self.draft_banner, banner = frame('callout', (12, 8, 12, 8))
        banner.addWidget(label('剧本有未应用的修改。右侧保留上次有效需求，请解析后再补齐素材。', wrap=True))
        self.draft_banner.hide()
        work.addWidget(self.draft_banner)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(11)
        work.addWidget(self.splitter, 1)
        editor_panel, editor_layout = frame('editorPanel', (17, 15, 16, 14), 10)
        editor_panel.setMinimumWidth(340)
        self.editor_context = label('Production Script', 'sectionTitle')
        self.editor_context.setToolTip('可执行生产剧本')
        editor_layout.addWidget(self.editor_context)
        self.editor = ScriptEditor()
        self.editor.setPlaceholderText('影片名/名称\n01/章节/章节名\n\n001/镜头标题\n人物/-/服装/音声\n【环境参照】/背景音\n\n镜头：\n自由描述摄影、动作与表演。\n\n也可以从左下角打开示例项目。')
        self.editor.textChanged.connect(self.draft_changed)
        editor_layout.addWidget(self.editor, 1)
        self.diagnostics = QListWidget()
        self.diagnostics.setObjectName('diagnostics')
        self.diagnostics.setMaximumHeight(130)
        self.diagnostics.itemClicked.connect(lambda item: self.editor.go_line(item.data(Qt.ItemDataRole.UserRole)))
        self.diagnostics.hide()
        editor_layout.addWidget(self.diagnostics)
        self.splitter.addWidget(editor_panel)
        right, right_layout = frame('panel', (13, 12, 13, 10), 8)
        right.setMinimumWidth(380)
        self.requirement_title = label('参照与媒体', 'sectionTitle')
        self.filter = QComboBox()
        self.filter.setFixedWidth(90)
        for title, key in [('全部', 'all'), ('待处理', 'todo'), ('已就绪', 'resolved')]:
            self.filter.addItem(title, key)
        self.filter.currentIndexChanged.connect(self.render_requirements)
        right_layout.addLayout(row(self.requirement_title, None, self.filter))
        self.viewer, viewer_layout = frame('viewer', (4, 4, 4, 0), 0)
        self.viewer.setObjectName('viewer')
        self.viewer_image = ImageMonitor('选择一项已入库资产以监看')
        self.viewer_image.setObjectName('viewerImage')
        self.viewer_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.viewer_image.setMinimumHeight(120)
        self.viewer_image.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
        viewer_layout.addWidget(self.viewer_image, 1)
        self.viewer_caption = label('无媒体  /  资产入库后可监看', 'muted')
        self.viewer_caption.setObjectName('viewerCaption')
        self.viewer_open = button('预览  ↗', self.inspect_viewed, 'quiet')
        viewer_layout.addLayout(row(self.viewer_caption, None, self.viewer_open, spacing=4))
        self.viewer.setMinimumHeight(225)
        self.viewer.setMaximumHeight(350)
        self.viewer_open.setEnabled(False)
        right_layout.addWidget(self.viewer, 3)
        self.viewed_asset_id = None
        self.viewed_asset_sha = None
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        content.setStyleSheet('background:transparent;')
        self.cards = QVBoxLayout(content)
        self.cards.setContentsMargins(0, 0, 5, 0)
        self.cards.setSpacing(5)
        scroll.setWidget(content)
        right_layout.addWidget(scroll, 1)
        self.impact_button = button('版本与影响  /  0', self.show_impacts, 'quiet')
        right_layout.addWidget(self.impact_button, 0, Qt.AlignmentFlag.AlignRight)
        self.splitter.addWidget(right)
        self.splitter.setSizes([620, 590])
        self.feedback = label('本地工作区   /   准备阶段', 'muted')
        self.feedback.setWordWrap(True)
        work.addWidget(self.feedback)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'viewer'):
            self.viewer.setMaximumHeight(350 if self.height() >= 850 else 305)

    def open_workspace(self, root):
        root = Path(root).resolve()
        root.mkdir(parents=True, exist_ok=True)
        if self.workspace and root == self.workspace.root:
            return
        lock = QLockFile(str(root / '.workspace.lock'))
        lock.setStaleLockTime(0)
        if not lock.tryLock(0):
            raise ValueError('此工作区已在另一个窗口打开，请先关闭另一窗口。')
        try: workspace = Workspace(root)
        except Exception:
            lock.unlock()
            raise
        if self.workspace:
            try: self.save_draft()
            except Exception:
                lock.unlock()
                raise
        if self.lock: self.lock.unlock()
        self.lock, self.workspace = lock, workspace
        self.loading = True
        self.editor.setPlainText(workspace.state['draft'])
        self.chapter_id = workspace.state['ui'].get('chapter_id')
        self.shot_id = workspace.state['ui'].get('shot_id')
        self.loading = False
        self.refresh()
        cursor = self.editor.textCursor()
        cursor.setPosition(min(workspace.state['ui'].get('cursor', 0), len(self.editor.toPlainText())))
        self.editor.setTextCursor(cursor)
        self.editor.centerCursor()
        self.saved.setText('草稿已恢复' if workspace.state['draft'] else '本地工作区')
        if self.session_path:
            write_json(self.session_path, {'last_project': str(workspace.root)})
        self.scan()

    def guard(self, operation):
        try: return operation()
        except Exception as exc:
            self.feedback.setText('操作未完成 · ' + str(exc))
            return None

    def choose_workspace(self):
        folder = QFileDialog.getExistingDirectory(self, '打开或新建 V0.2 项目', str(self.workspace.root.parent))
        if folder: self.guard(lambda: self.open_workspace(folder))

    def import_script(self):
        filename, _ = QFileDialog.getOpenFileName(self, '导入规范剧本', '', '剧本文本 (*.md *.txt)')
        if not filename: return
        if self.editor.toPlainText().strip() and QMessageBox.question(self, '替换当前草稿', '导入会替换当前编辑区。已应用的历史剧本保留。继续？') != QMessageBox.StandardButton.Yes:
            return
        def load():
            self.editor.setPlainText(Path(filename).read_text(encoding='utf-8-sig'))
            self.apply_script()
        self.guard(load)

    def open_example(self):
        def load():
            from .preparation.example import create_example
            target = self.workspace.root.parent / 'example-preparation'
            if not (target / 'project.json').exists(): create_example(target)
            self.open_workspace(target)
        self.guard(load)

    def open_library(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.workspace.root / 'library')))

    def draft_changed(self):
        if self.loading: return
        self.saved.setText('正在保存草稿…')
        self.autosave.start()
        self.draft_banner.show()
        self.ready_label.setText('草稿待解析')
        self.set_mapping_enabled(False)

    def save_draft(self):
        if not self.workspace or self.loading: return
        self.autosave.stop()
        try:
            self.workspace.save_draft(self.editor.toPlainText())
            self.workspace.set_ui(cursor=self.editor.textCursor().position())
            self.saved.setText('已保存到本地')
        except Exception as exc:
            self.saved.setText('保存失败')
            self.feedback.setText('草稿未保存：' + str(exc))
            raise

    def apply_script(self):
        if self.worker and self.worker.isRunning(): return
        self.autosave.stop()
        def apply():
            parsed = self.workspace.apply(self.editor.toPlainText())
            self.show_diagnostics(parsed)
            self.refresh()
            self.saved.setText('需求已更新' if parsed.valid else '草稿已保存 · 请修正错误')
            self.feedback.setText('剧本已解析，资产需求已更新。' if parsed.valid else '解析未通过；上一次有效需求与素材关联保持不变。点击错误可定位原文。')
        self.guard(apply)

    def show_diagnostics(self, parsed):
        self.diagnostics.clear()
        for diagnostic in parsed.diagnostics:
            item = QListWidgetItem(f'第 {diagnostic.line} 行  ·  {diagnostic.message}')
            item.setData(Qt.ItemDataRole.UserRole, diagnostic.line)
            self.diagnostics.addItem(item)
        self.diagnostics.setVisible(bool(parsed.diagnostics) and bool(parsed.source.strip()))

    def scan(self):
        if self.worker and self.worker.isRunning(): return
        try: self.save_draft()
        except Exception: return
        self.body.setEnabled(False)
        for control in (self.open_button, self.scan_button, self.apply_button): control.setEnabled(False)
        self.saved.setText('正在扫描与校验素材…')
        self.scan_error = None
        self.worker = ScanThread(self.workspace)
        self.worker.failed.connect(self.scan_failed)
        self.worker.finished.connect(self.scan_finished)
        self.worker.start()

    def scan_failed(self, message):
        self.scan_error = message

    def scan_finished(self):
        self.body.setEnabled(True)
        for control in (self.open_button, self.scan_button, self.apply_button): control.setEnabled(True)
        self.refresh()
        if self.scan_error:
            self.saved.setText('同步未完成')
            self.feedback.setText(self.scan_error)
        else:
            self.saved.setText('素材库已同步')
            self.feedback.setText('LIBRARY  /  素材库已同步   ·   变更与歧义保留人工确认')

    def shot_names(self):
        script = self.workspace.script
        return {s.id: f'{c.number.zfill(2)} / {s.number} {s.title}' for c in script.chapters for s in c.shots} if script else {}

    def refresh(self):
        script = self.workspace.script
        self.loading = True
        self.chapters.blockSignals(True)
        self.chapters.clear()
        if script:
            self.project_title.setText(script.title)
            for chapter in script.chapters: self.chapters.addItem(f'{chapter.number.zfill(2)}  {chapter.title}', chapter.id)
            index = self.chapters.findData(self.chapter_id)
            self.chapters.setCurrentIndex(max(0, index))
            self.chapter_id = self.chapters.currentData()
        else:
            self.chapters.addItem('尚未建立章节', None)
            self.chapter_id = None
            self.project_title.setText('AI 视频工作流')
        self.chapters.blockSignals(False)
        self.example_badge.setVisible(bool(self.workspace.state.get('is_example')))
        self.populate_shots()
        self.loading = False
        self.show_diagnostics(self.workspace.draft_result)
        self.render_summary()
        self.render_requirements()

    def current_chapter(self):
        script = self.workspace.script
        return next((c for c in script.chapters if c.id == self.chapter_id), None) if script else None

    def populate_shots(self):
        self.shots.blockSignals(True)
        self.shots.clear()
        chapter = self.current_chapter()
        report = {r['requirement']['id']: r for r in self.workspace.report()}
        current = None
        if chapter:
            for shot in chapter.shots:
                done = sum(report[rid]['status'] == 'resolved' for rid in shot.requirement_ids)
                item = QListWidgetItem(f'{shot.number}   {shot.title}\n        {done}/{len(shot.requirement_ids)}  参照就绪')
                item.setData(Qt.ItemDataRole.UserRole, shot.id)
                item.setData(Qt.ItemDataRole.UserRole + 1, (shot.number, shot.title, done, len(shot.requirement_ids)))
                self.shots.addItem(item)
                if shot.id == self.shot_id: current = item
        if current: self.shots.setCurrentItem(current)
        else: self.shot_id = None
        self.shots.blockSignals(False)

    def chapter_changed(self, *_):
        if self.loading or not self.workspace: return
        self.chapter_id = self.chapters.currentData()
        self.shot_id = None
        self.populate_shots()
        self.persist_selection()
        self.render_summary()
        self.render_requirements()
        chapter = self.current_chapter()
        if chapter: self.editor.go_line(chapter.line)

    def shot_changed(self, current, previous):
        if self.loading: return
        self.shot_id = current.data(Qt.ItemDataRole.UserRole) if current else None
        self.persist_selection()
        self.render_requirements()
        chapter = self.current_chapter()
        shot = next((s for s in chapter.shots if s.id == self.shot_id), None) if chapter else None
        if shot: self.editor.go_line(shot.line)

    def select_chapter(self):
        self.shots.clearSelection()
        self.shots.setCurrentRow(-1)
        self.shot_id = None
        self.persist_selection()
        self.render_requirements()

    def persist_selection(self):
        self.guard(lambda: self.workspace.set_ui(chapter_id=self.chapter_id, shot_id=self.shot_id))

    def applied(self):
        script = self.workspace.script
        return bool(script and parse(self.editor.toPlainText(), self.workspace.state['project_id']).revision == script.revision)

    def render_summary(self):
        chapter = self.current_chapter()
        applied = self.applied()
        self.draft_banner.setVisible(bool(self.editor.toPlainText()) and not applied)
        if chapter:
            counts = self.workspace.chapter_status(chapter.id)
            self.heading.setText(chapter.title)
            self.chapter_caption.setText(f'CHAPTER {chapter.number.zfill(2)}  /  章节准备')
            self.summary.setText(f'{counts["resolved"]} / {counts["total"]}  参照就绪')
            pending = counts['missing'] + counts['unresolved'] + counts['changed']
            self.summary_right.setText(f'{pending} 项待处理' if pending else '本章参照已就绪')
            self.ready_label.setText('READY' if counts['ready'] else 'DRAFT' if not applied else 'PREP')
        else:
            self.heading.setText('从剧本开始，让素材各就其位。')
            self.ready_label.setText('等待有效剧本')
            self.summary.setText('0 / 0 参照就绪')
            self.summary_right.setText('从左侧打开示例，或直接编辑')

    def set_mapping_enabled(self, enabled):
        for control in self.findChildren(QPushButton):
            if control.property('mappingAction'): control.setEnabled(enabled)

    def render_requirements(self, *_):
        if not self.workspace: return
        clear(self.cards)
        chapter = self.current_chapter()
        selected = next((s for s in chapter.shots if s.id == self.shot_id), None) if chapter else None
        ids = set(selected.requirement_ids) if selected else {r for s in chapter.shots for r in s.requirement_ids} if chapter else set()
        self.requirement_title.setText(f'{selected.number}  ·  {selected.title}' if selected else '整章参照')
        reports = [r for r in self.workspace.report() if r['requirement']['id'] in ids]
        mode = self.filter.currentData()
        reports = [r for r in reports if mode == 'all' or (mode == 'todo' and r['status'] != 'resolved') or (mode == 'resolved' and r['status'] == 'resolved')]
        reports.sort(key=lambda r: (r['status'] == 'resolved', r['requirement']['media']))
        all_reports = [r for r in self.workspace.report() if r['requirement']['id'] in ids]
        if not any(r['asset'] and r['asset']['id'] == self.viewed_asset_id and r['asset']['sha256'] == self.viewed_asset_sha and r['status'] == 'resolved' for r in all_reports):
            default = next((r for r in all_reports if r['status'] == 'resolved' and r['requirement']['kind'] == 'environment'), None)
            default = default or next((r for r in all_reports if r['status'] == 'resolved'), None)
            self.select_media(default) if default else self.select_media({'asset': None})
        for report in reports: self.cards.addWidget(self.requirement_card(report))
        if not reports:
            empty, layout = frame('info', (20, 26, 20, 26))
            layout.addWidget(label('这里会自动汇集你的参照需求' if not chapter else '当前筛选下没有待显示需求', 'sectionTitle', True))
            layout.addWidget(label('人物、环境、关键物件和镜头参照，从规范剧本中直接读取。' if not chapter else '可以切换筛选，或选择另一个镜头。', 'muted', True))
            self.cards.addWidget(empty)
        self.cards.addStretch()
        count = len(self.workspace.state['events'])
        self.impact_button.setText(f'版本与影响  ·  {count}' if count else '版本与影响')
        self.set_mapping_enabled(self.applied())

    def select_media(self, report):
        asset = report['asset']
        if not asset or asset.get('missing') or asset['problem']:
            self.viewer_image.set_source(None)
            self.viewer_image.setText('暂无媒体参照')
            self.viewer_caption.setText('绑定素材后可在此预览')
            self.viewer_open.setEnabled(False)
            self.viewed_asset_id = None
            self.viewed_asset_sha = None
            return
        self.viewed_asset_id = asset['id']
        self.viewed_asset_sha = asset['sha256']
        self.viewer_open.setEnabled(True)
        suffix = Path(asset['path']).suffix[1:].upper()
        display_name = ('DEMO  ·  ' if self.workspace.state.get('is_example') else '') + asset['name']
        if asset['media'] == 'image':
            pix = QPixmap(str(self.workspace.path(asset['path'])))
            if pix.isNull():
                self.viewer_image.set_source(None)
                self.viewer_image.setText('来源无法读取  /  请同步素材库')
                self.viewer_caption.setText(display_name + '  /  来源需重新扫描')
                self.viewer_open.setEnabled(False)
            else:
                self.viewer_image.set_source(pix)
                self.viewer_caption.setText(f'{display_name}   /   {pix.width()} × {pix.height()}   /   {suffix}')
        else:
            self.viewer_caption.setText(f'{display_name}   /   {suffix}')
            self.viewer_image.set_source(None)
            self.viewer_image.setText('视频参照 · 点击打开预览' if asset['media'] == 'video' else '音声参照 · 点击打开试听')

    def inspect_viewed(self):
        asset = self.workspace.state['assets'].get(self.viewed_asset_id)
        if asset and not asset.get('missing') and not asset['problem']:
            MediaDialog(self, asset).exec()

    def requirement_card(self, report):
        req, asset = report['requirement'], report['asset']
        card, layout = frame('card', (6, 8, 6, 8), 4)
        image = button({'image': '图像', 'audio': '声音', 'video': '视频'}[req['media']],
                       lambda: self.select_media(report), 'assetThumb')
        image.setFixedSize(82, 62)
        if asset and asset['media'] == 'image' and not asset.get('missing') and not asset['problem']:
            pix = QPixmap(str(self.workspace.path(asset['path'])))
            image.setText('')
            image.setIcon(QIcon(pix))
            image.setIconSize(image.size() - QSize(5, 5))
        image.setToolTip('监看真实素材  /  ' + req['name'])
        text, ink = STATUS[report['status']]
        state = label('●' if report['status'] == 'resolved' else text)
        state.setToolTip(text)
        state.setStyleSheet(f'color:{ink};font-size:10px;')
        name = button(req['name'], lambda: self.select_media(report), 'assetName')
        name.setToolTip(req['name'] + '  /  ' + report['reason'])
        name.setMinimumWidth(0)
        name.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        line = next((u['line'] for u in req['usages'] if not self.shot_id or u['shot_id'] == self.shot_id),
                    req['usages'][0]['line'])
        used = len({u['shot_id'] for u in req['usages']})
        meta = label(f'{KINDS[req["kind"]]}  ·  {used} 镜头', 'muted')
        action = button('查看绑定  ↗' if report['status'] == 'resolved'
                        else '导入素材  ↗' if report['status'] == 'missing'
                        else '处理需求  ↗', lambda: self.open_mapping(req['id']), 'quiet')
        action.setProperty('mappingAction', True)
        action.setObjectName('map_' + req['id'])
        action.setFlat(True)
        source = button(f'L{line:03d}', lambda: self.editor.go_line(line), 'quiet')
        source.setToolTip('跳到剧本声明行')
        content = QVBoxLayout()
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(1)
        content.addLayout(row(name, state, spacing=4))
        content.addWidget(meta)
        content.addLayout(row(source, None, action, spacing=2))
        lead = QHBoxLayout()
        lead.setContentsMargins(0, 0, 0, 0)
        lead.setSpacing(11)
        lead.addWidget(image)
        lead.addLayout(content, 1)
        layout.addLayout(lead)
        if report['status'] in ('unresolved', 'changed'):
            layout.addWidget(label(report['reason'], 'muted', True))
        return card

    def open_mapping(self, rid):
        report = next(r for r in self.workspace.report() if r['requirement']['id'] == rid)
        MappingDialog(self, report).exec()
        self.refresh()

    def show_impacts(self):
        dialog = QDialog(self)
        dialog.setWindowTitle('变更记录与影响定位')
        dialog.resize(760, 540)
        layout = QVBoxLayout(dialog)
        layout.addWidget(label('知道改动影响哪里，再决定下一步。', 'sectionTitle'))
        layout.addWidget(label('历史版本保留；不会删除结果，也不会自动重生成。双击镜头定位当前剧本。', 'muted', True))
        listing = QListWidget()
        names = self.shot_names()
        for event in reversed(self.workspace.state['events']):
            item = QListWidgetItem(event['message'])
            listing.addItem(item)
            for sid in event['shots']:
                child = QListWidgetItem('    ↳  ' + names.get(sid, '历史镜头（已移出当前剧本） · ' + sid[:8]))
                child.setData(Qt.ItemDataRole.UserRole, sid)
                listing.addItem(child)
        if not listing.count(): listing.addItem('尚无变更。素材替换、改名、缺失与剧本修改会显示在这里。')
        def locate(item):
            sid = item.data(Qt.ItemDataRole.UserRole)
            if not sid: return
            script = self.workspace.script
            for chapter in script.chapters:
                for shot in chapter.shots:
                    if shot.id == sid:
                        self.chapter_id, self.shot_id = chapter.id, shot.id
                        self.refresh()
                        self.editor.go_line(shot.line)
                        self.persist_selection()
                        dialog.accept()
                        return
        listing.itemDoubleClicked.connect(locate)
        layout.addWidget(listing, 1)
        layout.addWidget(button('返回工作区', dialog.accept))
        dialog.exec()

    def show_help(self):
        dialog = QDialog(self)
        dialog.setWindowTitle('规范剧本 · 5 分钟上手')
        dialog.resize(750, 640)
        layout = QVBoxLayout(dialog)
        text = ScriptEditor()
        text.setReadOnly(True)
        text.setPlainText(HELP)
        layout.addWidget(text)
        layout.addWidget(button('开始创作', dialog.accept, 'primary'))
        dialog.exec()

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.feedback.setText('正在保存扫描结果，请等待同步完成后关闭。')
            event.ignore()
            return
        try: self.save_draft()
        except Exception:
            QMessageBox.warning(self, '草稿尚未保存', '保存失败，窗口保持打开。请检查磁盘状态后重试。')
            event.ignore()
            return
        if self.lock: self.lock.unlock()
        event.accept()


HELP = '''影片名/名称
01/章节/雨停之前

001/推门进入
【林夏/-/雨衣】/低声
店员/-/围裙/-
【便利店/雨夜】/雨声、冰柜低鸣

镜头：
【门内后退跟拍】 保持中景，结尾缓慢停住。

动作：
林夏推门进入，收起【红伞.破损】。

对白：
林夏：雨还要下多久？

连续性：
承接上一镜，衣服仍然潮湿。

// 少量规则
// 影片 / 章节 / 镜头依次声明。镜头编号至少三位。
// 01/集数 也有效；章节编号和章内镜头编号不能重复。
// 人物/年龄/服装/音声，四个位置不能省；不需要时写 -。
// 完整视觉：【人物/年龄/服装】/音声。声音保持独立。
// 多人物一人一行，之后写一行 环境/背景音。
// 普通环境是描述；只有【环境】才强制要求参照素材。
// 人物和环境写在镜头、动作等自然语言区之前。
// 也可明确标记 人物：… 或 环境：…。
// 正文中的【】是关键物件，镜头：中的【】是视频参照。
// 正文里需要 / 时先写 动作： 或 备注：，系统不猜字段。
// 结构编号用于稳定识别；改标题不换 ID，改编号视为新镜头。

// 素材文件夹
// library/character_visual/林夏/-/雨衣.png
// library/environment/便利店/雨夜.png
// library/prop/红伞.破损.png
// library/voice/林夏/低声.wav
// library/video_reference/门内后退跟拍.mp4
// 同类型、完整名称匹配；两个同名文件需要你明确选择。
// 也可直接点需求卡片导入，文件名与关联由系统管理。
// 唯一内容匹配的改名可恢复身份；同时改名和改内容须手动确认。

// 修改后草稿自动保存，Ctrl+Enter 解析并应用。
// 解析错误不会覆盖上次有效需求。Ctrl+S 立即保存草稿。
// Ready 仅表示本章参照已准备，不代表生成质量或成片完成。
// 后续候选审核：绿=可用，黄=待定，红=废弃。
// 本轮只做准备；生成、审核、轻剪和输出在后续施工。
'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-dir', default=None)
    args = parser.parse_args()
    app = QApplication.instance() or QApplication(sys.argv)
    app.setFont(QFont('Microsoft YaHei UI', 10))
    session_path = Path('.v02-session.json') if args.data_dir is None else None
    target = args.data_dir or 'workspace-v02'
    if session_path and session_path.is_file():
        try:
            recent = json.loads(session_path.read_text(encoding='utf-8')).get('last_project')
            if recent and (Path(recent) / 'project.json').is_file(): target = recent
        except (ValueError, OSError, TypeError): pass
    try: window = PreparationWindow(target, session_path)
    except Exception as exc:
        QMessageBox.critical(None, '无法打开项目', str(exc))
        return 1
    window.show()
    return app.exec()


if __name__ == '__main__':
    raise SystemExit(main())
