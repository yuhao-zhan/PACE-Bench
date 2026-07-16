from __future__ import annotations

from typing import Any, Dict, List

import re

def _get_uniform_task_description_suffix() -> str:
    return """

Sensors indicate that this region exhibits non-standard physical properties.
While the following variables **MIGHT** have changed from the initial environment, **NOT ALL** of them will necessarily be mutated in any given task. You must use active interaction and environmental feedback to deduce which specific conditions apply:
- **Particle Count**: The total number of particles requiring removal may be adjusted.
- **Particle Distribution**: The initial layout and seeding of particles on the surface may have changed.
- **Particle Friction**: The adhesion and resistance of particles to being moved may be altered.
- **Particle Mass**: The mass and inertia of the individual particles may differ from standard.
- **Mass Budget**: The maximum total mass allowed for the wiper structure may differ from standard.
- **Motor Torque Limit**: The maximum torque available at motor-driven joints may differ from standard.
- **Glass Friction**: The friction coefficient of the glass surface, affecting how particles slide along it, may differ from standard.
- **Gravity**: The gravitational acceleration acting on all bodies may differ from standard.

"""

def update_task_description_for_visible_changes(base_description: str, target_terrain_config: Dict[str, Any], base_terrain_config: Dict[str, Any]) -> str:
    description = base_description
    target_count = target_terrain_config.get("particles", {}).get("count", 45)
    base_count = base_terrain_config.get("particles", {}).get("count", 45)
    if target_count != base_count:
        pattern = r"(- \*\*Particles\*\*: )(\d+)( small particles)"
        description = re.sub(pattern, f"\\g<1>{target_count} small particles (originally {base_count} small particles in the source environment)", description)
    target_mass = target_terrain_config.get("max_structure_mass", 15.0)
    base_mass = base_terrain_config.get("max_structure_mass", 15.0)
    if target_mass != base_mass:
        pattern = r"(Total structure mass must be less than )(\d+\.?\d*)( kg)"
        description = re.sub(pattern, f"\\g<1>{target_mass:.2f} kg (originally {base_mass:.2f} kg in the source environment)", description)
    target_motor_cap = target_terrain_config.get("max_motor_torque")
    base_motor_cap = base_terrain_config.get("max_motor_torque")
    if target_motor_cap is not None:
        old_val = f"{base_motor_cap:.1f} N·m" if base_motor_cap is not None else "no cap"
        pattern = r"(- \*\*Motor torque\*\*: )No environment cap \(solver may request up to API limits\)\."
        replacement = f"\\g<1>Capped at {target_motor_cap:.1f} N·m (originally {old_val} in the source environment)."
        if re.search(pattern, description):
            description = re.sub(pattern, replacement, description)
    target_friction = target_terrain_config.get("particles", {}).get("friction", 0.35)
    base_friction = base_terrain_config.get("particles", {}).get("friction", 0.35)
    if target_friction != base_friction:
        pattern = r"(- \*\*Particle Friction\*\*: The particles have a surface friction coefficient of )(\d+\.?\d*)(\.)"
        replacement = f"\\g<1>{target_friction} (originally {base_friction} in the source environment)\\g<3>"
        if re.search(pattern, description):
            description = re.sub(pattern, replacement, description)
    target_particle_mass = target_terrain_config.get("particles", {}).get("mass", 0.15)
    base_particle_mass = base_terrain_config.get("particles", {}).get("mass", 0.15)
    if target_particle_mass != base_particle_mass:
        pattern = r"(- \*\*Particle Mass\*\*: Each particle has a mass of )(\d+\.?\d*)( kg\. This affects the force needed to push them off the glass\.)"
        replacement = f"\\g<1>{target_particle_mass:.2f} kg (originally {base_particle_mass:.2f} kg in the source environment). This affects the force needed to push them off the glass."
        if re.search(pattern, description):
            description = re.sub(pattern, replacement, description)
    target_glass_friction = target_terrain_config.get("glass_friction", 0.25)
    base_glass_friction = base_terrain_config.get("glass_friction", 0.25)
    if target_glass_friction != base_glass_friction:
        pattern = r"(- \*\*Glass Friction\*\*: The glass surface has a friction coefficient of )(\d+\.?\d*)( \(originally \d+\.?\d* in the source environment\)\. This affects how the particles slide along the glass\.)"
        replacement = f"\\g<1>{target_glass_friction} (originally {base_glass_friction} in the source environment). This affects how the particles slide along the glass."
        if re.search(pattern, description):
            description = re.sub(pattern, replacement, description)
    return description

