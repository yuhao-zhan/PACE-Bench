from typing import Dict, Any, List, Optional

import math

def _is_nonfinite(x: Any) -> bool:
    if x is None:
        return False
    try:
        return not math.isfinite(float(x))
    except (TypeError, ValueError):
        return False

def _safe_float(x: Any, default: float = 0.0) -> float:
    if x is None:
        return default
    try:
        v = float(x)
        return v if math.isfinite(v) else default
    except (TypeError, ValueError):
        return default

def _bullet(label: str, value: str) -> str:
    return f"- **{label}**: {value}"

def _section(title: str) -> str:
    return f"\n### {title}"

def _format_chronology(metrics: Dict[str, Any]) -> List[str]:
    parts: List[str] = []
    parts.append(_section("1. Temporal Event Chronology"))
    zone_events = metrics.get("zone_crossing_events") or []
    joint_failures = metrics.get("joint_failure_events") or []
    sink_traj = metrics.get("sink_trajectory") or []
    if not zone_events and not joint_failures and not sink_traj:
        parts.append("\n(No chronological event data recorded for this run.)")
        return parts
    if zone_events:
        parts.append("\n**Zone Crossings** (step order):")
        for ev in zone_events:
            step = ev.get("step", "?")
            zone = ev.get("zone", "unknown")
            fx = ev.get("front_x", "?")
            ly = ev.get("lowest_y", "?")
            fx_s = f"{float(fx):.2f}" if not _is_nonfinite(fx) else str(fx)
            ly_s = f"{float(ly):.2f}" if not _is_nonfinite(ly) else str(ly)
            parts.append(f"- Step {step}: {zone} (front_x={fx_s}, lowest_y={ly_s})")
    else:
        parts.append("\n- No zone crossings recorded.")
    if joint_failures:
        parts.append(f"\n**Joint Failures** ({len(joint_failures)}):")
        for jf in joint_failures:
            step = jf.get("step", "?")
            force = _safe_float(jf.get("reaction_force"))
            limit = _safe_float(jf.get("force_limit"), default=-1)
            ba = jf.get("body_a_idx", "?")
            bb = jf.get("body_b_idx", "?")
            pct = ""
            if limit > 0 and math.isfinite(limit):
                pct = f" ({force / limit * 100.0:.1f}% of {limit:.1f} N)"
            parts.append(f"- Step {step}: joint [{ba}–{bb}] → {force:.2f} N{pct}")
    if sink_traj:
        first = sink_traj[0]
        last = sink_traj[-1]
        first_y = _safe_float(first.get("lowest_y"))
        last_y = _safe_float(last.get("lowest_y"))
        first_step = first.get("step", 0)
        last_step = last.get("step", 0)
        delta_step = max(1, int(last_step) - int(first_step))
        rate = (last_y - first_y) / delta_step if delta_step > 0 else 0.0
        parts.append(
            f"\n**Sink Depth** ({len(sink_traj)} samples): "
            f"{first_y:.3f}m @ step {first_step} → {last_y:.3f}m @ step {last_step} "
            f"(rate={rate:+.4f} m/step)"
        )
        threshold = _safe_float(metrics.get("sink_y_threshold"), default=-0.5)
        for s in sink_traj:
            if _safe_float(s.get("lowest_y")) < threshold:
                sx = s.get("step", "?")
                sy = _safe_float(s.get("lowest_y"))
                sfx = s.get("front_x", "?")
                sfx_s = f"{float(sfx):.2f}" if not _is_nonfinite(sfx) else str(sfx)
                parts.append(
                    f"  ⚠️ Sank below y={threshold:.2f} at step {sx} "
                    f"(lowest_y={sy:.2f}, front_x={sfx_s})"
                )
                break
    return parts

