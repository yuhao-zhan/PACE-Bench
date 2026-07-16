from __future__ import annotations

import importlib.util

import os

import re

from typing import Any, Dict, List

_stages_dir = os.path.dirname(os.path.abspath(__file__))

_spec_c03_st = importlib.util.spec_from_file_location(
    "c03_environment_stages", os.path.join(_stages_dir, "environment.py")

)

_c03_env_st = importlib.util.module_from_spec(_spec_c03_st)

_spec_c03_st.loader.exec_module(_c03_env_st)

DEFAULT_ACTIVATION_ZONE_X_MIN = _c03_env_st.ACTIVATION_ZONE_X_MIN

DEFAULT_ACTIVATION_ZONE_X_MAX = _c03_env_st.ACTIVATION_ZONE_X_MAX

DEFAULT_ACTIVATION_REQUIRED_STEPS = _c03_env_st.ACTIVATION_REQUIRED_STEPS

DEFAULT_HEADING_REF_MIN_TARGET_SPEED = _c03_env_st.HEADING_REFERENCE_MIN_TARGET_SPEED

RENDEZVOUS_DISTANCE_DEFAULT = _c03_env_st.RENDEZVOUS_DISTANCE_DEFAULT

DEFAULT_IMPULSE_BUDGET = _c03_env_st.IMPULSE_BUDGET

DEFAULT_TRACK_DISTANCE = _c03_env_st.TRACK_DISTANCE_DEFAULT

DEFAULT_RENDEZVOUS_REL_SPEED = _c03_env_st.RENDEZVOUS_REL_SPEED_DEFAULT

DEFAULT_TARGET_SPEED = 1.5

DEFAULT_GROUND_FRICTION = 0.4

DEFAULT_SPAWN_X = 11.0

DEFAULT_SPAWN_Y = 1.35

DEFAULT_SLOTS_PHASE1 = list(_c03_env_st.SLOTS_PHASE1)

DEFAULT_SLOTS_PHASE2 = list(_c03_env_st.SLOTS_PHASE2)

DEFAULT_LINEAR_DAMPING = 0.5

DEFAULT_ANGULAR_DAMPING = 0.5

DEFAULT_GRAVITY_XY = (0.0, -10.0)

DEFAULT_COOLDOWN_THRESHOLD = _c03_env_st.COOLDOWN_THRESHOLD

DEFAULT_COOLDOWN_MAX_THRUST = _c03_env_st.COOLDOWN_MAX_THRUST

DEFAULT_COOLDOWN_STEPS = _c03_env_st.COOLDOWN_STEPS

DEFAULT_MAX_THRUST_MAGNITUDE = _c03_env_st.MAX_THRUST_MAGNITUDE

DEFAULT_HEADING_TOLERANCE_DEG = _c03_env_st.RENDEZVOUS_HEADING_TOLERANCE_DEG_DEFAULT

DEFAULT_BLIND_ZONE_X_MIN = _c03_env_st.BLIND_ZONE_X_MIN

DEFAULT_BLIND_ZONE_X_MAX = _c03_env_st.BLIND_ZONE_X_MAX

DEFAULT_SPEED_BLIND_THRESHOLD = _c03_env_st.SPEED_BLIND_THRESHOLD

DEFAULT_RENDEZVOUS_DISTANCE = RENDEZVOUS_DISTANCE_DEFAULT

DEFAULT_RENDEZVOUS_ZONE_X_MIN = _c03_env_st.RENDEZVOUS_ZONE_X_MIN

DEFAULT_RENDEZVOUS_ZONE_X_MAX = _c03_env_st.RENDEZVOUS_ZONE_X_MAX

DEFAULT_GROUND_Y_TOP = _c03_env_st.DEFAULT_GROUND_Y_TOP

DEFAULT_SEEKER_MASS = 20.0

DEFAULT_SEEKER_RADIUS = 0.35

DEFAULT_TARGET_START_X = 12.0

DEFAULT_TARGET_START_Y = 2.0

DEFAULT_TARGET_CHANGE_INTERVAL = 1.2

STATIC_OBSTACLE_FIXTURE_SNIPPET = "fixture friction 0.5, restitution 0.1"

_orig_plain = r"(\d+\.\d+), (\d+\.\d+)"

_PROMPT_SCALAR = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"

def _gravity_tuple(physics_cfg: Dict[str, Any]) -> tuple:
    physics_cfg = physics_cfg or {}
    g = physics_cfg.get("gravity", DEFAULT_GRAVITY_XY)
    if isinstance(g, (list, tuple)) and len(g) >= 2:
        return (float(g[0]), float(g[1]))
    return DEFAULT_GRAVITY_XY

DEFAULT_ICE_ZONES = [tuple(z) for z in _c03_env_st.ICE_ZONES]

def _ice_zones_key(zones) -> tuple:
    if not zones:
        return ()
    out = []
    for item in zones:
        (cx, cy, hw, hh), mu = item
        out.append(
            (
                round(float(cx), 6),
                round(float(cy), 6),
                round(float(hw), 6),
                round(float(hh), 6),
                round(float(mu), 6),
            )
        )
    return tuple(out)

def _fmt_ice_xy(x: float, y: float) -> str:
    return f"({float(x):.1f}, {float(y):.2f})"

def _fmt_ice_half(hw: float, hh: float) -> str:
    return f"{float(hw):.1f}×{float(hh):.2f}"

def _format_ice_sentence(zones) -> str:
    if not zones:
        return "none"
    zlist = list(zones)
    if len(zlist) == 2:
        (ax, ay, ahw, ahh), mu0 = zlist[0]
        (bx, by, bhw, bhh), mu1 = zlist[1]
        if (
            abs(float(mu0) - float(mu1)) < 1e-12
            and abs(float(ahw) - float(bhw)) < 1e-12
            and abs(float(ahh) - float(bhh)) < 1e-12
        ):
            return (
                f"2 identical low-friction ice patches at {_fmt_ice_xy(ax, ay)} "
                f"and {_fmt_ice_xy(bx, by)} "
                f"with friction {mu0:.2f} and size {ahw:.1f}×{ahh:.2f}"
            )
    parts = []
    for (cx, cy, hw, hh), mu in zlist:
        parts.append(
            f"centered at {_fmt_ice_xy(cx, cy)} with friction {mu:.2f} and size "
            f"{_fmt_ice_half(hw, hh)}"
        )
    return (
        "Low-friction ice patches: " + "; ".join(parts) + " on the patch fixtures (seeker–patch contact)"
    )

