from __future__ import annotations

import math

from typing import Any, Dict, List

def gravity_resonant_violent(t: float) -> tuple:
    g_y = 28.0 * math.sin(2.0 * math.pi * t / 0.5)
    return (0.0, g_y)

def gravity_biased_extreme(t: float) -> tuple:
    g_x = 8.0
    g_y = 15.0 * math.sin(2.0 * math.pi * t / 2.0)
    return (g_x, g_y)

def gravity_supercritical(t: float) -> tuple:
    g_x = 18.0 * math.sin(2.0 * math.pi * t / 0.3)
    g_y = 30.0 * math.cos(2.0 * math.pi * t / 0.4)
    return (g_x, g_y)

def gravity_chaotic_max(t: float) -> tuple:
    g_x = 18.0 * math.sin(2.0 * math.pi * t / 1.0)
    g_y = 35.0 * math.cos(2.0 * math.pi * t / 0.7)
    return (g_x, g_y)

def gravity_vortex_singularity(t: float) -> tuple:
    phase = 2.0 * math.pi * t / 0.35
    g_x = 25.0 * math.sin(phase)
    g_y = 40.0 * math.cos(phase * 1.3)
    return (g_x, g_y)

def gravity_cataclysm(t: float) -> tuple:
    g_x = 30.0 * math.sin(2.0 * math.pi * t / 0.45)
    g_y = 48.0 * math.cos(2.0 * math.pi * t / 0.55)
    return (g_x, g_y)

TASK_DESCRIPTION_SUFFIX = """

Sensors indicate that this region exhibits non-standard physical properties.
While the following variables **MIGHT** have changed from the initial environment, **NOT ALL** of them will necessarily be mutated in any given task. You must use active interaction and environmental feedback to deduce which specific conditions apply:
- **Arena and Build Zone Boundaries**: May differ from standard values.
- **Gravity Field Dynamics**: May differ from standard values.
- **Motion Damping**: May differ from standard values.
- **Structural Integrity Thresholds**: May differ from standard values.
- **Surface Traction**: May differ from standard values.
- **Logistical Constraints**: May differ from standard values.
- **Material Density Scaling**: May differ from standard values.

**Discovery via feedback**: Use environmental feedback to identify the underlying physical rules of this specific environment and adapt your design accordingly.
"""

import re

def update_task_description_for_visible_changes(
    base_description: str,
    target_terrain_config: Dict[str, Any],
    base_terrain_config: Dict[str, Any],
    target_physics_config: Dict[str, Any] = None,
    base_physics_config: Dict[str, Any] = None,

) -> str:
    description = base_description
    target_terrain_config = target_terrain_config or {}
    base_terrain_config = base_terrain_config or {}
    target_physics_config = target_physics_config or {}
    base_physics_config = base_physics_config or {}
    target_arena_y_max = target_terrain_config.get("arena_y_max", 20.0)
    base_arena_y_max = base_terrain_config.get("arena_y_max", 20.0)
    if target_arena_y_max != base_arena_y_max:
        arena_pattern = r"(- \*\*Arena\*\*: A bounded region with x in \[0, 40\] m and y in \[0, )(\d+\.?\d*)(\] m\.)"
        if re.search(arena_pattern, description):
            description = re.sub(
                arena_pattern,
                f"\\g<1>{target_arena_y_max:.1f}\\g<3> (originally y in [0, {base_arena_y_max:.1f}] m in the source environment).",
                description,
            )
    target_bz_y_max = target_terrain_config.get("build_zone_y_max", 18.0)
    base_bz_y_max = base_terrain_config.get("build_zone_y_max", 18.0)
    if target_bz_y_max != base_bz_y_max:
        bz_pattern = r"(- \*\*Build Zone\*\*: Structure must be built within x=\[12\.0, 28\.0\], y=\[6\.0, )(\d+\.?\d*)(\]\.|\] \()"
        if re.search(bz_pattern, description):
            description = re.sub(
                bz_pattern,
                f"\\g<1>{target_bz_y_max:.1f}]. (originally y=[6.0, {base_bz_y_max:.1f}] in the source environment).",
                description,
            )
    default_joint_limit = float("inf")
    target_joint_limit = target_physics_config.get("joint_force_limit", default_joint_limit)
    base_joint_limit = base_physics_config.get("joint_force_limit", default_joint_limit)
    if target_joint_limit != base_joint_limit and target_joint_limit < float("inf"):
        no_limit_phrase = r"(- \*\*Joint strength\*\*: )Joints have no force limit( in the default configuration)? \(they do not break from overload\); some environment stages may introduce a finite joint breaking threshold — discover the actual limit from feedback if joints fail unexpectedly\."
        originally_phrase = (
            f"(originally {base_joint_limit:.0f} N in the source environment)."
            if base_joint_limit < float("inf")
            else "(originally no force limit in the source environment)."
        )
        finite_replacement = (
            f"\\g<1>Joints break when reaction force exceeds {target_joint_limit:.0f} N "
            f"{originally_phrase}"
        )
        if re.search(no_limit_phrase, description):
            description = re.sub(no_limit_phrase, finite_replacement, description)
        else:
            finite_pattern = r"(- \*\*Joint strength\*\*: )Joints have no force limit"
            if re.search(finite_pattern, description):
                originally_finite = (
                    f"(originally {base_joint_limit:.0f} N in the source environment)."
                    if base_joint_limit < float("inf")
                    else "(originally no force limit in the source environment)."
                )
                description = re.sub(
                    finite_pattern,
                    f"\\g<1>{target_joint_limit:.0f} N {originally_finite}",
                    description,
                )
    return description

