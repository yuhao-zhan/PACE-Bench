from __future__ import annotations

import re

from typing import Any, Dict, List

DEFAULT_JOINT_BREAK_FORCE = 6.0

DEFAULT_JOINT_BREAK_TORQUE = 10.0

def _get_annotated_task_description(physics_config: Dict[str, Any]) -> str:
    import importlib
    import os
    _dir = os.path.dirname(os.path.abspath(__file__))
    _spec = importlib.util.spec_from_file_location("_prompt_mod", os.path.join(_dir, "prompt.py"))
    _prompt_mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_prompt_mod)
    TASK_PROMPT = _prompt_mod.TASK_PROMPT
    base_td = TASK_PROMPT["task_description"]
    return update_task_description_for_visible_changes(
        base_description=base_td,
        target_terrain_config={},
        base_terrain_config={},
        target_physics_config=physics_config,
        base_physics_config={},
    )

_DEFAULT_GRAVITY = (0, -10.0)

def _fmt_limit(value: float) -> str:
    if value == 0 or (abs(value) < 1e-6 and value != 0):
        return f"{value:.4g}"
    if abs(value) >= 1000 or (abs(value) < 0.001 and value != 0):
        return f"{value:.4g}"
    return f"{value:.4f}".rstrip("0").rstrip(".")

TASK_DESCRIPTION_SUFFIX = """

Sensors indicate that this region exhibits non-standard physical properties.
While the following variables **MIGHT** have changed from the initial environment, **NOT ALL** of them will necessarily be mutated in any given task. You must use active interaction and environmental feedback to deduce which specific conditions apply:
- **Aerodynamic Loading**: Atmospheric properties may differ from nominal conditions.
- **Wind Pressure**: Lateral wind pressure magnitude may differ from the nominal value.
- **Connection Axial Strength**: Connection strength parameters may be non-standard.
- **Connection Torsional Yield**: Connection torsional properties may be non-standard.
- **Base Excitation**: Ground support oscillation characteristics may differ from the nominal pattern.
- **Dynamic Mass Resonance**: Mass variation characteristics (frequency, amplitude, spatial phase) may differ from the nominal pattern.
- **Progressive Structural Fatigue**: Joint strength may decay over time under sustained loading.
- **Fatigue Time Constant**: The fatigue time constant may differ from the nominal value.
- **Gravitational Field**: Gravitational field properties may differ from the nominal field.

**Discovery via feedback**: Your objective is to identify the underlying physical rules of this specific environment through trial and reasoning. Initial standard solutions may fail; analyze the failure mode (e.g., where a joint breaks or how a body moves) to infer the hidden constraints and adapt your design.
"""

def update_task_description_for_visible_changes(
    base_description: str,
    target_terrain_config: Dict[str, Any],
    base_terrain_config: Dict[str, Any],
    target_physics_config: Dict[str, Any] = None,
    base_physics_config: Dict[str, Any] = None,

) -> str:
    description = base_description
    target_physics_config = target_physics_config or {}
    base_physics_config = base_physics_config or {}
    base_force = base_physics_config.get("joint_break_force", DEFAULT_JOINT_BREAK_FORCE)
    base_torque = base_physics_config.get("joint_break_torque", DEFAULT_JOINT_BREAK_TORQUE)
    target_force = target_physics_config.get("joint_break_force", base_force)
    target_torque = target_physics_config.get("joint_break_torque", base_torque)
    if target_force != base_force:
        force_pattern = r"(Joints fail if reaction force exceeds )(\d+\.?\d*e?-?\d*)( N or reaction torque exceeds )(\d+\.?\d*e?-?\d*)( N·m)(\s*\(before fatigue decay\)\.?)"
        if re.search(force_pattern, description):
            description = re.sub(
                force_pattern,
                lambda m: f"{m.group(1)}{_fmt_limit(target_force)} N (originally {_fmt_limit(base_force)} N in the source environment) or reaction torque exceeds {_fmt_limit(target_torque)} N·m (originally {_fmt_limit(base_torque)} N·m in the source environment) (before fatigue decay).",
                description,
            )
        else:
            alt_force_pattern = r"(reaction force exceeds )(\d+\.?\d*e?-?\d*)( N)"
            if re.search(alt_force_pattern, description):
                description = re.sub(
                    alt_force_pattern,
                    lambda m: f"{m.group(1)}{_fmt_limit(target_force)} N (originally {_fmt_limit(base_force)} N in the source environment)",
                    description,
                    1,
                )
    if target_torque != base_torque:
        _fp_combined_fired = target_force != base_force
        if not _fp_combined_fired:
            torque_pattern = r"(reaction torque exceeds )(\d+\.?\d*e?-?\d*)( N·m)(\s*\(before fatigue decay\)\.?)"
            if re.search(torque_pattern, description):
                description = re.sub(
                    torque_pattern,
                    lambda m: f"{m.group(1)}{_fmt_limit(target_torque)} N·m (originally {_fmt_limit(base_torque)} N·m in the source environment) (before fatigue decay).",
                    description,
                )
            else:
                alt_torque_pattern = r"(reaction torque exceeds )(\d+\.?\d*e?-?\d*)( N·m)"
                if re.search(alt_torque_pattern, description):
                    description = re.sub(
                        alt_torque_pattern,
                        lambda m: f"{m.group(1)}{_fmt_limit(target_torque)} N·m (originally {_fmt_limit(base_torque)} N·m in the source environment)",
                        description,
                        1,
                    )
    base_tau = base_physics_config.get("fatigue_tau_seconds", 100.0)
    target_tau = target_physics_config.get("fatigue_tau_seconds", base_tau)
    if target_tau != base_tau:
        tau_pattern = r"(exp\(-t/)(τ)(\)\.)"
        if re.search(tau_pattern, description):
            description = re.sub(
                tau_pattern,
                lambda m: f"exp(-t/{_fmt_limit(target_tau)}) (originally exp(-t/{_fmt_limit(base_tau)}) in the source environment).",
                description,
            )
    return description

