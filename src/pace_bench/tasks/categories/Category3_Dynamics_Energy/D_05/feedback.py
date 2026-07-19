from typing import Dict, Any, List

import math

def _f(v):
    if v is None:
        return "N/A"
    try:
        fv = float(v)
        if not math.isfinite(fv):
            return str(v)
        if abs(fv) >= 1000:
            return f"{fv:.1f}"
        if abs(fv) >= 10:
            return f"{fv:.2f}"
        return f"{fv:.3f}"
    except (TypeError, ValueError):
        return str(v)

def _fm(m, key, default=None):
    v = m.get(key)
    if v is None:
        return default
    try:
        fv = float(v)
        if not math.isfinite(fv):
            return default
        return fv
    except (TypeError, ValueError):
        return default

def _pct(part, whole):
    if whole is None or float(whole) == 0:
        return "N/A"
    return f"{100.0 * float(part) / float(whole):.1f}%"

def _section_outcome(m: Dict[str, Any]) -> List[str]:
    parts = []
    shell_broken = m.get("shell_broken", False)
    step_count = m.get("step_count", "N/A")
    parts.append("## 1. Outcome\n")
    parts.append(f"Shell: {'BROKEN' if shell_broken else 'INTACT'}  |  Steps: {step_count}")
    return parts

def _section_temporal_chronology(m: Dict[str, Any]) -> List[str]:
    parts: List[str] = []
    parts.append("## 2. Temporal Chronology\n")
    events: List[str] = []
    step_count = m.get("step_count", 0)
    entry_step = m.get("slot_entry_step")
    if entry_step is not None:
        hy = _fm(m, "slot_entry_hammer_y")
        by = _fm(m, "slot_entry_bar_y")
        line = f"Step {int(entry_step)}: Slot entry at x>={_f(m.get('slot_bar_x', 15.0))} m"
        if hy is not None:
            line += f", hammer y={_f(hy)}"
        if by is not None:
            line += f", bar y={_f(by)}"
        events.append(line)
    contact_events = m.get("contact_events", []) or []
    for ce in contact_events:
        obs = ce.get("obstacle", "unknown")
        s = ce.get("step", "?")
        hx = ce.get("hammer_x")
        hy = ce.get("hammer_y")
        line = f"Step {s}: CONTACT with **{obs}**"
        if hx is not None and hy is not None:
            line += f" at ({_f(hx)}, {_f(hy)})"
        events.append(line)
    hx = _fm(m, "hammer_x")
    hy = _fm(m, "hammer_y")
    speed = _fm(m, "speed")
    ke = _fm(m, "kinetic_energy")
    if hx is not None and hy is not None:
        line = f"Step {step_count} (final): hammer at ({_f(hx)}, {_f(hy)}) m"
        if speed is not None:
            line += f", speed={_f(speed)} m/s"
        if ke is not None:
            line += f", KE={_f(ke)} J"
        events.append(line)
    if not events:
        parts.append("  No events recorded.\n")
    else:
        for ev in events:
            parts.append(f"  • {ev}")
        parts.append("")
    return parts

