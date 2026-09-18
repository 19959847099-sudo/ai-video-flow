"""Approved C / 镜头上下文 visual system for the preparation workspace."""
from PySide6.QtCore import Qt, QRectF, QSize
from PySide6.QtGui import QColor, QPainter, QFont, QLinearGradient, QRadialGradient, QPen
from PySide6.QtWidgets import QPlainTextEdit, QWidget, QStyledItemDelegate, QStyle

STYLE = """
QWidget { font-family: "Segoe UI", "Microsoft YaHei UI"; font-size: 13px; color: #dce5ee; }
QMainWindow, QDialog, QMessageBox { background: #0b111a; }
QLabel { background: transparent; }
QLabel#brand { font-size: 17px; font-weight: 600; letter-spacing: 2px; color: #edf3f8; }
QPushButton#stageEnabled { font-size: 12px; color:#9cabbc; border:0; border-radius:0; padding:0 2px; }
QPushButton#stageEnabled:hover { color:#e5edf4; background:transparent; border-bottom:2px solid #809db5; }
QLabel#stageFuture { font-size: 12px; color: #758597; }
QLabel#stageActive { font-size: 12px; color: #e6edf4; border-bottom: 2px solid #b6cfe4; }
QLabel#brandSub, QLabel#eyebrow { font-size: 10px; letter-spacing: 1px; color: #879bb0; }
QLabel#projectTitle { font-size: 25px; font-weight: 500; letter-spacing: 2px; color: #eef3f7; }
QLabel#chapterNumber { font-size: 31px; font-weight: 300; color: #819bb4; }
QLabel#chapterHeading { font-size: 14px; color: #dfe8f0; }
QLabel#sectionTitle { font-size: 12px; font-weight: 600; color: #dce6ef; }
QLabel#muted, QLabel#status { color: #8fa1b4; font-size: 11px; }
QLabel#readiness { color: #b4c9d8; font-size: 11px; }
QLabel#summaryCount { color: #e0eaf2; font-size: 17px; }
QLabel#viewerCaption { color: #dce8f0; font-size: 15px; }
QLabel#error { color: #d5a097; }
QFrame#topbar { background: rgba(11,17,26,205); border-bottom: 1px solid rgba(215,234,251,17); }
QFrame#projectbar { background: transparent; }
QFrame#scriptSurface { background: #172231; border: 1px solid rgba(221,237,251,10); border-radius: 5px; }
QFrame#scriptHeader { border-bottom: 1px solid rgba(221,237,251,18); }
QFrame#scriptFooter { border-top: 1px solid rgba(221,237,251,18); }
QFrame#shotRail { border-top: 1px solid rgba(221,237,251,21); }
QFrame#callout { background: #283243; border-left: 2px solid #c9a779; border-radius: 3px; }
QFrame#viewer { background: #111b28; border-radius: 4px; }
QFrame#assetCard { background: transparent; border: none; }
QFrame#assetCard:hover { background: rgba(207,229,246,7); }
QFrame#resolutionBar { border-top: 1px solid rgba(221,237,251,18); }
QFrame#capabilityRow { background: rgba(221,237,251,5); }
QFrame#capabilitySelected { background: rgba(106,151,188,25); border-left: 2px solid #a9c6dc; }
QLabel#resolutionContext { color: #c5d5e2; font-size: 11px; }
QPushButton#resolutionQuiet { color: #9fb1c0; font-size: 11px; }
QPushButton#resolutionAction { color: #d7e4ec; font-size: 11px; }
QFrame#info { background: #14202d; border-radius: 4px; }
QPushButton { background: transparent; border: 1px solid transparent; border-radius: 4px; padding: 6px 9px; color: #aebfce; }
QPushButton:hover { background: rgba(209,232,249,13); color: #e9f2f8; }
QPushButton:focus { border: 2px solid #a8c9e7; padding: 5px 8px; }
QPushButton:disabled { color: #627386; }
QPushButton#primary, QPushButton#confirmMapping { background: #c8d9e7; color: #172330; border: 1px solid #d7e5f0; padding: 9px 17px; font-weight: 600; }
QPushButton#primary:hover, QPushButton#confirmMapping:hover { background: #e3edf4; color: #101c29; }
QPushButton#primary:disabled { background: #35485b; color: #8192a3; border-color: #35485b; }
QPushButton#tool, QPushButton#quiet, QPushButton#importScript, QPushButton#nav { color: #a7b8c8; }
QPushButton#assetThumb { background: #14202e; padding: 0; border: 1px solid transparent; border-radius: 3px; }
QPushButton#assetThumb:hover { border-color: #708aa2; background: #1d3043; }
QPushButton#assetThumb[selected="true"] { border: 1px solid #aac4d6; }
QPushButton#assetName { color: #d8e3eb; text-align: left; padding: 3px 0 0; }
QPushButton#mapAction { color: #8faac0; text-align: left; padding: 1px 0; font-size: 10px; }
QPushButton#chapter { text-align: left; color: #a9c0d4; }
QComboBox { background: rgba(25,39,55,170); color: #d9e5ee; border: 1px solid rgba(219,238,253,28); border-radius: 4px; padding: 5px 8px; min-height: 18px; }
QComboBox:hover, QComboBox:focus { border-color: #8babc5; }
QComboBox::drop-down { border: none; width: 20px; }
QComboBox QAbstractItemView { background: #182534; border: 1px solid #4a647b; selection-background-color: #2b435a; }
QListWidget { background: transparent; border: none; outline: none; }
QListWidget#shots::item { padding: 0; }
QListWidget#shots::item:selected, QListWidget#shots::item:hover { background: transparent; }
QListWidget#diagnostics { background: #2f2932; color: #ecc2b9; border-radius: 3px; }
QTextBrowser#scriptReading { background: transparent; border: none; color: #d9e4ed; selection-background-color: #34516b; }
QPlainTextEdit { background: #172231; color: #dce6ee; border: none; padding: 12px 10px; selection-background-color: #3c5870; }
QScrollArea { background: transparent; border: none; }
QScrollBar:vertical { background: transparent; width: 7px; }
QScrollBar::handle:vertical { background: #36495c; border-radius: 3px; min-height: 25px; }
QScrollBar:horizontal { background: transparent; height: 5px; }
QScrollBar::handle:horizontal { background: #36495c; border-radius: 2px; min-width: 26px; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QSplitter::handle { background: transparent; width: 8px; }
QSplitter::handle:hover { background: rgba(164,198,226,24); }
QLineEdit { background: #172637; border: 1px solid #445b71; border-radius: 4px; padding: 7px; }
QLineEdit:focus { border: 2px solid #a8c9e7; }
QToolTip { background: #1b2c3d; color: #e3edf4; border: 1px solid #536b80; padding: 5px; }
"""

