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

def _fmt_f(val: Any, decimals: int = 3) -> str:
    if val is None:
        return "—"
    try:
        f = float(val)
        if not math.isfinite(f):
            return str(val)
        return f"{f:.{decimals}f}"
    except (TypeError, ValueError):
        return str(val)

def _fmt_deg(rad: Any) -> str:
    if rad is None:
        return "—"
    try:
        return f"{math.degrees(float(rad)):.1f}°"
    except (TypeError, ValueError):
        return str(rad)

def _build_numerical_health(metrics: Dict[str, Any]) -> List[str]:
    lines: List[str] = []
    issues: List[str] = []
    state_keys = [
        ("lander_x", "Lander x"),
        ("lander_y", "Lander y"),
        ("lander_vx", "Lander vx"),
        ("lander_vy", "Lander vy"),
        ("lander_angle", "Lander angle"),
        ("lander_angular_velocity", "Lander angular velocity"),
        ("height_above_ground", "Height above ground"),
        ("remaining_fuel", "Remaining fuel"),
    ]
    for key, label in state_keys:
        val = metrics.get(key)
        if val is not None and not _is_finite(val):
            issues.append(f"  - {label}: non-finite ({val})")
    ang_vel = _fval(metrics, "lander_angular_velocity")
    if math.isfinite(ang_vel) and abs(ang_vel) > 10.0:
        issues.append(
            f"  - |ω|={abs(ang_vel):.3f} rad/s ({math.degrees(abs(ang_vel)):.0f} deg/s) — extreme tumbling"
        )
    vx = _fval(metrics, "lander_vx")
    vy = _fval(metrics, "lander_vy")
    if math.isfinite(vx) and math.isfinite(vy):
        speed = math.hypot(vx, vy)
        if speed > 50.0:
            issues.append(f"  - |v|={speed:.2f} m/s — possibly divergent")
    max_vy = _fval(metrics, "max_safe_vertical_speed", 2.0)
    if math.isfinite(vy) and max_vy > 0 and abs(vy) > 3.0 * max_vy:
        issues.append(
            f"  - |vy|={abs(vy):.2f} m/s exceeds 3× safe limit ({max_vy:.2f})"
        )
    if issues:
        lines.append("⚠️ Issues:")
        lines.extend(issues)
    else:
        lines.append("✅ Finite")
    return lines

def _build_temporal_chronology(metrics: Dict[str, Any]) -> List[str]:
    lines: List[str] = []
    events: List[str] = []
    step = metrics.get("step_count")
    horizon = _fval(metrics, "episode_horizon")
    ct = metrics.get("corridor_transit") or {}
    if ct.get("entered") and ct.get("entry_step") is not None:
        es = ct["entry_step"]
        events.append(
            f"  Step {es}: entered corridor at x={_fmt_f(ct.get('entry_x'), 2)}, y={_fmt_f(ct.get('entry_y'), 2)} m"
        )
    if ct.get("violation_step") is not None:
        vs = ct["violation_step"]
        vk = ct.get("violation_kind", "unknown")
        kind_label = "obstacle (too low)" if vk == "obstacle" else (
            "ceiling (too high)" if vk == "ceiling" else str(vk)
        )
        events.append(
            f"  Step {vs}: BARRIER VIOLATION — {kind_label} at x={_fmt_f(ct.get('violation_x'), 2)}, y={_fmt_f(ct.get('violation_y'), 2)} m"
        )
    if ct.get("exit_step") is not None and ct.get("violation_step") is None:
        xs = ct["exit_step"]
        events.append(
            f"  Step {xs}: exited corridor at x={_fmt_f(ct.get('exit_x'), 2)}, y={_fmt_f(ct.get('exit_y'), 2)} m"
        )
        barrier_yt = _fval(metrics, "barrier_y_top")
        barrier_yb = _fval(metrics, "barrier_y_bottom")
        min_y = ct.get("min_y_in_corridor")
        max_y = ct.get("max_y_in_corridor")
        if min_y is not None and math.isfinite(float(min_y)):
            events.append(
                f"    Transit altitude range: y=[{_fmt_f(min_y, 2)}, {_fmt_f(max_y, 2) if max_y is not None else '—'}] m "
                f"(obstacle={_fmt_f(barrier_yt, 2)}, ceiling={_fmt_f(barrier_yb, 2)})"
            )
    remaining_fuel = metrics.get("remaining_fuel")
    if remaining_fuel is not None and _is_finite(remaining_fuel):
        if float(remaining_fuel) <= 0 and not metrics.get("landed"):
            events.append(f"  Step {step}: fuel exhausted")
    if metrics.get("landed"):
        ls = metrics.get("landing_step")
        lx = _fval(metrics, "landing_x")
        lvy = metrics.get("landing_vy")
        lang = metrics.get("landing_angle")
        events.append(
            f"  Step {ls}: TOUCHDOWN at x={_fmt_f(lx, 2)} m, "
            f"|vy|={_fmt_f(abs(float(lvy)) if lvy is not None else None, 3)} m/s, "
            f"angle={_fmt_deg(lang)}"
        )
    if (not metrics.get("landed") and horizon > 0
            and step is not None and step >= horizon):
        events.append(f"  Step {step}: episode step limit ({int(horizon)})")
    if events:
        lines.append("**Events** (ordered by step):")
        lines.extend(events)
    else:
        lines.append("**Events**: none recorded")
        if step is not None:
            pct_str = ""
            if horizon > 0:
                pct_str = f", {min(100.0, float(step) / horizon * 100.0):.1f}%"
            lines.append(f"  In progress: step {step}/{int(horizon)}{pct_str}")
    return lines