def _section_spatial_margins(m: Dict[str, Any]) -> List[str]:
    parts: List[str] = []
    parts.append("## 3. Spatial Diagnostics\n")
    entry_y = _fm(m, "slot_entry_hammer_y")
    gap_low = _fm(m, "slot_gap_y_low", 1.85)
    gap_high = _fm(m, "slot_gap_y_high", 3.35)
    entry_bar_y = _fm(m, "slot_entry_bar_y")
    bar_half_h = _fm(m, "slot_bar_half_height", 0.10)
    if entry_y is not None and gap_low is not None and gap_high is not None:
        gap_h = gap_high - gap_low
        margin_low = entry_y - gap_low
        margin_high = gap_high - entry_y
        parts.append("### Slot Gap at Entry\n")
        parts.append(f"  Hammer y={_f(entry_y)}  |  Gap [{_f(gap_low)}, {_f(gap_high)}] (h={_f(gap_h)} m)")
        parts.append(f"  Margins: lower={_f(margin_low)} m ({_pct(margin_low, gap_h)})  |  upper={_f(margin_high)} m ({_pct(margin_high, gap_h)})")
        if entry_bar_y is not None:
            bar_to_hammer = abs(entry_bar_y - entry_y)
            clearance = bar_to_hammer - bar_half_h
            status = "✗ COLLISION" if clearance <= 0.05 else "✓ clear"
            parts.append(f"  Bar y={_f(entry_bar_y)}  |  sep={_f(bar_to_hammer)} m  |  edge clearance={_f(clearance)} m {status}")
        parts.append("")
    hx = _fm(m, "hammer_x")
    hy = _fm(m, "hammer_y")
    sx = _fm(m, "shell_x", 16.0)
    sy = _fm(m, "shell_y", 2.6)
    if all(v is not None for v in [hx, hy, sx, sy]):
        dx = hx - sx
        dy = hy - sy
        dist = math.sqrt(dx * dx + dy * dy)
        parts.append("### Distance to Shell\n")
        parts.append(f"  Hammer ({_f(hx)}, {_f(hy)}) → Shell ({_f(sx)}, {_f(sy)})")
        parts.append(f"  dist={_f(dist)} m  |  dx={_f(dx)} ({'ahead' if dx > 0 else 'behind'})  |  dy={_f(dy)} ({'above' if dy > 0 else 'below'})")
        parts.append("")
    return parts

def _section_energy_flow(m: Dict[str, Any]) -> List[str]:
    parts: List[str] = []
    parts.append("## 4. Energy & Power\n")
    peak_ke = _fm(m, "peak_kinetic_energy")
    peak_step = m.get("peak_ke_step", 0)
    final_ke = _fm(m, "kinetic_energy")
    speed = _fm(m, "speed")
    has_motion = (peak_ke is not None and peak_ke > 0.01) or (speed is not None and speed > 0.01)
    if not has_motion:
        parts.append(f"  KE={_f(final_ke)} J  |  No motion — energy diagnostics inapplicable")
        parts.append("")
        return parts
    if peak_ke is not None:
        parts.append(f"  Peak KE: {_f(peak_ke)} J at step {peak_step}")
    if final_ke is not None:
        parts.append(f"  Final KE: {_f(final_ke)} J")
    if peak_ke is not None and peak_ke > 0 and final_ke is not None:
        efficiency = final_ke / peak_ke * 100.0
        loss_pct = 100.0 - efficiency
        parts.append(f"  Energy retention: {efficiency:.1f}%")
        if loss_pct > 20:
            parts.append(f"  Energy loss: {loss_pct:.1f}% dissipated")
    entry_step = m.get("slot_entry_step")
    if entry_step is not None and peak_step is not None and peak_ke is not None and peak_ke > 0:
        if int(peak_step) < int(entry_step):
            parts.append(f"  Peak KE (step {peak_step}) BEFORE slot entry (step {entry_step}) — energy decaying at slot")
    parts.append("")
    return parts

def _section_load_stress(m: Dict[str, Any]) -> List[str]:
    parts: List[str] = []
    parts.append("## 5. Load & Stress\n")
    max_force = _fm(m, "max_shell_joint_force")
    shell_break = _fm(m, "shell_break_force", 5000.0)
    if max_force is not None and shell_break is not None and shell_break > 0:
        force_pct = max_force / shell_break * 100.0
        if force_pct >= 100:
            tier = "BROKEN"
        elif force_pct > 80:
            tier = "critical"
        elif force_pct > 50:
            tier = "elevated"
        else:
            tier = "nominal"
        parts.append(f"  Shell joint force: {_f(max_force)} / {_f(shell_break)} N ({force_pct:.1f}% — {tier})")
        if 80 < force_pct < 100:
            parts.append(f"  Near-limit: within {100.0 - force_pct:.1f}% of break threshold")
    else:
        parts.append(f"  Shell joint force data unavailable (break threshold: {_f(shell_break)} N)")
    parts.append("")
    return parts