def _replace_ice_task_line(description: str, body: str) -> str:
    return re.sub(r"(- \*\*Ice patches\*\*: )[^\n]*", rf"\g<1>{body}", description, count=1)

STATIC_BOXES_PROMPT_SNIPPET = "at (7.5, 1.5, 0.3, 0.5); at (14.0, 1.5, 0.3, 0.5); at (20.5, 1.5, 0.3, 0.5)"

MOVING_OBSTACLES_PROMPT_SNIPPET = "Kinematic boxes oscillating horizontally in the corridor at (10.5, 1.5) and (17.0, 1.5); query `sandbox.get_terrain_obstacles()` for real-time positions"

def _slot_window_bounds(slots_phase1: List, slots_phase2: List) -> tuple:
    def bounds(slots):
        if not slots:
            return 3700, 4800
        try:
            return min(s[0] for s in slots), max(s[1] for s in slots)
        except (TypeError, IndexError):
            return 3700, 4800
    p1_lo, p1_hi = bounds(slots_phase1)
    p2_lo, p2_hi = bounds(slots_phase2)
    return p1_lo, p1_hi, p2_lo, p2_hi

def _format_slot_bands(slots: List) -> str:
    if not slots:
        return ""
    return ", ".join(f"[{int(s[0])}, {int(s[1])}]" for s in slots)

def _require_pristine_prompt_text(text: str, *, label: str) -> None:
    if "(originally " in text and " in the source environment)" in text:
        raise ValueError(
        )

