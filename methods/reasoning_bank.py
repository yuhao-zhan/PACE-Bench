"""ReasoningBank with optional parallel MaTTS for PACE-Bench.

ReasoningBank retrieves structured memories before generation and induces new
memories from both successful and failed verifier trajectories.  MaTTS produces a
batch of candidates for one task and contrastively distills the verified batch.
The retrieval count, MaTTS width, and remaining sandbox budget are deliberately
separate settings.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from pace_bench.core.types import (
    AttemptRecord,
    EvaluationResult,
    GenerationRequest,
    RunMode,
)
from pace_bench.evaluation.config import (
    CandidateSubmission,
    StrategyContext,
    StrategyRuntime,
    StrategyStep,
)
from pace_bench.evaluation.prompts import PromptBuilder
from pace_bench.evaluation.providers import load_object


Embedder = Callable[[str], Sequence[float]]

SUCCESSFUL_INSTRUCTION = """You are an expert in physics-based 2D design. Distill
at most 3 non-overlapping, actionable, generalizable memory items from a successful
trajectory. Explain why it worked without task-specific literal values."""

FAILED_INSTRUCTION = """You are an expert in physics-based 2D design. Distill at
most 3 non-overlapping, actionable, generalizable memory items from a failed
trajectory. Explain the failure and preventive strategy without one-off values."""

PARALLEL_INSTRUCTION = """Compare and contrast the verified candidate trajectories.
Use self-contrast reasoning to identify robust success patterns and failure guards.
Return at most 5 non-overlapping, actionable, transferable memory items."""

MEMORY_FORMAT = """Return only Markdown in this repeated format:
# Memory Item i
## Title <concise title>
## Description <one sentence describing when to use it>
## Content <1-5 sentences of transferable reasoning>"""


