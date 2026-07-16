import math

from typing import Dict, Any, List

def _sfmt(value, decimals=3):
    if value is None:
        return "N/A"
    try:
        v = float(value)
        if not math.isfinite(v):
            return str(v)
        return f"{v:.{decimals}f}"
    except (TypeError, ValueError):
        return str(value)

def _safe_float(value, default=0.0):
    if value is None:
        return default
    try:
        v = float(value)
        if not math.isfinite(v):
            return default
        return v
    except (TypeError, ValueError):
        return default

def _section_constraint_violations(metrics: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    violations = metrics.get("constraint_violations")
    if not violations or not isinstance(violations, list):
        return out
    out.append("### 0. Design Constraint Violations (step 0)")
    for v in violations:
        out.append(f"- {v}")
    return out

def _section_constraint_profile(metrics: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    out.append("### 1. Constraints")
    entries: List[str] = []
    in_hopper = _safe_float(metrics.get("particles_in_truck"))
    target = _safe_float(metrics.get("min_particles_in_hopper"))
    if target > 0:
        pct_in = 100.0 * in_hopper / target if target > 0 else 0.0
        shortfall = max(0.0, target - in_hopper)
        status = "PASS" if in_hopper >= target else "FAIL"
        entries.append(
            f"- **Particles in hopper**: {_sfmt(in_hopper, 0)} / {_sfmt(target, 0)} "
            f"({pct_in:.0f}% of target, shortfall {_sfmt(shortfall, 0)}) — **{status}**"
        )
    mass = _safe_float(metrics.get("structure_mass"))
    mass_lim = _safe_float(metrics.get("max_structure_mass"))
    if mass_lim > 0:
        margin_kg = mass_lim - mass
        pct_mass = 100.0 * mass / mass_lim
        status = "PASS" if margin_kg >= 0 else "FAIL"
        if margin_kg < 0 or pct_mass > 50:
            tier = "EXCEEDED" if margin_kg < 0 else f"elevated"
            entries.append(
                f"- **Mass**: {_sfmt(mass)} / {_sfmt(mass_lim)} kg "
                f"({pct_mass:.0f}%) — **{status}** [{tier}]"
            )
        else:
            entries.append(
                f"- **Mass**: {_sfmt(mass)} / {_sfmt(mass_lim)} kg "
                f"({pct_mass:.0f}%) — **{status}**"
            )
    sc = _safe_float(metrics.get("step_count"))
    max_steps = _safe_float(metrics.get("max_steps"))
    max_time = _safe_float(metrics.get("max_time_seconds"))
    if max_steps > 0 and max_time > 0:
        elapsed = sc / max_steps * max_time
        pct_time = 100.0 * sc / max_steps
        remaining = max_time - elapsed
        status = "EXHAUSTED" if remaining <= 0 else "PASS"
        entries.append(
            f"- **Time**: {_sfmt(elapsed, 1)} / {_sfmt(max_time, 0)} s "
            f"({pct_time:.0f}% used, {_sfmt(remaining, 1)} s left) — **{status}**"
        )
    broken = metrics.get("structure_broken", False)
    jc = metrics.get("joint_count")
    if broken:
        entries.append(f"- **Structure**: BROKEN" + (f", {jc} joint(s) left" if jc is not None else ""))
    else:
        entries.append("- **Structure**: intact")
    bx_min = _safe_float(metrics.get("build_zone_x_min"), -4.0)
    bx_max = _safe_float(metrics.get("build_zone_x_max"), 2.0)
    by_min = _safe_float(metrics.get("build_zone_y_min"), 0.0)
    by_max = _safe_float(metrics.get("build_zone_y_max"), 5.0)
    entries.append(
        f"- **Build zone**: x=[{_sfmt(bx_min)}, {_sfmt(bx_max)}], "
        f"y=[{_sfmt(by_min)}, {_sfmt(by_max)}]"
    )
    scoop_cap = _safe_float(metrics.get("scoop_capacity"))
    if scoop_cap > 0 and scoop_cap < 999:
        entries.append(f"- **Scoop capacity**: {_sfmt(scoop_cap, 0)} particles/trip")
    drift = _safe_float(metrics.get("pit_drift_force"))
    if drift > 0:
        entries.append(f"- **Pit drift**: {_sfmt(drift, 2)} N per particle")
    out.extend(entries)
    return out

def _section_spatial_diagnostics(metrics: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    out.append("### 2. Spatial")
    entries: List[str] = []
    pit = metrics.get("pit_bounds", {})
    hop_valid = metrics.get("hopper_valid_bounds", {})
    ax = metrics.get("agent_x")
    ay = metrics.get("agent_y")
    if ax is not None and ay is not None:
        ax_f = _safe_float(ax)
        ay_f = _safe_float(ay)
        if hop_valid:
            hvx_min = _safe_float(hop_valid.get("x_min"))
            hvx_max = _safe_float(hop_valid.get("x_max"))
            hvy_min = _safe_float(hop_valid.get("y_min"))
            hvy_max = _safe_float(hop_valid.get("y_max"))
            in_hx = hvx_min <= ax_f <= hvx_max
            in_hy = hvy_min <= ay_f <= hvy_max
            if in_hx and in_hy:
                dist_str = "AT hopper"
            else:
                dx_h = _sfmt(ax_f - hvx_max if ax_f > hvx_max else hvx_min - ax_f if ax_f < hvx_min else 0.0)
                dy_h = _sfmt(ay_f - hvy_max if ay_f > hvy_max else hvy_min - ay_f if ay_f < hvy_min else 0.0)
                dist_str = f"to hopper: dx={dx_h}, dy={dy_h} m"
            if pit:
                px_min = _safe_float(pit.get("x_min"))
                px_max = _safe_float(pit.get("x_max"))
                py_min = _safe_float(pit.get("y_min"))
                py_max = _safe_float(pit.get("y_max"))
                in_pit = (px_min <= ax_f <= px_max and py_min <= ay_f <= py_max)
                pit_str = " (in pit)" if in_pit else ""
            else:
                pit_str = ""
            entries.append(
                f"- **Bucket**: ({_sfmt(ax_f)}, {_sfmt(ay_f)}) m — {dist_str}{pit_str}"
            )
    sx_min = metrics.get("scoop_traj_x_min")
    sx_max = metrics.get("scoop_traj_x_max")
    sy_min = metrics.get("scoop_traj_y_min")
    sy_max = metrics.get("scoop_traj_y_max")
    if any(v is not None for v in (sx_min, sx_max, sy_min, sy_max)):
        parts = [f"x=[{_sfmt(sx_min)}, {_sfmt(sx_max)}]"]
        if sy_min is not None and sy_max is not None:
            parts.append(f"y=[{_sfmt(sy_min)}, {_sfmt(sy_max)}]")
        reached_hopper = False
        if hop_valid and sx_min is not None and sx_max is not None:
            hx_min = _safe_float(hop_valid.get("x_min"))
            hx_max = _safe_float(hop_valid.get("x_max"))
            hy_min = _safe_float(hop_valid.get("y_min"))
            hy_max = _safe_float(hop_valid.get("y_max"))
            if sx_max >= hx_min and sx_min <= hx_max:
                sy_lo = sy_min if sy_min is not None else float('-inf')
                sy_hi = sy_max if sy_max is not None else float('inf')
                if sy_hi >= hy_min and sy_lo <= hy_max:
                    reached_hopper = True
        hopper_note = ", reached hopper" if reached_hopper else ""
        entries.append(f"- **Scoop envelope**: {', '.join(parts)} m{hopper_note}")
    arm_x = metrics.get("arm_x")
    arm_y = metrics.get("arm_y")
    arm_ang = _safe_float(metrics.get("arm_joint_angle_rad"))
    if arm_x is not None and arm_y is not None:
        entries.append(
            f"- **Arm**: ({_sfmt(arm_x, 2)}, {_sfmt(arm_y, 2)}) m, "
            f"angle={_sfmt(arm_ang, 3)} rad ({_sfmt(arm_ang * 180.0 / math.pi, 1)} deg)"
        )
    out.extend(entries)
    return out

def _section_particle_chronology(metrics: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    out.append("### 3. Particles")
    entries: List[str] = []
    initial = _safe_float(metrics.get("initial_particle_count"))
    in_pit = metrics.get("particles_in_pit")
    escaped = metrics.get("particles_escaped")
    if any(v is not None for v in (in_pit, escaped)):
        bits = []
        if in_pit is not None:
            pct_pit = 100.0 * _safe_float(in_pit) / initial if initial > 0 else 0.0
            bits.append(f"pit: {_sfmt(in_pit, 0)}/{_sfmt(initial, 0)} ({pct_pit:.0f}%)")
        if escaped is not None:
            pct_esc = 100.0 * _safe_float(escaped) / initial if initial > 0 else 0.0
            bits.append(f"escaped: {_sfmt(escaped, 0)}/{_sfmt(initial, 0)} ({pct_esc:.0f}%)")
        entries.append(f"- Distribution: {', '.join(bits)}")
    carry_log = metrics.get("carry_log")
    if carry_log and isinstance(carry_log, list) and len(carry_log) > 0:
        carrying_entries = [c for c in carry_log if _safe_float(c.get("carried")) > 0]
        max_carried = max((_safe_float(c.get("carried")) for c in carrying_entries), default=0)
        dump_events = [c for c in carry_log
                       if c.get("over_hopper") and c.get("dumping")
                       and _safe_float(c.get("carried")) > 0]
        if max_carried > 0:
            line = f"- **Carry**: peak {_sfmt(max_carried, 0)} particles, {len(dump_events)} dump(s)"
            if len(carrying_entries) < len(carry_log):
                line += f" (captured in {len(carrying_entries)}/{len(carry_log)} frames)"
            entries.append(line)
        else:
            entries.append("- **Carry**: 0 particles picked up")
    break_events = metrics.get("joint_break_events")
    if break_events and isinstance(break_events, list) and len(break_events) > 0:
        entries.append(f"- **Joint breaks**: {len(break_events)}")
        for be in break_events:
            step = _safe_float(be.get("step"))
            force = _safe_float(be.get("force_N"))
            torque = _safe_float(be.get("torque_Nm"))
            lim_f = _safe_float(be.get("limit_force_N"))
            lim_t = _safe_float(be.get("limit_torque_Nm"))
            causes = []
            if force > lim_f:
                causes.append(f"force {_sfmt(force)} N > {_sfmt(lim_f)} N")
            if torque > lim_t:
                causes.append(f"torque {_sfmt(torque)} Nm > {_sfmt(lim_t)} Nm")
            cause_str = f" ({'; '.join(causes)})" if causes else ""
            entries.append(f"  step {_sfmt(step, 0)}{cause_str}")
    out.extend(entries)
    return out

def _section_load_distribution(metrics: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    entries: List[str] = []
    peak_force = _safe_float(metrics.get("peak_joint_force"))
    peak_torque = _safe_float(metrics.get("peak_joint_torque"))
    jfl = metrics.get("joint_max_force_limit")
    jtl = metrics.get("joint_max_torque_limit")
    force_limit = _safe_float(jfl) if jfl is not None else float("inf")
    torque_limit = _safe_float(jtl) if jtl is not None else float("inf")
    has_finite_limits = (math.isfinite(force_limit) and force_limit > 0) or \
                        (math.isfinite(torque_limit) and torque_limit > 0)
    if not has_finite_limits and peak_force <= 0 and peak_torque <= 0:
        return out
    out.append("### 4. Joint Loads")
    if not has_finite_limits:
        entries.append(
            f"- No finite limits set; peak force={_sfmt(peak_force)} N, "
            f"torque={_sfmt(peak_torque)} Nm"
        )
        out.extend(entries)
        return out
    if math.isfinite(force_limit) and force_limit > 0:
        pct_f = 100.0 * peak_force / force_limit
        flag = " **CRITICAL**" if pct_f > 80 else " elevated" if pct_f > 50 else ""
        entries.append(
            f"- **Force**: {_sfmt(peak_force)} / {_sfmt(force_limit)} N "
            f"({pct_f:.0f}%){flag}"
        )
    if math.isfinite(torque_limit) and torque_limit > 0:
        pct_t = 100.0 * peak_torque / torque_limit
        flag = " **CRITICAL**" if pct_t > 80 else " elevated" if pct_t > 50 else ""
        entries.append(
            f"- **Torque**: {_sfmt(peak_torque)} / {_sfmt(torque_limit)} Nm "
            f"({pct_t:.0f}%){flag}"
        )
    out.extend(entries)
    return out

def _section_numerical_health(metrics: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    entries: List[str] = []
    peak_speed = _safe_float(metrics.get("peak_body_speed"))
    max_ps = _safe_float(metrics.get("max_particle_speed"))
    peak_av = _safe_float(metrics.get("peak_angular_velocity"))
    nan_keys = []
    for key in ("agent_x", "agent_y", "velocity_x", "velocity_y",
                 "structure_mass", "particles_in_truck", "peak_joint_force",
                 "peak_joint_torque", "peak_body_speed"):
        v = metrics.get(key)
        if v is not None:
            try:
                fv = float(v)
                if not math.isfinite(fv):
                    nan_keys.append(key)
            except (TypeError, ValueError):
                nan_keys.append(key)
    has_anomaly = bool(nan_keys)
    has_motion = peak_speed > 0.01 or max_ps > 0.01 or peak_av > 0.01
    if not has_anomaly and not has_motion:
        return out
    out.append("### 5. Numerical Health")
    if has_anomaly:
        entries.append(f"- Non-finite: {', '.join(sorted(nan_keys))}")
    if has_motion:
        speed_parts = [f"body={_sfmt(peak_speed, 2)} m/s"]
        if max_ps > 0.01:
            speed_parts.append(f"particle={_sfmt(max_ps, 2)} m/s")
        if peak_av > 0.01:
            speed_parts.append(f"angular={_sfmt(peak_av, 2)} rad/s")
        entries.append(f"- Peak speeds: {', '.join(speed_parts)}")
    out.extend(entries)
    return out

def format_task_metrics(metrics: Dict[str, Any]) -> List[str]:
    parts: List[str] = []
    sec0 = _section_constraint_violations(metrics)
    if sec0:
        parts.extend(sec0)
        parts.append("")
    parts.extend(_section_constraint_profile(metrics))
    parts.append("")
    sec2 = _section_spatial_diagnostics(metrics)
    if len(sec2) > 1:
        parts.extend(sec2)
        parts.append("")
    sec3 = _section_particle_chronology(metrics)
    if len(sec3) > 1:
        parts.extend(sec3)
        parts.append("")
    sec4 = _section_load_distribution(metrics)
    if sec4:
        parts.extend(sec4)
        parts.append("")
    sec5 = _section_numerical_health(metrics)
    if sec5:
        parts.extend(sec5)
    return parts
