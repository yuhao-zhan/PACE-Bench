from __future__ import annotations

import re

from typing import Any, Dict, List

from pace_bench.tasks.categories.Category5_Cybernetics_Control.C_05 import environment as _env

_BASE_TRIGGER_STAY = _env.TRIGGER_STAY_STEPS

_BASE_SPEED_CAP = _env.SPEED_CAP_INSIDE

_BASE_COOLDOWN = _env.COOLDOWN_STEPS

_BASE_BARRIER_DELAY = _env.BARRIER_DELAY_STEPS

_BASE_C_REQUIRED_MAX_Y = _env.C_REQUIRED_MAX_Y

_BASE_C_HIGH_HISTORY = _env.C_HIGH_HISTORY

_BASE_RECENT_A_FOR_B = _env.RECENT_A_FOR_B

_BASE_RECENT_B_FOR_C = _env.RECENT_B_FOR_C

_BASE_FORCE_LIMIT = _env.FORCE_LIMIT_INSIDE

_BASE_REPULSION_MAG = _env.REPULSION_MAG

_BASE_REPULSION_TANGENTIAL_MAG = _env.REPULSION_TANGENTIAL_MAG

_BASE_BARRIER_X = _env.BARRIER_X

_BASE_SPAWN_X = _env.SPAWN_X

_BASE_SPAWN_Y = _env.SPAWN_Y

_BASE_AGENT_RADIUS = _env.AGENT_RADIUS

_BASE_AGENT_MASS = _env.AGENT_MASS

_BASE_MAX_AGENT_FORCE_PER_AXIS = _env.MAX_AGENT_FORCE_PER_AXIS

_BASE_REPULSION_RANGE = _env.REPULSION_RANGE

_BASE_GROUND_FRICTION = _env.GROUND_FRICTION_DEFAULT

_BASE_RAMP_FRICTION = _env.RAMP_FRICTION_DEFAULT

_BASE_PLATFORM_FRICTION = _env.PLATFORM_FRICTION_DEFAULT

_BASE_AGENT_BODY_FRICTION = _env.AGENT_FIXTURE_FRICTION

_BARRIER_BODY_FRICTION = _env.BARRIER_FIXTURE_FRICTION

def _fmt_scalar_prompt(x: float) -> str:
    xf = float(x)
    if abs(xf - round(xf)) < 1e-9:
        return str(int(round(xf)))
    return format(xf, ".15g").rstrip("0").rstrip(".") or "0"

def _fmt_repulsion_peak(x: float) -> str:
    return f"{float(x):.1f}"

def _effective_terrain(
    target_tc: Dict[str, Any], base_tc: Dict[str, Any], key: str, default: float

) -> float:
    if target_tc and key in target_tc:
        return float(target_tc[key])
    if base_tc and key in base_tc:
        return float(base_tc[key])
    return float(default)

def _base_terrain(base_tc: Dict[str, Any], key: str, default: float) -> float:
    if base_tc and key in base_tc:
        return float(base_tc[key])
    return float(default)

def _get_physics(base_physics: Dict[str, Any], key: str, default: Any) -> Any:
    if base_physics is None:
        return default
    return base_physics.get(key, default)