def update_task_description_for_visible_changes(
    base_description: str,
    target_terrain_config: Dict[str, Any],
    base_terrain_config: Dict[str, Any],
    target_physics_config: Dict[str, Any] = None,
    base_physics_config: Dict[str, Any] = None,

) -> str:
    _require_pristine_prompt_text(base_description, label="base_description (task_description)")
    description = base_description
    target_terrain_config = target_terrain_config or {}
    base_terrain_config = base_terrain_config or {}
    tp = dict(target_physics_config or {})
    bp = dict(base_physics_config or {})
    base_az0 = float(
        base_terrain_config.get("activation_zone_x_min", DEFAULT_ACTIVATION_ZONE_X_MIN)
    )
    base_az1 = float(
        base_terrain_config.get("activation_zone_x_max", DEFAULT_ACTIVATION_ZONE_X_MAX)
    )
    base_ast = int(
        base_terrain_config.get("activation_required_steps", DEFAULT_ACTIVATION_REQUIRED_STEPS)
    )
    target_az0 = float(target_terrain_config.get("activation_zone_x_min", base_az0))
    target_az1 = float(target_terrain_config.get("activation_zone_x_max", base_az1))
    target_ast = int(target_terrain_config.get("activation_required_steps", base_ast))
    if (target_az0, target_az1, target_ast) != (base_az0, base_az1, base_ast):
        act_gate_pat = (
            r"(Rendezvous only counts after the seeker \"activates\" by staying at least )(\d+)( consecutive steps with seeker x in )\[" + r"(\d+\.\d+)" + r", " + r"(\d+\.\d+)" + r"\]"
        )
        if re.search(act_gate_pat, description):
            bounds_disp = f"[{target_az0:.1f}, {target_az1:.1f}] m"
            if abs(target_az0 - base_az0) > 1e-9 or abs(target_az1 - base_az1) > 1e-9:
                bounds_disp += f" (originally [{base_az0:.1f}, {base_az1:.1f}] m in the source environment)"
            step_disp = f"for at least {target_ast} consecutive steps"
            if target_ast != base_ast:
                step_disp += f" (originally {base_ast} in the source environment)"
            description = re.sub(
                act_gate_pat,
                f"\\g<1>{step_disp} \\g<3>{bounds_disp}",
                description,
                count=1,
            )
    base_href = float(
        base_terrain_config.get(
            "heading_reference_min_target_speed", DEFAULT_HEADING_REF_MIN_TARGET_SPEED
        )
    )
    target_href = float(
        target_terrain_config.get("heading_reference_min_target_speed", base_href)
    )
    if abs(target_href - base_href) > 1e-12:
        href_obj_pat = (
            r"(target speed ≥ )" + r"(\d+\.\d+)" + r"( m/s, else)"
        )
        if re.search(href_obj_pat, description):
            description = re.sub(
                href_obj_pat,
                f"\\g<1>{target_href:g}\\g<3> (originally {base_href:g} m/s in the source environment)",
                description,
                count=1,
            )
    target_speed = float(target_terrain_config.get("target_speed", DEFAULT_TARGET_SPEED))
    base_speed = float(base_terrain_config.get("target_speed", DEFAULT_TARGET_SPEED))
    if target_speed != base_speed:
        pattern = (
            r"(default speed )" + r"(\d+\.\d+)" + r" m/s"
        )
        if re.search(pattern, description):
            description = re.sub(
                pattern,
                f"\\g<1>{target_speed:.1f} m/s (originally {base_speed:.1f} m/s in the source environment)",
                description,
                count=1,
            )
    target_obstacles = target_terrain_config.get("obstacles")
    if target_obstacles is not None and len(target_obstacles) == 0:
        esc = re.escape(STATIC_BOXES_PROMPT_SNIPPET)
        pattern = rf"(\*\*Static boxes\*\*: ){esc}(\.)"
        if re.search(pattern, description):
            description = re.sub(
                pattern,
                rf"\1none (originally {STATIC_BOXES_PROMPT_SNIPPET} in the source environment)\2",
                description,
                count=1,
            )
    base_ice = base_terrain_config.get("ice_zones", None)
    if base_ice is None:
        base_ice = list(DEFAULT_ICE_ZONES)
    if "ice_zones" in target_terrain_config:
        target_ice = target_terrain_config["ice_zones"]
        if len(target_ice) == 0:
            body = f"none (originally {_format_ice_sentence(base_ice)} in the source environment)."
            if re.search(r"- \*\*Ice patches\*\*:", description):
                description = _replace_ice_task_line(description, body)
        elif _ice_zones_key(target_ice) != _ice_zones_key(base_ice):
            body = (
                f"{_format_ice_sentence(target_ice)} (originally {_format_ice_sentence(base_ice)} in the source environment)."
            )
            if re.search(r"- \*\*Ice patches\*\*:", description):
                description = _replace_ice_task_line(description, body)
    target_sx = float(target_terrain_config.get("spawn_x", DEFAULT_SPAWN_X))
    target_sy = float(target_terrain_config.get("spawn_y", DEFAULT_SPAWN_Y))
    base_sx = float(base_terrain_config.get("spawn_x", DEFAULT_SPAWN_X))
    base_sy = float(base_terrain_config.get("spawn_y", DEFAULT_SPAWN_Y))
    if (target_sx, target_sy) != (base_sx, base_sy):
        spawn_re = re.compile(
            r"Spawns at \(" + _PROMPT_SCALAR + r", " + _PROMPT_SCALAR + r"\) m \(x, y\)\."
        )
        if spawn_re.search(description):
            description = spawn_re.sub(
                f"Spawns at ({target_sx}, {target_sy}) m (x, y) (originally ({base_sx}, {base_sy}) m (x, y) in the source environment).",
                description,
                count=1,
            )
    base_sm = float(base_terrain_config.get("seeker_mass", DEFAULT_SEEKER_MASS))
    base_sr = float(base_terrain_config.get("seeker_radius", DEFAULT_SEEKER_RADIUS))
    target_sm = float(target_terrain_config.get("seeker_mass", base_sm))
    target_sr = float(target_terrain_config.get("seeker_radius", base_sr))
    if abs(target_sm - base_sm) > 1e-9 or abs(target_sr - base_sr) > 1e-9:
        seeker_mr_pat = (
            r"(seeker mass: default )" + r"(\d+\.\d+)" + r" kg"
        )
        if re.search(seeker_mr_pat, description):
            description = re.sub(
                seeker_mr_pat,
                f"\\g<1>{target_sm:.1f} kg (originally {base_sm:.1f} kg in the source environment)",
                description,
                count=1,
            )
    base_tx = float(base_terrain_config.get("target_start_x", DEFAULT_TARGET_START_X))
    base_ty = float(base_terrain_config.get("target_start_y", DEFAULT_TARGET_START_Y))
    target_tx = float(target_terrain_config.get("target_start_x", base_tx))
    target_ty = float(target_terrain_config.get("target_start_y", base_ty))
    if abs(target_tx - base_tx) > 1e-9 or abs(target_ty - base_ty) > 1e-9:
        tgt_start_pat = (
            r"(Starts at \()" + r"(\d+\.\d+)" + r"(, )" + r"(\d+\.\d+)" + r"(\) m)"
        )
        if re.search(tgt_start_pat, description):
            description = re.sub(
                tgt_start_pat,
                f"\\g<1>{target_tx:.1f}\\g<3>{target_ty:.1f}\\g<5> (originally ({base_tx:.1f}, {base_ty:.1f}) m in the source environment)",
                description,
                count=1,
            )
    base_tci = float(base_terrain_config.get("target_change_interval", DEFAULT_TARGET_CHANGE_INTERVAL))
    target_tci = float(target_terrain_config.get("target_change_interval", base_tci))
    if abs(target_tci - base_tci) > 1e-9:
        tci_pat = (
            r"(direction changes roughly every )" + r"(\d+\.\d+)" + r" s"
        )
        if re.search(tci_pat, description):
            description = re.sub(
                tci_pat,
                f"\\g<1>{target_tci:.1f} s (originally {base_tci:.1f} s in the source environment)",
                description,
                count=1,
            )
    target_impulse = float(target_terrain_config.get("impulse_budget", DEFAULT_IMPULSE_BUDGET))
    base_impulse = float(base_terrain_config.get("impulse_budget", DEFAULT_IMPULSE_BUDGET))
    if target_impulse != base_impulse:
        impulse_pat = (
            r"(Total thrust impulse is limited to )" + r"(\d+)" + r" N·s"
        )
        if re.search(impulse_pat, description):
            description = re.sub(
                impulse_pat,
                f"\\g<1>{target_impulse:.0f} N·s (originally {base_impulse:.0f} N·s in the source environment)",
                description,
            )
    target_track = float(target_terrain_config.get("track_distance", DEFAULT_TRACK_DISTANCE))
    base_track = float(base_terrain_config.get("track_distance", DEFAULT_TRACK_DISTANCE))
    if target_track != base_track:
        track_pat = (
            r"(Maintain distance <= )" + r"(\d+\.\d+)" + r" m from the target"
        )
        if re.search(track_pat, description):
            description = re.sub(
                track_pat,
                f"\\g<1>{target_track:.1f} m (originally {base_track:.1f} m in the source environment)",
                description,
                count=1,
            )
    target_rel = float(target_terrain_config.get("rendezvous_rel_speed", DEFAULT_RENDEZVOUS_REL_SPEED))
    base_rel = float(base_terrain_config.get("rendezvous_rel_speed", DEFAULT_RENDEZVOUS_REL_SPEED))
    if abs(target_rel - base_rel) > 1e-9:
        rel_pat = (
            r"(relative speed < )" + r"(\d+\.\d+)" + r" m/s"
        )
        if re.search(rel_pat, description):
            description = re.sub(
                rel_pat,
                f"\\g<1>{target_rel:.2f} m/s (originally {base_rel:.2f} m/s in the source environment)",
                description,
                count=1,
            )
    base_rd = float(base_terrain_config.get("rendezvous_distance", DEFAULT_RENDEZVOUS_DISTANCE))
    target_rd = float(target_terrain_config.get("rendezvous_distance", base_rd))
    if abs(target_rd - base_rd) > 1e-9:
        rd_pat = (
            r"(distance to target ≤ )" + r"(\d+\.\d+)" + r" m"
        )
        if re.search(rd_pat, description):
            description = re.sub(
                rd_pat,
                f"\\g<1>{target_rd:.1f}m (originally {base_rd:.1f} m in the source environment)",
                description,
                count=1,
            )
    base_rzx0 = float(base_terrain_config.get("rendezvous_zone_x_min", DEFAULT_RENDEZVOUS_ZONE_X_MIN))
    base_rzx1 = float(base_terrain_config.get("rendezvous_zone_x_max", DEFAULT_RENDEZVOUS_ZONE_X_MAX))
    target_rzx0 = float(target_terrain_config.get("rendezvous_zone_x_min", base_rzx0))
    target_rzx1 = float(target_terrain_config.get("rendezvous_zone_x_max", base_rzx1))
    if abs(target_rzx0 - base_rzx0) > 1e-9 or abs(target_rzx1 - base_rzx1) > 1e-9:
        rzx_pat = (
            r"seeker x ∈ \[" + r"(\d+\.\d+)" + r", " + r"(\d+\.\d+)" + r"\] m"
        )
        if re.search(rzx_pat, description):
            description = re.sub(
                rzx_pat,
                f"seeker x ∈ [{target_rzx0:.1f}, {target_rzx1:.1f}] m (originally [{base_rzx0:.1f}, {base_rzx1:.1f}] m in the source environment)",
                description,
                count=1,
            )
    base_ht = float(
        base_terrain_config.get("rendezvous_heading_tolerance_deg", DEFAULT_HEADING_TOLERANCE_DEG)
    )
    target_ht = float(
        target_terrain_config.get("rendezvous_heading_tolerance_deg", base_ht)
    )
    if abs(target_ht - base_ht) > 1e-9:
        ht_pat = (
            r"(heading within )" + r"(\d+\.\d+)" + r"(° of the reference direction)"
        )
        if re.search(ht_pat, description):
            description = re.sub(
                ht_pat,
                f"\\g<1>{target_ht:.1f}\\g<3> (originally {base_ht:.1f}\\g<3> in the source environment)",
                description,
                count=1,
            )
    base_mtm = float(base_terrain_config.get("max_thrust_magnitude", DEFAULT_MAX_THRUST_MAGNITUDE))
    target_mtm = float(target_terrain_config.get("max_thrust_magnitude", base_mtm))
    if abs(target_mtm - base_mtm) > 1e-9:
        mtm_pat = (
            r"(max )" + r"(\d+)" + r" N"
        )
        if re.search(mtm_pat, description):
            description = re.sub(
                mtm_pat,
                f"\\g<1>{target_mtm:.0f} N (originally {base_mtm:.0f} N in the source environment)",
                description,
                count=1,
            )
    base_cth = float(base_terrain_config.get("cooldown_threshold", DEFAULT_COOLDOWN_THRESHOLD))
    base_cmt = float(base_terrain_config.get("cooldown_max_thrust", DEFAULT_COOLDOWN_MAX_THRUST))
    base_csteps = int(base_terrain_config.get("cooldown_steps", DEFAULT_COOLDOWN_STEPS))
    target_cth = float(target_terrain_config.get("cooldown_threshold", base_cth))
    target_cmt = float(target_terrain_config.get("cooldown_max_thrust", base_cmt))
    target_csteps = int(target_terrain_config.get("cooldown_steps", base_csteps))
    if (target_cth, target_cmt, target_csteps) != (base_cth, base_cmt, base_csteps):
        cool_desc_pat = re.compile(
            r"(Exceeding )" + _PROMPT_SCALAR + r"( N thrust triggers a cooldown; during the next )(\d+)( steps, maximum thrust is reduced to )" + _PROMPT_SCALAR + r"( N\.)",
            re.DOTALL,
        )
        m = cool_desc_pat.search(description)
        if m:
            thr_exceeds = f"{target_cth:.0f}"
            if abs(target_cth - base_cth) > 1e-9:
                thr_exceeds += f" (originally {base_cth:.0f} N in the source environment)"
            steps_disp = str(target_csteps)
            if target_csteps != base_csteps:
                steps_disp += f" (originally {base_csteps} in the source environment)"
            thr_reduced = f"{target_cmt:.0f}"
            if abs(target_cmt - base_cmt) > 1e-9:
                thr_reduced += f" (originally {base_cmt:.0f} N in the source environment)"
            replacement = (
                f"Exceeding {thr_exceeds} N thrust triggers a cooldown; "
                f"during the next {steps_disp} steps, maximum thrust is reduced to {thr_reduced} N."
            )
            description = re.sub(cool_desc_pat, replacement, description, count=1)
    base_bzmin = float(base_terrain_config.get("blind_zone_x_min", DEFAULT_BLIND_ZONE_X_MIN))
    base_bzmax = float(base_terrain_config.get("blind_zone_x_max", DEFAULT_BLIND_ZONE_X_MAX))
    target_bzmin = float(target_terrain_config.get("blind_zone_x_min", base_bzmin))
    target_bzmax = float(target_terrain_config.get("blind_zone_x_max", base_bzmax))
    base_sb = float(base_terrain_config.get("speed_blind_threshold_mps", DEFAULT_SPEED_BLIND_THRESHOLD))
    target_sb = float(target_terrain_config.get("speed_blind_threshold_mps", base_sb))
    if (
        abs(target_bzmin - base_bzmin) > 1e-9
        or abs(target_bzmax - base_bzmax) > 1e-9
        or abs(target_sb - base_sb) > 1e-9
    ):
        blind_pat = re.compile(
            r"If seeker x is in .+?the reading does not update \(stale\)\.",
            re.DOTALL,
        )
        x_clause = f"[{target_bzmin:.1f}, {target_bzmax:.1f}] m (blind band)"
        if abs(target_bzmin - base_bzmin) > 1e-9 or abs(target_bzmax - base_bzmax) > 1e-9:
            x_clause += f" (originally [{base_bzmin:.1f}, {base_bzmax:.1f}] m in the source environment)"
        sb_clause = f"OR seeker speed > {target_sb:.1f} m/s"
        if abs(target_sb - base_sb) > 1e-9:
            sb_clause += f" (originally {base_sb:.1f} m/s in the source environment)"
        new_blind = (
            f"If seeker x is in {x_clause} {sb_clause}, the reading does not update (stale)."
        )
        if blind_pat.search(description):
            description = blind_pat.sub(new_blind, description, count=1)
    base_gy_top = float(base_terrain_config.get("ground_y_top", DEFAULT_GROUND_Y_TOP))
    target_gy_top = float(target_terrain_config.get("ground_y_top", base_gy_top))
    if abs(target_gy_top - base_gy_top) > 1e-9:
        gy_top_pat = (
            r"(top surface at y = )" + r"(\d+\.\d+)" + r" m"
        )
        if re.search(gy_top_pat, description, re.IGNORECASE):
            description = re.sub(
                gy_top_pat,
                f"\\g<1>{target_gy_top:.1f} m (originally {base_gy_top:.1f} m in the source environment)",
                description,
                count=1,
                flags=re.IGNORECASE,
            )
        ymin_t, ymax_t = target_gy_top + 0.5, target_gy_top + 2.0
        ymin_b, ymax_b = base_gy_top + 0.5, base_gy_top + 2.0
        tgt_y_pat = (
            r"y ∈ \[" + r"(\d+\.\d+)" + r", " + r"(\d+\.\d+)" + r"\] m"
        )
        if re.search(tgt_y_pat, description):
            description = re.sub(
                tgt_y_pat,
                f"y ∈ [{ymin_t:.1f}, {ymax_t:.1f}] m (originally [{ymin_b:.1f}, {ymax_b:.1f}] m in the source environment)",
                description,
                count=1,
            )
    if target_obstacles is not None and len(target_obstacles) > 0 and target_obstacles != [(7.5, 1.5, 0.3, 0.5), (14.0, 1.5, 0.3, 0.5), (20.5, 1.5, 0.3, 0.5)]:
        esc = re.escape(STATIC_BOXES_PROMPT_SNIPPET)
        pattern = rf"(\*\*Static boxes\*\*: ){esc}(\.)"
        if re.search(pattern, description):
            new_obs_str = "; ".join(
                f"({cx:.1f}, {cy:.1f}, {hw:.1f}, {hh:.1f})" for cx, cy, hw, hh in target_obstacles
            )
            new_obs_str = f"{new_obs_str}, {STATIC_OBSTACLE_FIXTURE_SNIPPET}"
            description = re.sub(
                pattern,
                rf"\1{new_obs_str} (originally {STATIC_BOXES_PROMPT_SNIPPET} in the source environment)\2",
                description,
                count=1,
            )
    if "moving_obstacle" in target_terrain_config or "moving_obstacle_2" in target_terrain_config:
        target_mo1 = target_terrain_config.get("moving_obstacle")
        base_mo1 = base_terrain_config.get("moving_obstacle")
        target_mo2 = target_terrain_config.get("moving_obstacle_2")
        base_mo2 = base_terrain_config.get("moving_obstacle_2")
        tmo1_actual = target_mo1 is not None
        bmo1_actual = (base_mo1 is not None) if "moving_obstacle" in base_terrain_config else True
        tmo2_actual = target_mo2 is not None
        bmo2_actual = (base_mo2 is not None) if "moving_obstacle_2" in base_terrain_config else True
        if tmo1_actual != bmo1_actual or tmo2_actual != bmo2_actual:
            mo_esc = re.escape(MOVING_OBSTACLES_PROMPT_SNIPPET)
            mo_pattern = rf"(\*\*Moving obstacles\*\*: ){mo_esc}(\.)"
            if re.search(mo_pattern, description):
                if tmo1_actual and tmo2_actual:
                    description = re.sub(
                        mo_pattern,
                        rf"\1{MOVING_OBSTACLES_PROMPT_SNIPPET} (unchanged from source environment)\2",
                        description,
                        count=1,
                    )
                elif not tmo1_actual and not tmo2_actual:
                    description = re.sub(
                        mo_pattern,
                        rf"\1none (originally {MOVING_OBSTACLES_PROMPT_SNIPPET} in the source environment)\2",
                        description,
                        count=1,
                    )
                elif not tmo1_actual:
                    description = re.sub(
                        mo_pattern,
                        rf"\1one kinematic box oscillating horizontally at (17.0, 1.5); query `sandbox.get_terrain_obstacles()` for real-time positions. (originally {MOVING_OBSTACLES_PROMPT_SNIPPET} in the source environment)\2",
                        description,
                        count=1,
                    )
                else:
                    description = re.sub(
                        mo_pattern,
                        rf"\1one kinematic box oscillating horizontally at (10.5, 1.5); query `sandbox.get_terrain_obstacles()` for real-time positions. (originally {MOVING_OBSTACLES_PROMPT_SNIPPET} in the source environment)\2",
                        description,
                        count=1,
                    )
    t_s1 = target_terrain_config.get("slots_phase1", DEFAULT_SLOTS_PHASE1)
    t_s2 = target_terrain_config.get("slots_phase2", DEFAULT_SLOTS_PHASE2)
    b_s1 = base_terrain_config.get("slots_phase1", DEFAULT_SLOTS_PHASE1)
    b_s2 = base_terrain_config.get("slots_phase2", DEFAULT_SLOTS_PHASE2)
    if t_s1 != b_s1 or t_s2 != b_s2:
        t_lo1, t_hi1, t_lo2, t_hi2 = _slot_window_bounds(t_s1, t_s2)
        b_lo1, b_hi1, b_lo2, b_hi2 = _slot_window_bounds(b_s1, b_s2)
        window_pat = r'(?!)'
        if re.search(window_pat, description):
            description = re.sub(
                window_pat,
                f"\\g<1> and \\g<2> steps (originally \\g<1> and \\g<2> in the source environment)",
                description,
                count=1,
            )
        slots_strip_pat = r'(?!)'
        if re.search(slots_strip_pat, description):
            description = re.sub(slots_strip_pat, r"\1 and \2", description, count=1)
        slots_pat = r'(?!)'
        if re.search(slots_pat, description):
            t_f1 = _format_slot_bands(t_s1)
            t_f2 = _format_slot_bands(t_s2)
            b_f1 = _format_slot_bands(b_s1)
            b_f2 = _format_slot_bands(b_s2)
            description = re.sub(
                slots_pat,
                f"phase 1 {t_f1}; phase 2 {t_f2} (originally phase 1 {b_f1}; phase 2 {b_f2} in the source environment)",
                description,
                count=1,
            )
    return description

