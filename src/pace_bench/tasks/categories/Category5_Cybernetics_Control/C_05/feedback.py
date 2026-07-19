from typing import Dict, Any, List, Optional

import math

def _is_finite(x: Any) -> bool:
    if x is None:
        return True
    try:
        return math.isfinite(float(x))
    except (TypeError, ValueError):
        return True

def _fval(metrics: Dict[str, Any], key: str, default: float = 0.0) -> float:
    v = metrics.get(key, default)
    try:
        return float(v)
    except (TypeError, ValueError):
        return float(default)

def _ival(metrics: Dict[str, Any], key: str, default: int = 0) -> int:
    v = metrics.get(key, default)
    try:
        return int(v)
    except (TypeError, ValueError):
        return int(default)

def _fmt_f(val: float, decimals: int = 3) -> str:
    if not _is_finite(val):
        return str(val)
    return f"{val:.{decimals}f}"

def _margin_str(value: float, limit: float, is_lower_better: bool = True) -> str:
    if not _is_finite(value) or not _is_finite(limit) or limit == 0:
        return f"{_fmt_f(value)} / {_fmt_f(limit)}"
    pct = value / limit * 100.0 if is_lower_better else (1.0 - value / max(limit, 0.001)) * 100.0
    return f"{_fmt_f(value)}/{_fmt_f(limit)} ({_fmt_f(pct, 1)}%)"

def _zone_distance(x: float, y: float, cx: float, cy: float, hw: float, hh: float) -> float:
    closest_x = min(max(x, cx - hw), cx + hw)
    closest_y = min(max(y, cy - hh), cy + hh)
    return math.hypot(x - closest_x, y - closest_y)

def _in_zone(x: float, y: float, cx: float, cy: float, hw: float, hh: float) -> bool:
    return (cx - hw <= x <= cx + hw) and (cy - hh <= y <= cy + hh)