def _build_spatial_diagnostics(metrics: Dict[str, Any]) -> List[str]:
    lines: List[str] = []
    x = _fval(metrics, "lander_x")
    y = _fval(metrics, "lander_y")
    vx = _fval(metrics, "lander_vx")
    vy = _fval(metrics, "lander_vy")
    angle = _fval(metrics, "lander_angle")
    ang_vel = _fval(metrics, "lander_angular_velocity")
    h_above = _fval(metrics, "height_above_ground")
    speed = math.hypot(vx, vy) if (math.isfinite(vx) and math.isfinite(vy)) else 0.0
    lines.append(
        f"**Pos**: ({_fmt_f(x, 2)}, {_fmt_f(y, 2)}) m  |  "
        f"**v**: ({_fmt_f(vx, 2)}, {_fmt_f(vy, 2)}) m/s  |  "
        f"**|v|**: {_fmt_f(speed, 2)} m/s"
    )
    max_angle = _fval(metrics, "max_landing_angle", 0.1745)
    angle_deg = math.degrees(abs(angle)) if math.isfinite(angle) else 0.0
    limit_deg = math.degrees(max_angle) if max_angle > 0 else 0.0
    margin_deg = limit_deg - angle_deg
    ang_vel_deg_s = math.degrees(abs(ang_vel)) if math.isfinite(ang_vel) else 0.0
    lines.append(
        f"**|θ|**: {angle_deg:.1f}° (limit {limit_deg:.1f}°, margin {margin_deg:+.1f}°)  |  "
        f"**|ω|**: {abs(ang_vel):.3f} rad/s ({ang_vel_deg_s:.0f} deg/s)"
    )
    max_safe_vy = _fval(metrics, "max_safe_vertical_speed", 2.0)
    if max_safe_vy > 0:
        vy_margin = max_safe_vy - abs(vy)
        vy_status = "WITHIN" if vy_margin >= 0 else "EXCEEDS"
        lines.append(
            f"**Alt**: {_fmt_f(h_above, 2)} m above ground  |  "
            f"**|vy|**: {abs(vy):.3f} m/s — {vy_status} limit {max_safe_vy:.2f} m/s "
            f"(margin {vy_margin:+.3f})"
        )
    else:
        lines.append(f"**Alt**: {_fmt_f(h_above, 2)} m above ground  |  **|vy|**: {abs(vy):.3f} m/s")
    bl = _fval(metrics, "barrier_x_left")
    br = _fval(metrics, "barrier_x_right")
    bt = _fval(metrics, "barrier_y_top")
    bb = _fval(metrics, "barrier_y_bottom")
    if math.isfinite(x):
        if x < bl:
            lines.append(f"**Corridor**: {_fmt_f(bl - x, 2)} m to left edge (zone x=[{bl:.2f}, {br:.2f}])")
        elif x > br:
            lines.append(f"**Corridor**: {_fmt_f(x - br, 2)} m past right edge (zone x=[{bl:.2f}, {br:.2f}])")
        else:
            if math.isfinite(y):
                if y < bt:
                    lines.append(f"**Corridor**: x inside [{bl:.2f}, {br:.2f}] — y={_fmt_f(y, 2)} m BELOW obstacle ({_fmt_f(bt - y, 2)} m violation)")
                elif y > bb:
                    lines.append(f"**Corridor**: x inside [{bl:.2f}, {br:.2f}] — y={_fmt_f(y, 2)} m ABOVE ceiling ({_fmt_f(y - bb, 2)} m violation)")
                else:
                    margin_obs = y - bt
                    margin_ceil = bb - y
                    tighter = min(margin_obs, margin_ceil)
                    lines.append(
                        f"**Corridor**: x inside [{bl:.2f}, {br:.2f}] — y={_fmt_f(y, 2)} m "
                        f"(tightest margin: {_fmt_f(tighter, 2)} m)"
                    )
    zx_min = _fval(metrics, "zone_x_min")
    zx_max = _fval(metrics, "zone_x_max")
    z_width = zx_max - zx_min
    lx_lo = metrics.get("landing_x_lo")
    lx_hi = metrics.get("landing_x_hi")
    landing_x = _fval(metrics, "landing_x")
    if metrics.get("landed") and lx_lo is not None and lx_hi is not None and _is_finite(lx_lo) and _is_finite(lx_hi):
        flo, fhi = float(lx_lo), float(lx_hi)
        fw = fhi - flo
        margin_left = flo - zx_min
        margin_right = zx_max - fhi
        lines.append(
            f"**Landing zone**: x=[{zx_min:.2f}, {zx_max:.2f}] m (w={z_width:.2f})  |  "
            f"hull=[{flo:.2f}, {fhi:.2f}] m (w={fw:.2f})  |  "
            f"margins L={margin_left:+.2f} R={margin_right:+.2f}"
        )
    else:
        lines.append(f"**Landing zone**: x=[{zx_min:.2f}, {zx_max:.2f}] m (w={z_width:.2f})")
    remaining_fuel = metrics.get("remaining_fuel")
    if remaining_fuel is not None and _is_finite(remaining_fuel):
        rf = float(remaining_fuel)
        lines.append(f"**Fuel**: {rf:.3f} N·s remaining")
    td = metrics.get("thrust_delay_steps")
    if td is not None:
        dt = _fval(metrics, "time_step", 1.0 / 60.0)
        if dt > 0:
            delay_s = float(td) * dt
            lines.append(f"**Thrust delay**: {int(td)} steps ({delay_s:.3f} s)")
    return lines

