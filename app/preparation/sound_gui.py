"""Dialogue, voice, background and subtitle work surface for V0.2."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFileDialog,
    QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox,
    QPushButton, QScrollArea, QSpinBox, QVBoxLayout, QWidget)

from .prompt_gui import RuntimeWorker
from .production_gui import ReviewDot
from .sound import SoundProduction
from .workspace import EXTENSIONS
from .ui_copy import operation_message


def label(text='', role='soundMuted', wrap=False):
    item = QLabel(text); item.setObjectName(role); item.setWordWrap(wrap); return item


def button(text, callback, role='quiet'):
    item = QPushButton(text); item.setObjectName(role); item.setCursor(Qt.CursorShape.PointingHandCursor)
    item.clicked.connect(callback); return item


class SoundDialog(QDialog):
    def __init__(self, host, shot_id=None):
        super().__init__(host)
        self.host = host; self.workspace = host.workspace
        self.sound = SoundProduction(self.workspace); self.production = self.sound.production
        self.chapter = host.current_chapter(); self.shot_id = shot_id or self.chapter.shots[0].id
        self.worker = None; self.updating = False
        self.player = QMediaPlayer(self); self.audio_output = QAudioOutput(self)
        self.player.setAudioOutput(self.audio_output)
        self.setWindowTitle('对白、声音与字幕')
        self.resize(min(1240, max(980, host.width()-45)), min(850, max(660, host.height()-35)))
        self.setMinimumSize(950, 640)
        self.setStyleSheet(host.styleSheet() + '''
            QDialog { background:#0d1725; color:#dce8f1; }
            QLabel#soundTitle { font-size:23px; color:#eef4f8; font-weight:500; }
            QLabel#soundMuted { color:#8fa5b8; font-size:11px; }
            QLabel#soundText { color:#e1ebf2; font-size:15px; }
            QFrame#soundInspector { background:#172636; border-radius:5px; }
            QListWidget#soundItems { background:rgba(14,26,40,180); border:0; padding:6px; }
            QListWidget#soundItems::item { padding:9px 8px; min-height:38px; }
            QListWidget#soundItems::item:selected { background:#263d53; color:#f0f5f8; }
            QListWidget#soundCandidates { background:#101c2a; border:0; }
            QListWidget#soundCandidates::item { padding:7px; }
            QListWidget#soundCandidates::item:selected { background:#294258; }
            QLineEdit { background:#101c2a; }
        ''')
        self.build(); self.refresh_items()

    def build(self):
        root = QVBoxLayout(self); root.setContentsMargins(25, 18, 25, 16); root.setSpacing(12)
        top = QHBoxLayout(); titles = QVBoxLayout()
        titles.addWidget(label(f'第 {self.chapter.number} 章', 'soundMuted'))
        titles.addWidget(label('对白、声音与字幕', 'soundTitle'))
        top.addLayout(titles, 1)
        self.summary = label('', 'soundMuted'); top.addWidget(self.summary)
        top.addWidget(button('返回轻剪  ↗', self.accept))
        root.addLayout(top)
        body = QHBoxLayout(); body.setSpacing(16)
        self.items = QListWidget(); self.items.setObjectName('soundItems'); self.items.setMinimumWidth(270)
        self.items.currentItemChanged.connect(lambda *_: self.selection_changed())
        body.addWidget(self.items, 2)
        inspector = QFrame(); inspector.setObjectName('soundInspector')
        side = QVBoxLayout(inspector); side.setContentsMargins(18,16,18,14); side.setSpacing(8)
        self.kind_label = label('', 'soundMuted'); side.addWidget(self.kind_label)
        self.speaker = label('', 'soundTitle'); side.addWidget(self.speaker)
        self.words = label('', 'soundText', True); side.addWidget(self.words)
        self.voice = label('', 'soundMuted', True); side.addWidget(self.voice)
        policy = QHBoxLayout(); policy.addWidget(label('声音来源', 'soundMuted'))
        self.strategy = QComboBox()
        for title, value in [('视频原声', 'native'), ('独立对白', 'independent'), ('无对白音声', 'none')]:
            self.strategy.addItem(title, value)
        self.strategy.currentIndexChanged.connect(self.apply_strategy); policy.addWidget(self.strategy, 1)
        self.voice_button = button('声音素材  ↗', self.open_voice, 'quiet'); policy.addWidget(self.voice_button)
        side.addLayout(policy)
        candidate_head = QHBoxLayout(); candidate_head.addWidget(label('声音版本', 'soundMuted')); candidate_head.addStretch()
        self.current_label = label('', 'soundMuted'); candidate_head.addWidget(self.current_label); side.addLayout(candidate_head)
        self.candidates = QListWidget(); self.candidates.setObjectName('soundCandidates'); self.candidates.setFixedHeight(112)
        self.candidates.currentItemChanged.connect(lambda *_: self.candidate_changed()); side.addWidget(self.candidates)
        actions = QHBoxLayout()
        self.generate = button('生成 3 个', self.generate_current, 'tool'); actions.addWidget(self.generate)
        self.import_button = button('导入音频', self.import_audio, 'quiet'); actions.addWidget(self.import_button)
        self.play_button = button('试听', self.play, 'quiet'); actions.addWidget(self.play_button)
        actions.addStretch(); self.dots = {}
        for state in ('green','yellow','red'):
            dot=ReviewDot(state); dot.clicked.connect(lambda checked=False, value=state:self.review(value)); actions.addWidget(dot); self.dots[state]=dot
        self.bind_button=button('设为当前  ↗',self.bind,'primary'); actions.addWidget(self.bind_button); side.addLayout(actions)
        settings = QHBoxLayout(); settings.addWidget(label('开始', 'soundMuted'))
        self.start = QDoubleSpinBox(); self.start.setRange(0,999); self.start.setDecimals(2); self.start.setSuffix(' s'); settings.addWidget(self.start)
        settings.addWidget(label('音量', 'soundMuted')); self.volume=QDoubleSpinBox(); self.volume.setRange(0,2); self.volume.setSingleStep(.1); self.volume.setValue(1); self.volume.setSuffix(' ×'); settings.addWidget(self.volume)
        self.enabled=QCheckBox('启用'); self.mute=QCheckBox('静音'); settings.addWidget(self.enabled); settings.addWidget(self.mute)
        self.apply_audio=button('应用',self.apply_audio_settings,'quiet'); settings.addWidget(self.apply_audio); side.addLayout(settings)
        self.subtitle_frame=QFrame(); subtitle=QVBoxLayout(self.subtitle_frame); subtitle.setContentsMargins(0,8,0,0)
        subtitle.addWidget(label('字幕', 'soundMuted')); self.subtitle_text=QLineEdit(); subtitle.addWidget(self.subtitle_text)
        timing=QHBoxLayout(); self.subtitle_enabled=QCheckBox('显示'); timing.addWidget(self.subtitle_enabled)
        self.subtitle_start=QDoubleSpinBox(); self.subtitle_end=QDoubleSpinBox()
        for control in (self.subtitle_start,self.subtitle_end): control.setRange(0,999); control.setDecimals(2); control.setSuffix(' s'); timing.addWidget(control)
        timing.addWidget(button('保存字幕',self.save_subtitle,'quiet')); subtitle.addLayout(timing); side.addWidget(self.subtitle_frame)
        self.stale=label('', 'soundMuted', True); side.addWidget(self.stale); side.addStretch()
        scroll=QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.Shape.NoFrame); scroll.setWidget(inspector); body.addWidget(scroll,5)
        root.addLayout(body,1)
        foot=QHBoxLayout(); self.message=label('', 'soundMuted'); foot.addWidget(self.message,1)
        foot.addWidget(button('生成本镜头对白',self.generate_shot,'quiet'))
        foot.addWidget(button('补齐本章对白',self.generate_chapter,'quiet')); root.addLayout(foot)

    def records(self):
        rows=[]
        for shot in self.chapter.shots:
            for dialogue in self.sound.dialogues(shot_id=shot.id): rows.append(('dialogue',dialogue.id,shot,dialogue))
            for background in self.sound.background_items(shot_id=shot.id): rows.append(('background',background.id,shot,background))
        return rows

    def selected(self):
        item=self.items.currentItem(); key=item.data(Qt.ItemDataRole.UserRole) if item else None
        return next((row for row in self.records() if row[0]+':'+row[1]==key),None)

    def selected_candidate(self):
        item=self.candidates.currentItem(); return item.data(Qt.ItemDataRole.UserRole) if item else None

    def guard(self, operation):
        try:return operation()
        except Exception as exc: QMessageBox.warning(self,'操作未完成',operation_message(str(exc))); return None

    def refresh_items(self, preferred=None):
        key=preferred or (self.items.currentItem().data(Qt.ItemDataRole.UserRole) if self.items.currentItem() else None)
        self.items.blockSignals(True); self.items.clear(); ready=0
        for kind,identifier,shot,value in self.records():
            if kind=='dialogue':
                current=self.sound.current_dialogue(identifier); state=self.sound.state(identifier)
                title=f'{shot.number}  {value.speaker}'; detail=value.text
                ready += bool(current or state.strategy in ('native','none'))
            else:
                current=self.sound.current_background(identifier); title=f'{shot.number}  背景音'; detail=value.text; ready += bool(current)
            item=QListWidgetItem(f'{title}\n{detail[:25]}'); item.setData(Qt.ItemDataRole.UserRole,kind+':'+identifier); self.items.addItem(item)
            if item.data(Qt.ItemDataRole.UserRole)==key:self.items.setCurrentItem(item)
        if not self.items.currentItem() and self.items.count():self.items.setCurrentRow(0)
        self.items.blockSignals(False); self.summary.setText(f'{ready}/{self.items.count()} 已安排'); self.selection_changed()

    def selection_changed(self):
        row=self.selected(); self.updating=True
        if not row:self.updating=False;return
        kind,identifier,shot,value=row; is_dialogue=kind=='dialogue'
        self.kind_label.setText(f'镜头 {shot.number} · '+('对白' if is_dialogue else '环境声音'))
        self.speaker.setText(value.speaker if is_dialogue else '背景音')
        self.words.setText(value.text); self.strategy.setVisible(is_dialogue); self.voice_button.setVisible(is_dialogue); self.subtitle_frame.setVisible(is_dialogue)
        if is_dialogue:
            state=self.sound.state(identifier); self.strategy.setCurrentIndex(self.strategy.findData(state.strategy))
            self.start.setValue(state.start); self.volume.setValue(state.volume); self.enabled.setChecked(state.enabled); self.mute.setChecked(state.mute)
            voice='无角色音声' if not value.voice_requirement_id else '使用当前声音素材；没有固定素材时使用剧本声音描述'
            self.voice.setText(voice); current=self.sound.current_dialogue(identifier); candidates=self.sound.dialogue_candidates(identifier)
            subtitle=self.sound.subtitle(identifier); self.subtitle_text.setText(subtitle.display_text); self.subtitle_start.setValue(subtitle.start); self.subtitle_end.setValue(subtitle.end); self.subtitle_enabled.setChecked(subtitle.enabled)
            self.stale.setText('正式对白已变化 · 人工字幕保留待核对' if subtitle.stale else '')
            self.generate.setEnabled(bool(value.voice_requirement_id))
        else:
            state=self.workspace.state['background_states'][identifier]; self.start.setValue(state['start']); self.volume.setValue(state['volume']); self.enabled.setChecked(state['enabled']); self.mute.setChecked(state['mute'])
            self.voice.setText('独立背景音，不替代对白或视频原声'); current=self.sound.current_background(identifier); candidates=self.sound.background_candidates(identifier); self.stale.setText('')
            self.generate.setEnabled(True)
        self.current_label.setText('已有当前版本' if current else '尚未选用')
        self.candidates.blockSignals(True); self.candidates.clear()
        for candidate in candidates:
            item=QListWidgetItem(f'版本 {candidate.take_number:02d}  ·  '+{'unreviewed':'待判断','green':'可用','yellow':'待定','red':'废弃'}[candidate.review_state]); item.setData(Qt.ItemDataRole.UserRole,candidate.id); self.candidates.addItem(item)
            if candidate.id==current:self.candidates.setCurrentItem(item)
        if not self.candidates.currentItem() and self.candidates.count():self.candidates.setCurrentRow(0)
        self.candidates.blockSignals(False); self.updating=False; self.candidate_changed()

    def candidate_changed(self):
        cid=self.selected_candidate()
        if not cid:
            self.bind_button.setEnabled(False); self.play_button.setEnabled(False)
            for dot in self.dots.values():dot.setEnabled(False);dot.setChecked(False)
            return
        candidate=self.production.candidate(cid); current=(self.sound.current_dialogue(candidate.dialogue_id) if candidate.dialogue_id else self.sound.current_background(candidate.background_id))
        for state,dot in self.dots.items():dot.setEnabled(True);dot.setChecked(candidate.review_state==state)
        self.bind_button.setEnabled(candidate.review_state=='green' and self.production.available(cid) and cid!=current); self.play_button.setEnabled(self.production.available(cid))
        if self.sound.candidate_stale(cid):self.stale.setText('这个版本基于较早的剧本、声音或环境描述')

    def apply_strategy(self):
        if self.updating:return
        row=self.selected()
        if row and row[0]=='dialogue':self.guard(lambda:self.sound.update_state(row[1],strategy=self.strategy.currentData()));self.refresh_items('dialogue:'+row[1])

    def apply_audio_settings(self):
        row=self.selected()
        if not row:return
        changes=dict(start=self.start.value(),volume=self.volume.value(),enabled=self.enabled.isChecked(),mute=self.mute.isChecked())
        if row[0]=='dialogue':self.guard(lambda:self.sound.update_state(row[1],**changes))
        else:self.guard(lambda:self.sound.update_background(row[1],**changes))
        self.refresh_items(row[0]+':'+row[1])

    def save_subtitle(self):
        row=self.selected()
        if row and row[0]=='dialogue':self.guard(lambda:self.sound.update_subtitle(row[1],display_text=self.subtitle_text.text(),start=self.subtitle_start.value(),end=self.subtitle_end.value(),enabled=self.subtitle_enabled.isChecked()));self.refresh_items('dialogue:'+row[1])

    def generate_current(self):
        row=self.selected()
        if not row:return
        request=self.guard(lambda:(self.sound.build_dialogue_request(row[1],output_count=3)
                            if row[0]=='dialogue' else self.sound.build_background_request(row[1],output_count=3)))
        if request and self.guard(lambda:self.sound.runtime.enqueue(request,user_intent='声音多版本')):
            self.start_worker()

    def _batch(self, rows, intent):
        requests=[]
        for kind,identifier,shot,value in rows:
            if kind=='dialogue' and value.voice_requirement_id and not self.sound.current_dialogue(identifier):
                request=self.guard(lambda:self.sound.build_dialogue_request(identifier))
                if request:requests.append(request)
        if requests and self.guard(lambda:self.sound.runtime.enqueue_many(requests,user_intent=intent)):
            self.start_worker()

    def generate_shot(self):
        row=self.selected()
        if row:self._batch([r for r in self.records() if r[2].id==row[2].id],'生成本镜头对白')

    def generate_chapter(self):self._batch(self.records(),'补齐本章对白')

    def start_worker(self):
        if self.worker and self.worker.isRunning():return
        self.message.setText('正在生成声音…'); self.worker=RuntimeWorker(self.sound.runtime,self.host); self.worker.completed.connect(self.worker_done); self.worker.failed.connect(lambda text:self.message.setText(text)); self.worker.start()

    def worker_done(self):self.message.setText('声音已进入候选版本');self.refresh_items()

    def import_audio(self):
        row=self.selected()
        if not row:return
        filters=' '.join('*'+x for x in sorted(EXTENSIONS['audio'])); path,_=QFileDialog.getOpenFileName(self,'导入音频','',f'音频 ({filters})')
        if not path:return
        result=self.guard(lambda:self.sound.import_dialogue(row[1],path) if row[0]=='dialogue' else self.sound.import_background(row[1],path))
        if result:self.refresh_items(row[0]+':'+row[1])

    def review(self,state):
        cid=self.selected_candidate()
        if cid and self.guard(lambda:self.production.review(cid,state)):self.selection_changed()

    def bind(self):
        cid=self.selected_candidate()
        if not cid:return
        candidate=self.production.candidate(cid); result=self.guard(lambda:self.sound.bind_dialogue(cid) if candidate.dialogue_id else self.sound.bind_background(cid))
        if result:self.refresh_items(('dialogue:' if candidate.dialogue_id else 'background:')+(candidate.dialogue_id or candidate.background_id))

    def play(self):
        cid=self.selected_candidate()
        if not cid:return
        path=self.production.preview_path(cid)
        if path:self.player.setSource(QUrl.fromLocalFile(str(path)));self.player.play()

    def open_voice(self):
        row=self.selected()
        if not row or row[0]!='dialogue' or not row[3].voice_requirement_id:return
        from .production_gui import ProductionDialog
        ProductionDialog(self.host,row[3].voice_requirement_id,row[2].id).exec();self.selection_changed()

    def accept(self):
        if self.worker and self.worker.isRunning():self.message.setText('声音生成完成后再返回。');return
        self.player.stop();super().accept()

    def reject(self):self.accept()
