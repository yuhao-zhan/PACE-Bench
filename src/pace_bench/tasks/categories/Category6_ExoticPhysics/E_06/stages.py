from __future__ import annotations

import re

from typing import Any, Dict, List

DEFAULT_JOINT_BREAK_FORCE = 78.0

DEFAULT_JOINT_BREAK_TORQUE = 115.0

DEFAULT_DAMAGE_LIMIT = 100.0

DEFAULT_BEAM_ANGVEL_THRESH = 2.2

DEFAULT_BEAM_ANGVEL_TOLERANCE_STEPS = 10

TASK_DESCRIPTION_SUFFIX = """

Sensors indicate that this region exhibits non-standard physical properties.
While the following variables **MIGHT** have changed from the initial environment, **NOT ALL** of them will necessarily be mutated in any given task. You must use active interaction and environmental feedback to deduce which specific conditions apply:
- **Noise Strength**: The intensity of random thermal and environmental disturbances may vary.
- **Joint and Damage Thresholds**: The force, torque, and damage limits of structural components may be altered.
- **Coherent Pulses**: The frequency and magnitude of periodic energy impacts may have changed.
- **Motion Damping**: Linear damping may differ from standard values; resistance affecting the dissipation of kinetic energy may be adjusted.
- **Angular Damping**: Rotational damping may differ from standard values.
- **Shock Propagation**: The severity of damage cascading through the structure may differ from standard.
- **Fatigue Dynamics**: Thresholds for angular velocity-induced structural wear may vary.
- **Environmental Storms**: Multipliers for storm intensity, burst probability, and storm timing windows may be altered.
- **Mass Budget**: The maximum allowable total structure mass may be altered.
- **Anchor Zone**: The permissible ground anchor region boundaries may be altered.
- **Gravity**: The gravitational acceleration may differ from standard values.

**Discovery via feedback**: Your objective is to identify the underlying physical rules of this specific environment through trial and reasoning. Initial standard solutions may fail; analyze the failure mode (e.g., where a joint breaks or how a body moves) to infer the hidden constraints and adapt your design.
"""

