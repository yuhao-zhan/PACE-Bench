"""Official-CLI bridge for the PACE-Bench CodeEvolve adaptation.

The benchmark-facing ``Method`` is an in-process population adaptation, allowing the
V2 engine to own and count every Box2D verification.  A separate official-CLI bridge
is retained for implementation audits; it records each official fitness evaluation
to JSONL and deliberately does not re-verify the final best program.

The ``codeevolve`` executable/repository remains an external dependency.  This file
contains only the PACE input/config/evaluator bridge and never vendors official code.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import inspect
import random
from collections.abc import Sequence
from dataclasses import field

from pace_bench.core.types import (
    AttemptRecord,
    EvaluationResult,
    GenerationRequest,
    RunMode,
)
from pace_bench.evaluation.config import StrategyContext
from pace_bench.evaluation.prompts import PromptBuilder

try:
    from pace_bench.evaluation.config import (
        CandidateSubmission,
        StrategyRuntime,
        StrategyStep,
    )
except ImportError:

    @dataclass
    class CandidateSubmission:  # type: ignore[no-redef]
        request: GenerationRequest | None = None
        metadata: dict[str, Any] = field(default_factory=dict)

    @dataclass
    class StrategyStep:  # type: ignore[no-redef]
        submissions: Sequence[CandidateSubmission]
        metadata: dict[str, Any] = field(default_factory=dict)

    StrategyRuntime = Any  # type: ignore[misc,assignment]


OFFICIAL_REPOSITORY = "https://github.com/inter-co/science-codeevolve"
OFFICIAL_AUDIT_COMMIT = "c077959e1ab24b060aaa6d4c563bca2e9cbe8617"
EVOLVE_START = "# EVOLVE-BLOCK-START"
EVOLVE_END = "# EVOLVE-BLOCK-END"
PROMPT_START = "# PROMPT-BLOCK-START"
PROMPT_END = "# PROMPT-BLOCK-END"


@dataclass(frozen=True)
class CodeEvolveConfig:
    """Settings that affect official CodeEvolve search, not benchmark physics."""

    executable: str = "codeevolve"
    num_islands: int = 1
    population_size: int = 8
    exploration_rate: float = 0.3
    migration_interval: int = 10
    migration_rate: float = 0.1
    evaluation_timeout_seconds: int = 300

    def __post_init__(self) -> None:
        if self.num_islands < 1 or self.population_size < 2:
            raise ValueError("num_islands must be >=1 and population_size must be >=2")


@dataclass(frozen=True)
class CodeEvolveRun:
    returncode: int
    attempts: tuple[dict[str, Any], ...]
    best_code: str | None
    output_directory: Path
    stdout: str
    stderr: str


def _new(record_type: type[Any], **values: Any) -> Any:
    parameters = inspect.signature(record_type).parameters
    return record_type(
        **{key: value for key, value in values.items() if key in parameters}
    )


def _solution_with_markers(code: str) -> str:
    if EVOLVE_START in code and EVOLVE_END in code:
        return code
    return f"{EVOLVE_START}\n{code.rstrip()}\n{EVOLVE_END}\n"


def _system_message(task_context: Mapping[str, Any]) -> str:
    return f"""{PROMPT_START}
You are evolving a Python program for this PACE-Bench physics task.

Task:
{task_context.get("task_description", "")}

Success criteria:
{task_context.get("success_criteria", "")}

