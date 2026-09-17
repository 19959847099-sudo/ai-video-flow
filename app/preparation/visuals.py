"""Shared visual language for the V0.2 desktop workspace."""
from PySide6.QtCore import Qt, QRect, QSize
from PySide6.QtGui import QColor, QPainter, QFont, QSyntaxHighlighter, QTextCharFormat, QTextFormat
from PySide6.QtWidgets import QPlainTextEdit, QWidget, QTextEdit
import re

STYLE = '''
QWidget { font-family: "Microsoft YaHei UI", "Segoe UI"; font-size: 12px; color: #cbd2dc; }
QMainWindow, QWidget#surface { background: #1e232b; }
QFrame#header { background: #292f38; border-bottom: 1px solid #12171e; }
QFrame#sidebar { background: #252b34; border-right: 1px solid #11171e; }
QLabel { background: transparent; }
QLabel#brand { font-size: 14px; font-weight: 600; color: #e7ebf1; }
QLabel#logo { background: #384351; color: #dce6f2; border: 1px solid #617184; font-family: "Segoe UI"; font-size: 11px; font-weight: 700; }
QLabel#title { font-size: 19px; font-weight: 600; color: #e5eaf1; }
QLabel#sectionTitle { font-size: 12px; font-weight: 600; color: #e2e7ef; }
QLabel#eyebrow { font-size: 10px; font-weight: 600; color: #94a1b2; letter-spacing: 1px; }
QLabel#muted { color: #9ca8b8; font-size: 11px; }
QLabel#pill { color: #acbfd5; padding: 2px 7px; border: 1px solid #4d5e72; border-radius: 2px; font-size: 10px; }
QLabel#status { color: #9caabc; font-size: 11px; }
QFrame#panel { background: #292f38; border: 1px solid #171d24; border-radius: 0; }
QFrame#editorPanel { background: #e2e6eb; border: 1px solid #171d24; border-radius: 0; }
QFrame#editorPanel QLabel { color: #586575; }
QFrame#editorPanel QLabel#sectionTitle { color: #2b3a4d; }
QFrame#metric { background: #262d36; border-top: 1px solid #39434e; border-bottom: 1px solid #151b22; border-radius: 0; }
QFrame#card { background: #292f38; border: none; border-bottom: 1px solid #3c4652; border-radius: 0; }
QFrame#card:hover { background: #33404e; }
QFrame#callout { background: #373439; border-left: 2px solid #c4a36c; border-radius: 0; }
QFrame#info { background: #242d38; border: 1px solid #3f4a58; border-radius: 0; }
QLabel#error { color: #f0aaa3; }
QPushButton { background: #343d48; border: 1px solid #4b5867; border-radius: 2px; padding: 5px 10px; font-weight: 400; }
QPushButton:hover { background: #425164; border-color: #7290b0; }
QPushButton:pressed { background: #29405a; }
QPushButton:disabled { color: #788595; background: #2d343d; border-color: #3c4550; }
QPushButton#primary, QPushButton#confirmMapping { background: #426d99; color: #f3f7fc; border: 1px solid #7197be; padding: 5px 12px; font-weight: 600; }
QPushButton#primary:hover, QPushButton#confirmMapping:hover { background: #527faa; }
QPushButton#primary:disabled { background: #394958; color: #9aabba; border-color: #4e6071; }
QPushButton#quiet { background: transparent; border: 1px solid transparent; color: #aac1db; padding: 3px 5px; }
QPushButton#quiet:hover { background: #344457; border-color: #51677e; }
QPushButton#nav { background: transparent; color: #aab7c7; border: none; border-top: 1px solid #38414c; text-align: left; padding: 8px 2px; border-radius: 0; }
QPushButton#nav:hover { background: #33404e; color: #e5edf7; }
QPushButton#chapter { background: #303943; color: #d9e4f0; border: none; border-left: 2px solid #526171; text-align: left; padding: 7px 9px; border-radius: 0; }
QPushButton#assetName { background: transparent; color: #e1e8f2; border: none; text-align: left; padding: 0; font-size: 12px; }
QPushButton#assetName:hover { color: #9cc2ed; }
QPushButton#assetThumb { background: #171e27; color: #8b9bb0; border: 1px solid #475566; border-radius: 0; padding: 0; }
QPushButton#assetThumb:hover { border-color: #8bb1dc; }
QComboBox { background: #313a45; color: #dce3ec; border: 1px solid #4b5868; border-radius: 2px; padding: 4px 7px; min-height: 16px; }
QComboBox::drop-down { border: none; width: 15px; }
QComboBox QAbstractItemView { background: #2c3541; selection-background-color: #3c5774; selection-color: #eef4fb; }
QListWidget { background: transparent; border: none; outline: none; }
QListWidget::item { padding: 5px; border-radius: 0; }
QListWidget::item:selected { background: #39536f; color: #eff5fb; }
QListWidget#shots { background: #222932; color: #b4c0d0; }
QListWidget#shots::item { padding: 9px 8px; border-bottom: 1px solid #38424e; border-left: 2px solid transparent; margin: 0; }
QListWidget#shots::item:selected { background: #36495e; color: #ecf4fc; border-left: 2px solid #91bae8; }
QListWidget#shots::item:hover { background: #344250; }
QPlainTextEdit { color: #2b394c; background: #e2e6eb; border: none; selection-background-color: #b8cde5; selection-color: #203751; padding: 7px; }
QListWidget#diagnostics { background: #3e454e; color: #f2b6ae; }
QScrollArea { background: transparent; border: none; }
QScrollBar:vertical { background: #252d37; width: 7px; margin: 0; }
QScrollBar::handle:vertical { background: #5c6b7e; border-radius: 1px; min-height: 25px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QSplitter::handle { background: #161c23; width: 5px; }
QSplitter::handle:hover { background: #5b83ad; }
QProgressBar { background: #3d4a59; border: none; border-radius: 0; max-height: 3px; }
QProgressBar::chunk { background: #7d9dbe; border-radius: 0; }
QDialog, QMessageBox { background: #2b333e; }
QLineEdit { background: #212b36; border: 1px solid #516173; border-radius: 2px; padding: 5px; color: #e0e8f1; }
QToolTip { background: #212e3d; color: #edf4fc; border: 1px solid #5b7491; padding: 5px; }
'''