def update_task_description_for_visible_changes(
    base_description: str,
    target_terrain_config: Dict[str, Any],
    base_terrain_config: Dict[str, Any],
    target_physics_config: Dict[str, Any] = None,
    base_physics_config: Dict[str, Any] = None,

) -> str:
    description = base_description
    target_terrain_config = target_terrain_config or {}
    base_terrain_config = base_terrain_config or {}
    target_physics_config = target_physics_config or {}
    base_physics_config = base_physics_config or {}
    def target_phys(key: str, default: Any) -> Any:
        return target_physics_config.get(key, default)
    def base_phys(key: str, default: Any) -> Any:
        return _get_physics(base_physics_config, key, default)
    t_trigger = int(target_phys("trigger_stay_steps", _BASE_TRIGGER_STAY))
    b_trigger = int(base_phys("trigger_stay_steps", _BASE_TRIGGER_STAY))
    if t_trigger != b_trigger:
        pattern = r"(must stay inside a zone for )(\d+)( consecutive steps)"
        if re.search(pattern, description):
            description = re.sub(
                pattern,
                f"\\g<1>{t_trigger} consecutive steps (originally {b_trigger} steps in the source environment)",
                description,
            )
    t_speed = float(target_phys("speed_cap_inside", _BASE_SPEED_CAP))
    b_speed = float(base_phys("speed_cap_inside", _BASE_SPEED_CAP))
    if t_speed != b_speed:
        pattern = r"(for progress to count is )(\d+\.?\d*)( m/s; exceeding this resets that zone's progress)"
        if re.search(pattern, description):
            description = re.sub(
                pattern,
                f"\\g<1>{t_speed} m/s (originally {b_speed} m/s in the source environment); exceeding this resets that zone's progress",
                description,
            )
    t_cool = int(target_phys("cooldown_steps", _BASE_COOLDOWN))
    b_cool = int(base_phys("cooldown_steps", _BASE_COOLDOWN))
    if t_cool != b_cool:
        pattern = r"(must wait )(\d+)( steps before the next zone will accept progress)"
        if re.search(pattern, description):
            description = re.sub(
                pattern,
                f"\\g<1>{t_cool} steps (originally {b_cool} steps in the source environment) before the next zone will accept progress",
                description,
            )
    t_barrier = int(target_phys("barrier_delay_steps", _BASE_BARRIER_DELAY))
    b_barrier = int(base_phys("barrier_delay_steps", _BASE_BARRIER_DELAY))
    if t_barrier != b_barrier:
        pattern = r"(gate opens )(\d+)( steps after zone A is triggered, not immediately)"
        if re.search(pattern, description):
            description = re.sub(
                pattern,
                f"\\g<1>{t_barrier} steps (originally {b_barrier} steps in the source environment) after zone A is triggered, not immediately",
                description,
            )
    t_ab = int(target_phys("recent_a_for_b", _BASE_RECENT_A_FOR_B))
    b_ab = int(base_phys("recent_a_for_b", _BASE_RECENT_A_FOR_B))
    if t_ab != b_ab:
        pattern = r"(was in zone A within the last )(\d+)( steps\.)"
        if re.search(pattern, description):
            description = re.sub(
                pattern,
                f"\\g<1>{t_ab} steps (originally {b_ab} steps in the source environment)\\g<3>",
                description,
            )
    t_bc = int(target_phys("recent_b_for_c", _BASE_RECENT_B_FOR_C))
    b_bc = int(base_phys("recent_b_for_c", _BASE_RECENT_B_FOR_C))
    if t_bc != b_bc:
        pattern = r"(was in zone B within the last )(\d+)( steps\.)"
        if re.search(pattern, description):
            description = re.sub(
                pattern,
                f"\\g<1>{t_bc} steps (originally {b_bc} steps in the source environment)\\g<3>",
                description,
            )
    t_cy = float(target_phys("c_required_max_y", _BASE_C_REQUIRED_MAX_Y))
    b_cy = float(base_phys("c_required_max_y", _BASE_C_REQUIRED_MAX_Y))
    t_ch = int(target_phys("c_high_history", _BASE_C_HIGH_HISTORY))
    b_ch = int(base_phys("c_high_history", _BASE_C_HIGH_HISTORY))
    if t_cy != b_cy or t_ch != b_ch:
        c_alt_pat = r"y-history window.*?approach from elevated path\)\."
        if re.search(c_alt_pat, description):
            cy_note = (
                f" (originally {b_cy:g} m in the source environment)"
                if t_cy != b_cy
                else ""
            )
            ch_note = (
                f" (originally {b_ch} steps in the source environment)"
                if t_ch != b_ch
                else ""
            )
            new_line = (
                f"y-history window (length up to {t_ch} simulation steps{ch_note}; shorter early in the episode) is at "
                f"least {t_cy:g} m{cy_note} (approach from elevated path)."
            )
            description = re.sub(c_alt_pat, new_line, description, count=1)
    t_force = float(target_phys("force_limit_inside", _BASE_FORCE_LIMIT))
    b_force = float(base_phys("force_limit_inside", _BASE_FORCE_LIMIT))
    if t_force != b_force:
        pattern = r"(magnitude above )(\d+\.?\d*)( N \(Newtons\) while inside a zone resets that zone's progress)"
        if re.search(pattern, description):
            description = re.sub(
                pattern,
                f"\\g<1>{_fmt_scalar_prompt(t_force)} N (originally {_fmt_scalar_prompt(b_force)} N in the source environment) while inside a zone resets that zone's progress",
                description,
            )
    if t_speed != b_speed or t_force != b_force:
        speed_txt = (
            f"{t_speed} m/s (originally {b_speed} m/s in the source environment)"
            if t_speed != b_speed
            else f"{t_speed} m/s"
        )
        force_txt = (
            f"{_fmt_scalar_prompt(t_force)} N (originally {_fmt_scalar_prompt(b_force)} N in the source environment)"
            if t_force != b_force
            else f"{_fmt_scalar_prompt(t_force)} N"
        )
        pattern_obj_line = r"(Stay within speed cap \()(\d+\.?\d*)( m/s\) and force limit )(\d+\.?\d*)( N inside zones)"
        if re.search(pattern_obj_line, description):
            description = re.sub(
                pattern_obj_line,
                f"Stay within speed cap ({speed_txt}) and force limit {force_txt} inside zones",
                description,
            )
    t_rep = float(target_phys("repulsion_mag", _BASE_REPULSION_MAG))
    b_rep = float(base_phys("repulsion_mag", _BASE_REPULSION_MAG))
    if t_rep != b_rep:
        pattern = r"(peak repulsion scale\*\* at each zone center is )(\d+\.?\d*)( N \(Newtons\); strength decreases linearly)"
        if re.search(pattern, description):
            description = re.sub(
                pattern,
                f"\\g<1>{_fmt_repulsion_peak(t_rep)} N (Newtons) (originally {_fmt_repulsion_peak(b_rep)} N in the source environment); strength decreases linearly",
                description,
            )
    t_tan = float(target_phys("repulsion_tangential_mag", _BASE_REPULSION_TANGENTIAL_MAG))
    b_tan = float(base_phys("repulsion_tangential_mag", _BASE_REPULSION_TANGENTIAL_MAG))
    if t_tan != b_tan:
        tan_pat = r"(is )(not disclosed)(; rely on observed dwell behavior)"
        if re.search(tan_pat, description):
            b_tan_label = "not disclosed" if b_tan == 0.0 else f"{_fmt_repulsion_peak(b_tan)} N"
            description = re.sub(
                tan_pat,
                f"is {_fmt_repulsion_peak(t_tan)} N (originally {b_tan_label} in the source environment); rely on observed dwell behavior",
                description,
            )
    t_rr = float(target_phys("repulsion_range", _BASE_REPULSION_RANGE))
    b_rr = float(base_phys("repulsion_range", _BASE_REPULSION_RANGE))
    if t_rr != b_rr:
        rr_pat = r"(field extends to a radius of )(\d+\.?\d*)( m\.)"
        if re.search(rr_pat, description):
            description = re.sub(
                rr_pat,
                f"\\g<1>{_fmt_scalar_prompt(t_rr)} m (originally {_fmt_scalar_prompt(b_rr)} m in the source environment)\\g<3>",
                description,
            )
    t_bx = _effective_terrain(target_terrain_config, base_terrain_config, "barrier_x", _BASE_BARRIER_X)
    b_bx = _base_terrain(base_terrain_config, "barrier_x", _BASE_BARRIER_X)
    if t_bx != b_bx:
        bpat = r"- \*\*Barrier\*\*:.*$"
        if re.search(bpat, description):
            description = re.sub(
                bpat,
                r"- **Barrier**: blocks passage until it opens according to **Barrier delay after A** below.",
                description,
            )
        auth_bpat = r"(\*\*Barrier delay after A\*\*: )\d+"
        if re.search(auth_bpat, description):
            description = re.sub(
                auth_bpat,
                r"\g<1>None (same centerline x as the **Barrier** bullet below).",
                description,
            )
    t_sx = _effective_terrain(target_terrain_config, base_terrain_config, "spawn_x", _BASE_SPAWN_X)
    b_sx = _base_terrain(base_terrain_config, "spawn_x", _BASE_SPAWN_X)
    t_sy = _effective_terrain(target_terrain_config, base_terrain_config, "spawn_y", _BASE_SPAWN_Y)
    b_sy = _base_terrain(base_terrain_config, "spawn_y", _BASE_SPAWN_Y)
    t_ar = _effective_terrain(target_terrain_config, base_terrain_config, "agent_radius", _BASE_AGENT_RADIUS)
    b_ar = _base_terrain(base_terrain_config, "agent_radius", _BASE_AGENT_RADIUS)
    t_am = _effective_terrain(target_terrain_config, base_terrain_config, "agent_mass", _BASE_AGENT_MASS)
    b_am = _base_terrain(base_terrain_config, "agent_mass", _BASE_AGENT_MASS)
    if (t_sx, t_sy, t_ar, t_am) != (b_sx, b_sy, b_ar, b_am):
        apat = r"(- \*\*Agent\*\*: )[^.]+\."
        def _agent_repl(m: re.Match) -> str:
            passive = ""
            spawn_txt = f"Spawn at ({t_sx}, {t_sy}) m"
            if (t_sx, t_sy) != (b_sx, b_sy):
                spawn_txt += f" (originally Spawn at ({b_sx}, {b_sy}) m in the source environment)"
            rad_txt = f"radius {t_ar} m"
            if t_ar != b_ar:
                rad_txt = f"radius {t_ar} m (originally {b_ar} m in the source environment)"
            mass_txt = f"mass {t_am} kg"
            if t_am != b_am:
                mass_txt = f"mass {t_am} kg (originally {b_am} kg in the source environment)"
            return f"- **Agent**: {spawn_txt}; {rad_txt}; {mass_txt}."
        if re.search(apat, description):
            description = re.sub(apat, _agent_repl, description, count=1)
    t_maf = float(target_phys("max_agent_force_per_axis", _BASE_MAX_AGENT_FORCE_PER_AXIS))
    b_maf = float(base_phys("max_agent_force_per_axis", _BASE_MAX_AGENT_FORCE_PER_AXIS))
    if t_maf != b_maf:
        maf_pat = r"- \*\*Agent max applied force\*\*: [0-9.]+"
        if re.search(maf_pat, description):
            description = re.sub(
                maf_pat,
                f"- **Agent max applied force**: The controller can apply at most {t_maf} N per axis per step (originally {b_maf} N in the source environment).",
                description,
            )
    if t_trigger != b_trigger or t_ch != b_ch:
        c_hist_pat = r"- \*\*C altitude history\*\*: Rolling window of up to \d+ simulation steps \(TRIGGER_STAY_STEPS = \d+, C_HIGH_HISTORY = \d+\)\."
        if re.search(c_hist_pat, description):
            c_hist_repl = (
                f"- **C altitude history**: Rolling window of up to {t_ch} simulation steps "
                f"(TRIGGER_STAY_STEPS = {t_trigger}, C_HIGH_HISTORY = {t_ch})"
            )
            if t_trigger != b_trigger:
                c_hist_repl += f" (originally TRIGGER_STAY_STEPS = {b_trigger} in the source environment)"
            if t_ch != b_ch:
                c_hist_repl += f" (originally C_HIGH_HISTORY = {b_ch} in the source environment)"
            c_hist_repl += "."
            description = re.sub(c_hist_pat, c_hist_repl, description, count=1)
    return description