class Atmosphere(QWidget):
    """Blue-black field with only background-level ambient light."""
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor('#0b111a'))
        for x, y, radius, rgb, alpha in (
            (.31, -.25, 750, (51, 82, 111), 94),
            (.96, .18, 640, (38, 69, 102), 43),
        ):
            glow = QRadialGradient(self.width()*x, self.height()*y, radius)
            glow.setColorAt(0, QColor(*rgb, alpha))
            glow.setColorAt(1, QColor(*rgb, 0))
            painter.fillRect(self.rect(), glow)
        painter.setPen(QPen(QColor(156, 189, 217, 5), 1))
        for x in range(30, self.width(), 94):
            painter.drawLine(x, 0, x, self.height())
        for y in range(18, self.height(), 94):
            painter.drawLine(0, y, self.width(), y)

class ProgressSegments(QWidget):
    """A restrained readiness meter drawn from the current chapter counts."""
    def __init__(self):
        super().__init__()
        self.total = 0
        self.ready = 0
        self.setFixedSize(190, 9)

    def set_counts(self, ready, total):
        self.ready, self.total = ready, total
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        count = max(1, min(self.total, 12))
        gap = 4
        width = (self.width() - gap*(count-1)) / count
        for i in range(count):
            painter.fillRect(QRectF(i*(width+gap), 3, width, 3),
                             QColor('#95bba9' if i < self.ready else '#2b3643'))


