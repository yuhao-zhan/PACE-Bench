from __future__ import annotations

import math

from typing import Any, Dict, List

import re

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
    target_terrain_config = target_terrain_config or {}
    base_terrain_config = base_terrain_config or {}
    if stage is not None:
        target_physics_config = dict(stage.get("physics_config") or {})
        base_physics_config = {}
    target_physics_config = target_physics_config or {}
    base_physics_config = base_physics_config or {}
    default_y_max = 25.0
    target_y_max = target_terrain_config.get("build_zone_y_max", default_y_max)
    base_y_max = base_terrain_config.get("build_zone_y_max", default_y_max)
    if target_y_max != base_y_max:
        build_zone_pattern = r"(y=\[0, )(\d+\.?\d*)(\])"
        if re.search(build_zone_pattern, description):
            description = re.sub(
                build_zone_pattern,
                f"\\g<1>{target_y_max:.1f}\\g<3> (originally y=[0, {base_y_max:.1f}] in the source environment)",
                description
            )
    default_min_mass = 0.0
    target_min_mass = target_terrain_config.get("min_structure_mass", default_min_mass)
    base_min_mass = base_terrain_config.get("min_structure_mass", default_min_mass)
    if target_min_mass != base_min_mass:
        min_mass_pattern = r"(Total structure mass must be at least )(\d+\.?\d*)( kg and less than )(\d+\.?\d*)( kg\.)"
        if re.search(min_mass_pattern, description):
            description = re.sub(
                min_mass_pattern,
                f"\\g<1>{target_min_mass:.1f} kg (originally {base_min_mass:.1f} kg in the source environment) and less than \\g<4>\\g<5>",
                description
            )
    default_max_mass = 50.0
    target_max_mass = target_terrain_config.get("max_structure_mass", default_max_mass)
    base_max_mass = base_terrain_config.get("max_structure_mass", default_max_mass)
    if target_max_mass != base_max_mass:
        max_mass_pattern = r"( and less than )(\d+\.?\d*)( kg\.)"
        if re.search(max_mass_pattern, description):
            description = re.sub(
                max_mass_pattern,
                f"\\g<1>{target_max_mass:.0f} kg (originally {base_max_mass:.0f} kg in the source environment).",
                description
            )
    inf_val = float("inf")
    default_joint_force = inf_val
    default_joint_torque = inf_val
    target_joint_force = target_physics_config.get("max_joint_force", default_joint_force)
    target_joint_torque = target_physics_config.get("max_joint_torque", default_joint_torque)
    base_joint_force = base_physics_config.get("max_joint_force", default_joint_force)
    base_joint_torque = base_physics_config.get("max_joint_torque", default_joint_torque)
    force_changed = target_joint_force != base_joint_force and target_joint_force != inf_val
    torque_changed = target_joint_torque != base_joint_torque and target_joint_torque != inf_val
    if force_changed or torque_changed:
        joint_strength_pattern = r"(- \*\*Joint strength\*\*: )(Maximum joint reaction force and maximum joint torque are unlimited in the default environment \(joints do not break\)\.)"
        base_force_str = "unlimited" if base_joint_force == inf_val else f"{base_joint_force:.1f} N"
        base_torque_str = "unlimited" if base_joint_torque == inf_val else f"{base_joint_torque:.1f} N·m"
        if force_changed and torque_changed:
            new_str = (
                f"Maximum joint reaction force is limited to {target_joint_force:.1f} N and maximum joint torque "
                f"to {target_joint_torque:.1f} N·m (joints break if exceeded; originally unlimited in the default environment)."
            )
        elif force_changed:
            new_str = (
                f"Maximum joint reaction force is limited to {target_joint_force:.1f} N (joints break if exceeded; "
                f"maximum joint torque {base_torque_str}; originally unlimited in the default environment)."
            )
        else:
            new_str = (
                f"Maximum joint torque is limited to {target_joint_torque:.1f} N·m (joints break if exceeded; "
                f"maximum joint reaction force {base_force_str}; originally unlimited in the default environment)."
            )
        if re.search(joint_strength_pattern, description):
            description = re.sub(joint_strength_pattern, r"\g<1>" + new_str, description)
    target_sz = target_terrain_config.get("suction_zones") if target_terrain_config else None
    base_sz = base_terrain_config.get("suction_zones") if base_terrain_config else None
    sz_changed = target_sz != base_sz
    if sz_changed and target_sz is not None:
        bands_str = ", ".join(f"[{z[0]:.0f}, {z[1]:.0f}]" for z in target_sz)
        if base_sz is None:
            orig_sz_str = "everywhere (no gaps in the default environment)"
        else:
            orig_bands_str = ", ".join(f"[{z[0]:.0f}, {z[1]:.0f}]" for z in base_sz)
            orig_sz_str = f"bands: {orig_bands_str} in the source environment"
        description += (
            f"\n- **Wall adhesion bands**: Adhesive pads may only engage in these altitude ranges (m): {bands_str} "
            f"({orig_sz_str}). Outside these bands, wall adhesion may not behave as in the default environment.\n"
        )
    return description