class ScriptHighlighter(QSyntaxHighlighter):
    def highlightBlock(self, text):
        def style(start, size, color, bold=False):
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(color))
            if bold: fmt.setFontWeight(QFont.Weight.DemiBold)
            self.setFormat(start, size, fmt)
        if re.match(r'^.+/名称\s*$', text): style(0, len(text), '#274667', True)
        elif re.match(r'^\d+/(章节|集数)', text): style(0, len(text), '#536f91', True)
        elif re.match(r'^\d{3,}/', text): style(0, len(text), '#315779', True)
        elif re.match(r'^(镜头|动作|对白|表演|连续性|备注)[：:]', text):
            style(0, text.find('：') + 1 if '：' in text else text.find(':') + 1, '#697a8c', True)
        for match in re.finditer(r'【[^【】]*】', text):
            style(match.start(), match.end() - match.start(), '#476e9c')
        if text.strip().startswith('//'): style(0, len(text), '#84909e')


class Gutter(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        return QSize(self.editor.gutter_width(), 0)

    def paintEvent(self, event):
        self.editor.paint_gutter(event)


class ScriptEditor(QPlainTextEdit):
    def __init__(self):
        super().__init__()
        self.setObjectName('scriptEditor')
        self.setFont(QFont('Microsoft YaHei UI', 10))
        self.setTabStopDistance(32)
        self.gutter = Gutter(self)
        self.blockCountChanged.connect(self.update_margin)
        self.updateRequest.connect(self.update_gutter)
        self.cursorPositionChanged.connect(self.highlight_line)
        self.highlighter = ScriptHighlighter(self.document())
        self.update_margin()
        self.highlight_line()

    def gutter_width(self):
        return 22 + self.fontMetrics().horizontalAdvance('9') * len(str(max(1, self.blockCount())))

    def update_margin(self, *_):
        self.setViewportMargins(self.gutter_width(), 0, 0, 0)

    def update_gutter(self, rect, dy):
        if dy: self.gutter.scroll(0, dy)
        else: self.gutter.update(0, rect.y(), self.gutter.width(), rect.height())
        if rect.contains(self.viewport().rect()): self.update_margin()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.gutter.setGeometry(QRect(cr.left(), cr.top(), self.gutter_width(), cr.height()))

    def highlight_line(self):
        selection = QTextEdit.ExtraSelection()
        selection.format.setBackground(QColor('#ccd8e5'))
        selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
        selection.cursor = self.textCursor()
        selection.cursor.clearSelection()
        self.setExtraSelections([selection])

    def go_line(self, line):
        cursor = self.textCursor()
        cursor.setPosition(self.document().findBlockByNumber(max(0, line - 1)).position())
        self.setTextCursor(cursor)
        self.centerCursor()
        self.setFocus()

    def paint_gutter(self, event):
        painter = QPainter(self.gutter)
        painter.fillRect(event.rect(), QColor('#e2e6eb'))
        block = self.firstVisibleBlock()
        number = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        while block.isValid() and top <= event.rect().bottom():
            height = int(self.blockBoundingRect(block).height())
            if block.isVisible() and top + height >= event.rect().top():
                painter.setPen(QColor('#3d709f' if number == self.textCursor().blockNumber() else '#84909d'))
                painter.setFont(QFont('Consolas', 9))
                painter.drawText(0, top, self.gutter.width() - 12, self.fontMetrics().height(),
                                 Qt.AlignmentFlag.AlignRight, str(number + 1))
            block = block.next()
            top += height
            number += 1
