"""One reusable loop for from-scratch, adaptation, and reference protocols."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Protocol

from pace_bench.errors import ProviderError
from pace_bench.types import (
    AttemptRecord,
    EvaluationResult,
    GenerationRequest,
    GenerationResult,
    RunMode,
    VerificationResult,
)
from pace_bench.evaluation.config import RunConfig
from pace_bench.evaluation.method import VanillaMethod, load_method
from pace_bench.evaluation.prompts import PromptBuilder
from pace_bench.evaluation.config import (
    EvaluationStrategy,
    ModelProvider,
    StrategyContext,
)
from pace_bench.evaluation.providers import load_provider
from pace_bench.evaluation.verification.safety import (
    extract_code,
    validate_solver_output,
)
from pace_bench.evaluation.verification.verifier import PhysicsVerifier
from pace_bench.tasks.registry import get_reference_solution
from pace_bench.tasks.registry import TaskRegistry, get_registry
from pace_bench.tasks.registry import max_steps_for_task
from pace_bench.tasks.registry import EnvironmentSpec, TaskSpec


class CandidateVerifier(Protocol):
    def verify(self, code: str, attempt: int) -> VerificationResult: ...

    def close(self) -> None: ...


VerifierFactory = Callable[[TaskSpec, EnvironmentSpec, RunConfig], CandidateVerifier]


class EvaluationEngine:
    """Execute exactly one task/environment protocol with explicit dependencies."""

    def __init__(
        self,
        config: RunConfig,
        *,
        registry: TaskRegistry | None = None,
        provider: ModelProvider | None = None,
        strategy: EvaluationStrategy | None = None,
        verifier_factory: VerifierFactory | None = None,
    ) -> None:
        self.config = config
        self.registry = registry or get_registry()
        self.provider = provider or load_provider(
            config.provider, model=config.model, options=config.provider_options
        )
        if strategy is not None:
            self.strategy = strategy
        elif config.strategy in {"iterative", "vanilla"}:
            self.strategy = VanillaMethod(PromptBuilder(self.registry))
        else:
            self.strategy = load_method(config.strategy)
        self.verifier_factory = verifier_factory or self._physics_verifier_factory

    def run(self) -> EvaluationResult:
        started_wall = time.time()
        started = time.perf_counter()
        task = self.registry.resolve(self.config.task)
        environments = {
            str(item.environment_id): item for item in self.registry.environments(task)
        }
        target = environments[str(self.config.target)]
        task_context = PromptBuilder(self.registry).load_task_context(task, target)
        verifier = self.verifier_factory(task, target, self.config)
        history: list[AttemptRecord] = []
        stop_reason = "budget_exhausted"
        invalid_error: str | None = None
        try:
            reference_code = None
            reference_feedback = None
            if self.config.mode in {
                RunMode.ADAPTATION,
                RunMode.REFERENCE,
                RunMode.SINGLE,
            }:
                reference_environment = (
                    self.config.source
                    if self.config.mode == RunMode.ADAPTATION
                    else self.config.target
                )
                reference_code = get_reference_solution(task, reference_environment)
            if self.config.mode == RunMode.ADAPTATION:
                reference_attempt = self._verify_attempt(
                    verifier,
                    attempt=0,
                    code=reference_code or "",
                    phase="reference",
                )
                history.append(reference_attempt)
                reference_feedback = reference_attempt.verification.feedback
                if reference_attempt.success:
                    stop_reason = "reference_passes_target"
            self.strategy.initialize(
                StrategyContext(
                    config=self.config,
                    task_context=task_context,
                    reference_code=reference_code,
                    reference_feedback=reference_feedback,
                )
            )
            for attempt_number in self._attempt_numbers(stop_reason):
                request = (
                    self.strategy.build_initial_request()
                    if not history
                    else self.strategy.build_revision_request(history)
                )
                generation, code, invalid_error = self._generate_valid_candidate(
                    request, attempt_number
                )
                if generation is None or code is None:
                    stop_reason = "invalid_solver_output"
                    break
                attempt = self._verify_attempt(
                    verifier,
                    attempt=attempt_number,
                    code=code,
                    phase="initial" if not history else "revision",
                    request=request,
                    generation=generation,
                )
                history.append(attempt)
                self.strategy.observe(attempt)
                if attempt.success:
                    stop_reason = "success"
                    break
            if self.config.mode in {RunMode.REFERENCE, RunMode.SINGLE} and not history:
                direct = self._verify_attempt(
                    verifier,
                    attempt=0,
                    code=reference_code or "",
                    phase="reference",
                )
                history.append(direct)
                stop_reason = "success" if direct.success else "reference_failed"
        finally:
            verifier.close()
            self.provider.close()

        best = max(history, key=lambda item: item.score) if history else None
        result = EvaluationResult(
            task_id=task.name,
            task_path=task.full_name,
            mode=self.config.mode.value,
            provider=self.config.provider,
            model=self.config.model,
            strategy=getattr(self.strategy, "name", self.config.strategy),
            attempts=history,
            source_environment=(
                str(self.config.source)
                if self.config.mode == RunMode.ADAPTATION
                else None
            ),
            target_environment=str(self.config.target),
            environment_pair=(
                f"{self.config.source}_to_{self.config.target}"
                if self.config.mode == RunMode.ADAPTATION
                else None
            ),
            success=any(attempt.success for attempt in history),
            best_score=best.score if best else 0.0,
            best_attempt=best.attempt if best else None,
            stop_reason=stop_reason,
            started_at=started_wall,
            finished_at=time.time(),
            total_time_seconds=time.perf_counter() - started,
            config=self.config.to_dict(),
            metadata={"invalid_solver_error": invalid_error} if invalid_error else {},
        )
        self.strategy.finalize(result)
        return result

    def _attempt_numbers(self, stop_reason: str) -> range:
        if stop_reason == "reference_passes_target":
            return range(0)
        if self.config.mode == RunMode.FROM_SCRATCH:
            return range(1, self.config.attempts + 1)
        if self.config.mode == RunMode.ADAPTATION:
            return range(1, self.config.attempts + 1)
        return range(0)

    def _generate_valid_candidate(
        self, request: GenerationRequest, attempt: int
    ) -> tuple[GenerationResult | None, str | None, str | None]:
        last_error = "provider produced no candidate"
        for retry in range(self.config.generation_retries + 1):
            retry_request = replace(
                request,
                seed=self.config.seed + attempt * 1000 + retry,
                metadata={**request.metadata, "retry": retry},
            )
            try:
                generation = self.provider.generate(retry_request)
            except ProviderError as exc:
                last_error = str(exc)
                continue
            code = (
                generation.code
                if generation.code is not None
                else extract_code(generation.text)
            )
            valid, reason = validate_solver_output(generation.text, code)
            if valid:
                generation.code = code
                return generation, code, None
            last_error = reason
        return None, None, last_error

    @staticmethod
    def _verify_attempt(
        verifier: CandidateVerifier,
        *,
        attempt: int,
        code: str,
        phase: str,
        request: GenerationRequest | None = None,
        generation: GenerationResult | None = None,
    ) -> AttemptRecord:
        return AttemptRecord(
            attempt=attempt,
            code=code,
            request=request,
            generation=generation,
            verification=verifier.verify(code, attempt),
            timestamp=time.time(),
            phase=phase,
        )

    def _physics_verifier_factory(
        self, task: TaskSpec, environment: EnvironmentSpec, config: RunConfig
    ) -> PhysicsVerifier:
        max_steps = config.max_steps or max_steps_for_task(task)
        artifact_directory = None
        if config.output is not None:
            artifact_directory = (
                Path(config.output)
                / "artifacts"
                / task.name
                / str(environment.environment_id)
            )
        return PhysicsVerifier(
            task,
            environment,
            max_steps=max_steps,
            headless=config.headless,
            save_gif=config.save_gif,
            artifact_directory=artifact_directory,
            registry=self.registry,
        )
