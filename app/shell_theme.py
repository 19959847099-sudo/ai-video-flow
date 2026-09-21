"""Frozen D Layout visual tokens for the integrated PySide6 application."""
TOKENS = {
    "workspace": "#FAFAF8", "surface": "#FFFFFF", "text": "#20201E",
    "secondary": "#686863", "weak": "#B8B8B1", "divider": "#E5E5DF",
    "hover": "#F0F0EB", "selection": "#E9EEF0", "accent": "#3F5964",
    "media": "#1D2426", "danger": "#9A4D46",
}

D_STYLE = """
* { font-family:"Segoe UI Variable","Segoe UI","Microsoft YaHei UI"; font-size:12px; color:#20201E; }
QMainWindow, QDialog, QWidget#dRoot, QWidget#dPage { background:#FAFAF8; }
QLabel { background:transparent; }
QLabel#shellProject { font-size:12px; font-weight:600; }
QLabel#shellContext, QLabel#muted, QLabel#creativeMuted, QLabel#productionSmall,
QLabel#finishingMuted { color:#686863; font-size:10px; }
QLabel#pageTitle, QLabel#creativeTitle, QLabel#productionTitle, QLabel#finishingTitle {
    color:#20201E; font-size:21px; font-weight:500;
}
QLabel#sectionTitle, QLabel#productionStatus, QLabel#finishingShot {
    color:#20201E; font-size:12px; font-weight:600;
}
QFrame#shell { background:#FAFAF8; border-bottom:1px solid #E5E5DF; }
QFrame#returnBar { background:#F0F0EB; border-bottom:1px solid #E5E5DF; }
QFrame#dSurface, QFrame#creativeSurface, QFrame#productionRight, QFrame#finishingInspector {
    background:#FFFFFF; border:0; border-radius:4px;
}
QFrame#dDivider { background:#E5E5DF; min-height:1px; max-height:1px; }
QPushButton { background:transparent; border:1px solid transparent; border-radius:6px;
              padding:6px 9px; color:#686863; }
QPushButton:hover { background:#F0F0EB; color:#20201E; }
QPushButton:focus { border:1px solid #71858D; }
QPushButton#workspaceNav { padding:7px 11px; color:#686863; }
QPushButton#workspaceNav[active="true"] { color:#20201E; background:#F0F0EB; }
QPushButton#primary, QPushButton#confirmMapping {
    background:#243238; color:#FFFFFF; padding:8px 14px; font-weight:600;
}
QPushButton#primary:hover, QPushButton#confirmMapping:hover { background:#34464D; }
QPushButton:disabled { color:#B8B8B1; background:transparent; }
QComboBox, QLineEdit, QPlainTextEdit, QTextEdit {
    background:#FFFFFF; border:1px solid #E5E5DF; border-radius:6px; padding:6px 8px;
    selection-background-color:#CBD7DA; selection-color:#20201E;
}
QComboBox::drop-down { border:0; width:20px; }
QComboBox QAbstractItemView { background:#FFFFFF; border:1px solid #D8D8D2;
                              selection-background-color:#F0F0EB; }
QTextBrowser { background:transparent; border:0; color:#20201E; }
QListWidget, QTreeWidget, QTableWidget { background:transparent; border:0; outline:0; }
QListWidget::item, QTreeWidget::item { border-bottom:1px solid #EEEEEA; padding:6px; }
QListWidget::item:selected, QTreeWidget::item:selected { background:#E9EEF0; color:#20201E; }
QScrollArea { background:transparent; border:0; }
QScrollBar:vertical { background:transparent; width:8px; }
QScrollBar::handle:vertical { background:#CBCBC5; border-radius:4px; min-height:28px; }
QScrollBar:horizontal { background:transparent; height:7px; }
QScrollBar::handle:horizontal { background:#CBCBC5; border-radius:3px; min-width:28px; }
QScrollBar::add-line, QScrollBar::sub-line { width:0; height:0; }
QSplitter::handle { background:#E5E5DF; width:1px; }
QToolTip { background:#20201E; color:#FFFFFF; border:0; padding:5px; }
QLabel#candidatePreview, QLabel#previewPoster { background:#1D2426; color:#D8DDDE; border-radius:4px; }
QListWidget#candidateStrip, QListWidget#segmentStrip { background:#FFFFFF; border:0; }
QLineEdit#reviewNote, QPlainTextEdit#creativeInput, QPlainTextEdit#creativeDraft,
QPlainTextEdit#creativeDiff, QTextBrowser#creativeConversation {
    background:#FFFFFF; color:#20201E; border:1px solid #E5E5DF; border-radius:4px;
}
QDoubleSpinBox { background:#FFFFFF; color:#20201E; border:1px solid #E5E5DF;
                 padding:6px; border-radius:4px; }
QCheckBox { color:#20201E; spacing:7px; }
"""

EMBEDDED_D_STYLE = """
QDialog { background:#FAFAF8; color:#20201E; }
QFrame#creativeSurface, QFrame#productionRight, QFrame#finishingInspector {
    background:#FFFFFF; border:0; border-radius:4px;
}
QLabel#creativeTitle, QLabel#productionTitle, QLabel#finishingTitle { color:#20201E; }
QLabel#creativeMuted, QLabel#productionSmall, QLabel#finishingMuted { color:#686863; }
QLabel#productionStatus, QLabel#finishingShot { color:#20201E; }
QTextBrowser#creativeConversation, QPlainTextEdit#creativeInput, QPlainTextEdit#creativeDiff,
QPlainTextEdit#creativeDraft, QLineEdit#reviewNote { background:#FFFFFF; color:#20201E;
    border:1px solid #E5E5DF; }
QLabel#candidatePreview, QLabel#previewPoster { background:#1D2426; color:#D8DDDE; }
QListWidget#candidateStrip, QListWidget#segmentStrip { background:#FFFFFF; color:#20201E; }
"""
