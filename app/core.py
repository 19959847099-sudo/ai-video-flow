"""Portable production records. All media paths are relative to the data root."""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Literal, Protocol
from uuid import uuid4
from datetime import datetime, timezone

from PIL import Image
from pydantic import BaseModel, ConfigDict, Field, model_validator


def new_id():
    return uuid4().hex


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Reference(Record):
    id: str = Field(default_factory=new_id)
    name: str = Field(min_length=1)
    path: str
    sha256: str
    source_image_result_id: str | None = None


class FirstFrame(Record):
    result_id: str
    task_id: str
    shot_id: str
    path: str
    sha256: str


class Look(Record):
    id: str = Field(default_factory=new_id)
    name: str = Field(min_length=1)
    description: str = ""
    appearance: str = ""
    reference_ids: list[str] = Field(default_factory=list)


class Character(Record):
    schema_version: Literal["0.1"] = "0.1"
    id: str = Field(default_factory=new_id)
    name: str = Field(min_length=1)
    description: str = ""
    identity: str = Field(min_length=1)
    is_example: bool = False
    references: list[Reference] = Field(default_factory=list)
    identity_reference_ids: list[str] = Field(default_factory=list)
    looks: list[Look] = Field(default_factory=list)

    @model_validator(mode="after")
    def relations(self):
        ids = [r.id for r in self.references]
        if len(set(ids)) != len(ids) or len({x.id for x in self.looks}) != len(self.looks):
            raise ValueError("Reference / Look ID 重复")
        for refs in [self.identity_reference_ids] + [x.reference_ids for x in self.looks]:
            if len(set(refs)) != len(refs) or not set(refs) <= set(ids):
                raise ValueError("Reference 引用无效或重复")
        return self


class SceneState(Record):
    id: str = Field(default_factory=new_id)
    name: str = Field(min_length=1)
    description: str = ""
    environment: str = ""
    reference_ids: list[str] = Field(default_factory=list)


class Scene(Record):
    schema_version: Literal["0.2"] = "0.2"
    id: str = Field(default_factory=new_id)
    name: str = Field(min_length=1)
    description: str = ""
    identity: str = Field(min_length=1)
    is_example: bool = False
    references: list[Reference] = Field(default_factory=list)
    identity_reference_ids: list[str] = Field(default_factory=list)
    states: list[SceneState] = Field(default_factory=list)

    @model_validator(mode="after")
    def relations(self):
        ids = [r.id for r in self.references]
        if len(set(ids)) != len(ids) or len({s.id for s in self.states}) != len(self.states):
            raise ValueError("场景 Reference / State ID 重复")
        for refs in [self.identity_reference_ids] + [s.reference_ids for s in self.states]:
            if len(set(refs)) != len(refs) or not set(refs) <= set(ids):
                raise ValueError("场景 Reference 引用无效或重复")
        return self


class Shot(Record):
    # Legacy records remain readable; no implicit rewrite or invented scene.
    schema_version: Literal["0.1", "0.2"] = "0.1"
    id: str = Field(default_factory=new_id)
    description: str = Field(min_length=1)
    character_id: str
    look_id: str
    scene_id: str | None = None
    scene_state_id: str | None = None
    requirements: str = Field(min_length=1)
    generation_description: str = Field(min_length=1)
    is_example: bool = False

    @model_validator(mode="after")
    def scene_pair(self):
        if bool(self.scene_id) != bool(self.scene_state_id):
            raise ValueError("场景与场景状态必须同时选择")
        if self.schema_version == "0.2" and not self.scene_id:
            raise ValueError("A-02 Shot 必须选择场景和状态")
        return self