def _build_constraint_profile(
    metrics: Dict[str, Any]

) -> List[str]:
    lines: List[str] = []
    profile = metrics.get("constraint_profile")
    if not isinstance(profile, list) or not profile:
        profile = _build_fallback_constraint_profile(metrics)
    if not profile:
        lines.append("**Constraint data**: unavailable.")
        return lines
    n_fail = sum(1 for c in profile if c.get("status") == "FAIL")
    n_pending = sum(1 for c in profile if c.get("status") == "PENDING")
    n_pass = sum(1 for c in profile if c.get("status") == "PASS")
    n_total = len(profile)
    parts_summary = [f"**{n_total} constraints**"]
    if n_fail:
        parts_summary.append(f"{n_fail} FAIL")
    if n_pending:
        parts_summary.append(f"{n_pending} PENDING")
    if n_pass:
        parts_summary.append(f"{n_pass} PASS")
    lines.append(" — ".join(parts_summary))
    near_limit = []
    for c in profile:
        if c.get("status") != "PASS":
            continue
        margin = c.get("margin")
        limit = c.get("limit")
        bound_type = c.get("bound_type", "upper")
        if margin is None or not isinstance(margin, (int, float)):
            continue
        is_near = False
        if bound_type == "upper" and isinstance(limit, (int, float)) and float(limit) > 0:
            is_near = float(margin) / float(limit) < 0.30
        elif bound_type == "lower" and isinstance(limit, (int, float)) and float(limit) > 0:
            is_near = float(margin) / float(limit) < 0.30
        elif bound_type == "boundary" and isinstance(limit, list) and len(limit) == 2:
            zone_size = abs(float(limit[1]) - float(limit[0]))
            if zone_size > 0:
                is_near = abs(float(margin)) < 0.30 * zone_size
        if is_near:
            near_limit.append(c)
    expanded_any = False
    for c in profile:
        if c.get("status") != "FAIL":
            continue
        name = c.get("name", "?")
        val = c.get("value")
        limit = c.get("limit")
        margin = c.get("margin")
        val_str = _fmt_constraint_val(val)
        limit_str = _fmt_constraint_limit(limit)
        margin_str = f", margin {margin:+.3f}" if isinstance(margin, (int, float)) else ""
        lines.append(f"  ❌ {name}: {val_str} (limit {limit_str}{margin_str})".rstrip())
        expanded_any = True
    for c in near_limit:
        name = c.get("name", "?")
        val = c.get("value")
        limit = c.get("limit")
        margin = c.get("margin")
        val_str = _fmt_constraint_val(val)
        limit_str = _fmt_constraint_limit(limit)
        pct = c.get("pct_of_limit")
        pct_str = f" ({pct:.0f}% of limit)" if pct is not None and math.isfinite(float(pct)) else ""
        margin_str = f", margin {margin:+.3f}" if isinstance(margin, (int, float)) else ""
        lines.append(f"  ⚠️ {name}: {val_str} (limit {limit_str}{margin_str}){pct_str}".rstrip())
        expanded_any = True
    if n_pending > 0 and not expanded_any:
        pending_names = [c["name"] for c in profile if c.get("status") == "PENDING"]
        lines.append("  ⏳ " + ", ".join(pending_names) + " — awaiting touchdown")
    if not expanded_any and n_pending == 0:
        lines.append("  ✅ All constraints satisfied")
    return lines

