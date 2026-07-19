from __future__ import annotations

import re

from typing import Any, Dict, List

_DEFAULT_GRAVITY = (0, -10.0)

TASK_DESCRIPTION_SUFFIX = """

Sensors indicate that this region exhibits non-standard physical properties.
While the following variables **MIGHT** have changed from the initial environment, **NOT ALL** of them will necessarily be mutated in any given task. You must use active interaction and environmental feedback to deduce which specific conditions apply:
- **Surface Friction**: Resistance encountered when sliding or moving across the terrain may have changed.
- **Gravity**: The magnitude and direction of the gravitational acceleration may differ from standard.
- **Momentum Drain**: The rate at which the system loses momentum over time may be altered.
- **Motion Damping**: Linear damping may differ from standard values.
- **Atmospheric Damping**: Air resistance and motion drag may vary.
- **Propulsion Efficiency**: The scaling factor affecting thrust output may be adjusted.
- **Speed Limit Threshold**: The velocity threshold that triggers a severe speed reduction in certain zones may have changed.
- **Speed Penalty Factor**: The severity of the speed penalty applied when exceeding the threshold may be altered.

**Discovery via feedback**: Your objective is to identify the underlying physical rules of this specific environment through trial and reasoning. Initial standard solutions may fail; analyze the failure mode (e.g., how the sled loses speed, fails to reach a checkpoint, or overshoots the target) to infer the hidden constraints and adapt your design.
"""

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
            "title": "Higher global friction + damping",
            "mutation_description": "Ground and sled friction increased (0.02 -> 1.0) plus linear_damping 0.8. Momentum is lost faster; ref's fixed gains may not overcome drain zone in time.",
            "task_description_suffix": TASK_DESCRIPTION_SUFFIX,
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
            "title": "Stronger gravity",
            "mutation_description": "Gravity increased (0, -10) -> (0, -15). Vertical control harder; ref's gravity compensation and climb to checkpoint A may be insufficient.",
            "task_description_suffix": TASK_DESCRIPTION_SUFFIX,
            "terrain_config": {},
            "physics_config": {
                "gravity": (0, -15),
            },
        },
        {
            "stage_id": "Stage-3",
            "title": "Stronger drain + damping",
            "mutation_description": "Momentum drain factor 0.85 -> 0.70; linear_damping 0.5. Velocity decays faster; ref may not reach B or final target in time.",
            "task_description_suffix": TASK_DESCRIPTION_SUFFIX,
            "terrain_config": {},
            "physics_config": {
                "momentum_drain_factor": 0.70,
                "linear_damping": 0.5,
            },
        },
        {
            "stage_id": "Stage-4",
            "title": "Crushing multi-parameter extreme",
            "mutation_description": "Gravity (0,-18), friction 3.0, linear_damping 5.0, momentum_drain 0.30, thrust_scale 0.06, speed_penalty threshold 1.2 + factor 0.04. Ref's weak gains fail instantly; agent must overcome crippling drain+damping while surviving thrust-scale near checkpoint A and speed-penalty zone — conflicting pressures: go fast to beat drain but stay slow to avoid speed penalty.",
            "task_description_suffix": TASK_DESCRIPTION_SUFFIX,
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