def _format_spatial(metrics: Dict[str, Any]) -> List[str]:
    parts: List[str] = []
    parts.append(_section("2. Spatial Zone Position"))
    front_x = metrics.get("vehicle_front_x")
    lowest_y = metrics.get("vehicle_lowest_y")
    env_params = metrics.get("env_parameters") or {}
    fx = _safe_float(front_x) if front_x is not None else None
    ly = _safe_float(lowest_y) if lowest_y is not None else None
    if fx is None:
        parts.append("\n(No position data available.)")
        return parts
    lines: List[str] = []
    if fx < 10.0:
        lines.append(f"Water entry (x=10.0): {10.0 - fx:.1f}m ahead")
    elif fx > 24.0:
        lines.append(f"Past water exit (x=24.0) by {fx - 24.0:.1f}m")
    else:
        lines.append(f"In water zone [10.0–24.0]")
    dc = env_params.get("deep_channel_zone")
    if dc and len(dc) == 2:
        dc_l, dc_r = float(dc[0]), float(dc[1])
        if fx < dc_l:
            lines.append(f"Deep channel [{dc_l:.1f}–{dc_r:.1f}]: {dc_l - fx:.1f}m ahead")
        elif fx <= dc_r:
            lines.append(f"In deep channel [{dc_l:.1f}–{dc_r:.1f}] (reduced buoyancy ×{env_params.get('deep_channel_buoyancy_scale', 0.35):.2f})")
    emp = env_params.get("emp_zone")
    if emp and len(emp) == 2:
        emp_l, emp_r = float(emp[0]), float(emp[1])
        if fx < emp_l:
            lines.append(f"EMP [{emp_l:.1f}–{emp_r:.1f}]: {emp_l - fx:.1f}m ahead")
        elif fx <= emp_r:
            lines.append(f"In EMP [{emp_l:.1f}–{emp_r:.1f}] — thrust DISABLED")
        else:
            lines.append(f"Past EMP [{emp_l:.1f}–{emp_r:.1f}] — thrust restored")
    wp = env_params.get("whirlpool")
    if wp and isinstance(wp, dict):
        wx = float(wp.get("x", 17.0))
        ww = float(wp.get("width", 2.0))
        wf = float(wp.get("force", 100.0))
        wp_l = wx - ww / 2.0
        wp_r = wx + ww / 2.0
        if fx < wp_l:
            lines.append(f"Whirlpool [{wp_l:.1f}–{wp_r:.1f}, {wf:.0f}N/kg]: {wp_l - fx:.1f}m ahead")
        elif fx <= wp_r:
            lines.append(f"In whirlpool [{wp_l:.1f}–{wp_r:.1f}] — downward suction active")
    cy = env_params.get("corrosive_y")
    if cy is not None and math.isfinite(float(cy)) and ly is not None:
        cy = float(cy)
        if ly > cy:
            lines.append(f"In corrosive zone (y > {cy:.1f}) — crushing force active")
        else:
            lines.append(f"Below corrosive ceiling (y ≤ {cy:.1f}, margin={cy - ly:.2f}m)")
    water_y = _safe_float(env_params.get("water_surface_y"), default=2.0)
    if ly is not None:
        delta = ly - water_y
        lines.append(f"vs water surface (y={water_y:.1f}): {'above' if delta >= 0 else 'below'} by {abs(delta):.2f}m")
    if not lines:
        parts.append("\n(No zone data available.)")
    else:
        for line in lines:
            parts.append(f"- {line}")
    return parts

def _format_stress(metrics: Dict[str, Any]) -> List[str]:
    parts: List[str] = []
    parts.append(_section("3. Joint Load & Stress"))
    joint_failures = metrics.get("joint_failure_events") or []
    force_samples = metrics.get("joint_force_samples") or []
    env_params = metrics.get("env_parameters") or {}
    joint_limit = _safe_float(
        env_params.get("max_joint_force") if env_params else None,
        default=float("inf"),
    )
    if math.isfinite(joint_limit):
        parts.append(f"\n- Joint force limit: {joint_limit:.2f} N")
    else:
        parts.append("\n- Joint force limit: ∞ (no limit)")
    if joint_failures:
        ranked = sorted(joint_failures, key=lambda j: _safe_float(j.get("reaction_force")), reverse=True)
        parts.append(f"\n**Joint Failures** ({len(ranked)}):")
        for r in ranked:
            step = r.get("step", "?")
            force = _safe_float(r.get("reaction_force"))
            limit = _safe_float(r.get("force_limit"), default=-1)
            ba = r.get("body_a_idx", "?")
            bb = r.get("body_b_idx", "?")
            pct_s = ""
            if limit > 0 and math.isfinite(limit):
                pct_s = f" ({force / limit * 100.0:.1f}% of limit)"
            elif math.isfinite(joint_limit) and joint_limit > 0:
                pct_s = f" ({force / joint_limit * 100.0:.1f}% of global limit)"
            parts.append(f"- Step {step}: joint [{ba}–{bb}] → {force:.2f} N{pct_s}")
    if force_samples and math.isfinite(joint_limit) and joint_limit > 0:
        latest_by_joint: Dict[int, Dict] = {}
        for fs in force_samples:
            jidx = fs.get("joint_idx")
            if jidx is not None:
                latest_by_joint[int(jidx)] = fs
        if latest_by_joint:
            stressed = []
            for jidx in sorted(latest_by_joint.keys()):
                fs = latest_by_joint[jidx]
                force = _safe_float(fs.get("reaction_force"))
                pct = force / joint_limit * 100.0
                if pct >= 10.0:
                    ba = fs.get("body_a_idx", "?")
                    bb = fs.get("body_b_idx", "?")
                    stressed.append(
                        f"  Joint {jidx} [{ba}–{bb}]: {force:.2f} N ({pct:.1f}% of limit)"
                    )
            if stressed:
                parts.append(f"\n**Current Joint Stress** (>10% of limit={joint_limit:.1f} N):")
                parts.extend(stressed)
                low_count = len(latest_by_joint) - len(stressed)
                if low_count > 0:
                    parts.append(f"  ({low_count} other joints under 10% load — nominal)")
            else:
                parts.append(f"\nAll {len(latest_by_joint)} joints under 10% of limit — nominal.")
    return parts