def _section_constraint_profile(m: Dict[str, Any]) -> List[str]:
    parts: List[str] = []
    parts.append("## 6. Constraints\n")
    parts.append("### Build-Time (checked at step 0)\n")
    mass = _fm(m, "structure_mass")
    max_mass = _fm(m, "max_structure_mass", 70.0)
    body_positions = m.get("agent_body_positions", []) or []
    bx_min = _fm(m, "build_zone_x_min", 2.0)
    bx_max = _fm(m, "build_zone_x_max", 12.0)
    by_min = _fm(m, "build_zone_y_min", 2.0)
    by_max = _fm(m, "build_zone_y_max", 8.0)
    if mass is not None and max_mass is not None:
        mass_ok = mass <= max_mass
        status = "PASS" if mass_ok else "FAIL"
        parts.append(f"  Mass: {_f(mass)} / {_f(max_mass)} kg {status} (margin {_f(max_mass - mass)} kg)")
    zone_violations = []
    for i, bp in enumerate(body_positions):
        bx = bp.get("x")
        by = bp.get("y")
        if bx is None or by is None:
            continue
        x_ok = (bx_min is not None and bx_max is not None and bx_min <= bx <= bx_max)
        y_ok = (by_min is not None and by_max is not None and by_min <= by <= by_max)
        if not (x_ok and y_ok):
            zone_violations.append((i + 1, bx, by, x_ok, y_ok))
    if not body_positions:
        parts.append(f"  Build zone: no body positions recorded")
    elif not zone_violations:
        parts.append(f"  Build zone x=[{_f(bx_min)}, {_f(bx_max)}] y=[{_f(by_min)}, {_f(by_max)}]: {len(body_positions)} bodies ALL PASS")
    else:
        parts.append(f"  Build zone x=[{_f(bx_min)}, {_f(bx_max)}] y=[{_f(by_min)}, {_f(by_max)}]:")
        for vi in zone_violations:
            i, bx, by, x_ok, y_ok = vi
            reasons = []
            if not x_ok:
                reasons.append(f"x={_f(bx)} ∉ [{_f(bx_min)}, {_f(bx_max)}]")
            if not y_ok:
                reasons.append(f"y={_f(by)} ∉ [{_f(by_min)}, {_f(by_max)}]")
            parts.append(f"    Body {i}: FAIL ({'; '.join(reasons)})")
        passing = len(body_positions) - len(zone_violations)
        if passing > 0:
            parts.append(f"    {passing} other bodies: PASS")
    parts.append("")
    parts.append("### Runtime\n")
    hits = []
    obs_checks = [
        ("slot_bar", "slot bar"),
        ("slot_wall", "slot wall"),
        ("pendulum", "pendulum"),
        ("gate", "gate"),
        ("gate2", "gate2"),
        ("wall", "wall"),
    ]
    for key, label in obs_checks:
        if m.get(f"hammer_hit_{key}", False):
            hits.append(label)
    if hits:
        parts.append(f"  Obstacles hit: {', '.join(hits)} → FAIL")
    else:
        parts.append(f"  Obstacle contacts: none → PASS")
    parts.append("")
    return parts

def _section_numerical_health(m: Dict[str, Any]) -> List[str]:
    parts: List[str] = []
    parts.append("## 7. Numerical Health\n")
    warnings: List[str] = []
    peak_speed = _fm(m, "peak_speed")
    if peak_speed is not None:
        if peak_speed > 100.0:
            warnings.append(f"EXTREME peak speed {_f(peak_speed)} m/s — possible solver instability")
        elif peak_speed > 50.0:
            warnings.append(f"High peak speed: {_f(peak_speed)} m/s (>50 m/s)")
    speed = _fm(m, "speed")
    ang_vel = _fm(m, "angular_velocity")
    if speed is not None and not math.isfinite(speed):
        warnings.append(f"Non-finite final speed: {speed}")
    if ang_vel is not None and not math.isfinite(ang_vel):
        warnings.append(f"Non-finite final angular velocity: {ang_vel}")
    peak_ke = _fm(m, "peak_kinetic_energy")
    if peak_ke is not None:
        if not math.isfinite(peak_ke):
            warnings.append(f"Non-finite peak KE: {peak_ke}")
        elif peak_ke > 100000:
            warnings.append(f"Extreme peak KE: {_f(peak_ke)} J (>100,000 J)")
    body_positions = m.get("agent_body_positions", []) or []
    for i, bp in enumerate(body_positions):
        bx = bp.get("x")
        by = bp.get("y")
        if bx is not None and not math.isfinite(bx):
            warnings.append(f"Non-finite x on body {i + 1}: {bx}")
        if by is not None and not math.isfinite(by):
            warnings.append(f"Non-finite y on body {i + 1}: {by}")
    if warnings:
        for w in warnings:
            parts.append(f"  ⚠ {w}")
    else:
        parts.append("  No anomalies.")
    parts.append("")
    return parts