def update_task_description_for_visible_changes(
    base_description: str,
    target_terrain_config: Dict[str, Any],
    base_terrain_config: Dict[str, Any],
    target_physics_config: Dict[str, Any] = None,
    base_physics_config: Dict[str, Any] = None,
    **kwargs,

) -> str:
    description = base_description
    target_physics_config = target_physics_config or {}
    base_physics_config = base_physics_config or {}
    target_force = target_physics_config.get("joint_break_force", DEFAULT_JOINT_BREAK_FORCE)
    base_force = base_physics_config.get("joint_break_force", DEFAULT_JOINT_BREAK_FORCE)
    target_torque = target_physics_config.get("joint_break_torque", DEFAULT_JOINT_BREAK_TORQUE)
    base_torque = base_physics_config.get("joint_break_torque", DEFAULT_JOINT_BREAK_TORQUE)
    target_damage = target_physics_config.get("damage_limit", DEFAULT_DAMAGE_LIMIT)
    base_damage = base_physics_config.get("damage_limit", DEFAULT_DAMAGE_LIMIT)
    if target_force != base_force:
        _MIDDLE = "\u00b7"
        _force_pat = r"(Joints fail above )(\d+ N)( reaction force)"
        if re.search(_force_pat, description):
            _new_force = (
                f"{target_force:.0f} N (originally {base_force:.0f} N in the source environment)"
            )
            description = re.sub(
                _force_pat,
                r"\g<1>" + _new_force + r"\g<3>",
                description,
            )
        _torque_pat = r"( or )(\d+ N" + _MIDDLE + r"m)( reaction torque)"
        if re.search(_torque_pat, description):
            _new_torque = (
                f"{target_torque:.1f} N{_MIDDLE}m (originally {base_torque:.1f} N{_MIDDLE}m in the source environment)"
            )
            description = re.sub(
                _torque_pat,
                r"\g<1>" + _new_torque + r"\g<3>",
                description,
            )
    if target_damage != base_damage:
        pattern = r"(cumulative damage fails at )(\d+\.?\d* pts)\."
        if re.search(pattern, description):
            description = re.sub(
                pattern,
                f"\\g<1>{target_damage:.1f} pts (originally {base_damage:.1f} pts in the source environment).",
                description,
            )
    target_angvel = target_physics_config.get("beam_angvel_thresh", DEFAULT_BEAM_ANGVEL_THRESH)
    base_angvel = base_physics_config.get("beam_angvel_thresh", DEFAULT_BEAM_ANGVEL_THRESH)
    target_angvel_tol = target_physics_config.get("beam_angvel_tolerance_steps", DEFAULT_BEAM_ANGVEL_TOLERANCE_STEPS)
    base_angvel_tol = base_physics_config.get("beam_angvel_tolerance_steps", DEFAULT_BEAM_ANGVEL_TOLERANCE_STEPS)
    if target_angvel != base_angvel or target_angvel_tol != base_angvel_tol:
        _beam_pat = r"A beam is destroyed if angular velocity exceeds \d+\.?\d* rad/s for \d+ consecutive steps\."
        if re.search(_beam_pat, description):
            _parts = ["A beam is destroyed if angular velocity exceeds "]
            if target_angvel != base_angvel:
                _parts.append(f"{target_angvel:.1f} rad/s (originally {base_angvel:.1f} rad/s in the source environment)")
            else:
                _parts.append(f"{target_angvel:.1f} rad/s")
            _parts.append(" for ")
            if target_angvel_tol != base_angvel_tol:
                _parts.append(f"{target_angvel_tol} consecutive steps (originally {base_angvel_tol} consecutive steps in the source environment)")
            else:
                _parts.append(f"{target_angvel_tol} consecutive steps")
            _parts.append(".")
            description = re.sub(_beam_pat, "".join(_parts), description)
    DEFAULT_MASS = 120.0
    target_mass = float(target_terrain_config.get("max_structure_mass", DEFAULT_MASS))
    base_mass = float(base_terrain_config.get("max_structure_mass", DEFAULT_MASS))
    if target_mass != base_mass:
        _mass_pat = r"(Total structure mass <= )(\d+\.?\d* kg)\b"
        if re.search(_mass_pat, description):
            _new_mass = (
                f"{target_mass:.0f} kg (originally {base_mass:.0f} kg in the source environment)"
            )
            description = re.sub(
                _mass_pat,
                r"\g<1>" + _new_mass,
                description,
            )
        _mass_pat2 = r"(mass limit \()(\d+\.?\d* kg)\)"
        if re.search(_mass_pat2, description):
            _new_mass2 = (
                f"{target_mass:.0f} kg (originally {base_mass:.0f} kg in the source environment)"
            )
            description = re.sub(
                _mass_pat2,
                r"\g<1>" + _new_mass2 + r")",
                description,
            )
    DEFAULT_ANCHOR_LO = 5.0
    DEFAULT_ANCHOR_HI = 6.5
    target_anchor_lo = float(target_terrain_config.get("allowed_anchor_x_lo", DEFAULT_ANCHOR_LO))
    base_anchor_lo = float(base_terrain_config.get("allowed_anchor_x_lo", DEFAULT_ANCHOR_LO))
    target_anchor_hi = float(target_terrain_config.get("allowed_anchor_x_hi", DEFAULT_ANCHOR_HI))
    base_anchor_hi = float(base_terrain_config.get("allowed_anchor_x_hi", DEFAULT_ANCHOR_HI))
    if target_anchor_lo != base_anchor_lo or target_anchor_hi != base_anchor_hi:
        _anchor_pat = r"(x in \[)(\d+\.?\d*),\s*(\d+\.?\d*)(\]m\).*?anchor)"
        if re.search(_anchor_pat, description):
            _new_anchor = (
                f"{target_anchor_lo:.1f}, {target_anchor_hi:.1f}"
                f" (originally {base_anchor_lo:.1f}, {base_anchor_hi:.1f} in the source environment)"
            )
            description = re.sub(
                _anchor_pat,
                r"\g<1>" + _new_anchor + r"\g<4>",
                description,
            )
    return description

