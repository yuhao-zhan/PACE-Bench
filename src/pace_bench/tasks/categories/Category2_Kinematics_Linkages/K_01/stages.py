from __future__ import annotations

from pace_bench.tasks.stage_prompt import uniform_suffix_for_task

import math

import re

from typing import Any, Dict, List

_DEFAULT_MAX_STRUCTURE_MASS = 100.0

def _mass_str(m: float) -> str:
    return f"{m:.0f}" if m == int(m) else f"{m:.1f}"

def _coefficient_str(value: float) -> str:
    return f"{float(value):.3f}".rstrip("0").rstrip(".")

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
    target_max_mass = float(target_terrain_config.get("max_structure_mass", _DEFAULT_MAX_STRUCTURE_MASS))
    base_max_mass = float(base_terrain_config.get("max_structure_mass", _DEFAULT_MAX_STRUCTURE_MASS))
    if target_max_mass != base_max_mass:
        mass_desc_pattern = re.compile(r"\(default:\s+\d+\.?\d*\s+kg\)\.")
        if mass_desc_pattern.search(description):
            description = mass_desc_pattern.sub(
                f"(originally {_mass_str(base_max_mass)} kg in the source environment; default now {_mass_str(target_max_mass)} kg).",
                description,
            )
    target_body_friction = target_physics_config.get("max_body_friction")
    base_body_friction_raw = base_physics_config.get("max_body_friction")
    base_body_friction = (
        float(base_body_friction_raw) if base_body_friction_raw is not None
        else 1.0
    )
    if target_body_friction is not None and base_body_friction != target_body_friction:
        bf_pattern_with_orig = re.compile(
            r"(\*\*Body Friction Cap\*\*(?:(?!\().)*?(?<!`)(?<=\w) is )(\d+\.?\d*)(\)\.?\s*|.,?\s*)",
        )
        if bf_pattern_with_orig.search(description):
            def _replace_bf_orig(m, target, base):
                g3 = m.group(3)
                t = float(target)
                b = float(base)
                val = f"{_coefficient_str(t)} (originally {_coefficient_str(b)} in the source environment)"
                return m.group(1) + val + g3
            description = bf_pattern_with_orig.sub(
                lambda m: _replace_bf_orig(m, target_body_friction, base_body_friction),
                description,
            )
        else:
            bf_pattern = re.compile(
                r"(\*\*Body Friction Cap\*\*(?:(?!\().)*?(?<!`)(?<=\w) is )(\d+\.?\d*)(.,?\s*)",
            )
            if bf_pattern.search(description):
                description = bf_pattern.sub(
                    lambda m: m.group(1) + f"{_coefficient_str(target_body_friction)} (originally {_coefficient_str(base_body_friction)} in the source environment)" + m.group(3),
                    description,
                )
    target_lo = target_physics_config.get("default_joint_lower_limit")
    target_hi = target_physics_config.get("default_joint_upper_limit")
    base_lo_raw = base_physics_config.get("default_joint_lower_limit")
    base_hi_raw = base_physics_config.get("default_joint_upper_limit")
    _DEFAULT_LO = -math.pi
    _DEFAULT_HI = math.pi
    base_lo = float(base_lo_raw) if base_lo_raw is not None else _DEFAULT_LO
    base_hi = float(base_hi_raw) if base_hi_raw is not None else _DEFAULT_HI
    if target_lo is not None and target_hi is not None and (target_lo != base_lo or target_hi != base_hi):
        def _fmt(v):
            if abs(abs(v) - math.pi) < 1e-9:
                return ("-" if v < 0 else "") + "π"
            ratio = abs(v) / math.pi
            if abs(ratio - round(ratio)) < 1e-9:
                n = int(round(ratio))
                if n == 1:
                    return ("-" if v < 0 else "") + "π"
                else:
                    return ("-" if v < 0 else "") + f"{n}π"
            ratio6 = abs(v) / (math.pi / 6)
            if abs(ratio6 - round(ratio6)) < 1e-9:
                n = int(round(ratio6))
                if n == 1:
                    return ("-" if v < 0 else "") + "π/6"
                else:
                    return ("-" if v < 0 else "") + f"{n}π/6"
            return f"{v:.4f}"
        new_lo_str = _fmt(target_lo)
        new_hi_str = _fmt(target_hi)
        base_lo_str = _fmt(base_lo)
        base_hi_str = _fmt(base_hi)
        _PI = "\u03C0"
        full_circle_text = f"in the range -{_PI} to {_PI} radians (full circle)"
        if full_circle_text in description:
            description = description.replace(
                full_circle_text,
                f"in the range {new_lo_str} to {new_hi_str} radians (restricted; originally {base_lo_str} to {base_hi_str} radians in the source environment)",
            )
        if f"(full \u00B1{_PI} radians in the initial environment)" in description:
            description = description.replace(
                f"(full \u00B1{_PI} radians in the initial environment)",
                f"(now {new_lo_str} to {new_hi_str} radians; originally {base_lo_str} to {base_hi_str} radians in the source environment)",
            )
    return description

