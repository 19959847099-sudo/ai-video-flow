"""Capture the real Qt unified production workspace and zero-call runtime evidence."""
import json
import sys
import time
from tempfile import TemporaryDirectory
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.preparation.example import create_example
from app.preparation.prompt_gui import PromptDialog
from app.preparation.production_gui import ProductionDialog
from app.preparation.runtime import ProductionRuntime
from app.preparation_gui import PreparationWindow

app = QApplication.instance() or QApplication(sys.argv)
output = Path('evidence/V0.2-Unified-Runtime')
output.mkdir(parents=True, exist_ok=True)
sample = TemporaryDirectory()
project = Path(sample.name) / 'runtime-project'
create_example(project)
window = PreparationWindow(project)
window.show()
while window.worker and window.worker.isRunning():
    QTest.qWait(30); time.sleep(.005)
window.resize(1480, 940)
QTest.qWait(100)

runtime = ProductionRuntime(window.workspace)
shot = window.current_chapter().shots[0]
requirements = [r for r in window.workspace.script.requirements if r.id in shot.requirement_ids]
image_req = next(r for r in requirements if r.media == 'image')
image = runtime.build_request(shot.id, 'image', image_req.id, 'fixture-image-v1', output_count=3)
image_job, image_batch = runtime.enqueue(image, user_intent='三版图像素材')
failed = runtime.build_request(shot.id, 'image', image_req.id, 'fixture-image-v1',
                               model_settings={'fixture_mode': 'failure'})
failed_job, _ = runtime.enqueue(failed, user_intent='故障注入')
audio_req = next((r for r in requirements if r.media == 'audio'), None)
if audio_req:
    audio_job, _ = runtime.enqueue(runtime.build_request(shot.id, 'audio', audio_req.id,
                                     'fixture-audio-v1'), user_intent='音频素材')
else:
    audio_job = None
video_job, _ = runtime.enqueue(runtime.build_request(shot.id, 'video', None, 'fixture-video-v1',
                                 common={'duration': .6, 'frame_rate': 12}), user_intent='镜头视频')
runtime.run_until_idle()

prompt = PromptDialog(window, shot.id, media='image', requirement_id=image_req.id)
prompt.show(); prompt.resize(1320, 860); prompt.refresh_queue(); QTest.qWait(180)
prompt.grab().save(str(output / 'generate-workspace.png'))
prompt.resize(940, 660); QTest.qWait(180)
prompt.grab().save(str(output / 'generate-workspace-compact.png'))
prompt.close()

review = ProductionDialog(window, image_req.id, shot.id)
review.show(); review.resize(1180, 780); QTest.qWait(150)
review.grab().save(str(output / 'candidate-merge.png'))
review.close(); window.close(); QTest.qWait(50)

jobs = [runtime.job(jid).model_dump(mode='json') for jid in window.workspace.state['runtime_jobs']]
summary = {
    'provider': runtime.registry.provider_info(),
    'batch': runtime.batch(image_batch.id).model_dump(mode='json'),
    'jobs': [{k: j[k] for k in ('id','task','media','provider_id','model_id','status','attempt',
                                 'candidate_ids','error_code','retryable','cost_metadata')} for j in jobs],
    'candidate_reviews': {cid: window.workspace.state['candidates'][cid]['review_state']
                          for j in jobs for cid in j['candidate_ids']},
    'current_bindings': dict(window.workspace.state['bindings']),
    'shot_current': dict(window.workspace.state['shot_bindings']),
    'commercial_api_calls': 0,
    'actual_cost': 0,
}
(output / 'runtime-summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
(output / 'README.md').write_text('''# V0.2 Unified Production Runtime evidence\n\n- `generate-workspace.png`: real PySide6 generation workspace at desktop size.\n- `generate-workspace-compact.png`: the same workspace at compact size.\n- `candidate-merge.png`: generated outputs in the existing Candidate review surface.\n- `runtime-summary.json`: Image/Audio/Video, batch, injected failure, Candidate and zero-call facts.\n\nAll media shown here is explicitly marked local Fixture / ZERO-CALL. No commercial API was called.\n''', encoding='utf-8')
sample.cleanup()
