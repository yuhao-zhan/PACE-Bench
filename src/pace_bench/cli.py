"""The single public command-line interface for PACE-Bench."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from pace_bench.errors import ConfigurationError, PaceBenchError
from pace_bench.evaluation.config import RunConfig
from pace_bench.evaluation.results import aggregate, load_results
from pace_bench.evaluation.runner import enumerate_work_items
from pace_bench.evaluation.runner import run_work_items
from pace_bench.evaluation.runner import validate_task_references
from pace_bench.tasks.registry import CATEGORIES, get_registry
from pace_bench.types import EnvironmentId, RunMode


def build_parser() -> argparse.ArgumentParser:
    """Build the small public CLI: list, evaluate, validate, and report."""

    parser = argparse.ArgumentParser(
        prog="pace-bench",
        description="Physics Adaptation via Code Evolution in Dynamic Environments",
    )
    parser.add_argument("--version", action="version", version="%(prog)s 0.1.0")
    commands = parser.add_subparsers(dest="command", required=True)

    list_parser = commands.add_parser("list", help="List tasks and environments")
    list_parser.add_argument("--task", action="append")
    list_parser.add_argument("--json", action="store_true")
    list_parser.set_defaults(handler=_list_command)

    evaluate_parser = commands.add_parser(
        "evaluate",
        help="Run vanilla or an external method on selected task/environment pairs",
    )
    evaluate_parser.add_argument(
        "--task",
        action="append",
        required=True,
        help="Task ID, full task path, category_N, or all; repeat to combine selectors",
    )
    evaluate_parser.add_argument(
        "--env",
        action="append",
        default=None,
        help="Target environment (Stage-1..Stage-4 or all); repeat to select several",
    )
    evaluate_parser.add_argument(
        "--from-scratch",
        action="store_true",
        help="Generate directly instead of evaluating the Initial reference as attempt 0",
    )
    evaluate_parser.add_argument(
        "--method",
        default="vanilla",
        help="vanilla or a dotted class path such as package.module:MyMethod",
    )
    evaluate_parser.add_argument(
        "--provider",
        default="mock",
        help="openai-compatible, local-transformers, mock, or package.module:Provider",
    )
    evaluate_parser.add_argument(
        "--model", default="mock", help="Model name or local path"
    )
    evaluate_parser.add_argument(
        "--api-key", help="Prefer OPENAI_API_KEY for normal use"
    )
    evaluate_parser.add_argument("--base-url", help="OpenAI-compatible API endpoint")
    evaluate_parser.add_argument("--device", default="auto")
    evaluate_parser.add_argument(
        "--devices",
        help="Comma-separated devices for local parallel runs, e.g. cuda:0,cuda:1",
    )
    evaluate_parser.add_argument("--dtype", default="auto")
    evaluate_parser.add_argument("--attempts", type=int, default=20)
    evaluate_parser.add_argument("--runs", type=int, default=1)
    evaluate_parser.add_argument("--workers", type=int, default=1)
    evaluate_parser.add_argument("--max-steps", type=int)
    evaluate_parser.add_argument("--generation-retries", type=int, default=2)
    evaluate_parser.add_argument("--timeout-seconds", type=float)
    evaluate_parser.add_argument("--seed", type=int, default=0)
    evaluate_parser.add_argument("--temperature", type=float, default=0.7)
    evaluate_parser.add_argument("--max-tokens", type=int, default=8192)
    evaluate_parser.add_argument("--output", type=Path, default=Path("outputs/default"))
    evaluate_parser.add_argument("--save-gif", action="store_true")
    evaluate_parser.add_argument("--display", action="store_true")
    evaluate_parser.add_argument("--no-resume", action="store_true")
    evaluate_parser.add_argument("--dry-run", action="store_true")
    evaluate_parser.set_defaults(handler=_evaluate_command)

    validate_parser = commands.add_parser(
        "validate", help="Validate task contracts/references"
    )
    validate_parser.add_argument("--task", action="append")
    validate_parser.add_argument("--contracts-only", action="store_true")
    validate_parser.add_argument("--skip-initial-failures", action="store_true")
    validate_parser.add_argument("--max-steps", type=int)
    validate_parser.set_defaults(handler=_validate_command)

    report_parser = commands.add_parser("report", help="Summarize result JSON files")
    report_parser.add_argument("--input", type=Path, required=True)
    report_parser.add_argument("--output", type=Path)
    report_parser.set_defaults(handler=_report_command)
    return parser


def _list_command(args: argparse.Namespace) -> int:
    registry = get_registry()
    tasks = registry.select(args.task or ["all"])
    if args.json:
        print(
            json.dumps(
                [
                    {
                        "task": task.full_name,
                        "id": task.name,
                        "category": task.category_number,
                        "environments": [
                            str(environment.environment_id)
                            for environment in registry.environments(task)
                        ],
                    }
                    for task in tasks
                ],
                indent=2,
            )
        )
        return 0
    for number, (_, _, display_name) in CATEGORIES.items():
        selected = [task for task in tasks if task.category_number == number]
        if selected:
            print(f"Category {number}: {display_name}")
            for task in selected:
                environments = ", ".join(
                    str(environment.environment_id)
                    for environment in registry.environments(task)
                )
                print(f"  {task.name:<4}  {task.full_name}  [{environments}]")
    print(f"{len(tasks)} benchmark task(s)")
    return 0


def _evaluate_command(args: argparse.Namespace) -> int:
    mode = RunMode.FROM_SCRATCH if args.from_scratch else RunMode.ADAPTATION
    environments = args.env or (["Initial"] if args.from_scratch else ["Stage-1"])
    base = _config_from_args(args, mode)
    items = enumerate_work_items(
        base,
        task_selectors=args.task,
        stages=environments,
        runs=args.runs,
    )
    if not items:
        raise ConfigurationError(
            "The selected tasks/environments produced no evaluation pairs"
        )
    outcomes = run_work_items(items, workers=args.workers, dry_run=args.dry_run)
    failures = 0
    for outcome in outcomes:
        if args.dry_run:
            print(outcome.work_item.identity)
        elif outcome.error:
            failures += 1
            print(f"ERROR {outcome.work_item.identity}: {outcome.error}")
        else:
            result = outcome.result
            print(
                f"DONE {outcome.work_item.identity}: success={result.success} "
                f"best_score={result.best_score:.3f} stop={result.stop_reason}"
            )
    print(f"{len(outcomes)} work item(s), {failures} orchestration error(s)")
    return 1 if failures else 0


def _config_from_args(args: argparse.Namespace, mode: RunMode) -> RunConfig:
    options: dict[str, Any] = {}
    if args.provider in {"openai", "openai-compatible"}:
        if args.api_key:
            options["api_key"] = args.api_key
        if args.base_url:
            options["base_url"] = args.base_url
        if args.timeout_seconds is not None:
            options["timeout"] = args.timeout_seconds
    elif args.provider in {"local", "local-transformers", "transformers"}:
        if args.devices:
            pool = [
                device.strip() for device in args.devices.split(",") if device.strip()
            ]
            if not pool:
                raise ConfigurationError("--devices must contain at least one device")
            options["device_pool"] = pool
        else:
            options["device"] = args.device
        options["dtype"] = args.dtype
    return RunConfig(
        task=args.task[0],
        mode=mode,
        source=EnvironmentId("Initial"),
        target=EnvironmentId("Initial" if mode == RunMode.FROM_SCRATCH else "Stage-1"),
        provider=args.provider,
        model=args.model,
        strategy=args.method,
        attempts=args.attempts,
        max_steps=args.max_steps,
        generation_retries=args.generation_retries,
        timeout_seconds=args.timeout_seconds,
        seed=args.seed,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        headless=not args.display,
        save_gif=args.save_gif,
        output=args.output,
        resume=not args.no_resume,
        provider_options=options,
    )


def _validate_command(args: argparse.Namespace) -> int:
    registry = get_registry()
    tasks = registry.select(args.task or ["all"])
    failures = 0
    for task in tasks:
        errors = registry.validate(task, import_modules=True)
        for error in errors:
            print(f"FAIL {task.full_name}: {error}")
        failures += len(errors)
        if errors:
            continue
        print(f"PASS {task.full_name}: contract")
        if args.contracts_only:
            continue
        for check in validate_task_references(
            task,
            registry=registry,
            check_initial_failures=not args.skip_initial_failures,
            max_steps=args.max_steps,
        ):
            label = "PASS" if check.passed else "FAIL"
            print(
                f"{label} {check.task}: {check.reference_environment} reference on "
                f"{check.execution_environment} score={check.score:.3f}"
            )
            if not check.passed:
                failures += 1
                if check.error:
                    print(f"  error: {check.error}")
    print(f"Validation complete: {len(tasks)} task(s), {failures} failure(s)")
    return 1 if failures else 0


def _report_command(args: argparse.Namespace) -> int:
    results, errors = load_results(args.input)
    summary = aggregate(results)
    summary["invalid_result_count"] = len(errors)
    rendered = json.dumps(summary, indent=2, sort_keys=True)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    for path, error in errors:
        print(f"warning: skipped {path}: {error}")
    return 0 if results else 1


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        return int(args.handler(args))
    except (PaceBenchError, ValueError) as exc:
        print(f"pace-bench: error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