class ReasoningBankStrategy:
    """Structured reasoning memory with budget-safe MaTTS batches."""

    name = "reasoning_bank"

    def __init__(
        self,
        *,
        retrieval_top_k: int = 5,
        matts_k: int = 2,
        max_memory_items: int = 200,
        reasoning_bank_memory: list[dict[str, Any]] | None = None,
        reasoning_bank_memory_path: str | None = None,
        reasoning_bank_embedder: str | None = None,
    ) -> None:
        if not 1 <= retrieval_top_k <= 10:
            raise ValueError("retrieval_top_k must be between 1 and 10")
        if matts_k < 1:
            raise ValueError("matts_k must be positive")
        if max_memory_items < 1:
            raise ValueError("max_memory_items must be positive")
        self.retrieval_top_k = retrieval_top_k
        self.matts_k = matts_k
        self.max_memory_items = max_memory_items
        self.context: StrategyContext | None = None
        self.runtime: StrategyRuntime | None = None
        self.prompts = PromptBuilder()
        self.memory: list[dict[str, str]] = []
        self.embedder: Embedder | None = None
        self._vectors: list[Sequence[float]] = []
        self.induction_calls = 0
        self.supplied_memory = list(reasoning_bank_memory or [])
        self.memory_path = reasoning_bank_memory_path
        self.embedder_specification = reasoning_bank_embedder

    def initialize(self, context: StrategyContext, runtime: StrategyRuntime) -> None:
        self.context = context
        self.runtime = runtime
        self.embedder = _load_embedder(self.embedder_specification)
        supplied = self.supplied_memory
        if supplied:
            self.memory = [
                _normalize_item(item) for item in supplied if isinstance(item, dict)
            ]
        configured_path = self.memory_path
        if configured_path:
            self.memory.extend(_load_jsonl(Path(str(configured_path)).expanduser()))
        self.memory = _dedupe_items(self.memory)[-self.max_memory_items :]
        self._refresh_vectors()

    def build_step(
        self, history: Sequence[AttemptRecord], remaining_attempts: int
    ) -> StrategyStep:
        context, _ = self._require_ready()
        base_prompt = _vanilla_prompt(self.prompts, context, history)
        query = _retrieval_query(context, history)
        retrieved = self._retrieve(query)
        if retrieved:
            memory_text = "\n\n".join(
                f"### {item['title']}\n{item['description']}\n{item['content']}"
                for item in retrieved
            )
            base_prompt = f"""# Retrieved ReasoningBank Memory

Use only memories relevant to the current physics and feedback:

{memory_text}

{base_prompt}"""

        # MaTTS width never exceeds the unspent sandbox-interaction budget.
        batch_size = min(self.matts_k, remaining_attempts)
        first_attempt = history[-1].attempt + 1 if history else 1
        candidates = []
        for offset in range(batch_size):
            request = self._request(
                base_prompt,
                attempt=first_attempt + offset,
                purpose="matts-candidate" if batch_size > 1 else "candidate",
                seed_offset=offset * 10_000,
            )
            candidates.append(CandidateSubmission(request=request))
        return StrategyStep.batch(
            candidates,
            metadata={
                "retrieval_top_k": self.retrieval_top_k,
                "matts_k": self.matts_k,
                "batch_size": batch_size,
            },
        )

    def observe(self, attempts: Sequence[AttemptRecord]) -> None:
        if not attempts:
            return
        context, runtime = self._require_ready()
        if len(attempts) > 1:
            instruction = PARALLEL_INSTRUCTION
            purpose = "reasoning-bank-matts-induction"
            trajectory = _parallel_trajectory(context, attempts)
            max_items = 5
        else:
            attempt = attempts[0]
            successful = attempt.success or attempt.score >= 99.0
            instruction = SUCCESSFUL_INSTRUCTION if successful else FAILED_INSTRUCTION
            purpose = "reasoning-bank-single-induction"
            trajectory = _single_trajectory(context, attempt)
            max_items = 3
        request = self._request(
            f"{instruction}\n\n{MEMORY_FORMAT}\n\n{trajectory}",
            attempt=attempts[-1].attempt,
            purpose="memory-induction",
        )
        response = runtime.generate_auxiliary(request, purpose=purpose)
        new_items = _parse_memory_markdown(response.text, max_items=max_items)
        self.memory = _dedupe_items([*self.memory, *new_items])[
            -self.max_memory_items :
        ]
        self._refresh_vectors()
        self.induction_calls += 1

    def snapshot(self) -> dict[str, Any]:
        return {
            "retrieval_top_k": self.retrieval_top_k,
            "matts_k": self.matts_k,
            "max_memory_items": self.max_memory_items,
            "induction_calls": self.induction_calls,
            "memory_item_count": len(self.memory),
            "memory_titles": [item["title"] for item in self.memory],
            "embedding": "configured" if self.embedder else "lexical-jaccard",
        }

    def finalize(self, result: EvaluationResult) -> None:
        """The engine persists :meth:`snapshot`; no duplicate state is added."""

    def _retrieve(self, query: str) -> list[dict[str, str]]:
        if not self.memory:
            return []
        if self.embedder and self._vectors:
            query_vector = self.embedder(query)
            scored = [
                (_cosine(query_vector, vector), index)
                for index, vector in enumerate(self._vectors)
            ]
        else:
            query_tokens = _tokens(query)
            scored = [
                (_jaccard(query_tokens, _tokens(_item_text(item))), index)
                for index, item in enumerate(self.memory)
            ]
        scored.sort(key=lambda pair: (-pair[0], pair[1]))
        return [self.memory[index] for _, index in scored[: self.retrieval_top_k]]

    def _refresh_vectors(self) -> None:
        self._vectors = (
            [self.embedder(_item_text(item)) for item in self.memory]
            if self.embedder
            else []
        )

    def _request(
        self,
        prompt: str,
        *,
        attempt: int,
        purpose: str,
        seed_offset: int = 0,
    ) -> GenerationRequest:
        context, _ = self._require_ready()
        config = context.config
        return GenerationRequest(
            prompt=prompt,
            seed=config.seed + attempt + seed_offset,
            temperature=config.temperature,
            top_p=config.top_p,
            max_tokens=config.max_tokens,
            metadata={"attempt": attempt, "method": self.name, "purpose": purpose},
        )

    def _require_ready(self) -> tuple[StrategyContext, StrategyRuntime]:
        if self.context is None or self.runtime is None:
            raise RuntimeError("ReasoningBankStrategy must be initialized before use")
        return self.context, self.runtime


def _single_trajectory(context: StrategyContext, attempt: AttemptRecord) -> str:
    status = "SUCCESS" if attempt.success or attempt.score >= 99.0 else "FAILURE"
    reasoning = attempt.generation.text if attempt.generation else ""
    return f"""**Task:** {context.task_context['task_description']}

**Outcome:** {status} (verifier score {attempt.score:.1f}/100)

**Model output:**
{reasoning}

**Code:**
```python
{attempt.code}
```

**Verifier feedback:**
{attempt.verification.feedback}"""