def update_success_criteria_for_visible_changes(base_success_criteria: str, target_terrain_config: Dict[str, Any], base_terrain_config: Dict[str, Any]) -> str:
    criteria = base_success_criteria
    target_max_mass = float(target_terrain_config.get("max_structure_mass", _DEFAULT_MAX_STRUCTURE_MASS))
    base_max_mass = float(base_terrain_config.get("max_structure_mass", _DEFAULT_MAX_STRUCTURE_MASS))
    if target_max_mass != base_max_mass:
        mass_pattern = re.compile(r"; default:\s+(\d+\.?\d*)\s+kg\)\.")
        if mass_pattern.search(criteria):
            criteria = mass_pattern.sub(
                lambda m: f"; default now {_mass_str(target_max_mass)} kg). (originally {_mass_str(base_max_mass)} kg in the source environment).",
                criteria,
            )
    return criteria

_UNIFORM_SUFFIX = uniform_suffix_for_task("K_01")

def get_k01_curriculum_stages() -> List[Dict[str, Any]]:
    return [
        {
            "stage_id": "Stage-1",
            "title": "Near-Zero Structure Mass Budget",
            "mutation_description": "Structure mass budget is pushed to a near-breaking extreme. The standard walker design exceeds the budget by over 10×; even a naively simplified design will likely fail. Every gram must be optimized, requiring ultra-light materials, minimal component dimensions, and elimination of all non-essential mass.",
            "task_description_suffix": uniform_suffix_for_task("K_01"),
            "terrain_config": {"max_structure_mass": 0.8},
            "physics_config": {},
        },
        {
            "stage_id": "Stage-2",
            "title": "Near-Zero Ground Traction + Restricted Joints",
            "mutation_description": "Ground traction is reduced to near-zero, and pivot joint range is restricted. Legs slip with almost no grip; the walker must use minimal motor torque to avoid breaking the tiny friction threshold, while operating within a narrow angular window.",
            "task_description_suffix": uniform_suffix_for_task("K_01"),
            "terrain_config": {"ground_friction": 0.02},
            "physics_config": {
                "default_joint_lower_limit": -math.pi / 12,
                "default_joint_upper_limit": math.pi / 12,
            },
        },
        {
            "stage_id": "Stage-3",
            "title": "Dissipative Low-Traction Walking Crown",
            "mutation_description": "A 1.5 kg mass budget excludes the Stage-2 many-legged chassis, while 1.7x gravity raises its support load. Default pivot travel contracts to ±π/14, linear and angular damping rise to 4.0, and the body-friction cap falls to 0.20 on ground friction 0.015. The coupled regime removes coasting, default full-turn wheel motion, heavy contact arrays, and friction-maximization as viable strategy families. A sparse articulated gait must alternate loaded stance and lifted recovery phases while maintaining torso clearance.",
            "task_description_suffix": uniform_suffix_for_task("K_01"),
            "terrain_config": {"ground_friction": 0.015, "max_structure_mass": 1.5},
            "physics_config": {
                "gravity": (0, -17.0),
                "max_body_friction": 0.2,
                "default_joint_lower_limit": -math.pi / 14,
                "default_joint_upper_limit": math.pi / 14,
                "linear_damping": 4.0,
                "angular_damping": 4.0,
            },
        },
        {
            "stage_id": "Stage-4",
            "title": "Maximum Difficulty — All Variables Beyond Stage-3 Extremes",
            "mutation_description": "Ground friction matched at Stage-3's extreme low of 0.01, but every other variable is pushed significantly further: structure mass budget slashed to 1.2 kg (60% less than Stage-3's 3.0), gravity nearly doubled to -20.0 (vs Stage-3's -14.0), body friction cap cut to 0.008 (nearly half of Stage-3's 0.015), joint range squeezed to ±12° (±π/15 vs Stage-3's ±18°), and both linear and angular damping raised to 18.0 (above Stage-3's 16.0). The walker faces double gravitational loading with barely any joint articulation, severe energy dissipation, minimal body friction, and a mass budget so tight that only the most aggressively weight-optimized design can fit. The combination creates a synergistic trap: high gravity demands structural robustness but the tiny mass budget forbids it; high damping kills all momentum between leg contacts; ultra-tight joints restrict the walking gait; and the near-zero body friction cap prevents friction-based traction strategies.",
            "task_description_suffix": uniform_suffix_for_task("K_01"),
            "terrain_config": {"ground_friction": 0.01, "max_structure_mass": 1.2},
            "physics_config": {
                "gravity": (0, -20.0),
                "max_body_friction": 0.008,
                "default_joint_lower_limit": -math.pi / 15,
                "default_joint_upper_limit": math.pi / 15,
                "linear_damping": 18.0,
                "angular_damping": 18.0,
            },
        },
    ]
