"""Shared visual language for the V0.2 desktop workspace."""
from PySide6.QtCore import Qt, QRect, QRectF, QSize
from PySide6.QtGui import QColor, QPainter, QFont, QSyntaxHighlighter, QTextCharFormat, QTextFormat, QLinearGradient, QRadialGradient, QPen
from PySide6.QtWidgets import QPlainTextEdit, QWidget, QTextEdit, QStyledItemDelegate, QStyle
import re

STYLE = '''
QWidget { font-family: "Segoe UI Variable", "Microsoft YaHei UI", "Segoe UI"; font-size: 12px; color: #d7e3f0; }
QMainWindow { background: #081321; }
QFrame#header { background: rgba(13, 26, 43, 225); border: none; }
QFrame#sidebar { background: rgba(12, 26, 43, 222); border: none; }
QLabel { background: transparent; }
QLabel#brand { font-size: 15px; font-weight: 650; color: #f1f6fc; }
QLabel#title { font-size: 23px; font-weight: 600; color: #f0f6fc; }
QLabel#sectionTitle { font-size: 13px; font-weight: 600; color: #e9f1fa; }
QLabel#eyebrow { font-size: 10px; font-weight: 600; color: #829ab3; letter-spacing: 1px; }
QLabel#muted { color: #91a6bb; font-size: 11px; }
QLabel#readiness { color: #9bc5df; font-size: 11px; font-weight: 600; }
QLabel#status { color: #9bb0c5; font-size: 11px; }
QFrame#panel { background: rgba(17, 34, 54, 217); border: none; border-radius: 10px; }
QFrame#editorPanel { background: #182c40; border: none; border-radius: 10px; }
QFrame#editorPanel QLabel { color: #91a8bf; }
QFrame#editorPanel QLabel#sectionTitle { color: #e6f0fb; }
QFrame#metric { background: transparent; border: none; }
QFrame#card { background: transparent; border: none; border-radius: 6px; }
QFrame#card:hover { background: rgba(99, 145, 190, 21); }
QFrame#callout { background: #283348; border-left: 2px solid #c9a97a; border-radius: 5px; }
QFrame#info { background: rgba(36, 58, 82, 70); border: none; border-radius: 9px; }
QFrame#viewer { background: #0b1b2b; border: none; border-radius: 7px; }
QLabel#viewerImage { background: #0b1b2b; color: #849cb1; font-size: 13px; }
QLabel#viewerCaption { background: transparent; color: #a9bfd2; padding: 5px 2px; font-size: 11px; }
QLabel#error { color: #f0aaa3; }
QPushButton { background: rgba(69, 98, 127, 47); border: 1px solid #3c5873; border-radius: 7px; padding: 6px 11px; color: #d8e7f5; font-weight: 500; }
QPushButton:hover { background: #263f59; border-color: #6a96bf; color: #f5faff; }
QPushButton:focus { border-color: #9fc5e9; }
QPushButton:pressed { background: #355878; }
QPushButton:disabled { color: #667d93; background: #1d3042; border-color: #30475d; }
QPushButton:flat { background: transparent; border: none; color: #8eabc4; padding: 2px 4px; }
QPushButton:flat:hover { background: rgba(76, 122, 160, 38); color: #dcebf7; border: none; }
QPushButton#primary, QPushButton#confirmMapping { background: #d7e9f9; color: #0b223a; border: 1px solid #e4f2ff; padding: 7px 14px; font-weight: 650; }
QPushButton#primary:hover, QPushButton#confirmMapping:hover { background: #eff8ff; }
QPushButton#primary:disabled { background: #334e67; color: #9ab1c5; border-color: #45617c; }
QPushButton#quiet { background: transparent; border: 1px solid transparent; color: #a9c8e6; padding: 4px 6px; }
QPushButton#quiet:hover { background: #203b57; border-color: transparent; color: #ebf6ff; }
QPushButton#nav { background: transparent; color: #a4b9ce; border: none; text-align: left; padding: 8px 9px; border-radius: 6px; }
QPushButton#importScript { background: transparent; color: #a4b9ce; border: none; text-align: left; padding: 8px 9px; border-radius: 6px; }
QPushButton#importScript:hover { background: #233d58; color: #f1f8ff; }
QPushButton#nav:hover { background: #233d58; color: #f1f8ff; }
QPushButton#chapter { background: rgba(57, 100, 137, 49); color: #c2d9eb; border: none; text-align: left; padding: 9px 11px; border-radius: 7px; }
QPushButton#chapter:hover { background: #284865; }
QPushButton#assetName { background: transparent; color: #e4f0fb; border: none; text-align: left; padding: 0; font-size: 12px; }
QPushButton#assetName:hover { color: #a6d4ff; }
QPushButton#assetThumb { background: rgba(39, 69, 96, 70); color: #8da9c0; border: none; border-radius: 5px; padding: 0; }
QPushButton#assetThumb:hover { background: rgba(56, 94, 126, 105); }
QComboBox { background: #1c344b; color: #e1ecf7; border: 1px solid #395873; border-radius: 7px; padding: 5px 9px; min-height: 19px; }
QComboBox:hover { border-color: #719abd; }
QComboBox::drop-down { border: none; width: 20px; }
QComboBox QAbstractItemView { background: #152a40; border: 1px solid #41627f; selection-background-color: #345b7d; selection-color: #f6fbff; }
QListWidget { background: transparent; border: none; outline: none; }
QListWidget::item { padding: 5px; border-radius: 5px; }
QListWidget::item:selected { background: #294763; color: #f2f8ff; }
QListWidget#shots { background: transparent; color: #bed0e1; }
QListWidget#shots::item { padding: 0; border: none; }
QListWidget#shots::item:selected { background: transparent; }
QListWidget#shots::item:hover { background: transparent; }
QPlainTextEdit { color: #e3ebf3; background: #1c3348; border: none; selection-background-color: #486a87; selection-color: #f5f9fc; padding: 12px 11px 12px 13px; }
QListWidget#diagnostics { background: #382f3a; color: #f4c0b9; }
QScrollArea { background: transparent; border: none; }
QScrollBar:vertical { background: transparent; width: 8px; margin: 1px; }
QScrollBar::handle:vertical { background: #46627e; border-radius: 4px; min-height: 27px; }
QScrollBar::handle:vertical:hover { background: #7195b5; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QSplitter::handle { background: transparent; width: 9px; }
QSplitter::handle:hover { background: rgba(109, 155, 197, 65); }
QDialog, QMessageBox { background: #102239; }
QLineEdit { background: #152c42; border: 1px solid #456480; border-radius: 7px; padding: 7px; color: #e7f2fc; }
QLineEdit:focus { border-color: #92bfe6; }
QToolTip { background: #19344f; color: #edf6ff; border: 1px solid #6c98be; padding: 6px; }
'''



