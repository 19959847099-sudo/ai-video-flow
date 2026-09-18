"""Media-first Candidate production and review for one V0.2 requirement."""
from __future__ import annotations

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QPixmap, QColor, QPainter, QFont, QShortcut, QKeySequence
from PySide6.QtWidgets import (
    QDialog, QFrame, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QListView, QFileDialog, QMessageBox, QLineEdit,
    QStyledItemDelegate, QStyle,
    QSizePolicy,
)

from .production import ProductionService
from .workspace import EXTENSIONS


REVIEW = {
    'unreviewed': ('待判断', '#91a6b9', '○'),
    'green': ('Green · 可用', '#8fbdac', '●'),
    'yellow': ('Yellow · 暂缓', '#d7ad79', '●'),
    'red': ('Red · 拒绝', '#d09b87', '●'),
}


def text(value='', role='muted', wrap=False):
    label = QLabel(value)
    label.setObjectName(role)
    label.setWordWrap(wrap)
    return label


def action(value, handler, role='quiet'):
    control = QPushButton(value)
    control.setObjectName(role)
    control.setCursor(Qt.CursorShape.PointingHandCursor)
    control.clicked.connect(handler)
    return control


class CandidatePreview(QLabel):
    def __init__(self):
        super().__init__()
        self.source = None
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumHeight(230)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
        self.setObjectName('candidatePreview')

    def set_source(self, pixmap):
        self.source = pixmap if pixmap and not pixmap.isNull() else None
        self.fit()

    def fit(self):
        if self.source:
            self.setPixmap(self.source.scaled(max(1, self.width()-14), max(1, self.height()-14),
                                              Qt.AspectRatioMode.KeepAspectRatio,
                                              Qt.TransformationMode.SmoothTransformation))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fit()


class CandidateDelegate(QStyledItemDelegate):
    def sizeHint(self, option, index):
        return QSize(184, 97)

    def paint(self, painter, option, index):
        take, state, is_current = index.data(Qt.ItemDataRole.UserRole + 1)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        rect = option.rect.adjusted(2, 2, -4, -3)
        painter.save()
        if selected:
            painter.fillRect(rect, QColor('#1e3042'))
            painter.fillRect(rect.left(), rect.top(), rect.width(), 2, QColor('#bad0df'))
        icon = index.data(Qt.ItemDataRole.DecorationRole)
        pix = icon.pixmap(QSize(154, 60)) if icon else QPixmap()
        if not pix.isNull():
            painter.drawPixmap(rect.left()+10, rect.top()+7, 154, 60, pix)
        painter.setFont(QFont('Segoe UI', 9))
        painter.setPen(QColor('#dce8f0'))
        painter.drawText(rect.left()+10, rect.top()+89, f'TAKE {take:02d}')
        painter.setPen(QColor(REVIEW[state][1]))
        painter.drawText(rect.left()+69, rect.top()+89, state.upper())
        if is_current:
            painter.setPen(QColor('#bcd4e6'))
            painter.drawText(rect.left()+119, rect.top()+89, 'CURRENT')
        painter.restore()