def _build_chronology(metrics: Dict[str, Any]) -> List[str]:
    lines = ["### 1. Temporal Chronology", ""]
    step = _ival(metrics, "step_count")
    max_steps = _ival(metrics, "max_steps")
    triggered = metrics.get("triggered_switches", [])
    next_req = metrics.get("next_required")
    cooldown_rem = _ival(metrics, "cooldown_remaining")
    cooldown_total = _ival(metrics, "cooldown_total")
    if triggered:
        lines.append(f"Step {step}/{max_steps} | "
                     f"triggered({len(triggered)}/3): {'→'.join(triggered)} | "
                     f"next: {next_req or 'none'}")
    else:
        lines.append(f"Step {step}/{max_steps} | "
                     f"triggered: none | next: {next_req or 'A'}")
    if cooldown_rem > 0:
        lines.append(f"Cooldown: {cooldown_rem}/{cooldown_total} steps remaining "
                     f"({'blocking' if cooldown_rem > 0 else 'ready'})")
    steps_since_A = _ival(metrics, "steps_since_last_A")
    steps_since_B = _ival(metrics, "steps_since_last_B")
    window_AB = _ival(metrics, "temporal_window_A_to_B")
    window_BC = _ival(metrics, "temporal_window_B_to_C")
    A_visited = metrics.get("A_visited", steps_since_A >= 0)
    B_visited = metrics.get("B_visited", steps_since_B >= 0)
    window_parts = []
    if window_AB > 0:
        if not A_visited:
            window_parts.append(f"A→B: not started ({window_AB} steps)")
        elif steps_since_A > window_AB:
            window_parts.append(f"A→B: EXPIRED ({steps_since_A}/{window_AB})")
        else:
            window_parts.append(f"A→B: {steps_since_A}/{window_AB} "
                               f"({window_AB - steps_since_A} remain)")
    if window_BC > 0:
        if not B_visited:
            window_parts.append(f"B→C: not started ({window_BC} steps)")
        elif steps_since_B > window_BC:
            window_parts.append(f"B→C: EXPIRED ({steps_since_B}/{window_BC})")
        else:
            window_parts.append(f"B→C: {steps_since_B}/{window_BC} "
                               f"({window_BC - steps_since_B} remain)")
    if window_parts:
        lines.append("Windows: " + " | ".join(window_parts))
    barrier_active = metrics.get("barrier_active", False)
    barrier_steps = _ival(metrics, "barrier_steps_until_open")
    barrier_delay = _ival(metrics, "barrier_delay_steps")
    if barrier_active:
        lines.append(f"Barrier: ACTIVE ({barrier_steps} steps until open, delay={barrier_delay})")
    else:
        if "A" in triggered:
            lines.append(f"Barrier: REMOVED (opened after {barrier_delay} step delay)")
        else:
            lines.append(f"Barrier: ACTIVE (opens {barrier_delay} steps after A)")
    reset_zone = _ival(metrics, "dwell_reset_zone_change")
    reset_speed = _ival(metrics, "dwell_reset_speed")
    reset_force = _ival(metrics, "dwell_reset_force")
    block_temp = _ival(metrics, "dwell_blocked_temporal")
    block_alt = _ival(metrics, "dwell_blocked_altitude")
    block_cool = _ival(metrics, "dwell_blocked_cooldown")
    total_resets = reset_zone + reset_speed + reset_force
    total_blocks = block_temp + block_alt + block_cool
    if total_resets > 0 or total_blocks > 0:
        reset_parts = []
        if reset_zone > 0:
            reset_parts.append(f"zone-exit({reset_zone})")
        if reset_speed > 0:
            reset_parts.append(f"speed-cap({reset_speed})")
        if reset_force > 0:
            reset_parts.append(f"force-limit({reset_force})")
        block_parts = []
        if block_temp > 0:
            block_parts.append(f"temporal({block_temp})")
        if block_alt > 0:
            block_parts.append(f"altitude({block_alt})")
        if block_cool > 0:
            block_parts.append(f"cooldown({block_cool})")
        dwell_line = f"Dwell: {total_resets} resets"
        if reset_parts:
            dwell_line += f" [{', '.join(reset_parts)}]"
        if total_blocks > 0:
            dwell_line += f" | {total_blocks} blocked"
            if block_parts:
                dwell_line += f" [{', '.join(block_parts)}]"
        lines.append(dwell_line)
    lines.append("")
    return lines

def _build_spatial(metrics: Dict[str, Any]) -> List[str]:
    lines = ["### 2. Spatial", ""]
    x = _fval(metrics, "agent_x")
    y = _fval(metrics, "agent_y")
    vx = _fval(metrics, "agent_vx")
    vy = _fval(metrics, "agent_vy")
    speed = _fval(metrics, "speed")
    lines.append(f"Pos: ({_fmt_f(x)}, {_fmt_f(y)}) m | "
                 f"Vel: ({_fmt_f(vx)}, {_fmt_f(vy)}) m/s | "
                 f"Speed: {_fmt_f(speed)} m/s")
    zones = metrics.get("zones", {})
    next_req = metrics.get("next_required")
    triggered_list = metrics.get("triggered_switches", [])
    if zones:
        zone_parts = []
        for node_name in ["A", "B", "C"]:
            if node_name in zones:
                cx, cy, hw, hh = zones[node_name]
                inside = _in_zone(x, y, cx, cy, hw, hh)
                dist = _zone_distance(x, y, cx, cy, hw, hh)
                is_triggered = node_name in triggered_list
                is_next = (node_name == next_req)
                flags = []
                if inside:
                    flags.append("IN")
                if is_triggered:
                    flags.append("TRIG")
                if is_next:
                    flags.append("NEXT")
                flag_str = f"[{','.join(flags)}]" if flags else ""
                zone_parts.append(f"{node_name}{flag_str}:d={_fmt_f(dist)}")
                if is_next and inside:
                    margin_left = x - (cx - hw)
                    margin_right = (cx + hw) - x
                    margin_bottom = y - (cy - hh)
                    margin_top = (cy + hh) - y
                    lines.append(f"  {node_name} margins: L+{_fmt_f(margin_left)} "
                                 f"R+{_fmt_f(margin_right)} "
                                 f"B+{_fmt_f(margin_bottom)} "
                                 f"T+{_fmt_f(margin_top)}")
        lines.append(f"Zones: {' | '.join(zone_parts)}")
    rmag = _fval(metrics, "repulsion_magnitude")
    if rmag > 0.01:
        rfx = _fval(metrics, "repulsion_fx")
        rfy = _fval(metrics, "repulsion_fy")
        rep_mag = _fval(metrics, "repulsion_mag")
        pct = rmag / max(rep_mag, 0.001) * 100.0
        severity = "CRITICAL" if pct >= 80 else ("ELEVATED" if pct >= 50 else "NOMINAL")
        lines.append(f"Repulsion: {_fmt_f(rmag)} N "
                     f"({_fmt_f(pct, 1)}% of peak {_fmt_f(rep_mag)} N) — {severity}")
    else:
        lines.append("Repulsion: none")
    lines.append("")
    return lines