def update_success_criteria_for_visible_changes(
    base_success_criteria: str,
    target_terrain_config: Dict[str, Any],
    base_terrain_config: Dict[str, Any],
    target_physics_config: Dict[str, Any] = None,
    base_physics_config: Dict[str, Any] = None,

) -> str:
    criteria = base_success_criteria
    target_physics_config = target_physics_config or {}
    base_physics_config = base_physics_config or {}
    target_terrain_config = target_terrain_config or {}
    base_terrain_config = base_terrain_config or {}
    default_mass = 200.0
    target_mass = target_physics_config.get("max_structure_mass", default_mass)
    base_mass = base_physics_config.get("max_structure_mass", default_mass)
    if target_mass != base_mass:
        mass_pattern = r"(- \*\*Mass Budget\*\*: Total structure mass must not exceed )(\d+\.?\d*)( kg\.)"
        if re.search(mass_pattern, criteria):
            criteria = re.sub(
                mass_pattern,
                f"\\g<1>{target_mass:.0f} kg (originally {base_mass:.0f} kg in the source environment).",
                criteria,
            )
    default_beams = 12
    target_beams = target_physics_config.get("max_beam_count", default_beams)
    base_beams = base_physics_config.get("max_beam_count", default_beams)
    if target_beams != base_beams:
        beam_pattern = r"(- \*\*Beam Limit\*\*: Maximum )(\d+)( beams \(discover the limit from feedback\)\.)"
        if re.search(beam_pattern, criteria):
            criteria = re.sub(
                beam_pattern,
                f"\\g<1>{int(target_beams)} beams (originally {int(base_beams)} beams in the source environment).",
                criteria,
            )
    default_joint_limit = float("inf")
    target_joint_limit = target_physics_config.get("joint_force_limit", default_joint_limit)
    base_joint_limit = base_physics_config.get("joint_force_limit", default_joint_limit)
    if target_joint_limit != base_joint_limit and target_joint_limit < float("inf"):
        no_limit_phrase = r"(- \*\*Joint strength\*\*: )Joints have no force limit( in the default configuration)? \(they do not break from overload\); some environment stages may introduce a finite joint breaking threshold — discover the actual limit from feedback if joints fail unexpectedly\."
        originally_phrase = (
            f"(originally {base_joint_limit:.0f} N in the source environment)."
            if base_joint_limit < float("inf")
            else "(originally no force limit in the source environment)."
        )
        finite_replacement = (
            f"\\g<1>Joints break when reaction force exceeds {target_joint_limit:.0f} N "
            f"{originally_phrase}"
        )
        if re.search(no_limit_phrase, criteria):
            criteria = re.sub(no_limit_phrase, finite_replacement, criteria)
        else:
            finite_pattern = r"(- \*\*Joint strength\*\*: )Joints break when reaction force exceeds (\d+\.?\d*) N"
            if re.search(finite_pattern, criteria):
                criteria = re.sub(
                    finite_pattern,
                    f"\\g<1>Joints break when reaction force exceeds {target_joint_limit:.0f} N (originally \\g<2> N in the source environment).",
                    criteria,
                )
    return criteria

