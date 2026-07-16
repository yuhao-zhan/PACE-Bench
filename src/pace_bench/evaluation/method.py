"""Vanilla Previous-One + Best method and external-method loading."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from pace_bench.errors import ConfigurationError
from pace_bench.evaluation.prompts import PromptBuilder
from pace_bench.evaluation.config import EvaluationStrategy, StrategyContext
from pace_bench.evaluation.providers import load_object
from pace_bench.types import AttemptRecord, EvaluationResult, GenerationRequest, RunMode


@dataclass(frozen=True)
class PreviousAndBest:
    previous: AttemptRecord
    best: AttemptRecord

    @property
    def same_attempt(self) -> bool:
        return self.previous.attempt == self.best.attempt


def select_previous_and_best(history: Sequence[AttemptRecord]) -> PreviousAndBest:
    """Select the newest attempt and earliest highest-scoring attempt."""

    if not history:
        raise ValueError("Cannot select from an empty attempt history")
    return PreviousAndBest(
        previous=history[-1], best=max(history, key=lambda item: item.score)
    )


class VanillaMethod:
    """The only bundled method: Previous-One + Best iterative refinement."""

    name = "vanilla"

    def __init__(self, prompt_builder: PromptBuilder | None = None) -> None:
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.context: StrategyContext | None = None

    def initialize(self, context: StrategyContext) -> None:
        self.context = context

    def build_initial_request(self) -> GenerationRequest:
        context = self._require_context()
        return self._request(
            self.prompt_builder.initial(context.task_context), attempt=1
        )

    def build_revision_request(
        self, history: Sequence[AttemptRecord]
    ) -> GenerationRequest:
        context = self._require_context()
        selected = select_previous_and_best(history)
        if context.config.mode == RunMode.ADAPTATION:
            reference = history[0]
            prompt = self.prompt_builder.adaptation_revision(
                context.task_context,
                reference_code=context.reference_code or reference.code,
                reference_feedback=context.reference_feedback
                or reference.verification.feedback,
                best_code=selected.best.code,
                best_feedback=selected.best.verification.feedback,
                previous_code=selected.previous.code,
                previous_feedback=selected.previous.verification.feedback,
                best_attempt=selected.best.attempt,
                previous_attempt=selected.previous.attempt,
            )
        else:
            prompt = self.prompt_builder.revision(
                context.task_context,
                best_code=selected.best.code,
                best_feedback=selected.best.verification.feedback,
                previous_code=selected.previous.code,
                previous_feedback=selected.previous.verification.feedback,
                best_attempt=selected.best.attempt,
                previous_attempt=selected.previous.attempt,
            )
        return self._request(prompt, attempt=selected.previous.attempt + 1)

    def observe(self, attempt: AttemptRecord) -> None:
        """Vanilla keeps no hidden state outside serialized attempt history."""

    def finalize(self, result: EvaluationResult) -> None:
        """Vanilla has no auxiliary finalization step."""

    def _request(self, prompt: str, *, attempt: int) -> GenerationRequest:
        context = self._require_context()
        config = context.config
        return GenerationRequest(
            prompt=prompt,
            seed=config.seed + attempt,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            metadata={"attempt": attempt, "method": self.name},
        )

    def _require_context(self) -> StrategyContext:
        if self.context is None:
            raise RuntimeError("Method must be initialized before building requests")
        return self.context


def load_method(name: str) -> EvaluationStrategy:
    """Load vanilla or a user-owned dotted-import implementation."""

    if name in {"vanilla", "iterative"}:
        return VanillaMethod()
    method = load_object(name)()
    required = (
        "initialize",
        "build_initial_request",
        "build_revision_request",
        "observe",
        "finalize",
    )
    missing = [
        attribute
        for attribute in required
        if not callable(getattr(method, attribute, None))
    ]
    if missing:
        raise ConfigurationError(
            f"Method {name!r} is missing required callables: {', '.join(missing)}"
        )
    return method
