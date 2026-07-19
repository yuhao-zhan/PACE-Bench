from __future__ import annotations

from typing import Any, Dict, List

import math

import re

UNIFORM_SUFFIX = """

Sensors indicate that this region exhibits non-standard physical properties.
While the following variables **MIGHT** have changed from the initial environment, **NOT ALL** of them will necessarily be mutated in any given task. You must use active interaction and environmental feedback to deduce which specific conditions apply:
 - **Deck surface traction**: The vessel deck's friction coefficient may differ, affecting cargo sliding and containment design.
 - **Structure mass budget**: Total allowed structure mass may differ, requiring more efficient designs.
 - **Joint load tolerance**: Structural connections may have different force/torque thresholds before failing.
 - **Cargo loss-plane height**: The height threshold for cargo failure detection may differ.
 - **Submerged obstacle layout**: The number, size, and placement of submerged rocks may differ.
 - **Integration zone (build zone)**: The allowable build region for attaching structures may differ.
 - **Environmental roll-restoring couple**: Passive torque from the environment that restores roll may differ.
 - **Hull vertical placement relative to obstacles**: The boat's vertical position relative to hazards may differ.
 - **Gravitational acceleration**: Global gravity may differ from the baseline.
 - **Hull and beam motion damping**: Linear and angular damping for hull and beams may differ.
 - **Water current effects**: Lateral water current strength may differ.
 - **Lateral wind forcing**: Wind amplitude and frequency may differ.
 - **Periodic lateral impulse kicks**: Impulse magnitude and interval may differ.
 - **Wave-driven vertical forcing**: Primary wave amplitude and frequency may differ.
 - **Secondary wave modulation**: Secondary wave amplitude and frequency may differ.
 - **Vertical gust cadence**: Gust amplitude and interval may differ.
 - **Large transient wave impulses**: Rogue wave amplitude, interval, and double-step may differ.
 - **Hull roll impulses**: Hull roll impulse amplitude and interval may differ.
 - **Cargo restitution**: Granular cargo bounciness may differ.
 - **Cargo friction and damping**: Granular cargo friction and damping may differ.

**Discovery via feedback**: Your objective is to identify the underlying physical rules of this specific environment through trial and reasoning. Initial standard solutions may fail; analyze failure modes from simulation feedback and adapt your design.
"""

from pace_bench.tasks.categories.Category4_Granular_FluidInteraction.F_05.environment import WELD_TORQUE_FORCE_RATIO

def _fmt_build_zone_axis(y: float) -> str:
    t = round(y * 100) / 100
    if math.isclose(t, round(t, 1), abs_tol=1e-9):
        return f"{round(t, 1):.1f}"
    s = f"{t:.2f}".rstrip("0").rstrip(".")
    return s

_ROCK_FIXTURES_SUFFIX = " Each rock uses environment-defined contact parameters."

def _f05_joint_limit_float(terrain_config: Dict[str, Any]) -> float:
    inf = float("inf")
    v = terrain_config.get("joint_max_force", inf)
    if v is None:
        return inf
    try:
        return float(v)
    except (TypeError, ValueError):
        return inf

_ROCK_COUNT_WORDS = (
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",

)

def _rock_count_phrase(n: int) -> str:
    if 0 <= n < len(_ROCK_COUNT_WORDS):
        return f"{_ROCK_COUNT_WORDS[n]} rocks"
    return f"{n} rocks"

def _format_rocks_summary(terrain_config: Dict[str, Any]) -> str:
    rocks = terrain_config.get("rocks")
    if not rocks:
        return (
        )
    parts = []
    for r in rocks:
        rx = float(r.get("x", 15.0))
        ry = float(r.get("y", 1.0))
        rr = float(r.get("radius", r.get("r", 0.2)))
        parts.append(f"({rx:.2f}, {ry:.2f}, r={rr:.2f})")
    return f"{_rock_count_phrase(len(rocks))}: " + "; ".join(parts)

