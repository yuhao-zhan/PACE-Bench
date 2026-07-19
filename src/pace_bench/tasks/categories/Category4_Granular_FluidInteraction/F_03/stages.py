from __future__ import annotations

from typing import Any, Dict, List

import re

_DEFAULT_GRAVITY_F03 = (0, -10.0)

UNIFORM_TASK_DESCRIPTION_SUFFIX = """

Sensors indicate that this region exhibits non-standard physical properties.
While the following variables **MIGHT** have changed from the initial environment, **NOT ALL** of them will necessarily be mutated in any given task. You must use active interaction and environmental feedback to deduce which specific conditions apply:
- **Particle Friction**: The surface traction between individual grains may be altered, affecting how easily material slides or piles within the scoop.
- **Ambient Damping**: The rate at which mechanical motion and material flow are resisted by the environment may have changed.
- **Transfer Requirement**: The minimum quantity of material that must be successfully relocated to the target zone for mission success may be adjusted.
- **Internal Pit Drift**: Persistent lateral forces acting within the excavation zone may vary, potentially shifting material or resisting scoop entry.
- **Volumetric Capacity**: Hidden limits on how much material can be effectively retained and transported during each cycle of operation may be altered.
- **Build Zone**: The permitted construction volume (x and y bounds within which the mechanism must be built) may be adjusted.
- **Mass Restriction**: The maximum allowable total structural mass may be adjusted from the standard constraint, requiring lighter or heavier designs.
- **Gravitational Field**: The strength and direction of the gravitational field may deviate from standard Earth-like conditions.
- **Time Limit**: The maximum allowed duration for completing the mission may be adjusted.

**Discovery via feedback**: Your objective is to identify the underlying physical rules of this specific environment through trial and reasoning. Initial standard solutions may fail; analyze the failure mode (e.g., how a body moves or how material behaves) to infer the hidden constraints and adapt your design.
"""

def update_task_description_for_visible_changes(
    base_description: str, target_terrain_config: Dict[str, Any], base_terrain_config: Dict[str, Any],
    target_physics_config: Dict[str, Any] = None, base_physics_config: Dict[str, Any] = None,
    **kwargs,

) -> str:
    description = base_description
    tp = target_physics_config or {}
    bp = base_physics_config or {}
    target_bx = target_terrain_config.get("build_zone_x_max", 2.0)
    base_bx = base_terrain_config.get("build_zone_x_max", 2.0)
    target_by = target_terrain_config.get("build_zone_y_max", 5.0)
    base_by = base_terrain_config.get("build_zone_y_max", 5.0)
    if target_bx != base_bx or target_by != base_by:
        pattern = r"(- \*\*Build Zone\*\*: Mechanism must be built in x=\[)([^\]]+)(\], y=\[)([^\]]+)(\]\.)( )(Base is anchored at x=-2\.0 m, y=0\.0 m \(evaluator accepts any body within 0\.5 m of this position\)\.)"
        replacement = f"\\g<1>-4.0, {target_bx}\\g<3>0.0, {target_by}] (originally x=[-4.0, {base_bx}], y=[0.0, {base_by}] in the source environment).\\g<6>\\g<7>"
        description = re.sub(pattern, replacement, description)
    default_scoop_capacity = 999
    target_scoop = int(target_terrain_config.get("scoop_capacity", default_scoop_capacity))
    base_scoop = int(base_terrain_config.get("scoop_capacity", default_scoop_capacity))
    if target_scoop != base_scoop:
        capacity_note = (
            f"**Scoop Capacity**: [{target_scoop}] (originally {base_scoop} in the source environment)."
        )
        discovery_marker = "**Discovery via feedback**"
        if discovery_marker in description:
            description = description.replace(
                discovery_marker,
                capacity_note + "\n" + discovery_marker,
                1
            )
        else:
            description += "\n" + capacity_note
    default_max_time = 40
    target_max_time = int(target_terrain_config.get("max_time_seconds", default_max_time))
    base_max_time = int(base_terrain_config.get("max_time_seconds", default_max_time))
    if target_max_time != base_max_time:
        pattern = r"(within )(\d+)( seconds)"
        if re.search(pattern, description):
            description = re.sub(
                pattern,
                f"\\g<1>{target_max_time} (originally {base_max_time} in the source environment)\\g<3>",
                description,
            )
    default_mass = 800
    target_mass = int(target_terrain_config.get("max_structure_mass", default_mass))
    base_mass = int(base_terrain_config.get("max_structure_mass", default_mass))
    if target_mass != base_mass:
        pattern = r"(Total structure mass <= )(\d+)( kg)"
        if re.search(pattern, description):
            description = re.sub(
                pattern,
                f"\\g<1>{target_mass} (originally {base_mass} in the source environment)\\g<3>",
                description,
            )
    return description

def update_success_criteria_for_visible_changes(
    base_success_criteria: str, target_terrain_config: Dict[str, Any], base_terrain_config: Dict[str, Any],
    target_physics_config: Dict[str, Any] = None, base_physics_config: Dict[str, Any] = None,
    **kwargs,

) -> str:
    criteria = base_success_criteria
    tp = target_physics_config or {}
    bp = base_physics_config or {}
    target_count = target_terrain_config.get("min_particles_in_hopper", 15)
    base_count = base_terrain_config.get("min_particles_in_hopper", 15)
    if target_count != base_count:
        pattern = r"(1\. \*\*Material Transfer\*\*: At least )(\d+)( sand particles are deposited in the hopper zone)"
        if re.search(pattern, criteria):
            criteria = re.sub(
                pattern,
                f"\\g<1>{target_count} (originally {base_count} in the source environment)\\g<3>",
                criteria,
            )
    return criteria

