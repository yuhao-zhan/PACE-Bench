"""Compact result persistence, backward-compatible decoding, and aggregation."""

from __future__ import annotations

import json
import os
import re
import tempfile
from hashlib import sha256
from collections import Counter, defaultdict
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from pace_bench.errors import ResultSchemaError
from pace_bench.evaluation.config import RunConfig
from pace_bench.paths import ensure_output_path
from pace_bench.tasks.registry import TaskSpec
from pace_bench.types import (
    RESULT_SCHEMA_VERSION,
    AttemptRecord,
    EvaluationResult,
    GenerationRequest,
    GenerationResult,
    VerificationResult,
    to_jsonable,
)

FULL_RESULT_SCHEMA_VERSION = "1.0"


def decode_result(data: dict[str, Any]) -> EvaluationResult:
    if "schema_version" not in data:
        data = migrate_legacy_result(data)
    version = str(data.get("schema_version"))
    if version == RESULT_SCHEMA_VERSION:
        return _decode_compact_result(data)
    if version != FULL_RESULT_SCHEMA_VERSION:
        raise ResultSchemaError(f"Unsupported result schema {version!r}.")
    fields = dict(data)
    fields["attempts"] = [_decode_attempt(item) for item in data.get("attempts", [])]
    try:
        return EvaluationResult(**fields)
    except TypeError as exc:
        raise ResultSchemaError(f"Malformed evaluation result: {exc}") from exc


def _decode_compact_result(data: dict[str, Any]) -> EvaluationResult:
    """Restore the public in-memory records from compact schema 2.x JSON."""

    attempts = [_decode_compact_attempt(item) for item in data.get("attempts", [])]
    config = dict(data.get("config") or {})
    if "run_index" in data:
        config.setdefault("run_index", data["run_index"])
    if "attempt_budget" in data:
        config.setdefault("attempts", data["attempt_budget"])
    fields = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "task_id": str(data.get("task_id") or "unknown"),
        "task_path": str(data.get("task_path") or data.get("task_id") or "unknown"),
        "mode": str(data.get("mode") or "adaptation"),
        "provider": str(data.get("provider") or "unknown"),
        "model": str(data.get("model") or "unknown"),
        "strategy": str(data.get("strategy") or data.get("method") or "unknown"),
        "attempts": attempts,
        "source_environment": data.get("source_environment"),
        "target_environment": data.get("target_environment"),
        "environment_pair": data.get("environment_pair"),
        "success": bool(data.get("success", False)),
        "best_score": float(data.get("best_score", 0.0) or 0.0),
        "best_attempt": data.get("best_attempt"),
        "stop_reason": str(data.get("stop_reason") or "unknown"),
        "started_at": data.get("started_at"),
        "finished_at": data.get("finished_at"),
        "total_time_seconds": float(data.get("total_time_seconds", 0.0) or 0.0),
        "config": config,
        "metadata": dict(data.get("metadata") or {}),
    }
    try:
        return EvaluationResult(**fields)
    except (TypeError, ValueError) as exc:
        raise ResultSchemaError(f"Malformed compact evaluation result: {exc}") from exc


def _decode_compact_attempt(data: dict[str, Any]) -> AttemptRecord:
    outcome = dict(data.get("outcome") or {})
    constraints = dict(data.get("constraints") or {})
    metrics = {
        "failed": not bool(data.get("success", False)),
        "failure_reason": outcome.get("failure_reason"),
        "error_type": outcome.get("error_type"),
        "error_stage": outcome.get("error_stage"),
        "error_message": outcome.get("error_message"),
        "step_count": data.get("step_count"),
        "constraint_violations": list(constraints.get("violations") or []),
        **dict(data.get("physics") or {}),
    }
    generation_data = data.get("generation")
    generation = None
    if isinstance(generation_data, dict):
        generation = GenerationResult(
            text="",
            code=str(data.get("code") or ""),
            token_usage=dict(generation_data.get("token_usage") or {}),
            model=generation_data.get("model"),
            latency_seconds=generation_data.get("latency_seconds"),
        )
    return AttemptRecord(
        attempt=int(data.get("attempt", 0)),
        code=str(data.get("code") or ""),
        request=None,
        generation=generation,
        verification=VerificationResult(
            success=bool(data.get("success", False)),
            score=float(data.get("score", 0.0) or 0.0),
            metrics={key: value for key, value in metrics.items() if value is not None},
            feedback="",
            error=outcome.get("error"),
            artifact_paths=list(data.get("artifacts") or []),
            duration_seconds=data.get("verification_seconds"),
        ),
        timestamp=data.get("timestamp"),
        phase=str(data.get("phase") or "revision"),
    )