def update_success_criteria_for_visible_changes(
    base_success_criteria: str,
    target_terrain_config: Dict[str, Any],
    base_terrain_config: Dict[str, Any],
    target_physics_config: Dict[str, Any] = None,
    base_physics_config: Dict[str, Any] = None,

) -> str:
    _require_pristine_prompt_text(base_success_criteria, label="base_success_criteria")
    criteria = base_success_criteria
    target_terrain_config = target_terrain_config or {}
    base_terrain_config = base_terrain_config or {}
    base_az0 = float(
        base_terrain_config.get("activation_zone_x_min", DEFAULT_ACTIVATION_ZONE_X_MIN)
    )
    base_az1 = float(
        base_terrain_config.get("activation_zone_x_max", DEFAULT_ACTIVATION_ZONE_X_MAX)
    )
    base_ast = int(
        base_terrain_config.get("activation_required_steps", DEFAULT_ACTIVATION_REQUIRED_STEPS)
    )
    target_az0 = float(target_terrain_config.get("activation_zone_x_min", base_az0))
    target_az1 = float(target_terrain_config.get("activation_zone_x_max", base_az1))
    target_ast = int(target_terrain_config.get("activation_required_steps", base_ast))
    if (target_az0, target_az1, target_ast) != (base_az0, base_az1, base_ast):
        act_succ_pat = (
            r"activation already achieved \(\≥" + r"(\d+)" + r"( consecutive steps with seeker x ∈ )" + r"(\[)" + r"(\d+\.\d+)" + r"(, )" + r"(\d+\.\d+)" + r"(\] m\))"
        )
        if re.search(act_succ_pat, criteria):
            m = re.search(act_succ_pat, criteria)
            g1 = m.group(1)
            g2 = m.group(2)
            g3 = m.group(3)
            g4 = m.group(4)
            g5 = m.group(5)
            g6 = m.group(6)
            g7 = m.group(7)
            orig_act = f" (originally ≥{g1}{g2}{g3}{g4}{g5}{g6}{g7} in the source environment)"
            repl = f"(≥{target_ast}{g2}{g3}{target_az0:.1f}{g5}{target_az1:.1f}{g7})" + orig_act
            criteria = re.sub(act_succ_pat, repl, criteria, count=1)
    base_href = float(
        base_terrain_config.get(
            "heading_reference_min_target_speed", DEFAULT_HEADING_REF_MIN_TARGET_SPEED
        )
    )
    target_href = float(
        target_terrain_config.get("heading_reference_min_target_speed", base_href)
    )
    if abs(target_href - base_href) > 1e-12:
        href_sc_pat = (
            r"(target speed ≥ )" + r"(\d+\.\d+)" + r"( m/s, else)"
        )
        if re.search(href_sc_pat, criteria):
            criteria = re.sub(
                href_sc_pat,
                f"\\g<1>{target_href:g}\\g<3> (originally {base_href:g} m/s in the source environment)",
                criteria,
                count=1,
            )
    target_track = float(target_terrain_config.get("track_distance", DEFAULT_TRACK_DISTANCE))
    base_track = float(base_terrain_config.get("track_distance", DEFAULT_TRACK_DISTANCE))
    if target_track != base_track:
        pattern = (
            r"(Maintain distance <= )" + r"(\d+\.\d+)" + r" m( from)"
        )
        if re.search(pattern, criteria):
            criteria = re.sub(
                pattern,
                f"\\g<1>{target_track:.1f} m\\g<3> (originally {base_track:.1f} m in the source environment)",
                criteria,
                count=1,
            )
    target_impulse = float(target_terrain_config.get("impulse_budget", DEFAULT_IMPULSE_BUDGET))
    base_impulse = float(base_terrain_config.get("impulse_budget", DEFAULT_IMPULSE_BUDGET))
    if target_impulse != base_impulse:
        pattern = (
            r"(Total thrust impulse must not exceed \*\*)" + r"(\d+)" + r"( N·s)"
        )
        if re.search(pattern, criteria):
            criteria = re.sub(
                pattern,
                f"\\g<1>{target_impulse:.0f}\\g<3> (originally **{base_impulse:.0f}\\g<3>** in the source environment)",
                criteria,
                count=1,
            )
        fuel_budget_pat = (
            r"(\*\*Fuel budget\*\*: )" + r"(\d+)" + r"( N·s total thrust impulse; reaching or exceeding fails the run\.)"
        )
        if re.search(fuel_budget_pat, criteria):
            criteria = re.sub(
                fuel_budget_pat,
                f"\\g<1>{target_impulse:.0f}\\g<3> (originally {base_impulse:.0f} N·s total thrust impulse in the source environment)",
                criteria,
                count=1,
            )
    target_rel = float(target_terrain_config.get("rendezvous_rel_speed", DEFAULT_RENDEZVOUS_REL_SPEED))
    base_rel = float(base_terrain_config.get("rendezvous_rel_speed", DEFAULT_RENDEZVOUS_REL_SPEED))
    if abs(target_rel - base_rel) > 1e-9:
        rel_pat = (
            r"(relative speed < )" + r"(\d+\.\d+)" + r" m/s"
        )
        if re.search(rel_pat, criteria):
            criteria = re.sub(
                rel_pat,
                f"\\g<1>{target_rel:.2f} m/s (originally {base_rel:.2f} m/s in the source environment)",
                criteria,
                count=1,
            )
    base_rd = float(base_terrain_config.get("rendezvous_distance", DEFAULT_RENDEZVOUS_DISTANCE))
    target_rd = float(target_terrain_config.get("rendezvous_distance", base_rd))
    if abs(target_rd - base_rd) > 1e-9:
        rd_crit_pat = (
            r"(distance to \*\*true\*\* target ≤ )" + r"(\d+\.\d+)" + r" m"
        )
        if re.search(rd_crit_pat, criteria):
            criteria = re.sub(
                rd_crit_pat,
                f"\\g<1>{target_rd:.1f}m (originally {base_rd:.1f} m in the source environment)",
                criteria,
                count=1,
            )
    base_rzx0 = float(base_terrain_config.get("rendezvous_zone_x_min", DEFAULT_RENDEZVOUS_ZONE_X_MIN))
    base_rzx1 = float(base_terrain_config.get("rendezvous_zone_x_max", DEFAULT_RENDEZVOUS_ZONE_X_MAX))
    target_rzx0 = float(target_terrain_config.get("rendezvous_zone_x_min", base_rzx0))
    target_rzx1 = float(target_terrain_config.get("rendezvous_zone_x_max", base_rzx1))
    if abs(target_rzx0 - base_rzx0) > 1e-9 or abs(target_rzx1 - base_rzx1) > 1e-9:
        rzx_crit_pat = (
            r"seeker x ∈ \[" + r"(\d+\.\d+)" + r", " + r"(\d+\.\d+)" + r"\] m"
        )
        if re.search(rzx_crit_pat, criteria):
            criteria = re.sub(
                rzx_crit_pat,
                f"seeker x ∈ [{target_rzx0:.1f}, {target_rzx1:.1f}] m (originally [{base_rzx0:.1f}, {base_rzx1:.1f}] m in the source environment)",
                criteria,
                count=1,
            )
    base_ht = float(
        base_terrain_config.get("rendezvous_heading_tolerance_deg", DEFAULT_HEADING_TOLERANCE_DEG)
    )
    target_ht = float(
        target_terrain_config.get("rendezvous_heading_tolerance_deg", base_ht)
    )
    if abs(target_ht - base_ht) > 1e-9:
        ht_pat = (
            r"(heading within )" + r"(\d+\.\d+)" + r"(° of target velocity direction)"
        )
        if re.search(ht_pat, criteria):
            criteria = re.sub(
                ht_pat,
                f"\\g<1>{target_ht:.1f}\\g<3> (originally {base_ht:.1f}\\g<3> in the source environment)",
                criteria,
                count=1,
            )
    base_cth_sc = float(base_terrain_config.get("cooldown_threshold", DEFAULT_COOLDOWN_THRESHOLD))
    base_cmt_sc = float(base_terrain_config.get("cooldown_max_thrust", DEFAULT_COOLDOWN_MAX_THRUST))
    base_csteps_sc = int(base_terrain_config.get("cooldown_steps", DEFAULT_COOLDOWN_STEPS))
    target_cth_sc = float(target_terrain_config.get("cooldown_threshold", base_cth_sc))
    target_cmt_sc = float(target_terrain_config.get("cooldown_max_thrust", base_cmt_sc))
    target_csteps_sc = int(target_terrain_config.get("cooldown_steps", base_csteps_sc))
    if (target_cth_sc, target_cmt_sc, target_csteps_sc) != (base_cth_sc, base_cmt_sc, base_csteps_sc):
        cool_sc_pat = re.compile(
            r"(Exceeding )" + _PROMPT_SCALAR + r"( N thrust triggers cooldown; max thrust reduced to )" + _PROMPT_SCALAR + r"( N for )(\d+)( steps\.)",
            re.DOTALL,
        )
        m2 = cool_sc_pat.search(criteria)
        if m2:
            thr_exceeds = f"{target_cth_sc:.0f}"
            if abs(target_cth_sc - base_cth_sc) > 1e-9:
                thr_exceeds += f" (originally {base_cth_sc:.0f} N in the source environment)"
            steps_disp = str(target_csteps_sc)
            if target_csteps_sc != base_csteps_sc:
                steps_disp += f" (originally {base_csteps_sc} in the source environment)"
            thr_reduced = f"{target_cmt_sc:.0f}"
            if abs(target_cmt_sc - base_cmt_sc) > 1e-9:
                thr_reduced += f" (originally {base_cmt_sc:.0f} N in the source environment)"
            replacement = (
                f"Exceeding {thr_exceeds} N thrust triggers cooldown; "
                f"max thrust reduced to {thr_reduced} N for {steps_disp} steps."
            )
            criteria = re.sub(cool_sc_pat, replacement, criteria, count=1)
    t_s1 = target_terrain_config.get("slots_phase1", DEFAULT_SLOTS_PHASE1)
    t_s2 = target_terrain_config.get("slots_phase2", DEFAULT_SLOTS_PHASE2)
    b_s1 = base_terrain_config.get("slots_phase1", DEFAULT_SLOTS_PHASE1)
    b_s2 = base_terrain_config.get("slots_phase2", DEFAULT_SLOTS_PHASE2)
    if t_s1 != b_s1 or t_s2 != b_s2:
        t_lo1, t_hi1, t_lo2, t_hi2 = _slot_window_bounds(t_s1, t_s2)
        b_lo1, b_hi1, b_lo2, b_hi2 = _slot_window_bounds(b_s1, b_s2)
        window_pat = r'(?!)'
        if re.search(window_pat, criteria):
            criteria = re.sub(
                window_pat,
                f"\\g<1>[{t_lo1}, {t_hi1}] and [{t_lo2}, {t_hi2}] steps (originally [{b_lo1}, {b_hi1}] and [{b_lo2}, {b_hi2}] steps in the source environment)\\g<2>",
                criteria,
                count=1,
            )
    return criteria