def _format_energy(metrics: Dict[str, Any]) -> List[str]:
    parts: List[str] = []
    parts.append(_section("4. Forces"))
    force_decomp = metrics.get("force_decomposition")
    env_params = metrics.get("env_parameters") or {}
    if not isinstance(force_decomp, list) or not force_decomp:
        parts.append("\n(No force decomposition data available.)")
        return parts
    current = _safe_float(env_params.get("current_per_kg"), default=5.5)
    buoyancy = _safe_float(env_params.get("buoyancy_factor"), default=0.8)
    drag = _safe_float(env_params.get("water_drag_coef"), default=115.0)
    headwind = _safe_float(env_params.get("headwind_per_kg"), default=0.8)
    emp = env_params.get("emp_zone")
    cy = env_params.get("corrosive_y")
    wp = env_params.get("whirlpool")
    dc_scale = env_params.get("deep_channel_buoyancy_scale")
    env_items = [
        f"buoyancy ×{buoyancy:.2f}" + (f" (×{dc_scale:.2f} in deep channel)" if dc_scale else ""),
        f"current −{current:.1f} N/kg",
        f"drag −{drag:.1f}×speed²",
        f"wind (variable)",
        f"headwind −{headwind:.1f} N/kg @ x=[15,19]",
    ]
    if emp:
        env_items.append(f"EMP [{emp[0]:.1f}–{emp[1]:.1f}] — thrust disabled")
    if cy is not None and math.isfinite(float(cy)):
        env_items.append(f"corrosive y > {float(cy):.1f} → −2000 N/kg")
    if wp and isinstance(wp, dict):
        wx = float(wp.get("x", 17))
        ww = float(wp.get("width", 2))
        wf = float(wp.get("force", 100))
        env_items.append(f"whirlpool [{wx - ww/2:.1f}–{wx + ww/2:.1f}] −{wf:.0f} N/kg")
    parts.append(f"\n**Environment**: {' | '.join(env_items)}")
    total_buoyancy_y = 0.0
    total_current_x = 0.0
    total_drag_x = 0.0
    total_drag_y = 0.0
    total_wind_y = 0.0
    total_headwind_x = 0.0
    total_corrosive_y = 0.0
    total_whirlpool_y = 0.0
    bodies_in_water = 0
    bodies_in_emp = 0
    bodies_in_deep = 0
    non_trivial_bodies: List[Dict] = []
    for bd in force_decomp:
        if bd.get("in_water"):
            bodies_in_water += 1
        if bd.get("in_deep_channel"):
            bodies_in_deep += 1
        if bd.get("in_emp"):
            bodies_in_emp += 1
        forces = bd.get("forces") or {}
        has_non_gravity = False
        for fkey in ("buoyancy", "current", "drag", "wind", "headwind", "corrosive", "whirlpool"):
            fv = forces.get(fkey, (0, 0))
            fx_v = fv[0] if isinstance(fv, (list, tuple)) and len(fv) >= 2 else 0
            fy_v = fv[1] if isinstance(fv, (list, tuple)) and len(fv) >= 2 else 0
            if abs(fx_v) > 0.01 or abs(fy_v) > 0.01:
                has_non_gravity = True
            if fkey == "buoyancy":
                total_buoyancy_y += fy_v
            elif fkey == "current":
                total_current_x += fx_v
            elif fkey == "drag":
                total_drag_x += fx_v
                total_drag_y += fy_v
            elif fkey == "wind":
                total_wind_y += fy_v
            elif fkey == "headwind":
                total_headwind_x += fx_v
            elif fkey == "corrosive":
                total_corrosive_y += fy_v
            elif fkey == "whirlpool":
                total_whirlpool_y += fy_v
        if has_non_gravity:
            non_trivial_bodies.append(bd)
    net_all_y = total_buoyancy_y + total_drag_y + total_wind_y + total_corrosive_y + total_whirlpool_y
    net_all_x = total_current_x + total_drag_x + total_headwind_x
    agg_lines = [f"\n**Fleet Aggregate** ({len(force_decomp)} bodies):"]
    if bodies_in_water > 0:
        agg_lines.append(f"- In water: {bodies_in_water}/{len(force_decomp)}")
    if bodies_in_deep > 0:
        agg_lines.append(f"- In deep channel: {bodies_in_deep}")
    if bodies_in_emp > 0:
        agg_lines.append(f"- In EMP: {bodies_in_emp}")
    if abs(total_buoyancy_y) > 0.01:
        agg_lines.append(f"- ΣBuoyancy: ({0.0:+.1f}, {total_buoyancy_y:+.1f}) N")
    if abs(total_current_x) > 0.01:
        agg_lines.append(f"- ΣCurrent: ({total_current_x:+.1f}, {0.0:+.1f}) N")
    if abs(total_drag_x) > 0.01 or abs(total_drag_y) > 0.01:
        agg_lines.append(f"- ΣDrag: ({total_drag_x:+.1f}, {total_drag_y:+.1f}) N")
    if abs(total_wind_y) > 0.01:
        agg_lines.append(f"- ΣWind: ({0.0:+.1f}, {total_wind_y:+.1f}) N")
    if abs(total_headwind_x) > 0.01:
        agg_lines.append(f"- ΣHeadwind: ({total_headwind_x:+.1f}, {0.0:+.1f}) N")
    if abs(total_corrosive_y) > 0.01:
        agg_lines.append(f"- ΣCorrosive: ({0.0:+.1f}, {total_corrosive_y:+.1f}) N")
    if abs(total_whirlpool_y) > 0.01:
        agg_lines.append(f"- ΣWhirlpool: ({0.0:+.1f}, {total_whirlpool_y:+.1f}) N")
    agg_lines.append(f"- Net force: ({net_all_x:+.1f}, {net_all_y:+.1f}) N")
    if abs(net_all_y) > 0.01:
        agg_lines.append(f"  Vertical: {'BUOYANCY dominates (upward)' if net_all_y > 0 else 'DOWNWARD forces dominate'}")
    if abs(net_all_x) > 0.01:
        agg_lines.append(f"  Horizontal: {'FORWARD' if net_all_x > 0 else 'OPPOSING'} (net {'rightward' if net_all_x > 0 else 'leftward'})")
    parts.extend(agg_lines)
    trivial_count = len(force_decomp) - len(non_trivial_bodies)
    if non_trivial_bodies:
        show_n = min(6, len(non_trivial_bodies))
        parts.append(f"\n**Bodies with Active Forces** ({len(non_trivial_bodies)}/{len(force_decomp)}):")
        for bd in non_trivial_bodies[:show_n]:
            idx = bd.get("body_idx", "?")
            x = bd.get("x", 0)
            y = bd.get("y", 0)
            mass = _safe_float(bd.get("mass"))
            spd = _safe_float(bd.get("speed"))
            in_water = bd.get("in_water", False)
            in_dc = bd.get("in_deep_channel", False)
            in_emp = bd.get("in_emp", False)
            forces = bd.get("forces") or {}
            net = bd.get("net_force", (0, 0))
            tags = []
            if in_water:
                tags.append("submerged")
            if in_dc:
                tags.append("deep")
            if in_emp:
                tags.append("EMP")
            tag_s = f" [{', '.join(tags)}]" if tags else ""
            parts.append(f"\n  Body {idx} @ ({x:.2f}, {y:.2f}) m, mass={mass:.2f} kg, speed={spd:.3f} m/s{tag_s}")
            force_labels = [
                ("buoyancy", "Buoyancy"),
                ("current", "Current"), ("drag", "Drag"),
                ("wind", "Wind"), ("headwind", "Headwind"),
                ("corrosive", "Corrosive"), ("whirlpool", "Whirlpool"),
            ]
            for fkey, flabel in force_labels:
                fv = forces.get(fkey, (0, 0))
                fx_v = fv[0] if isinstance(fv, (list, tuple)) and len(fv) >= 2 else 0
                fy_v = fv[1] if isinstance(fv, (list, tuple)) and len(fv) >= 2 else 0
                if abs(fx_v) < 0.005 and abs(fy_v) < 0.005:
                    continue
                parts.append(f"    {flabel}: ({fx_v:+.1f}, {fy_v:+.1f}) N")
            net_x = net[0] if isinstance(net, (list, tuple)) and len(net) >= 2 else 0
            net_y = net[1] if isinstance(net, (list, tuple)) and len(net) >= 2 else 0
            parts.append(f"    → Net: ({net_x:+.1f}, {net_y:+.1f}) N")
        if len(non_trivial_bodies) > show_n:
            parts.append(f"\n  ... and {len(non_trivial_bodies) - show_n} more bodies with active forces.")
    if trivial_count > 0:
        parts.append(f"\n- {trivial_count}/{len(force_decomp)} bodies have no environmental forces active.")
    return parts