def get_f03_curriculum_stages() -> List[Dict[str, Any]]:
    return [
        {
            "stage_id": "Stage-1",
            "title": "Mass starvation — paper-thin mandate",
            "mutation_description": "Mass budget slashed to 30 kg — a 96% reduction from the standard 800 kg. The Initial agent's standard design weighs approximately 278 kg and fails the mass check instantly at step 0 — it cannot even begin operation. The agent must discover that structural integrity in Box2D is independent of density, allowing extreme weight reduction without compromising strength. Every beam, the tower, and the scoop must use densities 10-100x below standard values. This is not a parameter tweak — it is a fundamental re-engineering: the tower at default density alone exceeds the entire budget, so every component must be rethought. Standard motor torque (3000 Nm) remains sufficient for the ultra-light mechanism, but the real challenge is designing a 2-DOF excavator that weighs less than a single standard beam. The scoop and arm must still collect and transport at least 15 particles within 40 seconds.",
            "task_description_suffix": UNIFORM_TASK_DESCRIPTION_SUFFIX,
            "terrain_config": {
                "max_structure_mass": 30,
            },
            "physics_config": {},
        },
        {
            "stage_id": "Stage-2",
            "title": "Micro-scoop restriction",
            "mutation_description": "Scoop capacity limited to 2 particles per trip (from unlimited/default 999). The Initial agent's 10 s cycle completes only 4 trips per run — at 2 particles per trip that delivers at most 8 particles, far short of the 15 required. The agent must radically shorten its work cycle to <=5 s to complete enough trips (>=8) within 40 s. Higher motor speeds and reduced phase durations are essential; the mechanical design itself may remain standard.",
            "task_description_suffix": UNIFORM_TASK_DESCRIPTION_SUFFIX,
            "terrain_config": {
                "scoop_capacity": 2,
            },
            "physics_config": {},
        },
        {
            "stage_id": "Stage-3",
            "title": "Heavy gravity, ice particles, drift storm, mass starvation, capacity famine, time crunch",
            "mutation_description": "Gravity doubled to 2.0x normal (20 m/s^2) makes every lift a struggle — the gravitational torque on the standard 4 m arm at horizontal reaches ~3800 Nm, exceeding the initial agent's 3000 Nm motor. Damping quadrupled to 4x normal (0.08) makes all motion extremely sluggish, sapping energy from every movement. Particle friction dropped to near-zero (0.04) so grains behave like ice on glass, sliding out of the scoop at the slightest tilt or acceleration. Combined with maximum pit drift (1.0) that aggressively pushes particles rightward away from the scoop zone, capturing any material becomes a precision operation requiring exact scoop positioning and gentle transport. Scoop capacity limited to a mere 8 particles per trip forces at least 4 complete cycles. Mass budget slashed to 120 kg — the standard 278 kg design fails the mass check instantly and cannot even be built. Only 20 seconds to deliver 30+ particles — the standard 10 s cycle would complete at most 2 trips, collecting at most 16 particles, nowhere near the 30 required. This is a multi-dimensional trap: doubled gravity demands powerful motors, but the mass budget forbids heavy construction; near-zero friction and max drift demand impossibly precise scoop control under quadruple damping; and the capacity-time squeeze (8/trip, 30 target, 20s) demands fast, precise cycles.",
            "task_description_suffix": UNIFORM_TASK_DESCRIPTION_SUFFIX,
            "terrain_config": {
                "particles": {"friction": 0.04, "count": 200, "radius": 0.06, "density": 1500.0, "seed": 42},
                "min_particles_in_hopper": 30,
                "pit_drift_force": 1.0,
                "max_time_seconds": 20,
                "max_structure_mass": 120,
                "scoop_capacity": 8,
            },
            "physics_config": {
                "gravity": (0, -20.0),
                "linear_damping": 0.08,
                "angular_damping": 0.08,
            },
        },
        {
            "stage_id": "Stage-4",
            "title": "Cataclysmic excavation nightmare",
            "mutation_description": "Gravity at 2.2x normal (22 m/s²) — 10% beyond Stage-3's 2.0x — makes every kilogram feel heavier, straining motors and testing structural integrity. Damping at 5x normal (0.10) — 25% beyond Stage-3's 4x — smothers all motion in viscous resistance, demanding higher motor torque just to achieve normal speeds. Particle friction of 0.02 is half of Stage-3's 0.04, turning grains into near-frictionless spheres that slide off the scoop at the slightest tilt or acceleration. Pit drift of 1.2 — 20% stronger than Stage-3's 1.0 — accelerates particle evacuation, shortening the viable excavation window. Scoop capacity limited to 6 particles per trip (vs Stage-3's 8) demands at least 4 complete trips to reach 22 particles, all within 17 seconds (3 seconds less than Stage-3's 20 s). Mass budget of 100 kg — 17% tighter than Stage-3's 120 kg — requires a leaner design. Every parameter is strictly worse than Stage-3: stronger gravity, heavier damping, slipperier particles, stronger drift, smaller capacity, tighter mass, and less time. The conflicting extremes create a brutal optimization problem: gravity demands power but mass is forbidden; drift demands speed but damping prevents it; small capacity needs many trips but time is short; slippery particles need precise control but viscous damping makes precision difficult.",
            "task_description_suffix": UNIFORM_TASK_DESCRIPTION_SUFFIX,
            "terrain_config": {
                "particles": {"friction": 0.02, "count": 200, "radius": 0.06, "density": 1500.0, "seed": 42},
                "min_particles_in_hopper": 22,
                "pit_drift_force": 1.2,
                "max_time_seconds": 17,
                "max_structure_mass": 100,
                "scoop_capacity": 6,
            },
            "physics_config": {
                "gravity": (0, -22.0),
                "linear_damping": 0.10,
                "angular_damping": 0.10,
            },
        },
    ]
