"""Integrated D Layout application shell over the existing V0.2 production truth."""
from __future__ import annotations

from pathlib import Path
import shutil

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFileDialog, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QMainWindow, QMenu, QMessageBox, QPlainTextEdit, QPushButton,
    QScrollArea, QStackedWidget, QTextBrowser, QVBoxLayout, QWidget,
)

from .integration import ActivityAdapter, AppSettingsStore, WorkspaceRouter
from .shell_theme import D_STYLE


def label(value="", name="muted", wrap=False):
    item = QLabel(value)
    item.setObjectName(name)
    item.setWordWrap(wrap)
    return item


def button(value, callback, name="quiet"):
    item = QPushButton(value)
    item.setObjectName(name)
    item.setCursor(Qt.CursorShape.PointingHandCursor)
    item.clicked.connect(callback)
    return item


def clear(layout):
    while layout.count():
        item = layout.takeAt(0)
        if item.widget():
            item.widget().deleteLater()


class ScriptEditDialog(QDialog):
    def __init__(self, shell):
        super().__init__(shell)
        self.shell = shell
        self.setWindowTitle("Production Script")
        self.resize(820, 680)
        self.setStyleSheet(D_STYLE)
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 18)
        root.addWidget(label("Production Script", "pageTitle"))
        root.addWidget(label("修改会先保存为草稿；只有“应用剧本”才更新正式生产源。", "muted"))
        self.editor = QPlainTextEdit()
        self.editor.setPlainText(shell.workspace.state.get("draft", ""))
        root.addWidget(self.editor, 1)
        self.message = label("", "muted", True)
        root.addWidget(self.message)
        actions = QHBoxLayout()
        actions.addWidget(button("取消", self.reject))
        actions.addStretch()
        actions.addWidget(button("保存草稿", self.save))
        actions.addWidget(button("应用剧本", self.apply, "primary"))
        root.addLayout(actions)

    def save(self):
        try:
            self.shell.workspace.save_draft(self.editor.toPlainText())
            self.message.setText("草稿已保存，正式 Production Script 未改变。")
        except Exception as exc:
            self.message.setText(str(exc))

    def apply(self):
        try:
            parsed = self.shell.workspace.apply(self.editor.toPlainText())
            if not parsed.valid:
                self.message.setText(" / ".join(f"第 {d.line} 行 · {d.message}" for d in parsed.diagnostics[:3]))
                return
            self.shell.prep.loading = True
            self.shell.prep.editor.setPlainText(self.shell.workspace.state["draft"])
            self.shell.prep.loading = False
            self.shell.refresh_all()
            self.accept()
        except Exception as exc:
            self.message.setText(str(exc))


class PreparationItem(QFrame):
    def __init__(self, row, selected, choose, open_production):
        super().__init__()
        self.setObjectName("dSurface")
        requirement = row["requirement"]
        status = row["status"]
        root = QHBoxLayout(self)
        root.setContentsMargins(12, 9, 12, 9)
        root.setSpacing(12)
        glyph = {"image": "▧", "audio": "≋", "video": "▷"}.get(requirement["media"], "·")
        media = label(glyph, "sectionTitle")
        media.setFixedSize(28, 28)
        media.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(media)
        text = QVBoxLayout()
        text.setSpacing(2)
        text.addWidget(label(requirement["name"], "sectionTitle"))
        text.addWidget(label(self.detail(row), "muted"))
        root.addLayout(text, 1)
        state = label(self.state_text(status), "muted")
        state.setMinimumWidth(72)
        root.addWidget(state)
        root.addWidget(button("进入制作  →" if status != "resolved" else "查看  →",
                              lambda: open_production(requirement["id"])))
        self.setProperty("selected", selected)
        self.mousePressEvent = lambda event: choose(requirement["id"])

    @staticmethod
    def state_text(status):
        return {
            "missing": "缺少参照", "unresolved": "需要确认", "changed": "来源已变化",
            "resolved": "已有参照", "free": "不固定素材",
        }.get(status, status)

    @staticmethod
    def detail(row):
        requirement = row["requirement"]
        use_count = row.get("use_count", len(requirement.get("shot_ids", [])))
        kind = {
            "character": "人物", "environment": "环境", "prop": "关键物件",
            "voice": "Voice", "video_reference": "视频参照",
        }.get(requirement["kind"], requirement["kind"])
        return f"{kind} · 用于 {use_count} 个 Shot"