class GenerationTask(Record):
    schema_version: Literal["0.1", "0.2"] = "0.1"
    id: str = Field(default_factory=new_id)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    kind: Literal["video"] = "video"
    is_example: bool
    shot: Shot
    character: Character
    look: Look
    references: list[Reference]
    prompt_source: dict[str, str]
    scene: Scene | None = None
    scene_state: SceneState | None = None
    scene_references: list[Reference] = Field(default_factory=list)
    final_prompt: str = ""
    first_frame: FirstFrame | None = None

    @model_validator(mode="after")
    def context_relations(self):
        if self.first_frame and self.first_frame.shot_id != self.shot.id:
            raise ValueError("首帧不属于任务 Shot")
        if self.shot.character_id != self.character.id or self.shot.look_id != self.look.id:
            raise ValueError("任务角色 / Look 快照不匹配")
        if self.look not in self.character.looks:
            raise ValueError("任务 Look 不属于角色快照")
        expected = set(self.character.identity_reference_ids + self.look.reference_ids)
        if self.references != [r for r in self.character.references if r.id in expected]:
            raise ValueError("任务角色参考图不匹配")
        if self.scene is not None:
            if (self.scene_state is None or self.scene_state not in self.scene.states
                    or self.shot.scene_id != self.scene.id or self.shot.scene_state_id != self.scene_state.id):
                raise ValueError("任务场景 / State 快照不匹配")
            expected = set(self.scene.identity_reference_ids + self.scene_state.reference_ids)
            if self.scene_references != [r for r in self.scene.references if r.id in expected]:
                raise ValueError("任务场景参考图不匹配")
        elif self.scene_state is not None or self.scene_references or self.shot.scene_id:
            raise ValueError("任务场景上下文不完整")
        if self.schema_version == "0.2" and (self.scene is None or not self.final_prompt.strip()):
            raise ValueError("A-02 任务需要场景和最终生成描述")
        return self


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + "." + new_id() + ".tmp")
    try:
        with temp.open("w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


class Store:
    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, relative: str):
        result = (self.root / relative).resolve()
        if not result.is_relative_to(self.root):
            raise ValueError("资产路径必须位于数据目录内")
        return result

    def record_path(self, kind, identifier):
        if not re.fullmatch(r"[a-f0-9]{32}", identifier):
            raise ValueError("记录 ID 无效")
        return self.path(f"{kind}/{identifier}.json")

    def characters(self):
        return [Character.model_validate_json(p.read_text(encoding="utf-8"))
                for p in sorted(self.path("characters").glob("*.json"))]

    def shots(self):
        return [Shot.model_validate_json(p.read_text(encoding="utf-8"))
                for p in sorted(self.path("shots").glob("*.json"))]

    def character(self, identifier):
        return Character.model_validate_json(self.record_path("characters", identifier).read_text(encoding="utf-8"))

    def scenes(self):
        return [Scene.model_validate_json(p.read_text(encoding="utf-8"))
                for p in sorted(self.path("scenes").glob("*.json"))]

    def scene(self, identifier):
        return Scene.model_validate_json(self.record_path("scenes", identifier).read_text(encoding="utf-8"))

    def save_scene(self, scene):
        scene = Scene.model_validate(scene.model_dump())
        for ref in scene.references:
            if not self.path(ref.path).is_file():
                raise ValueError(f"场景 Reference 文件缺失：{ref.name}")
        write_json(self.record_path("scenes", scene.id), scene.model_dump())

    def save_character(self, character):
        character = Character.model_validate(character.model_dump())
        for ref in character.references:
            if not self.path(ref.path).is_file():
                raise ValueError(f"Reference 文件缺失：{ref.name}")
        write_json(self.record_path("characters", character.id), character.model_dump())

    def save_shot(self, shot):
        shot = Shot.model_validate(shot.model_dump())
        char = self.character(shot.character_id)
        if not any(x.id == shot.look_id for x in char.looks):
            raise ValueError("Look 不属于所选角色")
        if shot.scene_id:
            scene = self.scene(shot.scene_id)
            if not any(s.id == shot.scene_state_id for s in scene.states):
                raise ValueError("State 不属于所选场景")
        write_json(self.record_path("shots", shot.id), shot.model_dump())

    def import_reference(self, filename):
        source = Path(filename)
        if source.stat().st_size > 30 * 1024 * 1024:
            raise ValueError("图片不能超过 30 MB")
        with Image.open(source) as im:
            fmt = im.format
            im.verify()
        suffix = {"PNG": ".png", "JPEG": ".jpg", "WEBP": ".webp"}.get(fmt)
        if not suffix:
            raise ValueError("请选择 PNG、JPEG 或 WebP 图片")
        content = source.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        relative = f"assets/{digest}{suffix}"
        destination = self.path(relative)
        destination.parent.mkdir(exist_ok=True)
        if not destination.exists():
            destination.write_bytes(content)
        return Reference(name=source.name, path=relative, sha256=digest)

    def task(self, shot_id, generation_description=None, include_first_frame=True):
        shot = Shot.model_validate_json(self.record_path("shots", shot_id).read_text(encoding="utf-8"))
        if generation_description is not None:
            shot = Shot.model_validate({**shot.model_dump(), "generation_description": generation_description})
        char = self.character(shot.character_id)
        look = next((x for x in char.looks if x.id == shot.look_id), None)
        if look is None:
            raise ValueError("Shot 所引用的 Look 不存在")
        selected = set(char.identity_reference_ids + look.reference_ids)
        refs = [r for r in char.references if r.id in selected]
        if not refs:
            raise ValueError("请为角色勾选身份参考图，或为当前 Look 勾选参考图")
        scene = self.scene(shot.scene_id) if shot.scene_id else None
        state = next((s for s in scene.states if s.id == shot.scene_state_id), None) if scene else None
        if scene and state is None:
            raise ValueError("场景状态已不存在")
        scene_ids = set(scene.identity_reference_ids + state.reference_ids) if scene else set()
        scene_refs = [r for r in scene.references if r.id in scene_ids] if scene else []
        if scene and not scene_refs:
            raise ValueError("请为场景设置稳定参考图或当前状态参考图")
        for ref in refs + scene_refs:
            if hashlib.sha256(self.path(ref.path).read_bytes()).hexdigest() != ref.sha256:
                raise ValueError(f"Reference 内容已改变：{ref.name}")
        sources = {"identity": char.identity, "character_description": char.description,
                "look": look.description, "appearance": look.appearance,
                "shot": shot.description, "requirements": shot.requirements,
                "generation_description": shot.generation_description}
        if scene:
            sources.update(scene_name=scene.name, scene_identity=scene.identity,
                scene_description=scene.description, scene_state=state.name,
                scene_state_description=state.description, scene_environment=state.environment)
        first_frame = None
        binding = self.record_path("first_frames", shot.id)
        if include_first_frame and binding.exists():
            first_frame = FirstFrame.model_validate_json(binding.read_text(encoding="utf-8"))
            from .image_production import ImageProduction
            image_result, image_task = ImageProduction(self).trace(first_frame.result_id)
            if (image_result.task_id != first_frame.task_id or image_result.path != first_frame.path
                    or image_result.sha256 != first_frame.sha256 or image_task.shot is None
                    or image_task.shot.id != shot.id
                    or (image_task.shot.character_id, image_task.shot.look_id, image_task.shot.scene_id, image_task.shot.scene_state_id)
                    != (shot.character_id, shot.look_id, shot.scene_id, shot.scene_state_id)):
                raise ValueError("首帧对应资产已改变，请重新生成并选定首帧")
            if hashlib.sha256(self.path(first_frame.path).read_bytes()).hexdigest() != first_frame.sha256:
                raise ValueError("选定首帧内容与记录不匹配")
        return GenerationTask(schema_version="0.2" if scene else "0.1", first_frame=first_frame,
            is_example=char.is_example or shot.is_example or bool(scene and scene.is_example),
            shot=shot, character=char, look=look, references=refs, scene=scene,
            scene_state=state, scene_references=scene_refs, prompt_source=sources,
            final_prompt="\n".join(f"{key}: {value}" for key, value in sources.items()))

    def generate(self, shot_id, adapter: ProviderAdapter):
        task = self.task(shot_id)
        request = adapter.prepare(task, self.root)
        folder = self.path(f"tasks/{task.id}")
        write_json(folder / "task.json", task.model_dump())
        write_json(folder / "dummy_request.json", request)
        return task, folder


class ProviderAdapter(Protocol):
    """Translate neutral tasks at the edge; real adapters must use programmatic APIs."""
    def prepare(self, task: GenerationTask, asset_root: Path) -> dict: ...


class DummyProviderAdapter:
    def prepare(self, task: GenerationTask, asset_root: Path) -> dict:
        for ref in task.references + task.scene_references + ([task.first_frame] if task.first_frame else []):
            path = (asset_root / ref.path).resolve()
            if not path.is_relative_to(asset_root.resolve()) or not path.is_file():
                raise ValueError("Adapter 无法读取 Reference")
        return {"provider": "dummy", "simulation_only": True, "api_called": False,
            "task_id": task.id, "model": "dummy-video-v0",
            "input": {"text": task.final_prompt or "\n".join(task.prompt_source.values()),
                      "images": [{"asset_path": r.path, "sha256": r.sha256}
                                 for r in task.references + task.scene_references]}}
