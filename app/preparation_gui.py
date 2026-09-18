"""V0.2 chapter preparation workspace. Run: python -m app.preparation_gui."""
from __future__ import annotations

import argparse
import html
import re
import json
from pathlib import Path
import sys

from PySide6.QtCore import Qt, QTimer, QThread, Signal, QUrl, QLockFile, QSize
from PySide6.QtGui import QFont, QPixmap, QDesktopServices, QShortcut, QKeySequence, QIcon, QPainter, QColor, QLinearGradient
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame, QLabel, QPushButton, QVBoxLayout,
    QHBoxLayout, QSplitter, QComboBox, QListWidget, QListWidgetItem, QScrollArea,
    QFileDialog, QMessageBox, QDialog, QDialogButtonBox, QSizePolicy,
    QTextBrowser, QStackedWidget, QListView,
)

from .core import write_json
from .preparation.script import KINDS, parse
from .preparation.workspace import Workspace, EXTENSIONS
from .preparation.visuals import STYLE, ScriptEditor, Atmosphere, FilmMark, ShotDelegate, ProgressSegments

STATUS = {'resolved': ('就绪', '#8fbdac'), 'free': ('无需固定素材', '#9aafc1'), 'missing': ('缺失', '#d7ad79'),
          'unresolved': ('待确认', '#b3a4d6'), 'changed': ('已变更', '#d09b87')}
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


def hframe(name, margins=(0, 0, 0, 0), spacing=0):
    widget = QFrame()
    widget.setObjectName(name)
    layout = QHBoxLayout(widget)
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
        candidate_assets = {c['asset_id'] for c in host.workspace.state['candidates'].values()}
        choices = [a for a in host.workspace.state['assets'].values()
                   if a['kind'] == req['kind'] and not a.get('missing') and a['id'] not in candidate_assets]
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


class ApiCapabilityDialog(QDialog):
    """Truthful entry point for internal capabilities; no provider or credential is implied."""
    CAPABILITIES = (('text', 'Text'), ('image', 'Image'), ('video', 'Video'), ('audio', 'Audio'))

    def __init__(self, host, requirement):
        super().__init__(host)
        self.capability = requirement['media']
        self.setWindowTitle('生成能力  ·  ' + self.capability.upper())
        self.setStyleSheet(host.styleSheet())
        self.resize(500, 370)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 22)
        layout.setSpacing(12)
        layout.addWidget(label('INTERNAL GENERATION  /  API', 'eyebrow'))
        layout.addWidget(label('生成能力', 'title'))
        layout.addWidget(label(f'{KINDS[requirement["kind"]]} · {requirement["name"]}  →  {self.capability.upper()}',
                               'muted', True))
        self.rows = {}
        for key, title in self.CAPABILITIES:
            line, box = hframe('capabilitySelected' if key == self.capability else 'capabilityRow',
                               (13, 9, 13, 9), 0)
            name = label(title, 'sectionTitle')
            state = label('未配置', 'muted')
            box.addWidget(name)
            box.addStretch()
            box.addWidget(state)
            layout.addWidget(line)
            self.rows[key] = state
        layout.addWidget(label('当前无可用内部 Provider。接入真实 Adapter 后，对应能力将在这里配置；'
                               '本轮不保存 API Key，也不发起模型请求。', 'muted', True))
        layout.addStretch()
        layout.addWidget(button('返回当前镜头', self.accept, 'quiet'))


