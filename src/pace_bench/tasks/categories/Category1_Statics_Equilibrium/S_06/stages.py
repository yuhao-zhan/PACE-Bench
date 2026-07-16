from __future__ import annotations

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
            description = re.sub(pattern, f"\\g<1>{target_overhang:.2f}m (was {base_overhang:.2f}m).\\g<3>", description)
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
    default_table_friction = 0.8
    default_block_friction = 0.6
    target_table_friction = target_terrain_config.get("table_friction", default_table_friction)
    base_table_friction = base_terrain_config.get("table_friction", default_table_friction)
    if target_table_friction != base_table_friction:
        pattern = r"(\s*-\s*\*\*Table Friction\*\*: mu_table = )(\d+\.?\d*)(.*)"
        if re.search(pattern, description):
            description = re.sub(pattern, f"\\g<1>{target_table_friction:.4g} (was {base_table_friction:.4g})\\g<3>", description)
    target_block_friction = target_terrain_config.get("block_friction", default_block_friction)
    base_block_friction = base_terrain_config.get("block_friction", default_block_friction)
    if target_block_friction != base_block_friction:
        pattern = r"(\s*-\s*\*\*Block Friction\*\*: mu_block = )(\d+\.?\d*)(.*)"
        if re.search(pattern, description):
            description = re.sub(pattern, f"\\g<1>{target_block_friction:.4g} (was {base_block_friction:.4g})\\g<3>", description)
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
    UNIFORM_SUFFIX = """
Environmental Anomalies Detected
Sensors indicate that this region exhibits non-standard physical properties.
While the following variables MIGHT have changed from the initial environment, NOT ALL of them will necessarily be mutated in any given task. You must use active interaction and environmental feedback to deduce which specific conditions apply:
 - Horizontal reach requirements: The required extent beyond the table edge may differ from the initial specification.
 - Block placement boundaries: The permitted x-interval for placing blocks may be restricted differently.
 - Gravitational Intensity: The magnitude of the downward pull may have changed, affecting structural stress and balance.
 - Table Friction Coefficient: The friction coefficient between blocks and the table surface may have changed, affecting how effectively the base of the stack resists sliding.
 - Block-to-Block Friction: The friction between stacked blocks may differ from the table friction, affecting internal stability.
 - Lateral Forces: Persistent horizontal force vectors may act on the structure; their presence or magnitude may differ from the initial environment.
 - Mass Budget: Total structure mass may be more severely constrained, requiring efficient design.
 - Oscillatory Surface Dynamics: The table may exhibit kinematic motion (oscillation) rather than being static. The oscillation amplitude and frequency may differ from the initial environment, requiring dynamic stability management.

Discovery via feedback: Your objective is to identify the underlying physical rules of this specific environment through trial and reasoning. Initial standard solutions may fail; analyze the failure mode (e.g., where a joint breaks or how a body moves) to infer the hidden constraints and adapt your design.
"""
    return [
        {
            "stage_id": "Stage-1",
            "title": "The Slippery Gale",
            "mutation_description": "Friction-Starved Wind Tunnel: Table friction crippled to 0.015 (53× below baseline 0.8) combined with a persistent 2.5N lateral wind force applied to every block. Block-to-block friction weakened to 0.25. Mass budget tightened to 35.0. The table friction provides at most 0.15 N/kg of lateral resistance — a 2.5N wind force demands at least 16.7 kg per block to resist sliding through direct table contact. For a 2-block stack under 5.0N total combined wind, the total mass must exceed 33.34 kg to avoid sliding off the table. Every extra block adds another 2.5N to the cumulative wind load; designs with 3+ blocks are categorically non-viable as combined wind overwhelms the friction budget. The initial standard solution using lightweight blocks (0.2 kg each) slides instantly as 2.5N wind >> 0.03N table friction. Only a precisely engineered 2-block counterbalanced stack consuming nearly the entire mass budget with exact density ratios can survive — and even then with only a ~2% friction safety margin.",
            "task_description_suffix": UNIFORM_SUFFIX,
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
            "title": "The Friction Abyss",
            "mutation_description": "Near-Absolute Friction Collapse + Persistent Wind: Table friction is virtually nonexistent at 0.001 (800× lower than baseline 0.8), AND a continuous lateral wind of 0.33N pushes on every block. The obliterated friction means the table provides at most 0.67N of lateral resistance (67.0 mass budget × 10 m/s² × 0.001). With wind loading proportional to block count, using more than 2 blocks multiplies wind beyond friction capacity. The target overhang of 0.57m demands extreme positional precision — the top block must be centered within 5cm of the spawn boundary, leaving millimeter-level placement tolerance. The spawn zone caps block centers at x=0.12, forcing the top block to sit at the absolute limit of what 1.0m-wide blocks can achieve. Block-to-block friction remains high (0.8) so internal stacking is stable, but the table provides effectively zero grip. The standard solution using lightweight blocks (0.2 kg each at density 1.0) slides catastrophically as wind force (0.66N total) exceeds friction (0.0032N) by over 200×. Only a precisely engineered 2-block design consuming the entire mass budget at density ~167.5 with sub-centimeter positional accuracy can survive. The friction-wind safety margin is approximately 1.5% — any deviation in density, mass distribution, or block count triggers immediate structural failure. Three or more blocks add wind load beyond friction capacity and are categorically non-viable.",
            "task_description_suffix": UNIFORM_SUFFIX,
            "terrain_config": {
                "target_overhang": 0.57,
                "floor_length": 20.0,
                "spawn_zone": [-10.0, 0.12],
                "max_total_mass": 67.0,
                "table_friction": 0.001,
                "block_friction": 0.8,
                "oscillate": False,
                "osc_amplitude": 0.0,
                "osc_frequency": 0.0,
            },
            "physics_config": {
                "gravity": (0, -10.0),
                "wind_force": 0.33,
            },
        },
        {
            "stage_id": "Stage-3",
            "title": "The Mass-Budget Crucible",
            "mutation_description": "Friction-hierarchy trap + oscillation + gale wind + extreme mass budget: Table friction is moderately depleted to 0.16 while block-to-block friction is set even lower at 0.14 — creating a subtle friction hierarchy where the top block is 14% weaker against sliding than the base. Continuous table oscillation at 2.7 rad/s with 0.05m amplitude generates peak inertial demands of 0.365 m/s² on every block, while a persistent lateral wind of 4.0N per block pushes relentlessly rightward. The real killer is the mass budget: slashed to just 13.0 (over 1500× below baseline 20000). This creates a non-obvious survival zone — designs with less than ~8 kg total mass slide off catastrophically within seconds (as the Box2D contact solver requires substantial friction headroom beyond pure Coulomb theory to track an oscillating surface), while designs exceeding 13.0 kg fail the budget constraint. The viable mass window is a razor-thin [~12.0, 13.0] kg. Target overhang at 0.53m with spawn zone compressed to [-10.0, 0.05] further restricts options: the top block must be placed at the absolute spawn boundary for reach, while COM must remain behind the table edge. The initial standard solution (0.4kg total) experiences wind forces (8.0N combined) exceeding table friction capacity by over 1400% and slides off instantly. Even designs at ~8-11 kg exhibit steady rightward drift and fail after several oscillation cycles as COM drifts past the edge. Only a precisely engineered 2-block design consuming nearly the entire mass budget (e.g., both blocks at density ~32, total mass ~12.8 kg, utilizing 98.5% of budget) can survive: the top block operates at 70.7% friction utilization while the bottom contact runs at 61.9%. Any design with 3+ blocks triples wind load past friction capacity and is categorically non-viable.",
            "task_description_suffix": UNIFORM_SUFFIX,
            "terrain_config": {
                "target_overhang": 0.53,
                "floor_length": 20.0,
                "spawn_zone": [-10.0, 0.05],
                "max_total_mass": 13.0,
                "table_friction": 0.16,
                "block_friction": 0.14,
                "oscillate": True,
                "osc_amplitude": 0.05,
                "osc_frequency": 2.7,
            },
            "physics_config": {
                "gravity": (0, -10.0),
                "wind_force": 4.0,
            },
        },
        {
            "stage_id": "Stage-4",
            "title": "The Gravitational Siege",
            "mutation_description": "Amplified gravity (12.0 m/s², 20% above baseline) combined with critically depleted dual-friction surfaces and extreme oscillatory dynamics. Both table and block-to-block friction are identically crippled to 0.10 (8× and 6× below baselines of 0.8 and 0.6 respectively), creating a uniformly fragile system with only 1.20 m/s² of lateral resistance per kg. Aggressive continuous oscillation at 3.0 rad/s with 0.12m amplitude generates massive peak lateral accelerations of 1.08 m/s², consuming 90% of the friction budget per kg before wind enters the equation. A persistent 1.8N lateral wind per block (3× Stage-3 wind) devours the remaining friction. The amplified gravity makes the net friction headroom per kg exactly 0.12 m/s² (1.20 - 1.08), matching the razor-thin 0.63% safety margin of the original stage — but now at much higher absolute force levels. Mass budget restricted to 32.0, requiring each 2-block design to consume the entire allowance. The elevated gravity makes COM management far more punishing: any COM excursion past the table edge triggers catastrophic tipping 50% faster than at baseline gravity. Spawn zone compressed to [-10.0, 0.05] with target overhang 0.55m, forcing the top block to the absolute spawn boundary. The initial 2-block lightweight solution (total ~0.4kg) is annihilated — wind forces (3.6N) exceed table friction (0.48N) by 7.5× and the entire structure slides off within 2 seconds. Three or more blocks multiply wind past the friction singularity and are categorically non-viable. Only a precisely engineered 2-block design consuming the entire mass budget at density 80 with exact positional alignment can survive — and even then with margin measured in fractions of a percent.",
            "task_description_suffix": UNIFORM_SUFFIX,
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