def _parallel_trajectory(
    context: StrategyContext, attempts: Sequence[AttemptRecord]
) -> str:
    blocks = [f"**Task:** {context.task_context['task_description']}"]
    for index, attempt in enumerate(attempts, start=1):
        status = "SUCCESS" if attempt.success or attempt.score >= 99.0 else "FAILURE"
        blocks.append(
            f"""**Trajectory {index}: {status}, score {attempt.score:.1f}**
```python
{attempt.code}
```
Verifier feedback: {attempt.verification.feedback}"""
        )
    return "\n\n".join(blocks)


def _retrieval_query(context: StrategyContext, history: Sequence[AttemptRecord]) -> str:
    current = context.task_context["task_description"]
    if history:
        current += "\nLatest verifier feedback: " + history[-1].verification.feedback
    meta_task = (
        "Given prior physics-simulation design tasks, select experience that helps "
        "solve the current task under its observed environment behavior."
    )
    return f"Instruct: {meta_task}\nQuery: {current}"


def _parse_memory_markdown(text: str, *, max_items: int) -> list[dict[str, str]]:
    parts = re.split(
        r"^#\s*Memory Item\s*\d*\s*$", text, flags=re.MULTILINE | re.IGNORECASE
    )
    items: list[dict[str, str]] = []
    for part in (value.strip() for value in parts if value.strip()):
        title = _field(part, "Title", "Description")
        description = _field(part, "Description", "Content")
        content_match = re.search(
            r"##\s*Content\s*(.+)\Z", part, re.DOTALL | re.IGNORECASE
        )
        content = content_match.group(1).strip() if content_match else ""
        if title or content:
            items.append(
                {
                    "title": _strip_placeholder(title) or "Strategy",
                    "description": _strip_placeholder(description),
                    "content": _strip_placeholder(content or description),
                }
            )
        if len(items) >= max_items:
            break
    return items


def _field(text: str, field: str, next_field: str) -> str:
    match = re.search(
        rf"##\s*{field}\s*(.+?)(?=\n##\s*{next_field}|\Z)",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    return match.group(1).strip() if match else ""


def _strip_placeholder(value: str) -> str:
    value = value.strip()
    return (
        value[1:-1].strip() if value.startswith("<") and value.endswith(">") else value
    )


def _normalize_item(item: dict[str, Any]) -> dict[str, str]:
    return {
        "title": str(item.get("title") or "Strategy").strip(),
        "description": str(item.get("description") or "").strip(),
        "content": str(item.get("content") or item.get("description") or "").strip(),
    }


def _load_jsonl(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(
            f"Configured ReasoningBank memory does not exist: {path}"
        )
    items: list[dict[str, str]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), 1
    ):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSONL at {path}:{line_number}") from exc
        if isinstance(value, dict):
            if isinstance(value.get("memory_items"), list):
                items.extend(
                    _normalize_item(item)
                    for item in value["memory_items"]
                    if isinstance(item, dict)
                )
            else:
                items.append(_normalize_item(value))
    return items


def _dedupe_items(items: Sequence[dict[str, str]]) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in items:
        normalized = _normalize_item(item)
        key = re.sub(r"\s+", " ", _item_text(normalized)).casefold()
        if key and key not in seen:
            seen.add(key)
            output.append(normalized)
    return output


def _item_text(item: dict[str, str]) -> str:
    return "\n".join((item["title"], item["description"], item["content"]))


def _load_embedder(specification: Any) -> Embedder | None:
    if not specification:
        return None
    if not isinstance(specification, str):
        raise TypeError("reasoning_bank_embedder must be a dotted import string")
    loaded = load_object(specification)
    instance = loaded() if isinstance(loaded, type) else loaded
    if callable(instance):
        return instance
    encode = getattr(instance, "encode", None)
    if callable(encode):
        return encode
    raise TypeError(
        "Configured ReasoningBank embedder must be callable or expose encode(text)"
    )


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z_][a-z0-9_]+", text.lower()))


def _jaccard(left: set[str], right: set[str]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 0.0


def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
    size = min(len(left), len(right))
    if not size:
        return 0.0
    dot = sum(float(left[i]) * float(right[i]) for i in range(size))
    left_norm = math.sqrt(sum(float(left[i]) ** 2 for i in range(size)))
    right_norm = math.sqrt(sum(float(right[i]) ** 2 for i in range(size)))
    return dot / (left_norm * right_norm) if left_norm and right_norm else 0.0


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


Method = ReasoningBankStrategy
Strategy = ReasoningBankStrategy
