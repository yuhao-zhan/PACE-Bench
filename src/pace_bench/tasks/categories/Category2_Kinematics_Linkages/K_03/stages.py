from __future__ import annotations

from pace_bench.tasks.stage_prompt import uniform_suffix_for_task

from typing import Any, Dict, List

import re

def update_task_description_for_visible_changes(
    base_description: str,
    target_terrain_config: Dict[str, Any],
    base_terrain_config: Dict[str, Any],
    target_physics_config: Dict[str, Any] = None,
    base_physics_config: Dict[str, Any] = None,

) -> str:
    description = base_description
    target_physics_config = target_physics_config or {}
    base_physics_config = base_physics_config or {}
    target_obj = target_terrain_config.get("objects", {})
    base_obj = base_terrain_config.get("objects", {})
    target_shape = target_obj.get("shape", "box")
    base_shape = base_obj.get("shape", "box")
    if target_shape != base_shape:
        names = {"box": "rectangular block", "circle": "circular disk", "triangle": "triangular block"}
        base_name = names.get(base_shape, str(base_shape))
        target_name = names.get(target_shape, str(target_shape))
        shape_pattern = rf"(\*\*Target Object\*\*: )A {re.escape(base_name)}"
        description, replacements = re.subn(
            shape_pattern,
            rf"\1A {target_name} (originally a {base_name})",
            description,
            count=1,
        )
        if replacements != 1:
            raise ValueError(f"K_03 visible shape update expected 1 replacement, got {replacements}")
    return description

def update_success_criteria_for_visible_changes(base_success_criteria: str, target_terrain_config: Dict[str, Any], base_terrain_config: Dict[str, Any]) -> str:
    return base_success_criteria

def get_k03_curriculum_stages():
    task_description_suffix = uniform_suffix_for_task("K_03")
    return [
        {
            "stage_id": "Stage-1",
            "title": "Slippery Object",
            "mutation_description": "Target is a circular (disk) object with reduced surface friction. Added stabilization damping.",
            "task_description_suffix": uniform_suffix_for_task("K_03"),
            "terrain_config": {"objects": {"shape": "circle", "mass": 1.0, "friction": 0.25, "x": 5.0, "y": 2.0}},
            "physics_config": {"linear_damping": 0.5, "angular_damping": 0.5},
        },
        {
            "stage_id": "Stage-2",
            "title": "Crushing Gravity",
            "mutation_description": "Extreme gravity (3x); object mass increased 10x. Damping present.",
            "task_description_suffix": uniform_suffix_for_task("K_03"),
            "terrain_config": {"objects": {"shape": "box", "mass": 10.0, "friction": 0.6, "x": 5.0, "y": 2.0}},
            "physics_config": {"gravity": (0, -30.0), "linear_damping": 0.5, "angular_damping": 0.5},
        },
        {
            "stage_id": "Stage-3",
            "title": "Slippery Object + Heavy World + Damping",
            "mutation_description": "Object friction reduced; gravity increased; object mass increased; atmospheric damping present.",
            "task_description_suffix": uniform_suffix_for_task("K_03"),
            "terrain_config": {"objects": {"shape": "box", "mass": 5.0, "friction": 0.2, "x": 5.0, "y": 2.0}},
            "physics_config": {
                "gravity": (0, -20.0),
                "linear_damping": 0.5,
                "angular_damping": 0.5,
            },
        },
        {
            "stage_id": "Stage-4",
            "title": "Circular Object + Slippery + Heavy + Damping",
            "mutation_description": "Target is a circular object (disk) with reduced friction; gravity increased; object mass increased; damping present.",
            "task_description_suffix": uniform_suffix_for_task("K_03"),
            "terrain_config": {"objects": {"shape": "circle", "mass": 5.0, "friction": 0.2, "x": 5.0, "y": 2.0}},
            "physics_config": {
                "gravity": (0, -20.0),
                "linear_damping": 0.5,
                "angular_damping": 0.5,
            },
        },
    ]