def update_success_criteria_for_visible_changes(base_success_criteria: str, target_terrain_config: Dict[str, Any], base_terrain_config: Dict[str, Any]) -> str:
    criteria = base_success_criteria
    target_mass = target_terrain_config.get("max_structure_mass", 15.0)
    base_mass = base_terrain_config.get("max_structure_mass", 15.0)
    if target_mass != base_mass:
        pattern = r"(\n- \*\*Mass Budget\*\*: < )(\d+\.?\d*)( kg\.)"
        replacement = rf"\g<1>{target_mass:.2f} kg (originally {base_mass:.2f} kg in the source environment)."
        criteria = re.sub(pattern, replacement, criteria)
    target_friction = target_terrain_config.get("particles", {}).get("friction", 0.35)
    base_friction = base_terrain_config.get("particles", {}).get("friction", 0.35)
    if target_friction != base_friction:
        pattern = r"(- \*\*Particle Friction\*\*: The particles have a surface friction coefficient of )(\d+\.?\d*)(\.)"
        replacement = f"\\g<1>{target_friction} (originally {base_friction} in the source environment)\\g<3>"
        if re.search(pattern, criteria):
            criteria = re.sub(pattern, replacement, criteria)
    target_particle_mass = target_terrain_config.get("particles", {}).get("mass", 0.15)
    base_particle_mass = base_terrain_config.get("particles", {}).get("mass", 0.15)
    if target_particle_mass != base_particle_mass:
        pattern = r"(- \*\*Particle Mass\*\*: Each particle has a mass of )(\d+\.?\d*)( kg\. This affects the force needed to push them off the glass\.)"
        replacement = f"\\g<1>{target_particle_mass:.2f} kg (originally {base_particle_mass:.2f} kg in the source environment). This affects the force needed to push them off the glass."
        if re.search(pattern, criteria):
            criteria = re.sub(pattern, replacement, criteria)
    return criteria

def get_k06_curriculum_stages() -> List[Dict[str, Any]]:
    UNIFORM_SUFFIX = _get_uniform_task_description_suffix()
    return [
        {
            "stage_id": "Stage-1",
            "title": "Extreme Motor Torque Starvation",
            "mutation_description": "Motor torque capped at 1.0 N·m. The standard high-torque wiper (requesting 4500 N·m) is completely starved — tip force at full span drops far below particle friction threshold, making single-pivot designs impossible.",
            "task_description_suffix": UNIFORM_SUFFIX,
            "terrain_config": {
                "max_motor_torque": 1.0,
                "particles": {"count": 45, "seed": 42, "friction": 0.35, "mass": 0.15},
            },
            "physics_config": {},
        },
        {
            "stage_id": "Stage-2",
            "title": "Severe Torque Starvation with Near-Maximum Particle Adhesion",
            "mutation_description": "Max motor torque capped at 10.0 N·m; particle friction 0.88. Standard wiper is completely neutered — barely any torque and particles resist sliding.",
            "task_description_suffix": UNIFORM_SUFFIX,
            "terrain_config": {
                "max_motor_torque": 10.0,
                "particles": {"count": 45, "seed": 42, "friction": 0.88, "mass": 0.15},
            },
            "physics_config": {},
        },
        {
            "stage_id": "Stage-3",
            "title": "Mass Starvation vs Heavy Sticky Particle Overload with Capped Torque",
            "mutation_description": "Mass budget 0.10 kg, motor torque cap 28 N·m, 78 heavy sticky particles (0.40 kg each, friction 0.76). Extreme mass constraint forces ultra-minimalist design while heavy high-friction particles demand robust pushing power and limited motor torque restricts sweeping force.",
            "task_description_suffix": UNIFORM_SUFFIX,
            "terrain_config": {
                "max_structure_mass": 0.10,
                "max_motor_torque": 28.0,
                "particles": {"count": 78, "seed": 37, "friction": 0.76, "mass": 0.40},
            },
            "physics_config": {},
        },
        {
            "stage_id": "Stage-4",
            "title": "Extreme: Double Gravity, Glass Adhesion & Torque Starvation Paradox",
            "mutation_description": "Gravity 2.2× (22 m/s²), mass budget 0.06 kg, motor cap 10.0 N·m, glass friction 0.55, 65 particles (0.15 kg each, friction 0.75). Combines extreme conflicting constraints: doubled gravity makes particles nearly immovable, heightened glass friction glues particles to the surface, ultra-tight mass budget forbids any reinforcement, and severely starved torque limits all actuators. Per-particle sliding resistance ≈2.12 N vs 2.06 N in Stage-3 — but torque is cut 2.8× and gravity doubled.",
            "task_description_suffix": UNIFORM_SUFFIX,
            "terrain_config": {
                "max_structure_mass": 0.06,
                "max_motor_torque": 10.0,
                "glass_friction": 0.55,
                "particles": {"count": 65, "seed": 51, "friction": 0.75, "mass": 0.15},
            },
            "physics_config": {
                "gravity": (0, -22),
            },
        },
    ]