def update_success_criteria_for_visible_changes(
    base_success_criteria: str,
    target_terrain_config: Dict[str, Any],
    base_terrain_config: Dict[str, Any],
    target_physics_config: Dict[str, Any] = None,
    base_physics_config: Dict[str, Any] = None,
    **kwargs,

) -> str:
    criteria = base_success_criteria
    target_physics_config = target_physics_config or {}
    base_physics_config = base_physics_config or {}
    target_force = target_physics_config.get("joint_break_force", DEFAULT_JOINT_BREAK_FORCE)
    base_force = base_physics_config.get("joint_break_force", DEFAULT_JOINT_BREAK_FORCE)
    target_torque = target_physics_config.get("joint_break_torque", DEFAULT_JOINT_BREAK_TORQUE)
    base_torque = base_physics_config.get("joint_break_torque", DEFAULT_JOINT_BREAK_TORQUE)
    target_damage = target_physics_config.get("damage_limit", DEFAULT_DAMAGE_LIMIT)
    base_damage = base_physics_config.get("damage_limit", DEFAULT_DAMAGE_LIMIT)
    if target_force != base_force:
        pattern = r"(force > )(\d+\.?\d* N)( or)"
        if re.search(pattern, criteria):
            criteria = re.sub(
                pattern,
                r"\g<1>" + f"{target_force:.0f} N (originally {base_force:.0f} N in the source environment)" + r"\g<3>",
                criteria,
            )
    if target_torque != base_torque:
        pattern = r"(torque > )(\d+\.?\d* N·m)(;)"
        if re.search(pattern, criteria):
            criteria = re.sub(
                pattern,
                r"\g<1>" + f"{target_torque:.1f} N·m (originally {base_torque:.1f} N·m in the source environment)" + r"\g<3>",
                criteria,
            )
    if target_damage != base_damage:
        pattern = r"(damage failure at )(\d+\.?\d* pts)\."
        if re.search(pattern, criteria):
            criteria = re.sub(
                pattern,
                f"\\g<1>{target_damage:.1f} pts (originally {base_damage:.1f} pts in the source environment).",
                criteria,
            )
    target_angvel = target_physics_config.get("beam_angvel_thresh", DEFAULT_BEAM_ANGVEL_THRESH)
    base_angvel = base_physics_config.get("beam_angvel_thresh", DEFAULT_BEAM_ANGVEL_THRESH)
    target_angvel_tol = target_physics_config.get("beam_angvel_tolerance_steps", DEFAULT_BEAM_ANGVEL_TOLERANCE_STEPS)
    base_angvel_tol = base_physics_config.get("beam_angvel_tolerance_steps", DEFAULT_BEAM_ANGVEL_TOLERANCE_STEPS)
    if target_angvel != base_angvel or target_angvel_tol != base_angvel_tol:
        _beam_pat = r"A beam is destroyed if angular velocity exceeds \d+\.?\d* rad/s for \d+ consecutive steps\."
        if re.search(_beam_pat, criteria):
            _parts = ["A beam is destroyed if angular velocity exceeds "]
            if target_angvel != base_angvel:
                _parts.append(f"{target_angvel:.1f} rad/s (originally {base_angvel:.1f} rad/s in the source environment)")
            else:
                _parts.append(f"{target_angvel:.1f} rad/s")
            _parts.append(" for ")
            if target_angvel_tol != base_angvel_tol:
                _parts.append(f"{target_angvel_tol} consecutive steps (originally {base_angvel_tol} consecutive steps in the source environment)")
            else:
                _parts.append(f"{target_angvel_tol} consecutive steps")
            _parts.append(".")
            criteria = re.sub(_beam_pat, "".join(_parts), criteria)
    DEFAULT_MASS = 120.0
    target_mass = float(target_terrain_config.get("max_structure_mass", DEFAULT_MASS))
    base_mass = float(base_terrain_config.get("max_structure_mass", DEFAULT_MASS))
    if target_mass != base_mass:
        _mass_pat = r"(mass limit \()(\d+\.?\d* kg)\)"
        if re.search(_mass_pat, criteria):
            _new_mass = (
                f"{target_mass:.0f} kg (originally {base_mass:.0f} kg in the source environment)"
            )
            criteria = re.sub(
                _mass_pat,
                r"\g<1>" + _new_mass + r")",
                criteria,
            )
        _mass_pat2 = r"(Total structure mass <= )(\d+\.?\d* kg)\b"
        if re.search(_mass_pat2, criteria):
            _new_mass2 = (
                f"{target_mass:.0f} kg (originally {base_mass:.0f} kg in the source environment)"
            )
            criteria = re.sub(
                _mass_pat2,
                r"\g<1>" + _new_mass2,
                criteria,
            )
    DEFAULT_ANCHOR_LO = 5.0
    DEFAULT_ANCHOR_HI = 6.5
    target_anchor_lo = float(target_terrain_config.get("allowed_anchor_x_lo", DEFAULT_ANCHOR_LO))
    base_anchor_lo = float(base_terrain_config.get("allowed_anchor_x_lo", DEFAULT_ANCHOR_LO))
    target_anchor_hi = float(target_terrain_config.get("allowed_anchor_x_hi", DEFAULT_ANCHOR_HI))
    base_anchor_hi = float(base_terrain_config.get("allowed_anchor_x_hi", DEFAULT_ANCHOR_HI))
    if target_anchor_lo != base_anchor_lo or target_anchor_hi != base_anchor_hi:
        _anchor_pat = r"(x in \[)(\d+\.?\d*),\s*(\d+\.?\d*)(\]m\).*?anchor)"
        if re.search(_anchor_pat, criteria):
            _new_anchor = (
                f"{target_anchor_lo:.1f}, {target_anchor_hi:.1f}"
                f" (originally {base_anchor_lo:.1f}, {base_anchor_hi:.1f} in the source environment)"
            )
            criteria = re.sub(
                _anchor_pat,
                r"\g<1>" + _new_anchor + r"\g<4>",
                criteria,
            )
    return criteria