def update_success_criteria_for_visible_changes(base_success_criteria: str, target_terrain_config: Dict[str, Any], base_terrain_config: Dict[str, Any]) -> str:
    criteria = base_success_criteria
    default_y_max = 25.0
    target_y_max = target_terrain_config.get("build_zone_y_max", default_y_max)
    base_y_max = base_terrain_config.get("build_zone_y_max", default_y_max)
    if target_y_max != base_y_max:
        build_zone_pattern = r"(y=\[0, )(\d+\.?\d*)(\])"
        if re.search(build_zone_pattern, criteria):
            criteria = re.sub(
                build_zone_pattern,
                f"\\g<1>{target_y_max:.1f}\\g<3> (originally y=[0, {base_y_max:.1f}] in the source environment)",
                criteria
            )
    default_min_mass = 0.0
    target_min_mass = target_terrain_config.get("min_structure_mass", default_min_mass)
    base_min_mass = base_terrain_config.get("min_structure_mass", default_min_mass)
    if target_min_mass != base_min_mass:
        min_mass_criteria_pattern = r"(Minimum )(\d+\.?\d*)( kg, maximum)"
        if re.search(min_mass_criteria_pattern, criteria):
            criteria = re.sub(
                min_mass_criteria_pattern,
                f"\\g<1>{target_min_mass:.1f} kg (originally {base_min_mass:.1f} kg in the source environment), maximum",
                criteria
            )
    default_max_mass = 50.0
    target_max_mass = target_terrain_config.get("max_structure_mass", default_max_mass)
    base_max_mass = base_terrain_config.get("max_structure_mass", default_max_mass)
    if target_max_mass != base_max_mass:
        max_mass_criteria_pattern = r"(maximum < )(\d+\.?\d*)( kg\.)"
        if re.search(max_mass_criteria_pattern, criteria):
            criteria = re.sub(
                max_mass_criteria_pattern,
                f"\\g<1>{target_max_mass:.0f} kg (originally {base_max_mass:.0f} kg in the source environment).",
                criteria
            )
    return criteria

def get_k02_curriculum_stages() -> List[Dict[str, Any]]:
    task_description_suffix = """

Sensors indicate that this region exhibits non-standard physical properties.
While the following variables MIGHT have changed from the initial environment, NOT ALL of them will necessarily be mutated in any given task. You must use active interaction and environmental feedback to deduce which specific conditions apply:
 - **Build Zone (Vertical Extent)**: May differ from the default.
 - **Structural Integrity Thresholds (Joint Force/Torque)**: May differ from the default.
 - **Gravitational Acceleration**: May differ from the default.
 - **Surface Adhesion Gaps (Suction Zones)**: May differ from the default.
 - **Mass Budget Constraints (Min/Max Mass)**: May differ from the default.
 - **Atmospheric Turbulence (Wind/Vortex)**: May differ from the default.
 - **Rotational Damping**: May differ from the default.

Discovery via feedback: Your objective is to identify the underlying physical rules of this specific environment through trial and reasoning. Initial standard solutions may fail; analyze the failure mode to infer the hidden constraints and adapt your design.
"""
    return [
        {
            "stage_id": "Stage-1",
            "title": "Fragile Structural Integrity",
            "mutation_description": "Near-zero joint strength thresholds — only molecular-scale structures survive. Joints shatter under even minimal load.",
            "task_description_suffix": task_description_suffix,
            "terrain_config": {
                "build_zone_y_max": 5.0,
            },
            "physics_config": {
                "max_joint_force": 1.5,
                "max_joint_torque": 3.0,
            },
        },
        {
            "stage_id": "Stage-2",
            "title": "Gravitational Flux & Void Zones",
            "mutation_description": "Stronger gravity that increases over time, combined with a 3m suction gap. Forces high-power, long-reach climbing.",
            "task_description_suffix": task_description_suffix,
            "terrain_config": {
                "build_zone_y_max": 8.0,
                "suction_zones": [(0, 16), (19, 35)],
            },
            "physics_config": {
                "gravity": (0, -12.0),
                "gravity_evolution": -0.1,
            },
        },
        {
            "stage_id": "Stage-3",
            "title": "Resonant Interference Phase",
            "mutation_description": "Extreme gravity, ultra-narrow mass budget, fragile joints, and relentless lateral wind. The climber faces a web of conflicting constraints: dense builds break joints, light builds violate mass thresholds, and gravity intensifies rapidly.",
            "task_description_suffix": task_description_suffix,
            "terrain_config": {
                "build_zone_y_max": 5.0,
                "min_structure_mass": 41.0,
                "max_structure_mass": 44.0,
                "wind_force": -18.0,
            },
            "physics_config": {
                "max_joint_force": 2200.0,
                "max_joint_torque": 640.0,
                "gravity": (0, -24.0),
                "gravity_evolution": -0.25,
                "angular_damping": 6.0,
            },
        },
        {
            "stage_id": "Stage-4",
            "title": "The Resonant Singularity",
            "mutation_description": "Extreme suction adhesion gaps combined with lateral wind and height-triggered vortex forces. Forces ultra-long-reach precision.",
            "task_description_suffix": task_description_suffix,
            "terrain_config": {
                "build_zone_y_max": 5.0,
                "min_structure_mass": 25.0,
                "wind_force": -15.0,
                "vortex_y": 5.0,
                "vortex_force_x": 15.0,
                "vortex_force_y": -5.0,
                "suction_zones": [(0, 7), (9, 16), (18, 25), (27, 35)],
            },
            "physics_config": {
                "max_joint_force": 3000.0,
            },
        },
    ]