class DPreparationPage(QWidget):
    def __init__(self, shell):
        super().__init__()
        self.shell = shell
        self.workspace = shell.workspace
        self.selected_id = None
        self.setObjectName("dPage")
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(30, 22, 30, 22)
        root.setSpacing(14)
        header = QHBoxLayout()
        titles = QVBoxLayout()
        titles.addWidget(label("生产准备", "pageTitle"))
        titles.addWidget(label("先准备一次，让多个 Shot 直接使用", "muted"))
        header.addLayout(titles, 1)
        self.search = QLineEdit()
        self.search.setPlaceholderText("搜索名称或类型")
        self.search.setFixedWidth(210)
        self.search.textChanged.connect(self.refresh)
        header.addWidget(self.search)
        self.filter = QComboBox()
        self.filter.addItem("待处理", "todo")
        self.filter.addItem("全部", "all")
        self.filter.currentIndexChanged.connect(self.refresh)
        header.addWidget(self.filter)
        header.addWidget(button("同步素材", self.sync))
        header.addWidget(button("编辑 Production Script", self.edit_script))
        root.addLayout(header)

        body = QHBoxLayout()
        body.setSpacing(22)
        left = QVBoxLayout()
        self.context = label("", "muted")
        left.addWidget(self.context)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.container = QWidget()
        self.items = QVBoxLayout(self.container)
        self.items.setContentsMargins(0, 0, 0, 0)
        self.items.setSpacing(4)
        self.scroll.setWidget(self.container)
        left.addWidget(self.scroll, 1)
        self.selection_bar = QFrame()
        self.selection_bar.setObjectName("dSurface")
        selection = QHBoxLayout(self.selection_bar)
        self.selection_label = label("选择一个准备项", "muted")
        selection.addWidget(self.selection_label, 1)
        self.free_button = button("不需要固定素材", self.toggle_free)
        self.import_button = button("导入素材", self.import_asset)
        self.production_button = button("进入制作", self.open_selected, "primary")
        selection.addWidget(self.free_button)
        selection.addWidget(self.import_button)
        selection.addWidget(self.production_button)
        left.addWidget(self.selection_bar)
        body.addLayout(left, 3)

        script = QFrame()
        script.setObjectName("dSurface")
        right = QVBoxLayout(script)
        right.setContentsMargins(18, 16, 18, 16)
        script_head = QHBoxLayout()
        script_head.addWidget(label("Production Script", "sectionTitle"))
        script_head.addStretch()
        script_head.addWidget(button("编辑", self.edit_script))
        right.addLayout(script_head)
        self.script_context = label("", "muted")
        right.addWidget(self.script_context)
        self.script = QTextBrowser()
        right.addWidget(self.script, 1)
        right.addWidget(button("用 AI 协作修改  →",
                               lambda: self.shell.navigate("creative", deep_link=True)),
                        0, Qt.AlignmentFlag.AlignRight)
        body.addWidget(script, 2)
        root.addLayout(body, 1)

    def set_route(self, route):
        memory = self.shell.router.memory("preparation")
        self.selected_id = route.object_id if route.object_type == "requirement" else (
            memory.get("selected_requirement") or self.selected_id)
        if not self.search.hasFocus():
            self.search.blockSignals(True)
            self.search.setText(memory.get("search", self.search.text()))
            self.search.blockSignals(False)
        wanted = memory.get("filter")
        index = self.filter.findData(wanted)
        if index >= 0:
            self.filter.blockSignals(True)
            self.filter.setCurrentIndex(index)
            self.filter.blockSignals(False)
        self.refresh()
        QTimer.singleShot(0, lambda: self.scroll.verticalScrollBar().setValue(
            int(memory.get("scroll_y", 0))))

    def capture(self):
        self.shell.router.remember(
            "preparation", selected_requirement=self.selected_id,
            search=self.search.text(), filter=self.filter.currentData(),
            scroll_y=self.scroll.verticalScrollBar().value())

    def scoped_reports(self):
        chapter = self.shell.current_chapter()
        if not chapter:
            return []
        ids = {rid for shot in chapter.shots for rid in shot.requirement_ids}
        rows = [
            {**row, "use_count": sum(
                row["requirement"]["id"] in shot.requirement_ids
                for shot in chapter.shots
            )}
            for row in self.workspace.report()
            if row["requirement"]["id"] in ids
        ]
        query = self.search.text().strip().casefold()
        if query:
            rows = [row for row in rows if query in (
                row["requirement"]["name"] + " " + row["requirement"]["kind"]).casefold()]
        if self.filter.currentData() == "todo":
            rows = [row for row in rows if row["status"] in ("missing", "unresolved", "changed")]
        order = {"missing": 0, "unresolved": 1, "changed": 2, "free": 3, "resolved": 4}
        return sorted(rows, key=lambda row: (order.get(row["status"], 9),
                                             row["requirement"]["name"]))

    def refresh(self):
        clear(self.items)
        rows = self.scoped_reports()
        chapter = self.shell.current_chapter()
        todo = sum(row["status"] in ("missing", "unresolved", "changed") for row in rows)
        self.context.setText(
            f"Chapter {chapter.number} · {chapter.title} · {todo} 项需要处理"
            if chapter else "导入或创建 Production Script 后开始准备")
        valid_ids = {row["requirement"]["id"] for row in rows}
        if self.selected_id not in valid_ids:
            self.selected_id = next(iter(valid_ids), None)
        for row in rows:
            self.items.addWidget(PreparationItem(
                row, row["requirement"]["id"] == self.selected_id,
                self.choose, self.shell.open_requirement))
        if not rows:
            empty = label("当前范围没有需要处理的准备项。\n可切换到“全部”查看已有参照。",
                          "muted", True)
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.items.addWidget(empty, 1)
        self.items.addStretch()
        self.refresh_script()
        selected = next((row for row in self.workspace.report()
                         if row["requirement"]["id"] == self.selected_id), None)
        self.selection_label.setText(
            selected["requirement"]["name"] if selected else "选择一个准备项")
        self.free_button.setEnabled(bool(selected))
        self.import_button.setEnabled(bool(selected) and selected["status"] != "free")
        self.production_button.setEnabled(bool(selected))
        self.free_button.setText(
            "恢复固定素材" if selected and selected["status"] == "free" else "不需要固定素材")

    def refresh_script(self):
        chapter = self.shell.current_chapter()
        shot = self.shell.current_shot()
        if not chapter:
            self.script_context.setText("尚无章节")
            self.script.setPlainText("从一句想法、外部文本或手写剧本开始。")
            return
        if not shot and chapter.shots:
            shot = chapter.shots[0]
        self.script_context.setText(
            f"Chapter {chapter.number} · Shot {shot.number}" if shot else f"Chapter {chapter.number}")
        self.script.setPlainText(shot.text if shot else "\n\n".join(s.text for s in chapter.shots))

    def choose(self, requirement_id):
        self.selected_id = requirement_id
        self.refresh()

    def open_selected(self):
        if self.selected_id:
            self.shell.open_requirement(self.selected_id)

    def toggle_free(self):
        if not self.selected_id:
            return
        row = next(row for row in self.workspace.report()
                   if row["requirement"]["id"] == self.selected_id)
        self.workspace.set_reference_required(self.selected_id, row["status"] == "free")
        self.shell.refresh_all()

    def import_asset(self):
        if not self.selected_id:
            return
        filename, _ = QFileDialog.getOpenFileName(self, "导入素材")
        if not filename:
            return
        try:
            self.workspace.import_asset(self.selected_id, filename)
            self.shell.refresh_all()
        except Exception as exc:
            QMessageBox.warning(self, "导入未完成", str(exc))

    def sync(self):
        try:
            self.workspace.scan()
            self.shell.refresh_all()
        except Exception as exc:
            QMessageBox.warning(self, "同步未完成", str(exc))

    def edit_script(self):
        ScriptEditDialog(self.shell).exec()


