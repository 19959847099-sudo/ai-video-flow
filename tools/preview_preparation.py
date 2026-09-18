"""Capture the real Qt preparation workspace; no independent mockup."""
import sys
import time
from tempfile import TemporaryDirectory
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from app.preparation.example import create_example
from app.preparation_gui import PreparationWindow, MappingDialog

app = QApplication.instance() or QApplication(sys.argv)
output = Path('evidence/V0.2-Visual4')
output.mkdir(parents=True, exist_ok=True)
sample = TemporaryDirectory()
project = Path(sample.name) / 'visual-project'
create_example(project)
window = PreparationWindow(project)
window.show()
while window.worker and window.worker.isRunning():
    QTest.qWait(30)
    time.sleep(0.005)
QTest.qWait(200)
window.resize(1480, 940)
window.shots.setCurrentRow(0)
QTest.qWait(200)
window.grab().save(str(output / 'preparation-workspace.png'))
window.resize(1200, 780)
QTest.qWait(200)
window.grab().save(str(output / 'preparation-compact.png'))
window.resize(1480, 940)
window.filter.setCurrentIndex(2)
QTest.qWait(100)
window.grab().save(str(output / 'preparation-assets.png'))
report = next(r for r in window.workspace.report() if r['requirement']['kind'] == 'environment')
dialog = MappingDialog(window, report)
dialog.show()
QTest.qWait(100)
dialog.grab().save(str(output / 'asset-mapping.png'))
dialog.reject()
window.close()
QTest.qWait(50)

sample.cleanup()