def update_success_criteria_for_visible_changes(base_success_criteria: str, target_terrain_config: Dict[str, Any], base_terrain_config: Dict[str, Any]) -> str:
    return base_success_criteria

def get_e04_curriculum_stages() -> List[Dict[str, Any]]:
    stage1_physics = {
        "mass_freq_1": 1.5,
        "mass_amp_1": 0.4,
        "joint_break_force": 0.005,
        "joint_break_torque": 0.002,
    }
    stage2_physics = {
        "joint_break_torque": 1e-10,
        "wind_pressure": 10000.0,
        "fatigue_tau_seconds": 400.0,
    }
    stage3_physics = {
        "wind_pressure": 1500.0,
        "mass_phase_gradient": 15.0,
        "mass_amp_1": 0.4,
        "fatigue_tau_seconds": 400.0,
        "joint_break_torque": 0.05,
    }
    stage4_physics = {
        "gravity": (15000.0, -30.0),
        "joint_break_torque": 1e-10,
        "fatigue_tau_seconds": 60.0,
    }
    return [
        {
            "stage_id": "Stage-1",
            "title": "Resonant Instability",
            "mutation_description": "Structural mass varies at high frequency with large amplitude, targeting standard beam resonance.",
            "task_description": _get_annotated_task_description(stage1_physics),
            "task_description_suffix": TASK_DESCRIPTION_SUFFIX,
            "terrain_config": {},
            "physics_config": stage1_physics,
        },
        {
            "stage_id": "Stage-2",
            "title": "The Weld-less Truss",
            "mutation_description": "Joints cannot resist ANY torque. Structure must be a perfect funicular arch or truss.",
            "task_description": _get_annotated_task_description(stage2_physics),
            "task_description_suffix": TASK_DESCRIPTION_SUFFIX,
            "terrain_config": {},
            "physics_config": stage2_physics,
        },
        {
            "stage_id": "Stage-3",
            "title": "The Lateral Vortex",
            "mutation_description": "Extreme wind pressure combined with high spatial mass phase gradient creating non-uniform twisting loads.",
            "task_description": _get_annotated_task_description(stage3_physics),
            "task_description_suffix": TASK_DESCRIPTION_SUFFIX,
            "terrain_config": {},
            "physics_config": stage3_physics,
        },
        {
            "stage_id": "Stage-4",
            "title": "Gravitational Shear",
            "mutation_description": "Massive lateral gravity vector combined with zero torque capacity and rapid fatigue.",
            "task_description": _get_annotated_task_description(stage4_physics),
            "task_description_suffix": TASK_DESCRIPTION_SUFFIX,
            "terrain_config": {},
            "physics_config": stage4_physics,
        },
    ]
