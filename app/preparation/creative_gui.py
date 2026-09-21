"""Qt Creative Workspace for conversation, proposal preview and explicit apply."""
from __future__ import annotations
import html
from pathlib import Path
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (QComboBox, QDialog, QFileDialog, QFrame, QHBoxLayout, QLabel,
    QMessageBox, QPlainTextEdit, QPushButton, QSplitter, QTextBrowser, QVBoxLayout, QWidget)
from .creative import CreativeService, Scope
from app.shell_theme import D_STYLE, EMBEDDED_D_STYLE

TASKS = [
    ("\u9879\u76ee\u8ba8\u8bba", "project_discussion"),
    ("\u4fee\u6539\u5f53\u524d\u955c\u5934", "edit_shot"),
    ("\u4fee\u6539\u5f53\u524d\u5bf9\u767d", "edit_dialogue"),
    ("\u4fee\u6539\u5f53\u524d\u7ae0\u8282", "edit_chapter"),
    ("\u8fde\u7eed\u6027\u68c0\u67e5", "continuity_review"),
    ("\u4ece\u4e00\u53e5\u60f3\u6cd5\u5f00\u59cb", "idea_to_script"),
    ("\u6574\u7406\u5916\u90e8\u5267\u672c", "normalize_external_script"),
]

def label(text="", role="creativeMuted", wrap=False):
    item = QLabel(text); item.setObjectName(role); item.setWordWrap(wrap); return item

def button(text, callback, role="quiet"):
    item = QPushButton(text); item.setObjectName(role)
    item.setCursor(Qt.CursorShape.PointingHandCursor); item.clicked.connect(callback)
    return item

class CreativeWorker(QThread):
    completed = Signal(object, object)
    def __init__(self, service, run, request, repair=True):
        super().__init__(); self.service=service; self.run_record=run
        self.request=request; self.repair=repair
    def run(self):
        self.completed.emit(*self.service.complete(self.run_record.id, self.request,
                                                    repair=self.repair))

