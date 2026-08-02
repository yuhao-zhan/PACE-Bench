import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from pace_bench.core.types import (
    AttemptRecord,
    EvaluationResult,
    VerificationResult,
)
from pace_bench.evaluation.config import RunConfig
from pace_bench.evaluation.metrics import aggregate
from pace_bench.evaluation.results import (
    artifact_directory,
    load_results,
    result_path,
    result_path_candidates,
    save_result,
)
from pace_bench.evaluation.runner import run_single
from pace_bench.tasks.registry import TaskSpec, get_registry


class ResultPathTests(unittest.TestCase):
    def test_benchmark_json_and_gif_paths_include_category_before_task(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory).resolve()
            config = RunConfig(
                task="Category1_Statics_Equilibrium/S_01",
                model="Qwen3-4B",
                strategy="vanilla",
                output=output,
                run_index=2,
            )
            task = TaskSpec(
                name="S_01",
                path=Path("Category1_Statics_Equilibrium/S_01"),
                module_name="pace_bench.tasks.categories.Category1_Statics_Equilibrium.S_01",
                benchmark=True,
                category_number=1,
                category_name="Category1_Statics_Equilibrium",
            )

            self.assertEqual(
                result_path(
                    config,
                    task,
                    environment_identity="Initial_to_Stage-1",
                ),
                output
                / "json"
                / "Category1_Statics_Equilibrium"
                / "S_01"
                / "Qwen3-4B"
                / "vanilla"
                / "run-2"
                / "Initial_to_Stage-1.json",
            )
            self.assertEqual(
                artifact_directory(
                    config,
                    task,
                    environment_identity="Initial_to_Stage-1",
                ),
                output
                / "gif"
                / "Category1_Statics_Equilibrium"
                / "S_01"
                / "Qwen3-4B"
                / "vanilla"
                / "run-2"
                / "Initial_to_Stage-1",
            )

    def test_demo_paths_use_demo_category(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory).resolve()
            config = RunConfig(task="demo/basic", output=output)
            task = TaskSpec(
                name="basic",
                path=Path("demo/basic"),
                module_name="pace_bench.tasks.demos.basic",
                benchmark=False,
            )

            self.assertEqual(
                result_path(config, task, environment_identity="Stage-1"),
                output
                / "json"
                / "demo"
                / "basic"
                / "mock"
                / "vanilla"
                / "run-1"
                / "Stage-1.json",
            )

    def test_loader_accepts_legacy_tree_without_category_level(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory).resolve()
            legacy_path = (
                output
                / "json"
                / "S_01"
                / "mock"
                / "vanilla"
                / "run-1"
                / "Initial_to_Stage-1.json"
            )
            legacy_path.parent.mkdir(parents=True)
            legacy_path.write_text(
                json.dumps(
                    {
                        "schema_version": "2.0",
                        "task_id": "S_01",
                        "task_path": "Category1_Statics_Equilibrium/S_01",
                        "model": "mock",
                        "strategy": "vanilla",
                        "attempts": [],
                    }
                ),
                encoding="utf-8",
            )

            results, errors = load_results(output)

            self.assertEqual(errors, [])
            self.assertEqual([result.task_id for result in results], ["S_01"])

    def test_resume_finds_completed_legacy_result_path(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory).resolve()
            registry = get_registry()
            task = registry.resolve("S_01")
            config = RunConfig(task="S_01", output=output, resume=True)
            _current_path, legacy_path = result_path_candidates(
                config,
                task,
                environment_identity="Initial_to_Stage-1",
            )
            legacy_path.parent.mkdir(parents=True)
            legacy_path.write_text(
                json.dumps(
                    {
                        "schema_version": "2.0",
                        "task_id": "S_01",
                        "task_path": "Category1_Statics_Equilibrium/S_01",
                        "model": "mock",
                        "strategy": "vanilla",
                        "source_environment": "Initial",
                        "target_environment": "Stage-1",
                        "environment_pair": "Initial_to_Stage-1",
                        "stop_reason": "legacy_resume",
                        "attempts": [],
                    }
                ),
                encoding="utf-8",
            )

            resumed = run_single(config, registry=registry)

            self.assertEqual(resumed.stop_reason, "legacy_resume")

    def test_saved_artifact_path_preserves_category_and_task(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory).resolve()
            config = RunConfig(
                task="Category1_Statics_Equilibrium/S_01",
                model="Qwen3-4B",
                output=output,
            )
            task = get_registry().resolve("S_01")
            gif = (
                artifact_directory(
                    config,
                    task,
                    environment_identity="Initial_to_Stage-1",
                )
                / "attempt-01.gif"
            )
            result = EvaluationResult(
                task_id="S_01",
                task_path="Category1_Statics_Equilibrium/S_01",
                mode="adaptation",
                provider="mock",
                model="Qwen3-4B",
                strategy="vanilla",
                attempts=[
                    AttemptRecord(
                        attempt=1,
                        code="def build_agent(env):\n    return None\n",
                        verification=VerificationResult(
                            success=False,
                            score=0.0,
                            artifact_paths=[str(gif)],
                        ),
                    )
                ],
                source_environment="Initial",
                target_environment="Stage-1",
                environment_pair="Initial_to_Stage-1",
                config=config.to_dict(),
            )
            json_path = result_path(
                config,
                task,
                environment_identity="Initial_to_Stage-1",
            )

            save_result(json_path, result)
            payload = json.loads(json_path.read_text(encoding="utf-8"))

            self.assertEqual(
                payload["attempts"][0]["artifacts"],
                [
                    "gif/Category1_Statics_Equilibrium/S_01/Qwen3-4B/"
                    "vanilla/run-1/Initial_to_Stage-1/attempt-01.gif"
                ],
            )

    def test_report_groups_new_and_legacy_paths_by_canonical_category(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory).resolve()
            payloads = (
                (
                    output
                    / "json"
                    / "Category1_Statics_Equilibrium"
                    / "S_01"
                    / "mock"
                    / "vanilla"
                    / "run-1"
                    / "Initial_to_Stage-1.json",
                    "S_01",
                    "S_01",
                ),
                (
                    output
                    / "json"
                    / "K_01"
                    / "mock"
                    / "vanilla"
                    / "run-1"
                    / "Initial_to_Stage-1.json",
                    "K_01",
                    "category_2_01",
                ),
            )
            for path, task_id, task_path in payloads:
                path.parent.mkdir(parents=True)
                path.write_text(
                    json.dumps(
                        {
                            "schema_version": "2.0",
                            "task_id": task_id,
                            "task_path": task_path,
                            "model": "mock",
                            "strategy": "vanilla",
                            "source_environment": "Initial",
                            "target_environment": "Stage-1",
                            "environment_pair": "Initial_to_Stage-1",
                            "attempt_budget": 1,
                            "attempts": [],
                        }
                    ),
                    encoding="utf-8",
                )

            results, errors = load_results(output)
            report = aggregate(results)

            self.assertEqual(errors, [])
            self.assertEqual(report["result_count"], 2)
            self.assertEqual(
                set(report["by_category"]),
                {
                    "Category1_Statics_Equilibrium",
                    "Category2_Kinematics_Linkages",
                },
            )


if __name__ == "__main__":
    unittest.main()
