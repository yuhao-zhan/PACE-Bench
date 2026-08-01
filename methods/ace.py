"""Self-contained Agentic Context Engineering (ACE) strategy for PACE-Bench.

The candidate generator reads a structured playbook.  After verification, a
Reflector labels used bullets and extracts lessons; a Curator returns incremental
ADD/UPDATE/MERGE/DELETE operations.  Operations are applied deterministically,
so the model never rewrites the whole playbook and causes context collapse.
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from pace_bench.core.types import (
    AttemptRecord,
    EvaluationResult,
    GenerationRequest,
    RunMode,
)
from pace_bench.evaluation.config import StrategyContext, StrategyRuntime, StrategyStep
from pace_bench.evaluation.prompts import PromptBuilder


SECTIONS = (
    "STRATEGIES & INSIGHTS",
    "FORMULAS & CALCULATIONS",
    "CODE SNIPPETS & TEMPLATES",
    "COMMON MISTAKES TO AVOID",
    "PROBLEM-SOLVING HEURISTICS",
    "CONTEXT CLUES & INDICATORS",
    "OTHERS",
)


@dataclass
class Bullet:
    id: str
    section: str
    content: str
    helpful: int = 0
    harmful: int = 0


class ACEStrategy:
    """Online ACE playbook using the benchmark backbone for both auxiliary roles."""

    name = "ace"

    def __init__(
        self,
        *,
        playbook_token_budget: int = 8_000,
        ace_initial_playbook: list[dict[str, Any]] | None = None,
    ) -> None:
        if playbook_token_budget < 256:
            raise ValueError("playbook_token_budget must be at least 256")
        self.playbook_token_budget = playbook_token_budget
        self.context: StrategyContext | None = None
        self.runtime: StrategyRuntime | None = None
        self.prompts = PromptBuilder()
        self.bullets: list[Bullet] = []
        self.next_id = 1
        self.update_count = 0
        self.initial_playbook = list(ace_initial_playbook or [])

    def initialize(self, context: StrategyContext, runtime: StrategyRuntime) -> None:
        self.context = context
        self.runtime = runtime
        initial = self.initial_playbook
        if isinstance(initial, list):
            for item in initial:
                if isinstance(item, dict) and item.get("content"):
                    self.bullets.append(
                        Bullet(
                            id=str(item.get("id") or self._new_id()),
                            section=_section(str(item.get("section") or "OTHERS")),
                            content=str(item["content"]),
                            helpful=int(item.get("helpful", 0)),
                            harmful=int(item.get("harmful", 0)),
                        )
                    )

    def build_step(
        self, history: Sequence[AttemptRecord], remaining_attempts: int
    ) -> StrategyStep:
        context, _ = self._require_ready()
        prompt = _vanilla_prompt(self.prompts, context, history)
        playbook = self._format_playbook()
        if self.bullets:
            prompt = f"""# ACE Evolving Playbook

Use relevant bullets as guidance. In your analysis, cite the IDs of bullets you
actually used so their utility can be updated; still return complete Python code.

{playbook}

