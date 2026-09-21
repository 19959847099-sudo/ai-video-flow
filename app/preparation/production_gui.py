"""Media-first Candidate production and review for one V0.2 requirement."""
from __future__ import annotations

from PySide6.QtCore import Qt, QSize, QPointF
from PySide6.QtGui import QIcon, QPixmap, QColor, QPainter, QFont, QShortcut, QKeySequence
from PySide6.QtWidgets import (
    QDialog, QFrame, QLabel, QPushButton, QAbstractButton, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QListView, QFileDialog, QMessageBox, QLineEdit,
    QStyledItemDelegate, QStyle,
    QSizePolicy,
)

from .production import ProductionService
from .workspace import EXTENSIONS
from .ui_copy import asset_message, operation_message
from app.shell_theme import D_STYLE, EMBEDDED_D_STYLE


REVIEW = {
    'unreviewed': ('待判断', '#91a6b9', '○'),
    'green': ('', '#42d684', '●'),
    'yellow': ('', '#f2b83f', '●'),
    'red': ('', '#f0645d', '●'),
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


class ReviewDot(QAbstractButton):
    COLORS = {'green': '#42d684', 'yellow': '#f2b83f', 'red': '#f0645d'}

    def __init__(self, state, parent=None):
        super().__init__(parent)
        self.state = state
        self.setCheckable(True)
        self.setFixedSize(31, 31)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName(state)
        self.setToolTip('')

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor(self.COLORS[self.state])
        if not self.isEnabled():
            color.setAlpha(145)
        elif self.underMouse():
            color = color.lighter(118)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        radius = 6.0 if self.underMouse() else 5.4
        painter.drawEllipse(QPointF(self.rect().center()), radius, radius)
        if self.isChecked():
            ring = QColor(self.COLORS[self.state])
            ring.setAlpha(210)
            painter.setPen(ring)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QPointF(self.rect().center()), 10.2, 10.2)
        painter.end()


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
        painter.drawText(rect.left()+10, rect.top()+89, f'版本 {take:02d}')
        painter.setPen(QColor(REVIEW[state][1]))
        painter.setBrush(QColor(REVIEW[state][1]))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(rect.left()+84, rect.top()+83, 9, 9)
        painter.restore()