def _build_constraints(metrics: Dict[str, Any]) -> List[str]:
    lines = ["### 3. Constraints & Control Load", ""]
    speed = _fval(metrics, "speed")
    speed_cap = _fval(metrics, "speed_cap_inside")
    force_mag = _fval(metrics, "applied_force_magnitude")
    force_limit = _fval(metrics, "force_limit_inside")
    max_force = _fval(metrics, "max_agent_force_per_axis")
    dwell_current = _ival(metrics, "steps_in_current_zone")
    dwell_required = _ival(metrics, "steps_required_to_trigger")
    cooldown_rem = _ival(metrics, "cooldown_remaining")
    cooldown_total = _ival(metrics, "cooldown_total")
    steps_since_A = _ival(metrics, "steps_since_last_A")
    steps_since_B = _ival(metrics, "steps_since_last_B")
    window_AB = _ival(metrics, "temporal_window_A_to_B")
    window_BC = _ival(metrics, "temporal_window_B_to_C")
    agent_y_max = _fval(metrics, "agent_y_max_recent")
    required_y = _fval(metrics, "required_max_y_c")
    inside_next = metrics.get("inside_next_required_zone", False)
    next_req = metrics.get("next_required")
    step = _ival(metrics, "step_count")
    max_steps = _ival(metrics, "max_steps")
    failures = []
    near_limits = []
    passes = []
    if speed_cap > 0:
        pct = speed / speed_cap * 100.0
        label = f"Speed: {_margin_str(speed, speed_cap)} m/s"
        if speed > speed_cap:
            failures.append(f"FAIL {label}")
        elif pct >= 50.0:
            near_limits.append(f"NEAR {label}")
        else:
            passes.append(f"OK   {label}")
    if force_limit > 0:
        pct = force_mag / force_limit * 100.0
        label = f"Force (in-zone): {_margin_str(force_mag, force_limit)} N"
        if force_mag > force_limit:
            failures.append(f"FAIL {label}")
        elif pct >= 50.0:
            near_limits.append(f"NEAR {label}")
    if inside_next or dwell_current > 0:
        pct = dwell_current / max(dwell_required, 1) * 100.0
        label = f"Dwell ({next_req or '?'}): {dwell_current}/{dwell_required} steps"
        if dwell_current >= dwell_required:
            passes.append(f"OK   {label}")
        elif pct >= 50.0:
            near_limits.append(f"NEAR {label}")
        else:
            failures.append(f"FAIL {label}")
    if cooldown_total > 0:
        if cooldown_rem > 0:
            failures.append(f"FAIL Cooldown: {cooldown_rem}/{cooldown_total} (blocking)")
    A_visited = metrics.get("A_visited", steps_since_A >= 0)
    if window_AB > 0 and A_visited:
        if steps_since_A > window_AB:
            failures.append(f"FAIL A→B window: {steps_since_A}/{window_AB} (EXPIRED)")
        elif steps_since_A > window_AB * 0.5:
            near_limits.append(f"NEAR A→B window: {steps_since_A}/{window_AB}")
    B_visited = metrics.get("B_visited", steps_since_B >= 0)
    if window_BC > 0 and B_visited:
        if steps_since_B > window_BC:
            failures.append(f"FAIL B→C window: {steps_since_B}/{window_BC} (EXPIRED)")
        elif steps_since_B > window_BC * 0.5:
            near_limits.append(f"NEAR B→C window: {steps_since_B}/{window_BC}")
    budget_remaining = max(0, max_steps - step)
    if budget_remaining < dwell_required * 2:
        failures.append(f"FAIL Budget: {budget_remaining}/{max_steps} steps remain "
                        f"(< {dwell_required * 2} needed)")
    if required_y > 0:
        label = f"C altitude: max_y={_fmt_f(agent_y_max)} m / need ≥{_fmt_f(required_y)} m"
        if agent_y_max >= required_y:
            passes.append(f"OK   {label}")
        elif agent_y_max >= required_y * 0.5:
            near_limits.append(f"NEAR {label}")
        else:
            failures.append(f"FAIL {label}")
    if max_force > 0:
        pct = force_mag / max_force * 100.0
        if pct >= 80.0:
            failures.append(f"FAIL Agent force: {_margin_str(force_mag, max_force)} N/axis ({_fmt_f(pct, 1)}%)")
        elif pct >= 50.0:
            near_limits.append(f"NEAR Agent force: {_margin_str(force_mag, max_force)} N/axis ({_fmt_f(pct, 1)}%)")
    if failures:
        for f in failures:
            lines.append(f)
    if near_limits:
        for nl in near_limits:
            lines.append(nl)
    if not failures and not near_limits:
        for p in passes:
            lines.append(p)
    if not failures and not near_limits and not passes:
        lines.append("All constraints: nominal")
    lines.append("")
    return lines

