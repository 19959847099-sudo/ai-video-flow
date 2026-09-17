"""fal REST contract mapping. A-03 ships only a local fixture transport, never HTTP."""
from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
from pathlib import Path
from urllib.parse import urlparse

from .core import DummyProviderAdapter, write_json
from .production import MockProviderAdapter

MODEL = "fal-ai/kling-video/o3/standard/reference-to-video"
ENDPOINT = "https://queue.fal.run/" + MODEL
FIXTURES = Path(__file__).resolve().parent / "fixtures/fal_queue.json"


class FalAdapter:
    """Provider-specific request/response semantics; no persistence or networking."""

    def prepare(self, task, asset_root):
        DummyProviderAdapter().prepare(task, asset_root)  # Reuse safe local path validation.
        if not task.scene or not task.references or not task.scene_references:
            raise ValueError("fal 适配需要角色和场景参考图")
        refs = [("Character / Look", r) for r in task.references]
        refs += [("Scene / State", r) for r in task.scene_references]
        # Conservative local V0 budget, not a claim about the provider's universal limit.
        if len(refs) > 4:
            raise ValueError("当前 fal V0 最多使用 4 张参考图；不会静默丢弃，请精简资产参考图")
        images, bindings = [], []
        for i, (role, ref) in enumerate(refs, 1):
            raw = (Path(asset_root) / ref.path).read_bytes()
            if hashlib.sha256(raw).hexdigest() != ref.sha256:
                raise ValueError("参考图内容与任务快照哈希不匹配")
            if len(raw) > 10 * 1024 * 1024:
                raise ValueError("当前 fal V0 单张参考图上限 10 MB，请使用较小图片")
            mime = mimetypes.guess_type(ref.path)[0]
            if mime not in ("image/png", "image/jpeg", "image/webp"):
                raise ValueError("参考图格式不支持")
            images.append(f"data:{mime};base64," + base64.b64encode(raw).decode("ascii"))
            bindings.append(dict(token=f"@Image{i}", role=role, reference_id=ref.id,
                                 name=ref.name, asset_path=ref.path, sha256=ref.sha256))
        prompt = task.final_prompt + "\n\nReference bindings:\n" + "\n".join(
            f"{b['token']}: {b['role']} — {b['name']}" for b in bindings)
        if len(prompt) > 2500:
            raise ValueError("当前 fal V0 最终描述上限 2500 字符，请缩短描述；不会自动截断")
        first_frame_input = {}
        if task.first_frame:
            raw = (Path(asset_root) / task.first_frame.path).read_bytes()
            if hashlib.sha256(raw).hexdigest() != task.first_frame.sha256 or len(raw) > 10 * 1024 * 1024:
                raise ValueError("首帧哈希不匹配或超过 10 MB")
            mime = mimetypes.guess_type(task.first_frame.path)[0]
            if mime not in ("image/png", "image/jpeg", "image/webp"):
                raise ValueError("首帧格式不支持")
            first_frame_input['start_image_url'] = f"data:{mime};base64," + base64.b64encode(raw).decode("ascii")
        return dict(provider="fal", model=MODEL, simulation_only=True, transport="fixture",
            method="POST", url=ENDPOINT, headers={"Content-Type": "application/json"},
            auth_requirement="Authorization: Key <FAL_KEY>; omitted in fixture mode",
            body=dict(prompt=prompt, image_urls=images, duration="3", aspect_ratio="16:9",
                      generate_audio=False, shot_type="customize", **first_frame_input), reference_bindings=bindings,
            first_frame_binding=task.first_frame.model_dump() if task.first_frame else None)

    @staticmethod
    def checked(http_status, body):
        if not isinstance(body, dict):
            raise ValueError("fal 响应不是 JSON 对象")
        if not 200 <= http_status < 300:
            raise ValueError(f"fal HTTP {http_status}: {body.get('detail', body.get('error', '请求失败'))}")
        return body

    def submission(self, http_status, body):
        body = self.checked(http_status, body)
        request_id = body.get("request_id")
        if not isinstance(request_id, str) or not request_id or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in request_id):
            raise ValueError("fal 未返回有效 request_id")
        for key in ("status_url", "response_url"):
            url = urlparse(body.get(key, ""))
            if (url.scheme != "https" or url.netloc != "queue.fal.run" or
                    f"/requests/{request_id}/" not in url.path + "/" or url.query or url.fragment):
                raise ValueError(f"fal {key} 与 request_id 不匹配")
        return {key: body[key] for key in ("request_id", "status_url", "response_url")}

    def status(self, http_status, body, request_id):
        body = self.checked(http_status, body)
        if body.get("request_id") != request_id:
            raise ValueError("fal 状态 request_id 不匹配")
        state = body.get("status")
        if state not in ("IN_QUEUE", "IN_PROGRESS", "COMPLETED"):
            raise ValueError(f"未知 fal 状态：{state}")
        if body.get("error") or body.get("error_type"):
            raise ValueError(f"fal 生成失败：{body.get('error_type', '')} {body.get('error', '')}")
        return {"IN_QUEUE": "pending", "IN_PROGRESS": "processing", "COMPLETED": "completed"}[state]

    def result(self, http_status, body):
        body = self.checked(http_status, body)
        video = body.get("video")
        if not isinstance(video, dict):
            raise ValueError("fal 结果缺少 video")
        url = urlparse(video.get("url", ""))
        if url.scheme != "https" or not url.hostname:
            raise ValueError("fal 结果缺少 HTTPS 视频地址")
        if video.get("content_type") not in (None, "video/mp4"):
            raise ValueError("fal 返回了非 MP4 视频类型")
        return video["url"]


