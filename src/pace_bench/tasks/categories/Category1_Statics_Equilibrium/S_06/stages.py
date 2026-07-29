from __future__ import annotations

from pace_bench.tasks.stage_prompt import uniform_suffix_for_task

from typing import Any, Dict, List

import re

def update_task_description_for_visible_changes(base_description: str, target_terrain_config: Dict[str, Any], base_terrain_config: Dict[str, Any]) -> str:
    description = base_description
    base_terrain_config = base_terrain_config or {}
    default_spawn = [-10.0, 0.0]
    default_ceiling = 100.0
    default_mass = 20000.0
    default_stability_time = 10.0
    default_floor_length = 20.0
    target_floor_length = target_terrain_config.get("floor_length", default_floor_length)
    base_floor_length = base_terrain_config.get("floor_length", default_floor_length)
    if target_floor_length != base_floor_length:
        target_edge = -10.0 + target_floor_length / 2.0
        base_edge = -10.0 + base_floor_length / 2.0
        pattern = r"(- \*\*Table\*\*: A horizontal surface extending from x=-20 to x=)(\d+\.?\d*)(\. The table edge is at x=)(\d+\.?\d*)(\.)"
        if re.search(pattern, description):
            description = re.sub(
                pattern,
                f"\\g<1>{target_edge:.1f}\\g<3>{target_edge:.1f} (was x={base_edge:.1f}).",
                description,
            )
    target_overhang = target_terrain_config.get("target_overhang", 0.1)
    base_overhang = base_terrain_config.get("target_overhang", 0.1)
    if target_overhang != base_overhang:
        pattern = r"(\s*-\s*\*\*Goal\*\*: Reach x >= )(\d+\.?\d*)m( beyond the edge\.)"
        if re.search(pattern, description):
            description = re.sub(pattern, f"\\g<1>{target_overhang:.2f}m (was {base_overhang:.2f}m)\\g<3>", description)
    target_spawn = target_terrain_config.get("spawn_zone", default_spawn)
    base_spawn = base_terrain_config.get("spawn_zone", default_spawn)
    if target_spawn != base_spawn:
        pattern = r"(\*\*Spawn Rule\*\*: Blocks must be initialized within the permitted build access zone: x in )(\[.*?\])(\.)"
        if re.search(pattern, description):
            base_str = f"[{base_spawn[0]:.2f}, {base_spawn[1]:.2f}]"
            description = re.sub(pattern, f"\\g<1>[{target_spawn[0]:.2f}, {target_spawn[1]:.2f}] (was {base_str})\\g<3>", description)
    target_ceiling = target_terrain_config.get("ceiling_y", default_ceiling)
    base_ceiling = base_terrain_config.get("ceiling_y", default_ceiling)
    if target_ceiling != base_ceiling:
        pattern = r"(\s*-\s*\*\*Ceiling Boundary\*\*: Structure cannot exceed y = )(\d+\.?\d*)m( in height\.)"
        if re.search(pattern, description):
            description = re.sub(pattern, f"\\g<1>{target_ceiling:.1f}m in height (was {base_ceiling:.1f}m).", description)
    target_mass = target_terrain_config.get("max_total_mass", default_mass)
    base_mass = base_terrain_config.get("max_total_mass", default_mass)
    if target_mass != base_mass:
        pattern = r"(\s*-\s*\*\*Mass Budget\*\*: Total structure mass must be less than or equal to )(\d+\.?\d*)( units\.)"
        if re.search(pattern, description):
            description = re.sub(pattern, f"\\g<1>{target_mass:.1f} units (was {base_mass:.1f} units).", description)
    return description

