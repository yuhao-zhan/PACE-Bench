from __future__ import annotations

import unittest
from pathlib import Path

from pace_bench.cli.main import build_parser, _config_from_args
from pace_bench.core.types import RunMode
from pace_bench.evaluation.prompts import PromptBuilder
from pace_bench.evaluation.results import result_path
from pace_bench.evaluation.runner import WorkItem
from pace_bench.tasks.registry import get_registry


class FromScratchConfigurationTests(unittest.TestCase):
    def test_default_output_is_separate(self) -> None:
        args = build_parser().parse_args(
            [
                "evaluate",
                "--task",
                "S_01",
                "--env",
                "Stage-1",
                "--from-scratch",
            ]
        )
        config = _config_from_args(args, RunMode.FROM_SCRATCH)
        self.assertEqual(config.output, Path("results_scratch"))

    def test_result_path_uses_one_environment_not_a_pair(self) -> None:
        registry = get_registry()
        task = registry.resolve("S_01")
        args = build_parser().parse_args(
            ["evaluate", "--task", "S_01", "--env", "Stage-1", "--from-scratch"]
        )
        config = _config_from_args(args, RunMode.FROM_SCRATCH)
        path = result_path(config, task, environment_identity="Stage-1")
        self.assertEqual(path.name, "Stage-1.json")
        self.assertNotIn("_to_", str(path))
        self.assertEqual(
            WorkItem(0, config).identity,
            "S_01:Initial:run-1",
        )


class FromScratchPromptTests(unittest.TestCase):
    def test_all_stage_prompts_have_no_source_transition_language(self) -> None:
        registry = get_registry()
        builder = PromptBuilder(registry)
        for task in registry.select("all"):
            for environment in registry.environments(task):
                if environment.environment_id.value == "Initial":
                    continue
                with self.subTest(task=task.name, environment=environment.environment_id):
                    context = builder.load_task_context(
                        task,
                        environment,
                        include_source_comparison=False,
                    )
                    prompt = builder.initial(context).lower()
                    self.assertNotIn("originally", prompt)
                    self.assertNotIn("source environment", prompt)
                    self.assertNotIn("environment has changed", prompt)


if __name__ == "__main__":
    unittest.main()