def _format_constraints(metrics: Dict[str, Any]) -> List[str]:
    parts: List[str] = []
    parts.append(_section("5. Constraints"))
    front_x = metrics.get("vehicle_front_x")
    lowest_y = metrics.get("vehicle_lowest_y")
    target_x = _safe_float(metrics.get("target_x"), default=26.0)
    sink_threshold = _safe_float(metrics.get("sink_y_threshold"), default=-0.5)
    mass = _safe_float(metrics.get("structure_mass"))
    max_mass = metrics.get("max_structure_mass")
    structure_broken = metrics.get("structure_broken", False)
    joint_count = metrics.get("joint_count")
    initial_joint_count = metrics.get("initial_joint_count")
    violations = metrics.get("constraint_violations")
    lines: List[str] = []
    failures: List[str] = []
    warnings: List[str] = []
    passes: List[str] = []
    if max_mass is not None:
        mm = _safe_float(max_mass)
        if mm > 0:
            pct = mass / mm * 100.0
            if mass > mm:
                failures.append(f"Mass: {mass:.1f}/{mm:.0f} kg OVER ({pct:.1f}% — FAIL)")
            elif pct > 70:
                warnings.append(f"Mass: {mass:.1f}/{mm:.0f} kg ({pct:.1f}% — near limit)")
            else:
                passes.append(f"Mass: {mass:.1f}/{mm:.0f} kg ({pct:.1f}%)")
    if violations and isinstance(violations, list) and violations:
        for v in violations:
            failures.append(f"Build zone: {v}")
    if front_x is not None:
        fx = _safe_float(front_x)
        dist = target_x - fx
        if dist > 0:
            failures.append(f"Target reach (x≥{target_x:.1f}): front_x={fx:.2f}m — {dist:.2f}m short")
        else:
            passes.append(f"Target reach (x≥{target_x:.1f}): front_x={fx:.2f}m — {abs(dist):.2f}m past")
    if lowest_y is not None:
        ly = _safe_float(lowest_y)
        margin = ly - sink_threshold
        if margin < 0:
            failures.append(f"Sink (y≥{sink_threshold:.2f}): lowest_y={ly:.2f}m — BELOW by {abs(margin):.2f}m")
        elif margin < 0.2:
            warnings.append(f"Sink (y≥{sink_threshold:.2f}): lowest_y={ly:.2f}m — margin only {margin:+.2f}m")
        else:
            passes.append(f"Sink (y≥{sink_threshold:.2f}): lowest_y={ly:.2f}m — margin {margin:+.2f}m")
    if joint_count is not None and initial_joint_count is not None:
        broken = int(initial_joint_count) - int(joint_count)
        if broken > 0:
            failures.append(f"Joints: {broken} broken ({joint_count}/{initial_joint_count} intact)")
        else:
            passes.append(f"Joints: all {joint_count}/{initial_joint_count} intact")
    if failures:
        parts.append("\n**FAILED**:")
        parts.extend(f"  - {f}" for f in failures)
    if warnings:
        parts.append("\n**NEAR LIMIT**:")
        parts.extend(f"  - {w}" for w in warnings)
    if passes:
        parts.append(f"\n**Passed**: {', '.join(p.strip().split(':')[0] for p in passes)}")
    total_constraints = len(failures) + len(warnings) + len(passes)
    total_pass = len(passes)
    if total_constraints > 0:
        parts.append(f"\n**Summary**: {total_pass}/{total_constraints} passed" + (
            f" ({len(failures)} failed, {len(warnings)} near-limit)" if failures or warnings else ""
        ))
    return parts