class ProductionDialog(QDialog):
    def __init__(self, host, requirement_id, shot_id=None, integrated=False):
        super().__init__(host)
        self.host = host
        self.integrated = integrated
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
        """)
        if self.integrated:
            self.setStyleSheet(D_STYLE + EMBEDDED_D_STYLE)
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
        title.addWidget(text('示例项目' if self.host.workspace.state.get('is_example') else '素材', 'eyebrow'))
        title.addWidget(text(self.req.name, 'productionTitle'))
        title.addWidget(text(f'{self.chapter.number.zfill(2)} {self.chapter.title}  ·  镜头 {self.shot.number} {self.shot.title}',
                             'productionSmall'))
        top.addLayout(title, 1)
        self.status = text('', 'productionStatus')
        top.addWidget(self.status, 0, Qt.AlignmentFlag.AlignVCenter)
        if self.integrated:
            top.addWidget(action('准备素材', self.open_preparation, 'quiet'))
            top.addWidget(action('AI 协作', self.open_creative, 'quiet'))
            top.addWidget(action('进入成片', self.open_assembly, 'quiet'))
        top.addWidget(action('返回来源  ↗', self.go_back, 'quiet'), 0, Qt.AlignmentFlag.AlignVCenter)
        root.addLayout(top)

        body = QHBoxLayout()
        body.setSpacing(20)
        left = QFrame()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)
        preview_header = QHBoxLayout()
        self.preview_title = text('', 'sectionTitle')
        self.preview_state = text('', 'productionSmall')
        preview_header.addWidget(self.preview_title)
        preview_header.addStretch()
        preview_header.addWidget(self.preview_state)
        left_layout.addLayout(preview_header)
        self.preview = CandidatePreview()
        self.preview.setText('暂无素材')
        left_layout.addWidget(self.preview, 1)
        preview_footer = QHBoxLayout()
        self.path_note = text('', 'productionSmall')
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
        self.reason = text('', 'productionStatus', True)
        side.addWidget(self.reason)
        self.bound = text('', 'productionSmall', True)
        side.addWidget(self.bound)
        self.fixture_button = action('生成素材  ↗', self.open_generation, 'tool')
        self.fixture_button.setEnabled(True)
        initial_status = next(r['status'] for r in self.host.workspace.report()
                              if r['requirement']['id'] == self.req.id)
        self.fixture_button.setVisible(initial_status != 'free')
        side.addWidget(self.fixture_button)
        self.import_button = action('导入素材  ↗', self.import_candidate, 'tool')
        side.addWidget(self.import_button)
        side.addSpacing(3)
        side.addWidget(text('判断', 'sectionTitle'))
        reviews = QHBoxLayout()
        reviews.setSpacing(4)
        self.review_buttons = {}
        for state in ('green', 'yellow', 'red'):
            control = ReviewDot(state)
            control.clicked.connect(lambda checked=False, choice=state: self.review_selected(choice))
            reviews.addWidget(control)
            self.review_buttons[state] = control
        side.addLayout(reviews)
        self.note = QLineEdit()
        self.note.setObjectName('reviewNote')
        self.note.setPlaceholderText('审核备注（可选）')
        side.addWidget(self.note)
        self.history = text('', 'productionSmall', True)
        side.addWidget(self.history)
        side.addStretch()
        self.bind_button = action('设为当前  ↗', self.bind_selected, 'primary')
        side.addWidget(self.bind_button)
        self.unbind_button = action('取消选用', self.unbind_current)
        side.addWidget(self.unbind_button, 0, Qt.AlignmentFlag.AlignRight)
        body.addWidget(right, 2)
        root.addLayout(body, 1)

        strip_header = QHBoxLayout()
        strip_header.addWidget(text('历史版本', 'eyebrow'))
        strip_header.addStretch()
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

    def _guard(self, operation):
        try:
            return operation()
        except Exception as exc:
            QMessageBox.warning(self, '操作未完成', operation_message(str(exc)))
            return None

    def refresh(self, prefer=None):
        report = next(r for r in self.host.workspace.report() if r['requirement']['id'] == self.req.id)
        self.reason.setText(asset_message(report))
        self.reason.setVisible(bool(asset_message(report)) and asset_message(report) != '缺少素材')
        current = self.service.current(self.req.id)
        self.bound.setText(f'当前使用 · 版本 {self.service.candidate(current).take_number:02d}' if current else '')
        self.bound.setVisible(bool(current))
        candidates = self.service.candidates(self.req.id)
        self.status.setText(('尚未选用' if candidates else '缺少素材') if report['status'] == 'missing' else
                            {'resolved': '', 'free': '无需固定素材', 'unresolved': '待确认',
                             'changed': '文件已变化'}[report['status']])
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
            item = QListWidgetItem(icon, f'版本 {candidate.take_number:02d}')
            item.setData(Qt.ItemDataRole.UserRole, candidate.id)
            item.setData(Qt.ItemDataRole.UserRole + 1, (candidate.take_number, candidate.review_state, candidate.id == current))
            self.list.addItem(item)
        target = prefer or self.selected_id
        index = next((i for i in range(self.list.count())
                      if self.list.item(i).data(Qt.ItemDataRole.UserRole) == target), None)
        if index is None and self.list.count(): index = 0
        self.list.setCurrentRow(index if index is not None else -1)
        self.list.blockSignals(False)
        self.selection_changed(self.list.currentItem(), None)

    def selection_changed(self, current, previous):
        self.selected_id = current.data(Qt.ItemDataRole.UserRole) if current else None
        if not self.selected_id:
            self.preview.set_source(None)
            self.preview.setText('暂无素材')
            self.preview_title.setText('')
            self.preview_state.setText('')
            self.path_note.setText('')
            self.history.setText('')
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
        self.preview_title.setText(f'版本 {candidate.take_number:02d}')
        state_label, color, symbol = REVIEW[candidate.review_state]
        self.preview_state.setText('')
        self.preview_state.setStyleSheet(f'color:{color};')
        self.preview.set_source(QPixmap(str(path)) if path and candidate.media == 'image' else None)
        if candidate.media != 'image':
            self.preview.setText('≋  打开媒体试听' if candidate.media == 'audio'
                                 else '▷  打开媒体预览')
        elif not path:
            self.preview.setText('媒体与历史快照均不可用')
        available = self.service.available(candidate.id)
        self.path_note.setText('来源已变化 · 仅可查看历史版本' if not available else '')
        self.play_button.setEnabled(bool(path) and candidate.media != 'image')
        self.note.setText(candidate.note)
        reviews = [e for e in candidate.history if e['event'] == 'review']
        self.history.setText(f'已判断 {len(reviews)} 次' if len(reviews) > 1 else '')
        for state, control in self.review_buttons.items():
            control.setEnabled(True)
            control.setChecked(state == candidate.review_state)
        already_current = candidate.id == self.service.current(self.req.id)
        self.bind_button.setText('已设为当前' if already_current else '设为当前  ↗')
        self.bind_button.setEnabled(candidate.review_state == 'green' and available and not already_current)
        self.unbind_button.setEnabled(bool(self.service.current(self.req.id)))

    def open_generation(self):
        from .prompt_gui import PromptDialog
        PromptDialog(self.host, self.shot.id, media=self.req.media, requirement_id=self.req.id).exec()
        self.refresh()

    def generate_fixture(self):
        # Compatibility helper used by focused GUI tests; the visible action opens the
        # non-blocking generation workspace above.  It still uses the formal runtime.
        def run():
            from .runtime import ProductionRuntime
            runtime = ProductionRuntime(self.host.workspace)
            model = {'image': 'fixture-image-v1', 'audio': 'fixture-audio-v1',
                     'video': 'fixture-video-v1'}[self.req.media]
            request = runtime.build_request(self.shot.id, self.req.media, self.req.id, model)
            job, _ = runtime.enqueue(request, user_intent='素材生成')
            runtime.run_until_idle()
            result = runtime.job(job.id)
            if result.status != 'succeeded':
                raise ValueError(result.error or '生成未完成')
            self.refresh(result.candidate_ids[0])
        self._guard(run)

    def import_candidate(self):
        patterns = ' '.join('*' + ext for ext in sorted(EXTENSIONS[self.req.media]))
        filename, _ = QFileDialog.getOpenFileName(self, '导入素材', '', f'媒体文件 ({patterns})')
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
        asset['name'] = f'版本 {candidate.take_number:02d}  ·  {self.req.name}'
        from app.preparation_gui import MediaDialog
        MediaDialog(self.host, asset).exec()

    def open_preparation(self):
        if getattr(self.host, "shell", None):
            self.host.shell.navigate("preparation", chapter_id=self.chapter.id,
                shot_id=self.shot.id, object_type="requirement", object_id=self.req.id,
                deep_link=True, reason="制作缺少输入")

    def open_creative(self):
        if getattr(self.host, "shell", None):
            self.host.shell.navigate("creative", chapter_id=self.chapter.id,
                shot_id=self.shot.id, object_type="shot", object_id=self.shot.id,
                deep_link=True, reason="从制作台协作")

    def open_assembly(self):
        if getattr(self.host, "shell", None):
            self.host.shell.navigate("assembly", chapter_id=self.chapter.id,
                shot_id=self.shot.id, deep_link=True, reason="从制作台进入成片")

    def go_back(self):
        if self.integrated and getattr(self.host, "shell", None):
            self.host.shell.return_route()
        else:
            self.accept()

    def closeEvent(self, event):
        self.host.refresh()
        super().closeEvent(event)