class CreativeDialog(QDialog):
    def __init__(self, host, integrated=False):
        super().__init__(host)
        self.host=host; self.workspace=host.workspace; self.integrated=integrated
        self.service=CreativeService(self.workspace)
        self.scope=self.current_scope()
        self.conversation=self.service.active_conversation(self.scope)
        self.worker=None; self.current_run_id=None; self.external_text=None
        self.setWindowTitle("\u6620\u5e8f \u00b7 AI \u521b\u4f5c")
        self.resize(min(1320,max(1000,host.width()-55)), min(880,max(680,host.height()-35)))
        self.setMinimumSize(960,650)
        self.setStyleSheet(host.styleSheet()+"""
            QDialog { background:#0c1725; color:#dce8f1; }
            QLabel#creativeTitle { color:#eef4f8; font-size:23px; font-weight:500; }
            QLabel#creativeMuted { color:#8ea5b8; font-size:11px; }
            QFrame#creativeSurface { background:#142334; border-radius:4px; }
            QTextBrowser#creativeConversation { background:#0f1c2a; border:0; padding:12px; }
            QPlainTextEdit#creativeInput { background:#101e2d; border:1px solid #30475a; padding:9px; }
            QPlainTextEdit#creativeDiff { background:#101c29; border:0; color:#cfe0ea; font-family:Consolas; }
            QPlainTextEdit#creativeDraft { background:#132232; border:0; color:#dce8f1; }
            QComboBox { background:#142638; border:1px solid #31495d; padding:5px; }
        """)
        if self.integrated:self.setStyleSheet(D_STYLE+EMBEDDED_D_STYLE)
        self.build(); self.refresh()

    def current_scope(self):
        script=self.workspace.script
        if not script:
            return Scope()
        chapter=self.host.current_chapter()
        shot=next((s for s in chapter.shots if s.id==self.host.shot_id),None) if chapter else None
        if shot:
            return Scope(level="shot",chapter_id=chapter.id,shot_id=shot.id,
                         dialogue_id=shot.dialogues[0].id if shot.dialogues else None)
        if chapter:
            return Scope(level="chapter",chapter_id=chapter.id)
        return Scope()

    def build(self):
        root=QVBoxLayout(self); root.setContentsMargins(24,18,24,16); root.setSpacing(11)
        top=QHBoxLayout(); titles=QVBoxLayout()
        titles.addWidget(label(self.scope_text(),"creativeMuted"))
        titles.addWidget(label("AI \u521b\u4f5c","creativeTitle"))
        top.addLayout(titles,1)
        self.model=QComboBox()
        for model in self.service.runtime.registry.models.values():
            self.model.addItem(model.display_name,model.id)
        top.addWidget(label("\u6a21\u578b","creativeMuted")); top.addWidget(self.model)
        top.addWidget(button("\u6a21\u578b\u8bbe\u7f6e",self.model_settings,"quiet"))
        top.addWidget(button("\u8fd4\u56de\u6765\u6e90  \u2197",self.go_back,"quiet"))
        root.addLayout(top)

        split=QSplitter(Qt.Orientation.Horizontal)
        conversation=QFrame(); conversation.setObjectName("creativeSurface")
        left=QVBoxLayout(conversation); left.setContentsMargins(14,13,14,13); left.setSpacing(9)
        left.addWidget(label("\u5bf9\u8bdd","creativeMuted"))
        self.chat=QTextBrowser(); self.chat.setObjectName("creativeConversation")
        left.addWidget(self.chat,1)
        taskrow=QHBoxLayout(); self.task=QComboBox()
        for title,value in TASKS:self.task.addItem(title,value)
        if not self.workspace.script:self.task.setCurrentIndex(self.task.findData("idea_to_script"))
        taskrow.addWidget(self.task,1)
        taskrow.addWidget(button("\u5bfc\u5165\u5916\u90e8\u6587\u672c",self.import_external,"quiet"))
        left.addLayout(taskrow)
        self.input=QPlainTextEdit(); self.input.setObjectName("creativeInput")
        self.input.setPlaceholderText("\u8bf4\u4e00\u4e2a\u60f3\u6cd5\uff0c\u6216\u8bf4\u660e\u60f3\u4fee\u6539\u4ec0\u4e48\u2026")
        self.input.setFixedHeight(92); left.addWidget(self.input)
        actions=QHBoxLayout(); self.send_button=button("\u53d1\u9001  \u2197",self.send,"primary")
        self.continue_button=button("\u7ee7\u7eed\u4fee\u6539",self.continue_editing,"tool")
        self.cancel_button=button("\u53d6\u6d88",self.cancel,"quiet")
        actions.addWidget(self.send_button); actions.addWidget(self.continue_button)
        actions.addWidget(self.cancel_button); actions.addStretch()
        left.addLayout(actions); split.addWidget(conversation)

        proposal=QFrame(); proposal.setObjectName("creativeSurface")
        right=QVBoxLayout(proposal); right.setContentsMargins(15,13,15,13); right.setSpacing(8)
        head=QHBoxLayout(); head.addWidget(label("\u5f53\u524d\u4fee\u6539","creativeMuted"))
        head.addStretch(); self.proposal_state=label("","creativeMuted"); head.addWidget(self.proposal_state)
        right.addLayout(head)
        self.summary=label("\u8fd8\u6ca1\u6709\u4fee\u6539\u5efa\u8bae","creativeTitle",True); right.addWidget(self.summary)
        self.diff=QPlainTextEdit(); self.diff.setObjectName("creativeDiff"); self.diff.setReadOnly(True)
        self.diff.setPlaceholderText("\u751f\u6210\u4fee\u6539\u540e\uff0c\u8fd9\u91cc\u663e\u793a\u771f\u5b9e\u53d8\u5316\u3002")
        right.addWidget(self.diff,2)
        right.addWidget(label("\u5b8c\u6574\u8349\u7a3f \u00b7 \u53ef\u624b\u5de5\u8c03\u6574","creativeMuted"))
        self.draft=QPlainTextEdit(); self.draft.setObjectName("creativeDraft"); right.addWidget(self.draft,2)
        proposal_actions=QHBoxLayout()
        proposal_actions.addWidget(button("\u66f4\u65b0\u9884\u89c8",self.update_preview,"quiet"))
        proposal_actions.addStretch()
        self.discard_button=button("\u653e\u5f03",self.discard,"quiet")
        self.apply_button=button("\u5e94\u7528  \u2197",self.apply,"primary")
        proposal_actions.addWidget(self.discard_button); proposal_actions.addWidget(self.apply_button)
        right.addLayout(proposal_actions)
        self.diagnostics=label("","creativeMuted",True); right.addWidget(self.diagnostics)
        split.addWidget(proposal); split.setSizes([520,690]); root.addWidget(split,1)
        has_live_model=any(not model.fixture for model in self.service.runtime.registry.models.values())
        status_text=("模型已配置" if has_live_model else
                     "尚未配置真实模型 · FIXTURE / DEMO / ZERO-CALL")
        foot=QHBoxLayout(); self.status=label(status_text,"creativeMuted")
        foot.addWidget(self.status,1); root.addLayout(foot)

    def scope_text(self):
        script=self.workspace.script
        if not script:return "\u65b0\u9879\u76ee \u00b7 \u4ece\u60f3\u6cd5\u5f00\u59cb"
        chapter=self.host.current_chapter()
        shot=next((s for s in chapter.shots if s.id==self.scope.shot_id),None) if chapter else None
        text=script.title
        if chapter:text+=f"  \u00b7  \u7b2c {chapter.number} \u7ae0"
        if shot:text+=f"  \u00b7  \u955c\u5934 {shot.number}"
        return text

    def model_settings(self):
        QMessageBox.information(self,"\u6a21\u578b\u8bbe\u7f6e",
            "\u771f\u5b9e\u6587\u672c\u6a21\u578b\u901a\u8fc7\u672c\u673a\u73af\u5883\u53d8\u91cf\u914d\u7f6e\uff1a\n"
            "OPENAI_COMPATIBLE_BASE_URL\nOPENAI_COMPATIBLE_MODEL\nOPENAI_COMPATIBLE_API_KEY\n\n"
            "\u5f53\u524d Fixture \u4ec5\u7528\u4e8e DEMO / ZERO-CALL \u9a8c\u8bc1\u3002")

    def import_external(self):
        path,_=QFileDialog.getOpenFileName(self,"\u5bfc\u5165\u5916\u90e8\u5267\u672c","","\u6587\u672c (*.txt *.md)")
        if not path:return
        try:self.external_text=Path(path).read_text(encoding="utf-8-sig")
        except Exception as exc:self.status.setText(str(exc));return
        self.task.setCurrentIndex(self.task.findData("normalize_external_script"))
        self.input.setPlainText("\u8bf7\u628a\u8fd9\u4efd\u5916\u90e8\u5267\u672c\u6574\u7406\u6210\u5236\u4f5c\u5267\u672c\u3002")
        self.status.setText(Path(path).name)

    def selected_scope(self, task):
        scope=self.current_scope()
        if task=="idea_to_script" or task=="normalize_external_script":return Scope()
        if task=="edit_chapter":return Scope(level="chapter",chapter_id=scope.chapter_id)
        if task=="edit_dialogue":return Scope(level="dialogue",chapter_id=scope.chapter_id,
            shot_id=scope.shot_id,dialogue_id=scope.dialogue_id)
        return scope

    def send(self):
        if self.worker and self.worker.isRunning():return
        text=self.input.toPlainText().strip()
        if not text:return
        task=self.task.currentData(); scope=self.selected_scope(task)
        try:run,request=self.service.begin(self.conversation["id"],task,text,scope,
            model_id=self.model.currentData(),external_text=self.external_text)
        except Exception as exc:self.status.setText(str(exc));return
        self.external_text=None; self.input.clear(); self.start_worker(run,request)

    def continue_editing(self):
        if self.worker and self.worker.isRunning():return
        text=self.input.toPlainText().strip()
        if not text:return
        proposal=self.service.active_proposal(self.conversation["id"])
        if not proposal:return
        try:run,request=self.service.begin(self.conversation["id"],proposal.task,text,proposal.scope,
            model_id=self.model.currentData(),continue_proposal=True)
        except Exception as exc:self.status.setText(str(exc));return
        self.input.clear(); self.start_worker(run,request)

    def start_worker(self,run,request):
        self.current_run_id=run.id; self.status.setText("\u6b63\u5728\u51c6\u5907\u4fee\u6539\u2026")
        self.send_button.setEnabled(False); self.continue_button.setEnabled(False)
        self.worker=CreativeWorker(self.service,run,request); self.worker.completed.connect(self.worker_done)
        self.worker.start()

    def cancel(self):
        if self.current_run_id:
            try:self.service.runtime.cancel(self.current_run_id); self.status.setText("\u5df2\u53d6\u6d88")
            except Exception as exc:self.status.setText(str(exc))

    def worker_done(self,run,output):
        self.current_run_id=None; self.send_button.setEnabled(True)
        selected=self.service.runtime.registry.model(run.model_id)
        complete_text=("FIXTURE / DEMO / ZERO-CALL · 已完成" if selected.fixture else
                       f"{selected.display_name} · 已完成")
        self.status.setText(self.service.error_message(run) if run.status!="succeeded" else complete_text)
        self.refresh()

    def refresh(self):
        self.conversation=self.service.conversation(self.conversation["id"])
        blocks=[]
        for message in self.conversation["messages"]:
            who=("你" if message["role"]=="user" else
                 "AI" if message["role"]=="assistant" else "系统")
            color="#8fa9bc" if message["role"]=="user" else "#e1ebf2"
            blocks.append(f'<p style="color:{color};"><b>{who}</b><br>{html.escape(message["text"]).replace(chr(10),"<br>")}</p>')
        self.chat.setHtml("".join(blocks) or '<span style="color:#7891a5;">\u4ece\u4e00\u4e2a\u95ee\u9898\u3001\u4e00\u53e5\u60f3\u6cd5\uff0c\u6216\u5f53\u524d\u955c\u5934\u5f00\u59cb\u3002</span>')
        self.chat.verticalScrollBar().setValue(self.chat.verticalScrollBar().maximum())
        proposal=self.service.active_proposal(self.conversation["id"])
        if proposal:
            proposal=self.service.refresh_proposal(proposal.id)
            diff,counts=self.service.proposal_diff(proposal.id)
            self.summary.setText(proposal.summary or "\u4fee\u6539\u5efa\u8bae")
            self.proposal_state.setText(
                "\u9879\u76ee\u5185\u5bb9\u5df2\u53d8\u5316" if proposal.status=="stale" else
                "\u8fd9\u7248\u8fd8\u4e0d\u80fd\u5e94\u7528" if proposal.validation_state=="invalid" else
                f'{counts["added"]+counts["removed"]} \u5904\u53d8\u5316')
            self.diff.setPlainText(diff or "\u65b0\u5efa Production Script Draft")
            if not self.draft.hasFocus():self.draft.setPlainText(proposal.draft)
            messages=[f'\u7b2c {x["line"]} \u884c \u00b7 {x["message"]}' for x in proposal.diagnostics[:3]]
            self.diagnostics.setText("  /  ".join(messages))
            self.apply_button.setEnabled(proposal.status=="open" and proposal.validation_state=="valid")
            self.discard_button.setEnabled(proposal.status in ("open","stale"))
            self.continue_button.setEnabled(proposal.status=="open" and not (self.worker and self.worker.isRunning()))
        else:
            self.summary.setText("\u8fd8\u6ca1\u6709\u4fee\u6539\u5efa\u8bae"); self.proposal_state.setText("")
            self.diff.clear(); self.draft.clear(); self.diagnostics.clear()
            self.apply_button.setEnabled(False); self.discard_button.setEnabled(False)
            self.continue_button.setEnabled(False)

    def update_preview(self):
        proposal=self.service.active_proposal(self.conversation["id"])
        if not proposal:return
        try:self.service.update_draft(proposal.id,self.draft.toPlainText());self.refresh()
        except Exception as exc:self.status.setText(str(exc))

    def apply(self):
        proposal=self.service.active_proposal(self.conversation["id"])
        if not proposal:return
        try:
            self.service.update_draft(proposal.id,self.draft.toPlainText())
            self.service.apply(proposal.id)
            self.host.loading=True; self.host.editor.setPlainText(self.workspace.state["draft"]); self.host.loading=False
            self.host.refresh(); self.status.setText("\u5df2\u5e94\u7528\u5230\u5236\u4f5c\u5267\u672c"); self.refresh()
        except Exception as exc:self.status.setText(
            "\u9879\u76ee\u5185\u5bb9\u5df2\u53d8\u5316" if "changed" in str(exc).lower() else
            "\u8fd9\u7248\u8fd8\u4e0d\u80fd\u5e94\u7528")

    def discard(self):
        proposal=self.service.active_proposal(self.conversation["id"])
        if proposal:
            try:self.service.discard(proposal.id);self.status.setText("\u5df2\u653e\u5f03\u8fd9\u7248\u4fee\u6539");self.refresh()
            except Exception as exc:self.status.setText(str(exc))

    def go_back(self):
        if self.integrated and getattr(self.host,"shell",None):
            self.host.shell.return_route()
        else:self.accept()

    def accept(self):
        if self.worker and self.worker.isRunning():self.status.setText("\u8bf7\u5148\u7b49\u5f85\u5b8c\u6210\u6216\u53d6\u6d88");return
        super().accept()
    def reject(self):self.accept()