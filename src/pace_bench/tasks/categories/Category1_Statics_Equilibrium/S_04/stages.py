from __future__ import annotations

from typing import Any, Dict, List

import re

UNIFORM_SUFFIX = """
Environmental Anomalies Detected
Sensors indicate that this region exhibits non-standard physical properties.
While the following variables MIGHT have changed from the initial environment, NOT ALL of them will necessarily be mutated in any given task. You must use active interaction and environmental feedback to deduce which specific conditions apply:
 - **Pivot Connection Type**: The type of connection at the central support may differ from the default.
 - **Fragile Anchor Points (Joint Torque Capacity)**: The pivot joint's static torque capacity may differ from the default.
 - **Rotational Friction**: Friction properties at the pivot point may differ from the default.
 - **Precision Thresholds (Angle Tolerance)**: The allowable angular deviation for balance may differ from the default.
 - **Balance Duration**: The required time for which balance must be continuously maintained may differ from the default.
 - **Load Mass**: The mass of the heavy load block may differ from the default.
 - **Lateral Wind Forces**: Wind forces may act on all components.
 - **Gravitational Constant**: Local gravity magnitude may differ from the default.
 - **Spatial Obstructions**: Static structural barriers may occupy parts of the workspace.
 - **Dynamic Loading**: The target mass delivery method may differ from the default.
 - **Angular Damping**: Rotational damping of bodies may differ from the default.

Discovery via feedback: Your objective is to identify the underlying physical rules of this specific environment through trial and reasoning.
"""

def update_task_description_for_visible_changes(base_description: str, target_terrain_config: Dict[str, Any], base_terrain_config: Dict[str, Any]) -> str:
    description = base_description
    base_mass = base_terrain_config.get("load_mass", 200.0)
    target_mass = target_terrain_config.get("load_mass", 200.0)
    if target_mass != base_mass:
        pattern = r"(- \*\*The Load\*\*: A heavy block \(mass: )(\d+\.?\d*)( kg\) )"
        description = re.sub(
            pattern,
            f"\\g<1>{target_mass:.1f} kg (originally {base_mass:.1f} kg in the source environment)) ",
            description,
        )
    base_angle = base_terrain_config.get("max_angle_deviation_deg", 10.0)
    target_angle = target_terrain_config.get("max_angle_deviation_deg", 10.0)
    if target_angle != base_angle:
        angle_pattern = r"(horizontal angle within ±)(\d+\.?\d*)( degrees)(\))( for \d+ seconds\.)"
        if re.search(angle_pattern, description):
            description = re.sub(
                angle_pattern,
                lambda m: f"{m.group(1)}{target_angle:.1f}{m.group(3)} (originally ±{base_angle:.1f} degrees in the source environment)){m.group(5)}",
                description,
            )
    if target_terrain_config.get("drop_load") != base_terrain_config.get("drop_load"):
        if target_terrain_config.get("drop_load"):
            description = description.replace(
                "It may automatically attach (weld) to your structure if any part of your design is built within 0.5m of (3, 5.5), OR it may be DROPPED from above, starting at (3, 9). When dropped, the load is considered caught when within 0.6 m of any part of your structure.",
                "It may be DROPPED from above, starting at (3, 9) (originally static\u2014attach when within 0.5 m of (3, 5.5)\u2014in the source environment). When dropped, the load is considered caught when within 0.6 m of any part of your structure.",
            )
        else:
            description = description.replace(
                "It may automatically attach (weld) to your structure if any part of your design is built within 0.5m of (3, 5.5), OR it may be DROPPED from above, starting at (3, 9). When dropped, the load is considered caught when within 0.6 m of any part of your structure.",
                "It may automatically attach (weld) to your structure if any part of your design is built within 0.5m of (3, 5.5) (originally dropped in the source environment).",
            )
    default_max_joint_torque = 1000.0
    base_torque = base_terrain_config.get("max_joint_torque", default_max_joint_torque)
    target_torque = target_terrain_config.get("max_joint_torque", default_max_joint_torque)
    if target_torque != base_torque:
        torque_pattern = r"(- \*\*Pivot torque capacity\*\* \(when fragile\): In environments where the pivot is fragile, the joint fails if the magnitude of static torque about the pivot exceeds )(\d+\.?\d*)( N·m\.)"
        if re.search(torque_pattern, description):
            description = re.sub(
                torque_pattern,
                lambda m: f"{m.group(1)}{target_torque:.1f} N·m (originally {base_torque:.1f} N·m in the source environment).",
                description,
            )
    if target_terrain_config.get("force_pivot_joint") != base_terrain_config.get("force_pivot_joint"):
        pivot_conn_pattern = r"(2\. Connects to the pivot point at \(0, 5\)\.)"
        if re.search(pivot_conn_pattern, description):
            base_conn = "a free-rotating (revolute) joint" if base_terrain_config.get("force_pivot_joint") else "a fixed weld"
            target_conn = "a free-rotating (revolute) joint" if target_terrain_config.get("force_pivot_joint") else "a fixed weld"
            description = re.sub(
                pivot_conn_pattern,
                f"2. Connects to the pivot point at (0, 5). The pivot is {target_conn} (originally {base_conn} in the source environment).",
                description,
            )
    default_balance_time = 15.0
    base_balance_time = base_terrain_config.get("balance_time", default_balance_time)
    target_balance_time = target_terrain_config.get("balance_time", default_balance_time)
    if target_balance_time != base_balance_time:
        balance_time_pattern = r"( for )(\d+\.?\d*)( seconds\.)"
        if re.search(balance_time_pattern, description):
            description = re.sub(
                balance_time_pattern,
                f"\\g<1>{target_balance_time:.1f} seconds (originally {base_balance_time:.1f} s in the source environment).",
                description,
                1,
            )
    default_ground_y = -5.0
    base_ground_y = base_terrain_config.get("ground_y_failure", default_ground_y)
    target_ground_y = target_terrain_config.get("ground_y_failure", default_ground_y)
    if target_ground_y != base_ground_y:
        ground_lt_pattern = r"(y < )(-?\d+\.?\d*)( m\) will lead to failure\.)"
        if re.search(ground_lt_pattern, description):
            description = re.sub(
                ground_lt_pattern,
                f"\\g<1>{target_ground_y:.1f} m (originally {base_ground_y:.1f} m in the source environment)) will lead to failure.",
                description,
            )
    PIVOT_Y = 5.0
    if target_terrain_config.get("obstacle_active") != base_terrain_config.get("obstacle_active"):
        if target_terrain_config.get("obstacle_active"):
            rects = target_terrain_config.get("obstacles", [])
            if rects:
                world_rects = [(r[0], r[1] + PIVOT_Y, r[2], r[3] + PIVOT_Y) for r in rects]
                obstacle_desc = "; ".join(f"[{xmin:.1f}, {ymin:.1f}, {xmax:.1f}, {ymax:.1f}]" for xmin, ymin, xmax, ymax in world_rects)
                old = "The environment may contain static obstacles you must build around, or experience"
                if base_terrain_config.get("obstacle_active"):
                    new = f"Static obstructions occupy axis-aligned region(s): {obstacle_desc} (originally present but different in the source environment). The environment may experience"
                else:
                    new = f"Static obstructions occupy axis-aligned region(s): {obstacle_desc} (originally none in the source environment). The environment may experience"
                description = description.replace(old, new)
        else:
            old = "The environment may contain static obstacles you must build around, or experience"
            new = "No static obstacles are present (originally present in the source environment). The environment may experience"
            description = description.replace(old, new)
    return description

