from __future__ import annotations

from typing import Any, Dict, List

import re

def update_task_description_for_visible_changes(base_description: str, target_terrain_config: Dict[str, Any], base_terrain_config: Dict[str, Any], target_physics_config: Dict[str, Any] = None, base_physics_config: Dict[str, Any] = None, **kwargs) -> str:
    description = base_description
    target_physics_config = target_physics_config or {}
    base_physics_config = base_physics_config or {}
    target_terrain_config = target_terrain_config or {}
    base_terrain_config = base_terrain_config or {}
    for key, pattern, default, suffix in [
        ("max_joint_force", r"(- \*\*Joint Strength\*\*: Maximum linear force for a joint is )(\w+\.?\d*)", float('inf'), ";"),
        ("max_joint_torque", r"(; maximum torque is )(inf|\d+\.?\d*|unlimited)", float('inf'), ".")
    ]:
        target_val = target_physics_config.get(key, default)
        base_val = base_physics_config.get(key, default)
        if target_val != base_val:
            target_str = f"{target_val:.1f}" if target_val != float('inf') else "inf"
            base_str = f"{base_val:.1f}" if base_val != float('inf') else "inf"
            if re.search(pattern, description):
                description = re.sub(
                    pattern,
                    f"\\g<1>{target_str} (originally {base_str} in the source environment)",
                    description
                )
    return description

def update_success_criteria_for_visible_changes(base_success_criteria: str, target_terrain_config: Dict[str, Any], base_terrain_config: Dict[str, Any]) -> str:
    return base_success_criteria

def get_s02_curriculum_stages() -> List[Dict[str, Any]]:
    UNIFORM_SUFFIX = """

Sensors indicate that this region exhibits non-standard physical properties.
While the following variables **MIGHT** have changed from the initial environment, **NOT ALL** of them will necessarily be mutated in any given task. You must use active interaction and environmental feedback to deduce which specific conditions apply:
 - **Structural Integrity Thresholds**: Joints between beams may have altered breaking limits for both force and torque.
 - **Seismic Dynamics**: The foundation's oscillation pattern may differ from the initial environment.
 - **Atmospheric Loading**: Wind forces may differ in magnitude, application altitude, or shear behavior.
 - **Gravitational Constant**: The local gravitational acceleration may differ from standard Earth gravity, altering the weight of the structure.
 - **Seismic Frequency**: The rate at which the foundation oscillates may differ from the initial environment.
 - **Wind Application Altitude**: The altitude above which wind forces are applied may differ.
 - **Wind Shear Behavior**: The rate at which wind force scales with altitude may differ.

**Discovery via feedback**: Your objective is to identify the underlying physical rules of this specific environment through trial and reasoning. Initial standard solutions may fail; analyze the failure mode (e.g., where a joint breaks or how the tower sways) to infer the hidden constraints and adapt your design.
"""
    return [
        {
            "stage_id": "Stage-1",
            "title": "The Brittle Foundation",
            "mutation_description": "Near-zero structural torque and force limits. Any joint in any standard design will snap within milliseconds of the earthquake starting — the combined seismic and wind loads on normal structural mass instantly exceed the razor-thin joint margins. A heavy tower with even moderate joint count will suffer cascading joint failures from the base upward. Survival demands an ultra-light skeleton with maximum base width for torque distribution across as many connection points as possible, using the absolute minimum of joints and the lightest feasible materials.",
            "task_description_suffix": UNIFORM_SUFFIX,
            "terrain_config": {
            },
            "physics_config": {
                "max_joint_torque": 5000.0,
                "max_joint_force": 7000.0,
            },
        },
        {
            "stage_id": "Stage-2",
            "title": "The Glass Skeleton",
            "mutation_description": "Extremely brittle joints: the maximum torque any joint can withstand is reduced to a razor-thin margin. Every kilogram of structural mass and every millimeter of height multiplies the torque imposed by seismic acceleration and wind loading. Standard designs snap their base joints within milliseconds of the earthquake starting. Survival demands an ultra-light skeleton with the absolute minimum number of joints and the widest possible base to distribute torque across as many connection points as possible.",
            "task_description_suffix": UNIFORM_SUFFIX,
            "terrain_config": {
            },
            "physics_config": {
                "max_joint_torque": 5000.0,
            },
        },
        {
            "stage_id": "Stage-3",
            "title": "The Resonant Collapse",
            "mutation_description": "Near-resonant seismic frequency combined with elevated gravity and extremely brittle joints. The shifted earthquake frequency drives the tower near its fundamental sway mode, while heavier gravity amplifies joint loads. Joints fracture under forces that would be safe in any other environment. Survival demands an ultra-light structure with precision-tuned harmonic damping.",
            "task_description_suffix": UNIFORM_SUFFIX,
            "terrain_config": {
                "earthquake_amplitude": 0.6,
                "earthquake_frequency": 1.2,
            },
            "physics_config": {
                "gravity": (0, -11.5),
                "max_joint_force": 30000.0,
                "max_joint_torque": 35000.0,
            },
        },
        {
            "stage_id": "Stage-4",
            "title": "The Impossible Equilibrium",
            "mutation_description": "Brutal gravity (+80%) crushes any structure of normal mass, while razor-thin joint margins (13 kN force / 17 kNm torque) snap at the slightest imbalance. Every kilogram of material becomes a crushing liability, and even a handful of joints will fracture under the combined assault of seismic acceleration and wind loading. The sole path to survival: an ultra-light skeleton with surgical mass distribution that exploits a maximally wide base for torque distribution, keeping total mass under 10 kg so that even with joint damage the structure barely holds together through the storm.",
            "task_description_suffix": UNIFORM_SUFFIX,
            "terrain_config": {
                "earthquake_amplitude": 0.55,
                "earthquake_frequency": 2.0,
                "wind_force": 55.0,
                "wind_height_threshold": 17.0,
                "wind_shear_factor": 0.035,
            },
            "physics_config": {
                "gravity": (0, -18.0),
                "max_joint_force": 13000.0,
                "max_joint_torque": 17000.0,
            },
        },
    ]
