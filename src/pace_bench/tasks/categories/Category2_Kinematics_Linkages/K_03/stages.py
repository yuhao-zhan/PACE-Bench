from __future__ import annotations

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
    target_mass = float(target_obj.get("mass", 1.0))
    base_mass = float(base_obj.get("mass", 1.0))
    if target_shape != base_shape:
        shape_pattern = r"(- \*\*Target Object\*\*: )(An object|a \w+ \w+)( of mass.*)"
        if re.search(shape_pattern, description):
            shape_name = "a circular disk" if target_shape == "circle" else "a triangular block" if target_shape == "triangle" else "a rectangular block"
            orig_name = "a rectangular block" if base_shape == "box" else "a triangular block" if base_shape == "triangle" else "a circular disk"
            description = re.sub(
                shape_pattern,
                lambda m: f"{m.group(1)}{shape_name}{m.group(3)} (originally {orig_name} in the source environment)",
                description,
                count=1
            )
    if target_mass != base_mass:
        mass_pattern = r"(of mass )(\d+\.?\d*)( kg)(?! \()"
        if re.search(mass_pattern, description):
            description = re.sub(
                mass_pattern,
                lambda m: f"{m.group(1)}{target_mass}{m.group(3)} (originally {m.group(2)} kg in the source environment)",
                description,
                count=1,
            )
    target_friction = float(target_obj.get("friction", 0.6))
    base_friction = float(base_obj.get("friction", 0.6))
    if target_friction != base_friction:
        obj_friction_pattern = r"(with surface friction coefficient )(\d+\.?\d*)( at x=\d+\.?\d*m, y=\d+\.?\d*m)"
        if re.search(obj_friction_pattern, description):
            description = re.sub(
                obj_friction_pattern,
                lambda m: f"{m.group(1)}{target_friction}{m.group(3)} (originally {m.group(2)} in the source environment)",
                description,
                count=1,
            )
    return description

def update_success_criteria_for_visible_changes(base_success_criteria: str, target_terrain_config: Dict[str, Any], base_terrain_config: Dict[str, Any]) -> str:
    return base_success_criteria

def get_k03_curriculum_stages():
    task_description_suffix = """

Sensors indicate that this region exhibits non-standard physical properties.
While the following variables **MIGHT** have changed from the initial environment, **NOT ALL** of them will necessarily be mutated in any given task. You must use active interaction and environmental feedback to deduce which specific conditions apply:
 - **Target object shape**
 - **Object surface friction**
 - **Gravitational acceleration**
 - **Object mass**
 - **Linear Damping**
 - **Angular Damping**
"""
    return [
        {
            "stage_id": "Stage-1",
            "title": "Slippery Object",
            "mutation_description": "Target is a circular (disk) object with reduced surface friction. Added stabilization damping.",
            "task_description_suffix": task_description_suffix,
            "terrain_config": {"objects": {"shape": "circle", "mass": 1.0, "friction": 0.25, "x": 5.0, "y": 2.0}},
            "physics_config": {"linear_damping": 0.5, "angular_damping": 0.5},
        },
        {
            "stage_id": "Stage-2",
            "title": "Crushing Gravity",
            "mutation_description": "Extreme gravity (3x); object mass increased 10x. Damping present.",
            "task_description_suffix": task_description_suffix,
            "terrain_config": {"objects": {"shape": "box", "mass": 10.0, "friction": 0.6, "x": 5.0, "y": 2.0}},
            "physics_config": {"gravity": (0, -30.0), "linear_damping": 0.5, "angular_damping": 0.5},
        },
        {
            "stage_id": "Stage-3",
            "title": "Slippery Object + Heavy World + Damping",
            "mutation_description": "Object friction reduced; gravity increased; object mass increased; atmospheric damping present.",
            "task_description_suffix": task_description_suffix,
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
            "task_description_suffix": task_description_suffix,
            "terrain_config": {"objects": {"shape": "circle", "mass": 5.0, "friction": 0.2, "x": 5.0, "y": 2.0}},
            "physics_config": {
                "gravity": (0, -20.0),
                "linear_damping": 0.5,
                "angular_damping": 0.5,
            },
        },
    ]