class Atmosphere(QWidget):
    """A quiet blue-black field behind the actual production surfaces."""
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        base = QLinearGradient(0, 0, 0, self.height())
        base.setColorAt(0, QColor('#0c1d32'))
        base.setColorAt(0.52, QColor('#091827'))
        base.setColorAt(1, QColor('#081321'))
        painter.fillRect(self.rect(), base)
        for x, y, radius, center in (
            (0.78, 0.05, 730, QColor(60, 119, 177, 78)),
            (0.30, 0.78, 520, QColor(32, 83, 141, 42)),
        ):
            glow = QRadialGradient(self.width() * x, self.height() * y, radius)
            glow.setColorAt(0, center)
            glow.setColorAt(0.58, QColor(center.red(), center.green(), center.blue(), 17))
            glow.setColorAt(1, QColor(center.red(), center.green(), center.blue(), 0))
            painter.fillRect(self.rect(), glow)
        painter.setPen(QPen(QColor(145, 185, 223, 9), 1))
        for x in range(44, self.width(), 88):
            painter.drawLine(x, 0, x, self.height())
        for y in range(36, self.height(), 88):
            painter.drawLine(0, y, self.width(), y)
        painter.end()


class FilmMark(QWidget):
    """Original frame-sequence mark; drawn locally, with no borrowed branding."""
    def __init__(self):
        super().__init__()
        self.setFixedSize(32, 32)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor('#aed3f3'), 1.5))
        painter.setBrush(QColor(24, 54, 82))
        painter.drawRoundedRect(QRectF(3, 6, 19, 19), 4, 4)
        painter.setPen(QPen(QColor('#e7f5ff'), 1.5))
        painter.setBrush(QColor(40, 85, 124))
        painter.drawRoundedRect(QRectF(9, 9, 19, 19), 4, 4)
        painter.setPen(QPen(QColor('#d8f0ff'), 2))
        painter.drawLine(14, 15, 22, 15)
        painter.drawLine(14, 20, 19, 20)
        painter.end()


