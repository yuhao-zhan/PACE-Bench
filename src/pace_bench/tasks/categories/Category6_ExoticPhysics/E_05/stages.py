from __future__ import annotations

import re

from typing import Any, Dict, List

_DEFAULT_MAGNETS = [
    (12.0, 4.0, -300.0), (12.0, 5.0, -300.0), (12.0, 6.0, -300.0),
    (12.0, 7.0, -300.0), (12.0, 8.0, -280.0), (12.0, 8.3, -260.0),
    (11.0, 9.7, -200.0), (13.0, 9.7, -200.0), (15.0, 9.7, -200.0),
    (17.0, 9.7, -200.0), (19.0, 9.7, -200.0), (21.0, 9.7, -180.0),
    (15.0, 9.0, -250.0, 230.0, 0.12), (20.0, 9.0, -350.0, 330.0, 0.15, 3.14159),
    (19.0, 3.0, 160.0), (21.0, 3.5, 130.0),
    (24.0, 5.0, -190.0), (24.0, 8.2, -180.0),
    (24.0, 6.6, -180.0, 160.0, 0.165),
    (26.0, 5.5, -130.0), (27.0, 9.5, -120.0), (29.5, 7.5, 95.0),

]

def _magnets_stage1() -> List[tuple]:
    return [(14.0, y, -800.0) for y in range(0, 15)]

def _magnets_stage2() -> List[tuple]:
    return [tuple(x) for x in _DEFAULT_MAGNETS]

def _magnets_stage3() -> List[tuple]:
    return [
        (12.0, 4.0, -420.0), (12.0, 5.0, -420.0), (12.0, 6.0, -420.0),
        (12.0, 7.0, -420.0), (12.0, 8.0, -400.0), (12.0, 8.3, -380.0),
        (11.0, 9.7, -280.0), (13.0, 9.7, -280.0), (15.0, 9.7, -280.0),
        (17.0, 9.7, -280.0), (19.0, 9.7, -280.0), (21.0, 9.7, -260.0),
        (15.0, 9.0, -420.0, 380.0, 0.12),
        (20.0, 9.0, -480.0, 440.0, 0.15, 3.14159),
        (19.0, 3.0, 320.0), (21.0, 3.5, 280.0),
        (24.0, 5.0, -250.0), (24.0, 8.2, -240.0),
        (24.0, 6.6, -240.0, 200.0, 0.165),
        (26.0, 5.5, -190.0), (27.0, 9.5, -190.0),
        (29.5, 7.5, 95.0),
    ]

def _magnets_stage4() -> List[tuple]:
    magnets = []

    magnets.append((20.0, 8.0, -250.0, 240.0, 0.12))

    magnets.append((12.0, 7.0, -80.0))
    magnets.append((16.0, 7.0, -60.0))
    magnets.append((24.0, 7.0, -90.0))
    magnets.append((28.0, 7.0, -70.0))

    magnets.append((29.5, 7.5, 120.0))
    magnets.append((30.0, 8.0, 80.0))
    return magnets

UNIFORM_SUFFIX = """

Sensors indicate that this region exhibits non-standard physical properties.
While the following variables **MIGHT** have changed from the initial environment, **NOT ALL** of them will necessarily be mutated in any given task. You must use active interaction and environmental feedback to deduce which specific conditions apply:
- **Electromagnetic Fields**: The spatial layout and strength of repulsive walls or attractive nodes may differ from the source environment.
- **Gravitational acceleration**: The gravitational field may differ from the source environment.
- **Motion Damping**: Environmental friction and air resistance may differ from the source environment.
- **Maximum Thrust**: The engine's thrust output limit may differ from the source environment.

**Discovery via feedback**: Your objective is to identify the underlying physical rules of this specific environment through trial and reasoning. Initial standard solutions may fail; analyze the failure mode (e.g., where the body gets stuck or how it responds to thrust) to infer the hidden constraints and adapt your design.
"""

_DEFAULT_MAX_THRUST = 165.0

_DEFAULT_GRAVITY = (0, -10.0)

_DEFAULT_LINEAR_DAMPING = 0.28

_DEFAULT_ANGULAR_DAMPING = 0.15