def update_task_description_for_visible_changes(
    base_description: str,
    target_terrain_config: Dict[str, Any],
    base_terrain_config: Dict[str, Any],
    target_physics_config: Dict[str, Any] | None = None,
    base_physics_config: Dict[str, Any] | None = None,
    *,
    stage: Dict[str, Any] | None = None,

) -> str:
    description = base_description
    if target_physics_config is None:
        target_physics_config = dict((stage or {}).get("physics_config") or {})
    else:
        target_physics_config = dict(target_physics_config)
    base_physics_config = dict(base_physics_config or {})
    target_x_min = target_terrain_config.get("build_zone_x_min", 12.0)
    target_x_max = target_terrain_config.get("build_zone_x_max", 18.0)
    target_y_min = target_terrain_config.get("build_zone_y_min", 2.0)
    target_y_max = target_terrain_config.get("build_zone_y_max", 4.5)
    base_x_min = base_terrain_config.get("build_zone_x_min", 12.0)
    base_x_max = base_terrain_config.get("build_zone_x_max", 18.0)
    base_y_min = base_terrain_config.get("build_zone_y_min", 2.0)
    base_y_max = base_terrain_config.get("build_zone_y_max", 4.5)
    if (
        target_x_min != base_x_min
        or target_x_max != base_x_max
        or target_y_min != base_y_min
        or target_y_max != base_y_max
    ):
        bz_pat = r"(- \*\*Build zone\*\*: Beam centers must lie in )x=\[[^\]]+\](, y=\[)[^\]]+\]"
        tx0 = f"{float(target_x_min):.1f}"
        tx1 = f"{float(target_x_max):.1f}"
        ty0 = _fmt_build_zone_axis(float(target_y_min))
        ty1 = _fmt_build_zone_axis(float(target_y_max))
        bx0 = f"{float(base_x_min):.1f}"
        bx1 = f"{float(base_x_max):.1f}"
        by0 = _fmt_build_zone_axis(float(base_y_min))
        by1 = _fmt_build_zone_axis(float(base_y_max))
        box = f"x=[{tx0}, {tx1}], y=[{ty0}, {ty1}] (originally x=[{bx0}, {bx1}], y=[{by0}, {by1}] in the source environment)"
        replacement = f"\\g<1>{box}"
        if bz_pat and re.search(bz_pat, description):
            description = re.sub(bz_pat, replacement, description, count=1)
    default_boat_off = 0.0
    target_off = float(target_terrain_config.get("boat_y_offset", default_boat_off))
    base_off = float(base_terrain_config.get("boat_y_offset", default_boat_off))
    if target_off != base_off:
        target_y = 2.5 + target_off
        base_y = 2.5 + base_off
        def _boat_repl(_m: re.Match[str]) -> str:
            return f"{_m.group(1)}{target_y:.1f} m (originally {base_y:.1f} m in the source environment)."
        boat_pat_mut = r"(- \*\*Boat\*\*: Hull center at x\u2248 15 m, y\u2248 )([\d.]+)( m\.(?: originally [\d.]+ in the source environment\.)?)"
        boat_pat_plain = r"(- \*\*Boat\*\*: Hull center at x≈15 m, y≈)([\d.]+)( m\.)"
        if boat_pat_mut and re.search(boat_pat_mut, description):
            description = re.sub(boat_pat_mut, _boat_repl, description, count=1)
        elif re.search(boat_pat_plain, description):
            description = re.sub(boat_pat_plain, _boat_repl, description, count=1)
    default_df = 0.5
    target_df = float(target_terrain_config.get("deck_friction", default_df))
    base_df = float(base_terrain_config.get("deck_friction", default_df))
    if target_df != base_df:
        df_pat = r"(- \*\*Hull & beam deck friction\*\*: .*? the baseline value is \*\*)([\d.]+)(\*\* \(variants may override\))"
        if df_pat and re.search(df_pat, description):
            def _df_repl(_m: re.Match[str]) -> str:
                return f"{_m.group(1)}{target_df} (originally {base_df} in the source environment){_m.group(3)}"
            description = re.sub(df_pat, _df_repl, description, count=1)
    default_cr = 0.12
    target_cr = float(target_terrain_config.get("cargo_restitution", default_cr))
    base_cr = float(base_terrain_config.get("cargo_restitution", default_cr))
    if target_cr != base_cr:
        cr_pat = r"(, restitution \*\*)([\d.]+)(\*\* \(variants may override contact parameters\))"
        if cr_pat and re.search(cr_pat, description):
            def _cr_repl(_m: re.Match[str]) -> str:
                return f"{_m.group(1)}{target_cr} (originally {base_cr} in the source environment){_m.group(3)}"
            description = re.sub(cr_pat, _cr_repl, description, count=1)
    target_rocks = _format_rocks_summary(target_terrain_config)
    base_rocks = _format_rocks_summary(base_terrain_config)
    if target_rocks != base_rocks:
        obs_pat_full = r"(- \*\*Submerged obstacles\*\*: )([^\n]+)"
        if obs_pat_full and re.search(obs_pat_full, description):
            description = re.sub(
                obs_pat_full,
                f"\\g<1>{target_rocks} (originally {base_rocks} in the source environment).",
                description,
                count=1,
            )
        else:
            obs_pat_legacy = r"(- \*\*Submerged obstacles\*\*: )([^\n]+)"
            if re.search(obs_pat_legacy, description):
                description = re.sub(
                    obs_pat_legacy,
                    f"\\g<1>{target_rocks} (originally {base_rocks} in the source environment).{_ROCK_FIXTURES_SUFFIX}",
                    description,
                    count=1,
                )
    return description