UNIFORM_SUFFIX = """

Sensors indicate that this region exhibits non-standard physical properties.
While the following variables **MIGHT** have changed from the initial environment, **NOT ALL** of them will necessarily be mutated in any given task. You must use active interaction and environmental feedback to deduce which specific conditions apply:
 - **Effective acceleration field** may differ.
 - **Linear and angular damping** may differ.
 - **Impulse budget** may differ.
 - **Post-rendezvous track-distance requirement** may differ.
 - **Rendezvous distance requirement** may differ.
 - **Rendezvous relative-speed requirement** may differ.
 - **Rendezvous heading tolerance** may differ.
 - **Rendezvous time windows and slot bands** may differ.
 - **Static obstacle layout** may differ.
 - **Moving obstacle configuration** may differ.
 - **Seeker spawn position** may differ.
 - **Surface interaction (ground friction and low-friction patches)** may differ.
 - **Maximum thrust capability** may differ.
 - **Thrust cooldown regime** may differ.
 - **Sensor blind-zone boundaries** may differ.
 - **Target motion dynamics** may differ.
**Discovery via feedback**: Your objective is to identify the underlying physical rules of this specific environment through trial and reasoning. Initial standard solutions may fail; analyze failure modes to infer the hidden constraints and adapt your design.
"""

