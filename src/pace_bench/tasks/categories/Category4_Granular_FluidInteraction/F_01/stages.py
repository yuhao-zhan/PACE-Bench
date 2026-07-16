from __future__ import annotations

from typing import Any, Dict, List

import re

UNIFORM_SUFFIX = """

Sensors indicate that this region exhibits non-standard physical properties.
While the following variables MIGHT have changed from the initial environment, NOT ALL of them will necessarily be mutated in any given task. You must use active interaction and environmental feedback to deduce which specific conditions apply:
 - Beam-to-beam weld force threshold
 - Weld failure persistence
 - Gravitational acceleration
 - Reservoir particle normal restitution
 - Reservoir particle surface friction
 - Downstream boundary oscillation
 - Downstream boundary oscillation rate
 - Debris impact velocity
 - Seismic horizontal impulse magnitude
 - Vertical fluid surge impulse intensity
 - Reverse fluid surge impulse magnitude
 - Forward surge impulse intensity
 - Maximum allowable structure mass budget
 - Maximum leakage rate tolerance

Discovery via feedback: Your objective is to identify the underlying physical rules of this specific environment through trial and reasoning. Initial standard solutions may fail; analyze the failure mode through interaction feedback to infer which hidden variables have changed and adapt your design.
"""

def _replace_weld_constraint_line(
    description: str,
    *,
    target_force: float,
    base_force: float,
    target_steps: int,
    base_steps: int,

) -> str:
    marker = "- **Constraint**: Beam-to-beam welds break when reaction force **reaches or exceeds** "
    start = description.find(marker)
    if start == -1:
        return description
    end = description.find("\n", start)
    if end == -1:
        end = len(description)
    force_part = f"{target_force:.0f} N"
    if target_force != base_force:
        force_part += f" (originally {base_force:.0f} N in the source environment)"
    steps_part = f"{target_steps} consecutive simulation steps"
    if target_steps != base_steps:
        steps_part += f" (originally {base_steps} in the source environment)"
    new_line = f"{marker}{force_part} for {steps_part}."
    return description[:start] + new_line + description[end:]

def _fmt_float_short(x: float) -> str:
    s = f"{float(x):.6f}".rstrip("0").rstrip(".")
    return s if s else "0"

def _replace_debris_velocity_line(
    description: str, target_terrain_config: Dict[str, Any], base_terrain_config: Dict[str, Any]

) -> str:
    default_vx = 2.2
    default_vy = 0.0
    tvx = float(target_terrain_config.get("debris_linear_velocity_x", default_vx))
    bvx = float(base_terrain_config.get("debris_linear_velocity_x", default_vx))
    tvy = float(target_terrain_config.get("debris_linear_velocity_y", default_vy))
    bvy = float(base_terrain_config.get("debris_linear_velocity_y", default_vy))
    if tvx == bvx and tvy == bvy:
        return description
    pat = re.compile(r'\*\*\(([\d.]+),\s*(-?[\d.]+)\)\*\*\s*m/s')
    m = pat.search(description)
    if not m:
        return description
    vx_seg = _fmt_float_short(tvx)
    vy_seg = _fmt_float_short(tvy)
    if tvx != bvx:
        vx_seg += f" (originally {_fmt_float_short(bvx)} in the source environment)"
    if tvy != bvy:
        vy_seg += f" (originally {_fmt_float_short(bvy)} in the source environment)"
    new_text = f"**({vx_seg}, {vy_seg})** m/s"
    return pat.sub(new_text, description, count=1)

_DEFAULT_GRAVITY_F01 = (0, -10.0)