def get_e06_curriculum_stages() -> List[Dict[str, Any]]:
    return [
        {
            "stage_id": "Stage-1",
            "title": "Tight mass budget",
            "mutation_description": "Maximum structure mass reduced to 12.0 kg (from 120.0 kg) — a 10x stricter budget forces radically lighter designs. All other physics remain at standard values.",
            "task_description_suffix": TASK_DESCRIPTION_SUFFIX,
            "terrain_config": {
                "max_structure_mass": 12.0,
            },
            "physics_config": {},
        },
        {
            "stage_id": "Stage-2",
            "title": "Brittle micro-joint regime with accelerated fatigue",
            "mutation_description": "Joints fail at 2.5 N force / 3.5 N·m torque — structural connections are barely stronger than insect silk. Angular damping fully disabled (0.0) so rotational energy persists without decay. Spin-death threshold lowered to 2.0 rad/s with only 4 consecutive steps of tolerance. Noise increased to 50.0 with storms starting at step 80 (2.2x multiplier, 5% burst probability). Coherent overturning pulses occur every 30 steps at 50.0 N. Damage limit lowered to 15.0 pts with thresholds at 1.5 N force / 3.0 N·m torque — even moderate sustained loads cause rapid cumulative fatigue failure. The initial reference design will fail as joints simultaneously exceed these tightened limits across all failure axes.",
            "task_description_suffix": TASK_DESCRIPTION_SUFFIX,
            "terrain_config": {},
            "physics_config": {
                "joint_break_force": 2.5,
                "joint_break_torque": 3.5,
                "angular_damping": 0.0,
                "beam_angvel_thresh": 2.0,
                "beam_angvel_tolerance_steps": 4,
                "noise_strength": 50.0,
                "coherent_pulse_interval": 30,
                "coherent_pulse_force": 50.0,
                "damage_limit": 15.0,
                "damage_force_thresh": 1.5,
                "damage_torque_thresh": 3.0,
                "phased_storm_mult": 2.2,
                "phased_storm_start": 80,
                "phased_storm_end": 500,
                "burst_prob": 0.05,
            },
        },
        {
            "stage_id": "Stage-3",
            "title": "Cascade catastrophe: heavy gravity, per-step pulses, instant death",
            "mutation_description": "Gravity elevated to 1.7× standard (0, -17) — constant structural stress 70% above baseline, relentless downward loading on every beam. Joint break force at absolute minimum 2.0 N / 3.5 N·m (matching Stage-4). Per-step coherent pulses at 130.0 N (>2× current) fire EVERY step — total horizontal impulse per body per step is massive, direction alternating each step so cumulative net displacement is zero but peak joint shear forces are extreme. Damage thresholds lowered to 0.35 N force / 0.8 N·m torque with a tiny 1.0 pt limit — even moderate pulse-driven force spikes rapidly accumulate fatal damage. Cascade shock at 500.0 pts guarantees one joint failure IMMEDIATELY saturates every neighbor's damage to the limit, triggering an unstoppable chain reaction that destroys the entire structure within a few simulation steps. Zero linear and angular damping means every oscillation persists without decay; spin-death threshold at 1.5 rad/s with only 2 consecutive steps of tolerance — half the leeway of Stage-2. Noise at 14.0 with storm starting at step 15 (4.5× multiplier, 15% burst probability) means moderate ambient noise but intense storm amplification peaking at ~240 N during burst events. Structure mass capped at 35.0 kg, creating a brutal dilemma: the deep truss needed to resist 1.7× gravity amplifies pulse-induced shear across web members; heavier chords resist spin but consume mass budget and increase gravitational joint stress; lighter chords save mass but risk cumulative spin-death across 500 steps. A stage-specific solution must find the precise balance point where geometry, density, and node count allow survival across all failure axes simultaneously.",
            "task_description_suffix": TASK_DESCRIPTION_SUFFIX,
            "terrain_config": {
                "max_structure_mass": 35.0,
            },
            "physics_config": {
                "gravity": (0, -17),
                "joint_break_force": 2.0,
                "joint_break_torque": 3.5,
                "coherent_pulse_interval": 1,
                "coherent_pulse_force": 130.0,
                "angular_damping": 0.0,
                "linear_damping": 0.0,
                "noise_strength": 14.0,
                "damage_limit": 1.0,
                "damage_force_thresh": 0.35,
                "damage_torque_thresh": 0.8,
                "cascade_shock_damage": 500.0,
                "beam_angvel_thresh": 1.5,
                "beam_angvel_tolerance_steps": 2,
                "phased_storm_mult": 4.5,
                "phased_storm_start": 15,
                "burst_prob": 0.15,
            },
        },
        {
            "stage_id": "Stage-4",
            "title": "Absolute extinction regime",
            "mutation_description": "Maximum-difficulty all-axes assault: 3.0x gravity, per-step massive coherent pulses (550 N), critically-weak joints (2.0 N / 3.5 N·m break), ultra-narrow damage regime (0.22 N / 0.38 N·m thresholds with 0.9 pt limit — thresholds 55x/47x below default, limit 111x below default), near-absent damping (0.20 angular — 8x below default), spin-death at 1.0 rad/s with 2-step tolerance (half the default threshold), intense storm (4.5x) from step 0, elevated burst probability (0.4), apocalyptic cascade (5000 shock — 192x default), brutal mass restriction (20 kg — 6x below default), and severely compressed anchor zone ([5.6, 5.9] — 80% narrower). Joint damage accumulates on every single step; only an ultra-wide-beam minimal-joint truss with extreme rotational inertia can survive all failure axes simultaneously.",
            "task_description_suffix": TASK_DESCRIPTION_SUFFIX,
            "terrain_config": {
                "max_structure_mass": 20.0,
                "allowed_anchor_x_lo": 5.6,
                "allowed_anchor_x_hi": 5.9,
            },
            "physics_config": {
                "gravity": (0, -30),
                "noise_strength": 2.0,
                "coherent_pulse_interval": 1,
                "coherent_pulse_force": 550.0,
                "angular_damping": 0.20,
                "linear_damping": 0.0,
                "joint_break_force": 2.0,
                "joint_break_torque": 3.5,
                "damage_limit": 0.9,
                "damage_force_thresh": 0.22,
                "damage_torque_thresh": 0.38,
                "cascade_shock_damage": 5000.0,
                "beam_angvel_thresh": 1.0,
                "beam_angvel_tolerance_steps": 2,
                "phased_storm_mult": 4.5,
                "burst_prob": 0.4,
                "phased_storm_start": 0,
                "phased_storm_end": 500,
            },
        },
    ]
