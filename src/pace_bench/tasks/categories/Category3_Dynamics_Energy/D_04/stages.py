from __future__ import annotations

from typing import Any, Dict, List

def get_d04_curriculum_stages() -> List[Dict[str, Any]]:
    union_variables = {
        "Actuator Dead Zone": "The swing's primary force thrusters may exhibit spatial or engagement anomalies; use feedback to infer where and when thrust is available.",
        "Quadratic Damping Anomaly": "The environment may exhibit anomalous energy dissipation; use feedback to infer the actual behavior.",
        "Directional Actuator Fault": "The force actuators may exhibit directional or engagement anomalies; use feedback to infer how thrust is available.",
        "Extreme Atmospheric Conditions": "Atmospheric or wind conditions may differ from the initial environment in ways that affect the swing's equilibrium and trajectory; use feedback to infer the actual behavior.",
    }
    bullet_points = "\n".join([f" - **{k}**: {v}" for k, v in union_variables.items()])
    _D04_SUFFIX = f"""

Sensors indicate that this region exhibits non-standard physical properties.
While the following variables **MIGHT** have changed from the initial environment, **NOT ALL** of them will necessarily be mutated in any given task. You must use active interaction and environmental feedback to deduce which specific conditions apply:
{bullet_points}

**Discovery via feedback**: Your objective is to identify the underlying physical rules of this specific environment through trial and reasoning. Initial standard solutions may fail; analyze the failure mode (e.g., where a joint breaks or how a body moves) to infer the hidden constraints and adapt your design.
"""
    return [
        {
            "stage_id": "Stage-1",
            "title": "The Velocity-Gated Dead Zone",
            "mutation_description": "Actuator fails in an asymmetric central region unless horizontal speed exceeds a critical threshold; thrust is only available in narrow side bands or when crossing the zone at high speed—discovery of the velocity-gate and side-band strategy is required.",
            "task_description_suffix": _D04_SUFFIX,
            "terrain_config": {
                "dead_zone": [9.5, 11.0],
                "dead_zone_min_speed": 14.0,
            },
            "physics_config": {},
        },
        {
            "stage_id": "Stage-2",
            "title": "Quadratic Energy Drain",
            "mutation_description": "Extreme quadratic damping penalizes any motion; drag approaches max pump force at peak swing speeds, making horizontal-only pumping self-defeating. Requires velocity-aligned continuous energy injection and careful phase-timing to accumulate net energy per cycle.",
            "task_description_suffix": _D04_SUFFIX,
            "terrain_config": {
                "quadratic_damping": 0.36,
            },
            "physics_config": {},
        },
        {
            "stage_id": "Stage-3",
            "title": "One-Way Actuator & Gale",
            "mutation_description": "Directional actuator fault combined with strong constant wind; thrust is available in only one horizontal direction and wind acts in a fixed direction. The agent must discover which directions apply via feedback.",
            "task_description_suffix": _D04_SUFFIX,
            "terrain_config": {
                "actuator_fault": "left_only",
                "wind_strength": 30.0,
                "wind_period": 0.0,
            },
            "physics_config": {},
        },
        {
            "stage_id": "Stage-4",
            "title": "The Ultimate Crucible",
            "mutation_description": "Combined directional actuator fault, central dead zone, quadratic damping, and strong constant wind; all directions and magnitudes must be inferred from feedback.",
            "task_description_suffix": _D04_SUFFIX,
            "terrain_config": {
                "actuator_fault": "right_only",
                "dead_zone": [9.8, 10.2],
                "quadratic_damping": 0.10,
                "wind_strength": -25.0,
                "wind_period": 0.0,
            },
            "physics_config": {},
        },
    ]

def update_task_description_for_visible_changes(
    base_description: str,
    target_terrain_config: Dict[str, Any],
    base_terrain_config: Dict[str, Any],
    target_physics_config: Dict[str, Any] = None,
    base_physics_config: Dict[str, Any] = None,
    *,
    stage: Dict[str, Any] = None,

) -> str:
    return base_description

def update_success_criteria_for_visible_changes(
    base_success_criteria: str,
    target_terrain_config: Dict[str, Any],
    base_terrain_config: Dict[str, Any],
    *,
    stage: Dict[str, Any] = None,

) -> str:
    description = base_success_criteria
    import re
    base_dz = base_terrain_config.get("dead_zone")
    target_dz = target_terrain_config.get("dead_zone")
    base_dz_min_spd = base_terrain_config.get("dead_zone_min_speed")
    target_dz_min_spd = target_terrain_config.get("dead_zone_min_speed")
    if target_dz is not None:
        dz_x0, dz_x1 = target_dz[0], target_dz[1]
        if base_dz is None:
            dz_note = (
                f"Dead Zone**: The force actuators may exhibit a spatial dead zone in which force "
                f"application is suppressed unless the seat's horizontal speed exceeds a minimum "
                f"threshold. Active dead zone x in [{dz_x0:.1f}, {dz_x1:.1f}] m"
                + (f", min speed {target_dz_min_spd:.1f} m/s" if target_dz_min_spd else "")
                + " (originally no dead zone is active in the source environment)."
            )
        else:
            bz0, bz1 = base_dz[0], base_dz[1]
            dz_note = (
                f"Dead Zone**: The force actuators may exhibit a spatial dead zone in which force "
                f"application is suppressed unless the seat's horizontal speed exceeds a minimum "
                f"threshold. Active dead zone x in [{dz_x0:.1f}, {dz_x1:.1f}] m"
                + (f", min speed {target_dz_min_spd:.1f} m/s" if target_dz_min_spd else "")
                + f" (originally x in [{bz0:.1f}, {bz1:.1f}] m"
                + (f", min speed {base_dz_min_spd:.1f} m/s" if base_dz_min_spd else "")
                + " in the source environment)."
            )
        dz_pat = r"(- \*\*Dead Zone\*\*: .*?)(?:\n|$)"
        if re.search(dz_pat, description):
            description = re.sub(dz_pat, f"- **{dz_note}\n", description)
    base_fault = base_terrain_config.get("actuator_fault")
    target_fault = target_terrain_config.get("actuator_fault")
    if target_fault != base_fault:
        fault_val = "no actuator fault is active" if target_fault is None else f"actuator fault: {target_fault}"
        fault_orig = "no actuator fault is active" if base_fault is None else f"actuator fault: {base_fault}"
        fault_pat = r"(- \*\*Actuator Fault\*\*: .*?)(?:\n|$)"
        if re.search(fault_pat, description):
            description = re.sub(
                fault_pat,
                f"- **Actuator Fault**: The force actuators may fail to produce thrust in one or "
                f"more directions. {fault_val} (originally {fault_orig} in the source environment).\n",
                description,
            )
    return description
