from __future__ import annotations

from typing import Any, Dict, List

import re

_UNIFORM_SUFFIX_BASE = """

Sensors indicate that this region exhibits non-standard physical properties.
While the following variables **MIGHT** have changed from the initial environment, **NOT ALL** of them will necessarily be mutated in any given task. You must use active interaction and environmental feedback to deduce which specific conditions apply:
- **Gravity**: The gravitational acceleration vector, affecting body weight and drive effectiveness.
- **Object Mass**: The mass of the payload object, affecting the force required to push it.
- **Ground Friction**: The ground surface friction coefficient, affecting traction and pushing dynamics.
- **Object Friction**: The object surface friction coefficient, affecting push dynamics and contact forces.
- **Object Center of Mass**: The payload's center-of-mass offset, affecting its tendency to tip while being pushed.
- **Object Linear Damping**: The payload's resistance to translational motion.
- **Structure Mass Budget**: The maximum permitted mass of the pusher structure.
- **Target Distance**: The required push distance to the target position.

**Discovery via feedback**: Your objective is to identify the underlying physical rules of this specific environment through trial and reasoning. Initial standard solutions may fail; analyze the failure mode (e.g., where the object tips, how the pusher slips, or how far the object moves) to infer the hidden constraints and adapt your design.
"""

def _build_uniform_suffix() -> str:
    return _UNIFORM_SUFFIX_BASE

def update_task_description_for_visible_changes(
    base_description: str,
    target_terrain_config: Dict[str, Any],
    base_terrain_config: Dict[str, Any],

) -> str:
    description = base_description
    target_dist = target_terrain_config.get("target_distance", 10.0)
    base_dist = base_terrain_config.get("target_distance", 10.0)
    if target_dist != base_dist:
        target_pattern = r"(- \*\*Target\*\*: Push the object to at least x=)(\d+\.?\d*)(m)( \([^)]+\)\.)"
        if re.search(target_pattern, description):
            description = re.sub(
                target_pattern,
                f"\\g<1>{8.0 + target_dist:.1f}\\g<3> (originally x={8.0 + base_dist:.1f}m in the source environment).",
                description
            )
        distance_pattern = r"(- \*\*Distance\*\*: The object center reaches x >= )(\d+\.?\d*)(m)\."
        if re.search(distance_pattern, description):
            description = re.sub(
                distance_pattern,
                f"\\g<1>{8.0 + target_dist:.1f}\\g<3> (originally {8.0 + base_dist:.1f}\\g<3> in the source environment).",
                description
            )
    target_bz = target_terrain_config.get("build_zone", {})
    base_bz = base_terrain_config.get("build_zone", {})
    target_x = target_bz.get("x", [0.0, 15.0])
    target_y = target_bz.get("y", [1.5, 8.0])
    base_x = base_bz.get("x", [0.0, 15.0])
    base_y = base_bz.get("y", [1.5, 8.0])
    if (target_x != base_x or target_y != base_y) and isinstance(target_x, (list, tuple)) and isinstance(target_y, (list, tuple)):
        x_min_t, x_max_t = float(target_x[0]), float(target_x[1])
        y_min_t, y_max_t = float(target_y[0]), float(target_y[1])
        x_min_b, x_max_b = float(base_x[0]), float(base_x[1])
        y_min_b, y_max_b = float(base_y[0]), float(base_y[1])
        bz_desc_pattern = r"(- \*\*Build Zone\*\*: x=\[)(\d+\.?\d*),\s*(\d+\.?\d*)(\], y=\[)(\d+\.?\d*),\s*(\d+\.?\d*)(\].)"
        if re.search(bz_desc_pattern, description):
            description = re.sub(
                bz_desc_pattern,
                lambda m: (
                    m.group(1)
                    + f"{x_min_t:.1f}, {x_max_t:.1f}"
                    + m.group(4)
                    + f"{y_min_t:.1f}, {y_max_t:.1f}"
                    + m.group(7)
                ),
                description
            )
        bz_constraint_pattern = r"(All components must stay within x=\[)(\d+\.?\d*),\s*(\d+\.?\d*)(\], y=\[)(\d+\.?\d*),\s*(\d+\.?\d*)(\].)"
        if re.search(bz_constraint_pattern, description):
            description = re.sub(
                bz_constraint_pattern,
                f"\\g<1>{x_min_t:.1f}, {x_max_t:.1f}\\g<4>{y_min_t:.1f}, {y_max_t:.1f}\\g<7> (originally x=[{x_min_b:.1f}, {x_max_b:.1f}], y=[{y_min_b:.1f}, {y_max_b:.1f}] in the source environment).",
                description
            )
    target_obj = target_terrain_config.get("object", {})
    base_obj = base_terrain_config.get("object", {})
    target_obj_mass = target_obj.get("mass") if isinstance(target_obj, dict) else None
    base_obj_mass = base_obj.get("mass", 50.0) if isinstance(base_obj, dict) else 50.0
    if target_obj_mass is not None and target_obj_mass != base_obj_mass:
        heavy_obj_pattern = r"(- \*\*Heavy Object\*\*: A rectangular block 1\.0 m \xd7 0\.8 m \(width \xd7 height\), approximately )(\d+\.?\d*)( kg)(.+)"
        if re.search(heavy_obj_pattern, description):
            def _mass_replacer(m):
                return f"{m.group(1)}{target_obj_mass:.0f}{m.group(3)} (originally {m.group(2)} in the source environment){m.group(4)}"
            description = re.sub(heavy_obj_pattern, _mass_replacer, description)
    target_mass = target_terrain_config.get("max_structure_mass", 40.0)
    base_mass = base_terrain_config.get("max_structure_mass", 40.0)
    if target_mass != base_mass:
        mass_pattern = r"(- \*\*Mass Budget\*\*: Total structure mass must be less than )(\d+\.?\d*)( kg\.)"
        if re.search(mass_pattern, description):
            description = re.sub(
                mass_pattern,
                f"\\g<1>{target_mass:.0f} kg (originally {base_mass:.0f} kg in the source environment).",
                description
            )
    target_gf = target_terrain_config.get("ground_friction", 1.2)
    base_gf = base_terrain_config.get("ground_friction", 1.2)
    if target_gf != base_gf:
        gf_pattern = r"(- \*\*Ground\*\*: A .* friction coefficient )(\d+\.?\d*)(\.)"
        if re.search(gf_pattern, description):
            description = re.sub(
                gf_pattern,
                f"\\g<1>{target_gf:.2f} (originally {base_gf:.2f} in the source environment).",
                description
            )
    target_obj = target_terrain_config.get("object", {})
    base_obj = base_terrain_config.get("object", {})
    target_of = target_obj.get("friction") if isinstance(target_obj, dict) else None
    base_of = base_obj.get("friction", 0.8) if isinstance(base_obj, dict) else 0.8
    if target_of is not None and target_of != base_of:
        of_pattern = r"(with surface friction coefficient )(\d+\.?\d*)(,)"
        if re.search(of_pattern, description):
            description = re.sub(
                of_pattern,
                f"\\g<1>{target_of:.2f} (originally {base_of:.2f} in the source environment)\\g<3>",
                description
            )
    return description