def update_success_criteria_for_visible_changes(base_success_criteria: str, target_terrain_config: Dict[str, Any], base_terrain_config: Dict[str, Any]) -> str:
    criteria = base_success_criteria
    base_terrain_config = base_terrain_config or {}
    target_overhang = target_terrain_config.get("target_overhang", 0.1)
    base_overhang = base_terrain_config.get("target_overhang", 0.1)
    if target_overhang != base_overhang:
        pattern = r"(\(Tip reaches x >= )(\d+\.?\d*)m(\)\.)"
        if re.search(pattern, criteria):
            criteria = re.sub(pattern, f"\\g<1>{target_overhang:.2f}m (was {base_overhang:.2f}m)\\g<3>", criteria)
    target_mass = target_terrain_config.get("max_total_mass", 20000.0)
    base_mass = base_terrain_config.get("max_total_mass", 20000.0)
    if target_mass != base_mass:
        pattern = r"(\s*-\s*\*\*Mass Budget\*\*: Total mass must be <= )(\d+\.?\d*)( units\.)"
        if re.search(pattern, criteria):
            criteria = re.sub(pattern, f"\\g<1>{target_mass:.1f} units (was {base_mass:.1f} units).", criteria)
    target_stability_time = target_terrain_config.get("stability_time", 10.0)
    base_stability_time = base_terrain_config.get("stability_time", 10.0)
    if target_stability_time != base_stability_time:
        pattern = r"(\s*-\s*\*\*Stability Time\*\*: Structure must remain motionless for at least )(\d+\.?\d*)( seconds\.)"
        if re.search(pattern, criteria):
            criteria = re.sub(pattern, f"\\g<1>{target_stability_time:.1f} (was {base_stability_time:.1f})\\g<3>", criteria)
    return criteria