{prompt}"""
        attempt = history[-1].attempt + 1 if history else 1
        request = self._request(prompt, attempt=attempt, purpose="candidate")
        return StrategyStep.one(request, label="ace-generator")

    def observe(self, attempts: Sequence[AttemptRecord]) -> None:
        for attempt in attempts:
            self._update_after_attempt(attempt)

    def snapshot(self) -> dict[str, Any]:
        return {
            "playbook_token_budget": self.playbook_token_budget,
            "updates": self.update_count,
            "next_id": self.next_id,
            "bullet_count": len(self.bullets),
            "bullets": [
                {
                    "id": item.id,
                    "section": item.section,
                    "helpful": item.helpful,
                    "harmful": item.harmful,
                }
                for item in self.bullets
            ],
        }

    def finalize(self, result: EvaluationResult) -> None:
        """The engine persists :meth:`snapshot`; no duplicate state is added."""

    def _update_after_attempt(self, attempt: AttemptRecord) -> None:
        context, runtime = self._require_ready()
        used_ids = sorted(
            set(
                re.findall(
                    r"\[([a-z]+-\d{5})\]",
                    attempt.generation.text if attempt.generation else "",
                )
            )
        )
        used = [item for item in self.bullets if item.id in used_ids]
        reflection_request = self._request(
            _reflector_prompt(context.task_context, attempt, used),
            attempt=attempt.attempt,
            purpose="reflector",
        )
        reflection_result = runtime.generate_auxiliary(
            reflection_request, purpose="ace-reflector"
        )
        reflection_data = _json_object(reflection_result.text)
        tags = reflection_data.get("bullet_tags", [])
        if isinstance(tags, list):
            self._apply_tags(tags)
        reflection = str(
            reflection_data.get("reflection")
            or reflection_data.get("reasoning")
            or reflection_result.text
        )

        curator_request = self._request(
            _curator_prompt(
                context.task_context,
                self._format_playbook(),
                reflection,
                self.playbook_token_budget,
            ),
            attempt=attempt.attempt,
            purpose="curator",
        )
        curator_result = runtime.generate_auxiliary(
            curator_request, purpose="ace-curator"
        )
        curator_data = _json_object(curator_result.text)
        operations = curator_data.get("operations", [])
        if isinstance(operations, list):
            self._apply_operations([op for op in operations if isinstance(op, dict)])
        self._prune_to_budget()
        self.update_count += 1

    def _apply_tags(self, tags: list[Any]) -> None:
        by_id = {item.id: item for item in self.bullets}
        for raw in tags:
            if not isinstance(raw, dict):
                continue
            item = by_id.get(str(raw.get("id") or raw.get("bullet") or ""))
            if item is None:
                continue
            tag = str(raw.get("tag") or "neutral").lower()
            if tag == "helpful":
                item.helpful += 1
            elif tag == "harmful":
                item.harmful += 1

    def _apply_operations(self, operations: list[dict[str, Any]]) -> None:
        by_id = {item.id: item for item in self.bullets}
        for operation in operations:
            kind = str(operation.get("type") or "").upper()
            if kind == "ADD" and operation.get("content"):
                self.bullets.append(
                    Bullet(
                        self._new_id(),
                        _section(str(operation.get("section") or "OTHERS")),
                        str(operation["content"]).strip(),
                    )
                )
            elif kind == "UPDATE":
                item = by_id.get(
                    str(operation.get("bullet_id") or operation.get("id") or "")
                )
                if item and operation.get("content"):
                    item.content = str(operation["content"]).strip()
                    if operation.get("section"):
                        item.section = _section(str(operation["section"]))
            elif kind == "DELETE":
                bullet_id = str(operation.get("bullet_id") or operation.get("id") or "")
                self.bullets = [item for item in self.bullets if item.id != bullet_id]
            elif kind == "MERGE":
                source_ids = {str(value) for value in operation.get("source_ids", [])}
                sources = [item for item in self.bullets if item.id in source_ids]
                if sources and operation.get("content"):
                    self.bullets = [
                        item for item in self.bullets if item.id not in source_ids
                    ]
                    self.bullets.append(
                        Bullet(
                            self._new_id(),
                            _section(
                                str(operation.get("section") or sources[0].section)
                            ),
                            str(operation["content"]).strip(),
                            helpful=sum(item.helpful for item in sources),
                            harmful=sum(item.harmful for item in sources),
                        )
                    )
            by_id = {item.id: item for item in self.bullets}

    def _prune_to_budget(self) -> None:
        while (
            self.bullets
            and len(self._format_playbook().split()) > self.playbook_token_budget
        ):
            victim = min(
                self.bullets,
                key=lambda item: (
                    item.helpful - item.harmful,
                    item.helpful + item.harmful,
                ),
            )
            self.bullets.remove(victim)

    def _format_playbook(self) -> str:
        lines: list[str] = []
        for section in SECTIONS:
            lines.append(f"## {section}")
            for item in self.bullets:
                if item.section == section:
                    lines.append(
                        f"[{item.id}] helpful={item.helpful} harmful={item.harmful} :: {item.content}"
                    )
            lines.append("")
        return "\n".join(lines).strip()

    def _new_id(self) -> str:
        bullet_id = f"ace-{self.next_id:05d}"
        self.next_id += 1
        return bullet_id

    def _request(
        self,
        prompt: str,
        *,
        attempt: int,
        purpose: str,
    ) -> GenerationRequest:
        context, _ = self._require_ready()
        config = context.config
        return GenerationRequest(
            prompt=prompt,
            seed=config.seed + attempt,
            temperature=config.temperature,
            top_p=config.top_p,
            max_tokens=config.max_tokens,
            metadata={"attempt": attempt, "method": self.name, "purpose": purpose},
        )

    def _require_ready(self) -> tuple[StrategyContext, StrategyRuntime]:
        if self.context is None or self.runtime is None:
            raise RuntimeError("ACEStrategy must be initialized before use")
        return self.context, self.runtime


def _reflector_prompt(
    task: dict[str, Any], attempt: AttemptRecord, used: list[Bullet]
) -> str:
    used_text = (
        "\n".join(f"[{item.id}] {item.content}" for item in used) or "(none cited)"
    )
    return f"""You are the ACE Reflector. Analyze the candidate and real simulator feedback.