def _fmt_constraint_val(val: Any) -> str:
    if val is None:
        return "—"
    if isinstance(val, list):
        return f"[{_fmt_f(val[0], 2)},{_fmt_f(val[1], 2)}]"
    if isinstance(val, float):
        return _fmt_f(val, 3)
    return str(val)

def _fmt_constraint_limit(limit: Any) -> str:
    if limit is None:
        return "—"
    if isinstance(limit, list):
        return f"[{_fmt_f(limit[0], 2)},{_fmt_f(limit[1], 2)}]"
    if isinstance(limit, float):
        return _fmt_f(limit, 3)
    return str(limit)

def _build_fallback_constraint_profile(
    metrics: Dict[str, Any]

) -> List[Dict[str, Any]]:
    profile: List[Dict[str, Any]] = []
    max_vy = _fval(metrics, "max_safe_vertical_speed", 2.0)
    max_angle = _fval(metrics, "max_landing_angle", 0.1745)
    min_fuel = _fval(metrics, "min_fuel_remaining_at_landing", 450.0)
    horizon = _fval(metrics, "episode_horizon")
    step = metrics.get("step_count", 0)
    landing_vy = metrics.get("landing_vy")
    if metrics.get("landed") and landing_vy is not None and _is_finite(landing_vy):
        val = abs(float(landing_vy))
        margin = max_vy - val
        profile.append({
            "name": "Touchdown vertical speed",
            "status": "PASS" if margin >= 0 else "FAIL",
            "value": val, "limit": max_vy, "margin": margin,
            "pct_of_limit": val / max_vy * 100.0 if max_vy > 0 else 0.0,
            "bound_type": "upper",
        })
    elif not metrics.get("landed"):
        profile.append({
            "name": "Touchdown vertical speed",
            "status": "PENDING", "value": None, "limit": max_vy,
            "margin": None, "pct_of_limit": None,
            "bound_type": "upper",
        })
    lx_lo = metrics.get("landing_x_lo")
    lx_hi = metrics.get("landing_x_hi")
    zx_min = _fval(metrics, "zone_x_min")
    zx_max = _fval(metrics, "zone_x_max")
    if metrics.get("landed") and lx_lo is not None and lx_hi is not None:
        lo, hi = float(lx_lo), float(lx_hi)
        margin = min(lo - zx_min, zx_max - hi)
        profile.append({
            "name": "Hull in landing zone",
            "status": "PASS" if (lo >= zx_min and hi <= zx_max) else "FAIL",
            "value": [lo, hi], "limit": [zx_min, zx_max],
            "margin": margin, "pct_of_limit": None,
            "bound_type": "boundary",
        })
    elif not metrics.get("landed"):
        profile.append({
            "name": "Hull in landing zone",
            "status": "PENDING", "value": None,
            "limit": [zx_min, zx_max], "margin": None, "pct_of_limit": None,
            "bound_type": "boundary",
        })
    landing_angle = metrics.get("landing_angle")
    if metrics.get("landed") and landing_angle is not None and _is_finite(landing_angle):
        val = abs(float(landing_angle))
        margin = max_angle - val
        profile.append({
            "name": "Landing angle",
            "status": "PASS" if margin >= 0 else "FAIL",
            "value": val, "limit": max_angle, "margin": margin,
            "pct_of_limit": val / max_angle * 100.0 if max_angle > 0 else 0.0,
            "bound_type": "upper",
        })
    elif not metrics.get("landed"):
        profile.append({
            "name": "Landing angle",
            "status": "PENDING", "value": None, "limit": max_angle,
            "margin": None, "pct_of_limit": None,
            "bound_type": "upper",
        })
    remaining_fuel = metrics.get("remaining_fuel")
    if metrics.get("landed") and remaining_fuel is not None and _is_finite(remaining_fuel):
        val = float(remaining_fuel)
        margin = val - min_fuel
        profile.append({
            "name": "Fuel remaining at landing",
            "status": "PASS" if margin >= 0 else "FAIL",
            "value": val, "limit": min_fuel, "margin": margin,
            "pct_of_limit": val / min_fuel * 100.0 if min_fuel > 0 else 0.0,
            "bound_type": "lower",
        })
    elif not metrics.get("landed"):
        profile.append({
            "name": "Fuel remaining at landing",
            "status": "PENDING",
            "value": remaining_fuel, "limit": min_fuel,
            "margin": (float(remaining_fuel) - min_fuel) if remaining_fuel is not None and _is_finite(remaining_fuel) else None,
            "pct_of_limit": None,
            "bound_type": "lower",
        })
    fr = metrics.get("failure_reason") or ""
    barrier_hit = ("forbidden zone" in str(fr).lower() or
                   "obstacle" in str(fr).lower() or
                   "ceiling" in str(fr).lower())
    profile.append({
        "name": "No barrier violation",
        "status": "FAIL" if barrier_hit else "PASS",
        "value": None, "limit": "No contact with forbidden zone",
        "margin": None, "pct_of_limit": None,
        "bound_type": "boundary",
    })
    fuel_exhausted = (remaining_fuel is not None and _is_finite(remaining_fuel)
                      and float(remaining_fuel) <= 0 and not metrics.get("landed"))
    profile.append({
        "name": "Fuel not exhausted before landing",
        "status": "FAIL" if fuel_exhausted else "PASS",
        "value": remaining_fuel, "limit": ">0 N·s until touchdown",
        "margin": float(remaining_fuel) if remaining_fuel is not None and _is_finite(remaining_fuel) else None,
        "pct_of_limit": None,
        "bound_type": "lower",
    })
    if horizon > 0:
        margin_steps = horizon - int(step)
        at_limit = (not metrics.get("landed") and int(step) >= horizon)
        profile.append({
            "name": "Land within episode steps",
            "status": "FAIL" if at_limit else ("PASS" if metrics.get("landed") else "PENDING"),
            "value": int(step), "limit": int(horizon),
            "margin": margin_steps,
            "pct_of_limit": int(step) / horizon * 100.0 if horizon > 0 else 0.0,
            "bound_type": "upper",
        })
    status_order = {"FAIL": 0, "PENDING": 1, "PASS": 2}
    profile.sort(key=lambda c: (
        status_order.get(c.get("status", "PASS"), 3),
        -(c.get("margin") if isinstance(c.get("margin"), (int, float)) else 0.0)
    ))
    return profile

