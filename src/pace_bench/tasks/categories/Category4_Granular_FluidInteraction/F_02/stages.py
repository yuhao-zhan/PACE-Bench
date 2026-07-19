from __future__ import annotations

from typing import Any, Dict, List

import re

def update_task_description_for_visible_changes(base_description: str, target_terrain_config: Dict[str, Any], base_terrain_config: Dict[str, Any]) -> str:
    description = base_description
    default_cooldown = 3
    target_cooldown = int(target_terrain_config.get("thrust_cooldown_steps", default_cooldown))
    base_cooldown = int(base_terrain_config.get("thrust_cooldown_steps", default_cooldown))
    if target_cooldown != base_cooldown:
        cooldown_pattern = r"(\s*- \*\*Propulsion\*\*: .* \*\*Cooldown\*\*: Each component has a )(\d+)(-step cooldown between thrusts\.)"
        if re.search(cooldown_pattern, description):
            description = re.sub(
                cooldown_pattern,
                f"\\g<1>{target_cooldown}-step (originally {base_cooldown}-step in the source environment) cooldown between thrusts.",
                description
            )
    default_current = 5.5
    target_current = float(target_terrain_config.get("current_per_kg", default_current))
    base_current = float(base_terrain_config.get("current_per_kg", default_current))
    if target_current != base_current:
        current_pattern = r"(current \(standard )(\d+\.?\d*)( N/kg)( opposing force on submerged bodies\))"
        replacement = r"\g<1>" + f"{target_current:.1f}" + r" N/kg (originally " + f"{base_current:.1f}" + r" N/kg in the source environment)\g<4>"
        description = re.sub(current_pattern, replacement, description)
    target_emp = target_terrain_config.get("emp_zone")
    base_emp = base_terrain_config.get("emp_zone")
    emp_pattern = r"(- \*\*Electromagnetic Deadzone\*\*: .+?)not present in this environment\."
    if target_emp is not None:
        emp_replacement = f"- **Electromagnetic Deadzone**: Electromagnetic field regions (EMP) that disable thrust for components entering them: EMP active at x={target_emp[0]:.1f}–{target_emp[1]:.1f}m (originally "
        if base_emp is None:
            emp_replacement += "not present in the source environment"
        else:
            emp_replacement += f"x={base_emp[0]:.1f}–{base_emp[1]:.1f}m in the source environment"
        emp_replacement += ")."
        if re.search(emp_pattern, description):
            description = re.sub(emp_pattern, emp_replacement, description)
    elif target_emp is None and base_emp is not None:
        emp_replacement = f"- **Electromagnetic Deadzone**: Electromagnetic field regions (EMP) that disable thrust for components entering them: not present (originally x={base_emp[0]:.1f}–{base_emp[1]:.1f}m in the source environment)."
        if re.search(emp_pattern, description):
            description = re.sub(emp_pattern, emp_replacement, description)
    target_corrosive = target_terrain_config.get("corrosive_y")
    base_corrosive = base_terrain_config.get("corrosive_y")
    corrosive_pattern = r"(- \*\*Corrosive Altitude Ceiling\*\*: .+?)not present in this environment\."
    if target_corrosive is not None:
        base_corrosive_str = f"y={base_corrosive}m" if base_corrosive is not None else "not present"
        corrosive_replacement = f"- **Corrosive Altitude Ceiling**: A toxic atmospheric layer above the water that applies catastrophic downward crushing forces to elevated structures: toxic layer at y={target_corrosive}m (originally {base_corrosive_str} in the source environment)."
        if re.search(corrosive_pattern, description):
            description = re.sub(corrosive_pattern, corrosive_replacement, description)
    elif target_corrosive is None and base_corrosive is not None:
        corrosive_replacement = f"- **Corrosive Altitude Ceiling**: A toxic atmospheric layer above the water that applies catastrophic downward crushing forces to elevated structures: not present (was y={base_corrosive}m in the source environment)."
        if re.search(corrosive_pattern, description):
            description = re.sub(corrosive_pattern, corrosive_replacement, description)
    target_whirlpool = target_terrain_config.get("whirlpool")
    base_whirlpool = base_terrain_config.get("whirlpool")
    whirlpool_pattern = r"(- \*\*Abyssal Whirlpool\*\*: .+?)not present in this environment\."
    if target_whirlpool is not None:
        base_wp_str = f"at x={base_whirlpool.get('x',17.0):.1f}m" if base_whirlpool else "not present"
        whirlpool_replacement = f"- **Abyssal Whirlpool**: Localized vortexes in the water channel that generate extreme downward suction on submerged or floating masses: vortex at x={target_whirlpool.get('x',17.0):.1f}m (width={target_whirlpool.get('width',2.0):.1f}m, force={target_whirlpool.get('force',100.0):.0f}N/kg) (originally {base_wp_str} in the source environment)."
        if re.search(whirlpool_pattern, description):
            description = re.sub(whirlpool_pattern, whirlpool_replacement, description)
    elif target_whirlpool is None and base_whirlpool is not None:
        whirlpool_replacement = f"- **Abyssal Whirlpool**: Localized vortexes in the water channel that generate extreme downward suction on submerged or floating masses: not present (was at x={base_whirlpool.get('x',17.0):.1f}m in the source environment)."
        if re.search(whirlpool_pattern, description):
            description = re.sub(whirlpool_pattern, whirlpool_replacement, description)
    return description

