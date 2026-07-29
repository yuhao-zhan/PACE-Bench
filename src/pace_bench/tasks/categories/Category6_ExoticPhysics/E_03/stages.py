from __future__ import annotations

from pace_bench.tasks.stage_prompt import uniform_suffix_for_task

from typing import Any, Dict, List

TASK_DESCRIPTION_SUFFIX = uniform_suffix_for_task("E_03")

def update_task_description_for_visible_changes(
    base_description: str,
    target_terrain_config: Dict[str, Any],
    base_terrain_config: Dict[str, Any],
    target_physics_config: Dict[str, Any] = None,
    base_physics_config: Dict[str, Any] = None,

) -> str:
    description = base_description
    return description

def update_success_criteria_for_visible_changes(base_success_criteria: str, target_terrain_config: Dict[str, Any], base_terrain_config: Dict[str, Any]) -> str:
    return base_success_criteria

def get_e03_curriculum_stages() -> List[Dict[str, Any]]:
    return [
        {
            "stage_id": "Stage-1",
            "title": "Environmental Adaptation I",
            "mutation_description": "Undisclosed physical properties differ from Initial.",
            "task_description_suffix": uniform_suffix_for_task("E_03"),
            "terrain_config": {
                "ground_friction": 1.0,
                "sled_friction": 1.0,
            },
            "physics_config": {
                "linear_damping": 0.8,
            },
        },
        {
            "stage_id": "Stage-2",
            "title": "Environmental Adaptation II",
            "mutation_description": "Undisclosed physical properties differ from Initial.",
            "task_description_suffix": uniform_suffix_for_task("E_03"),
            "terrain_config": {},
            "physics_config": {
                "gravity": (0, -15),
            },
        },
        {
            "stage_id": "Stage-3",
            "title": "Environmental Adaptation III",
            "mutation_description": "Undisclosed physical properties differ from Initial.",
            "task_description_suffix": uniform_suffix_for_task("E_03"),
            "terrain_config": {},
            "physics_config": {
                "momentum_drain_factor": 0.70,
                "linear_damping": 0.5,
            },
        },
        {
            "stage_id": "Stage-4",
            "title": "Environmental Adaptation IV",
            "mutation_description": "Undisclosed physical properties differ from Initial.",
            "task_description_suffix": uniform_suffix_for_task("E_03"),
            "terrain_config": {
                "ground_friction": 3.0,
                "sled_friction": 3.0,
            },
            "physics_config": {
                "gravity": (0, -18),
                "linear_damping": 5.0,
                "momentum_drain_factor": 0.30,
                "thrust_scale_factor": 0.06,
                "speed_penalty_threshold": 1.2,
                "speed_penalty_factor": 0.04,
            },
        },
    ]