def _decode_attempt(data: dict[str, Any]) -> AttemptRecord:
    request = data.get("request")
    generation = data.get("generation")
    return AttemptRecord(
        attempt=int(data.get("attempt", 0)),
        code=str(data.get("code") or ""),
        request=GenerationRequest(**request) if request else None,
        generation=GenerationResult(**generation) if generation else None,
        verification=VerificationResult(**(data.get("verification") or {})),
        timestamp=data.get("timestamp"),
        phase=str(data.get("phase") or "revision"),
    )


def migrate_legacy_result(data: dict[str, Any]) -> dict[str, Any]:
    """Convert old unversioned evaluator JSON while retaining unknown fields."""

    history = data.get("history") or data.get("iteration_history") or []
    attempts: list[dict[str, Any]] = []
    for index, item in enumerate(history):
        number = int(item.get("iteration", index))
        prompt = item.get("prompt")
        raw_output = item.get("raw_llm_output")
        attempts.append(
            {
                "attempt": number,
                "code": str(item.get("code") or ""),
                "request": {"prompt": prompt} if prompt is not None else None,
                "generation": {
                    "text": str(raw_output or item.get("code") or ""),
                    "code": str(item.get("code") or ""),
                    "token_usage": dict(item.get("token_usage") or {}),
                }
                if prompt is not None or raw_output is not None
                else None,
                "verification": {
                    "success": bool(item.get("success", False)),
                    "score": float(item.get("score", 0.0) or 0.0),
                    "metrics": dict(item.get("metrics") or {}),
                    "feedback": str(item.get("feedback") or ""),
                    "error": item.get("error"),
                    "artifact_paths": [item["gif_path"]]
                    if item.get("gif_path")
                    else [],
                },
                "timestamp": item.get("timestamp"),
                "phase": str(
                    item.get("phase") or ("reference" if number == 0 else "revision")
                ),
            }
        )
    best_index = (
        max(
            range(len(attempts)),
            key=lambda index: attempts[index]["verification"]["score"],
        )
        if attempts
        else None
    )
    task_name = str(data.get("task_name") or data.get("task") or "unknown")
    pair = data.get("environment_pair") or data.get("mutated_task_name")
    source = data.get("source_environment")
    target = data.get("target_environment")
    if pair and "_to_" in str(pair):
        source, target = str(pair).split("_to_", 1)
    known = {
        "task_name",
        "task",
        "method",
        "base_method",
        "history",
        "iteration_history",
        "success",
        "best_score",
        "iterations",
        "start_timestamp",
        "total_time_seconds",
        "stop_reason",
        "environment_pair",
        "mutated_task_name",
        "source_environment",
        "target_environment",
        "model_type",
        "model_name",
    }
    return {
        "schema_version": FULL_RESULT_SCHEMA_VERSION,
        "task_id": task_name.split("/")[-1],
        "task_path": task_name,
        "mode": "adaptation" if pair else "from-scratch",
        "provider": str(data.get("model_type") or "legacy"),
        "model": str(data.get("model_name") or "unknown"),
        "strategy": str(data.get("method") or data.get("base_method") or "legacy"),
        "attempts": attempts,
        "source_environment": source,
        "target_environment": target,
        "environment_pair": pair,
        "success": bool(data.get("success", False)),
        "best_score": float(data.get("best_score", 0.0) or 0.0),
        "best_attempt": attempts[best_index]["attempt"]
        if best_index is not None
        else None,
        "stop_reason": str(data.get("stop_reason") or "legacy_import"),
        "started_at": data.get("start_timestamp"),
        "finished_at": None,
        "total_time_seconds": float(data.get("total_time_seconds", 0.0) or 0.0),
        "config": {},
        "metadata": {
            "migrated_from": "legacy-unversioned",
            "legacy_method": data.get("method") or data.get("base_method"),
            "legacy_fields": {
                key: value for key, value in data.items() if key not in known
            },
        },
    }