def update_success_criteria_for_visible_changes(base_success_criteria: str, target_terrain_config: Dict[str, Any], base_terrain_config: Dict[str, Any]) -> str:
    criteria = base_success_criteria
    default_mass = 600.0
    target_mass = float(target_terrain_config.get("max_structure_mass", default_mass))
    base_mass = float(base_terrain_config.get("max_structure_mass", default_mass))
    if target_mass != base_mass:
        mass_pattern = r"(\s*- \*\*Mass Budget\*\*: Total structure mass <= )(\d+)( kg\.)"
        if re.search(mass_pattern, criteria):
            criteria = re.sub(
                mass_pattern,
                f"\\g<1>{target_mass:.0f} kg (originally {base_mass:.0f} kg in the source environment).",
                criteria
            )
    default_joint_force = float('inf')
    target_joint_force = target_terrain_config.get("max_joint_force", default_joint_force)
    base_joint_force = base_terrain_config.get("max_joint_force", default_joint_force)
    joint_limit_pattern = r"(- \*\*Joint Strength\*\*: Maximum force before shear is )(\d+\.?\d*)( N \(originally .+ in the source environment\)\.)"
    joint_no_limit_pattern = r"(- \*\*Joint Strength\*\*: Structural connections do not break under load \(no force limit\)\.)"
    joint_no_limit_with_origin_pattern = r"(- \*\*Joint Strength\*\*: Structural connections do not break under load \(no force limit\) \(originally .+ in the source environment\)\.)"
    if target_joint_force != base_joint_force:
        base_str = "no limit" if base_joint_force == float('inf') else f"{base_joint_force:.0f} N"
        if target_joint_force != float('inf'):
            if re.search(joint_no_limit_pattern, criteria):
                criteria = re.sub(
                    joint_no_limit_pattern,
                    f"- **Joint Strength**: Maximum force before shear is {target_joint_force:.0f} N (originally {base_str} in the source environment).",
                    criteria
                )
            elif re.search(joint_no_limit_with_origin_pattern, criteria):
                criteria = re.sub(
                    joint_no_limit_with_origin_pattern,
                    f"- **Joint Strength**: Maximum force before shear is {target_joint_force:.0f} N (originally {base_str} in the source environment).",
                    criteria
                )
            elif re.search(joint_limit_pattern, criteria):
                criteria = re.sub(
                    joint_limit_pattern,
                    f"\\g<1>{target_joint_force:.0f} N (originally {base_str} in the source environment).",
                    criteria
                )
        else:
            if re.search(joint_limit_pattern, criteria):
                criteria = re.sub(
                    joint_limit_pattern,
                    f"- **Joint Strength**: Structural connections do not break under load (no force limit) (originally {base_str} in the source environment).",
                    criteria
                )
    return criteria