def _build_platform_timing(metrics: Dict[str, Any]) -> List[str]:
    lines: List[str] = []
    if not metrics.get("landed"):
        return lines
    landing_step = metrics.get("landing_step")
    landing_x = _fval(metrics, "landing_x")
    if landing_step is None:
        return lines
    dt = _fval(metrics, "time_step", 1.0 / 60.0)
    landing_t = float(landing_step) * dt if dt > 0 else 0.0
    plat_center = metrics.get("platform_center_at_landing")
    plat_zone = metrics.get("platform_zone_at_landing")
    timing_info = [f"t={landing_t:.3f} s (step {landing_step})"]
    if plat_center is not None and math.isfinite(float(plat_center)):
        pc = float(plat_center)
        offset = landing_x - pc if math.isfinite(landing_x) else 0.0
        timing_info.append(f"platform center x={pc:.2f} m, lander offset {offset:+.2f} m")
    if plat_zone and len(plat_zone) == 2:
        timing_info.append(f"zone at touchdown=[{plat_zone[0]:.2f}, {plat_zone[1]:.2f}] m")
    lines.append(f"**Touchdown**: {' | '.join(timing_info)}")
    return lines

def format_task_metrics(metrics: Dict[str, Any]) -> List[str]:
    parts: List[str] = []
    score = _fval(metrics, "score", 0.0)
    success = metrics.get("success", False)
    landed = metrics.get("landed", False)
    fr = metrics.get("failure_reason")
    step = metrics.get("step_count", 0)
    horizon = _fval(metrics, "episode_horizon")
    if success:
        parts.append("## C-02 Lander\n✅ **SUCCESS** (100.0/100)")
    elif fr:
        parts.append(f"## C-02 Lander\n❌ **FAILED** — {fr}")
    else:
        parts.append(
            f"## C-02 Lander\n❌ **FAILED** — "
            f"{'landed but failed constraints' if landed else 'did not land'}"
        )
    if horizon > 0:
        pct = min(100.0, float(step) / horizon * 100.0)
        parts.append(f"   Score: {_fmt_f(score, 1)}/100  |  step {step}/{int(horizon)} ({pct:.1f}%)")
    else:
        parts.append(f"   Score: {_fmt_f(score, 1)}/100  |  step {step}")
    parts.append("")
    parts.append("### 1. Numerical Health")
    parts.extend(_build_numerical_health(metrics))
    parts.append("")
    parts.append("### 2. Events")
    parts.extend(_build_temporal_chronology(metrics))
    parts.append("")
    parts.append("### 3. Spatial State")
    parts.extend(_build_spatial_diagnostics(metrics))
    parts.append("")
    parts.append("### 4. Constraints")
    parts.extend(_build_constraint_profile(metrics))
    if metrics.get("landed"):
        parts.append("")
        parts.append("### 5. Platform Arrival")
        timing_lines = _build_platform_timing(metrics)
        if timing_lines:
            parts.extend(timing_lines)
        else:
            parts.append("Timing data unavailable.")
    return parts