Available primitives:
{task_context.get("primitives_api", "")}
{PROMPT_END}
"""


def _config_dict(
    *,
    task_context: Mapping[str, Any],
    model: str,
    attempt_budget: int,
    seed: int,
    settings: CodeEvolveConfig,
    temperature: float = 0.7,
    top_p: float = 0.95,
    max_tokens: int = 65_536,
) -> dict[str, Any]:
    """Create a config matching the audited official CLI schema.

    Each island evaluates one generated child per epoch.  Consequently
    ``num_epochs * num_islands`` is capped by the remaining attempt budget.
    """

    epochs = attempt_budget // settings.num_islands
    if epochs < 1:
        raise ValueError(
            "remaining attempt budget is smaller than the configured island count"
        )
    ensemble = [
        {
            "model_name": model,
            "temp": temperature,
            "top_p": top_p,
            "max_tokens": max_tokens,
            "weight": 1,
        }
    ]
    return {
        "SEED": seed,
        "CODEBASE_PATH": ".",
        "EVAL_FILE_NAME": "evaluate.py",
        "INIT_FILE_DATA": {"filename": "solution.py", "language": "python"},
        "SYS_MSG": _system_message(task_context),
        "BUDGET_CONFIG": {
            "eval_timeout": settings.evaluation_timeout_seconds,
            "max_mem_bytes": 2 * 1024**3,
            "resource_check_interval_s": 0.1,
        },
        "ENSEMBLE": ensemble,
        "SAMPLER_AUX_LM": ensemble[0],
        "EVOLVE_CONFIG": {
            "num_epochs": epochs,
            "num_islands": settings.num_islands,
            "init_pop": settings.population_size,
            "max_size": settings.population_size,
            "migration": {
                "topology": "directed_ring",
                "interval": settings.migration_interval,
                "rate": settings.migration_rate,
            },
            "selection": {
                "policy": "tournament",
                "kwargs": {"tournament_size": min(3, settings.population_size)},
            },
            "num_inspirations": 2,
            "exploration_rate": settings.exploration_rate,
            "fitness_key": "fitness",
            "ckpt": max(1, min(10, epochs)),
            "early_stopping_rounds": None,
            "meta_prompting": True,
            "evolve_start_marker": EVOLVE_START,
            "evolve_end_marker": EVOLVE_END,
            "mp_start_marker": PROMPT_START,
            "mp_end_marker": PROMPT_END,
        },
    }


_EVALUATOR_SOURCE = r'''"""Generated PACE-Bench fitness adapter for CodeEvolve."""
import json
import os
import sys
import time
from pathlib import Path

from pace_bench.core.types import EnvironmentId
from pace_bench.evaluation.config import RunConfig
from pace_bench.evaluation.verification.verifier import PhysicsVerifier
from pace_bench.tasks.registry import get_registry, max_steps_for_task


def main():
    code_path = Path(sys.argv[1])
    result_path = Path(sys.argv[2])
    task_selector = os.environ["PACE_CODEEVOLVE_TASK"]
    target_name = os.environ["PACE_CODEEVOLVE_TARGET"]
    ledger_path = Path(os.environ["PACE_CODEEVOLVE_LEDGER"])
    registry = get_registry()
    task = registry.resolve(task_selector)
    environment = next(
        item for item in registry.environments(task) if str(item.environment_id) == target_name
    )
    max_steps = int(os.environ.get("PACE_CODEEVOLVE_MAX_STEPS") or max_steps_for_task(task))
    code = code_path.read_text(encoding="utf-8")
    verifier = PhysicsVerifier(
        task,
        environment,
        max_steps=max_steps,
        headless=True,
        save_gif=False,
        registry=registry,
    )
    started = time.time()
    try:
        verification = verifier.verify(code, attempt=0)
    finally:
        verifier.close()
    record = {
        "code": code,
        "success": verification.success,
        "score": verification.score,
        "feedback": verification.feedback,
        "metrics": verification.metrics,
        "error": verification.error,
        "duration_seconds": verification.duration_seconds,
        "timestamp": started,
    }
    with ledger_path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False) + "\n")
    result_path.write_text(
        json.dumps({"fitness": float(verification.score), "success": verification.success}),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
'''


def _write_yaml(path: Path, data: Mapping[str, Any]) -> None:
    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError("CodeEvolve requires PyYAML") from exc
    path.write_text(yaml.safe_dump(dict(data), sort_keys=False), encoding="utf-8")


def _read_ledger(path: Path) -> tuple[dict[str, Any], ...]:
    if not path.exists():
        return ()
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), 1
    ):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"invalid CodeEvolve ledger line {line_number}: {exc}"
            ) from exc
    return tuple(records)


def _best_code(
    output_directory: Path, attempts: tuple[dict[str, Any], ...]
) -> str | None:
    candidates = list(output_directory.glob("**/best_sol.py"))
    if candidates:
        return max(candidates, key=lambda path: path.stat().st_mtime).read_text(
            encoding="utf-8"
        )
    return (
        max(attempts, key=lambda item: float(item.get("score", 0.0))).get("code")
        if attempts
        else None
    )


def run_official_codeevolve(
    *,
    task: str,
    target: str,
    task_context: Mapping[str, Any],
    initial_code: str,
    model: str,
    attempt_budget: int,
    seed: int,
    output_directory: Path,
    settings: CodeEvolveConfig | None = None,
    api_base: str | None = None,
    api_key: str | None = None,
    max_steps: int | None = None,
    temperature: float = 0.7,
    top_p: float = 0.95,
    max_tokens: int = 65_536,
) -> CodeEvolveRun:
    """Run one official island population and return its exact fitness ledger."""

    settings = settings or CodeEvolveConfig()
    output_directory.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="pace_codeevolve_") as temporary:
        input_directory = Path(temporary) / "input"
        input_directory.mkdir()
        (input_directory / "solution.py").write_text(
            _solution_with_markers(initial_code), encoding="utf-8"
        )
        (input_directory / "evaluate.py").write_text(
            _EVALUATOR_SOURCE, encoding="utf-8"
        )
        config_path = Path(temporary) / "config.yaml"
        ledger_path = output_directory / "attempts.jsonl"
        _write_yaml(
            config_path,
            _config_dict(
                task_context=task_context,
                model=model,
                attempt_budget=attempt_budget,
                seed=seed,
                settings=settings,
                temperature=temperature,
                top_p=top_p,
                max_tokens=max_tokens,
            ),
        )
        environment = os.environ.copy()
        environment.update(
            {
                "PACE_CODEEVOLVE_TASK": task,
                "PACE_CODEEVOLVE_TARGET": target,
                "PACE_CODEEVOLVE_LEDGER": str(ledger_path.resolve()),
                "API_KEY": api_key or os.environ.get("OPENAI_API_KEY", "dummy"),
                "API_BASE": api_base or os.environ.get("OPENAI_BASE_URL", ""),
            }
        )
        if max_steps is not None:
            environment["PACE_CODEEVOLVE_MAX_STEPS"] = str(max_steps)
        completed = subprocess.run(
            [
                settings.executable,
                f"--inpt_dir={input_directory}",
                f"--cfg_path={config_path}",
                f"--out_dir={output_directory}",
                "--load_ckpt=0",
                "--y",
            ],
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
    attempts = _read_ledger(ledger_path)
    if len(attempts) > attempt_budget:
        raise RuntimeError(
            f"CodeEvolve exceeded its verifier budget: {len(attempts)} > {attempt_budget}"
        )
    return CodeEvolveRun(
        returncode=completed.returncode,
        attempts=attempts,
        best_code=_best_code(output_directory, attempts),
        output_directory=output_directory,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


class CodeEvolveMethod:
    """In-process population adaptation with engine-owned verification.

    The standalone ``run_official_codeevolve`` bridge above is retained for direct
    official-CLI audits.  The benchmark loader uses this in-process implementation
    so each generated child passes through the V2 engine exactly once.
    """

    name = "codeevolve"

    def __init__(self, **settings: Any) -> None:
        self.settings = CodeEvolveConfig(**settings)
        self.context: StrategyContext | None = None
        self.runtime: StrategyRuntime | None = None
        self.last_run: CodeEvolveRun | None = None
        self.prompt_builder = PromptBuilder()
        self.population: list[AttemptRecord] = []
        self.generation = 0
        self.lineage: dict[int, dict[str, Any]] = {}

    def initialize(self, context: StrategyContext, runtime: StrategyRuntime) -> None:
        self.context = context
        self.runtime = runtime
        self.population.clear()
        self.generation = 0
        self.lineage.clear()

    def build_step(
        self, history: Sequence[AttemptRecord], remaining_attempts: int
    ) -> StrategyStep:
        count = min(self.settings.num_islands, remaining_attempts)
        if count <= 0:
            raise ValueError("build_step requires a positive remaining_attempts budget")
        self.generation += 1
        submissions = []
        for island in range(count):
            parent, inspirations = self._select_family(history, island)
            prompt = self._evolution_prompt(parent, inspirations, history)
            config = self._require_context().config
            request = GenerationRequest(
                prompt=prompt,
                seed=config.seed + self.generation * 10_000 + island,
                temperature=config.temperature,
                top_p=config.top_p,
                max_tokens=config.max_tokens,
                metadata={
                    "method": self.name,
                    "generation": self.generation,
                    "island": island,
                    "parent_attempt": parent.attempt if parent else None,
                    "inspiration_attempts": [item.attempt for item in inspirations],
                },
            )
            submissions.append(
                _new(CandidateSubmission, request=request, metadata=request.metadata)
            )
        return _new(
            StrategyStep,
            submissions=tuple(submissions),
            metadata={
                "generation": self.generation,
                "verification_cost": len(submissions),
            },
        )

    def observe(self, attempts: Sequence[AttemptRecord]) -> None:
        for attempt in attempts:
            metadata = attempt.request.metadata if attempt.request else {}
            self.lineage[attempt.attempt] = {
                "generation": metadata.get("generation"),
                "island": metadata.get("island"),
                "parent_attempt": metadata.get("parent_attempt"),
                "inspiration_attempts": metadata.get("inspiration_attempts", []),
                "score": attempt.score,
            }
        self.population.extend(attempts)
        self.population = sorted(
            self.population, key=lambda item: item.score, reverse=True
        )[: self.settings.population_size]

    def snapshot(self) -> dict[str, Any]:
        return {
            "official_repository": OFFICIAL_REPOSITORY,
            "official_audit_commit": OFFICIAL_AUDIT_COMMIT,
            "official_cli": self.settings.executable,
            "num_islands": self.settings.num_islands,
            "population_size": self.settings.population_size,
            "generations": self.generation,
            "population_attempts": [item.attempt for item in self.population],
            "lineage": self.lineage,
            "official_equivalence": False,
            "adaptation_note": (
                "The evaluator uses an in-process population so the V2 engine owns and counts "
                "each Box2D fitness call. Parent/inspiration/island semantics are retained, but "
                "official subprocess scheduling, prompt co-evolution, and migration are not exact."
            ),
        }

    def finalize(self, result: EvaluationResult) -> None:
        """The engine persists :meth:`snapshot`; no duplicate state is added."""

    def _select_family(
        self, history: Sequence[AttemptRecord], island: int
    ) -> tuple[AttemptRecord | None, list[AttemptRecord]]:
        candidates = self.population or list(history)
        if not candidates:
            return None, []
        rng = random.Random(
            self._require_context().config.seed + self.generation * 10_000 + island
        )
        tournament = rng.sample(candidates, k=min(3, len(candidates)))
        parent = max(tournament, key=lambda item: item.score)
        inspiration_pool = [
            item for item in candidates if item.attempt != parent.attempt
        ]
        inspirations = rng.sample(inspiration_pool, k=min(2, len(inspiration_pool)))
        return parent, inspirations

    def _evolution_prompt(
        self,
        parent: AttemptRecord | None,
        inspirations: Sequence[AttemptRecord],
        history: Sequence[AttemptRecord],
    ) -> str:
        context = self._require_context()
        if parent is None:
            base = self.prompt_builder.initial(context.task_context)
        else:
            best = max(self.population or list(history), key=lambda item: item.score)
            arguments = dict(
                best_code=best.code,
                best_feedback=best.verification.feedback,
                previous_code=parent.code,
                previous_feedback=parent.verification.feedback,
                best_attempt=best.attempt,
                previous_attempt=parent.attempt,
            )
            if context.config.mode == RunMode.ADAPTATION:
                base = self.prompt_builder.adaptation_revision(
                    context.task_context,
                    reference_code=context.reference_code or history[0].code,
                    reference_feedback=context.reference_feedback
                    or history[0].verification.feedback,
                    **arguments,
                )
            else:
                base = self.prompt_builder.revision(context.task_context, **arguments)
        inspiration_text = "\n\n".join(
            f"Inspiration {index + 1} (score {item.score:.3f}):\n```python\n{item.code}\n```"
            for index, item in enumerate(inspirations)
        )
        return (
            base
            + "\n\n# Evolution operator\nCreate a materially different child by mutating or "
            "crossing over the parent and inspirations. Preserve only mechanisms supported "
            "by verifier evidence; output one complete candidate.\n\n"
            + inspiration_text
        )

    def _require_context(self) -> StrategyContext:
        if self.context is None:
            raise RuntimeError("initialize() must be called before use")
        return self.context


Strategy = CodeEvolveMethod
Method = CodeEvolveMethod