def update_success_criteria_for_visible_changes(
    base_success_criteria: str,
    target_terrain_config: Dict[str, Any],
    base_terrain_config: Dict[str, Any],
    *,
    stage: Dict[str, Any] | None = None,

) -> str:
    criteria = base_success_criteria
    inf = float("inf")
    target_joint = _f05_joint_limit_float(target_terrain_config)
    base_joint = _f05_joint_limit_float(base_terrain_config)
    _tr = WELD_TORQUE_FORCE_RATIO
    joint_limits_generic = r"Structure remains intact \(all welds survive the episode\)\."
    pattern_generic = (
        r"(3\. \*\*Tertiary\*\*: )" + joint_limits_generic
    )
    pattern_any_terse = r"(3\. \*\*Tertiary\*\*: )Structure remains intact \(all welds survive the episode\)\."
    if not math.isinf(target_joint):
        target_val = float(target_joint)
        torque_limit = target_val * WELD_TORQUE_FORCE_RATIO
        if math.isinf(base_joint):
            orig_f = "∞ in the source environment"
            orig_t = "∞ in the source environment"
        else:
            base_val = float(base_joint)
            base_torque = base_val * WELD_TORQUE_FORCE_RATIO
            orig_f = f"{base_val:.0f} N in the source environment"
            orig_t = f"{base_torque:.0f} N*m in the source environment"
        def _joint_repl(m: re.Match[str]) -> str:
            return m.group(1) + f"Joint weld force <= {target_val:.0f} N (originally {orig_f}) and torque <= {torque_limit:.0f} N*m (originally {orig_t})."
        if pattern_generic and re.search(pattern_generic, criteria):
            criteria = re.sub(pattern_generic, _joint_repl, criteria, count=1)
        elif pattern_any_terse and re.search(pattern_any_terse, criteria):
            criteria = re.sub(pattern_any_terse, _joint_repl, criteria, count=1)
    elif re.search(pattern_generic, criteria):
        criteria = re.sub(pattern_generic, r"3. **Tertiary**: Structure remains intact (all welds survive the episode).", criteria, count=1)
    default_mass = 60.0
    target_mass = float(target_terrain_config.get("max_structure_mass", default_mass))
    base_mass = float(base_terrain_config.get("max_structure_mass", default_mass))
    if target_mass != base_mass:
        mass_pat_plain = r"(- \*\*Mass Budget\*\*: Total structure mass <= )([\d.]+)( kg\.)"
        mass_pat_mut = r"(- \*\*Mass Budget\*\*: Total structure mass <= )([\d.]+)( kg\.)( \(originally [\d.]+ kg in the source environment\))?"
        mass_repl = f"\\g<1>{target_mass:.0f} kg (originally {base_mass:.0f} kg in the source environment)."
        if mass_pat_mut and re.search(mass_pat_mut, criteria):
            criteria = re.sub(mass_pat_mut, mass_repl, criteria, count=1)
        elif re.search(mass_pat_plain, criteria):
            criteria = re.sub(mass_pat_plain, mass_repl, criteria, count=1)
    default_cap = 18.0
    target_cap = float(target_terrain_config.get("max_capsize_angle_deg", default_cap))
    base_cap = float(base_terrain_config.get("max_capsize_angle_deg", default_cap))
    if target_cap != base_cap:
        marker = "at or below "
        idx_marker = criteria.find(marker)
        if idx_marker != -1:
            angle_start = idx_marker + len(marker)
            space_idx = criteria.find(" ", angle_start)
            if space_idx != -1:
                old_angle = criteria[angle_start:space_idx]
                dec_prec = len(old_angle.split(".")[1]) if "." in old_angle else 0
                new_angle = f"{target_cap:.{dec_prec}f}"
                tmp = criteria[:angle_start] + new_angle + criteria[space_idx:]
                orig_idx = tmp.find("(originally", angle_start)
                if orig_idx != -1:
                    orig_end = tmp.find(").", orig_idx)
                    if orig_end != -1:
                        tmp = tmp[:orig_idx] + f"(originally {base_cap:.1f} degrees in the source environment)."
                else:
                    degrees_idx = tmp.find("degrees", angle_start)
                    if degrees_idx != -1:
                        dot_idx = tmp.find(".", degrees_idx)
                        if dot_idx != -1:
                            tmp = tmp[:dot_idx] + f" (originally {base_cap:.1f} degrees in the source environment)."
                criteria = tmp
    default_cwy = 1.98
    default_grace = 120
    target_cwy = float(target_terrain_config.get("cargo_water_y", default_cwy))
    base_cwy = float(base_terrain_config.get("cargo_water_y", default_cwy))
    target_grace = int(target_terrain_config.get("cargo_loss_grace_steps", default_grace))
    base_grace = int(base_terrain_config.get("cargo_loss_grace_steps", default_grace))
    if target_cwy != base_cwy or target_grace != base_grace:
        retention_pat = r"1\. \*\*Cargo Retention\*\*: A particle fails if its center \*\*ever\*\* falls below y = ([\d.]+) m after the first (\d+) physics steps \(brief spawn/settling is ignored\)\."
        def _retention_repl(m: re.Match[str]) -> str:
            grace_val = int(m.group(2))
            grace_part = (
                f"{target_grace} (originally {base_grace} in the source environment)"
                if target_grace != grace_val
                else str(grace_val)
            )
            y_part = (
                f"{target_cwy:.2f} m (originally {base_cwy:.2f} m in the source environment)"
                if not math.isclose(target_cwy, base_cwy, rel_tol=0.0, abs_tol=1e-9)
                else f"{target_cwy:.2f} m"
            )
            return (
                f"1. **Cargo Retention**: A particle fails if its center **ever** falls below {y_part} "
                f"after the first {grace_part} physics steps (brief spawn/settling is ignored)."
            )
        if retention_pat and re.search(retention_pat, criteria, re.IGNORECASE | re.DOTALL):
            criteria = re.sub(retention_pat, _retention_repl, criteria, count=1)
    return criteria

