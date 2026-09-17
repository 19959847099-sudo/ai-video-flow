"""ComfyUI API-format img2img template + contract adapter + network-free transport.
Reference board is an integration input, NOT a proven identity-conditioning recipe.
"""
import hashlib
import io
import math
from pathlib import PurePosixPath
from uuid import UUID
from urllib.parse import urlencode, urlsplit, parse_qs
from PIL import Image, ImageOps, ImageDraw

class WorkflowBuilder:
    def __init__(self, checkpoint='REMOTE_CHECKPOINT_REQUIRED.safetensors'):
        self.checkpoint=checkpoint
    def prepare(self,task,store,folder):
        refs=task.references+task.scene_references
        uploads=[];bindings=[]
        if refs:
            board=Image.new('RGB',(task.width,task.height),'#222b32')
            cols=math.ceil(math.sqrt(len(refs)));rows=math.ceil(len(refs)/cols)
            cell=(task.width//cols,task.height//rows)
            for i,r in enumerate(refs):
                path=store.path(r.path)
                if hashlib.sha256(path.read_bytes()).hexdigest()!=r.sha256:raise ValueError('Reference 已变化')
                with Image.open(path) as im:thumb=ImageOps.contain(im.convert('RGB'),cell)
                x=(i%cols)*cell[0];y=(i//cols)*cell[1];board.paste(thumb,(x,y))
                bindings.append(dict(reference_id=r.id,sha256=r.sha256,path=r.path,role='character' if i<len(task.references) else 'scene',board_cell=[x,y,*cell]))
            file=folder/'reference-board.png';board.save(file)
            upload=dict(name=task.id+'.png',subfolder='aigc',type='input',local_path=file.relative_to(store.root).as_posix(),sha256=hashlib.sha256(file.read_bytes()).hexdigest())
            uploads.append(upload)
        def node(kind,**inputs):return dict(class_type=kind,inputs=inputs)
        graph={
            '4':node('CheckpointLoaderSimple',ckpt_name=self.checkpoint),
            '6':node('CLIPTextEncode',clip=['4',1],text=task.final_prompt),
            '7':node('CLIPTextEncode',clip=['4',1],text=''),
            '3':node('KSampler',model=['4',0],positive=['6',0],negative=['7',0],latent_image=['5',0],seed=task.seed,steps=20,cfg=7.0,sampler_name='euler',scheduler='normal',denoise=0.7 if refs else 1.0),
            '8':node('VAEDecode',samples=['3',0],vae=['4',2]),
            '9':node('SaveImage',images=['8',0],filename_prefix='aigc/'+task.id)}
        if refs:
            graph['10']=node('LoadImage',image='aigc/'+task.id+'.png')
            graph['5']=node('VAEEncode',pixels=['10',0],vae=['4',2])
        else:graph['5']=node('EmptyLatentImage',width=task.width,height=task.height,batch_size=1)
        self.validate(graph)
        return dict(template='core-img2img-board-v1',simulation_only=True,checkpoint_configured=not self.checkpoint.startswith('REMOTE_'),
            payload=dict(prompt=graph,client_id=task.id),uploads=uploads,reference_bindings=bindings,output_node='9')
    @staticmethod
    def validate(graph):
        allowed={'CheckpointLoaderSimple','CLIPTextEncode','KSampler','VAEDecode','SaveImage','LoadImage','VAEEncode','EmptyLatentImage'}
        if not isinstance(graph,dict) or not graph or not all(isinstance(n,dict) for n in graph.values()) or not any(n.get('class_type')=='SaveImage' for n in graph.values()):raise ValueError('缺少输出节点')
        for key,n in graph.items():
            if not isinstance(key,str) or n.get('class_type') not in allowed or not isinstance(n.get('inputs'),dict):raise ValueError('不是支持的 API 节点图')
            for value in n['inputs'].values():
                if isinstance(value,list) and (len(value)!=2 or value[0] not in graph or not isinstance(value[1],int) or value[1]<0):raise ValueError('Workflow 节点连接无效')

class ComfyAdapter:
    """Transport owns endpoint/auth/IO. This adapter owns routes and response mapping."""
    def __init__(self,transport):self.transport=transport
    def call(self,method,path,events,body=None):
        code,response=self.transport.request(method,path,body)
        events.append(dict(method=method,path=path,request=body,http_status=code,response=response if isinstance(response,dict) else {'bytes':len(response)},api_called=False))
        if not 200<=code<300:raise ValueError(f'ComfyUI HTTP {code}: {response}')
        if isinstance(response,dict) and (response.get('error') or response.get('node_errors')):raise ValueError(f'ComfyUI 拒绝工作流: {response}')
        return response
    def submit(self,workflow,events):
        for upload in workflow['uploads']:
            multipart=dict(content_type='multipart/form-data',fields=dict(type='input',subfolder=upload['subfolder'],overwrite='false'),
                files={'image':dict(filename=upload['name'],local_path=upload['local_path'],sha256=upload['sha256'])})
            response=self.call('POST','/upload/image',events,multipart)
            if (response.get('name'),response.get('subfolder'),response.get('type'))!=(upload['name'],upload['subfolder'],'input'):raise ValueError('上传图片名称与 Workflow 不匹配')
        response=self.call('POST','/prompt',events,workflow['payload'])
        identifier=response.get('prompt_id','')
        UUID(identifier)
        return identifier
    def poll(self,identifier,step,events):
        UUID(identifier)
        # Fixture time advances explicitly; a live transport would ignore this hook.
        if hasattr(self.transport, "advance"): self.transport.advance(step)
        history=self.call('GET','/history/'+identifier,events)
        if identifier in history:
            item=history[identifier];status=item.get('status',{})
            if status.get('status_str')=='error':raise ValueError('ComfyUI execution_error: '+str(status.get('messages')))
            if status.get('completed') is not True: return 'processing',None
            images=item.get('outputs',{}).get('9',{}).get('images',[])
            if len(images)!=1:raise ValueError('预期一个图片输出')
            image=images[0]
            for key in ('filename','subfolder'):
                value=image.get(key,'')
                if not isinstance(value,str) or '\\' in value or ':' in value or PurePosixPath(value).is_absolute() or '..' in PurePosixPath(value).parts:raise ValueError('远程输出路径无效')
            if not image.get('filename') or image.get('type')!='output':raise ValueError('远程图片类型不匹配')
            raw=self.call('GET','/view?'+urlencode(image),events)
            if not isinstance(raw,bytes):raise ValueError('图片响应不是二进制')
            return 'completed',raw
        queue=self.call('GET','/queue',events)
        for key,state in [('queue_running','processing'),('queue_pending','pending')]:
            if any(len(row)>1 and row[1]==identifier for row in queue.get(key,[])):return state,None
        raise ValueError('ComfyUI 任务不在 Queue / History 中；未自动重提')

class FixtureTransport:
    """Official-shaped fixtures, synthesized locally. No HTTP/key/socket fallback."""
    def __init__(self,identifier,task,workflow,store):
        self.identifier=str(UUID(identifier));self.task=task;self.workflow=workflow;self.store=store;self.step=0
    def advance(self,step):self.step=step
    def request(self,method,path,body=None):
        if (method,path)==('POST','/upload/image'):
            fields=body.get('fields',{});file=body.get('files',{}).get('image',{})
            upload=next((u for u in self.workflow['uploads'] if u['name']==file.get('filename')),None)
            if not upload or body.get('content_type')!='multipart/form-data' or fields!=dict(type='input',subfolder=upload['subfolder'],overwrite='false') or file.get('local_path')!=upload['local_path'] or file.get('sha256')!=upload['sha256'] or hashlib.sha256(self.store.path(file['local_path']).read_bytes()).hexdigest()!=file['sha256']:raise ValueError('上传 Fixture 不匹配')
            return 200,{k:upload[k] for k in ('name','subfolder','type')}
        if (method,path)==('POST','/prompt'):
            if body!=self.workflow['payload']:raise ValueError('提交 Fixture 与工作流不匹配')
            WorkflowBuilder.validate(body['prompt'])
            return 200,dict(prompt_id=self.identifier,number=1,node_errors={})
        if (method,path)==('GET','/queue'):
            row=[1,self.identifier,self.workflow['payload']['prompt'],{},['9']]
            return 200,dict(queue_pending=[row] if self.step==1 else [],queue_running=[row] if self.step==2 else [])
        if (method,path)==('GET','/history/'+self.identifier):
            if self.step<3:return 200,{}
            return 200,{self.identifier:dict(outputs={'9':dict(images=[dict(filename=self.identifier+'.png',subfolder='aigc',type='output')])},status=dict(status_str='success',completed=True,messages=[['execution_success',dict(prompt_id=self.identifier)]]))}
        if method=='GET' and urlsplit(path).path=='/view':
            query={k:v[0] for k,v in parse_qs(urlsplit(path).query).items()}
            if query!=dict(filename=self.identifier+'.png',subfolder='aigc',type='output'):raise ValueError('输出 Fixture 不匹配')
            im=Image.new('RGB',(self.task.width,self.task.height),'#283e47');draw=ImageDraw.Draw(im)
            draw.text((32,32),'FIXTURE / MOCK - NOT AI GENERATED',fill='white',font_size=25)
            draw.text((32,100),self.task.purpose,fill='#a7e3c4',font_size=24)
            draw.text((32,155),'Task: '+self.task.id,fill='white',font_size=18)
            draw.text((32,200),'Result: '+self.identifier,fill='white',font_size=18)
            draw.text((32,260),'ZERO API CALLS / HUMAN REVIEW REQUIRED',fill='white',font_size=22)
            out=io.BytesIO();im.save(out,format='PNG');return 200,out.getvalue()
        raise ValueError('Fixture 不支持此请求；禁止网络回退')