def update_success_criteria_for_visible_changes(base_success_criteria: str, target_terrain_config: Dict[str, Any], base_terrain_config: Dict[str, Any]) -> str:
    criteria = base_success_criteria
    if target_terrain_config.get("drop_load") != base_terrain_config.get("drop_load"):
        if target_terrain_config.get("drop_load"):
            criteria = criteria.replace(
                "Successfully catch or connect to the heavy load at x=3.0.",
                "Successfully catch the falling load (originally catch or connect to the heavy load at x=3.0 in the source environment).",
            )
        else:
            criteria = criteria.replace(
                "Successfully catch or connect to the heavy load at x=3.0.",
                "Successfully catch or connect to the heavy load at x=3.0 (originally catch the falling load in the source environment).",
            )
    base_angle = base_terrain_config.get("max_angle_deviation_deg", 10.0)
    max_angle = target_terrain_config.get("max_angle_deviation_deg", 10.0)
    if max_angle != base_angle:
        criteria = criteria.replace("within ±10 degrees", f"within ±{max_angle:.1f} degrees (originally ±{base_angle:.1f} degrees in the source environment)")
    default_balance_time = 15.0
    base_balance_time = base_terrain_config.get("balance_time", default_balance_time)
    target_balance_time = target_terrain_config.get("balance_time", default_balance_time)
    if target_balance_time != base_balance_time:
        criteria_balance_pattern = r"(for at least )(\d+\.?\d*)( seconds after the load is supported\.)"
        if re.search(criteria_balance_pattern, criteria):
            criteria = re.sub(
                criteria_balance_pattern,
                f"\\g<1>{target_balance_time:.1f} seconds (originally {base_balance_time:.1f} s in the source environment) after the load is supported.",
                criteria,
                1,
            )
    default_ground_y = -5.0
    base_ground_y = base_terrain_config.get("ground_y_failure", default_ground_y)
    target_ground_y = target_terrain_config.get("ground_y_failure", default_ground_y)
    if target_ground_y != base_ground_y:
        criteria_ground_pattern = r"(The structure does not touch the ground \(y >= )(-?\d+\.?\d*)( m)(\) or any surface other than the pivot\.)"
        if re.search(criteria_ground_pattern, criteria):
            criteria = re.sub(
                criteria_ground_pattern,
                f"\\g<1>{target_ground_y:.1f}\\g<3> (originally {base_ground_y:.1f} m in the source environment)\\g<4>",
                criteria,
            )
    return criteria