def get_improvement_suggestions(
    metrics: Dict[str, Any],
    score: float,
    success: bool,
    failed: bool,
    failure_reason: Optional[str] = None,
    error: Optional[str] = None,

) -> List[str]:
    suggestions: List[str] = []
    if error:
        error_lower = error.lower()
        if "prohibited" in error_lower:
            suggestions.append(
            )
        elif "syntax" in error_lower or "indentation" in error_lower:
            suggestions.append(
            )
        elif "name" in error_lower and ("not defined" in error_lower
                                         or "undefined" in error_lower):
            suggestions.append(
            )
        else:
            suggestions.append(
            )
        return suggestions
    if not failed and not success:
        return suggestions
    if not failed:
        return suggestions
    fr = (failure_reason or "").lower()
    if "forbidden zone" in fr or "obstacle" in fr or "ceiling" in fr:
        suggestions.append(
        )
    if "vertical speed" in fr or "|vy|" in fr:
        suggestions.append(
        )
    if "footprint" in fr or "hull" in fr or "not fully inside" in fr:
        suggestions.append(
        )
    if "angle" in fr and ("exceeds" in fr or "limit" in fr):
        suggestions.append(
        )
    if "fuel" in fr and ("exhausted" in fr or "remaining" in fr
                         or "minimum" in fr or "below" in fr):
        suggestions.append(
        )
    if "step limit" in fr or "episode" in fr:
        suggestions.append(
        )
    if not suggestions:
        suggestions.append(
        )
    return suggestions
