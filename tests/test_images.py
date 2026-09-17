import json
import unittest
from unittest.mock import patch
from pathlib import Path
import test_production as fixtures
from app.image_production import ImageProduction,ImageTask
from app.comfy_adapter import WorkflowBuilder,ComfyAdapter
from app.core import Store,GenerationTask
from app.fal_adapter import FalAdapter,ProductionRunner
from integrations.production_bridge import execute

class ImageTests(unittest.TestCase):
    setUp=fixtures.ProductionTests.setUp
    tearDown=fixtures.ProductionTests.tearDown
    def image(self,purpose='SHOT_FIRST_FRAME',identifier=None,variant=None):
        p=ImageProduction(self.store)
        j=p.submit(purpose,identifier or self.shots[0].id,variant)
        for _ in range(4):j=p.poll(j.id)
        self.assertEqual(j.status,'completed',j.error)
        return p,j
    def test_three_purposes_context_workflow_lifecycle(self):
        for purpose,identifier,variant in [('CHARACTER_REFERENCE',self.char.id,self.char.looks[0].id),('SCENE_REFERENCE',self.scene.id,self.scene.states[0].id),('SHOT_FIRST_FRAME',self.shots[0].id,None)]:
            with patch('socket.socket.connect',side_effect=AssertionError('NETWORK')):
                p,j=self.image(purpose,identifier,variant)
            r,t=p.trace(j.id);self.assertEqual(t.purpose,purpose);self.assertEqual(j.history,['pending','processing','completed'])
            workflow=json.loads((p.folder(t.id)/'workflow.json').read_text(encoding='utf-8'))
            self.assertEqual(len(workflow['reference_bindings']),len(t.references+t.scene_references))
            self.assertEqual(workflow['payload']['prompt']['6']['inputs']['text'],t.final_prompt)
            self.assertEqual(workflow['payload']['prompt']['5']['inputs']['pixels'],['10',0])
            self.assertNotIn('provider',t.model_dump());self.assertNotIn('checkpoint',t.model_dump_json())
            self.assertFalse(p.review(r.id).promotion)
            from PIL import Image
            with Image.open(self.store.path(r.path)) as im:self.assertEqual(im.size,(768,512));im.verify()
    def test_human_reference_promotion_restart(self):
        for purpose,identifier,variant,read in [('CHARACTER_REFERENCE',self.char.id,self.char.looks[0].id,self.store.character),('SCENE_REFERENCE',self.scene.id,self.scene.states[0].id,self.store.scene)]:
            p,j=self.image(purpose,identifier,variant)
            before=len(read(identifier).references)
            review=p.promote(j.id,'variant');asset=read(identifier)
            self.assertEqual(len(asset.references),before+1)
            self.assertEqual(asset.references[-1].source_image_result_id,j.id)
            self.assertIn(review.reference_id,(asset.looks if purpose=='CHARACTER_REFERENCE' else asset.states)[0].reference_ids)
            restored=ImageProduction(Store(self.store.root));self.assertEqual(restored.review(j.id),review)
            p.promote(j.id,'variant');self.assertEqual(len(read(identifier).references),before+1)
            with self.assertRaises(ValueError):p.reject(j.id)
    def test_first_frame_video_handoff_and_independent_selected_take(self):
        p,j=self.image();self.assertIsNone(self.store.task(self.shots[0].id).first_frame)
        p.promote(j.id,'first_frame');task=Store(self.store.root).task(self.shots[0].id)
        self.assertEqual(task.first_frame.result_id,j.id)
        request=FalAdapter().prepare(task,self.store.root)
        self.assertTrue(request['body']['start_image_url'].startswith('data:image/png;base64,'))
        self.assertEqual(len(request['body']['image_urls']),4)
        self.assertIsNone(ProductionRunner(self.store).review(self.shots[0].id).selected_result_id)
        self.assertEqual(GenerationTask.model_validate_json(task.model_dump_json()),task)
    def test_retry_new_snapshot_and_history(self):
        p,j=self.image();raw=(p.folder(j.task_id)/'task.json').read_bytes()
        self.char.description='new description';self.store.save_character(self.char)
        with self.assertRaises(ValueError):p.retry(j.id,'again')
        p.reject(j.id,'test');new=p.retry(j.id,'changed description')
        self.assertNotEqual(j.task_id,new.task_id);self.assertEqual(p.task(new.task_id).retry_of,j.id)
        self.assertEqual(p.task(new.task_id).character.description,'new description')
        self.assertEqual((p.folder(j.task_id)/'task.json').read_bytes(),raw)
        with self.assertRaises(ValueError):p.promote(j.id,'first_frame')
    def test_tampering_wrong_target_and_path_rejected(self):
        p,j=self.image();shot=self.shots[0];shot.look_id=self.char.looks[1].id;self.store.save_shot(shot)
        with self.assertRaises(ValueError):p.promote(j.id,'first_frame')
        result,_=p.trace(j.id);self.store.path(result.path).write_bytes(b'corrupt')
        with self.assertRaises(ValueError):p.trace(j.id)
        with self.assertRaises(ValueError):p.task('../bad')
    def test_adapter_failures_and_illegal_workflow(self):
        class Transport:
            def advance(self,step):pass
            def request(self,*args):return 400,{'error':'invalid_prompt','node_errors':{'4':{'errors':['model missing']}}}
        with self.assertRaises(ValueError):ComfyAdapter(Transport()).submit({'uploads':[],'payload':{}},[])
        with self.assertRaises(ValueError):WorkflowBuilder.validate({'nodes':[]})
        class FailedHistory(Transport):
            def request(self,*args):return 200,{'00000000-0000-0000-0000-000000000000':{'status':{'status_str':'error','messages':['execution_error']}}}
        with self.assertRaises(ValueError):ComfyAdapter(FailedHistory()).poll('00000000-0000-0000-0000-000000000000',3,[])
    def test_dsh_tool_keeps_human_gate(self):
        result=execute(self.store,'prepare_shot_first_frame',{'shot_id':self.shots[0].id})
        self.assertTrue(result['human_review_required']);self.assertIsNone(self.store.task(self.shots[0].id).first_frame)
        self.assertFalse(ImageProduction(self.store).review(result['result_id']).promotion)
        with self.assertRaises(ValueError):execute(self.store,'promote_image',{'result_id':result['result_id']})
    def test_actual_dsh_image_tool(self):
        from tools.run_harness import launch
        if not Path('integrations/dsh/node_modules/@deepseek-ai/dsh/lib/bin.js').is_file():self.skipTest('Optional DSH runtime absent')
        path=launch(self.shots[0].id,self.store.root,self.root/'image-dsh',mode='first-frame')
        trace=json.loads((path/'trace.json').read_text(encoding='utf-8'))
        self.assertEqual([s['tool'] for s in trace['steps']],['get_shot_context','prepare_shot_first_frame','get_shot_context'])
        self.assertTrue(trace['result']['human_review_required'])

    def test_restart_pending_relocation_and_stale_first_frame(self):
        import shutil
        from app.core import Shot
        p=ImageProduction(self.store);j=p.submit('SHOT_FIRST_FRAME',self.shots[0].id)
        j=p.poll(j.id);j=p.poll(j.id)
        relocated=self.root/'relocated';shutil.copytree(self.store.root,relocated)
        restored=ImageProduction(Store(relocated))
        j=restored.poll(j.id);j=restored.poll(j.id)
        self.assertEqual(j.status,'completed');restored.promote(j.id,'first_frame')
        shot=self.shots[0];shot.look_id=self.char.looks[1].id;restored.store.save_shot(shot)
        with self.assertRaises(ValueError):restored.store.task(shot.id)
        replacement=restored.submit('SHOT_FIRST_FRAME',shot.id)
        for _ in range(4):replacement=restored.poll(replacement.id)
        restored.promote(replacement.id,'first_frame')
        self.assertEqual(restored.store.task(shot.id).first_frame.result_id,replacement.id)

    def test_image_gui_gate_and_snapshot_tamper(self):
        from app.gui import App
        p,j=self.image()
        app=App(self.store.root);app.withdraw()
        try:
            panel=app.image_panel;panel.refresh(j.id);panel.choose()
            self.assertEqual(str(panel.accept_frame.cget('state')),'normal')
            self.assertEqual(str(panel.accept_identity.cget('state')),'disabled')
            self.assertEqual(str(panel.retry_button.cget('state')),'disabled')
            self.assertIsNotNone(panel.preview.image)
            panel.reason.set('test');panel.reject()
            self.assertEqual(str(panel.accept_frame.cget('state')),'disabled')
            self.assertEqual(str(panel.retry_button.cget('state')),'normal')
        finally:app.closing=True;app.worker.shutdown(wait=True);app.destroy()
        workflow=p.folder(j.task_id)/'workflow.json';workflow.write_text('{}',encoding='utf-8')
        with self.assertRaises(ValueError):p.trace(j.id)
