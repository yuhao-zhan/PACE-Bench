import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from pace_bench.core.types import EnvironmentId
from pace_bench.evaluation.verification.verifier import PhysicsVerifier
from pace_bench.tasks.registry import EnvironmentSpec, TaskSpec, get_registry


class _ConcurrentProbeVerifier:
    active = 0
    maximum_active = 0
    cleanup_count = 0
    guard = threading.Lock()

    def __init__(self, *args, **kwargs) -> None:
        pass

    def verify_code(self, *args, **kwargs):
        with self.guard:
            type(self).active += 1
            type(self).maximum_active = max(
                type(self).maximum_active,
                type(self).active,
            )
        try:
            time.sleep(0.05)
            return False, 0.0, {"failed": True}, None
        finally:
            with self.guard:
                type(self).active -= 1

    def cleanup(self) -> None:
        with self.guard:
            type(self).cleanup_count += 1


class VerifierConcurrencyTests(unittest.TestCase):
    def setUp(self) -> None:
        _ConcurrentProbeVerifier.active = 0
        _ConcurrentProbeVerifier.maximum_active = 0
        _ConcurrentProbeVerifier.cleanup_count = 0

    def test_native_verification_lifecycles_do_not_overlap(self) -> None:
        task = TaskSpec(
            name="S_01",
            path=Path("Category1_Statics_Equilibrium/S_01"),
            module_name="pace_bench.tasks.categories.Category1_Statics_Equilibrium.S_01",
            benchmark=True,
            category_number=1,
            category_name="Category1_Statics_Equilibrium",
        )
        environment = EnvironmentSpec(
            environment_id=EnvironmentId("Stage-1"),
            title="Stage 1",
        )
        verifiers = [
            PhysicsVerifier(
                task,
                environment,
                max_steps=10,
                headless=True,
                save_gif=False,
                artifact_directory=None,
                registry=get_registry(),
            )
            for _ in range(2)
        ]

        with (
            patch(
                "pace_bench.evaluation.verification.verifier.CodeVerifier",
                _ConcurrentProbeVerifier,
            ),
            patch(
                "pace_bench.evaluation.verification.verifier.format_feedback",
                return_value="feedback",
            ),
            ThreadPoolExecutor(max_workers=2) as executor,
        ):
            results = list(
                executor.map(
                    lambda verifier: verifier.verify("code", 1),
                    verifiers,
                )
            )

        self.assertEqual(len(results), 2)
        self.assertEqual(_ConcurrentProbeVerifier.maximum_active, 1)
        self.assertEqual(_ConcurrentProbeVerifier.cleanup_count, 2)


if __name__ == "__main__":
    unittest.main()