def get_f02_curriculum_stages() -> List[Dict[str, Any]]:
    UNIFORM_SUFFIX = """

Sensors indicate that this region exhibits non-standard physical properties.
While the following variables **MIGHT** have changed from the initial environment, **NOT ALL** of them will necessarily be mutated in any given task. You must use active interaction and environmental feedback to deduce which specific conditions apply:
- **Water Current Intensity** may differ from the source environment.
- **Electromagnetic Deadzone** may be present.
- **Corrosive Altitude Ceiling** may be present.
- **Abyssal Whirlpools** may be present.
- **Joint Strength** may differ from the source environment.
- **Thrust Cooldown Duration** may differ from the source environment.

**Discovery via feedback**: Your objective is to identify the underlying physical rules of this specific environment through trial and reasoning. Initial standard solutions may fail; analyze the failure mode (e.g., where a joint breaks or how a body moves) to infer the hidden constraints and adapt your design.
"""
    return [
        {
            "stage_id": "Stage-1",
            "title": "The Sluggish Dawn",
            "mutation_description": "Thrust cooldown extended to an astronomical 200 steps (originally 3). Each component fires only once every 3.3 seconds, rendering conventional propulsion strategies completely obsolete. A standard fleet of 9 beams produces an average of only 23 N/step forward thrust — utterly incapable of countering even the standard 5.5 N/kg water current on 68 kg of mass (376 N backward), let alone achieving forward progress. Every traditional design is doomed to drift backward into failure. Survival demands a fundamental rethinking of the relationship between component count, mass, and propulsion scheduling.",
            "task_description_suffix": UNIFORM_SUFFIX,
            "terrain_config": {
                "thrust_cooldown_steps": 200,
            },
            "physics_config": {},
        },
        {
            "stage_id": "Stage-2",
            "title": "The Brittle Expanse",
            "mutation_description": "All structural connections shear at the slightest stress — 1.0 N of force snaps any joint. Joint-dependent designs collapse instantly; the only viable path is a joint-less fleet that launches airborne to avoid water drag entirely.",
            "task_description_suffix": UNIFORM_SUFFIX,
            "terrain_config": {
                "max_joint_force": 1.0,
            },
            "physics_config": {},
        },
        {
            "stage_id": "Stage-3",
            "title": "The Maelstrom",
            "mutation_description": "A violent whirlpool pulls vehicles down. Weak joints prevent rigid brute-force bridging.",
            "task_description_suffix": UNIFORM_SUFFIX,
            "terrain_config": {
                "whirlpool": {"x": 17.0, "width": 4.0, "force": 200.0},
                "max_joint_force": 200.0,
            },
            "physics_config": {},
        },
        {
            "stage_id": "Stage-4",
            "title": "The Gauntlet of Contradictions",
            "mutation_description": "A catastrophic confluence of extreme forces. EMP deadzone (x=14.0–15.2) disables all thrust through a 1.2 m gauntlet while a 28.0 N/kg current tears backward at every submerged kilogram — in water, drag kills speed instantly, so the EMP is a wall that only airborne flight can clear. No sooner does the EMP relent at x=15.2 than a ferocious whirlpool (centered at x=17.5 m, width=4.0 m, 240.0 N/kg downward suction) engages at x=15.5, leaving a razor-thin 0.3 m window to react. Joints shear at a laughable 30.0 N, forbidding rigid chaining. Thrust cooldown stretched to 18 steps cripples reaction time. A corrosive ceiling at y=2.7 seals off any high-altitude escape — the flight ceiling forces a ballistic trajectory that must thread the needle: start high enough to clear the EMP above the water, but not so high that toxic incineration triggers. Every conventional strategy — chained fleets, airborne skips, massed thrust — is shattered by at least two constraints simultaneously. Survival demands a design that is jointless, ultra-lightweight, stagger-fired, and precisely altitude-managed.",
            "task_description_suffix": UNIFORM_SUFFIX,
            "terrain_config": {
                "emp_zone": [14.0, 15.2],
                "corrosive_y": 2.7,
                "whirlpool": {"x": 17.5, "width": 4.0, "force": 240.0},
                "current_per_kg": 28.0,
                "max_joint_force": 30.0,
                "thrust_cooldown_steps": 18,
            },
            "physics_config": {},
        },
    ]