def cover_thumbnail(pixmap, width, height):
    """Crop actual bound pixels for a media-first thumbnail; never synthesize media."""
    scaled = pixmap.scaled(width, height, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                           Qt.TransformationMode.SmoothTransformation)
    x = max(0, (scaled.width() - width) // 2)
    y = max(0, int((scaled.height() - height) * (.18 if pixmap.height() > pixmap.width() else .5)))
    return scaled.copy(x, y, width, height)


class ImageMonitor(QLabel):
    """Cover-fitted pixels from the actual bound asset, with a restrained caption."""
    def __init__(self, text=''):
        super().__init__(text)
        self.source = None
        self.media_title = ''
        self.media_detail = ''
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def set_source(self, pixmap):
        self.source = pixmap if pixmap and not pixmap.isNull() else None
        self.update()

    def set_media_caption(self, title, detail=''):
        self.media_title, self.media_detail = title, detail
        self.update()

    def paintEvent(self, event):
        if not self.source:
            super().paintEvent(event)
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        scaled = self.source.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                    Qt.TransformationMode.SmoothTransformation)
        x = (scaled.width() - self.width()) // 2
        y = (scaled.height() - self.height()) // 2
        painter.drawPixmap(self.rect(), scaled, scaled.rect().adjusted(x, y, -x, -y))
        gradient = QLinearGradient(0, self.height() * .50, 0, self.height())
        gradient.setColorAt(0, QColor(2, 7, 12, 0))
        gradient.setColorAt(1, QColor(2, 7, 12, 215))
        painter.fillRect(self.rect(), gradient)
        painter.setPen(QColor('#ecf2f6'))
        painter.setFont(QFont('Microsoft YaHei UI', 15, QFont.Weight.Medium))
        painter.drawText(21, self.height()-39, self.width()-50, 24,
                         Qt.AlignmentFlag.AlignLeft, self.media_title)
        painter.setPen(QColor('#bccbd7'))
        painter.setFont(QFont('Microsoft YaHei UI', 10))
        painter.drawText(22, self.height()-18, self.width()-50, 16,
                         Qt.AlignmentFlag.AlignLeft, self.media_detail)
        painter.end()


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
        self.active_requirement_id = None
        self.setWindowTitle('AI 视频工作流 · V0.2 章节准备')
        self.resize(1480, 940)
        self.setMinimumSize(1120, 720)
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

        top, top_layout = hframe('topbar', (32, 0, 32, 0), 0)
        top.setFixedHeight(60)
        mark = FilmMark()
        brand = label('映序', 'brand')
        brand_note = label('AI FILM WORKSPACE', 'brandSub')
        top_layout.addLayout(row(mark, brand, brand_note, spacing=10))
        top_layout.addSpacing(34)
        stages = QHBoxLayout()
        stages.setContentsMargins(0, 0, 0, 0)
        stages.setSpacing(24)
        self.production_stages = []
        for title, active in [('准备', True), ('生成', False), ('判断', False), ('轻剪', False), ('输出', False)]:
            if title in ('生成', '判断'):
                stage = button(title, self.open_prompt if title == '生成' else self.open_production, 'stageEnabled')
                stage.setToolTip('编写当前镜头的 Prompt Draft' if title == '生成' else '进入当前需求的 Candidate 生产与判断')
                self.production_stages.append(stage)
            else:
                stage = label(title, 'stageActive' if active else 'stageFuture')
            stage.setFixedHeight(57)
            stages.addWidget(stage)
        top_layout.addLayout(stages)
        top_layout.addStretch()
        self.open_button = button('打开项目', self.choose_workspace, 'tool')
        import_button = button('导入剧本', self.import_script, 'importScript')
        self.library_button = button('素材库', self.open_library, 'tool')
        self.scan_button = button('同步素材', self.scan, 'tool')
        self.scan_button.setObjectName('scanLibrary')
        top_layout.addLayout(row(self.open_button, import_button, self.library_button,
                                 self.scan_button, spacing=4))
        root.addWidget(top)

        project, project_layout = hframe('projectbar', (36, 14, 36, 14), 0)
        project.setFixedHeight(104)
        film = QVBoxLayout()
        film.setSpacing(3)
        self.example_badge = label('DEMO  ·  示例项目', 'eyebrow')
        self.project_title = label('AI 视频工作流', 'projectTitle')
        film.addWidget(self.example_badge)
        film.addWidget(self.project_title)
        project_layout.addLayout(film)
        chapter_context = QHBoxLayout()
        chapter_context.setContentsMargins(26, 0, 0, 0)
        chapter_context.setSpacing(11)
        self.chapter_number = label('01', 'chapterNumber')
        chapter_context.addWidget(self.chapter_number)
        chapter_text = QVBoxLayout()
        chapter_text.setSpacing(4)
        self.chapter_caption = label('CHAPTER  /  准备阶段', 'eyebrow')
        self.heading = label('尚未建立章节', 'chapterHeading')
        chapter_text.addWidget(self.chapter_caption)
        chapter_text.addWidget(self.heading)
        chapter_context.addLayout(chapter_text)
        project_layout.addLayout(chapter_context)
        self.chapters = QComboBox()
        self.chapters.setObjectName('chapterChoice')
        self.chapters.setFixedWidth(150)
        self.chapters.currentIndexChanged.connect(self.chapter_changed)
        project_layout.addWidget(self.chapters)
        project_layout.addStretch()
        metric = QVBoxLayout()
        metric.setSpacing(3)
        self.summary = label('0 / 0', 'summaryCount')
        self.summary_right = label('等待剧本', 'muted')
        self.ready_label = label('PREP', 'readiness')
        metric.addLayout(row(self.summary, self.ready_label, spacing=12))
        self.progress_bar = ProgressSegments()
        metric.addWidget(self.progress_bar)
        metric.addWidget(self.summary_right)
        project_layout.addLayout(metric)
        self.apply_button = button('应用剧本   ↗', self.apply_script, 'primary')
        self.apply_button.setToolTip('Ctrl+Enter · 解析有效剧本并更新生产需求')
        project_layout.addSpacing(24)
        project_layout.addWidget(self.apply_button)
        root.addWidget(project)

        self.body = QWidget()
        body = QVBoxLayout(self.body)
        body.setContentsMargins(36, 0, 36, 0)
        body.setSpacing(0)
        root.addWidget(self.body, 1)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(16)
        body.addWidget(self.splitter, 1)

        media = QWidget()
        media_layout = QVBoxLayout(media)
        media_layout.setContentsMargins(0, 0, 5, 0)
        media_layout.setSpacing(0)
        media_head = QHBoxLayout()
        media_head.setContentsMargins(0, 0, 0, 0)
        media_head.addWidget(label('MEDIA  /  当前镜头参照', 'eyebrow'))
        media_head.addStretch()
        self.viewer_open = button('查看媒体  ↗', self.inspect_viewed, 'quiet')
        self.viewer_open.setEnabled(False)
        media_head.addWidget(self.viewer_open)
        media_layout.addLayout(media_head)
        self.viewer, viewer_layout = frame('viewer', (0, 0, 0, 0), 0)
        self.viewer_image = ImageMonitor('当前镜头尚无已绑定媒体')
        self.viewer_image.setObjectName('viewerImage')
        self.viewer_image.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
        viewer_layout.addWidget(self.viewer_image, 1)
        media_layout.addWidget(self.viewer, 1)
        self.viewer_caption = label('等待真实媒体参照', 'muted')
        self.viewer_caption.setFixedHeight(26)
        media_layout.addWidget(self.viewer_caption)
        self.viewed_asset_id = None
        self.viewed_asset_sha = None
        assets_head = QHBoxLayout()
        assets_head.setContentsMargins(0, 8, 0, 6)
        self.requirement_title = label('当前镜头资产需求', 'sectionTitle')
        assets_head.addWidget(self.requirement_title)
        self.production_button = button('制作 / 判断  ↗', self.open_production, 'quiet')
        assets_head.addWidget(self.production_button)
        assets_head.addStretch()
        self.filter = QComboBox()
        self.filter.setFixedWidth(83)
        for title, key in [('全部', 'all'), ('待处理', 'todo'), ('已就绪', 'resolved')]:
            self.filter.addItem(title, key)
        self.filter.currentIndexChanged.connect(self.render_requirements)
        assets_head.addWidget(self.filter)
        self.chapter_all = button('整章参照  ↗', self.select_chapter, 'quiet')
        assets_head.addWidget(self.chapter_all)
        media_layout.addLayout(assets_head)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setFixedHeight(159)
        content = QWidget()
        content.setObjectName('assetContent')
        content.setStyleSheet('QWidget#assetContent { background: #101923; }')
        scroll.viewport().setStyleSheet('background: #101923;')
        self.cards = QHBoxLayout(content)
        self.cards.setContentsMargins(0, 0, 0, 5)
        self.cards.setSpacing(10)
        scroll.setWidget(content)
        self.asset_scroll = scroll
        media_layout.addWidget(scroll)
        self.resolution_bar, resolution = hframe('resolutionBar', (0, 7, 0, 3), 7)
        self.resolution_label = label('', 'resolutionContext')
        self.resolution_label.setMaximumWidth(210)
        resolution.addWidget(self.resolution_label)
        resolution.addStretch()
        self.free_button = button('不需要固定素材', self.toggle_reference_requirement, 'resolutionQuiet')
        self.free_button.setObjectName('freeRequirement')
        self.import_candidate_button = button('导入素材', self.import_for_requirement, 'resolutionAction')
        self.import_candidate_button.setObjectName('importRequirement')
        self.add_api_button = button('添加 API', self.open_api_settings, 'resolutionAction')
        self.add_api_button.setObjectName('addApiRequirement')
        for control in (self.free_button, self.import_candidate_button, self.add_api_button):
            control.setProperty('mappingAction', True)
            resolution.addWidget(control)
        media_layout.addWidget(self.resolution_bar)
        self.resolution_bar.hide()
        self.rework_bar, rework = hframe('reworkBar', (0, 7, 0, 3), 7)
        self.rework_label = label('', 'resolutionContext')
        self.rework_label.setMaximumWidth(220)
        rework.addWidget(self.rework_label)
        rework.addStretch()
        self.rework_generate_button = button('重新生成', self.rework_generate, 'resolutionQuiet')
        self.rework_generate_button.setObjectName('reworkGenerate')
        self.rework_import_button = button('导入新素材', self.rework_import, 'resolutionAction')
        self.rework_import_button.setObjectName('reworkImport')
        for control in (self.rework_generate_button, self.rework_import_button):
            control.setProperty('mappingAction', True)
            control.setToolTip('当前素材继续使用；新结果先作为 Candidate，审核后才能明确更换 Current。')
            rework.addWidget(control)
        media_layout.addWidget(self.rework_bar)
        self.rework_bar.hide()
        attention = QHBoxLayout()
        attention.setContentsMargins(0, 7, 0, 5)
        self.attention = label('资产状态基于当前已应用剧本', 'muted')
        attention.addWidget(self.attention, 1)
        self.impact_button = button('版本与影响  ↗', self.show_impacts, 'quiet')
        attention.addWidget(self.impact_button)
        media_layout.addLayout(attention)
        self.splitter.addWidget(media)

        script, script_layout = frame('scriptSurface', (0, 0, 0, 0), 0)
        script_head, sh = frame('scriptHeader', (25, 0, 22, 0), 0)
        script_head.setFixedHeight(48)
        self.editor_context = label('PRODUCTION SCRIPT', 'sectionTitle')
        self.script_context = label('当前镜头  /  可执行生产剧本', 'muted')
        sh.addLayout(row(self.editor_context, self.script_context, None, spacing=14))
        script_layout.addWidget(script_head)
        self.draft_banner, banner = frame('callout', (12, 7, 12, 7), 0)
        banner.addWidget(label('剧本有未应用修改；需求仍基于上一次有效版本。', wrap=True))
        self.draft_banner.hide()
        script_layout.addWidget(self.draft_banner)
        self.script_stack = QStackedWidget()
        self.reading = QTextBrowser()
        self.reading.setObjectName('scriptReading')
        self.reading.setOpenExternalLinks(False)
        self.reading.document().setDocumentMargin(0)
        self.script_stack.addWidget(self.reading)
        self.editor = ScriptEditor()
        self.editor.setPlaceholderText('影片名/名称\n01/章节/章节名\n\n001/镜头标题\n人物/-/服装/音声\n【环境参照】/背景音\n\n镜头：\n描述摄影、动作与表演。')
        self.editor.textChanged.connect(self.draft_changed)
        self.script_stack.addWidget(self.editor)
        script_layout.addWidget(self.script_stack, 1)
        self.diagnostics = QListWidget()
        self.diagnostics.setObjectName('diagnostics')
        self.diagnostics.setMaximumHeight(110)
        self.diagnostics.itemClicked.connect(lambda item: self.show_source_line(item.data(Qt.ItemDataRole.UserRole)))
        self.diagnostics.hide()
        script_layout.addWidget(self.diagnostics)
        script_foot, sf = frame('scriptFooter', (20, 2, 18, 2), 0)
        script_foot.setFixedHeight(40)
        self.script_footnote = label('原文驱动  ·  镜头与资产需求保持关联', 'muted')
        self.edit_button = button('编辑剧本  ↗', self.toggle_edit, 'quiet')
        sf.addLayout(row(self.script_footnote, None, self.edit_button))
        script_layout.addWidget(script_foot)
        self.splitter.addWidget(script)
        self.splitter.setSizes([850, 660])

        rail, rail_layout = hframe('shotRail', (0, 10, 0, 0), 0)
        self.shot_rail = rail
        rail.setFixedHeight(130)
        intro = QVBoxLayout()
        intro.setSpacing(5)
        intro.addWidget(label('SHOT INDEX', 'eyebrow'))
        self.shot_count = label('0 个镜头', 'sectionTitle')
        intro.addWidget(self.shot_count)
        intro.addStretch()
        rail_layout.addLayout(intro)
        self.shots = QListWidget()
        self.shots.setObjectName('shots')
        self.shots.setItemDelegate(ShotDelegate(self.shots))
        self.shots.setViewMode(QListView.ViewMode.IconMode)
        self.shots.setFlow(QListView.Flow.LeftToRight)
        self.shots.setWrapping(False)
        self.shots.setResizeMode(QListView.ResizeMode.Fixed)
        self.shots.setMovement(QListView.Movement.Static)
        self.shots.setGridSize(QSize(286, 88))
        self.shots.setHorizontalScrollMode(QListView.ScrollMode.ScrollPerPixel)
        self.shots.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.shots.currentItemChanged.connect(self.shot_changed)
        rail_layout.addWidget(self.shots, 1)
        body.addWidget(rail)
        foot = QHBoxLayout()
        foot.setContentsMargins(0, 0, 0, 0)
        self.feedback = label('本地工作区  /  准备阶段', 'muted')
        self.feedback.setWordWrap(False)
        self.saved = label('本地保存', 'status')
        self.example_button = button('打开示例', self.open_example, 'quiet')
        self.help_button = button('剧本规则', self.show_help, 'quiet')
        foot.addWidget(self.feedback, 1)
        foot.addWidget(self.saved)
        foot.addWidget(self.example_button)
        foot.addWidget(self.help_button)
        body.addLayout(foot)
        self.chapter_overview = False

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'asset_scroll'):
            compact = self.height() < 800
            self.asset_scroll.setFixedHeight(140 if compact else 159)
            if hasattr(self, 'shot_rail'): self.shot_rail.setFixedHeight(112 if compact else 130)
            for thumb in self.asset_scroll.findChildren(QPushButton, 'assetThumb'):
                thumb.setFixedHeight(64 if compact else 78)
            width = self.asset_scroll.viewport().width()
            for card in self.asset_scroll.findChildren(QFrame, 'assetCard'):
                card.setFixedWidth(max(96, (width - 40) // 5))

    def toggle_edit(self):
        self.set_edit_mode(self.script_stack.currentIndex() == 0)

    def set_edit_mode(self, editing):
        self.script_stack.setCurrentIndex(1 if editing else 0)
        self.edit_button.setText('返回阅读  ↗' if editing else '编辑剧本  ↗')
        if editing:
            self.editor.setFocus()

    def show_source_line(self, line):
        self.set_edit_mode(True)
        self.editor.go_line(line)

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
        self.set_edit_mode(True)
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
            self.set_edit_mode(not parsed.valid)
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
        for control in (self.open_button, self.scan_button, self.apply_button, *self.production_stages): control.setEnabled(False)
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
        for control in (self.open_button, self.scan_button, self.apply_button, *self.production_stages): control.setEnabled(True)
        self.refresh()
        if self.scan_error:
            self.saved.setText('同步未完成')
            self.feedback.setText(self.scan_error)
        else:
            self.saved.setText('素材库已同步')
            self.feedback.setText('LIBRARY  /  素材库已同步   ·   变更与歧义保留人工确认')
        self.reading.setFocus()

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
                done = sum(report[rid]['status'] in ('resolved', 'free') for rid in shot.requirement_ids)
                item = QListWidgetItem(f'{shot.number}  {shot.title}')
                item.setData(Qt.ItemDataRole.UserRole, shot.id)
                item.setData(Qt.ItemDataRole.UserRole + 1, (shot.number, shot.title, done, len(shot.requirement_ids)))
                visual = next((report[rid]['asset'] for rid in shot.requirement_ids
                               if report[rid]['asset'] and report[rid]['asset']['media'] == 'image'
                               and report[rid]['status'] == 'resolved'
                               and report[rid]['requirement']['kind'] == 'environment'), None)
                visual = visual or next((report[rid]['asset'] for rid in shot.requirement_ids
                                         if report[rid]['asset'] and report[rid]['asset']['media'] == 'image'
                                         and report[rid]['status'] == 'resolved'), None)
                if visual:
                    item.setData(Qt.ItemDataRole.UserRole + 2, QPixmap(str(self.workspace.path(visual['path']))))
                self.shots.addItem(item)
                if shot.id == self.shot_id: current = item
            if not current and chapter.shots and not self.chapter_overview:
                current = self.shots.item(0)
                self.shot_id = current.data(Qt.ItemDataRole.UserRole)
        self.shots.setCurrentItem(current)
        self.shot_count.setText(f'{self.shots.count()} 个镜头')
        self.shots.blockSignals(False)

    def chapter_changed(self, *_):
        if self.loading or not self.workspace: return
        self.chapter_id = self.chapters.currentData()
        self.shot_id = None
        self.chapter_overview = False
        self.populate_shots()
        self.persist_selection()
        self.render_summary()
        self.render_requirements()
        if self.current_chapter(): self.editor.go_line(self.current_chapter().line)

    def shot_changed(self, current, previous):
        if self.loading: return
        self.shot_id = current.data(Qt.ItemDataRole.UserRole) if current else None
        self.chapter_overview = False
        self.persist_selection()
        self.render_requirements()
        chapter = self.current_chapter()
        shot = next((s for s in chapter.shots if s.id == self.shot_id), None) if chapter else None
        if shot and self.script_stack.currentIndex() == 1: self.editor.go_line(shot.line)

    def select_chapter(self):
        self.chapter_overview = True
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
            self.chapter_number.setText(chapter.number.zfill(2))
            self.chapter_caption.setText('CHAPTER  /  准备阶段')
            self.summary.setText(f'{counts["resolved"] + counts["free"]} / {counts["total"]}')
            self.progress_bar.set_counts(counts['resolved'] + counts['free'], counts['total'])
            pending = counts['missing'] + counts['unresolved'] + counts['changed']
            self.summary_right.setText(f'{pending} 项待处理  ·  固定参照' if pending else '本章需求已处理')
            self.ready_label.setText('READY' if counts['ready'] and applied else 'DRAFT' if not applied else 'PREP')
        else:
            self.heading.setText('从剧本开始')
            self.chapter_number.setText('—')
            self.ready_label.setText('等待有效剧本')
            self.summary.setText('0 / 0')
            self.progress_bar.set_counts(0, 0)
            self.summary_right.setText('参照就绪')

    def set_mapping_enabled(self, enabled):
        for control in self.findChildren(QPushButton):
            if control.property('mappingAction'): control.setEnabled(enabled)

    def render_requirements(self, *_):
        if not self.workspace: return
        clear(self.cards)
        chapter = self.current_chapter()
        selected = next((s for s in chapter.shots if s.id == self.shot_id), None) if chapter else None
        ids = set(selected.requirement_ids) if selected else {r for s in chapter.shots for r in s.requirement_ids} if chapter else set()
        self.requirement_title.setText('当前镜头资产需求' if selected else '整章资产需求')
        reports = [r for r in self.workspace.report() if r['requirement']['id'] in ids]
        active = next((r for r in reports if r['requirement']['id'] == self.active_requirement_id), None)
        if active is None:
            preferred = (next((r for r in reports if r['status'] == 'missing'), None) or
                         next((r for r in reports if r['status'] == 'free'), None))
            self.active_requirement_id = (preferred or (reports[0] if reports else None))['requirement']['id'] if reports else None
        self.production_button.setEnabled(bool(reports) and self.applied())
        mode = self.filter.currentData()
        visible = [r for r in reports if mode == 'all' or (mode == 'todo' and r['status'] not in ('resolved', 'free'))
                   or (mode == 'resolved' and r['status'] in ('resolved', 'free'))]
        # Preserve declaration order: the media strip follows the executable script.
        desired_requirement = self.active_requirement_id
        available = [r for r in reports if r['status'] == 'resolved' and r['asset']
                     and not r['asset'].get('missing') and not r['asset']['problem']]
        if not any(r['asset']['id'] == self.viewed_asset_id and r['asset']['sha256'] == self.viewed_asset_sha
                   for r in available):
            default = next((r for r in available if r['requirement']['kind'] == 'environment'), None)
            self.select_media(default or (available[0] if available else {'asset': None}))
        self.asset_thumbs = {}
        card_width = max(96, (max(480, self.asset_scroll.viewport().width()) - 40) // 5)
        for report in visible:
            card = self.requirement_card(report)
            card.setFixedWidth(card_width)
            self.cards.addWidget(card)
        if not visible:
            empty, layout = frame('info', (13, 20, 13, 20))
            empty.setMinimumWidth(250)
            layout.addWidget(label('暂无匹配的参照需求' if chapter else '导入剧本后，参照会出现在这里', 'muted', True))
            self.cards.addWidget(empty)
        self.cards.addStretch()
        self.active_requirement_id = desired_requirement
        self.update_asset_selection()
        count = len(self.workspace.state['events'])
        self.impact_button.setText(f'版本与影响  ·  {count}' if count else '版本与影响  ↗')
        pending = [r for r in reports if r['status'] not in ('resolved', 'free')]
        if pending:
            self.attention.setText(f'{len(pending)} 项需求待处理  ·  ' +
                                   '、'.join(dict.fromkeys(STATUS[r['status']][0] for r in pending)))
        else:
            self.attention.setText('当前镜头需求已处理' if reports else '当前范围暂无参照需求')
        self.update_resolution_bar(reports)
        self.update_rework_bar(reports)
        self.set_mapping_enabled(self.applied())
        self.render_script_view()

    def select_media(self, report):
        if 'requirement' in report:
            self.active_requirement_id = report['requirement']['id']
        asset = report['asset']
        if not asset or asset.get('missing') or asset['problem']:
            self.viewer_image.set_source(None)
            self.viewer_image.setText('当前镜头尚无已绑定媒体')
            self.viewer_image.set_media_caption('', '')
            self.viewer_caption.setText('绑定真实素材后，在这里监看参照')
            self.viewer_caption.show()
            self.viewer_open.setEnabled(False)
            self.viewed_asset_id = None
            self.viewed_asset_sha = None
            self.update_asset_selection()
            if hasattr(self, 'resolution_bar'): self.update_resolution_bar()
            if hasattr(self, 'rework_bar'): self.update_rework_bar()
            return
        self.viewed_asset_id = asset['id']
        self.viewed_asset_sha = asset['sha256']
        self.viewer_open.setEnabled(True)
        suffix = Path(asset['path']).suffix[1:].upper()
        demo = 'DEMO  ·  ' if self.workspace.state.get('is_example') else ''
        binding = report.get('binding') or {}
        candidate = self.workspace.state['candidates'].get(binding.get('candidate_id'))
        media_name = (f'{report["requirement"]["name"]}  ·  Take {candidate["take_number"]:02d}'
                      if candidate else asset['name'])
        if asset['media'] == 'image':
            pix = QPixmap(str(self.workspace.path(asset['path'])))
            if pix.isNull():
                self.viewer_image.set_source(None)
                self.viewer_image.setText('来源无法读取  /  请同步素材库')
                self.viewer_caption.setText(demo + asset['name'] + '  /  来源需重新扫描')
                self.viewer_open.setEnabled(False)
            else:
                self.viewer_image.set_source(pix)
                self.viewer_image.set_media_caption(media_name, f'{demo}{pix.width()} × {pix.height()}  /  {suffix}')
                self.viewer_caption.setText(f'{demo}{media_name}  ·  {suffix}')
                self.viewer_caption.hide()
        else:
            self.viewer_image.set_source(None)
            self.viewer_image.setText('▷  视频参照 · 打开预览' if asset['media'] == 'video' else '≋  音声参照 · 打开试听')
            self.viewer_image.set_media_caption('', '')
            self.viewer_caption.setText(f'{demo}{media_name}  ·  {suffix}')
            self.viewer_caption.show()
        self.update_asset_selection()
        if hasattr(self, 'resolution_bar'): self.update_resolution_bar()
        if hasattr(self, 'rework_bar'): self.update_rework_bar()

    def update_asset_selection(self):
        for aid, thumb in getattr(self, 'asset_thumbs', {}).items():
            thumb.setProperty('selected', 'true' if aid == self.viewed_asset_id else 'false')
            thumb.style().unpolish(thumb)
            thumb.style().polish(thumb)

    def inspect_viewed(self):
        asset = self.workspace.state['assets'].get(self.viewed_asset_id)
        if asset and not asset.get('missing') and not asset['problem']:
            MediaDialog(self, asset).exec()

    def requirement_card(self, report):
        req, asset = report['requirement'], report['asset']
        card, layout = frame('assetCard', (0, 0, 0, 0), 1)
        image = button('', lambda: self.select_media(report), 'assetThumb')
        image.setFixedHeight(64 if self.height() < 800 else 78)
        image.setToolTip('监看真实素材  /  ' + req['name'])
        if asset and asset['media'] == 'image' and not asset.get('missing') and not asset['problem']:
            pix = QPixmap(str(self.workspace.path(asset['path'])))
            if not pix.isNull():
                image.setIcon(QIcon(cover_thumbnail(pix, 135, 74)))
                image.setIconSize(QSize(135, 74))
        else:
            image.setText({'image': '▧', 'audio': '≋', 'video': '▷'}[req['media']])
            image.setStyleSheet('font-size:22px;color:#8297aa;')
        if asset and not asset.get('missing') and not asset['problem']:
            self.asset_thumbs[asset['id']] = image
        layout.addWidget(image)
        name = button(req['name'], lambda: self.select_media(report), 'assetName')
        name.setToolTip(req['name'] + '  /  ' + report['reason'])
        layout.addWidget(name)
        kind = label(KINDS[req['kind']], 'muted')
        source_line = next((u['line'] for u in req['usages']
                            if not self.shot_id or u['shot_id'] == self.shot_id), req['usages'][0]['line'])
        source = button(f'L{source_line:03d}', lambda: self.show_source_line(source_line), 'quiet')
        source.setToolTip('定位到可执行剧本中的需求声明')
        source.setStyleSheet('font-size:10px;padding:0;color:#8198ad;')
        layout.addLayout(row(kind, None, source, spacing=1))
        text, ink = STATUS[report['status']]
        state = label('●  ' + text)
        state.setStyleSheet(f'color:{ink};font-size:10px;')
        action = button('查看绑定  ↗' if report['status'] == 'resolved' else
                        '选择处理方式  ↓' if report['status'] in ('missing', 'free')
                        else '处理需求  ↗',
                        (lambda: self.select_media(report)) if report['status'] in ('missing', 'free')
                        else (lambda: self.open_mapping(req['id'])), 'mapAction')
        action.setProperty('mappingAction', True)
        action.setObjectName('map_' + req['id'])
        layout.addLayout(row(state, None, action, spacing=1))
        return card

    def render_script_view(self):
        chapter = self.current_chapter()
        shot = next((s for s in chapter.shots if s.id == self.shot_id), None) if chapter else None
        if not shot and chapter and chapter.shots: shot = chapter.shots[0]
        if not shot:
            self.reading.setHtml('<div style="color:#9aacc0;font-size:14px;margin:35px;">导入或编辑规范剧本，从第一个镜头开始。</div>')
            self.script_context.setText('当前镜头  /  可执行生产剧本')
            return
        self.script_context.setText(f'{chapter.number.zfill(2)}  /  SHOT {shot.number}')
        lines = shot.text.splitlines()
        cast_lines = {c.line-shot.line for c in shot.cast}
        if shot.environment:
            cast_lines.add(max(cast_lines, default=0)+1)
        parts = [f'<div style="margin-bottom:23px;"><span style="font-size:42px;color:#7993ad;font-weight:300;">{html.escape(shot.number)}</span>'
                 f'<span style="font-size:21px;color:#edf2f6;margin-left:15px;font-weight:500;">{html.escape(shot.title)}</span></div>']
        section = None
        for offset, raw in enumerate(lines[1:], 1):
            line = raw.strip()
            if not line:
                parts.append('<div style="height:7px;"></div>')
                continue
            if line.startswith('//'):
                parts.append(f'<div style="color:#7f91a4;font-size:11px;">{html.escape(line)}</div>')
                continue
            match = re.match(r'^(镜头|动作|表演|对白|连续性|备注)[：:](.*)$', line)
            if match:
                section = match.group(1)
                parts.append(f'<div style="color:#9aacc0;font-size:10px;letter-spacing:2px;margin-top:17px;margin-bottom:6px;">{section}</div>')
                line = match.group(2).strip()
                if not line: continue
            safe = html.escape(line)
            safe = re.sub(r'【([^【】]+)】', r'<span style="color:#b8d4e7;border-bottom:1px solid #718ca7;">【\1】</span>', safe)
            if offset in cast_lines:
                color, size, margin = '#d5e2ed', '14px', '3px'
            elif section == '对白':
                color, size, margin = '#e0e8ef', '15px', '6px'
            else:
                color, size, margin = '#d2dce6', '14px', '6px'
            parts.append(f'<div style="color:{color};font-size:{size};line-height:1.8;margin-bottom:{margin};">{safe}</div>')
        self.reading.setHtml('<html><body style="font-family:Microsoft YaHei UI,Segoe UI;'
                             'margin:23px 29px 18px;background:transparent;">' + ''.join(parts) + '</body></html>')
        self.reading.verticalScrollBar().setValue(0)

    def update_resolution_bar(self, reports=None):
        if not self.workspace or not hasattr(self, 'resolution_bar'):
            return
        reports = reports if reports is not None else self.workspace.report()
        selected = next((r for r in reports if r['requirement']['id'] == self.active_requirement_id), None)
        if not selected or selected['status'] not in ('missing', 'free'):
            self.resolution_bar.hide()
            return
        req = selected['requirement']
        self.resolution_label.setText(f'{KINDS[req["kind"]]} · {req["name"]}')
        self.resolution_label.setToolTip(req['name'])
        free = selected['status'] == 'free'
        self.free_button.setText('恢复固定素材' if free else '不需要固定素材')
        self.resolution_bar.show()

    def update_rework_bar(self, reports=None):
        if not self.workspace or not hasattr(self, 'rework_bar'):
            return
        reports = reports if reports is not None else self.workspace.report()
        selected = next((r for r in reports if r['requirement']['id'] == self.active_requirement_id), None)
        if not selected or selected['status'] != 'resolved' or not selected['binding'] or not self.applied():
            self.rework_bar.hide()
            return
        self.rework_label.setText('CURRENT  ·  ' + selected['requirement']['name'])
        self.rework_label.setToolTip('当前素材继续使用；新增 Candidate 不会替换 Current。')
        self.rework_bar.show()

    def rework_generate(self):
        report = next((r for r in self.workspace.report()
                       if r['requirement']['id'] == self.active_requirement_id), None)
        if not report or report['status'] != 'resolved' or not report['binding']:
            self.update_rework_bar()
            return
        rid = report['requirement']['id']
        # Demo image Fixture is the only executable internal production capability today.
        if self.workspace.state.get('is_example') and report['requirement']['media'] == 'image':
            self.open_production(rid)
        else:
            self.open_prompt(rid)

    def rework_import(self):
        report = next((r for r in self.workspace.report()
                       if r['requirement']['id'] == self.active_requirement_id), None)
        if not report or report['status'] != 'resolved' or not report['binding']:
            self.update_rework_bar()
            return
        self.open_production(report['requirement']['id'], import_now=True)

    def toggle_reference_requirement(self):
        rid = self.active_requirement_id
        status = next((r['status'] for r in self.workspace.report()
                       if r['requirement']['id'] == rid), None)
        if status not in ('missing', 'free'):
            return
        self.guard(lambda: self.workspace.set_reference_required(rid, status == 'free'))
        self.refresh()

    def import_for_requirement(self):
        if self.active_requirement_id:
            self.open_production(self.active_requirement_id, import_now=True)

    def open_api_settings(self):
        report = next((r for r in self.workspace.report()
                       if r['requirement']['id'] == self.active_requirement_id), None)
        if report:
            ApiCapabilityDialog(self, report['requirement']).exec()

    def open_prompt(self, requirement_id=None):
        if isinstance(requirement_id, bool):
            requirement_id = None
        if self.worker and self.worker.isRunning():
            self.feedback.setText('素材同步完成后再进入生成。')
            return
        if not self.workspace.script or not self.applied():
            self.feedback.setText('先应用有效剧本，再创建 Prompt Draft。')
            return
        chapter = self.current_chapter()
        if not chapter or not chapter.shots:
            self.feedback.setText('当前章节没有镜头。')
            return
        chosen_shot = self.shot_id
        media = 'image'
        if requirement_id:
            req = next((r for r in self.workspace.script.requirements if r.id == requirement_id), None)
            if not req:
                self.feedback.setText('当前剧本中没有此需求。')
                return
            media = req.media
            selected = next((shot for shot in chapter.shots
                             if shot.id == chosen_shot and requirement_id in shot.requirement_ids), None)
            chosen_shot = selected.id if selected else next(
                (shot.id for shot in chapter.shots if requirement_id in shot.requirement_ids), None)
            if not chosen_shot:
                self.feedback.setText('当前章节中没有此需求。')
                return
        from .preparation.prompt_gui import PromptDialog
        PromptDialog(self, chosen_shot, media=media, requirement_id=requirement_id).exec()
        self.refresh()

    def open_production(self, requirement_id=None, *, import_now=False):
        if self.worker and self.worker.isRunning():
            self.feedback.setText('素材同步完成后再进入生产。')
            return
        if isinstance(requirement_id, bool):
            requirement_id = None
        script = self.workspace.script if self.workspace else None
        if not script or not self.applied():
            self.feedback.setText('先应用有效剧本，再进入生产与判断。')
            return
        chapter = self.current_chapter()
        selected = next((s for s in chapter.shots if s.id == self.shot_id), None) if chapter else None
        ids = (selected.requirement_ids if selected else
               list(dict.fromkeys(r for shot in chapter.shots for r in shot.requirement_ids))) if chapter else []
        reports = [r for r in self.workspace.report() if r['requirement']['id'] in ids]
        rid = requirement_id or self.active_requirement_id
        if rid not in ids:
            missing = next((r for r in reports if r['status'] == 'missing'), None)
            rid = (missing or reports[0])['requirement']['id'] if reports else None
        if not rid:
            self.feedback.setText('当前章节没有可生产的资产需求。')
            return
        self.active_requirement_id = rid
        from .preparation.production_gui import ProductionDialog
        dialog = ProductionDialog(self, rid, self.shot_id if selected and rid in selected.requirement_ids else None)
        if import_now:
            QTimer.singleShot(0, dialog.import_candidate)
        dialog.exec()
        self.refresh()

    def open_mapping(self, rid):
        report = next(r for r in self.workspace.report() if r['requirement']['id'] == rid)
        if (report.get('binding') or {}).get('candidate_id'):
            self.open_production(rid)
            return
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
