import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from pace_bench.evaluation.config import RunConfig
from pace_bench.evaluation.results import (
    artifact_directory,
    load_results,
    result_path,
)
from pace_bench.tasks.registry import TaskSpec


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


if __name__ == "__main__":
    unittest.main()