def _build_numerical_health(metrics: Dict[str, Any]) -> List[str]:
    lines = ["### 4. Numerical Health", ""]
    issues = []
    keys_to_check = [
        ("agent_x", "agent_x"), ("agent_y", "agent_y"),
        ("agent_vx", "agent_vx"), ("agent_vy", "agent_vy"),
        ("speed", "speed"),
        ("repulsion_fx", "repulsion_fx"), ("repulsion_fy", "repulsion_fy"),
        ("repulsion_magnitude", "repulsion_magnitude"),
        ("applied_force_x", "applied_force_x"), ("applied_force_y", "applied_force_y"),
        ("applied_force_magnitude", "applied_force_magnitude"),
    ]
    for label, key in keys_to_check:
        v = metrics.get(key)
        if v is None:
            continue
        try:
            fv = float(v)
            if math.isnan(fv):
                issues.append(f"NaN in {label}")
            elif math.isinf(fv):
                issues.append(f"Inf in {label}")
            elif abs(fv) > 1e6:
                issues.append(f"Extreme magnitude ({_fmt_f(fv, 1)}) in {label}")
        except (TypeError, ValueError):
            issues.append(f"Non-numeric {label}: {v}")
    speed = _fval(metrics, "speed")
    if speed > 100.0:
        issues.append(f"Runaway velocity: {_fmt_f(speed)} m/s")
    elif speed > 10.0:
        issues.append(f"Elevated velocity: {_fmt_f(speed)} m/s")
    if issues:
        for issue in issues:
            lines.append(f"  ⚠ {issue}")
    else:
        lines.append("  OK — all values finite and within normal ranges.")
    lines.append("")
    return lines

