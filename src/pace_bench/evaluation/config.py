"""Validated configuration for every evaluation protocol."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from pace_bench.errors import ConfigurationError
from pace_bench.types import (
    AttemptRecord,
    EnvironmentId,
    EvaluationResult,
    GenerationRequest,
    GenerationResult,
    RunMode,
    to_jsonable,
)


@dataclass(frozen=True)
class RunConfig:
    """Model-independent configuration consumed by the evaluation engine."""

    task: str
    mode: RunMode = RunMode.ADAPTATION
    source: EnvironmentId = field(default_factory=lambda: EnvironmentId("Initial"))
    target: EnvironmentId = field(default_factory=lambda: EnvironmentId("Stage-1"))
    provider: str = "mock"
    model: str = "mock"
    strategy: str = "vanilla"
    attempts: int = 20
    max_steps: int | None = None
    generation_retries: int = 2
    seed: int = 0
    temperature: float = 0.7
    max_tokens: int = 8192
    headless: bool = True
    save_gif: bool = False
    output: Path | None = None
    resume: bool = True
    timeout_seconds: float | None = None
    run_index: int = 1
    provider_options: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.attempts < 1:
            raise ConfigurationError("attempts must be at least 1")
        if self.generation_retries < 0:
            raise ConfigurationError("generation_retries cannot be negative")
        if self.max_steps is not None and self.max_steps < 1:
            raise ConfigurationError("max_steps must be positive")
        if self.timeout_seconds is not None and self.timeout_seconds <= 0:
            raise ConfigurationError("timeout_seconds must be positive")
        if self.mode == RunMode.ADAPTATION and self.source.value != "Initial":
            raise ConfigurationError(
                "Canonical adaptation runs must use Initial as the source"
            )
        if self.mode == RunMode.ADAPTATION and self.target.value == "Initial":
            raise ConfigurationError(
                "Adaptation target must be Stage-1 through Stage-4"
            )
        if self.run_index < 1:
            raise ConfigurationError("run_index must be positive")

    def to_dict(self) -> dict[str, Any]:
        return to_jsonable(self)


@dataclass(frozen=True)
class StrategyContext:
    config: RunConfig
    task_context: dict[str, Any]
    reference_code: str | None = None
    reference_feedback: str | None = None


@runtime_checkable
class ModelProvider(Protocol):
    name: str
    model: str

    def generate(self, request: GenerationRequest) -> GenerationResult: ...

    def close(self) -> None: ...


@runtime_checkable
class EvaluationStrategy(Protocol):
    name: str

    def initialize(self, context: StrategyContext) -> None: ...

    def build_initial_request(self) -> GenerationRequest: ...

    def build_revision_request(
        self, history: Sequence[AttemptRecord]
    ) -> GenerationRequest: ...

    def observe(self, attempt: AttemptRecord) -> None: ...

    def finalize(self, result: EvaluationResult) -> None: ...
