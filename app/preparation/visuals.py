"""Shared visual language for the V0.2 desktop workspace."""
from PySide6.QtCore import Qt, QRect, QSize
from PySide6.QtGui import QColor, QPainter, QFont, QSyntaxHighlighter, QTextCharFormat, QTextFormat
from PySide6.QtWidgets import QPlainTextEdit, QWidget, QTextEdit
import re

STYLE = '''
QWidget { font-family: "Microsoft YaHei UI", "Segoe UI"; font-size: 13px; color: #29312f; }
QMainWindow, QWidget#surface { background: #f3f3ef; }
QFrame#header { background: #ffffff; border-bottom: 1px solid #e4e6e0; }
QFrame#sidebar { background: #242c2a; }
QFrame#sidebar QLabel { color: #dfe5df; background: transparent; }
QLabel#brand { font-size: 17px; font-weight: 700; letter-spacing: 1px; }
QLabel#logo { background: #e2edce; color: #263c2d; border-radius: 10px; font-size: 22px; font-weight: 700; }
QLabel#title { font-size: 27px; font-weight: 700; color: #242e29; }
QLabel#sectionTitle { font-size: 16px; font-weight: 700; }
QLabel#eyebrow { font-size: 11px; font-weight: 600; color: #869088; letter-spacing: 2px; }
QLabel#muted { color: #7a827b; font-size: 12px; }
QLabel#pill { color: #54614d; background: #edf2e5; padding: 5px 10px; border-radius: 10px; font-size: 11px; }
QLabel#status { color: #69746b; font-size: 12px; }
QLabel#count { font-size: 29px; font-weight: 600; color: #2d3c31; }
QFrame#panel { background: #ffffff; border: 1px solid #e2e5de; border-radius: 12px; }
QFrame#editorPanel { background: #fcfbf7; border: 1px solid #e2e3da; border-radius: 12px; }
QFrame#metric { background: #e9eee2; border-radius: 10px; }
QFrame#card { background: #ffffff; border: 1px solid #e6e8e1; border-radius: 9px; }
QFrame#callout { background: #f5eddd; border: 1px solid #e8dcc2; border-radius: 8px; }
QFrame#info { background: #edf1e8; border-radius: 8px; }
QLabel#error { color: #a33b39; }
QPushButton { background: #ffffff; border: 1px solid #dde2d8; border-radius: 7px; padding: 8px 13px; font-weight: 500; }
QPushButton:hover { background: #edf1e7; border-color: #bfcbb4; }
QPushButton:pressed { background: #dee7d4; }
QPushButton:disabled { color: #9da49b; background: #f2f3ef; border-color: #e5e7e1; }
QPushButton#primary { background: #354b36; color: #ffffff; border: none; padding: 10px 17px; font-weight: 600; }
QPushButton#primary:hover { background: #456446; }
QPushButton#primary:disabled { background: #a7b2a1; color: #f2f4ee; }
QPushButton#quiet { background: transparent; border: none; color: #66745f; padding: 6px 8px; }
QPushButton#quiet:hover { background: #eef2e8; }
QPushButton#nav { background: #303a35; color: #d5dfd1; border: none; text-align: left; padding: 12px; }
QPushButton#nav:hover { background: #3c483f; }
QPushButton#chapter { background: #dce9ca; color: #273e28; border: none; text-align: left; padding: 13px; font-weight: 600; }
QComboBox { background: white; border: 1px solid #dde2d8; border-radius: 6px; padding: 7px 10px; min-height: 18px; }
QComboBox::drop-down { border: none; width: 20px; }
QComboBox QAbstractItemView { background: white; selection-background-color: #e6eddc; selection-color: #283b2c; }
QListWidget { background: transparent; border: none; outline: none; }
QListWidget::item { border-radius: 6px; padding: 6px; }
QListWidget::item:selected { background: #eaf0df; color: #293c2b; }
QListWidget#shots { background: transparent; color: #bdc9bd; }
QListWidget#shots::item { padding: 15px 12px; border-radius: 8px; margin: 2px 0; }
QListWidget#shots::item:selected { background: #3b483d; color: #f3f5ef; }
QListWidget#shots::item:hover { background: #303b34; }
QPlainTextEdit { background: #fcfbf7; border: none; selection-background-color: #dee8cf; selection-color: #28352b; padding: 8px; }
QScrollArea { background: transparent; border: none; }
QScrollBar:vertical { background: transparent; width: 7px; margin: 3px; }
QScrollBar::handle:vertical { background: #ccd2c5; border-radius: 3px; min-height: 28px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QSplitter::handle { background: transparent; width: 14px; }
QProgressBar { background: #dce4d3; border: none; border-radius: 3px; max-height: 5px; }
QProgressBar::chunk { background: #64825b; border-radius: 3px; }
QDialog { background: #f6f7f2; }
QLineEdit { background: white; border: 1px solid #dce2d5; border-radius: 6px; padding: 9px; }
QToolTip { background: #27342b; color: white; border: none; padding: 7px; }
'''


class ScriptHighlighter(QSyntaxHighlighter):
    def highlightBlock(self, text):
        def style(start, size, color, bold=False):
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(color))
            if bold: fmt.setFontWeight(QFont.Weight.DemiBold)
            self.setFormat(start, size, fmt)
        if re.match(r'^.+/名称\s*$', text): style(0, len(text), '#344b32', True)
        elif re.match(r'^\d+/(章节|集数)', text): style(0, len(text), '#63734e', True)
        elif re.match(r'^\d{3,}/', text): style(0, len(text), '#354a35', True)
        elif re.match(r'^(镜头|动作|对白|表演|连续性|备注)[：:]', text):
            style(0, text.find('：') + 1 if '：' in text else text.find(':') + 1, '#8a7961', True)
        for match in re.finditer(r'【[^【】]*】', text):
            style(match.start(), match.end() - match.start(), '#6c6491')
        if text.strip().startswith('//'): style(0, len(text), '#9b9e92')


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
        self.setFont(QFont('Microsoft YaHei UI', 11))
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
        selection.format.setBackground(QColor('#f0f1e8'))
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
        painter.fillRect(event.rect(), QColor('#fcfbf7'))
        block = self.firstVisibleBlock()
        number = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        while block.isValid() and top <= event.rect().bottom():
            height = int(self.blockBoundingRect(block).height())
            if block.isVisible() and top + height >= event.rect().top():
                painter.setPen(QColor('#657557' if number == self.textCursor().blockNumber() else '#b2b7a9'))
                painter.setFont(QFont('Consolas', 9))
                painter.drawText(0, top, self.gutter.width() - 12, self.fontMetrics().height(),
                                 Qt.AlignmentFlag.AlignRight, str(number + 1))
            block = block.next()
            top += height
            number += 1
