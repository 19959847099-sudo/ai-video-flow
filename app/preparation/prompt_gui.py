"""Prompt work surface for the V0.2 generation stage."""
from __future__ import annotations

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFrame, QHBoxLayout, QLabel, QMessageBox,
    QPlainTextEdit, QPushButton, QScrollArea, QVBoxLayout, QWidget, QListWidget,
    QSpinBox, QDoubleSpinBox, QCheckBox,
)

from .prompt import create_draft, get_draft, save_draft, targets
from .runtime import ProductionRuntime
from .visuals import Atmosphere, STYLE
from .ui_copy import operation_message


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


class RuntimeWorker(QThread):
    completed = Signal()
    failed = Signal(str)

    def __init__(self, runtime, parent=None):
        super().__init__(parent)
        self.runtime = runtime

    def run(self):
        try:
            self.runtime.run_until_idle()
            self.completed.emit()
        except Exception as exc:
            self.failed.emit(str(exc))


class PromptDialog(QDialog):
    def __init__(self, host, shot_id=None, *, media='image', requirement_id=None):
        super().__init__(host)
        self.workspace = host.workspace
        self.host = host
        self.media = media
        self.initial_requirement_id = requirement_id
        self.rework_context = requirement_id is not None
        self.current_key = None
        self.loading = False
        self.shot_id = shot_id
        self.runtime = ProductionRuntime(self.workspace)
        self.worker = None
        self.setWindowTitle('提示词')
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
            QListWidget#runtimeQueue { background:rgba(12,22,33,145); border-radius:4px; padding:4px; }
            QListWidget#runtimeQueue::item { padding:5px 8px; color:#aebfce; }
            QListWidget#runtimeQueue::item:selected { background:#263b50; color:#edf4f9; }
            QLabel#capabilityOk { color:#93bbaa; font-size:11px; }
            QLabel#capabilityIssue { color:#d5a097; font-size:11px; }
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
        top.addWidget(note('示例项目' if self.workspace.state.get('is_example') else '生成', 'promptKicker'))
        bar = QHBoxLayout()
        title = QVBoxLayout()
        title.setSpacing(4)
        title.addWidget(note(context.title, 'promptTitle'))
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
            btn = action({'image': '图片', 'video': '视频', 'audio': '声音'}[medium], lambda _=False, m=medium: self.change_media(m), 'promptMedia')
            btn.setCheckable(True)
            self.media_buttons[medium] = btn
            control.addWidget(btn)
        self.target = QComboBox()
        self.target.setMinimumWidth(210)
        self.target.currentIndexChanged.connect(self.change_target)
        control.addWidget(self.target, 1)
        self.model = QComboBox()
        self.model.setMinimumWidth(220)
        self.model.currentIndexChanged.connect(self.model_changed)
        control.addWidget(self.model)
        self.output_count = QSpinBox()
        self.output_count.setRange(1, 8)
        self.output_count.setValue(1)
        self.output_count.setPrefix('版本  ')
        self.output_count.valueChanged.connect(self.update_capability)
        control.addWidget(self.output_count)
        self.chapter_batch = QCheckBox('本章镜头')
        self.chapter_batch.setToolTip('为本章每个镜头创建独立任务')
        control.addWidget(self.chapter_batch)
        layout.addLayout(control)
        settings = QHBoxLayout()
        settings.setSpacing(8)
        settings.addWidget(note('参数', 'promptMuted'))
        self.aspect = QComboBox()
        for label, value in [('自动比例', None), ('16:9', '16:9'), ('9:16', '9:16'), ('1:1', '1:1')]:
            self.aspect.addItem(label, value)
        self.resolution = QComboBox()
        for label, value in [('自动分辨率', None), ('1280 × 720', '1280x720'), ('1920 × 1080', '1920x1080')]:
            self.resolution.addItem(label, value)
        self.duration = QDoubleSpinBox(); self.duration.setRange(.5, 30); self.duration.setValue(3)
        self.duration.setSuffix(' 秒')
        self.frame_rate = QSpinBox(); self.frame_rate.setRange(12, 60); self.frame_rate.setValue(24)
        self.frame_rate.setSuffix(' fps')
        self.seed = QSpinBox(); self.seed.setRange(-1, 2147483647); self.seed.setValue(-1)
        self.seed.setSpecialValueText('随机 Seed')
        for widget in (self.aspect, self.resolution, self.duration, self.frame_rate, self.seed):
            settings.addWidget(widget)
            if hasattr(widget, 'currentIndexChanged'):
                widget.currentIndexChanged.connect(self.update_capability)
            else:
                widget.valueChanged.connect(self.update_capability)
        settings.addStretch()
        layout.addLayout(settings)
        body = QHBoxLayout()
        body.setSpacing(14)
        left = QFrame()
        left.setObjectName('promptContextSurface')
        side = QVBoxLayout(left)
        side.setContentsMargins(16, 17, 16, 15)
        side.setSpacing(10)
        side.addWidget(note('镜头参考', 'promptKicker'))
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
        edit_header.addWidget(note('提示词', 'promptKicker'))
        edit_header.addStretch()
        self.state_label = note('', 'promptState')
        edit_header.addWidget(self.state_label)
        editor_layout.addLayout(edit_header)
        self.text = QPlainTextEdit()
        self.text.setObjectName('promptText')
        self.text.setPlaceholderText('创建提示词')
        self.text.textChanged.connect(self.mark_dirty)
        editor_layout.addWidget(self.text, 1)
        editor_layout.addWidget(note('限制条件', 'promptKicker'))
        self.constraints = QPlainTextEdit()
        self.constraints.setObjectName('promptConstraints')
        self.constraints.setFixedHeight(70)
        self.constraints.setPlaceholderText('可选')
        self.constraints.textChanged.connect(self.mark_dirty)
        editor_layout.addWidget(self.constraints)
        body.addWidget(right, 7)
        layout.addLayout(body, 1)
        queue_bar = QHBoxLayout()
        queue_bar.addWidget(note('生产队列', 'promptKicker'))
        self.capability_label = note('', 'capabilityOk')
        queue_bar.addWidget(self.capability_label)
        queue_bar.addStretch()
        layout.addLayout(queue_bar)
        self.queue = QListWidget()
        self.queue.setObjectName('runtimeQueue')
        self.queue.setFixedHeight(104)
        layout.addWidget(self.queue)
        footer = QFrame()
        footer.setObjectName('promptFooter')
        bottom = QHBoxLayout(footer)
        bottom.setContentsMargins(0, 13, 0, 0)
        bottom.addStretch(1)
        self.provider_hint = note('本地 Fixture · ZERO-CALL', 'promptMuted')
        self.provider_hint.setVisible(True)
        bottom.addWidget(self.provider_hint)
        self.add_api_button = action('查看  ↗', self.show_add_api)
        self.add_api_button.setVisible(False)
        bottom.addWidget(self.add_api_button)
        self.rebuild_button = action('重新生成', self.rebuild)
        self.create_button = action('创建', self.create)
        self.save_button = action('保存', self.save, 'promptQuiet')
        self.cancel_button = action('取消任务', self.cancel_job)
        self.retry_button = action('重试', self.retry_job)
        self.review_button = action('查看结果  ↗', self.open_results)
        self.generate_button = action('开始生成', self.submit_generation, 'primary')
        bottom.addWidget(self.rebuild_button)
        bottom.addWidget(self.create_button)
        bottom.addWidget(self.save_button)
        bottom.addWidget(self.cancel_button)
        bottom.addWidget(self.retry_button)
        bottom.addWidget(self.review_button)
        bottom.addWidget(self.generate_button)
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
        self.load_models()
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
            self.target.addItem(title.replace('SHOT ', '镜头 '), rid)
        if self.initial_requirement_id:
            index = self.target.findData(self.initial_requirement_id)
            if index >= 0:
                self.target.setCurrentIndex(index)
            self.initial_requirement_id = None
        self.loading = False
        self.load_models()
        self.load_draft()

    def load_models(self):
        if not hasattr(self, 'model'):
            return
        current = self.model.currentData()
        self.model.blockSignals(True)
        self.model.clear()
        task = ('shot_video' if self.media == 'video' and not self.current_requirement else
                'video_reference' if self.media == 'video' else
                'asset_audio' if self.media == 'audio' else 'asset_image')
        self.chapter_batch.setVisible(task == 'shot_video')
        if task != 'shot_video':
            self.chapter_batch.setChecked(False)
        for manifest in self.runtime.registry.models_for(task, self.media):
            self.model.addItem(manifest.display_name, manifest.id)
        index = self.model.findData(current)
        self.model.setCurrentIndex(index if index >= 0 else 0)
        self.model.blockSignals(False)
        self.model_changed()

    def model_changed(self):
        if not self.model.currentData():
            return
        controls = self.runtime.registry.model(self.model.currentData()).common_controls
        self.aspect.setVisible(self.media in ('image', 'video') and 'aspect_ratio' in controls)
        self.resolution.setVisible(self.media in ('image', 'video') and 'resolution' in controls)
        self.duration.setVisible(self.media in ('audio', 'video') and 'duration' in controls)
        self.frame_rate.setVisible(self.media == 'video' and 'frame_rate' in controls)
        self.seed.setVisible('seed' in controls)
        self.update_capability()

    def update_capability(self):
        if self.loading or not self.model.currentData() or not self.shot_id:
            return
        try:
            request = self.runtime.build_request(self.shot_id, self.media, self.current_requirement,
                                                 self.model.currentData(), output_count=self.output_count.value(),
                                                 common=self.common_controls())
            report = self.runtime.capability(request)
            self.capability_label.setText('原生支持' if report.state == 'NATIVE' else
                                          '已明确转换' if report.state == 'TRANSLATED' else
                                          ' · '.join(report.reasons))
            self.capability_label.setObjectName('capabilityOk' if report.state != 'UNSUPPORTED' else 'capabilityIssue')
            self.capability_label.style().unpolish(self.capability_label)
            self.capability_label.style().polish(self.capability_label)
            self.generate_button.setEnabled(report.state != 'UNSUPPORTED')
        except Exception as exc:
            self.capability_label.setText(str(exc))
            self.generate_button.setEnabled(False)
        self.refresh_queue()

    def load_draft(self):
        record, facts, stale = get_draft(self.workspace, self.shot_id, self.media, self.current_requirement)
        self.loading = True
        self.current_key = record['key'] if record else None
        self.selected_requirement = self.current_requirement
        self.text.setPlainText(record['text'] if record else '')
        self.constraints.setPlainText(record['constraints'] if record else '')
        self.loading = False
        if record:
            status = '参考已变化 · 请核对' if stale else '已保存'
            self.state_label.setText(status)
        else:
            self.state_label.setText('')
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
            parts.append(('参考素材', ref['name'], 'promptContext'))
        if facts['free']:
            parts.append(('无需固定素材', '、'.join(facts['free']), 'promptMuted'))
        if facts['issues']:
            parts.append(('待处理', '\n'.join(facts['issues']), 'promptIssue'))
        if not parts:
            parts.append(('', '暂无固定参考', 'promptMuted'))
        for heading, value, role in parts:
            if heading:
                self.context_layout.addWidget(note(heading, 'promptKicker'))
            self.context_layout.addWidget(note(value, role, True))
        self.context_layout.addStretch()

    def mark_dirty(self):
        if self.loading or not self.current_key:
            return
        self.state_label.setText('尚未保存')

    def dirty(self):
        if not self.current_key:
            return False
        record = self.workspace.state['prompt_drafts'][self.current_key]
        return (self.text.toPlainText() != record['text'] or
                self.constraints.toPlainText() != record['constraints'])

    def maybe_leave(self):
        if not self.dirty():
            return True
        response = QMessageBox.question(self, '修改未保存',
                                        '保存后再切换？',
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
            QMessageBox.warning(self, '创建失败', operation_message(str(exc)))

    def rebuild(self):
        if not self.current_key:
            return
        response = QMessageBox.question(self, '重新生成提示词',
                                        '这会覆盖已保存的手工修改。继续？',
                                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                        QMessageBox.StandardButton.No)
        if response != QMessageBox.StandardButton.Yes:
            return
        try:
            create_draft(self.workspace, self.shot_id, self.media, self.current_requirement, replace=True)
            self.load_draft()
        except Exception as exc:
            QMessageBox.warning(self, '重建失败', operation_message(str(exc)))

    def show_add_api(self):
        rid = self.current_requirement
        if not rid:
            return
        req = next(r for r in self.workspace.script.requirements if r.id == rid)
        from app.preparation_gui import ApiCapabilityDialog
        ApiCapabilityDialog(self.host, req.model_dump()).exec()

    def save(self):
        try:
            current = self.workspace.state['prompt_drafts'][self.current_key]
            save_draft(self.workspace, current['shot_id'], current['media'], current['requirement_id'],
                       self.text.toPlainText(), self.constraints.toPlainText())
            self.load_draft()
            return True
        except Exception as exc:
            QMessageBox.warning(self, '保存失败', operation_message(str(exc)))
            return False

    def common_controls(self):
        return {'aspect_ratio': self.aspect.currentData() if self.aspect.isVisible() else None,
                'resolution': self.resolution.currentData() if self.resolution.isVisible() else None,
                'duration': self.duration.value() if self.duration.isVisible() else None,
                'frame_rate': self.frame_rate.value() if self.frame_rate.isVisible() else None,
                'seed': None if self.seed.value() < 0 else self.seed.value()}

    def submit_generation(self):
        try:
            if not self.current_key:
                create_draft(self.workspace, self.shot_id, self.media, self.current_requirement)
                self.load_draft()
            if self.dirty() and not self.save():
                return
            request = self.runtime.build_request(
                self.shot_id, self.media, self.current_requirement, self.model.currentData(),
                output_count=self.output_count.value(), prompt_text=self.text.toPlainText(),
                constraints=self.constraints.toPlainText(),
                common=self.common_controls())
            if self.chapter_batch.isChecked() and request.task == 'shot_video':
                requests = [self.runtime.build_request(
                    shot.id, 'video', None, self.model.currentData(),
                    output_count=self.output_count.value(),
                    common=self.common_controls())
                    for shot in self.host.current_chapter().shots]
                self.runtime.enqueue_many(requests, user_intent='本章镜头批量生成')
            else:
                self.runtime.enqueue(request, user_intent='当前目标生成')
            self.refresh_queue()
            self.start_worker()
        except Exception as exc:
            QMessageBox.warning(self, '无法开始生成', operation_message(str(exc)))

    def start_worker(self):
        if self.worker and self.worker.isRunning():
            return
        self.generate_button.setEnabled(False)
        self.worker = RuntimeWorker(self.runtime, self.host)
        self.worker.completed.connect(self.worker_done)
        self.worker.failed.connect(self.worker_failed)
        self.worker.start()

    def worker_done(self):
        self.generate_button.setEnabled(True)
        self.refresh_queue()
        self.host.refresh()

    def worker_failed(self, message):
        self.generate_button.setEnabled(True)
        self.refresh_queue()
        QMessageBox.warning(self, '生产队列异常', operation_message(message))

    def refresh_queue(self):
        if not hasattr(self, 'queue'):
            return
        selected = self.queue.currentItem().data(Qt.ItemDataRole.UserRole) if self.queue.currentItem() else None
        self.queue.clear()
        jobs = [self.runtime.job(jid) for jid in self.workspace.state.get('runtime_jobs', {})]
        jobs = [job for job in jobs if job.shot_id == self.shot_id]
        labels = {'queued': '等待', 'running': '生成中', 'succeeded': '已完成',
                  'failed': '失败', 'canceled': '已取消'}
        for job in reversed(jobs[-12:]):
            suffix = f' · {job.error}' if job.error else f' · {len(job.candidate_ids)} 个结果' if job.candidate_ids else ''
            from PySide6.QtWidgets import QListWidgetItem
            item = QListWidgetItem(f'{labels[job.status]}  {job.model_id}  ·  第 {job.attempt} 次{suffix}')
            item.setData(Qt.ItemDataRole.UserRole, job.id)
            self.queue.addItem(item)
            if job.id == selected:
                self.queue.setCurrentItem(item)
        if not self.queue.currentItem() and self.queue.count():
            self.queue.setCurrentRow(0)

    def selected_job(self):
        item = self.queue.currentItem()
        return self.runtime.job(item.data(Qt.ItemDataRole.UserRole)) if item else None

    def cancel_job(self):
        job = self.selected_job()
        if job:
            self.runtime.cancel(job.id)
            self.refresh_queue()

    def retry_job(self):
        job = self.selected_job()
        if not job:
            return
        try:
            self.runtime.retry(job.id, model_settings={'fixture_mode': 'success'})
            self.refresh_queue(); self.start_worker()
        except Exception as exc:
            QMessageBox.warning(self, '无法重试', operation_message(str(exc)))

    def open_results(self):
        job = self.selected_job()
        if not job or not job.candidate_ids:
            return
        if job.requirement_id:
            from .production_gui import ProductionDialog
            ProductionDialog(self.host, job.requirement_id, job.shot_id).exec()
        else:
            from .finishing_gui import ShotCandidateDialog
            ShotCandidateDialog(self.host, job.shot_id).exec()
        self.refresh_queue()

    def accept(self):
        if self.maybe_leave():
            super().accept()

    def reject(self):
        if self.maybe_leave():
            super().reject()
