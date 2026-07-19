from __future__ import annotations

import re

from typing import Any, Dict, List

_DEFAULT_GRAVITY = (0, -10.0)

def update_task_description_for_visible_changes(
    base_description: str, target_terrain_config: Dict[str, Any], base_terrain_config: Dict[str, Any],
    target_physics_config: Dict[str, Any] = None, base_physics_config: Dict[str, Any] = None,

) -> str:
    description = base_description
    tx_min = target_terrain_config.get("target_x_min")
    tx_max = target_terrain_config.get("target_x_max")
    ty_min = target_terrain_config.get("target_y_min")
    ty_max = target_terrain_config.get("target_y_max")
    base_tx_min = base_terrain_config.get("target_x_min", 40.0)
    base_tx_max = base_terrain_config.get("target_x_max", 45.0)
    base_ty_min = base_terrain_config.get("target_y_min", 2.0)
    base_ty_max = base_terrain_config.get("target_y_max", 5.0)
    out = description
    if tx_min is not None and tx_max is not None and (tx_min != base_tx_min or tx_max != base_tx_max):
        out = re.sub(r"x from 40 m to 45 m", f"x from {tx_min:.0f} m to {tx_max:.0f} m (originally x from {base_tx_min:.0f} m to {base_tx_max:.0f} m in the source environment)", out)
    if ty_min is not None and ty_max is not None and (ty_min != base_ty_min or ty_max != base_ty_max):
        out = re.sub(r"y from 2 m to 5 m", f"y from {ty_min:.0f} m to {ty_max:.0f} m (originally y from {base_ty_min:.0f} m to {base_ty_max:.0f} m in the source environment)", out)
    return out

def update_success_criteria_for_visible_changes(
    base_success_criteria: str, target_terrain_config: Dict[str, Any], base_terrain_config: Dict[str, Any]

) -> str:
    tx_min = target_terrain_config.get("target_x_min")
    tx_max = target_terrain_config.get("target_x_max")
    ty_min = target_terrain_config.get("target_y_min")
    ty_max = target_terrain_config.get("target_y_max")
    base_tx_min = base_terrain_config.get("target_x_min", 40.0)
    base_tx_max = base_terrain_config.get("target_x_max", 45.0)
    base_ty_min = base_terrain_config.get("target_y_min", 2.0)
    base_ty_max = base_terrain_config.get("target_y_max", 5.0)
    out = base_success_criteria
    if tx_min is not None and tx_max is not None and (tx_min != base_tx_min or tx_max != base_tx_max):
        out = re.sub(
            r"x in \[40, 45\] m",
            f"x in [{tx_min:.0f}, {tx_max:.0f}] m (originally [{base_tx_min:.0f}, {base_tx_max:.0f}] m in the source environment)",
            out,
        )
    if ty_min is not None and ty_max is not None and (ty_min != base_ty_min or ty_max != base_ty_max):
        out = re.sub(
            r"y in \[2, 5\] m",
            f"y in [{ty_min:.0f}, {ty_max:.0f}] m (originally [{base_ty_min:.0f}, {base_ty_max:.0f}] m in the source environment)",
            out,
        )
    return out

_D01_SUFFIX = """

Sensors indicate that this region exhibits non-standard physical properties.
While the following variables **MIGHT** have changed from the initial environment, **NOT ALL** of them will necessarily be mutated in any given task. You must use active interaction and environmental feedback to deduce which specific conditions apply:
- **Air Resistance**: Atmospheric drag properties may differ from the initial environment.
- **Target Zone Position**: The coordinates of the destination region may differ from the initial environment.
- **Gravity**: The gravitational field may differ from the initial environment.
- **Linear Damping**: The linear velocity damping coefficient for dynamic bodies may differ from the initial environment.
- **Angular Damping**: The angular velocity damping coefficient for dynamic bodies may differ from the initial environment.

**Discovery via feedback**: Your objective is to identify the underlying physical rules of this specific environment through trial and reasoning. Initial standard solutions may fail; analyze the failure mode to infer the hidden constraints and adapt your design.
"""

def get_d01_curriculum_stages() -> List[Dict[str, Any]]:
    return [
        {
            "stage_id": "Stage-1",
            "title": "The Dense Atmosphere",
            "mutation_description": "Air resistance (linear/angular damping) increased. Projectile loses energy in flight.",
            "task_description_suffix": _D01_SUFFIX,
            "terrain_config": {},
            "physics_config": {
                "linear_damping": 2.5,
                "angular_damping": 2.5,
            },
        },
        {
            "stage_id": "Stage-2",
            "title": "The Distant Target",
            "mutation_description": "Target zone moved further (visible change).",
            "task_description_suffix": _D01_SUFFIX,
            "terrain_config": {
                "target_x_min": 50.0,
                "target_x_max": 55.0,
                "target_y_min": 2.0,
                "target_y_max": 5.0,
            },
            "physics_config": {},
        },
        {
            "stage_id": "Stage-3",
            "title": "Heavy World and Drag",
            "mutation_description": "Gravity altered (heavier world) with air resistance (damping) increased. Dual invisible params.",
            "task_description_suffix": _D01_SUFFIX,
            "terrain_config": {},
            "physics_config": {
                "gravity": (0, -15.0),
                "linear_damping": 1.5,
                "angular_damping": 1.5,
            },
        },
        {
            "stage_id": "Stage-4",
            "title": "Extreme Range and Conditions",
            "mutation_description": "Target zone moved further (visible change) with heavier gravity and increased air resistance. Multiple invisible parameters are altered simultaneously.",
            "task_description_suffix": _D01_SUFFIX,
            "terrain_config": {
                "target_x_min": 52.0,
                "target_x_max": 57.0,
                "target_y_min": 2.0,
                "target_y_max": 5.0,
            },
            "physics_config": {
                "gravity": (0, -18.0),
                "linear_damping": 1.2,
                "angular_damping": 1.2,
            },
        },
    ]
