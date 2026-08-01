"""PACE-Bench adaptation of Tree of Thoughts beam search.

This module is intentionally self-contained and lives in the ignored ``methods/``
workspace.  It follows the official generate/evaluate/select breadth-first pattern,
but replaces LLM value/vote evaluation with the benchmark's Box2D verifier.  Every
generated child is a submission, so a beam of ``b`` parents with ``n`` children
costs ``b * n`` benchmark attempts.
"""

from __future__ import annotations

import inspect
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from pace_bench.core.types import (
    AttemptRecord,
    EvaluationResult,
    GenerationRequest,
    RunMode,
)
from pace_bench.evaluation.config import StrategyContext
from pace_bench.evaluation.prompts import PromptBuilder

try:  # V2 is being introduced in the public evaluator.
    from pace_bench.evaluation.config import (
        CandidateSubmission,
        StrategyRuntime,
        StrategyStep,
    )
except (
    ImportError
):  # Keep this ignored research script importable against the current checkout.

    @dataclass
    class CandidateSubmission:  # type: ignore[no-redef]
        request: GenerationRequest | None = None
        metadata: dict[str, Any] = field(default_factory=dict)

    @dataclass
    class StrategyStep:  # type: ignore[no-redef]
        submissions: Sequence[CandidateSubmission]
        metadata: dict[str, Any] = field(default_factory=dict)

    StrategyRuntime = Any  # type: ignore[misc,assignment]


OFFICIAL_REPOSITORY = "https://github.com/princeton-nlp/tree-of-thought-llm"
OFFICIAL_AUDIT_COMMIT = "8050e67d0e3a0fddc424d7fa5801538722a4c4cc"


def _new(record_type: type[Any], **values: Any) -> Any:
    """Construct a V2 record while tolerating metadata-field naming changes."""

    parameters = inspect.signature(record_type).parameters
    return record_type(
        **{key: value for key, value in values.items() if key in parameters}
    )


class TreeOfThoughtsMethod:
    """Breadth-first code-revision search scored by the physics verifier."""

    name = "tree_of_thoughts"

    def __init__(self, beam_width: int = 3, children_per_parent: int = 2) -> None:
        if beam_width < 1 or children_per_parent < 1:
            raise ValueError("beam_width and children_per_parent must be positive")
        self.beam_width = beam_width
        self.children_per_parent = children_per_parent
        self.context: StrategyContext | None = None
        self.runtime: StrategyRuntime | None = None
        self.prompt_builder = PromptBuilder()
        self.beam: list[AttemptRecord] = []
        self.observed: list[AttemptRecord] = []
        self.round_index = 0

    def initialize(self, context: StrategyContext, runtime: StrategyRuntime) -> None:
        self.context = context
        self.runtime = runtime
        self.beam.clear()
        self.observed.clear()
        self.round_index = 0

    def build_step(
        self, history: Sequence[AttemptRecord], remaining_attempts: int
    ) -> StrategyStep:
        """Build one BFS layer without ever exceeding the remaining budget."""

        self._require_context()
        self.round_index += 1
        if remaining_attempts <= 0:
            raise ValueError("build_step requires a positive remaining_attempts budget")

        if not self.beam:
            request = self._request(self._initial_search_prompt(history), child_index=0)
            submissions = (
                _new(CandidateSubmission, request=request, metadata={"parent": None}),
            )
        else:
            submissions_list: list[CandidateSubmission] = []
            global_best = max(
                self.observed or list(history), key=lambda item: item.score
            )
            for parent in self.beam:
                for child_index in range(self.children_per_parent):
                    if len(submissions_list) >= remaining_attempts:
                        break
                    prompt = self._revision_prompt(parent, global_best)
                    request = self._request(prompt, child_index=child_index)
                    submissions_list.append(
                        _new(
                            CandidateSubmission,
                            request=request,
                            metadata={
                                "parent_attempt": parent.attempt,
                                "child": child_index,
                            },
                        )
                    )
                if len(submissions_list) >= remaining_attempts:
                    break
            submissions = tuple(submissions_list)

        return _new(
            StrategyStep,
            submissions=submissions,
            metadata={
                "round": self.round_index,
                "beam_width": self.beam_width,
                "children_per_parent": self.children_per_parent,
                "verification_cost": len(submissions),
            },
        )

    def observe(self, attempts: Sequence[AttemptRecord]) -> None:
        """Greedily retain the verifier's top ``b`` children for the next layer."""

        batch = list(attempts)
        self.observed.extend(batch)
        # Stable ordering gives deterministic tie-breaking by submission order.
        self.beam = sorted(batch, key=lambda item: item.score, reverse=True)[
            : self.beam_width
        ]

    def snapshot(self) -> dict[str, Any]:
        return {
            "algorithm": "verifier_scored_breadth_first_tree_search",
            "official_repository": OFFICIAL_REPOSITORY,
            "official_audit_commit": OFFICIAL_AUDIT_COMMIT,
            "round": self.round_index,
            "beam_width": self.beam_width,
            "children_per_parent": self.children_per_parent,
            "beam_attempts": [item.attempt for item in self.beam],
            "verified_candidates": len(self.observed),
            "adaptation_note": (
                "Box2D scores replace the official LLM value/vote evaluator; code revisions "
                "replace task-specific textual thoughts."
            ),
        }

    def finalize(self, result: EvaluationResult) -> None:
        """The engine persists :meth:`snapshot`; no duplicate state is added."""

    def _initial_search_prompt(self, history: Sequence[AttemptRecord]) -> str:
        context = self._require_context()
        if context.config.mode != RunMode.ADAPTATION:
            return self.prompt_builder.initial(context.task_context)
        reference = history[0] if history else None
        code = context.reference_code or (reference.code if reference else "")
        feedback = context.reference_feedback or (
            reference.verification.feedback if reference else ""
        )
        return self.prompt_builder.adaptation_revision(
            context.task_context,
            reference_code=code,
            reference_feedback=feedback,
            best_code=code,
            best_feedback=feedback,
            previous_code=code,
            previous_feedback=feedback,
            best_attempt=0,
            previous_attempt=0,
        )

    def _revision_prompt(self, parent: AttemptRecord, best: AttemptRecord) -> str:
        context = self._require_context()
        arguments = dict(
            best_code=best.code,
            best_feedback=best.verification.feedback,
            previous_code=parent.code,
            previous_feedback=parent.verification.feedback,
            best_attempt=best.attempt,
            previous_attempt=parent.attempt,
        )
        if context.config.mode == RunMode.ADAPTATION:
            return self.prompt_builder.adaptation_revision(
                context.task_context,
                reference_code=context.reference_code or "",
                reference_feedback=context.reference_feedback or "",
                **arguments,
            )
        return self.prompt_builder.revision(context.task_context, **arguments)

    def _request(self, prompt: str, *, child_index: int) -> GenerationRequest:
        context = self._require_context()
        seed = context.config.seed + self.round_index * 10_000 + child_index
        return GenerationRequest(
            prompt=prompt,
            seed=seed,
            temperature=context.config.temperature,
            top_p=context.config.top_p,
            max_tokens=context.config.max_tokens,
            metadata={
                "method": self.name,
                "round": self.round_index,
                "child": child_index,
            },
        )

    def _require_context(self) -> StrategyContext:
        if self.context is None:
            raise RuntimeError("initialize() must be called before build_step()")
        return self.context


# Dotted import used by the evaluator:
Strategy = TreeOfThoughtsMethod
Method = TreeOfThoughtsMethod