def get_s06_curriculum_stages() -> List[Dict[str, Any]]:
    UNIFORM_SUFFIX = uniform_suffix_for_task("S_06")
    return [
        {
            "stage_id": "Stage-1",
            "title": "The Slippery Gale",
            "mutation_description": "Friction-Starved Wind Tunnel: Table friction crippled to 0.015 (53× below baseline 0.8) combined with a persistent 2.5N lateral wind force applied to every block. Block-to-block friction weakened to 0.25. Mass budget tightened to 35.0. The table friction provides at most 0.15 N/kg of lateral resistance — a 2.5N wind force demands at least 16.7 kg per block to resist sliding through direct table contact. For a 2-block stack under 5.0N total combined wind, the total mass must exceed 33.34 kg to avoid sliding off the table. Every extra block adds another 2.5N to the cumulative wind load; designs with 3+ blocks are categorically non-viable as combined wind overwhelms the friction budget. The initial standard solution using lightweight blocks (0.2 kg each) slides instantly as 2.5N wind >> 0.03N table friction. Only a precisely engineered 2-block counterbalanced stack consuming nearly the entire mass budget with exact density ratios can survive — and even then with only a ~2% friction safety margin.",
            "task_description_suffix": uniform_suffix_for_task("S_06"),
            "terrain_config": {
                "target_overhang": 0.5,
                "floor_length": 20.0,
                "spawn_zone": [-10.0, 0.0],
                "max_total_mass": 35.0,
                "table_friction": 0.015,
                "block_friction": 0.25,
                "oscillate": False,
                "osc_amplitude": 0.0,
                "osc_frequency": 0.0,
            },
            "physics_config": {
                "gravity": (0, -10.0),
                "wind_force": 2.5,
            },
        },
        {
            "stage_id": "Stage-2",
            "title": "The Wind-Loaded Mass Cascade",
            "mutation_description": "Layered dry-friction loading under a per-body force: The required terminal x-coordinate is 0.61 while block centers may be initialized only through x=0.12, placing an isolated reaching slab's center of mass beyond the x=0 support edge. A continuous 1.2N horizontal force acts independently on every block, so adding tiers also accumulates sliding and overturning load. Table and inter-block friction are 0.02 and 0.35 respectively, and total mass is capped at 30.0. The initial lightweight two-block stack is swept off the table, while the old Stage-2 pair exceeds the new mass limit. The stage reference uses a multi-tier cantilever with a heavy inboard foundation and progressively lighter outboard layers: every upper sub-stack center of mass remains inside the supporting block below, the whole-structure center of mass stays left of x=0, and the mass cascade supplies traction without violating the cap. This replaces uniform-density retuning with coupled topology, nested load-path, mass-gradient, and boundary-placement reasoning.",
            "task_description_suffix": uniform_suffix_for_task("S_06"),
            "terrain_config": {
                "target_overhang": 0.61,
                "floor_length": 20.0,
                "spawn_zone": [-10.0, 0.12],
                "max_total_mass": 30.0,
                "table_friction": 0.02,
                "block_friction": 0.35,
                "oscillate": False,
                "osc_amplitude": 0.0,
                "osc_frequency": 0.0,
            },
            "physics_config": {
                "gravity": (0, -10.0),
                "wind_force": 1.2,
            },
        },
        {
            "stage_id": "Stage-3",
            "title": "The Harmonic Lift Cantilever",
            "mutation_description": "A long-reach harmonic cantilever must terminate at x=1.38 even though block centers may be initialized only through x=0.89. The total mass limit is 18.0, table friction is 0.22, and inter-block friction is 0.8. A persistent external force vector couples the reach problem to contact retention: every added layer incurs another fixed force contribution, while insufficiently massive outboard layers lose normal load and cannot remain seated on their support. A two-block ballast pair cannot generate the required lever arm within the budget, and low-layer graded stacks lack enough theoretical reach once each member carries the contact-retention mass floor. The reference instead uses five independently weighted layers whose nested centers of mass remain supported while the inboard mass gradient supplies the table reaction. This replaces the previous equal-density pair with coupled harmonic geometry, per-interface mass allocation, contact-retention thresholds, and whole-structure counterbalance.",
            "task_description_suffix": uniform_suffix_for_task("S_06"),
            "terrain_config": {
                "target_overhang": 1.38,
                "floor_length": 20.0,
                "spawn_zone": [-10.0, 0.89],
                "max_total_mass": 18.0,
                "table_friction": 0.22,
                "block_friction": 0.8,
                "oscillate": False,
                "osc_amplitude": 0.0,
                "osc_frequency": 0.0,
            },
            "physics_config": {
                "gravity": (0, -10.0),
                "wind_force": (-3.0, 9.5),
            },
        },
        {
            "stage_id": "Stage-4",
            "title": "The Gravitational Siege",
            "mutation_description": "Amplified gravity (12.0 m/s², 20% above baseline) combined with critically depleted dual-friction surfaces and extreme oscillatory dynamics. Both table and block-to-block friction are identically crippled to 0.10 (8× and 6× below baselines of 0.8 and 0.6 respectively), creating a uniformly fragile system with only 1.20 m/s² of lateral resistance per kg. Aggressive continuous oscillation at 3.0 rad/s with 0.12m amplitude generates massive peak lateral accelerations of 1.08 m/s², consuming 90% of the friction budget per kg before wind enters the equation. A persistent 1.8N lateral wind per block (3× Stage-3 wind) devours the remaining friction. The amplified gravity makes the net friction headroom per kg exactly 0.12 m/s² (1.20 - 1.08), matching the razor-thin 0.63% safety margin of the original stage — but now at much higher absolute force levels. Mass budget restricted to 32.0, requiring each 2-block design to consume the entire allowance. The elevated gravity makes COM management far more punishing: any COM excursion past the table edge triggers catastrophic tipping 50% faster than at baseline gravity. Spawn zone compressed to [-10.0, 0.05] with target overhang 0.55m, forcing the top block to the absolute spawn boundary. The initial 2-block lightweight solution (total ~0.4kg) is annihilated — wind forces (3.6N) exceed table friction (0.48N) by 7.5× and the entire structure slides off within 2 seconds. Three or more blocks multiply wind past the friction singularity and are categorically non-viable. Only a precisely engineered 2-block design consuming the entire mass budget at density 80 with exact positional alignment can survive — and even then with margin measured in fractions of a percent.",
            "task_description_suffix": uniform_suffix_for_task("S_06"),
            "terrain_config": {
                "target_overhang": 0.55,
                "floor_length": 20.0,
                "spawn_zone": [-10.0, 0.05],
                "max_total_mass": 32.0,
                "table_friction": 0.10,
                "block_friction": 0.10,
                "oscillate": True,
                "osc_amplitude": 0.12,
                "osc_frequency": 3.0,
            },
            "physics_config": {
                "gravity": (0, -12.0),
                "wind_force": 1.8,
            },
        },
    ]
