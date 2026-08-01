"""PACE-Bench adaptation of Self-Refine with separate feedback/refine calls.

Each benchmark interaction verifies only the final product of an unverified
self-refinement inner loop.  The same runtime/backbone supplies the initial
candidate, self-feedback, and refined candidate; no extra model is introduced.
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
from pace_bench.evaluation.verification.safety import extract_code


CORRECT_PHRASE = "it is correct"


class SelfRefineStrategy:
    """Run at most ``inner_steps`` unverified feedback/refine cycles per attempt."""

    name = "self_refine"

    def __init__(self, *, inner_steps: int = 5) -> None:
        if inner_steps < 1:
            raise ValueError("inner_steps must be positive")
        self.inner_steps = inner_steps
        self.context: StrategyContext | None = None
        self.runtime: StrategyRuntime | None = None
        self.prompts = PromptBuilder()
        self.inner_calls = 0
        self.last_feedback = ""

    def initialize(self, context: StrategyContext, runtime: StrategyRuntime) -> None:
        self.context = context
        self.runtime = runtime

    def build_step(
        self, history: Sequence[AttemptRecord], remaining_attempts: int
    ) -> StrategyStep:
        context, runtime = self._require_ready()
        attempt = history[-1].attempt + 1 if history else 1
        current_request = self._request(
            _vanilla_prompt(self.prompts, context, history),
            attempt=attempt,
            purpose="initial-candidate",
        )
        current = runtime.generate_prepared_candidate(
            current_request, label="self-refine-initial"
        )

        for inner_index in range(1, self.inner_steps + 1):
            code = current.code or extract_code(current.text)
            if not code:
                break
            feedback_request = self._request(
                _feedback_prompt(context.task_context, code),
                attempt=attempt,
                purpose=f"self-feedback-{inner_index}",
            )
            feedback_result = runtime.generate_auxiliary(
                feedback_request, purpose="self-refine-feedback"
            )
            feedback = feedback_result.text.strip()
            self.last_feedback = feedback
            self.inner_calls += 1
            if _says_correct(feedback):
                break

            current_request = self._request(
                _refine_prompt(context.task_context, code, feedback),
                attempt=attempt,
                purpose=f"refine-{inner_index}",
            )
            refined = runtime.generate_prepared_candidate(
                current_request, label="self-refine-revision"
            )
            if not (refined.code or extract_code(refined.text)):
                break
            current = refined

        return StrategyStep.one(
            current_request,
            generation=current,
            label="self-refine-final",
            metadata={"inner_steps": self.inner_steps},
        )

    def observe(self, attempts: Sequence[AttemptRecord]) -> None:
        """The external verifier is intentionally observed only after the inner loop."""

    def snapshot(self) -> dict[str, Any]:
        return {
            "inner_steps": self.inner_steps,
            "self_feedback_calls": self.inner_calls,
            "last_feedback_available": bool(self.last_feedback),
        }

    def finalize(self, result: EvaluationResult) -> None:
        """The engine persists :meth:`snapshot`; no duplicate state is added."""

    def _request(self, prompt: str, *, attempt: int, purpose: str) -> GenerationRequest:
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
            raise RuntimeError("SelfRefineStrategy must be initialized before use")
        return self.context, self.runtime


def _feedback_prompt(task: dict[str, Any], code: str) -> str:
    return f"""# Task Description

{task['task_description']}

# Success Criteria

{task['success_criteria']}

# Current Code

```python
{code}
```

Act as the feedback provider in Self-Refine. Review semantically complete blocks
and identify concrete physical, algorithmic, constraint, or code errors. Give
feedback only; do not write replacement code. If no change is needed, end with
the exact standalone sentence `It is correct.`
"""


def _refine_prompt(task: dict[str, Any], code: str, feedback: str) -> str:
    return f"""# Task Description

{task['task_description']}

# Success Criteria

{task['success_criteria']}

# Available Primitives API

{task['primitives_api']}

# Current Code

```python
{code}
```

# Self-Feedback

{feedback}

Act as the refiner in Self-Refine. Apply the feedback and return complete Python
code defining `build_agent(sandbox)` and, when needed,
`agent_action(sandbox, agent_body, step_count)`."""


def _says_correct(feedback: str) -> bool:
    lower = feedback.lower()
    if CORRECT_PHRASE not in lower:
        return False
    contradictory_markers = (
        "```python",
        "def build_agent",
        "corrected code",
        "needs to",
    )
    return not any(marker in lower for marker in contradictory_markers)


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


Method = SelfRefineStrategy
Strategy = SelfRefineStrategy