def update_success_criteria_for_visible_changes(
    base_success_criteria: str,
    target_terrain_config: Dict[str, Any],
    base_terrain_config: Dict[str, Any],
    target_physics_config: Dict[str, Any] = None,
    base_physics_config: Dict[str, Any] = None,

) -> str:
    criteria = base_success_criteria
    target_terrain_config = target_terrain_config or {}
    base_terrain_config = base_terrain_config or {}
    target_physics_config = target_physics_config or {}
    base_physics_config = base_physics_config or {}
    def target_phys(key: str, default: Any) -> Any:
        return target_physics_config.get(key, default)
    def base_phys(key: str, default: Any) -> Any:
        return _get_physics(base_physics_config, key, default)
    t_trigger = int(target_phys("trigger_stay_steps", _BASE_TRIGGER_STAY))
    b_trigger = int(base_phys("trigger_stay_steps", _BASE_TRIGGER_STAY))
    if t_trigger != b_trigger:
        pattern_act = r"(\*\*Activation duration\*\*: )(\d+)( consecutive steps per zone)( \(with speed.*)"
        if re.search(pattern_act, criteria):
            criteria = re.sub(
                pattern_act,
                f"\\g<1>{t_trigger} consecutive steps per zone (originally {b_trigger} steps in the source environment)\\g<4>",
                criteria,
            )
    t_speed = float(target_phys("speed_cap_inside", _BASE_SPEED_CAP))
    b_speed = float(base_phys("speed_cap_inside", _BASE_SPEED_CAP))
    t_force = float(target_phys("force_limit_inside", _BASE_FORCE_LIMIT))
    b_force = float(base_phys("force_limit_inside", _BASE_FORCE_LIMIT))
    if t_speed != b_speed:
        pattern = r"(with speed <= )(\d+\.?\d*)( m/s and force)"
        if re.search(pattern, criteria):
            criteria = re.sub(
                pattern,
                f"\\g<1>{t_speed} m/s (originally {b_speed} m/s in the source environment) and force",
                criteria,
                count=1,
            )
    if t_force != b_force:
        pattern = r"(and force <= )(\d+\.?\d*)( N inside zone)"
        if re.search(pattern, criteria):
            criteria = re.sub(
                pattern,
                f"and force <= {_fmt_scalar_prompt(t_force)} N (originally {_fmt_scalar_prompt(b_force)} N in the source environment) inside zone",
                criteria,
                count=1,
            )
    t_cool = int(target_phys("cooldown_steps", _BASE_COOLDOWN))
    b_cool = int(base_phys("cooldown_steps", _BASE_COOLDOWN))
    if t_cool != b_cool:
        pattern = r"(\*\*Cooldown\*\*: )(\d+)( steps between triggers\.)"
        if re.search(pattern, criteria):
            criteria = re.sub(
                pattern,
                f"\\g<1>{t_cool} steps (originally {b_cool} steps in the source environment) between triggers.",
                criteria,
            )
    t_barrier = int(target_phys("barrier_delay_steps", _BASE_BARRIER_DELAY))
    b_barrier = int(base_phys("barrier_delay_steps", _BASE_BARRIER_DELAY))
    if t_barrier != b_barrier:
        pattern = r"(\*\*Barrier delay\*\*: )(\d+)( steps after A before gate opens)"
        if re.search(pattern, criteria):
            criteria = re.sub(
                pattern,
                f"\\g<1>{t_barrier} steps (originally {b_barrier} steps in the source environment) after A before gate opens",
                criteria,
            )
    t_bx_c = _effective_terrain(target_terrain_config, base_terrain_config, "barrier_x", _BASE_BARRIER_X)
    b_bx_c = _base_terrain(base_terrain_config, "barrier_x", _BASE_BARRIER_X)
    if t_bx_c != b_bx_c:
        crit_geom_pat = r"(- \*\*Barrier geometry\*\*:.*?blocks passage).*?(?:per \*\*Barrier delay\*\* below\.|\. )"
        if re.search(crit_geom_pat, criteria):
            criteria = re.sub(
                crit_geom_pat,
                r"blocks passage until opened per **Barrier delay** below.",
                criteria,
            )
    t_mafc = float(target_phys("max_agent_force_per_axis", _BASE_MAX_AGENT_FORCE_PER_AXIS))
    b_mafc = float(base_phys("max_agent_force_per_axis", _BASE_MAX_AGENT_FORCE_PER_AXIS))
    if t_mafc != b_mafc:
        maf_crit_pat = r"(\*\*Agent max applied force\*\*:.*?)(\d+\.?\d*)( N.*)"
        if re.search(maf_crit_pat, criteria):
            criteria = re.sub(
                maf_crit_pat,
                f"\\g<1>{t_mafc} N (originally {b_mafc} N in the source environment)\\g<3>",
                criteria,
            )
    t_ab = int(target_phys("recent_a_for_b", _BASE_RECENT_A_FOR_B))
    b_ab = int(base_phys("recent_a_for_b", _BASE_RECENT_A_FOR_B))
    t_bc = int(target_phys("recent_b_for_c", _BASE_RECENT_B_FOR_C))
    b_bc = int(base_phys("recent_b_for_c", _BASE_RECENT_B_FOR_C))
    if t_ab != b_ab or t_bc != b_bc:
        tw_pattern = r"A to B within \d+ steps.*?B to C within \d+ steps"
        def _tw_repl(m: re.Match) -> str:
            cur = m.group(0)
            ab_m = re.search(r"A to B within (\d+) steps", cur)
            bc_m = re.search(r"B to C within (\d+) steps", cur)
            cur_ab = int(ab_m.group(1)) if ab_m else b_ab
            cur_bc = int(bc_m.group(1)) if bc_m else b_bc
            ab_new = t_ab if t_ab != b_ab else cur_ab
            bc_new = t_bc if t_bc != b_bc else cur_bc
            ab_tag = f" (originally {b_ab} steps in the source environment)" if t_ab != b_ab else ""
            bc_tag = f" (originally {b_bc} steps in the source environment)" if t_bc != b_bc else ""
            return f"A to B within {ab_new} steps{ab_tag}; B to C within {bc_new} steps{bc_tag}"
        if re.search(tw_pattern, criteria):
            criteria = re.sub(tw_pattern, _tw_repl, criteria)
    t_cy = float(target_phys("c_required_max_y", _BASE_C_REQUIRED_MAX_Y))
    b_cy = float(base_phys("c_required_max_y", _BASE_C_REQUIRED_MAX_Y))
    t_ch = int(target_phys("c_high_history", _BASE_C_HIGH_HISTORY))
    b_ch = int(base_phys("c_high_history", _BASE_C_HIGH_HISTORY))
    if t_cy != b_cy or t_ch != b_ch or t_trigger != b_trigger:
        pattern = r"(\*\*C altitude history\*\*: Rolling window of up to )(\d+)( simulation steps \(TRIGGER_STAY_STEPS = )(\d+)(, C_HIGH_HISTORY = )(\d+)(\)\.)"
        if re.search(pattern, criteria):
            hist_num = f"{t_ch}"
            if t_ch != b_ch:
                hist_num += f" (originally {b_ch} steps in the source environment)"
            trig_num = f"{t_trigger}"
            if t_trigger != b_trigger:
                trig_num += f" (originally {b_trigger} in the source environment)"
            criteria = re.sub(
                pattern,
                f"\\g<1>{hist_num}\\g<3>{trig_num}\\g<5>{t_ch}\\g<7>",
                criteria,
                count=1,
            )
    t_rr = float(target_phys("repulsion_range", _BASE_REPULSION_RANGE))
    b_rr = float(base_phys("repulsion_range", _BASE_REPULSION_RANGE))
    if t_rr != b_rr:
        rr_crit_pat = r"(field radius )(\d+\.?\d*)( m \(linear falloff\))"
        if re.search(rr_crit_pat, criteria):
            criteria = re.sub(
                rr_crit_pat,
                f"field radius {_fmt_scalar_prompt(t_rr)} m (originally {_fmt_scalar_prompt(b_rr)} m in the source environment) (linear falloff)",
                criteria,
            )
    t_rep = float(target_phys("repulsion_mag", _BASE_REPULSION_MAG))
    b_rep = float(base_phys("repulsion_mag", _BASE_REPULSION_MAG))
    if t_rep != b_rep:
        pat_rep = r"(Peak scale \(radial component\) )(\d+\.?\d*)( N at zone centers)"
        if re.search(pat_rep, criteria):
            criteria = re.sub(
                pat_rep,
                f"Peak scale (radial component) {_fmt_repulsion_peak(t_rep)} N (originally {_fmt_repulsion_peak(b_rep)} N in the source environment) at zone centers",
                criteria,
            )
    t_tan = float(target_phys("repulsion_tangential_mag", _BASE_REPULSION_TANGENTIAL_MAG))
    b_tan = float(base_phys("repulsion_tangential_mag", _BASE_REPULSION_TANGENTIAL_MAG))
    if t_tan != b_tan:
        pat_tan = r"(scale )(not disclosed)( \(infer from behavior\))"
        if re.search(pat_tan, criteria):
            b_tan_label = "not disclosed" if b_tan == 0.0 else f"{_fmt_repulsion_peak(b_tan)} N"
            criteria = re.sub(
                pat_tan,
                f"scale {_fmt_repulsion_peak(t_tan)} N (originally {b_tan_label} in the source environment) (infer from behavior)",
                criteria,
            )
    return criteria