class ProductionDialog(QDialog):
    def __init__(self, host, requirement_id, shot_id=None):
        super().__init__(host)
        self.host = host
        self.service = ProductionService(host.workspace)
        self.req, self.chapter, self.shot = self.service.context(requirement_id, shot_id)
        self.selected_id = None
        self.setWindowTitle('生产与判断  ·  ' + self.req.name)
        self.resize(min(1170, max(950, host.width()-60)), min(790, max(640, host.height()-45)))
        self.setMinimumSize(900, 610)
        self.setStyleSheet(host.styleSheet() + """
            QLabel#productionTitle { font-size:22px; color:#eef3f7; font-weight:500; }
            QLabel#productionSmall { color:#91a6b9; font-size:11px; }
            QLabel#productionStatus { color:#dbe6ef; font-size:13px; }
            QLabel#candidatePreview { background:#111b28; color:#8fa5ba; font-size:17px; border-radius:4px; }
            QFrame#productionRight { background:#172231; border-radius:4px; }
            QListWidget#candidateStrip { background:transparent; }
            QListWidget#candidateStrip::item { border-top:1px solid rgba(220,238,250,15); padding:4px; }
            QListWidget#candidateStrip::item:selected { background:#1e3042; border-top:2px solid #bad0df; }
            QLineEdit#reviewNote { background:#101c29; }
            QPushButton#reviewGreen { color:#9fcbb8; }
            QPushButton#reviewYellow { color:#dfbc8f; }
            QPushButton#reviewRed { color:#dba896; }
            QPushButton#reviewGreen:checked { background:#244337; border:1px solid #668f7b; }
            QPushButton#reviewYellow:checked { background:#493d2c; border:1px solid #a28861; }
            QPushButton#reviewRed:checked { background:#49352f; border:1px solid #9d7062; }
        """)
        self.build()
        self.refresh()
        for key, state in [('1', 'green'), ('2', 'yellow'), ('3', 'red')]:
            shortcut = QShortcut(QKeySequence(key), self.list)
            shortcut.setContext(Qt.ShortcutContext.WidgetShortcut)
            shortcut.activated.connect(lambda choice=state: self.review_selected(choice))

    def build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 18, 24, 13)
        root.setSpacing(10)
        top = QHBoxLayout()
        top.setSpacing(18)
        title = QVBoxLayout()
        title.setSpacing(4)
        title.addWidget(text(('DEMO  ·  ' if self.host.workspace.state.get('is_example') else '') +
                             'PRODUCTION  /  CANDIDATE REVIEW', 'eyebrow'))
        title.addWidget(text(self.req.name, 'productionTitle'))
        title.addWidget(text(f'{self.host.workspace.script.title}   /   {self.chapter.number.zfill(2)} {self.chapter.title}   /   SHOT {self.shot.number} {self.shot.title}',
                             'productionSmall'))
        top.addLayout(title, 1)
        self.status = text('', 'productionStatus')
        top.addWidget(self.status, 0, Qt.AlignmentFlag.AlignVCenter)
        top.addWidget(action('返回镜头  ↗', self.accept, 'quiet'), 0, Qt.AlignmentFlag.AlignVCenter)
        root.addLayout(top)

        body = QHBoxLayout()
        body.setSpacing(20)
        left = QFrame()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)
        preview_header = QHBoxLayout()
        self.preview_title = text('等待 Candidate', 'sectionTitle')
        self.preview_state = text('', 'productionSmall')
        preview_header.addWidget(self.preview_title)
        preview_header.addStretch()
        preview_header.addWidget(self.preview_state)
        left_layout.addLayout(preview_header)
        self.preview = CandidatePreview()
        self.preview.setText('生成或导入后，Candidate 在这里接受判断')
        left_layout.addWidget(self.preview, 1)
        preview_footer = QHBoxLayout()
        self.path_note = text('媒体归档由系统管理', 'productionSmall')
        self.play_button = action('打开媒体  ↗', self.open_media)
        self.play_button.setEnabled(False)
        preview_footer.addWidget(self.path_note, 1)
        preview_footer.addWidget(self.play_button)
        left_layout.addLayout(preview_footer)
        body.addWidget(left, 3)

        right = QFrame()
        right.setObjectName('productionRight')
        right.setMinimumWidth(305)
        side = QVBoxLayout(right)
        side.setContentsMargins(18, 14, 18, 11)
        side.setSpacing(7)
        side.addWidget(text('当前需求  /  状态与上下文', 'eyebrow'))
        self.reason = text('', 'productionStatus', True)
        side.addWidget(self.reason)
        self.bound = text('', 'productionSmall', True)
        side.addWidget(self.bound)
        separator = QFrame()
        separator.setFixedHeight(1)
        separator.setStyleSheet('background:rgba(220,238,250,18);')
        side.addWidget(separator)
        side.addWidget(text('产生新 Candidate', 'sectionTitle'))
        self.fixture_button = action('生成本地示意图  ↗', self.generate_fixture, 'tool')
        self.fixture_button.setEnabled(self.req.media == 'image')
        # The zero-call fixture is evidence tooling, not a fourth formal Missing path.
        self.fixture_button.setVisible(bool(self.host.workspace.state.get('is_example')))
        side.addWidget(self.fixture_button)
        self.import_button = action('导入为 Candidate  ↗', self.import_candidate, 'tool')
        side.addWidget(self.import_button)
        side.addWidget(text('LOCAL FIXTURE  ·  零 API 调用  ·  不自动审核或绑定'
                            if self.host.workspace.state.get('is_example') and self.req.media == 'image'
                            else '导入后先判断 Candidate，再明确选用 Current。',
                            'productionSmall', True))
        side.addSpacing(3)
        side.addWidget(text('判断当前 Candidate', 'sectionTitle'))
        reviews = QHBoxLayout()
        reviews.setSpacing(4)
        self.review_buttons = {}
        for state, caption in [('green', '1  Green'), ('yellow', '2  Yellow'), ('red', '3  Red')]:
            control = action(caption, lambda checked=False, choice=state: self.review_selected(choice),
                             'review'+state.capitalize())
            control.setCheckable(True)
            reviews.addWidget(control)
            self.review_buttons[state] = control
        side.addLayout(reviews)
        self.note = QLineEdit()
        self.note.setObjectName('reviewNote')
        self.note.setPlaceholderText('审核备注（可选）')
        side.addWidget(self.note)
        self.history = text('尚无审核记录', 'productionSmall', True)
        side.addWidget(self.history)
        side.addStretch()
        self.bind_button = action('用于当前 Requirement  ↗', self.bind_selected, 'primary')
        side.addWidget(self.bind_button)
        self.unbind_button = action('解除当前绑定', self.unbind_current)
        side.addWidget(self.unbind_button, 0, Qt.AlignmentFlag.AlignRight)
        body.addWidget(right, 2)
        root.addLayout(body, 1)

        strip_header = QHBoxLayout()
        strip_header.addWidget(text('CANDIDATES  /  历次 Take', 'eyebrow'))
        strip_header.addStretch()
        self.count = text('0 个 Candidate', 'productionSmall')
        strip_header.addWidget(self.count)
        root.addLayout(strip_header)
        self.list = QListWidget()
        self.list.setObjectName('candidateStrip')
        self.list.setViewMode(QListView.ViewMode.IconMode)
        self.list.setItemDelegate(CandidateDelegate(self.list))
        self.list.setFlow(QListView.Flow.LeftToRight)
        self.list.setWrapping(False)
        self.list.setMovement(QListView.Movement.Static)
        self.list.setResizeMode(QListView.ResizeMode.Fixed)
        self.list.setGridSize(QSize(186, 99))
        self.list.setIconSize(QSize(154, 60))
        self.list.setFixedHeight(104)
        self.list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.currentItemChanged.connect(self.selection_changed)
        root.addWidget(self.list)
        root.addWidget(text('Green 表示可用；Current 是另一次明确选择。Yellow 与 Red 保留历史，不进入正常生产。',
                            'productionSmall'))

    def _guard(self, operation):
        try:
            return operation()
        except Exception as exc:
            QMessageBox.warning(self, '操作未完成', str(exc))
            return None

    def refresh(self, prefer=None):
        report = next(r for r in self.host.workspace.report() if r['requirement']['id'] == self.req.id)
        self.reason.setText(report['reason'])
        current = self.service.current(self.req.id)
        self.bound.setText('CURRENT  /  ' + (f'Take {self.service.candidate(current).take_number:02d}' if current else '尚未绑定'))
        self.status.setText({'resolved': '●  Resolved', 'free': '◇  无需固定素材', 'missing': '○  Missing',
                             'unresolved': '◇  待确认', 'changed': '△  已变更'}[report['status']])
        candidates = self.service.candidates(self.req.id)
        candidates.sort(key=lambda c: (c.review_state == 'red', c.take_number))
        self.list.blockSignals(True)
        self.list.clear()
        for candidate in candidates:
            path = self.service.preview_path(candidate.id)
            icon = QIcon()
            if path and candidate.media == 'image':
                pix = QPixmap(str(path))
                if not pix.isNull():
                    icon = QIcon(pix.scaled(120, 69, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                           Qt.TransformationMode.SmoothTransformation))
            if icon.isNull():
                frame = QPixmap(120, 69)
                frame.fill(QColor('#1d3040'))
                painter = QPainter(frame)
                painter.setPen(QColor('#9cafc0'))
                painter.setFont(QFont('Segoe UI', 19))
                painter.drawText(frame.rect(), Qt.AlignmentFlag.AlignCenter,
                                 '≋' if candidate.media == 'audio' else '▷' if candidate.media == 'video' else '▧')
                painter.end()
                icon = QIcon(frame)
            marker = '  CURRENT' if candidate.id == current else ''
            state = REVIEW[candidate.review_state][0]
            item = QListWidgetItem(icon, f'Take {candidate.take_number:02d}{marker}\n{state}')
            item.setData(Qt.ItemDataRole.UserRole, candidate.id)
            item.setData(Qt.ItemDataRole.UserRole + 1, (candidate.take_number, candidate.review_state, candidate.id == current))
            item.setToolTip(f'{candidate.source_type}  ·  {candidate.created_at}\n{candidate.media_path}')
            self.list.addItem(item)
        target = prefer or self.selected_id
        index = next((i for i in range(self.list.count())
                      if self.list.item(i).data(Qt.ItemDataRole.UserRole) == target), None)
        if index is None and self.list.count(): index = 0
        self.list.setCurrentRow(index if index is not None else -1)
        self.list.blockSignals(False)
        self.count.setText(f'{self.list.count()} 个 Candidate  ·  Red 保留在末尾')
        self.selection_changed(self.list.currentItem(), None)

    def selection_changed(self, current, previous):
        self.selected_id = current.data(Qt.ItemDataRole.UserRole) if current else None
        if not self.selected_id:
            self.preview.set_source(None)
            self.preview.setText('生成或导入后，Candidate 在这里接受判断')
            self.preview_title.setText('等待 Candidate')
            self.preview_state.setText('')
            self.path_note.setText('媒体归档由系统管理')
            self.history.setText('尚无审核记录')
            self.note.setText('')
            self.play_button.setEnabled(False)
            self.bind_button.setEnabled(False)
            for control in self.review_buttons.values():
                control.setEnabled(False)
                control.setChecked(False)
            self.unbind_button.setEnabled(bool(self.service.current(self.req.id)))
            return
        candidate = self.service.candidate(self.selected_id)
        path = self.service.preview_path(candidate.id)
        self.preview_title.setText(f'TAKE {candidate.take_number:02d}   /   {candidate.source_type.upper()}')
        state_label, color, symbol = REVIEW[candidate.review_state]
        current_label = '   ·   CURRENT' if candidate.id == self.service.current(self.req.id) else ''
        self.preview_state.setText(f'{symbol}  {state_label}{current_label}')
        self.preview_state.setStyleSheet(f'color:{color};')
        self.preview.set_source(QPixmap(str(path)) if path and candidate.media == 'image' else None)
        if candidate.media != 'image':
            self.preview.setText('≋  音频 Candidate · 打开媒体试听' if candidate.media == 'audio'
                                 else '▷  视频 Candidate · 打开媒体预览')
        elif not path:
            self.preview.setText('媒体与历史快照均不可用')
        available = self.service.available(candidate.id)
        self.path_note.setText(('本地有效' if available else '来源变化或丢失 · 显示历史快照')
                               + f'  ·  {candidate.sha256[:12]}  ·  {candidate.created_at[:16]}')
        self.play_button.setEnabled(bool(path) and candidate.media != 'image')
        self.note.setText(candidate.note)
        reviews = [e for e in candidate.history if e['event'] == 'review']
        self.history.setText(f'{len(reviews)} 次判断  ·  ' +
                             (f'最近：{reviews[-1]["from"]} → {reviews[-1]["to"]}' if reviews else '尚未判断'))
        for state, control in self.review_buttons.items():
            control.setEnabled(True)
            control.setChecked(state == candidate.review_state)
        already_current = candidate.id == self.service.current(self.req.id)
        self.bind_button.setText('已用于当前 Requirement' if already_current else '用于当前 Requirement  ↗')
        self.bind_button.setEnabled(candidate.review_state == 'green' and available and not already_current)
        self.unbind_button.setEnabled(bool(self.service.current(self.req.id)))

    def generate_fixture(self):
        def run():
            job = self.service.create_job(self.req.id, self.shot.id)
            self.service.poll_job(job.id)
            result = self.service.poll_job(job.id)
            if result.status != 'completed':
                raise ValueError(result.error or '本地 Fixture 未完成')
            self.refresh(result.candidate_id)
        self._guard(run)

    def import_candidate(self):
        patterns = ' '.join('*' + ext for ext in sorted(EXTENSIONS[self.req.media]))
        filename, _ = QFileDialog.getOpenFileName(self, '导入为 Candidate', '', f'媒体文件 ({patterns})')
        if not filename: return
        def run():
            candidate = self.service.import_candidate(self.req.id, self.shot.id, filename)
            self.refresh(candidate.id)
        self._guard(run)

    def review_selected(self, state):
        if not self.selected_id: return
        def run():
            self.service.review(self.selected_id, state, self.note.text())
            self.host.refresh()
            self.refresh(self.selected_id)
        self._guard(run)

    def bind_selected(self):
        if not self.selected_id: return
        def run():
            self.service.bind(self.selected_id)
            self.host.refresh()
            self.refresh(self.selected_id)
        self._guard(run)

    def unbind_current(self):
        if not self.service.current(self.req.id): return
        def run():
            self.service.unbind(self.req.id)
            self.host.refresh()
            self.refresh(self.selected_id)
        self._guard(run)

    def open_media(self):
        if not self.selected_id: return
        candidate = self.service.candidate(self.selected_id)
        path = self.service.preview_path(candidate.id)
        if not path: return
        asset = dict(self.host.workspace.state['assets'][candidate.asset_id])
        asset['path'] = path.relative_to(self.host.workspace.root).as_posix()
        asset['name'] = f'Take {candidate.take_number:02d}  ·  {self.req.name}'
        from app.preparation_gui import MediaDialog
        MediaDialog(self.host, asset).exec()

    def closeEvent(self, event):
        self.host.refresh()
        super().closeEvent(event)