class FilmMark(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(24, 24)
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor('#a8bed0'), 1))
        painter.drawRect(QRectF(3, 3, 17, 17))
        painter.drawLine(8, 0, 23, 16)
        painter.drawLine(0, 8, 16, 23)

class ShotDelegate(QStyledItemDelegate):
    """Compact horizontal production unit in the persistent shot index."""
    def sizeHint(self, option, index):
        return QSize(282, 82)
    def paint(self, painter, option, index):
        number, title, done, total = index.data(Qt.ItemDataRole.UserRole + 1)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        r = QRectF(option.rect).adjusted(2, 4, -4, -4)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if selected:
            painter.fillRect(r, QColor('#1c2b3b'))
            painter.fillRect(QRectF(r.left(), r.top(), r.width(), 2), QColor('#b6ccde'))
        elif hovered:
            painter.fillRect(r, QColor(191, 219, 239, 10))
        thumb = QRectF(r.left()+9, r.top()+12, 65, 48)
        pix = index.data(Qt.ItemDataRole.UserRole + 2)
        if pix and not pix.isNull():
            crop = pix.scaled(int(thumb.width()), int(thumb.height()),
                              Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                              Qt.TransformationMode.SmoothTransformation)
            painter.drawPixmap(thumb.toRect(), crop, crop.rect().adjusted(
                (crop.width()-int(thumb.width()))//2, (crop.height()-int(thumb.height()))//2,
                -(crop.width()-int(thumb.width()))//2, -(crop.height()-int(thumb.height()))//2))
        else:
            painter.fillRect(thumb, QColor('#142232'))
            painter.setPen(QColor('#718ba1'))
            painter.setFont(QFont('Segoe UI', 13))
            painter.drawText(thumb, Qt.AlignmentFlag.AlignCenter, str(number))
        painter.setFont(QFont('Segoe UI', 9))
        painter.setPen(QColor('#8198ae'))
        painter.drawText(QRectF(r.left()+85, r.top()+11, r.width()-92, 14), Qt.AlignmentFlag.AlignLeft, 'SHOT  ' + str(number))
        painter.setFont(QFont('Microsoft YaHei UI', 11, QFont.Weight.Medium))
        painter.setPen(QColor('#e2eaf1' if selected else '#bdcbd7'))
        name = option.fontMetrics.elidedText(str(title), Qt.TextElideMode.ElideRight, int(r.width()-95))
        painter.drawText(QRectF(r.left()+85, r.top()+29, r.width()-95, 23), Qt.AlignmentFlag.AlignVCenter, name)
        painter.setFont(QFont('Microsoft YaHei UI', 9))
        painter.setPen(QColor('#91bca9' if total and done == total else '#a3aeb9'))
        painter.drawText(QRectF(r.left()+85, r.top()+55, r.width()-95, 15), Qt.AlignmentFlag.AlignLeft,
                         f'{done}/{total} 需求已处理')
        painter.restore()

class ScriptEditor(QPlainTextEdit):
    """Raw executable text editor, revealed on demand from the reading page."""
    def __init__(self):
        super().__init__()
        self.setObjectName('scriptEditor')
        font = QFont('Microsoft YaHei UI')
        font.setPixelSize(14)
        self.setFont(font)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.setTabStopDistance(32)
    def go_line(self, line):
        block = self.document().findBlockByNumber(max(0, line-1))
        cursor = self.textCursor()
        cursor.setPosition(block.position())
        self.setTextCursor(cursor)
        self.centerCursor()
        self.setFocus()