def _merge_f05_terrain(prev: Dict[str, Any], delta: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(prev)
    for k, v in delta.items():
        if k == "cargo" and isinstance(v, dict):
            base_c = out.get("cargo")
            out["cargo"] = {**(base_c if isinstance(base_c, dict) else {}), **v}
        else:
            out[k] = v
    return out

def _merge_f05_physics(prev: Dict[str, Any], delta: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(prev)
    out.update(delta)
    return out

def get_f05_curriculum_stages() -> List[Dict[str, Any]]:
    _reef_barrier_rocks = [
        {"x": 13.15, "y": 2.02, "r": 0.44},
        {"x": 15.0, "y": 1.97, "r": 0.5},
        {"x": 16.85, "y": 2.02, "r": 0.44},
    ]
    _stage3_reef_field = [
        {"x": 13.05, "y": 2.06, "r": 0.46},
        {"x": 15.0, "y": 2.02, "r": 0.52},
        {"x": 16.95, "y": 2.06, "r": 0.46},
        {"x": 15.0, "y": 1.48, "r": 0.33},
    ]
    _raw_stages: List[Dict[str, Any]] = [
        {
            "stage_id": "Stage-1",
            "title": "Metacentric Deficit",
            "mutation_description": "Single-axis challenge: violent angular impulse kicks strike the hull at high frequency — each delivering enough rotational kinetic energy to throw the bare hull past its capsize threshold within fractions of a second. The kicks arrive faster than any passive self-righting can settle the hull between strikes. Without predictive counter-torque timing synchronized to the impulse cadence, massively distributed roll inertia, and active cargo containment against launch events, the hull will invert within the first few kick cycles. Standard roll-trim PID gains are wholly inadequate — this demands pre-emptive torque application and a full-cage architecture.",
            "task_description_suffix": None,
            "terrain_config": {
                "hull_roll_impulse_amplitude": 780.0,
                "hull_roll_impulse_interval_steps": 22,
            },
            "physics_config": {},
        },
        {
            "stage_id": "Stage-2",
            "title": "Raised Loss Plane",
            "mutation_description": "Single-axis challenge: the cargo-loss height threshold is raised to an extreme level above the bare hull deck, requiring a completely elevated containment architecture. Cargo on the bare deck will fail retention unconditionally — the design must supply a raised platform with its own containment walls.",
            "task_description_suffix": None,
            "terrain_config": {
                "cargo_water_y": 2.92,
                "restoring_coeff": 1600.0,
            },
            "physics_config": {},
        },
        {
            "stage_id": "Stage-3",
            "title": "Shoal Lock-In",
            "mutation_description": "Multi-axis coupling: altered reef layout, hull vertical placement, build-zone floor height, joint limits, lateral drift bias, impulsive hull roll kicks, and cargo contact parameters. Containment must supply roll inertia, avoid obstacle envelopes, and seal the hold within stated beam-width limits.",
            "task_description_suffix": None,
            "terrain_config": {
                "boat_y_offset": -0.10,
                "rocks": list(_stage3_reef_field),
                "build_zone_y_min": 2.58,
                "cargo_water_y": 2.28,
                "joint_max_force": 1750.0,
                "current_strength": 0.64,
                "cargo_restitution": 0.36,
                "cargo": {"friction": 0.62, "linear_damping": 0.24},
                "hull_roll_impulse_amplitude": 20.5,
                "hull_roll_impulse_interval_steps": 73,
                "restoring_coeff": 240.0,
            },
            "physics_config": {},
        },
        {
            "stage_id": "Stage-4",
            "title": "Perfect Storm Assembly Budget",
            "mutation_description": "Hardest multi-axis coupling: critically weak passive righting, extreme gravity, violent multi-frequency roll kicks, gale-force lateral forcing, ultra-bouncy near-frictionless cargo, massively amplified wave-fields, near-zero structural damping, and the tightest mass and joint budgets across any stage. Active torque must supply nearly all anti-capsize work; the structure must use extreme-cantilever roll inertia with multi-joint load distribution. Cargo containment must defeat bouncing, sliding, and launch events simultaneously within a budget under half the baseline allowance.",
            "task_description_suffix": None,
            "terrain_config": {
                "boat_y_offset": -0.10,
                "rocks": list(_reef_barrier_rocks),
                "build_zone_y_min": 2.58,
                "current_strength": 2.0,
                "deck_friction": 0.0,
                "max_structure_mass": 18.0,
                "restoring_coeff": 30.0,
                "wind_amplitude": 40.0,
                "wind_frequency": 0.32,
                "lateral_impulse_amplitude": 340.0,
                "lateral_impulse_interval_steps": 35,
                "joint_max_force": 99999.0,
                "hull_roll_impulse_amplitude": 420.0,
                "hull_roll_impulse_interval_steps": 14,
                "rogue_amplitude": 65.0,
                "rogue_interval_steps": 90,
                "cargo_restitution": 0.88,
                "cargo": {"friction": 0.018, "linear_damping": 0.003},
                "wave_amplitude": 55.0,
                "wave_frequency": 0.85,
                "wave2_amplitude": 35.0,
                "wave2_frequency": 0.65,
                "gust_amplitude": 35.0,
                "gust_interval_steps": 16,
            },
            "physics_config": {
                "gravity": (0, -42.0),
                "linear_damping": 0.002,
                "angular_damping": 0.0008,
            },
        },
    ]
    merged_tc: Dict[str, Any] = {}
    merged_pc: Dict[str, Any] = {}
    out_stages: List[Dict[str, Any]] = []
    for s in _raw_stages:
        s = dict(s)
        merged_tc = _merge_f05_terrain(merged_tc, s.get("terrain_config") or {})
        merged_pc = _merge_f05_physics(merged_pc, s.get("physics_config") or {})
        s["terrain_config"] = dict(merged_tc)
        s["physics_config"] = dict(merged_pc)
        s["task_description_suffix"] = UNIFORM_SUFFIX
        out_stages.append(s)
    return out_stages
