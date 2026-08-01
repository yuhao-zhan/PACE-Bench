"""PACE-Bench adaptation of Reflexion.

The verifier remains the source of environment feedback.  After every failed
submission, the same backbone model converts that feedback into a short verbal
reflection.  A FIFO buffer of reflections is then added to the next candidate
prompt.  This follows the paper's episodic verbal-memory loop without importing
the official task-specific HotPotQA/ALFWorld harnesses.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pace_bench.core.types import (
    AttemptRecord,
    EvaluationResult,
    GenerationRequest,
    RunMode,
)
from pace_bench.evaluation.config import StrategyContext, StrategyRuntime, StrategyStep
from pace_bench.evaluation.prompts import PromptBuilder


REFLECTION_SYSTEM_PROMPT = """You are an advanced reasoning agent that improves through verbal reflection.
Analyze a failed executable design using its simulator feedback. In 3-8 complete
sentences, diagnose the physical cause and give a concise, actionable repair plan.
Focus on mechanism, geometry, forces, stability, constraints, and timing. Do not
write replacement Python code."""


class ReflexionStrategy:
    """Keep up to ``reflection_limit`` verifier-grounded verbal reflections."""

    name = "reflexion"

    def __init__(self, *, reflection_limit: int = 3) -> None:
        if reflection_limit < 1:
            raise ValueError("reflection_limit must be positive")
        self.reflection_limit = reflection_limit
        self.context: StrategyContext | None = None
        self.runtime: StrategyRuntime | None = None
        self.prompts = PromptBuilder()
        self.reflections: list[str] = []
        self._reflected_attempts: set[int] = set()

    def initialize(self, context: StrategyContext, runtime: StrategyRuntime) -> None:
        self.context = context
        self.runtime = runtime

    def build_step(
        self, history: Sequence[AttemptRecord], remaining_attempts: int
    ) -> StrategyStep:
        if history and not history[-1].success:
            self._reflect(history[-1])
        request = self._candidate_request(history)
        return StrategyStep.one(request, label="reflexion-candidate")

    def observe(self, attempts: Sequence[AttemptRecord]) -> None:
        """Reflection is deferred until the next step so final success needs no call."""

    def snapshot(self) -> dict[str, Any]:
        return {
            "reflection_limit": self.reflection_limit,
            "reflection_count": len(self.reflections),
            "reflected_attempts": sorted(self._reflected_attempts),
        }

    def finalize(self, result: EvaluationResult) -> None:
        """The engine persists :meth:`snapshot`; no duplicate state is added."""

    def _reflect(self, attempt: AttemptRecord) -> None:
        if attempt.attempt in self._reflected_attempts:
            return
        context, runtime = self._require_ready()
        prompt = f"""# Task Description

{context.task_context['task_description']}

# Success Criteria

{context.task_context['success_criteria']}

# Failed Attempt {attempt.attempt}

```python
{attempt.code}
```

# Simulator Feedback

{attempt.verification.feedback}

Diagnose the failure and propose a high-level plan for the next attempt."""
        request = self._request(
            prompt,
            attempt=attempt.attempt,
            system_prompt=REFLECTION_SYSTEM_PROMPT,
            purpose="reflection",
        )
        response = runtime.generate_auxiliary(request, purpose="reflexion")
        reflection = response.text.strip()
        if reflection:
            self.reflections.append(reflection)
            self.reflections = self.reflections[-self.reflection_limit :]
        self._reflected_attempts.add(attempt.attempt)

    def _candidate_request(self, history: Sequence[AttemptRecord]) -> GenerationRequest:
        context, _ = self._require_ready()
        prompt = _vanilla_prompt(self.prompts, context, history)
        if self.reflections:
            memory = "\n\n".join(
                f"{index}. {reflection}"
                for index, reflection in enumerate(self.reflections, start=1)
            )
            block = f"""# Reflections from Previous Failures

Use this episodic verbal memory to avoid repeating earlier failures:

{memory}

"""
            marker = "# Task Description"
            position = prompt.find(marker)
            prompt = (
                prompt[:position] + block + prompt[position:]
                if position >= 0
                else block + prompt
            )
        attempt = history[-1].attempt + 1 if history else 1
        return self._request(prompt, attempt=attempt, purpose="candidate")

    def _request(
        self,
        prompt: str,
        *,
        attempt: int,
        purpose: str,
        system_prompt: str | None = None,
    ) -> GenerationRequest:
        context, _ = self._require_ready()
        config = context.config
        return GenerationRequest(
            prompt=prompt,
            system_prompt=system_prompt,
            seed=config.seed + attempt,
            temperature=config.temperature,
            top_p=config.top_p,
            max_tokens=config.max_tokens,
            metadata={"attempt": attempt, "method": self.name, "purpose": purpose},
        )

    def _require_ready(self) -> tuple[StrategyContext, StrategyRuntime]:
        if self.context is None or self.runtime is None:
            raise RuntimeError("ReflexionStrategy must be initialized before use")
        return self.context, self.runtime


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


# Conventional dotted-import alias used by CLI examples.
Method = ReflexionStrategy
Strategy = ReflexionStrategy