def _safe_segment(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._") or "unknown"


def result_path(
    config: RunConfig, task: TaskSpec, *, environment_identity: str
) -> Path:
    return _run_directory(config, task, kind="json") / (
        f"{_safe_segment(environment_identity)}.json"
    )


def artifact_directory(
    config: RunConfig, task: TaskSpec, *, environment_identity: str
) -> Path:
    """Return the matching directory for per-attempt GIF artifacts."""

    return _run_directory(config, task, kind="gif") / _safe_segment(
        environment_identity
    )


def _run_directory(config: RunConfig, task: TaskSpec, *, kind: str) -> Path:
    return (
        ensure_output_path(config.output)
        / kind
        / _safe_segment(task.name)
        / _safe_segment(config.model)
        / _safe_segment(config.strategy)
        / f"run-{config.run_index}"
    )


def save_result(path: Path, result: EvaluationResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        _compact_result(result, path), indent=2, ensure_ascii=False, sort_keys=True
    )
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", text=True
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(payload + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    finally:
        temporary = Path(temporary_name)
        if temporary.exists():
            temporary.unlink()


def load_result(path: Path) -> EvaluationResult:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Result root must be an object: {path}")
    result = decode_result(data)
    if "run_index" not in result.config:
        for parent in path.parents:
            match = re.fullmatch(r"run-(\d+)", parent.name, re.IGNORECASE)
            if match or parent.name.isdigit():
                result.config["run_index"] = int(
                    match.group(1) if match else parent.name
                )
                break
    return result


def is_complete(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        load_result(path)
    except (OSError, ValueError, TypeError):
        return False
    return True


def load_results(root: Path) -> tuple[list[EvaluationResult], list[tuple[Path, str]]]:
    results: list[EvaluationResult] = []
    errors: list[tuple[Path, str]] = []
    search_root = root / "json" if (root / "json").is_dir() else root
    for path in sorted(search_root.rglob("*.json")):
        try:
            results.append(load_result(path))
        except (OSError, ValueError, TypeError) as exc:
            errors.append((path, str(exc)))
    return results, errors


def _pass_rate(results: Sequence[EvaluationResult]) -> float:
    return (
        0.0 if not results else sum(result.success for result in results) / len(results)
    )


def _mean_score(results: Sequence[EvaluationResult]) -> float:
    return (
        0.0
        if not results
        else sum(result.best_score for result in results) / len(results)
    )


def _score_std(results: Sequence[EvaluationResult]) -> float:
    if len(results) < 2:
        return 0.0
    mean = _mean_score(results)
    return (
        sum((result.best_score - mean) ** 2 for result in results) / (len(results) - 1)
    ) ** 0.5


def _result_run_index(result: EvaluationResult) -> int:
    try:
        return int(result.config.get("run_index", 1))
    except (TypeError, ValueError):
        return 1


def _pair_key(result: EvaluationResult) -> tuple[str, ...]:
    environment = result.environment_pair or result.target_environment or "unknown"
    return (
        result.task_path,
        environment,
        result.mode,
        result.provider,
        result.model,
        result.strategy,
    )


def _pass_at_k(results: Sequence[EvaluationResult]) -> dict[str, Any]:
    grouped: dict[tuple[str, ...], list[EvaluationResult]] = defaultdict(list)
    for result in results:
        grouped[_pair_key(result)].append(result)
    for trajectories in grouped.values():
        trajectories.sort(key=_result_run_index)
    max_runs = max((len(items) for items in grouped.values()), default=0)
    values: dict[str, Any] = {}
    for k in range(1, max_runs + 1):
        eligible = [items for items in grouped.values() if len(items) >= k]
        passed = sum(any(item.success for item in items[:k]) for items in eligible)
        values[f"Pass@{k}"] = {
            "rate": 0.0 if not eligible else passed / len(eligible),
            "passed_pairs": passed,
            "pair_count": len(eligible),
        }
    return values


def _run_count_summary(results: Sequence[EvaluationResult]) -> dict[str, int]:
    counts = Counter(_pair_key(result) for result in results)
    values = list(counts.values())
    return {
        "minimum": min(values, default=0),
        "maximum": max(values, default=0),
    }


def _error_taxonomy_summary(results: Sequence[EvaluationResult]) -> dict[str, Any]:
    counts = Counter(_trajectory_error_type(result) for result in results)
    total = len(results)
    failures = total - counts.get("success", 0)
    return {
        "counts": dict(sorted(counts.items())),
        "rates": {key: count / total for key, count in sorted(counts.items())}
        if total
        else {},
        "failure_only_rates": {
            key: count / failures
            for key, count in sorted(counts.items())
            if key != "success"
        }
        if failures
        else {},
    }


def _pair_error_taxonomy_summary(
    results: Sequence[EvaluationResult],
) -> dict[str, Any]:
    grouped: dict[tuple[str, ...], list[EvaluationResult]] = defaultdict(list)
    for result in results:
        grouped[_pair_key(result)].append(result)
    labels: list[str] = []
    for trajectories in grouped.values():
        if any(item.success for item in trajectories):
            labels.append("success")
            continue
        counts = Counter(_trajectory_error_type(item) for item in trajectories)
        labels.append(sorted(counts, key=lambda key: (-counts[key], key))[0])
    synthetic = Counter(labels)
    total = len(labels)
    failures = total - synthetic.get("success", 0)
    return {
        "counts": dict(sorted(synthetic.items())),
        "rates": {key: count / total for key, count in sorted(synthetic.items())}
        if total
        else {},
        "failure_only_rates": {
            key: count / failures
            for key, count in sorted(synthetic.items())
            if key != "success"
        }
        if failures
        else {},
    }


def aggregate(results: list[EvaluationResult]) -> dict[str, Any]:
    by_category: dict[str, list[EvaluationResult]] = defaultdict(list)
    for result in results:
        category = (
            result.task_path.split("/", 1)[0] if "/" in result.task_path else "other"
        )
        by_category[category].append(result)
    return {
        "result_count": len(results),
        "trajectory_count": len(results),
        "pair_count": len({_pair_key(result) for result in results}),
        "pass_rate": _pass_rate(results),
        "trajectory_pass_rate": _pass_rate(results),
        "pass_at_k": _pass_at_k(results),
        "runs_per_pair": _run_count_summary(results),
        "error_taxonomy": _pair_error_taxonomy_summary(results),
        "trajectory_error_taxonomy": _error_taxonomy_summary(results),
        "mean_best_score": _mean_score(results),
        "best_score_std": _score_std(results),
        "mean_verified_attempts": (
            0.0
            if not results
            else sum(len(result.attempts) for result in results) / len(results)
        ),
        "stop_reasons": dict(
            sorted(Counter(item.stop_reason for item in results).items())
        ),
        "by_category": {
            category: {
                "result_count": len(items),
                "trajectory_pass_rate": _pass_rate(items),
                "pair_count": len({_pair_key(item) for item in items}),
                "pass_at_k": _pass_at_k(items),
                "error_taxonomy": _pair_error_taxonomy_summary(items),
                "trajectory_error_taxonomy": _error_taxonomy_summary(items),
                "mean_best_score": _mean_score(items),
                "best_score_std": _score_std(items),
            }
            for category, items in sorted(by_category.items())
        },
    }


def _compact_result(result: EvaluationResult, path: Path) -> dict[str, Any]:
    """Serialize only reproducibility and analysis fields, not prompts/raw metrics."""

    run_index = _result_run_index(result)
    token_usage: Counter[str] = Counter()
    for attempt in result.attempts:
        if attempt.generation:
            token_usage.update(attempt.generation.token_usage)
    config_keys = (
        "attempts",
        "max_steps",
        "generation_retries",
        "seed",
        "temperature",
        "max_tokens",
        "headless",
        "save_gif",
        "timeout_seconds",
        "run_index",
    )
    config = {
        key: result.config[key]
        for key in config_keys
        if key in result.config and result.config[key] is not None
    }
    return {
        "schema_version": RESULT_SCHEMA_VERSION,
        "task_id": result.task_id,
        "task_path": result.task_path,
        "mode": result.mode,
        "provider": result.provider,
        "model": result.model,
        "strategy": result.strategy,
        "run_index": run_index,
        "source_environment": result.source_environment,
        "target_environment": result.target_environment,
        "environment_pair": result.environment_pair,
        "attempt_budget": int(result.config.get("attempts", 0) or 0),
        "verified_attempts": len(result.attempts),
        "revision_attempts": sum(item.attempt > 0 for item in result.attempts),
        "success_attempt": min(
            (item.attempt for item in result.attempts if item.success), default=None
        ),
        "success": result.success,
        "best_score": result.best_score,
        "best_attempt": result.best_attempt,
        "stop_reason": result.stop_reason,
        "error_type": _trajectory_error_type(result),
        "started_at": result.started_at,
        "finished_at": result.finished_at,
        "total_time_seconds": result.total_time_seconds,
        "token_usage": dict(sorted(token_usage.items())),
        "config": config,
        "attempts": [_compact_attempt(item, path) for item in result.attempts],
        "metadata": _compact_metadata(result.metadata),
    }


def _compact_attempt(attempt: AttemptRecord, result_path_value: Path) -> dict[str, Any]:
    metrics = attempt.verification.metrics
    failure_reason = _optional_text(metrics.get("failure_reason"))
    error_type = _optional_text(metrics.get("error_type"))
    error_stage = _optional_text(metrics.get("error_stage"))
    error_message = _optional_text(metrics.get("error_message"))
    violations = _constraint_violations(metrics, failure_reason)
    outcome = {
        "category": _error_category(
            attempt.success,
            failure_reason=failure_reason,
            error_type=error_type,
            error_stage=error_stage,
            error=attempt.verification.error,
            violations=violations,
        ),
        "failure_reason": failure_reason,
        "error_type": error_type,
        "error_stage": error_stage,
        "error_message": error_message,
        "error": _optional_text(attempt.verification.error),
    }
    generation = None
    if attempt.generation is not None:
        generation = {
            "model": attempt.generation.model,
            "token_usage": dict(attempt.generation.token_usage),
            "latency_seconds": attempt.generation.latency_seconds,
        }
    return {
        "attempt": attempt.attempt,
        "phase": attempt.phase,
        "timestamp": attempt.timestamp,
        "success": attempt.success,
        "score": attempt.score,
        "step_count": metrics.get("step_count"),
        "code": attempt.code,
        "code_sha256": sha256(attempt.code.encode("utf-8")).hexdigest(),
        "outcome": {key: value for key, value in outcome.items() if value is not None},
        "constraints": {
            "violated": bool(violations),
            "count": len(violations),
            "violations": violations,
        },
        "physics": _physical_summary(metrics),
        "generation": generation,
        "verification_seconds": attempt.verification.duration_seconds,
        "artifacts": [
            _portable_artifact_path(item, result_path_value)
            for item in attempt.verification.artifact_paths
        ],
    }


def _constraint_violations(
    metrics: dict[str, Any], failure_reason: str | None
) -> list[str]:
    values: list[str] = []
    for key in ("constraint_violations", "design_violations", "violations"):
        raw = metrics.get(key)
        if isinstance(raw, str):
            values.append(raw)
        elif isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
            values.extend(str(item) for item in raw if item is not None)
    if not values and failure_reason and "constraint" in failure_reason.lower():
        detail = (
            failure_reason.split(":", 1)[1] if ":" in failure_reason else failure_reason
        )
        values.extend(item.strip() for item in detail.split(";") if item.strip())
    return list(dict.fromkeys(values))


def _physical_summary(metrics: dict[str, Any]) -> dict[str, Any]:
    """Retain only physical scalars consumed by benchmark error analysis."""

    summary: dict[str, Any] = {}
    if "structure_broken" in metrics:
        summary["structure_broken"] = bool(metrics["structure_broken"])
    broken = metrics.get("joints_broken_count")
    if broken is None:
        events = metrics.get("joint_failure_events")
        if isinstance(events, Sequence) and not isinstance(events, (str, bytes)):
            broken = len(events)
        elif isinstance(events, (int, float)):
            broken = int(events)
    if broken is not None:
        summary["joints_broken_count"] = int(broken)
    progress = metrics.get("progress")
    if progress is None:
        progress = metrics.get("progress_pct")
    if isinstance(progress, (int, float)):
        summary["progress"] = float(progress)
    return summary


def _trajectory_error_type(result: EvaluationResult) -> str:
    """Classify a trajectory using the lightweight signals from old result.py."""

    if result.success:
        return "success"
    if not result.attempts:
        return "stagnation"
    best = max(result.attempts, key=lambda item: item.score)
    best_metrics = best.verification.metrics
    if result.best_score <= -60:
        return "catastrophic_collapse"
    if _constraint_violations(
        best_metrics, _optional_text(best_metrics.get("failure_reason"))
    ):
        return "constraint_violation"
    physics = _physical_summary(best_metrics)
    if physics.get("structure_broken") or physics.get("joints_broken_count", 0) > 0:
        return "structural_failure"
    if result.best_score < 0:
        return "numerical_instability"

    attempts = sorted(result.attempts, key=lambda item: item.attempt)
    scores = [item.score for item in attempts]
    first_positive = next(
        (index for index, score in enumerate(scores) if score > 0), -1
    )
    third = max(1, len(scores) // 3)
    early_mean = sum(scores[:third]) / third
    late_start = max(third * 2, len(scores) - third)
    late_values = scores[late_start:]
    late_mean = sum(late_values) / max(1, len(late_values))
    score_trend = late_mean - early_mean
    improved_late = False
    if len(scores) >= 10:
        midpoint = len(scores) // 2
        improved_late = max(scores[midpoint:]) > max(scores[:midpoint]) + 2

    failure_reasons = {
        str(item.verification.metrics.get("failure_reason") or "").strip().lower()[:80]
        for item in attempts
        if item.verification.metrics.get("failure_reason")
    }
    similarities: list[float] = []
    for previous, current in zip(attempts, attempts[1:]):
        previous_tokens = set(previous.code.split())
        current_tokens = set(current.code.split())
        if previous_tokens and current_tokens:
            similarities.append(
                len(previous_tokens & current_tokens)
                / max(1, len(previous_tokens | current_tokens))
            )
    recent = similarities[-5:]
    mean_recent_similarity = sum(recent) / len(recent) if recent else 0.0
    if (
        mean_recent_similarity > 0.85
        and abs(score_trend) < 3
        and result.best_score < 50
    ):
        return "design_fixation"
    if improved_late and result.best_score >= 30:
        return "late_convergence"
    if first_positive < 0 and abs(score_trend) < 2 and len(failure_reasons) <= 1:
        return "stagnation"
    if first_positive < 0 and len(failure_reasons) >= 3:
        return "exploration"
    if 0 < result.best_score < 100:
        return "late_convergence" if improved_late else "budget_exhaustion"
    return "stagnation"


def _error_category(
    success: bool,
    *,
    failure_reason: str | None,
    error_type: str | None,
    error_stage: str | None,
    error: str | None,
    violations: list[str],
) -> str:
    if success:
        return "success"
    if violations:
        return "constraint_violation"
    stage = (error_stage or "").lower()
    kind = (error_type or "").lower()
    if stage in {"static_analysis", "code_parsing", "code_compilation"} or kind in {
        "prohibited_operation",
        "syntax_error",
        "missing_function",
    }:
        return "invalid_code"
    if stage == "agent_construction" or kind == "agent_building_error":
        return "construction_error"
    if error or error_type:
        return "runtime_error"
    if failure_reason:
        return "simulation_failure"
    return "unspecified_failure"


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _portable_artifact_path(value: str, result_path_value: Path) -> str:
    artifact = Path(value)
    try:
        json_root = next(
            parent for parent in result_path_value.parents if parent.name == "json"
        )
        root = json_root.parent
        return artifact.resolve().relative_to(root.resolve()).as_posix()
    except (OSError, StopIteration, ValueError):
        return str(artifact)


def _compact_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    blocked = ("prompt", "feedback", "metric", "traceback", "raw", "code")
    return {
        str(key): to_jsonable(value)
        for key, value in metadata.items()
        if not any(token in str(key).lower() for token in blocked)
    }