def get_s04_curriculum_stages() -> List[Dict[str, Any]]:
    return [
        {
            "stage_id": "Stage-1",
            "title": "The Supermassive Load",
            "mutation_description": "The load mass is tripled to 600 kg. The standard counterweight strategy used in the initial environment is hopelessly inadequate. The challenge: discover the extreme load mass through failure feedback, calculate the precise counterweight needed, and design a structure that achieves perfect torque equilibrium to maintain balance.",
            "task_description_suffix": UNIFORM_SUFFIX,
            "terrain_config": {
                "force_pivot_joint": True,
                "fragile_joints": False,
                "load_mass": 600.0,
                "max_angle_deviation_deg": 10.0,
            },
            "physics_config": {
                "gravity": (0, -10.0),
                "angular_damping": 2.0,
            },
        },
        {
            "stage_id": "Stage-2",
            "title": "The Frictionless Oscillator",
            "mutation_description": "Pivot friction is completely eliminated. Without damping, any imbalance causes sustained oscillation. You must achieve perfect mass distribution to avoid continuous back-and-forth swinging, combined with an extremely tight 1.5° balance tolerance.",
            "task_description_suffix": UNIFORM_SUFFIX,
            "terrain_config": {
                "force_pivot_joint": True,
                "pivot_friction": 0.0,
                "load_mass": 200.0,
                "max_angle_deviation_deg": 1.5,
                "balance_time": 45.0,
            },
            "physics_config": {
                "angular_damping": 0.0,
            },
        },
        {
            "stage_id": "Stage-3",
            "title": "The Hurricane Siege",
            "mutation_description": "Extreme gravity and hurricane-force winds combine with a fragile pivot joint. The torque threshold is set such that imperfect balance will shatter the joint. You must achieve both angle stability AND torque management in a multi-constraint environment with obstacles blocking simple solutions.",
            "task_description_suffix": UNIFORM_SUFFIX,
            "terrain_config": {
                "force_pivot_joint": True,
                "obstacle_active": True,
                "obstacles": [
                    [-5.0, -2.0, -2.0, 0.0],
                    [1.5, 0.0, 3.5, 1.5],
                ],
                "wind_active": True,
                "wind_force_multiplier": 12.0,
                "load_mass": 200.0,
                "fragile_joints": True,
                "max_joint_torque": 8000.0,
                "max_angle_deviation_deg": 15.0,
                "balance_time": 90.0,
            },
            "physics_config": {
                "gravity": (0, -40.0),
                "angular_damping": 0.5,
            },
        },
        {
            "stage_id": "Stage-4",
            "title": "The Dirac Fulcrum",
            "mutation_description": "Sixfold gravity (g=-60), 30x hurricane winds, a hair-trigger 0.5° balance tolerance, and a brutal 180-second endurance requirement combine with high rotational damping. Three obstacles blockade the workspace. Every physical parameter is pushed to its extreme; survival demands millimetric precision in counterweight placement.",
            "task_description_suffix": UNIFORM_SUFFIX,
            "terrain_config": {
                "force_pivot_joint": True,
                "fragile_joints": False,
                "wind_active": True,
                "wind_force_multiplier": 30.0,
                "load_mass": 200.0,
                "max_angle_deviation_deg": 0.5,
                "balance_time": 180.0,
                "obstacle_active": True,
                "obstacles": [
                    [-4.0, 0.2, -2.0, 1.0],
                    [1.0, 0.6, 3.5, 2.5],
                    [-6.0, -7.0, -4.0, -5.0],
                ],
            },
            "physics_config": {
                "gravity": (0, -60.0),
                "angular_damping": 2.0,
            },
        },
    ]
