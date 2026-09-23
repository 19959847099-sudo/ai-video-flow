"""Local media generation and shared execution/result/review records. No network calls."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Literal

from PIL import Image, ImageDraw, ImageFont
from pydantic import Field

from .core import Record, Store, GenerationTask, DummyProviderAdapter, new_id, write_json


from .resources import media_tool


def run_media(arguments):
    result = subprocess.run(arguments, capture_output=True, timeout=45,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    if result.returncode:
        raise ValueError("媒体处理失败：" + result.stderr.decode("utf-8", errors="replace")[-1600:])
    return result.stdout


def probe_video(path):
    info = json.loads(run_media([media_tool("ffprobe"), "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=codec_name,width,height:format=duration", "-of", "json", str(path)]))
    if not info.get("streams") or float(info.get("format", {}).get("duration", 0)) <= 0:
        raise ValueError("结果不包含有效视频")
    return {**info["streams"][0], "duration": float(info["format"]["duration"])}


class Execution(Record):
    id: str = Field(default_factory=new_id)
    task_id: str
    shot_id: str
    take_number: int = Field(ge=1)
    provider: Literal["local-mock", "fal"] = "local-mock"
    model: str = "mock-card-video-v0"
    simulation_only: Literal[True] = True
    status: Literal["pending", "processing", "completed", "failed"] = "pending"
    history: list[str] = Field(default_factory=lambda: ["pending"])
    retry_of: str | None = None
    result_id: str | None = None
    error: str = ""


class Result(Record):
    id: str
    execution_id: str
    shot_id: str
    task_id: str
    take_number: int
    provider: str
    model: str
    simulation_only: Literal[True] = True
    path: str
    poster_path: str
    sha256: str
    duration: float


class Review(Record):
    shot_id: str
    selected_result_id: str | None = None
    rejected: dict[str, str] = Field(default_factory=dict)


class MockProviderAdapter(DummyProviderAdapter):
    def __init__(self, store: Store):
        self.store = store

    def prepare(self, task, asset_root):
        request = super().prepare(task, asset_root)
        request.update(provider="local-mock", model="mock-card-video-v0")
        return request

    def task_snapshot(self, task_id):
        # Validate the ID before using it as a path component.
        self.store.record_path("tasks", task_id)
        return GenerationTask.model_validate_json(
            self.store.path(f"tasks/{task_id}/task.json").read_text(encoding="utf-8"))

    def executions(self, shot_id=None):
        items = [Execution.model_validate_json(p.read_text(encoding="utf-8"))
                 for p in self.store.path("executions").glob("*.json")]
        return sorted([j for j in items if shot_id is None or j.shot_id == shot_id],
                      key=lambda j: (j.shot_id, j.take_number))

    def execution(self, job_id):
        return Execution.model_validate_json(
            self.store.record_path("executions", job_id).read_text(encoding="utf-8"))

    def save_execution(self, job):
        write_json(self.store.record_path("executions", job.id), job.model_dump())

    def submit(self, shot_id, retry_of=None, generation_description=None):
        media_tool("ffmpeg")
        media_tool("ffprobe")
        if retry_of:
            previous = self.result(retry_of)
            if previous.shot_id != shot_id or retry_of not in self.review(shot_id).rejected:
                raise ValueError("Retry 必须来自当前 Shot 已 Reject 的结果")
        if any(j.status in ("pending", "processing") for j in self.executions(shot_id)):
            raise ValueError("这个 Shot 已有进行中的生成，请等待完成")
        task = self.store.task(shot_id, generation_description)
        if not task.scene:
            raise ValueError("Mock 视频需要场景与状态；旧 Shot 可继续 Dummy 验证，或先补齐场景")
        request = self.prepare(task, self.store.root)
        jobs = self.executions(shot_id)
        job = Execution(task_id=task.id, shot_id=shot_id, provider=request['provider'], model=request['model'],
            take_number=max((j.take_number for j in jobs), default=0) + 1, retry_of=retry_of)
        folder = self.store.path(f"tasks/{task.id}")
        write_json(folder / "task.json", task.model_dump())
        write_json(folder / ("mock_request.json" if job.provider == "local-mock" else "provider_request.json"), request)
        self.save_execution(job)
        return job

    def poll(self, job_id):
        job = self.execution(job_id)
        if job.status == "pending":
            job.status = "processing"
            job.history.append("processing")
            self.save_execution(job)
        elif job.status == "processing":
            try:
                # A processing job can be resumed after an application restart.
                task = self.task_snapshot(job.task_id)
                output = self.make_video(job, task)
                result = self.ingest(job, output)
                job.result_id = result.id
                job.status = "completed"
                output.unlink(missing_ok=True)
            except Exception as exc:
                job.status = "failed"
                job.error = str(exc)
            job.history.append(job.status)
            self.save_execution(job)
        return job

    def make_video(self, job, task):
        folder = self.store.path("mock_outputs")
        folder.mkdir(exist_ok=True)
        card = folder / f"{job.id}.png"
        output = folder / f"{job.id}.mp4"
        partial = folder / f"{job.id}.partial.mp4"
        picture = Image.new("RGB", (640, 360), (30, 45 + (job.take_number % 3) * 15, 65))
        font_path = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/msyh.ttc"
        font = ImageFont.truetype(str(font_path), 22) if font_path.exists() else ImageFont.load_default(size=22)
        draw = ImageDraw.Draw(picture)
        label = "fal FIXTURE" if job.provider == "fal" else "MOCK ONLY"
        lines = [f"{label} / 测试占位视频 / Take {job.take_number}",
                 task.shot.description, f"角色：{task.character.name} / {task.look.name}",
                 f"场景：{task.scene.name} / {task.scene_state.name}",
                 f"Shot {job.shot_id[:12]}", "零 API 调用 · 非真实 AI 生成"]
        for i, line in enumerate(lines):
            draw.text((24, 25 + i * 48), line[:42], font=font, fill="white")
        picture.save(card)
        try:
            run_media([media_tool("ffmpeg"), "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                "-loop", "1", "-i", str(card), "-t", "3", "-r", "24", "-c:v", "libx264",
                "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(partial)])
            os.replace(partial, output)
        finally:
            card.unlink(missing_ok=True)
            partial.unlink(missing_ok=True)
        return output

    def ingest(self, job, source):
        task = self.task_snapshot(job.task_id)
        if task.shot.id != job.shot_id:
            raise ValueError("生成任务与 Shot 关系不匹配，拒绝入库")
        info = probe_video(source)
        folder = self.store.path(f"results/{job.id}")
        folder.mkdir(parents=True, exist_ok=True)
        destination = folder / "video.mp4"
        partial = folder / "video.partial.mp4"
        shutil.copyfile(source, partial)
        os.replace(partial, destination)
        poster = folder / "poster.png"
        run_media([media_tool("ffmpeg"), "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                   "-i", str(destination), "-frames:v", "1", str(poster)])
        result = Result(id=job.id, execution_id=job.id, task_id=job.task_id, shot_id=job.shot_id,
            take_number=job.take_number, provider=job.provider, model=job.model,
            path=destination.relative_to(self.store.root).as_posix(),
            poster_path=poster.relative_to(self.store.root).as_posix(),
            sha256=hashlib.sha256(destination.read_bytes()).hexdigest(), duration=info["duration"])
        write_json(folder / "result.json", result.model_dump())
        return result

    def result(self, result_id):
        self.store.record_path("results", result_id)
        return Result.model_validate_json(
            self.store.path(f"results/{result_id}/result.json").read_text(encoding="utf-8"))

    def review(self, shot_id):
        path = self.store.record_path("reviews", shot_id)
        if path.exists():
            return Review.model_validate_json(path.read_text(encoding="utf-8"))
        return Review(shot_id=shot_id)

    def trace(self, result_id):
        result = self.result(result_id)
        job = self.execution(result.execution_id)
        task = self.task_snapshot(result.task_id)
        if (job.status != "completed" or job.result_id != result.id or
                job.task_id != result.task_id or job.shot_id != result.shot_id or task.shot.id != result.shot_id):
            raise ValueError("结果追溯关系不一致")
        if hashlib.sha256(self.store.path(result.path).read_bytes()).hexdigest() != result.sha256:
            raise ValueError("结果视频缺失或已被修改")
        return result, task

    def select(self, shot_id, result_id):
        result, _ = self.trace(result_id)
        if result.shot_id != shot_id:
            raise ValueError("不能选择其他 Shot 的结果")
        review = self.review(shot_id)
        review.selected_result_id = result_id
        review.rejected.pop(result_id, None)
        write_json(self.store.record_path("reviews", shot_id), review.model_dump())

    def reject(self, shot_id, result_id, reason=""):
        result, _ = self.trace(result_id)
        if result.shot_id != shot_id:
            raise ValueError("不能 Reject 其他 Shot 的结果")
        review = self.review(shot_id)
        review.rejected[result_id] = reason.strip()
        if review.selected_result_id == result_id:
            review.selected_result_id = None
        write_json(self.store.record_path("reviews", shot_id), review.model_dump())

    def play(self, result_id):
        result, _ = self.trace(result_id)
        title = f"fal Fixture Take {result.take_number}" if result.provider == "fal" else f"A-02 Mock Take {result.take_number}"
        return subprocess.Popen([media_tool("ffplay"), "-autoexit", "-loglevel", "error",
            "-window_title", title, str(self.store.path(result.path))],
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