def get_e01_curriculum_stages() -> List[Dict[str, Any]]:
    return [
        {
            "stage_id": "Stage-1",
            "title": "Near-Zero Joint Integrity",
            "mutation_description": "Joints snap at 1.0 N force threshold under high-frequency gravity. Requires atomically-light structures with dense anchoring.",
            "task_description_suffix": TASK_DESCRIPTION_SUFFIX,
            "terrain_config": {
                "arena_y_max": 20.0,
                "build_zone_y_max": 18.0,
            },
            "physics_config": {
                "gravity": gravity_resonant_violent,
                "joint_force_limit": 1.0,
            },
        },
        {
            "stage_id": "Stage-2",
            "title": "Hyperdense Microfracture",
            "mutation_description": "Extreme material density scaling (all beam densities multiplied by 200x — every beam's effective density is 200 times larger than specified, making even 'lightweight' density=0.001 beams generate forces exceeding 0.5 N), near-vanishing joint integrity (0.001 N threshold — each joint snaps if reaction force exceeds 0.001 Newtons, equivalent to the weight of just 0.1 grams under standard gravity), cataclysmic multi-axis gravity (30/48 m/s² amplitudes, 0.45/0.55s oscillation periods generating enormous directional inertial loads), aggressive negative damping (-6.0/-4.0) injecting continuous destabilizing energy that amplifies every perturbation toward joint-breaking amplitudes, zero surface friction eliminating all passive grip, singular beam allowance (max 1 beam), and ultralight mass budget (0.02 kg). The density scaling means any beam with normal density parameters will have massive real mass — even a microscopic 0.1×0.1 m beam at density=0.001 weighs 0.002 kg and generates 0.11 N joint force, far exceeding the 0.001 N limit. Only designs using sub-microgram densities (density parameters below 10^-5) can survive — the reference solution uses densities at the 10^-6 scale to keep joint forces within bounds.",
            "task_description_suffix": TASK_DESCRIPTION_SUFFIX,
            "terrain_config": {
                "arena_y_max": 9.0,
                "build_zone_y_max": 8.5,
                "friction": 0.0,
            },
            "physics_config": {
                "gravity": gravity_cataclysm,
                "beam_density_scale": 200.0,
                "linear_damping": -6.0,
                "angular_damping": -4.0,
                "joint_force_limit": 0.001,
                "max_beam_count": 1,
                "max_structure_mass": 0.02,
            },
        },
        {
            "stage_id": "Stage-3",
            "title": "Destabilization Cascade",
            "mutation_description": "Vortex-singularity multi-axis gravity (25/40 m/s² amplitudes, 0.35s oscillation period creating extremely rapid directional inertial loads — the fastest oscillation of any stage), extreme negative damping (-6.0/-4.0) that injects continuous destabilizing energy amplifying every perturbation toward joint-breaking amplitudes, catastrophic material density scaling (150x — every beam's effective density is 150 times larger than specified, meaning even density=0.01 produces effective density=1.5 and significant inertial forces), near-vanishing joint integrity (0.15 N threshold — each joint snaps if reaction force exceeds 0.15 Newtons, roughly the weight of just 15 grams under standard gravity), zero surface friction eliminating all passive grip, severely compressed vertical arena (y_max=9.5 m), and extreme resource scarcity (2 beams max, 0.3 kg mass budget). Density scaling means any beam with normal density parameters will be catastrophically heavy — a 0.1×0.1 m beam at density=0.01 weighs 0.015 kg (effective density=1.5) and generates 0.6 N of force under peak 40 m/s² gravity, four times the 0.15 N joint limit. Only atomically-light designs using sub-milligram densities can survive.",
            "task_description_suffix": TASK_DESCRIPTION_SUFFIX,
            "terrain_config": {
                "arena_y_max": 9.5,
                "build_zone_y_max": 9.0,
                "friction": 0.0,
            },
            "physics_config": {
                "gravity": gravity_vortex_singularity,
                "beam_density_scale": 150.0,
                "linear_damping": -6.0,
                "angular_damping": -4.0,
                "joint_force_limit": 0.15,
                "max_beam_count": 2,
                "max_structure_mass": 0.3,
            },
        },
        {
            "stage_id": "Stage-4",
            "title": "Absolute Nullification",
            "mutation_description": "Hyperdense material scaling (300x — every beam's effective density is 300 times larger than specified, the most extreme of any stage, making even density=0.00001 produce effective density=0.003 and tangible inertial forces), near-vanishing joint integrity (0.01 N threshold — each joint snaps if reaction force exceeds one hundredth of a Newton, roughly the weight of 1 gram under standard gravity), cataclysmic multi-axis gravity (30/48 m/s² amplitudes, 0.45/0.55s oscillation periods creating the largest amplitude directional inertial loads of any stage), maximum aggressive negative damping (-6.0/-4.0) injecting continuous destabilizing energy that amplifies every perturbation toward joint-breaking amplitudes, zero surface friction eliminating all passive grip, singular beam allowance (max 1 beam — cannot distribute across multiple elements), ultralight mass budget (0.005 kg — 5 grams total, the tightest constraint across all stages), and compressed vertical arena (y_max=9.0 m). The 300x density scaling means any beam with normal density parameters will have massive real mass — even a microscopic 0.05×0.05 m beam at density=0.001 weighs 0.00075 kg (effective density=0.3) and generates 0.036 N joint force, far exceeding the 0.01 N limit. Only designs using sub-microgram densities (density parameters at or below 10^-6 scale) with numerous anchoring points can survive. This stage combines the highest density scaling, tightest mass budget, and most extreme damping of any stage in the curriculum.",
            "task_description_suffix": TASK_DESCRIPTION_SUFFIX,
            "terrain_config": {
                "arena_y_max": 9.0,
                "build_zone_y_max": 8.5,
                "friction": 0.0,
            },
            "physics_config": {
                "gravity": gravity_cataclysm,
                "beam_density_scale": 300.0,
                "linear_damping": -6.0,
                "angular_damping": -4.0,
                "joint_force_limit": 0.01,
                "max_beam_count": 1,
                "max_structure_mass": 0.005,
            },
        },
    ]