def _format_numerical(metrics: Dict[str, Any]) -> List[str]:
    parts: List[str] = []
    parts.append(_section("6. Numerical Health"))
    num_issues = metrics.get("numerical_issues") or []
    speed_cap_count = metrics.get("speed_cap_count", 0)
    speed_cap_limit = _safe_float(metrics.get("speed_cap_limit"), default=4.0)
    max_vert_accel = _safe_float(metrics.get("max_vertical_accel_seen"))
    step_count = metrics.get("step_count", 0)
    front_x = metrics.get("vehicle_front_x")
    lowest_y = metrics.get("vehicle_lowest_y")
    issues: List[str] = []
    if num_issues:
        issues.extend(str(i) for i in num_issues)
    if speed_cap_count > 0:
        cap_rate = speed_cap_count / max(1, int(step_count)) if step_count else 0
        issues.append(
            f"Speed capped {speed_cap_count}× ({speed_cap_limit:.1f} m/s, {cap_rate * 100.0:.1f}% of steps)"
        )
    if front_x is not None and abs(_safe_float(front_x)) > 100.0:
        issues.append(f"Extreme front_x={_safe_float(front_x):.1f} m")
    if lowest_y is not None and abs(_safe_float(lowest_y)) > 50.0:
        issues.append(f"Extreme lowest_y={_safe_float(lowest_y):.1f} m")
    if max_vert_accel > 50.0:
        issues.append(f"Peak vertical accel: {max_vert_accel:.1f} m/s² ({max_vert_accel / 9.81:.1f} g)")
    if issues:
        parts.append(f"\n⚠️ Issues: {'; '.join(issues)}")
    else:
        parts.append("\n- No numerical anomalies detected.")
    return parts