def update_task_description_for_visible_changes(base_description: str, target_terrain_config: Dict[str, Any], base_terrain_config: Dict[str, Any], target_physics_config: Dict[str, Any] = None, base_physics_config: Dict[str, Any] = None) -> str:
    description = base_description
    target_terrain_config = target_terrain_config or {}
    base_terrain_config = base_terrain_config or {}
    target_physics_config = target_physics_config or {}
    base_physics_config = base_physics_config or {}
    target_max_thrust = float(target_terrain_config.get("max_thrust", _DEFAULT_MAX_THRUST))
    base_max_thrust = float(base_terrain_config.get("max_thrust", _DEFAULT_MAX_THRUST))
    if target_max_thrust != base_max_thrust:
        thrust_cap_pattern = r"(- \*\*Maximum Thrust\*\*:.*?must not exceed )(\d+\.?\d*)( \(engine limit\)\.)"
        if re.search(thrust_cap_pattern, description):
            description = re.sub(
                thrust_cap_pattern,
                lambda m: f"{m.group(1)}{target_max_thrust:.1f} (originally {base_max_thrust:.1f} in the source environment){m.group(3)}",
                description,
            )
    return description

def update_success_criteria_for_visible_changes(base_success_criteria: str, target_terrain_config: Dict[str, Any], base_terrain_config: Dict[str, Any]) -> str:
    criteria = base_success_criteria
    target_terrain_config = target_terrain_config or {}
    base_terrain_config = base_terrain_config or {}
    target_max_thrust = float(target_terrain_config.get("max_thrust", _DEFAULT_MAX_THRUST))
    base_max_thrust = float(base_terrain_config.get("max_thrust", _DEFAULT_MAX_THRUST))
    if target_max_thrust != base_max_thrust:
        thrust_constraint_pattern = r"(- \*\*Maximum Thrust\*\*:.*?must not exceed )(\d+\.?\d*)( \(engine limit\)\.)"
        if re.search(thrust_constraint_pattern, criteria):
            criteria = re.sub(
                thrust_constraint_pattern,
                lambda m: f"{m.group(1)}{target_max_thrust:.1f} (originally {base_max_thrust:.1f} in the source environment){m.group(3)}",
                criteria,
            )
    return criteria

def get_e05_curriculum_stages() -> List[Dict[str, Any]]:
    return [
        {
            "stage_id": "Stage-1",
            "title": "Electromagnetic Corridor Variant",
            "mutation_description": "Electromagnetic layout completely replaced by an altered field configuration.",
            "task_description_suffix": UNIFORM_SUFFIX,
            "terrain_config": {
                "magnets": _magnets_stage1(),
            },
            "physics_config": {},
        },
        {
            "stage_id": "Stage-2",
            "title": "Zero-G Microgravity",
            "mutation_description": "Gravitational acceleration changed to (0, 0.0) (originally (0, -10.0) in the source environment). Complete absence of gravity means no natural reference direction — any thrust results in unopposed acceleration, and the body drifts freely under magnetic forces alone.",
            "task_description_suffix": UNIFORM_SUFFIX,
            "terrain_config": {
                "magnets": _magnets_stage2(),
            },
            "physics_config": {
                "gravity": (0, 0.0),
            },
        },
        {
            "stage_id": "Stage-3",
            "title": "Viscous Abyss",
            "mutation_description": "Gravitational acceleration changed to (0, -28.0) (originally (0, -10.0) in the source environment). Maximum thrust cap changed to 420.0 (originally 165.0 in the source environment). Linear damping coefficient changed to 8.0 (originally 0.28 in the source environment). Angular damping coefficient changed to 4.0 (originally 0.15 in the source environment). Electromagnetic field strengths intensified across all repulsive walls, oscillating gates, and pit-zone attractors. High gravity consumes most thrust for hovering, while extreme viscous drag absorbs nearly all remaining lateral thrust. Every forward movement requires precise timing with oscillating gate weak windows.",
            "task_description_suffix": UNIFORM_SUFFIX,
            "terrain_config": {
                "magnets": _magnets_stage3(),
                "max_thrust": 420.0,
            },
            "physics_config": {
                "gravity": (0, -28.0),
                "linear_damping": 8.0,
                "angular_damping": 4.0,
            },
        },
        {
            "stage_id": "Stage-4",
            "title": "Event Horizon",
            "mutation_description": "Gravitational acceleration changed to (0, -51.0) (originally (0, -10.0) in the source environment). Maximum thrust cap changed to 580.0 (originally 165.0 in the source environment). Linear damping coefficient changed to 10.0 (originally 0.28 in the source environment). Angular damping coefficient changed to 5.0 (originally 0.15 in the source environment). Near-crushing gravity combined with magnetic down-force consumes ~95% of thrust just to stay airborne; extreme viscous drag absorbs nearly all remaining lateral thrust. Every forward centimeter requires perfect synchronization with gate cycles.",
            "task_description_suffix": UNIFORM_SUFFIX,
            "terrain_config": {
                "magnets": _magnets_stage4(),
                "max_thrust": 580.0,
            },
            "physics_config": {
                "gravity": (0, -51.0),
                "linear_damping": 10.0,
                "angular_damping": 5.0,
            },
        },
    ]
