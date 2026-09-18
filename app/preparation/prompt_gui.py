"""Prompt work surface for the V0.2 generation stage."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFrame, QHBoxLayout, QLabel, QMessageBox,
    QPlainTextEdit, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from .prompt import MEDIA_NAMES, create_draft, get_draft, save_draft, targets
from .visuals import Atmosphere, STYLE


def note(value='', name='promptMuted', wrap=False):
    widget = QLabel(value)
    widget.setObjectName(name)
    widget.setWordWrap(wrap)
    return widget


def action(value, handler, name='promptQuiet'):
    widget = QPushButton(value)
    widget.setObjectName(name)
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    widget.clicked.connect(handler)
    return widget


class PromptDialog(QDialog):
    def __init__(self, host, shot_id=None):
        super().__init__(host)
        self.workspace = host.workspace
        self.host = host
        self.media = 'image'
        self.current_key = None
        self.loading = False
        self.shot_id = shot_id
        self.setWindowTitle('生成 · Prompt Draft')
        self.resize(min(1180, max(1000, host.width()-55)), min(790, max(650, host.height()-45)))
        self.setMinimumSize(920, 620)
        self.setStyleSheet(STYLE + """
            QLabel#promptKicker { color:#91aac0; font-size:10px; letter-spacing:2px; }
            QLabel#promptTitle { color:#eef4f8; font-size:23px; font-weight:500; }
            QLabel#promptMuted { color:#93a7b9; font-size:11px; }
            QLabel#promptContext { color:#d8e5ee; font-size:12px; }
            QLabel#promptState { color:#b8d0e1; font-size:11px; }
            QLabel#promptIssue { color:#d8b688; font-size:11px; }
            QFrame#promptTop { border-bottom:1px solid rgba(220,237,249,20); }
            QFrame#promptContextSurface { background:rgba(20,33,47,178); border-radius:5px; }
            QFrame#promptEditorSurface { background:#172231; border-radius:5px; }
            QFrame#promptFooter { border-top:1px solid rgba(220,237,249,20); }
            QPlainTextEdit#promptText { background:transparent; color:#e1eaf1; padding:7px 5px;
                font-size:14px; line-height:1.5; }
            QPlainTextEdit#promptConstraints { background:rgba(9,18,29,100);
                border-radius:3px; padding:8px; color:#cbd8e3; font-size:12px; }
            QPushButton#promptMedia { color:#99acbc; font-size:12px; padding:7px 13px; }
            QPushButton#promptMedia:checked { color:#e9f2f8; background:#273c50; }
            QPushButton#promptQuiet { color:#aabccb; }
            QLabel#promptPreview { background:#0f1b28; border-radius:3px; color:#8198ac; }
            QScrollArea#promptContextList, QScrollArea#promptContextList QWidget { background:transparent; border:none; }
        """)
        self.build()
        self.load_shots()

    def build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        background = Atmosphere()
        root.addWidget(background)
        layout = QVBoxLayout(background)
        layout.setContentsMargins(28, 18, 28, 15)
        layout.setSpacing(14)
        header = QFrame()
        header.setObjectName('promptTop')
        top = QVBoxLayout(header)
        top.setContentsMargins(0, 0, 0, 15)
        top.setSpacing(7)
        context = self.workspace.script
        top.addWidget(note(('DEMO  ·  ' if self.workspace.state.get('is_example') else '') +
                           'GENERATE  /  PROMPT COMPOSER', 'promptKicker'))
        bar = QHBoxLayout()
        title = QVBoxLayout()
        title.setSpacing(4)
        title.addWidget(note(context.title, 'promptTitle'))
        title.addWidget(note('规则式语义转译 · Draft 只供编辑与保存，尚未提交任何模型', 'promptMuted'))
        bar.addLayout(title, 1)
        bar.addWidget(action('返回工作区  ↗', self.accept))
        top.addLayout(bar)
        layout.addWidget(header)
        control = QHBoxLayout()
        control.setSpacing(10)
        self.shots = QComboBox()
        self.shots.setMinimumWidth(230)
        self.shots.currentIndexChanged.connect(self.change_shot)
        control.addWidget(note('镜头', 'promptMuted'))
        control.addWidget(self.shots, 1)
        self.media_buttons = {}
        for medium in ('image', 'video', 'audio'):
            btn = action(MEDIA_NAMES[medium].upper(), lambda _=False, m=medium: self.change_media(m), 'promptMedia')
            btn.setCheckable(True)
            self.media_buttons[medium] = btn
            control.addWidget(btn)
        self.target = QComboBox()
        self.target.setMinimumWidth(225)
        self.target.currentIndexChanged.connect(self.change_target)
        control.addWidget(self.target, 1)
        layout.addLayout(control)
        self.subtitle = note('', 'promptContext')
        layout.addWidget(self.subtitle)
        body = QHBoxLayout()
        body.setSpacing(14)
        left = QFrame()
        left.setObjectName('promptContextSurface')
        side = QVBoxLayout(left)
        side.setContentsMargins(16, 17, 16, 15)
        side.setSpacing(10)
        side.addWidget(note('CURRENT SHOT  /  生产上下文', 'promptKicker'))
        self.preview = note('当前无图片参照', 'promptPreview')
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setFixedHeight(145)
        side.addWidget(self.preview)
        self.context_list = QScrollArea()
        self.context_list.setObjectName('promptContextList')
        self.context_list.viewport().setStyleSheet('background:transparent;')
        self.context_list.setWidgetResizable(True)
        self.context_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.context_body = QWidget()
        self.context_body.setStyleSheet('background:transparent;')
        self.context_layout = QVBoxLayout(self.context_body)
        self.context_layout.setContentsMargins(0, 0, 4, 0)
        self.context_layout.setSpacing(9)
        self.context_list.setWidget(self.context_body)
        side.addWidget(self.context_list, 1)
        body.addWidget(left, 4)
        right = QFrame()
        right.setObjectName('promptEditorSurface')
        editor_layout = QVBoxLayout(right)
        editor_layout.setContentsMargins(18, 16, 18, 15)
        editor_layout.setSpacing(8)
        edit_header = QHBoxLayout()
        edit_header.addWidget(note('PROMPT DRAFT', 'promptKicker'))
        edit_header.addStretch()
        self.state_label = note('', 'promptState')
        edit_header.addWidget(self.state_label)
        editor_layout.addLayout(edit_header)
        self.text = QPlainTextEdit()
        self.text.setObjectName('promptText')
        self.text.setPlaceholderText('选择当前任务，创建第一版 Prompt Draft。')
        self.text.textChanged.connect(self.mark_dirty)
        editor_layout.addWidget(self.text, 1)
        editor_layout.addWidget(note('NEGATIVE / CONSTRAINTS  ·  可选', 'promptKicker'))
        self.constraints = QPlainTextEdit()
        self.constraints.setObjectName('promptConstraints')
        self.constraints.setFixedHeight(70)
        self.constraints.setPlaceholderText('仅写对当前任务有帮助的限制。')
        self.constraints.textChanged.connect(self.mark_dirty)
        editor_layout.addWidget(self.constraints)
        body.addWidget(right, 7)
        layout.addLayout(body, 1)
        footer = QFrame()
        footer.setObjectName('promptFooter')
        bottom = QHBoxLayout(footer)
        bottom.setContentsMargins(0, 13, 0, 0)
        self.provenance = note('', 'promptMuted')
        bottom.addWidget(self.provenance, 1)
        self.rebuild_button = action('明确重建', self.rebuild)
        self.create_button = action('创建 Draft', self.create)
        self.save_button = action('保存 Draft  ↗', self.save, 'primary')
        bottom.addWidget(self.rebuild_button)
        bottom.addWidget(self.create_button)
        bottom.addWidget(self.save_button)
        layout.addWidget(footer)

    def load_shots(self):
        self.loading = True
        self.shots.clear()
        chapter = self.host.current_chapter()
        for shot in chapter.shots:
            self.shots.addItem(f'{shot.number}  {shot.title}', shot.id)
        index = self.shots.findData(self.shot_id)
        self.shots.setCurrentIndex(max(0, index))
        self.shot_id = self.shots.currentData()
        self.loading = False
        self.load_targets()

    def change_shot(self):
        if self.loading:
            return
        if not self.maybe_leave():
            self.loading = True
            self.shots.setCurrentIndex(self.shots.findData(self.shot_id))
            self.loading = False
            return
        self.shot_id = self.shots.currentData()
        self.load_targets()

    def change_media(self, media):
        if media == self.media:
            return
        if not self.maybe_leave():
            return
        self.media = media
        self.load_targets()

    def change_target(self):
        if self.loading:
            return
        if not self.maybe_leave():
            self.loading = True
            self.target.setCurrentIndex(self.target.findData(self.selected_requirement))
            self.loading = False
            return
        self.load_draft()

    @property
    def current_requirement(self):
        return self.target.currentData()

    def load_targets(self):
        self.loading = True
        for medium, btn in self.media_buttons.items():
            btn.setChecked(medium == self.media)
        self.target.clear()
        for rid, title in targets(self.workspace, self.shot_id, self.media):
            self.target.addItem(title, rid)
        self.loading = False
        self.load_draft()

    def load_draft(self):
        record, facts, stale = get_draft(self.workspace, self.shot_id, self.media, self.current_requirement)
        self.loading = True
        self.current_key = record['key'] if record else None
        self.selected_requirement = self.current_requirement
        self.text.setPlainText(record['text'] if record else '')
        self.constraints.setPlainText(record['constraints'] if record else '')
        self.loading = False
        self.subtitle.setText(f"{facts['chapter']}   /   SHOT {facts['shot']}   /   {facts['target']}")
        if record:
            status = '上下文已变化 · 请核对' if stale else '人工已修改' if record['edited'] else '已保存'
            self.state_label.setText(status)
            self.provenance.setText('来源  /  规则式转译' + ('  ·  人工修改' if record['edited'] else '') +
                                    ('  ·  当前上下文已变化' if stale else ''))
        else:
            self.state_label.setText('尚无 Draft')
            self.provenance.setText('来源  /  规则式转译 · 未调用模型')
        self.create_button.setVisible(not bool(record))
        self.rebuild_button.setVisible(bool(record))
        self.save_button.setEnabled(bool(record))
        self.show_context(facts)

    def show_context(self, facts):
        while self.context_layout.count():
            item = self.context_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.preview.setPixmap(QPixmap())
        self.preview.setText('当前无图片参照')
        image = next((r for r in facts['references'] if r['kind'] not in ('voice', 'video_reference')), None)
        if image:
            pix = QPixmap(str(self.workspace.path(image['path'])))
            if not pix.isNull():
                self.preview.setPixmap(pix.scaled(280, 145, Qt.AspectRatioMode.KeepAspectRatio,
                                                  Qt.TransformationMode.SmoothTransformation))
                self.preview.setText('')
        parts = []
        if facts['cast']:
            parts.append(('人物', ' · '.join(c['person'] for c in facts['cast']), 'promptContext'))
        if facts['environment'] and facts['environment'] != '-':
            parts.append(('环境', facts['environment'], 'promptContext'))
        if facts['ambience'] and facts['ambience'] != '-' and facts['media'] != 'image':
            parts.append(('背景音', facts['ambience'], 'promptContext'))
        for ref in facts['references']:
            parts.append(('CURRENT REFERENCE', ref['name'] + '\n' + ref['path'], 'promptContext'))
        for item in facts['free']:
            parts.append(('FREE · 无固定参照', item, 'promptMuted'))
        for item in facts['issues']:
            parts.append(('待解决', item, 'promptIssue'))
        if not parts:
            parts.append(('生产上下文', '当前镜头没有额外的固定参照。', 'promptMuted'))
        for heading, value, role in parts:
            self.context_layout.addWidget(note(heading, 'promptKicker'))
            self.context_layout.addWidget(note(value, role, True))
        self.context_layout.addStretch()

    def mark_dirty(self):
        if self.loading or not self.current_key:
            return
        self.state_label.setText('尚未保存')
        self.provenance.setText('人工修改尚未保存')

    def dirty(self):
        if not self.current_key:
            return False
        record = self.workspace.state['prompt_drafts'][self.current_key]
        return (self.text.toPlainText() != record['text'] or
                self.constraints.toPlainText() != record['constraints'])

    def maybe_leave(self):
        if not self.dirty():
            return True
        response = QMessageBox.question(self, '未保存的 Prompt Draft',
                                        '当前 Prompt 有未保存修改。保存后切换？',
                                        QMessageBox.StandardButton.Save |
                                        QMessageBox.StandardButton.Discard |
                                        QMessageBox.StandardButton.Cancel,
                                        QMessageBox.StandardButton.Save)
        if response == QMessageBox.StandardButton.Cancel:
            return False
        if response == QMessageBox.StandardButton.Save:
            return self.save()
        return True

    def create(self):
        try:
            create_draft(self.workspace, self.shot_id, self.media, self.current_requirement)
            self.load_draft()
        except Exception as exc:
            QMessageBox.warning(self, '创建失败', str(exc))

    def rebuild(self):
        if not self.current_key:
            return
        response = QMessageBox.question(self, '明确重建 Prompt Draft',
                                        '将用当前 Production Truth 重建此 Draft，覆盖保存过的人工文本。继续？',
                                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                        QMessageBox.StandardButton.No)
        if response != QMessageBox.StandardButton.Yes:
            return
        try:
            create_draft(self.workspace, self.shot_id, self.media, self.current_requirement, replace=True)
            self.load_draft()
        except Exception as exc:
            QMessageBox.warning(self, '重建失败', str(exc))

    def save(self):
        try:
            current = self.workspace.state['prompt_drafts'][self.current_key]
            save_draft(self.workspace, current['shot_id'], current['media'], current['requirement_id'],
                       self.text.toPlainText(), self.constraints.toPlainText())
            self.load_draft()
            return True
        except Exception as exc:
            QMessageBox.warning(self, '保存失败', str(exc))
            return False

    def accept(self):
        if self.maybe_leave():
            super().accept()

    def reject(self):
        if self.maybe_leave():
            super().reject()