def update_task_description_for_visible_changes(
    base_description: str, target_terrain_config: Dict[str, Any], base_terrain_config: Dict[str, Any],
    target_physics_config: Dict[str, Any] = None, base_physics_config: Dict[str, Any] = None,

) -> str:
    description = base_description
    default_leakage = 0.001
    default_joint_break_force = 50000.0
    default_joint_break_consecutive_steps = 3
    default_fluid_height = 7.0
    target_leakage = target_terrain_config.get("max_leakage_rate", default_leakage)
    base_leakage = base_terrain_config.get("max_leakage_rate", default_leakage)
    if target_leakage != base_leakage:
        pattern_obj = r"(the leakage rate does not exceed )(\d+\.?\d*%)"
        if re.search(pattern_obj, description):
            description = re.sub(
                pattern_obj,
                f"\\g<1>{target_leakage*100:.2f}% (originally {base_leakage*100:.2f}% in the source environment)",
                description,
            )
        pattern_legacy = r"(leakage rate remains below )(\d+\.?\d*%)"
        if re.search(pattern_legacy, description):
            description = re.sub(
                pattern_legacy,
                f"\\g<1>{target_leakage*100:.2f}% (originally {base_leakage*100:.2f}% in the source environment)",
                description,
            )
    target_break = float(target_terrain_config.get("joint_break_force", default_joint_break_force))
    base_break = float(base_terrain_config.get("joint_break_force", default_joint_break_force))
    target_steps = int(target_terrain_config.get("joint_break_consecutive_steps", default_joint_break_consecutive_steps))
    base_steps = int(base_terrain_config.get("joint_break_consecutive_steps", default_joint_break_consecutive_steps))
    if target_break != base_break or target_steps != base_steps:
        description = _replace_weld_constraint_line(
            description,
            target_force=target_break,
            base_force=base_break,
            target_steps=target_steps,
            base_steps=base_steps,
        )
    target_height = target_terrain_config.get("fluid_height", default_fluid_height)
    base_height = base_terrain_config.get("fluid_height", default_fluid_height)
    if target_height != base_height:
        pattern = r"(\*\*Reservoir fill height\*\*: )(\d+\.?\d*)( m\.)"
        if re.search(pattern, description):
            description = re.sub(
                pattern,
                f"\\g<1>{target_height:.1f} m (originally {base_height:.1f} m in the source environment).",
                description,
            )
    description = _replace_debris_velocity_line(description, target_terrain_config, base_terrain_config)
    return description

def update_success_criteria_for_visible_changes(
    base_success_criteria: str, target_terrain_config: Dict[str, Any], base_terrain_config: Dict[str, Any],
    target_physics_config: Dict[str, Any] = None, base_physics_config: Dict[str, Any] = None,

) -> str:
    criteria = base_success_criteria
    default_leakage = 0.001
    target_leakage = target_terrain_config.get("max_leakage_rate", default_leakage)
    base_leakage = base_terrain_config.get("max_leakage_rate", default_leakage)
    if target_leakage != base_leakage:
        pattern_le = r"(1\. \*\*Leakage Rate\*\*: Total leakage <= )(\d+\.?\d*%)"
        if re.search(pattern_le, criteria):
            criteria = re.sub(
                pattern_le,
                f"\\g<1>{target_leakage*100:.2f}% (originally {base_leakage*100:.2f}% in the source environment)",
                criteria,
            )
        else:
            pattern_lt = r"(1\. \*\*Leakage Rate\*\*: Total leakage < )(\d+\.?\d*%)"
            if re.search(pattern_lt, criteria):
                criteria = re.sub(
                    pattern_lt,
                    f"\\g<1>{target_leakage*100:.2f}% (originally {base_leakage*100:.2f}% in the source environment)",
                    criteria,
                )
    default_mass = 380.0
    target_mass = float(target_terrain_config.get("max_structure_mass", default_mass))
    base_mass = float(base_terrain_config.get("max_structure_mass", default_mass))
    if target_mass != base_mass:
        pattern_mass = r"(\*\*Mass Budget\*\*: Total structure mass <= )(\d+\.?\d*)( kg\.)"
        if re.search(pattern_mass, criteria):
            criteria = re.sub(
                pattern_mass,
                f"\\g<1>{target_mass:.0f} kg (originally {base_mass:.0f} kg in the source environment).",
                criteria,
            )
    return criteria

