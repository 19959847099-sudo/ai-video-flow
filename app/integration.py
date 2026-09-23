"""Formal V0.1 integration contracts for routing, memory, activity and local settings."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import os
from pathlib import Path
from typing import Any, Literal

from .version import LEGACY_USER_DATA_DIR

WorkspaceName = Literal["preparation", "production", "creative", "assembly", "settings"]
WORKSPACES = ("preparation", "production", "creative", "assembly")


@dataclass
class ReturnPoint:
    workspace: str
    project_id: str
    chapter_id: str | None = None
    shot_id: str | None = None
    object_type: str | None = None
    object_id: str | None = None
    selection: dict[str, Any] = field(default_factory=dict)
    scroll: dict[str, int] = field(default_factory=dict)
    panel: str | None = None
    tab: str | None = None
    playhead: int | None = None

    @classmethod
    def from_dict(cls, value):
        return cls(**{key: value.get(key) for key in cls.__dataclass_fields__
                      if key in value})


@dataclass
class Route:
    workspace: str
    project_id: str
    chapter_id: str | None = None
    shot_id: str | None = None
    object_type: str | None = None
    object_id: str | None = None
    origin: str | None = None
    return_point: ReturnPoint | None = None
    reason: str | None = None

    def to_dict(self):
        value = asdict(self)
        if self.return_point is None:
            value["return_point"] = None
        return value

    @classmethod
    def from_dict(cls, value):
        data = dict(value or {})
        point = data.get("return_point")
        data["return_point"] = ReturnPoint.from_dict(point) if point else None
        return cls(**{key: data.get(key) for key in cls.__dataclass_fields__
                      if key in data})


class WorkspaceRouter:
    """One project-scoped route truth with explicit deep-link return semantics."""

    KEY = "integration_v1"

    def __init__(self, workspace):
        self.workspace = workspace
        ui = workspace.state.setdefault("ui", {})
        self.state = ui.setdefault(self.KEY, {
            "last_workspace": None, "route": None, "memory": {}, "return_stack": []
        })
        self.notice = ""
        self.current = self._startup_route()
        self._persist()

    def _startup_route(self):
        saved = self.state.get("route")
        if saved:
            route = Route.from_dict(saved)
            if route.workspace in WORKSPACES:
                return self.resolve(route)
        script = self.workspace.script
        workspace = "production" if script else "preparation"
        chapter = script.chapters[0] if script and script.chapters else None
        shot = chapter.shots[0] if chapter and chapter.shots else None
        return Route(workspace=workspace, project_id=self.project_id,
                     chapter_id=chapter.id if chapter else None,
                     shot_id=shot.id if shot else None)

    @property
    def project_id(self):
        return self.workspace.state["project_id"]

    def memory(self, workspace=None):
        return self.state.setdefault("memory", {}).setdefault(
            workspace or self.current.workspace, {})

    def remember(self, workspace=None, **values):
        self.memory(workspace).update(values)
        self._persist()

    def return_point(self):
        route = self.current
        memory = dict(self.memory(route.workspace))
        return ReturnPoint(
            workspace=route.workspace, project_id=self.project_id,
            chapter_id=route.chapter_id, shot_id=route.shot_id,
            object_type=route.object_type, object_id=route.object_id,
            selection=dict(memory.get("selection", {})),
            scroll=dict(memory.get("scroll", {})),
            panel=memory.get("panel"), tab=memory.get("tab"),
            playhead=memory.get("playhead"),
        )

    def navigate(self, workspace, *, chapter_id=None, shot_id=None,
                 object_type=None, object_id=None, deep_link=False,
                 reason=None):
        if workspace not in WORKSPACES and workspace != "settings":
            raise ValueError("Unknown workspace")
        point = self.return_point() if deep_link else None
        route = Route(
            workspace=workspace, project_id=self.project_id,
            chapter_id=chapter_id if chapter_id is not None else self.current.chapter_id,
            shot_id=shot_id if shot_id is not None else self.current.shot_id,
            object_type=object_type, object_id=object_id,
            origin=self.current.workspace if deep_link else None,
            return_point=point, reason=reason,
        )
        if deep_link:
            self.state.setdefault("return_stack", []).append(asdict(point))
            self.state["return_stack"] = self.state["return_stack"][-12:]
        self.current = self.resolve(route)
        if workspace != "settings":
            self.state["last_workspace"] = workspace
        self._persist()
        return self.current

    def return_to_origin(self, fallback="production"):
        point = self.current.return_point
        stack = self.state.setdefault("return_stack", [])
        if point is not None and stack:
            # The route carries the immediate source for display and restart.
            # Consume its stack entry so it cannot become a later stale return.
            stack.pop()
        if point is None:
            point = ReturnPoint.from_dict(stack.pop()) if stack else None
        if point:
            route = Route(
                workspace=point.workspace, project_id=self.project_id,
                chapter_id=point.chapter_id, shot_id=point.shot_id,
                object_type=point.object_type, object_id=point.object_id,
            )
            self.memory(point.workspace).update({
                "selection": point.selection, "scroll": point.scroll,
                "panel": point.panel, "tab": point.tab,
                "playhead": point.playhead,
            })
        else:
            route = Route(workspace=fallback, project_id=self.project_id,
                          chapter_id=self.current.chapter_id,
                          shot_id=self.current.shot_id)
        self.current = self.resolve(route)
        self._persist()
        return self.current

    def resolve(self, route):
        self.notice = ""
        script = self.workspace.script
        chapters = {c.id: c for c in script.chapters} if script else {}
        chapter = chapters.get(route.chapter_id)
        if route.chapter_id and not chapter:
            self.notice = "原章节已不存在，已返回项目安全入口。"
        if not chapter and chapters:
            chapter = next(iter(chapters.values()))
        shots = {s.id: s for s in chapter.shots} if chapter else {}
        shot = shots.get(route.shot_id)
        if route.shot_id and not shot:
            self.notice = "原镜头已不存在，已定位到同章最近可用镜头。"
        if not shot and shots:
            shot = next(iter(shots.values()))
        workspace = route.workspace
        if workspace in ("production", "assembly") and not script:
            workspace = "preparation"
            self.notice = "项目尚无正式剧本，已返回准备工作区。"
        return Route(
            workspace=workspace, project_id=self.project_id,
            chapter_id=chapter.id if chapter else None,
            shot_id=shot.id if shot else None,
            object_type=route.object_type, object_id=route.object_id,
            origin=route.origin, return_point=route.return_point,
            reason=route.reason,
        )

    def _persist(self):
        self.state["route"] = self.current.to_dict()
        self.workspace._save()


class ActivityAdapter:
    """Read-only system observation over existing persisted runtimes."""

    def __init__(self, workspace):
        self.workspace = workspace

    def records(self):
        records = []
        for job in self.workspace.state.get("runtime_jobs", {}).values():
            records.append({
                "id": job["id"], "kind": job.get("task", "generation"),
                "state": job.get("status", "queued"),
                "label": self._job_label(job),
                "route": {
                    "workspace": "production",
                    "chapter_id": job.get("chapter_id"),
                    "shot_id": job.get("shot_id"),
                    "object_type": "requirement" if job.get("requirement_id") else "job",
                    "object_id": job.get("requirement_id") or job.get("id"),
                },
                "started_at": job.get("started_at") or job.get("created_at"),
                "error": job.get("error") or "",
                "session_only": False,
            })
        for run in self.workspace.state.get("creative_runs", {}).values():
            scope = run.get("scope", {})
            records.append({
                "id": run["id"], "kind": "creative",
                "state": run.get("status", "queued"),
                "label": "AI 协作 · " + run.get("task", "request"),
                "route": {
                    "workspace": "creative",
                    "chapter_id": scope.get("chapter_id"),
                    "shot_id": scope.get("shot_id"),
                    "object_type": "proposal" if run.get("proposal_id") else "conversation",
                    "object_id": run.get("proposal_id") or run.get("conversation_id"),
                },
                "started_at": run.get("started_at") or run.get("created_at"),
                "error": run.get("error") or "",
                "session_only": False,
            })
        for chapter_id, assembly in self.workspace.state.get("assemblies", {}).items():
            for kind in ("preview", "output", "handoff"):
                record = assembly.get(kind)
                if record:
                    records.append({
                        "id": f"{chapter_id}:{kind}", "kind": kind,
                        "state": "succeeded", "label": self._assembly_label(kind),
                        "route": {"workspace": "assembly", "chapter_id": chapter_id,
                                  "object_type": "output", "object_id": kind},
                        "started_at": record.get("created_at", ""),
                        "error": "", "session_only": False,
                    })
        return sorted(records, key=lambda item: item.get("started_at") or "", reverse=True)

    def active(self):
        return [item for item in self.records()
                if item["state"] in ("queued", "running")]

    @staticmethod
    def _job_label(job):
        labels = {
            "asset_image": "图像素材", "asset_audio": "声音素材",
            "dialogue_audio": "对白", "background_audio": "环境音",
            "video_reference": "视频参照", "shot_video": "镜头视频",
        }
        return labels.get(job.get("task"), "生成任务")

    @staticmethod
    def _assembly_label(kind):
        return {"preview": "章节预览", "output": "章节输出",
                "handoff": "专业剪辑交接"}.get(kind, kind)


class AppSettingsStore:
    """Versioned local app settings. Credentials deliberately stay outside this file."""

    VERSION = 1
    DEFAULTS = {
        "layout": "D", "reduced_motion": False, "resume_last_project": True,
        "default_project_path": "", "text_base_url": "", "text_model": "",
    }

    def __init__(self, path=None):
        configured = os.environ.get("AIVIDEO_CONFIG_PATH")
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".config"))
        self.path = Path(path or configured or base / LEGACY_USER_DATA_DIR / "settings-v1.json")
        self.values = dict(self.DEFAULTS)
        self.error = ""
        self.load()

    def load(self):
        if not self.path.is_file():
            return self.values
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if data.get("version") != self.VERSION or not isinstance(data.get("settings"), dict):
                raise ValueError("unsupported settings format")
            for key in self.DEFAULTS:
                if key in data["settings"]:
                    self.values[key] = data["settings"][key]
            if self.values["layout"] not in ("D", "C"):
                self.values["layout"] = "D"
        except (OSError, ValueError, TypeError) as exc:
            self.error = str(exc)
            self.values = dict(self.DEFAULTS)
        return self.values

    def save(self, **changes):
        unknown = set(changes) - set(self.DEFAULTS)
        if unknown:
            raise ValueError("Unknown app setting")
        values = dict(self.values)
        values.update(changes)
        if values["layout"] not in ("D", "C"):
            raise ValueError("Layout must be D or C")
        project_path = values.get("default_project_path")
        if project_path:
            target = Path(project_path)
            if not target.is_dir() or not os.access(target, os.W_OK):
                raise ValueError("默认项目位置不存在或不可写")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps({
            "version": self.VERSION, "settings": values
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, self.path)
        self.values = values
        self.error = ""
        return dict(values)

    def provider_config(self):
        return {
            "base_url": os.environ.get("OPENAI_COMPATIBLE_BASE_URL")
                        or self.values.get("text_base_url", ""),
            "model": os.environ.get("OPENAI_COMPATIBLE_MODEL")
                     or self.values.get("text_model", ""),
            "credential_configured": bool(os.environ.get("OPENAI_COMPATIBLE_API_KEY")),
        }
