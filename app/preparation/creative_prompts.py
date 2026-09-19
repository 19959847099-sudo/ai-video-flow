"""Versioned hidden prompt profiles for the controlled Creative Assistant."""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
from .script import dsl_guide

BASE_VERSION = "creative_base_v1"
PRODUCT_VERSION = "production_rules_v1"
OUTPUT_VERSION = "creative_output_v1"

BASE = """You are the Creative Assistant inside an AI film production system.
Understand creative intent and supplied production context. You may answer, review,
or propose a Production Script draft. You never write the formal project, change assets,
review Candidates, select Current, submit Jobs, change Assembly, or invent production results.
Every proposed edit remains a proposal until the human explicitly applies it."""

PRODUCT = """Production Script is the formal production source. Asset is reusable source media.
Candidate is a possible result. Review is human judgment. Current is the explicit selected result.
Job is execution fact. Assembly is edit arrangement. Draft and Proposal are temporary.
Green is not Current. Voice Reference is not Dialogue Audio. Subtitle is not Script.
Missing is a normal production state. FREE is not an Asset. Never auto-apply or auto-produce."""

OUTPUT = """Return one JSON object only, matching creative_output_v1:
{"assistant_message":"string","proposal":null}
or
{"assistant_message":"string","proposal":{"proposal_type":"script_draft","draft":"complete Production Script","summary":"string","notes":["string"]}}
Do not return markdown fences, patches, auto_apply, tool calls, or commentary outside JSON.
A proposal draft must contain the complete resulting Production Script, not a fragment."""

TASKS = {
    "idea_to_script": ("idea_to_script_v1", "Turn the idea into a concise, producible Production Script draft. Unknown asset facts use '-'."),
    "normalize_external_script": ("normalize_external_script_v1", "Normalize external screenplay data into the Production Script DSL without inventing fixed asset facts."),
    "edit_chapter": ("edit_chapter_v1", "Propose only changes inside the current chapter. Preserve unrelated chapters and established references."),
    "edit_shot": ("edit_shot_v1", "Propose only changes inside the current shot. Use previous and next shots for continuity."),
    "edit_dialogue": ("edit_dialogue_v1", "Propose only dialogue wording in the current shot. Preserve speaker identity and unrelated facts."),
    "continuity_review": ("continuity_review_v1", "Review continuity and answer with notes. Produce no proposal unless explicitly asked for edits."),
    "project_discussion": ("project_discussion_v1", "Answer the creative or production question. Discussion alone must not create a proposal."),
}

@dataclass(frozen=True)
class PromptProfile:
    task: str
    version: str
    text: str

def profile(task: str) -> PromptProfile:
    if task not in TASKS:
        raise ValueError("Unknown creative task")
    version, text = TASKS[task]
    return PromptProfile(task, version, text)

def versions(task: str):
    selected = profile(task)
    return {"base": BASE_VERSION, "product": PRODUCT_VERSION, "task": selected.version,
            "output": OUTPUT_VERSION, "dsl": "production_script_dsl_v1"}

def template_hash(task: str):
    selected = profile(task)
    content = "\n\n".join((BASE, PRODUCT, selected.text, dsl_guide(), OUTPUT))
    return hashlib.sha256(content.encode("utf-8")).hexdigest()

def system_prompt(task: str):
    selected = profile(task)
    return "\n\n".join((
        "[BASE SYSTEM RULES]\n" + BASE,
        "[PRODUCT RULES]\n" + PRODUCT,
        "[TASK RULES]\n" + selected.text,
        "[PRODUCTION SCRIPT DSL]\n" + dsl_guide(),
        "[OUTPUT CONTRACT]\n" + OUTPUT,
    ))