def get_c05_curriculum_stages() -> List[Dict[str, Any]]:
    UNIFORM_SUFFIX = """

Sensors indicate that this region exhibits non-standard physical properties.
While the following variables **MIGHT** have changed from the initial environment, **NOT ALL** of them will necessarily be mutated in any given task. You must use active interaction and environmental feedback to deduce which specific conditions apply:
- **Regional speed limits**: Constraints on the maximum velocity allowed within trigger zones to count progress.
- **Repulsive field strength**: Alterations in the intensity of forces pushing the agent away from targets.
- **Repulsive field geometry**: The spatial pattern of repulsive forces near targets may differ from the baseline. A tangential (swirling) component may also be present.
- **Input sensitivity thresholds**: High in-zone forces may interact with the trigger mechanism in non-obvious ways; rely on observed dwell behavior rather than assumptions.
- **Ground friction**: Surface grip on flat ground may differ from the baseline environment.
- **Ramp friction**: Surface grip on ramps may differ from the baseline environment.
- **Platform friction**: Surface grip on the elevated platform may differ from the baseline environment.
- **Agent friction**: Contact grip of the agent body may differ from the baseline environment.
- **Barrier friction**: Contact grip of the barrier gate may differ from the baseline environment.
- **Environmental response timing**: Delays in barrier activation or system feedback after a trigger may vary.
- **Activation duration**: The required continuous time to stay within a zone to successfully trigger it.
- **Temporal sequencing windows**: Changes in the allowed time between sequential interactions (e.g., A to B or B to C).
- **State persistence requirements**: Changes in how long prior motion history (e.g., elevated trajectory) is remembered for downstream triggers.
- **Ambient wind / lateral forcing**: Time-varying lateral disturbances may or may not be present; magnitudes are not disclosed.

**Discovery via feedback**: Your objective is to identify the underlying physical rules of this specific environment through trial and reasoning. Initial standard solutions may fail; use run feedback to infer effective constraints and adapt your strategy.
"""
    return [
        {
            "stage_id": "Stage-1",
            "title": "Extended trigger cooldown",
            "mutation_description": "The cooldown between successive zone triggers is extended from 55 steps to 300 steps — the agent must actively hold position inside the previously triggered zone while waiting, then complete the next trigger before temporal and altitude-history windows expire. All other physics parameters remain at baseline values.",
            "task_description_suffix": UNIFORM_SUFFIX,
            "terrain_config": {},
            "physics_config": {
                "cooldown_steps": 300,
            },
        },
        {
            "stage_id": "Stage-2",
            "title": "Long dwell, strong repulsion, strict zone speed",
            "mutation_description": "Longer dwell requirement, stronger repulsion, low zone speed; temporal windows still widened.",
            "task_description_suffix": UNIFORM_SUFFIX,
            "terrain_config": {},
            "physics_config": {
                "trigger_stay_steps": 300,
                "speed_cap_inside": 0.05,
                "repulsion_mag": 40.0,
                "recent_a_for_b": 5000,
                "recent_b_for_c": 5000,
                "c_high_history": 5000,
            },
        },
        {
            "stage_id": "Stage-3",
            "title": "Arctic Vortex — Ice Ramp, Extreme Dwell, Low Force Cap",
            "mutation_description": "Multi-variable extreme: ultra-tight speed cap (0.03 m/s), low force cap in zones (24 N), very long dwell (150 steps), intense repulsion (55 N radial + 38 N tangential), ice ramps (0.04 friction), and slippery ground (0.10 friction). The agent must precisely balance speed/force constraints while fighting repulsion and near-frictionless slopes.",
            "task_description_suffix": UNIFORM_SUFFIX,
            "terrain_config": {
                "ramp_friction": 0.04,
                "ground_friction": 0.10,
            },
            "physics_config": {
                "speed_cap_inside": 0.03,
                "repulsion_mag": 55.0,
                "repulsion_tangential_mag": 38.0,
                "force_limit_inside": 24.0,
                "trigger_stay_steps": 150,
                "recent_a_for_b": 5000,
                "recent_b_for_c": 5000,
                "c_high_history": 5000,
            },
        },
        {
            "stage_id": "Stage-4",
            "title": "Compound friction, barrier delay, repulsion",
            "mutation_description": "Lower ground and ramp friction, longer barrier delay after A, long dwell, stronger repulsion including tangential component.",
            "task_description_suffix": UNIFORM_SUFFIX,
            "terrain_config": {
                "ramp_friction": 0.02,
                "ground_friction": 0.2,
            },
            "physics_config": {
                "speed_cap_inside": 0.08,
                "repulsion_mag": 45.0,
                "repulsion_tangential_mag": 40.0,
                "force_limit_inside": 60.0,
                "trigger_stay_steps": 120,
                "barrier_delay_steps": 350,
                "recent_a_for_b": 5000,
                "recent_b_for_c": 5000,
                "c_high_history": 5000,
            },
        },
    ]