def update_success_criteria_for_visible_changes(base_success_criteria: str, target_terrain_config: Dict[str, Any], base_terrain_config: Dict[str, Any]) -> str:
    criteria = base_success_criteria
    target_dist = target_terrain_config.get("target_distance", 10.0)
    base_dist = base_terrain_config.get("target_distance", 10.0)
    if target_dist != base_dist:
        dist_pattern = r"(\*\*Movement\*\*: Object reaches x >= )(\d+\.?\d*)(m)\."
        if re.search(dist_pattern, criteria):
            criteria = re.sub(
                dist_pattern,
                f"\\g<1>{8.0 + target_dist:.1f}\\g<3> (originally x >= {8.0 + base_dist:.1f}\\g<3> in the source environment).",
                criteria
            )
    target_mass = target_terrain_config.get("max_structure_mass", 40.0)
    base_mass = base_terrain_config.get("max_structure_mass", 40.0)
    if target_mass != base_mass:
        mass_pattern = r"(\*\*Mass Budget\*\*: < )(\d+\.?\d*)( kg)(\.)"
        if re.search(mass_pattern, criteria):
            criteria = re.sub(
                mass_pattern,
                f"\\g<1>{target_mass:.0f}\\g<3> (originally {base_mass:.0f}\\g<3> in the source environment)\\g<4>",
                criteria
            )
    return criteria

def get_k04_curriculum_stages() -> List[Dict[str, Any]]:
    return [
        {
            "stage_id": "Base",
            "title": "Initial Environment",
            "mutation_description": "The base pusher environment with default parameters.",
            "task_description_suffix": "",
            "terrain_config": {},
            "physics_config": {},
        },
        {
            "stage_id": "Stage-1",
            "title": "Tipping Hazard and Mass Budget",
            "mutation_description": "Tight mass budget and object center-of-mass offset; a heavy front-plate pusher exceeds the budget and the object tips if pushed from below.",
            "task_description_suffix": _build_uniform_suffix(),
            "terrain_config": {
                "object": {"center_of_mass_offset": [0.2, 0.25]},
                "max_structure_mass": 26.0,
            },
            "physics_config": {},
        },
        {
            "stage_id": "Stage-2",
            "title": "Payload Mass Variation",
            "mutation_description": "Object mass is very high. The initial pusher structure cannot accelerate it to the target distance in time.",
            "task_description_suffix": _build_uniform_suffix(),
            "terrain_config": {
                "object": {"mass": 95.0},
            },
            "physics_config": {},
        },
        {
            "stage_id": "Stage-3",
            "title": "Modified Friction, Damping, and Mass Budget",
            "mutation_description": "Tight mass budget, significantly reduced friction, and altered object damping. Heavy wheeled pusher exceeds budget; light designs must overcome slip and damping effects.",
            "task_description_suffix": _build_uniform_suffix(),
            "terrain_config": {
                "ground_friction": 0.3,
                "object": {"friction": 0.08, "linear_damping": 4.0},
                "max_structure_mass": 26.0,
            },
            "physics_config": {},
        },
        {
            "stage_id": "Stage-4",
            "title": "Heavy Object, Slippery Surfaces, Strong Damping, Tight Budget, and High Gravity",
            "mutation_description": "An ultra-heavy object rests on near-frictionless surfaces with extreme linear damping, very high gravity, a far target distance, the tightest mass budget, and a shifted center-of-mass. Initial reference designs fail on mass budget; even compliant designs must overcome massive inertia, aggressive damping, and near-zero surface grip.",
            "task_description_suffix": _build_uniform_suffix(),
            "terrain_config": {
                "ground_friction": 0.06,
                "object": {
                    "mass": 110.0,
                    "friction": 0.03,
                    "linear_damping": 12.0,
                    "center_of_mass_offset": [0.24, 0.28],
                },
                "target_distance": 16.0,
                "max_structure_mass": 22.0,
            },
            "physics_config": {"gravity": (0, -18.0)},
        },
    ]