class ShotDelegate(QStyledItemDelegate):
    """A production shot strip, rather than a file-tree row."""
    def sizeHint(self, option, index):
        return QSize(0, 66)

    def paint(self, painter, option, index):
        data = index.data(Qt.ItemDataRole.UserRole + 1)
        if not data:
            return super().paint(painter, option, index)
        number, title, done, total = data
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        rect = QRectF(option.rect).adjusted(3, 3, -4, -3)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if selected:
            fill = QLinearGradient(rect.topLeft(), rect.bottomRight())
            fill.setColorAt(0, QColor('#274a6c'))
            fill.setColorAt(1, QColor('#1d3853'))
            painter.setBrush(fill)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(rect, 8, 8)
            painter.fillRect(QRectF(rect.left(), rect.top() + 12, 2, rect.height() - 24), QColor('#a8d3f4'))
        elif hovered:
            painter.setBrush(QColor(32, 60, 86, 150))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(rect, 8, 8)
        painter.setFont(QFont('Segoe UI', 10, QFont.Weight.DemiBold))
        painter.setPen(QColor('#8fb9db' if selected else '#7294b1'))
        painter.drawText(QRectF(rect.left() + 12, rect.top() + 12, 32, 20), Qt.AlignmentFlag.AlignLeft, str(number))
        painter.setFont(QFont('Microsoft YaHei UI', 10, QFont.Weight.DemiBold if selected else QFont.Weight.Medium))
        painter.setPen(QColor('#f1f8ff' if selected else '#b9ccde'))
        title_rect = QRectF(rect.left() + 48, rect.top() + 10, rect.width() - 59, 24)
        title_text = option.fontMetrics.elidedText(str(title), Qt.TextElideMode.ElideRight, int(title_rect.width()))
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignVCenter, title_text)
        painter.setFont(QFont('Microsoft YaHei UI', 9))
        painter.setPen(QColor('#91aec5' if selected else '#728da5'))
        painter.drawText(QRectF(rect.left() + 48, rect.top() + 36, rect.width() - 66, 20),
                         Qt.AlignmentFlag.AlignVCenter, f'{done}/{total}  参照')
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor('#9bcbbd' if total and done == total else '#c9ae7f'))
        painter.drawEllipse(QRectF(rect.right() - 17, rect.top() + 44, 5, 5))
        painter.restore()


class ScriptHighlighter(QSyntaxHighlighter):
    def highlightBlock(self, text):
        def style(start, size, color, bold=False, background=None):
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(color))
            if bold:
                fmt.setFontWeight(QFont.Weight.DemiBold)
            if background:
                fmt.setBackground(QColor(background))
            self.setFormat(start, size, fmt)

        if re.match(r'^.+/名称\s*$', text):
            style(0, len(text), '#bfd4e4', True)
        elif re.match(r'^\d+/(章节|集数)', text):
            style(0, len(text), '#accce2', True)
        else:
            shot = re.match(r'^(\d{3,})/', text)
            if shot:
                style(0, len(text), '#e7f0f7', True)
                style(0, len(shot.group(1)), '#a7d1e7', True)
            elif re.match(r'^(镜头|动作|对白|表演|连续性|备注)[：:]', text):
                stop = text.find('：') + 1 if '：' in text else text.find(':') + 1
                style(0, stop, '#a0b8cb', True)
        for match in re.finditer(r'【[^【】]*】', text):
            style(match.start(), match.end() - match.start(), '#bddfdc', True, '#2b4858')
        if text.strip().startswith('//'):
            style(0, len(text), '#7890a4')


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
        font = QFont('Microsoft YaHei UI')
        font.setPointSizeF(12)
        self.setFont(font)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
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
        selection.format.setBackground(QColor('#21394b'))
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
        painter.fillRect(event.rect(), QColor('#1c3348'))
        block = self.firstVisibleBlock()
        number = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        while block.isValid() and top <= event.rect().bottom():
            height = int(self.blockBoundingRect(block).height())
            if block.isVisible() and top + height >= event.rect().top():
                shown = (number == self.textCursor().blockNumber()
                         or bool(re.match(r'^\d{3,}/', block.text())))
                if shown:
                    painter.setPen(QColor('#92bad0' if number == self.textCursor().blockNumber() else '#536f83'))
                    painter.setFont(QFont('Segoe UI', 9))
                    painter.drawText(0, top, self.gutter.width() - 12, self.fontMetrics().height(),
                                     Qt.AlignmentFlag.AlignRight, str(number + 1))
            block = block.next()
            top += height
            number += 1