def format_task_metrics(metrics: Dict[str, Any]) -> List[str]:
    if not metrics:
        return ["**No metrics available**"]
    m = dict(metrics)
    parts: List[str] = []
    parts.append("")
    parts.extend(_section_outcome(m))
    parts.extend(_section_temporal_chronology(m))
    parts.extend(_section_spatial_margins(m))
    parts.extend(_section_energy_flow(m))
    parts.extend(_section_load_stress(m))
    parts.extend(_section_constraint_profile(m))
    parts.extend(_section_numerical_health(m))
    return parts

def get_improvement_suggestions(
    metrics: Dict[str, Any],
    score: float,
    success: bool,
    failed: bool,
    failure_reason: str = None,
    error: str = None,

) -> List[str]:
    suggestions: List[str] = []
    if error:
        suggestions.append("- Review the error details above to identify the specific issue")
        suggestions.append("- Ensure code follows the required function structure (build_agent and agent_action)")
        return suggestions
    if success:
        suggestions.append("- Design successfully broke the shell — consider how to generalize across parameter changes")
        return suggestions
    fr = (failure_reason or "").lower()
    if "slot bar" in fr or "oscillating" in fr:
        suggestions.append("- The oscillating bar moves vertically inside the slot gap — its position changes every step")
        suggestions.append("- The bar's vertical position follows a sinusoidal pattern: y = center + amplitude × sin(step × omega)")
        suggestions.append("- Hammer must cross the slot at x ≈ 15.0 m when the bar is at one extreme of its oscillation")
        suggestions.append("- Consider the timing of your swing initiation relative to the bar's oscillation period")
    if "slot barrier" in fr or "slot wall" in fr or "gap" in fr:
        suggestions.append("- The slot has vertical barriers; the hammer head must pass through the gap between them")
        suggestions.append("- The gap spans y = [gap_low, gap_high] at x = slot_barrier_x")
    if "pendulum" in fr:
        suggestions.append("- The pendulum swings near the hammer's path; it has its own angular velocity and period")
        suggestions.append("- Time the hammer's pass through the pendulum zone to avoid collision")
    if "not deliver enough force" in fr or "not broken" in fr or "shell not broken" in fr:
        suggestions.append("- The shell requires a minimum impact force to break")
        suggestions.append("- Impact force depends on hammer mass, speed, and the angle of contact")
        suggestions.append("- If the hammer hits an obstacle before reaching the shell, energy is lost to the collision")
    if "design constraint" in fr or "build zone" in fr or "structure mass" in fr:
        suggestions.append("- All beam centers must be placed inside the build zone at construction time")
        suggestions.append("- The build zone only constrains initial placement — not where the structure reaches during simulation")
        suggestions.append("- Check that beam center coordinates (not beam edges) are within the zone boundaries")
    if "not deliver enough force" not in fr and "slot" not in fr and "pendulum" not in fr and "design" not in fr and "build" not in fr:
        suggestions.append("- Review the trajectory of your hammer head — it must clear all obstacles and reach the shell")
        suggestions.append("- Consider energy efficiency: how much kinetic energy reaches the shell vs is lost to damping/collisions")
    return suggestions
