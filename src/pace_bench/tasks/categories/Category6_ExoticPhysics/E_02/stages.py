from __future__ import annotations

import re

from typing import Any, Dict, List

_DEFAULT_OVERHEAT_LIMIT = 72000.0

def update_task_description_for_visible_changes(
    base_description: str,
    target_terrain_config: Dict[str, Any],
    base_terrain_config: Dict[str, Any],
    target_physics_config: Dict[str, Any] = None,
    base_physics_config: Dict[str, Any] = None,
    *,
    stage: Dict[str, Any] = None,

) -> str:
    description = base_description
    target_physics_config = target_physics_config or {}
    base_physics_config = base_physics_config or {}
    if stage is not None:
        target_physics_config = dict(stage.get("physics_config") or {})
        base_physics_config = {}
    target_overheat = float(target_physics_config.get("overheat_limit", _DEFAULT_OVERHEAT_LIMIT))
    base_overheat = float(base_physics_config.get("overheat_limit", _DEFAULT_OVERHEAT_LIMIT))
    if target_overheat != base_overheat:
        pattern = r"(The overheat limit is )(\d+\.?\d*)( N·s; exceeding it causes mission failure\.)"
        if re.search(pattern, description):
            description = re.sub(
                pattern,
                lambda m: f"{m.group(1)}{target_overheat:.0f} N·s (originally {base_overheat:.0f} N·s in the source environment); exceeding it causes mission failure.",
                description,
            )
        elif f"The overheat limit is {target_overheat:.0f} N·s" not in description:
            old_line = f"The overheat limit is {base_overheat:.0f} N·s; exceeding it causes mission failure."
            new_line = f"The overheat limit is {target_overheat:.0f} N·s (originally {base_overheat:.0f} N·s in the source environment); exceeding it causes mission failure."
            description = description.replace(old_line, new_line)
    return description

def update_success_criteria_for_visible_changes(
    base_success_criteria: str,
    target_terrain_config: Dict[str, Any],
    base_terrain_config: Dict[str, Any],
    target_physics_config: Dict[str, Any] = None,
    base_physics_config: Dict[str, Any] = None,
    *,
    stage: Dict[str, Any] = None,

) -> str:
    criteria = base_success_criteria
    target_physics_config = target_physics_config or {}
    base_physics_config = base_physics_config or {}
    if stage is not None:
        target_physics_config = dict(stage.get("physics_config") or {})
        base_physics_config = {}
    target_overheat = float(target_physics_config.get("overheat_limit", _DEFAULT_OVERHEAT_LIMIT))
    base_overheat = float(base_physics_config.get("overheat_limit", _DEFAULT_OVERHEAT_LIMIT))
    if target_overheat != base_overheat:
        pattern = r"(2\. \*\*Thermal Safety\*\*: Craft heat stays below the overheat limit \()(\d+\.?\d*)( N·s\)\.\s*)"
        if re.search(pattern, criteria):
            criteria = re.sub(
                pattern,
                lambda m: f"{m.group(1)}{target_overheat:.0f} N·s) (originally {base_overheat:.0f} N·s in the source environment) at all times.\n\n",
                criteria,
            )
    return criteria

TASK_DESCRIPTION_SUFFIX = """

Sensors indicate that this region exhibits non-standard physical properties.
While the following variables **MIGHT** have changed from the initial environment,
**NOT ALL** of them will necessarily be mutated in any given task. You must use
active interaction and environmental feedback to deduce which specific conditions apply:
- **Atmospheric Properties**: Air resistance and motion drag may differ from the base environment.
- **Kinetic Dissipation**: Momentum drain and resistive forces in specific zones may be altered.
- **Motion Damping**: Linear damping may differ from standard values.
- **Propulsion Efficiency**: The total thrust budget before overheating may differ.
- **External Forces**: Constant horizontal or vertical body forces may be imposed on the craft.
- **Wind Disturbances**: Periodic vertical forces may have different characteristics.

The specific physical rules of this environment can be discovered through active
interaction and environmental feedback.
"""

def get_e02_curriculum_stages() -> List[Dict[str, Any]]:
    return [
        {
            "stage_id": "Stage-1",
            "title": "Constant Headwind (Lateral Bias)",
            "mutation_description": "A constant horizontal force pushes against the craft, requiring higher baseline thrust to maintain forward progress.",
            "task_description_suffix": TASK_DESCRIPTION_SUFFIX,
            "terrain_config": {},
            "physics_config": {
                "constant_force_x": -75.0,
            },
        },
        {
            "stage_id": "Stage-2",
            "title": "Relentless Updraft (Extreme Vertical Bias)",
            "mutation_description": "A massive constant upward force dwarfs gravity, requiring near-continuous maximum downward thrust just to maintain altitude. The extreme updraft makes low-clearance gate passage nearly impossible without precise counter-force management and altitude-aware throttle control.",
            "task_description_suffix": TASK_DESCRIPTION_SUFFIX,
            "terrain_config": {},
            "physics_config": {
                "constant_force_y": 500.0,
            },
        },
        {
            "stage_id": "Stage-3",
            "title": "Thermal Gauntlet (Multi-variable: Damping + Drain + Slip + Wind + Heat)",
            "mutation_description": "High atmospheric drag, near-total momentum drain, intense slip-back forces, strong oscillating crosswinds, and a severely constrained heat budget. Every corrective burst pushes the craft closer to thermal failure.",
            "task_description_suffix": TASK_DESCRIPTION_SUFFIX,
            "terrain_config": {},
            "physics_config": {
                "linear_damping": 10.0,
                "drain_velocity_factor": 0.04,
                "slip_backward_force": -110.0,
                "overheat_limit": 20000.0,
                "wind_amplitude": 50.0,
                "wind_omega": 0.20,
            },
        },
        {
            "stage_id": "Stage-4",
            "title": "The Perfect Storm (Extreme Multi-variable)",
            "mutation_description": "Relentless headwind, heightened atmospheric drag, violent oscillating crosswinds, crippling slip-zone forces, and a heat budget so constrained that every single newton of thrust must be accounted for. The agent faces an impossible trilemma: thrust too little and the headwind pins the craft backward; thrust too much and thermal failure is inevitable; spend too long in any hazard zone and the cumulative drain exhausts the budget.",
            "task_description_suffix": TASK_DESCRIPTION_SUFFIX,
            "terrain_config": {},
            "physics_config": {
                "linear_damping": 4.5,
                "constant_force_x": -48.0,
                "slip_backward_force": -75.0,
                "overheat_limit": 6000.0,
                "wind_amplitude": 105.0,
                "wind_omega": 0.48,
            },
        },
    ]