def get_f01_curriculum_stages() -> List[Dict[str, Any]]:
    return [
        {
            "stage_id": "Stage-1",
            "title": "Low weld ceiling (threshold physics)",
            "mutation_description": "Single lever: reduced weld force ceiling (just below what the stock design survives).",
            "task_description_suffix": UNIFORM_SUFFIX,
            "terrain_config": {
                "joint_break_force": 41000.0,
            },
            "physics_config": {},
        },
        {
            "stage_id": "Stage-2",
            "title": "Elastic reservoir granules",
            "mutation_description": "Single lever: raised restitution on every fluid particle so impacts rebound through the pile—multi-bounce chain reactions and impulsive lateral loading instead of the damped slosh the stock dam assumes.",
            "task_description_suffix": UNIFORM_SUFFIX,
            "terrain_config": {
                "fluid_particle_restitution": 0.78,
            },
            "physics_config": {},
        },
        {
            "stage_id": "Stage-3",
            "title": "Bounce apocalypse + wide squeeze + fast debris + heavy world",
            "mutation_description": "Multi-variable: near-perfectly elastic fluid particles (19x baseline) create violent sustained impact cascades; wide and fast downstream wall oscillation opens the gate dramatically; faster debris slams the structure with punishing blows; elevated gravity crushes everything; welds break after just 2 consecutive over-threshold steps. The dam faces compounded overload: hyper-elastic impacts never dissipate, the oscillating wall creates relentless gap cycles, heavy debris adds impulse loading, and extra gravity amplifies every force.",
            "task_description_suffix": UNIFORM_SUFFIX,
            "terrain_config": {
                "joint_break_force": 50000.0,
                "joint_break_consecutive_steps": 2,
                "downstream_wall_amplitude": 1.0,
                "downstream_wall_phase_divisor": 30.0,
                "fluid_particle_restitution": 0.95,
                "debris_linear_velocity_x": 3.2,
            },
            "physics_config": {
                "gravity": (0, -10.5),
            },
        },
        {
            "stage_id": "Stage-4",
            "title": "Apocalypse: every physics dial at breaking point",
            "mutation_description": "Cataclysmic 13-variable escalation far beyond Stage-3: welds at baseline 50000 N with 2-step break (vs baseline's 3-step grace, matching Stage-3's 2-step but combined with far worse conditions); wall oscillation at 1.0 m amplitude (2.5× baseline) with accelerated frequency (phase_divisor=20 vs Stage-3's 30, a 1.5× speedup); debris impacts at 4.0 m/s (1.82× baseline); elevated gravity at -11.5 m/s^2 (15% above baseline, vs Stage-3's modest +5%); particle restitution at 0.97 — virtually no energy dissipation (19.4× baseline); particle friction slashed to 0.02 (5× below baseline); earthquake pulses at 0.5 m/s (1.43× baseline); vertical fluid surge at 1.5 m/s (1.5× baseline); reverse slosh at -0.9 m/s (1.29× baseline); forward surge sequence escalated to 2.2 m/s peak (1.29× baseline); mass budget slashed to 130 kg (34% of baseline); leakage tightened to 0.5% (2× more stringent than baseline 0.1%). The dam faces a perfect storm: softened welds with reduced failure grace period, hyper-energetic particles that never lose momentum, violent multi-directional disturbances at extreme magnitudes, elevated gravity amplifying every hydrostatic load, severely restricted mass, and tight leakage tolerance — all simultaneously. Solving one problem (e.g., leakage) worsens others (mass, joint load distribution). This is the hard ceiling on physically-solvable dam design.",
            "task_description_suffix": UNIFORM_SUFFIX,
            "terrain_config": {
                "joint_break_force": 50000.0,
                "joint_break_consecutive_steps": 2,
                "downstream_wall_amplitude": 1.0,
                "downstream_wall_phase_divisor": 20.0,
                "fluid_particle_restitution": 0.97,
                "fluid_particle_friction": 0.02,
                "debris_linear_velocity_x": 4.0,
                "earthquake_impulse_x": 0.5,
                "upward_surge_impulse_y": 1.5,
                "max_structure_mass": 130.0,
                "backward_slosh_impulse_x": -0.9,
                "max_leakage_rate": 0.005,
                "surge_impulses": [1.0, 1.2, 1.3, 1.5, 1.6, 1.8, 1.9, 2.1, 2.2],
            },
            "physics_config": {
                "gravity": (0, -11.5),
            },
        },
    ]