def _build_env_config(metrics: Dict[str, Any]) -> List[str]:
    lines = ["### 5. Config", ""]
    speed_cap = _fval(metrics, "speed_cap_inside")
    force_limit = _fval(metrics, "force_limit_inside")
    max_force = _fval(metrics, "max_agent_force_per_axis")
    dwell_req = _ival(metrics, "steps_required_to_trigger")
    cooldown_total = _ival(metrics, "cooldown_total")
    barrier_delay = _ival(metrics, "barrier_delay_steps")
    window_AB = _ival(metrics, "temporal_window_A_to_B")
    window_BC = _ival(metrics, "temporal_window_B_to_C")
    req_y = _fval(metrics, "required_max_y_c")
    rep_mag = _fval(metrics, "repulsion_mag")
    rep_range = _fval(metrics, "repulsion_range")
    tan_mag = _fval(metrics, "repulsion_tangential_mag")
    lines.append(f"  limits: speed≤{_fmt_f(speed_cap)} m/s | force≤{_fmt_f(force_limit)} N/zone "
                 f"| agent≤{_fmt_f(max_force)} N/axis | dwell={dwell_req} steps | "
                 f"cooldown={cooldown_total} steps")
    lines.append(f"  windows: A→B={window_AB} | B→C={window_BC} | "
                 f"barrier+{barrier_delay} | "
                 f"C-alt≥{_fmt_f(req_y)} m | "
                 f"repulsion={_fmt_f(rep_mag)} N r={_fmt_f(rep_range)} m "
                 f"tan={_fmt_f(tan_mag)} N")
    env_flags = []
    if metrics.get("env_flag_tight_a_to_b"):
        env_flags.append("TIGHT_A_TO_B")
    if metrics.get("env_flag_loose_a_to_b_recency"):
        env_flags.append("LOOSE_A_TO_B")
    if metrics.get("env_flag_long_barrier_delay"):
        env_flags.append("LONG_BARRIER_DELAY")
    if metrics.get("env_flag_strong_repulsion"):
        env_flags.append("STRONG_REPULSION")
    if metrics.get("env_flag_sensitive_trigger"):
        env_flags.append("SENSITIVE_TRIGGER")
    if env_flags:
        lines.append(f"  flags: {', '.join(env_flags)}")
    lines.append("")
    return lines

def format_task_metrics(metrics: Dict[str, Any]) -> List[str]:
    if not metrics:
        return ["**No metrics available**"]
    parts: List[str] = []
    nan_keys = []
    for key in ("agent_x", "agent_y", "agent_vx", "agent_vy", "speed"):
        v = metrics.get(key)
        if v is not None and not _is_finite(v):
            nan_keys.append(key)
    if nan_keys:
        parts.append(f"**Critical numerical anomaly**: non-finite values in: {', '.join(nan_keys)}")
        parts.append("  Remaining diagnostics may be unreliable.")
        parts.append("")
        return parts
    parts.extend(_build_chronology(metrics))
    parts.extend(_build_spatial(metrics))
    parts.extend(_build_constraints(metrics))
    parts.extend(_build_numerical_health(metrics))
    parts.extend(_build_env_config(metrics))
    return parts

def get_improvement_suggestions(
    metrics: Dict[str, Any],
    score: float,
    success: bool,
    failed: bool,
    failure_reason: str = None,
    error: str = None,

) -> List[str]:
    suggestions = []
    if error:
        suggestions.append("- Review the error details above to identify the specific issue")
        suggestions.append("- Ensure code follows the required function structure "
                          "(build_agent and optionally agent_action)")
    elif failed:
        suggestions.append("- Review the constraint profile to identify which sub-constraints "
                          "are preventing progress")
        suggestions.append("- Examine the temporal chronology to understand when and where "
                          "dwell resets or blocks occurred")
    else:
        suggestions.append("- Review the metrics above to identify areas for improvement")
    return suggestions