Extract specific reusable lessons and classify every cited playbook bullet as
helpful, harmful, or neutral. Return only JSON:
{{"reflection": "...", "bullet_tags": [{{"id": "ace-00001", "tag": "helpful"}}]}}

Task: {task['task_description']}
Success criteria: {task['success_criteria']}
Candidate code:
```python
{attempt.code}
```
Score: {attempt.score}
Success: {attempt.success}
Simulator feedback: {attempt.verification.feedback}
Cited bullets:
{used_text}"""


def _curator_prompt(
    task: dict[str, Any], playbook: str, reflection: str, budget: int
) -> str:
    return f"""You are the ACE Curator. Apply localized delta updates to the current
playbook; never rewrite it wholesale. Preserve useful details and avoid duplicates.
Return only JSON with a reasoning string and an operations list. Supported forms:
{{"type":"ADD","section":"...","content":"..."}}
{{"type":"UPDATE","bullet_id":"ace-00001","content":"..."}}
{{"type":"MERGE","source_ids":["ace-00001","ace-00002"],"section":"...","content":"..."}}
{{"type":"DELETE","bullet_id":"ace-00001"}}
Use an empty operations list when no durable update is justified. The approximate
playbook token budget is {budget}.

Task context: {task['task_description']}
Recent reflection: {reflection}

Current playbook:
{playbook}"""


def _json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    try:
        value = json.loads(stripped)
        return value if isinstance(value, dict) else {}
    except json.JSONDecodeError:
        pass
    start = stripped.find("{")
    if start < 0:
        return {}
    depth = 0
    quoted = False
    escaped = False
    for index in range(start, len(stripped)):
        char = stripped[index]
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                try:
                    value = json.loads(stripped[start : index + 1])
                    return value if isinstance(value, dict) else {}
                except json.JSONDecodeError:
                    return {}
    return {}


def _section(value: str) -> str:
    normalized = value.upper().replace("_", " ").strip()
    return normalized if normalized in SECTIONS else "OTHERS"


def _vanilla_prompt(
    builder: PromptBuilder,
    context: StrategyContext,
    history: Sequence[AttemptRecord],
) -> str:
    if not history:
        return builder.initial(context.task_context)
    previous = history[-1]
    best = max(history, key=lambda item: item.score)
    if context.config.mode == RunMode.ADAPTATION:
        reference = history[0]
        return builder.adaptation_revision(
            context.task_context,
            reference_code=context.reference_code or reference.code,
            reference_feedback=context.reference_feedback
            or reference.verification.feedback,
            best_code=best.code,
            best_feedback=best.verification.feedback,
            previous_code=previous.code,
            previous_feedback=previous.verification.feedback,
            best_attempt=best.attempt,
            previous_attempt=previous.attempt,
        )
    return builder.revision(
        context.task_context,
        best_code=best.code,
        best_feedback=best.verification.feedback,
        previous_code=previous.code,
        previous_feedback=previous.verification.feedback,
        best_attempt=best.attempt,
        previous_attempt=previous.attempt,
    )


Method = ACEStrategy
Strategy = ACEStrategy