def format_task_metrics(metrics: Dict[str, Any]) -> List[str]:
    parts: List[str] = []
    violations = metrics.get("constraint_violations")
    if isinstance(violations, list) and violations:
        parts.append("### 0. Design Constraint Violations (Build Phase)")
        for v in violations:
            parts.append(f"- {v}")
        return parts
    front_x = metrics.get("vehicle_front_x")
    lowest_y = metrics.get("vehicle_lowest_y")
    step_count = metrics.get("step_count", "?")
    progress = metrics.get("progress")
    summary_parts = [f"step={step_count}"]
    if front_x is not None and not _is_nonfinite(front_x):
        summary_parts.append(f"front_x={float(front_x):.2f}")
    if lowest_y is not None and not _is_nonfinite(lowest_y):
        summary_parts.append(f"lowest_y={float(lowest_y):.2f}")
    if progress is not None and not _is_nonfinite(progress):
        summary_parts.append(f"progress={float(progress):.1f}%")
    parts.append(f"\n**Run Summary**: {', '.join(summary_parts)}")
    parts.extend(_format_chronology(metrics))
    parts.extend(_format_spatial(metrics))
    parts.extend(_format_stress(metrics))
    parts.extend(_format_energy(metrics))
    parts.extend(_format_constraints(metrics))
    parts.extend(_format_numerical(metrics))
    if len(parts) <= 1:
        try:
            from pace_bench.evaluation.verification.diagnostics import (
                format_generic_execution_metrics,
            )
            return format_generic_execution_metrics(metrics)
        except Exception:
            pass
    return parts

def get_improvement_suggestions(
    metrics: Dict[str, Any],
    score: float,
    success: bool,
    failed: bool,
    failure_reason: str = None,
    error: str = None,

) -> List[str]:
    return []
