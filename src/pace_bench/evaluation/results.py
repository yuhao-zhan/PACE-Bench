"""Versioned result decoding, persistence, and standard aggregation."""

from __future__ import annotations

import json
import os
import re
import tempfile
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
)


def decode_result(data: dict[str, Any]) -> EvaluationResult:
    if "schema_version" not in data:
        data = migrate_legacy_result(data)
    version = str(data.get("schema_version"))
    if version != RESULT_SCHEMA_VERSION:
        raise ResultSchemaError(
            f"Unsupported result schema {version!r}; expected {RESULT_SCHEMA_VERSION}."
        )
    fields = dict(data)
    fields["attempts"] = [_decode_attempt(item) for item in data.get("attempts", [])]
    try:
        return EvaluationResult(**fields)
    except TypeError as exc:
        raise ResultSchemaError(f"Malformed evaluation result: {exc}") from exc


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
        "schema_version": RESULT_SCHEMA_VERSION,
        "task_id": task_name.split("/")[-1],
        "task_path": task_name,
        "mode": "adaptation" if pair else "from-scratch",
        "provider": str(data.get("model_type") or "legacy"),
        "model": str(data.get("model_name") or "unknown"),
        "strategy": "legacy",
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
    return (
        ensure_output_path(config.output)
        / _safe_segment(task.category_name or "demos")
        / _safe_segment(task.name)
        / _safe_segment(config.model)
        / _safe_segment(config.strategy)
        / f"run-{config.run_index}"
        / f"{_safe_segment(environment_identity)}.json"
    )


def save_result(path: Path, result: EvaluationResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(result.to_dict(), indent=2, ensure_ascii=False, sort_keys=True)
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
    return decode_result(data)


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
    for path in sorted(root.rglob("*.json")):
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


def aggregate(results: list[EvaluationResult]) -> dict[str, Any]:
    by_category: dict[str, list[EvaluationResult]] = defaultdict(list)
    for result in results:
        category = (
            result.task_path.split("/", 1)[0] if "/" in result.task_path else "other"
        )
        by_category[category].append(result)
    return {
        "result_count": len(results),
        "pass_rate": _pass_rate(results),
        "mean_best_score": _mean_score(results),
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
                "pass_rate": _pass_rate(items),
                "mean_best_score": _mean_score(items),
            }
            for category, items in sorted(by_category.items())
        },
    }