class SettingsPage(QWidget):
    def __init__(self, shell):
        super().__init__()
        self.shell = shell
        self.store = shell.settings
        self.setObjectName("dPage")
        root = QVBoxLayout(self)
        root.setContentsMargins(36, 26, 36, 26)
        root.setSpacing(16)
        head = QHBoxLayout()
        titles = QVBoxLayout()
        titles.addWidget(label("设置", "pageTitle"))
        titles.addWidget(label("应用级默认与本机能力，不会改变当前项目 Truth。", "muted"))
        head.addLayout(titles, 1)
        head.addWidget(button("返回工作区", shell.return_route))
        root.addLayout(head)
        body = QHBoxLayout()
        body.setSpacing(22)
        self.categories = QComboBox()
        for title, key in (("通用", "general"), ("AI 服务", "ai"),
                           ("文件与输出", "files"), ("系统信息", "system")):
            self.categories.addItem(title, key)
        self.categories.setFixedWidth(160)
        self.categories.currentIndexChanged.connect(self.select_category)
        body.addWidget(self.categories, 0, Qt.AlignmentFlag.AlignTop)
        self.stack = QStackedWidget()
        body.addWidget(self.stack, 1)
        root.addLayout(body, 1)
        self._general(); self._ai(); self._files(); self._system()
        self.select_category()

    def surface(self, title, description):
        page = QFrame()
        page.setObjectName("dSurface")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(12)
        layout.addWidget(label(title, "pageTitle"))
        layout.addWidget(label(description, "muted", True))
        return page, layout

    def row(self, layout, title, control, detail=""):
        line = QHBoxLayout()
        text = QVBoxLayout()
        text.addWidget(label(title, "sectionTitle"))
        if detail:
            text.addWidget(label(detail, "muted", True))
        line.addLayout(text, 1)
        line.addWidget(control)
        layout.addLayout(line)
        divider = QFrame(); divider.setObjectName("dDivider")
        layout.addWidget(divider)

    def _general(self):
        page, layout = self.surface("通用", "界面选择保存到本机；D 是默认体验，C 是沉浸式备选。")
        self.layout_choice = QComboBox()
        self.layout_choice.addItem("D · 默认工作台", "D")
        self.layout_choice.addItem("C · 镜头上下文", "C")
        self.layout_choice.setCurrentIndex(self.layout_choice.findData(self.store.values["layout"]))
        self.layout_choice.currentIndexChanged.connect(self.save_general)
        self.row(layout, "界面布局", self.layout_choice, "切换布局在重新启动后生效。")
        self.motion = QCheckBox("减少动态")
        self.motion.setChecked(bool(self.store.values["reduced_motion"]))
        self.motion.toggled.connect(self.save_general)
        self.row(layout, "动态效果", self.motion)
        self.resume = QCheckBox("恢复上次项目")
        self.resume.setChecked(bool(self.store.values["resume_last_project"]))
        self.resume.toggled.connect(self.save_general)
        self.row(layout, "启动", self.resume)
        self.general_message = label("", "muted")
        layout.addWidget(self.general_message)
        layout.addStretch()
        self.stack.addWidget(page)

    def _ai(self):
        page, layout = self.surface("AI 服务", "只展示当前真实存在的 OpenAI-compatible Text 适配层。")
        self.base_url = QLineEdit(self.store.values.get("text_base_url", ""))
        self.model = QLineEdit(self.store.values.get("text_model", ""))
        self.row(layout, "Base URL", self.base_url)
        self.row(layout, "Model ID", self.model)
        provider = self.store.provider_config()
        self.credential = label(
            "API Key 已由环境配置" if provider["credential_configured"]
            else "API Key 未配置 · 使用 OPENAI_COMPATIBLE_API_KEY", "muted")
        layout.addWidget(self.credential)
        layout.addWidget(button("保存本机配置", self.save_ai, "primary"),
                         0, Qt.AlignmentFlag.AlignLeft)
        self.ai_message = label("", "muted")
        layout.addWidget(self.ai_message)
        layout.addStretch()
        self.stack.addWidget(page)

    def _files(self):
        page, layout = self.surface("文件与输出", "项目保持为可迁移目录；默认位置只影响未来新项目。")
        self.project_path = QLineEdit(self.store.values.get("default_project_path", ""))
        choose = button("选择目录", self.choose_path)
        row = QHBoxLayout(); row.addWidget(self.project_path, 1); row.addWidget(choose)
        holder = QWidget(); holder.setLayout(row)
        self.row(layout, "默认项目位置", holder)
        self.row(layout, "章节输出", label("1280×720 · 24fps · H.264 / AAC", "sectionTitle"),
                 "写入当前项目 finishing 目录。")
        self.file_message = label("", "muted")
        layout.addWidget(self.file_message)
        layout.addStretch()
        self.stack.addWidget(page)

    def _system(self):
        page, layout = self.surface("系统信息", "只读显示本机实际能力。")
        self.row(layout, "FFmpeg", label(shutil.which("ffmpeg") or "未找到", "muted"))
        self.row(layout, "FFprobe", label(shutil.which("ffprobe") or "未找到", "muted"))
        try:
            import opentimelineio  # noqa: F401
            otio = "可用"
        except Exception:
            otio = "未安装"
        self.row(layout, "OpenTimelineIO", label(otio, "muted"))
        self.row(layout, "当前项目", label(str(self.shell.workspace.root), "muted", True))
        layout.addWidget(button("打开项目文件夹",
                                lambda: QDesktopServices.openUrl(
                                    QUrl.fromLocalFile(str(self.shell.workspace.root)))))
        layout.addStretch()
        self.stack.addWidget(page)

    def select_category(self):
        self.stack.setCurrentIndex(max(0, self.categories.currentIndex()))

    def save_general(self, *_):
        try:
            self.store.save(layout=self.layout_choice.currentData(),
                            reduced_motion=self.motion.isChecked(),
                            resume_last_project=self.resume.isChecked())
            self.general_message.setText(
                "已保存 · 布局将在重新启动后生效"
                if self.layout_choice.currentData() != "D" else "已保存")
        except Exception as exc:
            self.general_message.setText(str(exc))

    def save_ai(self):
        try:
            self.store.save(text_base_url=self.base_url.text().strip(),
                            text_model=self.model.text().strip())
            self.ai_message.setText("已填写 · 未验证；未进行商业调用。")
        except Exception as exc:
            self.ai_message.setText(str(exc))

    def choose_path(self):
        path = QFileDialog.getExistingDirectory(self, "默认项目位置")
        if not path:
            return
        try:
            self.store.save(default_project_path=path)
            self.project_path.setText(path)
            self.file_message.setText("已保存，仅用于未来新项目。")
        except Exception as exc:
            self.file_message.setText(str(exc))