class FixtureTransport:
    """Deterministic local replay. No HTTP client, key lookup, or network fallback."""
    def __init__(self, request_id, scenario="success"):
        self.request_id = request_id
        self.scenario = scenario
        self.fixtures = json.loads(FIXTURES.read_text(encoding="utf-8"))
        if scenario not in self.fixtures:
            raise ValueError("未知 Fixture 场景")

    def exchange(self, method, url, step, body=None):
        base = ENDPOINT + "/requests/" + self.request_id
        expected = [("POST", ENDPOINT), ("GET", base + "/status"),
                    ("GET", base + "/status"), ("GET", base + "/status"),
                    ("GET", base + "/response")]
        if (method, url) != expected[step]:
            raise ValueError("Fixture 请求路由或顺序不匹配")
        if step == 0 and (not body or not body.get("image_urls") or not body.get("prompt")):
            raise ValueError("Fixture 提交缺少生产输入")
        entries = self.fixtures[self.scenario]
        response = entries[min(step, len(entries) - 1)]
        response = json.loads(json.dumps(response).replace("{request_id}", self.request_id).replace("{endpoint}", ENDPOINT))
        if response.get("timeout"):
            raise TimeoutError("Fixture 模拟传输超时；未自动重提")
        return response["http_status"], response["body"]

    def download(self, url, make_fixture_video):
        if url != f"https://fixture.invalid/{self.request_id}.mp4":
            raise ValueError("Fixture 没有这个视频资源；禁止回退到网络下载")
        return make_fixture_video()


class FalFixtureProvider(MockProviderAdapter):
    def prepare(self, task, asset_root):
        return FalAdapter().prepare(task, asset_root)

    def poll(self, job_id):
        job = self.execution(job_id)
        if job.status in ("completed", "failed"):
            return job
        folder = self.store.path(f"tasks/{job.task_id}")
        state_path = folder / "provider_exchange.json"
        state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {
            "transport": "fixture", "api_called": False, "step": 0, "scenario": "success", "events": []}
        adapter = FalAdapter()
        transport = FixtureTransport(job.id, state["scenario"])
        try:
            request = json.loads((folder / "provider_request.json").read_text(encoding="utf-8"))
            request_hash = hashlib.sha256((folder / "provider_request.json").read_bytes()).hexdigest()
            if state.get("request_sha256", request_hash) != request_hash:
                raise ValueError("已提交 Provider 请求被修改，拒绝继续")
            state["request_sha256"] = request_hash
            step = state["step"]
            method = "POST" if step == 0 else "GET"
            url = request["url"] if step == 0 else state["status_url" if step < 4 else "response_url"]
            code, body = transport.exchange(method, url, step, request["body"] if step == 0 else None)
            state["events"].append(dict(method=method, url=url, http_status=code, body=body))
            if step == 0:
                state.update(adapter.submission(code, body))
            elif step < 4:
                mapped = adapter.status(code, body, state["request_id"])
                # Queue completion is not local completion until result download + ingestion succeed.
                if mapped == "processing": job.status = "processing"
                if mapped == "completed": state["ready"] = True
            else:
                if not state.get("ready"): raise ValueError("fal 结果尚未就绪")
                video_url = adapter.result(code, body)
                source = transport.download(video_url, lambda: self.make_video(job, self.task_snapshot(job.task_id)))
                result = self.ingest(job, source)
                source.unlink(missing_ok=True)
                job.result_id = result.id
                job.status = "completed"
            state["step"] += 1
        except Exception as exc:
            job.status = "failed"
            job.error = str(exc)
            state["error"] = job.error
        if job.history[-1] != job.status: job.history.append(job.status)
        write_json(state_path, state)
        self.save_execution(job)
        return job


class ProductionRunner(MockProviderAdapter):
    """Two explicit routes: existing local Mock, or the one fal fixture adapter."""
    def submit(self, shot_id, retry_of=None, generation_description=None, provider="local-mock"):
        if retry_of:
            provider = self.result(retry_of).provider
        if provider == "fal":
            return FalFixtureProvider(self.store).submit(shot_id, retry_of, generation_description)
        if provider != "local-mock": raise ValueError("不支持此 Provider")
        return super().submit(shot_id, retry_of, generation_description)

    def poll(self, job_id):
        if self.execution(job_id).provider == "fal":
            return FalFixtureProvider(self.store).poll(job_id)
        return super().poll(job_id)

    def submitted_prompt(self, task_id):
        self.store.record_path("tasks", task_id)
        path = self.store.path(f"tasks/{task_id}/provider_request.json")
        return json.loads(path.read_text(encoding="utf-8"))["body"]["prompt"] if path.exists() else self.task_snapshot(task_id).final_prompt

    def trace(self, result_id):
        result, task = super().trace(result_id)
        job = self.execution(result.execution_id)
        if (result.provider, result.model) != (job.provider, job.model):
            raise ValueError("结果 Provider 与执行记录不匹配")
        if job.provider == "fal":
            folder = self.store.path(f"tasks/{job.task_id}")
            exchange = json.loads((folder / "provider_exchange.json").read_text(encoding="utf-8"))
            request_bytes = (folder / "provider_request.json").read_bytes()
            if exchange.get("request_sha256") not in (None, hashlib.sha256(request_bytes).hexdigest()):
                raise ValueError("Provider 请求与提交留痕不一致")
            if exchange.get("request_id") != job.id or not exchange.get("ready"):
                raise ValueError("Fixture 结果与 Provider 任务不匹配")
        return result, task