def get_c03_curriculum_stages() -> List[Dict[str, Any]]:
    return [
        {
            "stage_id": "Stage-1",
            "title": "Sonic Storm",
            "mutation_description": "Curriculum variant: extreme fuel scarcity — impulse budget reduced to near-breaking minimum.",
            "task_description_suffix": UNIFORM_SUFFIX,
            "terrain_config": {
                "impulse_budget": 5000.0,
            },
            "physics_config": {},
        },
        {
            "stage_id": "Stage-2",
            "title": "Hurricane Void",
            "mutation_description": "Curriculum variant: extreme sideways gravity (near cooldown limit) with zero ground friction, shifted spawn, no obstacles or ice.",
            "task_description_suffix": UNIFORM_SUFFIX,
            "terrain_config": {
                "ground_friction": 0.0,
                "impulse_budget": 40000.0,
                "spawn_x": 14.0,
                "obstacles": [],
                "ice_zones": [],
            },
            "physics_config": {
                "gravity": (-3.5, 0.0),
            },
        },
        {
            "stage_id": "Stage-3",
            "title": "Submerged Abyss",
            "mutation_description": "Curriculum variant: high linear damping (1.4, DAMP=28 Ns/m) with 1.5 angular damping, strong leftward gravity (-3.5,-9.5 m/s^2), near-zero ground friction (0.02), blind zone [12.5-17.0], tight rendezvous (rel-speed 2.0 m/s, heading 120deg), high cooldown (190 N trigger, 18 N recovery for 100 steps), wide slot windows (180 steps each), fast erratic target (2.0 m/s, 0.7 s interval), constrained impulse budget (20000 Ns), tight track distance (10.5 m). No ice patches or moving obstacles.",
            "task_description_suffix": UNIFORM_SUFFIX,
            "terrain_config": {
                "ground_friction": 0.02,
                "impulse_budget": 20000.0,
                "rendezvous_rel_speed": 2.0,
                "rendezvous_heading_tolerance_deg": 120.0,
                "max_thrust_magnitude": 200.0,
                "cooldown_threshold": 190.0,
                "cooldown_max_thrust": 18.0,
                "cooldown_steps": 100,
                "blind_zone_x_min": 12.5,
                "blind_zone_x_max": 17.0,
                "speed_blind_threshold_mps": 4.0,
                "track_distance": 10.5,
                "target_speed": 2.0,
                "target_change_interval": 0.7,
                "slots_phase1": [[3700, 3880], [4200, 4380]],
                "slots_phase2": [[6200, 6380], [6700, 6880]],
                "spawn_x": 11.0,
                "spawn_y": 1.55,
                "ice_zones": [],
                "moving_obstacle": None,
                "moving_obstacle_2": None,
                "obstacles": [(7.5, 1.3, 0.3, 0.3), (20.5, 1.3, 0.3, 0.3)],
            },
            "physics_config": {
                "linear_damping": 1.4,
                "angular_damping": 1.5,
                "gravity": (-3.5, -9.5),
            },
        },
        {
            "stage_id": "Stage-4",
            "title": "Molasses Prison",
            "mutation_description": "Curriculum variant: extreme multi-variable escalation — ultra-high damping (2.5/3.5, DAMP=50 Ns/m), near-zero friction (0.01), punishing cooldown (65N trigger → 10N for 250 steps), tight rendezvous (3.5m distance, 1.0m/s rel-speed, 30° heading), erratic target (1.0m/s, 0.7s interval), blind zone [15.0-17.5] with 1.2m/s speed-blind, narrow slot windows, tight fuel (12000 N·s), tight track (9.2m), shifted spawn (14.0,1.45), no obstacles/ice/moving.",
            "task_description_suffix": UNIFORM_SUFFIX,
            "terrain_config": {
                "impulse_budget": 12000.0,
                "ground_friction": 0.01,
                "cooldown_threshold": 65.0,
                "cooldown_max_thrust": 10.0,
                "cooldown_steps": 250,
                "rendezvous_distance": 3.5,
                "rendezvous_rel_speed": 1.0,
                "rendezvous_heading_tolerance_deg": 30.0,
                "track_distance": 9.2,
                "target_speed": 1.0,
                "target_change_interval": 0.7,
                "blind_zone_x_min": 15.0,
                "blind_zone_x_max": 17.5,
                "speed_blind_threshold_mps": 1.2,
                "slots_phase1": [[3650, 3880], [4150, 4410]],
                "slots_phase2": [[6150, 6380], [6650, 6910]],
                "spawn_x": 14.0,
                "spawn_y": 1.45,
                "obstacles": [],
                "ice_zones": [],
                "moving_obstacle": None,
                "moving_obstacle_2": None,
            },
            "physics_config": {
                "linear_damping": 2.5,
                "angular_damping": 3.5,
                "gravity": (0.0, -10.0),
            },
        },
    ]