class EmptyWorkspace(QWidget):
    def __init__(self, title, detail):
        super().__init__()
        self.setObjectName("dPage")
        root = QVBoxLayout(self)
        root.addStretch()
        heading = label(title, "pageTitle"); heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(heading)
        note = label(detail, "muted", True); note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(note)
        root.addStretch()


class ApplicationShell(QMainWindow):
    """56px frozen D Shell. Existing business services remain the only truth owners."""

    def __init__(self, data_root, session_path=None, settings_path=None):
        super().__init__()
        from .preparation_gui import PreparationWindow
        self.layout_variant = "D"
        self.session_path = Path(session_path) if session_path else None
        self.settings = AppSettingsStore(settings_path)
        self.prep = PreparationWindow(data_root, session_path)
        self.prep.shell = self
        self.prep.layout_variant = "D"
        self.workspace = self.prep.workspace
        self.router = WorkspaceRouter(self.workspace)
        self.activity = ActivityAdapter(self.workspace)
        self.pages = {}
        self.current_workspace_widget = None
        self.setWindowTitle("AI 视频个人生产工作流")
        self.resize(1440, 900)
        self.setMinimumSize(1100, 680)
        self.setStyleSheet(D_STYLE)
        self._build()
        self.show_route(self.router.current)
        self.activity_timer = QTimer(self)
        self.activity_timer.timeout.connect(self.refresh_activity)
        self.activity_timer.start(1200)

    def _build(self):
        root_widget = QWidget(); root_widget.setObjectName("dRoot")
        root = QVBoxLayout(root_widget)
        root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)
        self.setCentralWidget(root_widget)
        shell = QFrame(); shell.setObjectName("shell"); shell.setFixedHeight(56)
        bar = QHBoxLayout(shell); bar.setContentsMargins(22, 0, 18, 0); bar.setSpacing(8)
        identity = QVBoxLayout(); identity.setSpacing(0)
        self.project_label = label("", "shellProject")
        self.project_context = label("", "shellContext")
        identity.addWidget(self.project_label); identity.addWidget(self.project_context)
        bar.addLayout(identity); bar.addSpacing(24)
        self.nav_buttons = {}
        for title, workspace in (("准备", "preparation"), ("制作台", "production"),
                                 ("AI 协作", "creative"), ("成片", "assembly")):
            control = button(title, lambda checked=False, w=workspace: self.navigate(w),
                             "workspaceNav")
            control.setProperty("active", False)
            self.nav_buttons[workspace] = control
            bar.addWidget(control)
        bar.addStretch()
        self.chapter_choice = QComboBox(); self.chapter_choice.setMinimumWidth(150)
        self.chapter_choice.currentIndexChanged.connect(self.chapter_changed)
        bar.addWidget(self.chapter_choice)
        self.activity_button = button("活动  0", self.open_activity)
        bar.addWidget(self.activity_button)
        self.more_button = button("•••", self.open_system_menu); self.more_button.setFixedWidth(42)
        bar.addWidget(self.more_button)
        root.addWidget(shell)
        self.return_bar = QFrame(); self.return_bar.setObjectName("returnBar")
        self.return_bar.setFixedHeight(34)
        return_layout = QHBoxLayout(self.return_bar); return_layout.setContentsMargins(22, 0, 18, 0)
        self.return_label = label("", "muted")
        return_layout.addWidget(self.return_label, 1)
        return_layout.addWidget(button("返回来源", self.return_route))
        root.addWidget(self.return_bar)
        self.stack = QStackedWidget(); root.addWidget(self.stack, 1)
        self.preparation_page = DPreparationPage(self)
        self.settings_page = SettingsPage(self)
        self.stack.addWidget(self.preparation_page); self.stack.addWidget(self.settings_page)
        self.pages["preparation"] = self.preparation_page
        self.pages["settings"] = self.settings_page

    def current_chapter(self):
        script = self.workspace.script
        if not script:
            return None
        return next((c for c in script.chapters if c.id == self.router.current.chapter_id),
                    script.chapters[0] if script.chapters else None)

    def current_shot(self):
        chapter = self.current_chapter()
        return next((s for s in chapter.shots if s.id == self.router.current.shot_id),
                    chapter.shots[0] if chapter and chapter.shots else None) if chapter else None

    @property
    def shot_id(self):
        shot = self.current_shot()
        return shot.id if shot else None

    def navigate(self, workspace, *, chapter_id=None, shot_id=None,
                 object_type=None, object_id=None, deep_link=False, reason=None):
        self.capture_current()
        route = self.router.navigate(
            workspace, chapter_id=chapter_id, shot_id=shot_id,
            object_type=object_type, object_id=object_id,
            deep_link=deep_link, reason=reason)
        self.show_route(route)

    def open_requirement(self, requirement_id):
        chapter = self.current_chapter()
        current = self.current_shot()
        if current and requirement_id in current.requirement_ids:
            shot_id = current.id
        else:
            shot_id = next((shot.id for shot in chapter.shots
                            if requirement_id in shot.requirement_ids), self.shot_id) if chapter else self.shot_id
        self.navigate("production", shot_id=shot_id, object_type="requirement",
                      object_id=requirement_id, deep_link=True, reason="准备项进入制作")

    def return_route(self):
        self.capture_current()
        self.show_route(self.router.return_to_origin())

    def capture_current(self):
        workspace = self.router.current.workspace
        widget = self.current_workspace_widget
        if workspace == "preparation":
            self.preparation_page.capture()
        elif workspace == "production" and widget and hasattr(widget, "list"):
            selected = getattr(widget, "selected_id", None)
            selected = selected() if callable(selected) else selected
            self.router.remember("production",
                selected_candidate=selected,
                rail_scroll=widget.list.horizontalScrollBar().value())
        elif workspace == "creative" and widget and hasattr(widget, "service"):
            proposal = widget.service.active_proposal(widget.conversation["id"])
            if proposal and widget.draft.toPlainText() != proposal.draft:
                try: widget.service.update_draft(proposal.id, widget.draft.toPlainText())
                except Exception: pass
            self.router.remember("creative",
                input_draft=widget.input.toPlainText(),
                conversation_scroll=widget.chat.verticalScrollBar().value(),
                proposal_scroll=widget.draft.verticalScrollBar().value(),
                model=widget.model.currentData())
        elif workspace == "assembly" and widget and hasattr(widget, "strip"):
            selected = widget.selected_segment()
            self.router.remember("assembly",
                selected_segment=selected["id"] if selected else None,
                timeline_scroll=widget.strip.horizontalScrollBar().value(),
                playhead=widget.player.position(),
                inspector_scroll=widget.inspector_scroll.verticalScrollBar().value())

    def _sync_context(self, route):
        self.prep.chapter_id = route.chapter_id
        self.prep.shot_id = route.shot_id
        if route.object_type == "requirement":
            self.prep.active_requirement_id = route.object_id
        self.prep.workspace.set_ui(chapter_id=route.chapter_id, shot_id=route.shot_id,
                                   active_requirement_id=self.prep.active_requirement_id)
        self.prep.refresh()
        script = self.workspace.script
        self.project_label.setText(script.title if script else self.workspace.root.name)
        chapter = self.current_chapter(); shot = self.current_shot()
        self.project_context.setText(
            (f"Chapter {chapter.number}" if chapter else "New Project") +
            (f" · Shot {shot.number}" if shot else ""))
        self.chapter_choice.blockSignals(True); self.chapter_choice.clear()
        if script:
            for item in script.chapters:
                self.chapter_choice.addItem(f"Chapter {item.number} · {item.title}", item.id)
            index = self.chapter_choice.findData(route.chapter_id)
            self.chapter_choice.setCurrentIndex(max(0, index))
        self.chapter_choice.setVisible(bool(script and script.chapters))
        self.chapter_choice.blockSignals(False)

    def show_route(self, route):
        previous = self.current_workspace_widget
        route = self.router.resolve(route)
        self.router.current = route; self.router._persist()
        self._sync_context(route)
        for name, control in self.nav_buttons.items():
            control.setProperty("active", name == route.workspace)
            control.style().unpolish(control); control.style().polish(control)
        self.return_bar.setVisible(bool(route.return_point))
        self.return_label.setText(
            f"来自 {route.origin} · {route.reason or '上下文跳转'}" if route.return_point else "")
        widget = self.workspace_widget(route)
        self.current_workspace_widget = widget
        self.stack.setCurrentWidget(widget)
        self._retire_page(previous, keep=widget)
        if route.workspace == "preparation":
            self.preparation_page.set_route(route)
        if self.router.notice:
            self.statusBar().showMessage(self.router.notice, 5000)
        self.refresh_activity()

    def _retire_page(self, page, *, keep=None):
        """Release inactive workspace views without interrupting live workers."""
        if not page or page is keep or page in (self.preparation_page, self.settings_page):
            return
        worker = getattr(page, "worker", None)
        if worker and worker.isRunning():
            return
        self.stack.removeWidget(page)
        for key, value in list(self.pages.items()):
            if value is page:
                self.pages.pop(key, None)
        page.deleteLater()

    def _cleanup_inactive_pages(self):
        for page in list(self.pages.values()):
            if page is not self.current_workspace_widget:
                self._retire_page(page, keep=self.current_workspace_widget)

    def workspace_widget(self, route):
        if route.workspace in ("preparation", "settings"):
            return self.pages[route.workspace]
        if route.workspace == "production": return self._production(route)
        if route.workspace == "creative": return self._creative(route)
        if route.workspace == "assembly": return self._assembly(route)
        return EmptyWorkspace("工作区不可用", "请返回准备工作区。")

    def _embed(self, widget, workspace):
        widget.setWindowFlags(Qt.WindowType.Widget)
        widget.setParent(self.stack)
        widget.setMinimumSize(0, 0)
        widget.setStyleSheet(D_STYLE + widget.styleSheet())
        self.stack.addWidget(widget)
        self.pages[f"{workspace}:{id(widget)}"] = widget
        return widget

    def _production(self, route):
        chapter = self.current_chapter(); shot = self.current_shot()
        ids = shot.requirement_ids if shot else (
            list(dict.fromkeys(rid for s in chapter.shots for rid in s.requirement_ids))
            if chapter else [])
        rid = route.object_id if route.object_type == "requirement" and route.object_id in ids else None
        if not rid:
            rid = self.router.memory("production").get("requirement_id")
        if rid not in ids:
            rows = {row["requirement"]["id"]: row for row in self.workspace.report()}
            rid = next((item for item in ids if rows.get(item, {}).get("status") == "missing"),
                       ids[0] if ids else None)
        if not rid:
            return self._embed(EmptyWorkspace(
                "当前镜头没有可生产对象", "返回 Preparation 检查 Production Script。"), "production")
        if route.object_type == "shot_current":
            from .preparation.finishing_gui import ShotCandidateDialog
            widget = ShotCandidateDialog(self.prep, route.shot_id, integrated=True)
            return self._embed(widget, "production")
        from .preparation.production_gui import ProductionDialog
        widget = ProductionDialog(self.prep, rid, shot_id=route.shot_id, integrated=True)
        memory = self.router.memory("production")
        self.router.remember("production", requirement_id=rid)
        prefer = memory.get("selected_candidate")
        if prefer: widget.refresh(prefer)
        QTimer.singleShot(0, lambda: widget.list.horizontalScrollBar().setValue(
            int(memory.get("rail_scroll", 0))))
        return self._embed(widget, "production")

    def _creative(self, route):
        from .preparation.creative_gui import CreativeDialog
        widget = CreativeDialog(self.prep, integrated=True)
        memory = self.router.memory("creative")
        widget.input.setPlainText(memory.get("input_draft", ""))
        model_index = widget.model.findData(memory.get("model"))
        if model_index >= 0: widget.model.setCurrentIndex(model_index)
        QTimer.singleShot(0, lambda: (
            widget.chat.verticalScrollBar().setValue(int(memory.get("conversation_scroll", 0))),
            widget.draft.verticalScrollBar().setValue(int(memory.get("proposal_scroll", 0)))))
        return self._embed(widget, "creative")

    def _assembly(self, route):
        chapter = self.current_chapter()
        if not chapter:
            return self._embed(EmptyWorkspace(
                "尚无章节", "先在 Preparation 建立 Production Script。"), "assembly")
        from .preparation.finishing_gui import ChapterFinishingDialog
        widget = ChapterFinishingDialog(self.prep, chapter.id,
                                        selected_shot_id=route.shot_id, integrated=True)
        memory = self.router.memory("assembly")
        selected = memory.get("selected_segment")
        if selected:
            try: widget.refresh(selected)
            except Exception: pass
        QTimer.singleShot(0, lambda: (
            widget.strip.horizontalScrollBar().setValue(int(memory.get("timeline_scroll", 0))),
            widget.inspector_scroll.verticalScrollBar().setValue(
                int(memory.get("inspector_scroll", 0))),
            widget.player.setPosition(int(memory.get("playhead", 0)))))
        return self._embed(widget, "assembly")

    def chapter_changed(self, index):
        if index < 0 or not self.workspace.script: return
        chapter_id = self.chapter_choice.itemData(index)
        chapter = next((c for c in self.workspace.script.chapters if c.id == chapter_id), None)
        shot_id = chapter.shots[0].id if chapter and chapter.shots else None
        self.navigate(self.router.current.workspace, chapter_id=chapter_id, shot_id=shot_id)

    def refresh_all(self):
        self.workspace = self.prep.workspace
        self.prep.refresh()
        self.preparation_page.workspace = self.workspace
        self.preparation_page.refresh()
        self._sync_context(self.router.resolve(self.router.current))
        widget = self.current_workspace_widget
        if widget and widget not in (self.preparation_page, self.settings_page):
            try: widget.refresh()
            except Exception: pass
        self.refresh_activity()

    def refresh_activity(self):
        self._cleanup_inactive_pages()
        self.activity_button.setText(f"活动  {len(self.activity.active())}")

    def open_activity(self):
        menu = QMenu(self)
        records = self.activity.records()[:12]
        if not records:
            item = menu.addAction("暂无活动"); item.setEnabled(False)
        for record in records:
            state = {"running": "运行中", "queued": "等待", "failed": "失败",
                     "succeeded": "完成", "canceled": "已取消"}.get(record["state"], record["state"])
            action = menu.addAction(f"{record['label']}  ·  {state}")
            route = record["route"]
            action.triggered.connect(lambda checked=False, target=route:
                self.navigate(target["workspace"], chapter_id=target.get("chapter_id"),
                              shot_id=target.get("shot_id"),
                              object_type=target.get("object_type"),
                              object_id=target.get("object_id"), deep_link=True,
                              reason="后台活动"))
        menu.exec(self.activity_button.mapToGlobal(self.activity_button.rect().bottomLeft()))

    def open_system_menu(self):
        menu = QMenu(self)
        menu.addAction("打开项目…", self.open_project)
        menu.addAction("设置…", lambda: self.navigate("settings", deep_link=True, reason="系统设置"))
        menu.addSeparator()
        current = menu.addAction("当前布局 · D"); current.setEnabled(False)
        menu.exec(self.more_button.mapToGlobal(self.more_button.rect().bottomRight()))

    def open_project(self):
        path = QFileDialog.getExistingDirectory(self, "打开或创建项目",
                                                str(self.workspace.root.parent))
        if not path: return
        try:
            self.capture_current()
            self.prep.open_workspace(path)
            self.workspace = self.prep.workspace
            self.router = WorkspaceRouter(self.workspace)
            self.activity = ActivityAdapter(self.workspace)
            self.preparation_page.workspace = self.workspace
            self.show_route(self.router.current)
        except Exception as exc:
            QMessageBox.warning(self, "无法打开项目", str(exc))

    def closeEvent(self, event):
        self.capture_current()
        for page in self.pages.values():
            worker = getattr(page, "worker", None)
            if worker and worker.isRunning():
                QMessageBox.information(self, "后台任务仍在运行",
                                        "请等待当前本机会话任务完成后再关闭应用。")
                event.ignore(); return
        try:
            self.prep.save_draft()
            if self.session_path:
                import json
                self.session_path.write_text(json.dumps(
                    {"last_project": str(self.workspace.root)}, ensure_ascii=False),
                    encoding="utf-8")
            if self.prep.lock: self.prep.lock.unlock()
        except Exception as exc:
            QMessageBox.warning(self, "项目尚未安全关闭", str(exc))
            event.ignore(); return
        event.accept()
