from __future__ import annotations

from typing import Any, Dict, List

import re

DEFAULT_METEOR_COUNT = 12

DEFAULT_CORE_MAX_FORCE = 150.0

DEFAULT_CORE_X = 10.0

DEFAULT_CORE_Y = 1.0

DEFAULT_MAX_MASS = 300.0

DEFAULT_METEOR_SPAWN_INTERVAL = 30

DEFAULT_WIND_FORCE = 0.0

DEFAULT_METEOR_RESTITUTION = 0.2

DEFAULT_METEOR_DENSITY = 5.0

DEFAULT_FLOOR_FRICTION = 0.5

DEFAULT_MAX_JOINT_FORCE = 1e12

DEFAULT_MAX_JOINT_TORQUE = 1e12

DEFAULT_HAS_WALLS = False

DEFAULT_GRAVITY = (0, -10.0)

def update_task_description_for_visible_changes(
    base_description: str,
    target_terrain_config: Dict[str, Any],
    base_terrain_config: Dict[str, Any],
    target_physics_config: Dict[str, Any] = None,
    base_physics_config: Dict[str, Any] = None,

) -> str:
    description = base_description
    target_has_walls = bool(target_terrain_config.get("has_walls", DEFAULT_HAS_WALLS))
    base_has_walls = bool(base_terrain_config.get("has_walls", DEFAULT_HAS_WALLS))
    if target_has_walls != base_has_walls:
        if target_has_walls:
            description = re.sub(
                r"(Boulders will spawn above the core, mostly targeting the center, but some will fall from the left and right sides\.)( The core is extremely delicate)",
                r"\1 The scene is enclosed by lateral walls; debris ricochets and creates secondary impacts.\2",
                description,
                count=1
            )
        else:
            description = re.sub(
                r"(Boulders will spawn above the core, mostly targeting the center, but some will fall from the left and right sides\.) The scene is enclosed by lateral walls; debris ricochets and creates secondary impacts\.( The core is extremely delicate)",
                r"\1\2",
                description,
                count=1
            )
    target_meteor_count = int(target_terrain_config.get("meteor_count", DEFAULT_METEOR_COUNT))
    base_meteor_count = int(base_terrain_config.get("meteor_count", DEFAULT_METEOR_COUNT))
    target_spawn_interval = int(target_terrain_config.get("meteor_spawn_interval", DEFAULT_METEOR_SPAWN_INTERVAL))
    base_spawn_interval = int(base_terrain_config.get("meteor_spawn_interval", DEFAULT_METEOR_SPAWN_INTERVAL))
    if target_meteor_count != base_meteor_count or target_spawn_interval != base_spawn_interval:
        boulder_pattern = r"(In the nominal mission, )(\d+)( boulders spawn from above \(one every )(\d+)( simulation steps\))(?:, and 4 additional boulders spawn from the left and right sides \(every 90 steps\)\.)"
        if re.search(boulder_pattern, description):
            side_count = target_meteor_count // 3
            side_interval = target_spawn_interval * 3
            base_side_count = base_meteor_count // 3
            base_side_interval = base_spawn_interval * 3
            description = re.sub(
                boulder_pattern,
                f"\\g<1>{target_meteor_count} boulders spawn from above (one every {target_spawn_interval} simulation steps) (originally {base_meteor_count} boulders, one every {base_spawn_interval} simulation steps in the source environment), and {side_count} additional boulders spawn from the left and right sides (every {side_interval} steps) (originally {base_side_count} additional boulders, every {base_side_interval} steps in the source environment).",
                description,
                count=1,
            )
    target_max_mass = target_terrain_config.get("max_structure_mass", DEFAULT_MAX_MASS)
    base_max_mass = base_terrain_config.get("max_structure_mass", DEFAULT_MAX_MASS)
    if target_max_mass != base_max_mass:
        mass_desc_pattern = r"(- \*\*Mass Budget\*\*: Total structure mass must be less than )(\d+\.?\d*) kg\."
        if re.search(mass_desc_pattern, description):
            description = re.sub(
                mass_desc_pattern,
                f"\\g<1>{target_max_mass:.1f} kg (originally {base_max_mass:.1f} kg in the source environment).",
                description
            )
    target_core_x = target_terrain_config.get("core_x", DEFAULT_CORE_X)
    target_core_y = target_terrain_config.get("core_y", DEFAULT_CORE_Y)
    base_core_x = base_terrain_config.get("core_x", DEFAULT_CORE_X)
    base_core_y = base_terrain_config.get("core_y", DEFAULT_CORE_Y)
    if target_core_x != base_core_x or target_core_y != base_core_y:
        core_pos_pattern = r"(Protect a fragile Core \(a sensitive circular object at x=)(\d+\.?\d*)(, y=)(\d+\.?\d*)(\) from)"
        description = re.sub(core_pos_pattern,
                            f"\\g<1>{target_core_x:.1f}\\g<3>{target_core_y:.1f}) (originally x={base_core_x:.1f}, y={base_core_y:.1f} in the source environment). From",
                            description)
        env_core_pattern = r"(- \*\*Core\*\*: A circular object centered at \()(\d+\.?\d*)(, )(\d+\.?\d*)(\) with radius 0\.5 m\.)"
        description = re.sub(env_core_pattern,
                            f"\\g<1>{target_core_x:.1f}\\g<3>{target_core_y:.1f}) (originally centered at ({base_core_x:.1f}, {base_core_y:.1f}) in the source environment) with radius 0.5 m.",
                            description)
        koz_pattern = r"(- \*\*Keep-Out Zone\*\*: You cannot build any structural components within 1.3m of the core center \()(\d+\.?\d*)(, )(\d+\.?\d*)(\)\.)"
        description = re.sub(koz_pattern,
                            f"\\g<1>{target_core_x:.1f}\\g<3>{target_core_y:.1f}) (originally centered at ({base_core_x:.1f}, {base_core_y:.1f}) in the source environment). ",
                            description)
    target_core_force = target_terrain_config.get("max_core_force", DEFAULT_CORE_MAX_FORCE)
    base_core_force = base_terrain_config.get("max_core_force", DEFAULT_CORE_MAX_FORCE)
    if target_core_force != base_core_force:
        description = re.sub(
            r"exceeds (\d+\.?\d*) N \(its structural tolerance\)\.",
            f"exceeds {target_core_force:.1f} N (its structural tolerance) (originally {base_core_force:.1f} N in the source environment).",
            description
        )
    target_joint_force = float(target_terrain_config.get("max_joint_force", DEFAULT_MAX_JOINT_FORCE))
    base_joint_force = float(base_terrain_config.get("max_joint_force", DEFAULT_MAX_JOINT_FORCE))
    target_joint_torque = float(target_terrain_config.get("max_joint_torque", DEFAULT_MAX_JOINT_TORQUE))
    base_joint_torque = float(base_terrain_config.get("max_joint_torque", DEFAULT_MAX_JOINT_TORQUE))
    _num = r"\d+(?:\.\d+)?(?:e[+-]?\d+)?"
    if target_joint_force != base_joint_force:
        description = re.sub(
            rf"(maximum linear force capacity of ){_num} N( and a maximum torque capacity of )",
            f"\\g<1>{target_joint_force:.1e} N (originally {base_joint_force:.1e} N in the source environment)\\g<2>",
            description,
            count=1
        )
    if target_joint_torque != base_joint_torque:
        description = re.sub(
            rf"(maximum torque capacity of ){_num} Nm( in the nominal mission; these limits may be restricted in mission variants\.)\s*",
            rf"\g<1>{target_joint_torque:.1e} Nm\g<2> (originally {base_joint_torque:.1e} Nm in the source environment).",
            description,
            count=1
        )
    target_has_walls = bool(target_terrain_config.get("has_walls", DEFAULT_HAS_WALLS))
    base_has_walls = bool(base_terrain_config.get("has_walls", DEFAULT_HAS_WALLS))
    if target_has_walls != base_has_walls:
        if target_has_walls:
            description = re.sub(
                r"(- \*\*Lateral boundaries\*\*: )The scene has no lateral containment walls; the build zone is open at the sides\.",
                r"\g<1>The scene is enclosed by lateral walls (originally no lateral containment walls in the source environment).",
                description
            )
        else:
            description = re.sub(
                r"(- \*\*Lateral boundaries\*\*: )The scene is enclosed by lateral walls \(originally no lateral containment walls in the source environment\)\.",
                r"\g<1>The scene has no lateral containment walls; the build zone is open at the sides (originally enclosed by lateral walls in the source environment).",
                description
            )
    target_restitution = float(target_terrain_config.get("meteor_restitution", DEFAULT_METEOR_RESTITUTION))
    base_restitution = float(base_terrain_config.get("meteor_restitution", DEFAULT_METEOR_RESTITUTION))
    if target_restitution != base_restitution:
        description = re.sub(
            r"(Boulder elasticity \(restitution\): )(\d+\.\d+) \(low bounce",
            lambda m: f"{m.group(1)}{target_restitution:.2f} (originally {base_restitution:.2f} in the source environment) (low bounce",
            description,
            count=1
        )
        description = re.sub(
            r"(- \*\*Bombardment Parameters\*\*:.*?Boulder restitution: )(\d+\.\d+) \(low bounce",
            lambda m: f"{m.group(1)}{target_restitution:.2f} (originally {base_restitution:.2f} in the source environment) (low bounce",
            description,
            count=1
        )
    target_density = float(target_terrain_config.get("meteor_density", DEFAULT_METEOR_DENSITY))
    base_density = float(base_terrain_config.get("meteor_density", DEFAULT_METEOR_DENSITY))
    if target_density != base_density:
        description = re.sub(
            r"(Boulder density: )(\d+\.?\d*) kg/m² \(affects mass and momentum\)\.",
            f"\\g<1>{target_density:.1f} kg/m² (originally {base_density:.1f} kg/m² in the source environment) (affects mass and momentum).",
            description,
            count=1
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
    target_max_mass = target_terrain_config.get("max_structure_mass", DEFAULT_MAX_MASS)
    base_max_mass = base_terrain_config.get("max_structure_mass", DEFAULT_MAX_MASS)
    if target_max_mass != base_max_mass:
        mass_pattern = r"(- \*\*Mass Budget\*\*: < )(\d+\.?\d*) kg\."
        if re.search(mass_pattern, criteria):
            criteria = re.sub(
                mass_pattern,
                f"\\g<1>{target_max_mass:.1f} kg (originally {base_max_mass:.1f} kg in the source environment).",
                criteria
            )
    target_core_x = target_terrain_config.get("core_x", DEFAULT_CORE_X)
    target_core_y = target_terrain_config.get("core_y", DEFAULT_CORE_Y)
    base_core_x = base_terrain_config.get("core_x", DEFAULT_CORE_X)
    base_core_y = base_terrain_config.get("core_y", DEFAULT_CORE_Y)
    if target_core_x != base_core_x or target_core_y != base_core_y:
        koz_criteria_pattern = r"(- \*\*Keep-Out Zone\*\*: Beam center distance to \()(\d+\.?\d*)(, )(\d+\.?\d*)(\) must be >= 1.3m\.)"
        criteria = re.sub(koz_criteria_pattern,
                         f"\\g<1>{target_core_x:.1f}\\g<3>{target_core_y:.1f}) must be >= 1.3m (originally distance to ({base_core_x:.1f}, {base_core_y:.1f}) in the source environment).",
                         criteria)
    target_core_force = target_terrain_config.get("max_core_force", DEFAULT_CORE_MAX_FORCE)
    base_core_force = base_terrain_config.get("max_core_force", DEFAULT_CORE_MAX_FORCE)
    if target_core_force != base_core_force:
        criteria = re.sub(
            r"(peak impact force on the core must remain below )(\d+\.?\d*)( N\.)",
            f"\\g<1>{target_core_force:.1f} N (originally {base_core_force:.1f} N in the source environment).",
            criteria
        )
        criteria = re.sub(
            r"(Peak force on core < )(\d+\.?\d*)( N\.)",
            f"\\g<1>{target_core_force:.1f} N (originally {base_core_force:.1f} N in the source environment).",
            criteria
        )
    target_has_walls = bool(target_terrain_config.get("has_walls", DEFAULT_HAS_WALLS))
    base_has_walls = bool(base_terrain_config.get("has_walls", DEFAULT_HAS_WALLS))
    if target_has_walls != base_has_walls:
        if target_has_walls:
            criteria = re.sub(
                r"(- \*\*Lateral boundaries\*\*: )The scene has no lateral containment walls\.",
                r"\g<1>The scene is enclosed by lateral walls (originally no lateral containment walls in the source environment).",
                criteria
            )
        else:
            criteria = re.sub(
                r"(- \*\*Lateral boundaries\*\*: )The scene is enclosed by lateral walls \(originally no lateral containment walls in the source environment\)\.",
                r"\g<1>The scene has no lateral containment walls (originally enclosed by lateral walls in the source environment).",
                criteria
            )
    return criteria

UNIFORM_SUFFIX = """
Environmental Anomalies Detected
Sensors indicate that this region exhibits non-standard physical properties.
While the following variables MIGHT have changed from the initial environment, NOT ALL of them will necessarily be mutated in any given task. You must use active interaction and environmental feedback to deduce which specific conditions apply:
 - **Joint Shear Strength (Fragile Anchor Points)**: The maximum linear force and torque that connections can withstand may differ from the nominal environment; joints may fail if limits are exceeded.
 - **Atmospheric Turbulence (Wind)**: Horizontal forces may act on all bodies, affecting structural stability; environmental conditions may differ from the nominal environment.
 - **Mass Budget**: The total allowed mass for construction may differ from the nominal environment.
 - **Meteor Elasticity (Restitution)**: Falling debris elasticity may differ from nominal, affecting ricochets and secondary impacts.
 - **Meteor Mass (Density)**: Falling debris mass density may differ from nominal, affecting impact force and momentum transfer.
 - **Lateral Boundaries (Containment)**: The scene may be enclosed by lateral walls, amplifying ricochets and horizontal debris paths.
 - **Gravitational Constant**: Downward acceleration may differ from nominal; structural loads and impact energy may be affected.
 - **Protected Core Position**: The protected object's location and associated keep-out zone may differ from nominal.
 - **Core Fragility**: The protected object's impact tolerance may differ from nominal.

Discovery via feedback: Your objective is to identify the underlying physical rules of this specific environment through trial and reasoning. Initial standard solutions may fail; analyze the failure mode (e.g., where a joint breaks or how a body moves) to infer the hidden constraints and adapt your design.
"""

def get_s05_curriculum_stages() -> List[Dict[str, Any]]:
    return [
        {
            "stage_id": "Stage-1",
            "title": "The Fragile Anchor",
            "mutation_description": "Joints and ground anchors have severely reduced shear and torque capacity. A standard heavy shelter concentrates impact loads into few weld joints; when any reaction force or torque exceeds the hidden limit, that joint fails and the structure collapses. The agent must discover the failure mode from feedback and redesign so loads are distributed (e.g. more joints, lighter members, or geometry that keeps no single connection above the threshold).",
            "task_description_suffix": UNIFORM_SUFFIX,
            "terrain_config": {
                "max_joint_force": 5000.0,
                "max_joint_torque": 1e12,
            },
            "physics_config": {},
        },
        {
            "stage_id": "Stage-2",
            "title": "The Gale-Force Crucible",
            "mutation_description": "Extreme hurricane-force winds push everything violently leftward while joints are brittle and snap under even moderate loads. Boulders are much denser and more elastic than nominal, creating devastating high-momentum impacts that ricochet unpredictably. The core is extremely fragile — any direct contact is fatal. A standard shelter would have its joints shredded by wind forces or its roof punctured by heavy, bouncy boulders within seconds. The agent must discover the extreme wind, joint fragility, boulder density, boulder elasticity, and core fragility from catastrophic failure feedback and build an ultra-light, multi-anchor distributed-aerodynamic structure that can survive all of these interacting hazards simultaneously.",
            "task_description_suffix": UNIFORM_SUFFIX,
            "terrain_config": {
                "core_x": 5.0,
                "max_core_force": 30.0,
                "wind_force": -250.0,
                "max_joint_force": 3500.0,
                "max_joint_torque": 3500.0,
                "max_structure_mass": 100.0,
                "meteor_density": 9.0,
                "meteor_restitution": 0.8,
            },
            "physics_config": {},
        },
        {
            "stage_id": "Stage-3",
            "title": "The Ricochet Crucible",
            "mutation_description": "Very tight mass budget, fragile joints, and very dense meteors with high elasticity create conflicting constraints: the structure must be lightweight yet withstand heavy impacts without joint failures. Lateral walls cause unpredictable ricochets.",
            "task_description_suffix": UNIFORM_SUFFIX,
            "terrain_config": {
                "max_structure_mass": 2.0,
                "max_joint_force": 7000.0,
                "max_joint_torque": 7000.0,
                "max_core_force": 250.0,
                "meteor_restitution": 0.98,
                "meteor_density": 6.0,
                "has_walls": True,
                "seed": 123,
            },
            "physics_config": {},
        },
        {
            "stage_id": "Stage-4",
            "title": "The Impossible Asymmetry",
            "mutation_description": "Ultra-extreme multi-variable catastrophe — second escalation. The core is pinned at the far-right build-zone boundary (x=14); symmetric sheltering is impossible — the KOZ blocks everything to the right, forcing a pure cantilever from the left. Joints are barely stronger than toothpicks (9200 N / 24200 Nm), the core ruptures at 6.5 N (over 23× more fragile than nominal), and 2.5× gravity amplifies every impact while keeping the structure perpetually unsettled. Wind screams rightward at 80 N/kg, actively driving falling debris INTO the core zone. Perfect-elasticity boulders (restitution 1.0) at 10.0 density ricochet endlessly inside walled boundaries, creating cascading multi-hit chaos. Mass budget is slashed to 1.0 kg. Every variable is pushed to near-breaking; surviving requires a counterintuitive, ultra-distributed, ultra-lightweight cantilever with many redundant anchors — a design no naive model would discover without systematic trial-and-error.",
            "task_description_suffix": UNIFORM_SUFFIX,
            "terrain_config": {
                "core_x": 14.0,
                "max_core_force": 6.5,
                "max_structure_mass": 1.0,
                "max_joint_force": 9200.0,
                "max_joint_torque": 24200.0,
                "wind_force": 80.0,
                "has_walls": True,
                "meteor_restitution": 1.0,
                "meteor_density": 10.0,
            },
            "physics_config": {
                "gravity": (0, -25.0),
            },
        },
    ]
