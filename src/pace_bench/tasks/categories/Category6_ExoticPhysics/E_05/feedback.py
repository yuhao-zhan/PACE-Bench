from __future__ import annotations

import math

from typing import Any, Dict, List, Optional

def _is_bad_number(x: Any) -> bool:
    if x is None:
        return False
    if isinstance(x, (int, float)):
        return not math.isfinite(float(x))
    return False

def _collect_bad_numeric_paths(obj: Any, prefix: str = "") -> List[str]:
    bad: List[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{prefix}.{k}" if prefix else str(k)
            bad.extend(_collect_bad_numeric_paths(v, p))
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            bad.extend(_collect_bad_numeric_paths(v, f"{prefix}[{i}]"))
    elif _is_bad_number(obj):
        bad.append(prefix or "value")
    return bad

def _fmt(x: Any, nd: int = 3) -> str:
    try:
        xf = float(x)
        if not math.isfinite(xf):
            return str(xf)
        return f"{xf:.{nd}f}"
    except (TypeError, ValueError):
        return str(x)

def _safe_float(metrics: Dict[str, Any], key: str, default: float = 0.0) -> float:
    try:
        v = float(metrics.get(key, default))
        return v if math.isfinite(v) else default
    except (TypeError, ValueError):
        return default

def _pct_of(value: float, total: float) -> float:
    if not math.isfinite(total) or total == 0:
        return 0.0
    return max(0.0, min(100.0, value / total * 100.0))

def _section_position(metrics: Dict[str, Any]) -> List[str]:
    parts: List[str] = []
    parts.append("### 1. Position & Motion")
    x = _safe_float(metrics, "body_x")
    y = _safe_float(metrics, "body_y")
    vx = _safe_float(metrics, "velocity_x")
    vy = _safe_float(metrics, "velocity_y")
    speed = _safe_float(metrics, "speed")
    start_x = _safe_float(metrics, "start_x", 8.0)
    start_y = _safe_float(metrics, "start_y", 5.0)
    parts.append(
        f"**Position**: ({_fmt(x)}, {_fmt(y)}) m | "
        f"**Velocity**: ({_fmt(vx)}, {_fmt(vy)}) m/s, speed={_fmt(speed)} m/s"
    )
    dx = x - start_x
    dy = y - start_y
    parts.append(
        f"**Displacement from start** ({_fmt(start_x)}, {_fmt(start_y)}): "
        f"Δx={_fmt(dx)} m, Δy={_fmt(dy)} m"
    )
    tx_min = metrics.get("target_x_min")
    tx_max = metrics.get("target_x_max")
    ty_min = metrics.get("target_y_min")
    ty_max = metrics.get("target_y_max")
    dist_tgt = metrics.get("dist_to_target")
    if dist_tgt is not None:
        zone_str = ""
        if tx_min is not None and tx_max is not None:
            zone_str += f"x∈[{_fmt(tx_min, 1)},{_fmt(tx_max, 1)}]"
        if ty_min is not None and ty_max is not None:
            if zone_str:
                zone_str += " "
            zone_str += f"y∈[{_fmt(ty_min, 1)},{_fmt(ty_max, 1)}]"
        parts.append(f"**Target zone** {zone_str}: {_fmt(dist_tgt)} m away")
    ceiling_y = metrics.get("ceiling_y")
    ground_y = metrics.get("ground_y")
    boundary_parts: List[str] = []
    if ceiling_y is not None:
        cy = float(ceiling_y)
        m = cy - y
        if m <= 0:
            boundary_parts.append(f"Ceiling EXCEEDED by {_fmt(abs(m))} m (y={_fmt(y)} vs {_fmt(cy)})")
        elif m < 3.0:
            boundary_parts.append(f"Ceiling margin {_fmt(m)} m")
    if ground_y is not None:
        gy = float(ground_y)
        m = y - gy
        if m <= 0:
            boundary_parts.append(f"Ground BELOW by {_fmt(abs(m))} m (y={_fmt(y)} vs {_fmt(gy)})")
        elif m < 3.0:
            boundary_parts.append(f"Ground margin {_fmt(m)} m")
    if boundary_parts:
        parts.append("**Boundaries**: " + " | ".join(boundary_parts))
    step_count = metrics.get("step_count", 0)
    max_x = metrics.get("max_x_reached")
    if max_x is not None and step_count > 0:
        if max_x > start_x + 0.5:
            parts.append(f"**Max forward x**: {_fmt(max_x)} m (net +{_fmt(max_x - start_x)} m)")
        elif max_x <= start_x + 0.5:
            parts.append(f"**Forward progress**: none (max x={_fmt(max_x)} m)")
    max_spd = metrics.get("max_speed")
    if max_spd is not None and max_spd > max(speed * 1.5, 1.0):
        parts.append(f"**Peak speed**: {_fmt(max_spd)} m/s")
    zone_samples: Dict[str, int] = metrics.get("vertical_zone_samples") or {}
    if zone_samples:
        total_z = sum(zone_samples.values())
        non_corridor = [(zk, cnt) for zk, cnt in zone_samples.items()
                        if zk != "corridor" and _pct_of(cnt, total_z) > 1.0]
        if non_corridor:
            zone_labels = {
                "ceiling": "ceiling",
                "pit": "pit",
                "ground": "ground",
            }
            entries = [f"{zone_labels.get(zk, zk)}={_pct_of(cnt, total_z):.0f}%" for zk, cnt in non_corridor]
            parts.append(f"**Zone occupancy**: " + ", ".join(entries))
    return parts

def _section_events(metrics: Dict[str, Any]) -> List[str]:
    parts: List[str] = []
    events: List[dict] = metrics.get("temporal_events") or []
    vrev: List[dict] = metrics.get("velocity_reversal_events") or []
    plateau_step = metrics.get("progress_plateau_end_step")
    step_count = metrics.get("step_count", 0)
    if not events and not vrev and plateau_step is None:
        return parts
    parts.append("### 2. Events")
    if events:
        event_lines = []
        for ev in events:
            step = ev.get("step", "?")
            event_name = ev.get("event", "unknown")
            label = {
                "ceiling_entry": "Ceiling contact",
                "pit_entry": "Pit entry",
                "ground_entry": "Ground contact",
                "progress_plateau_detected": "Progress stalled",
            }.get(event_name, event_name.replace("_", " ").title())
            extra = ""
            if event_name == "progress_plateau_detected":
                dur = ev.get("stall_duration_steps", "?")
                extra = f" ({dur} steps)"
            bx = ev.get("body_x", "?")
            by_val = ev.get("body_y", "?")
            event_lines.append(
                f"Step {step}: {label} at ({_fmt(bx)}, {_fmt(by_val)}){extra}"
            )
        parts.extend(event_lines)
    if vrev:
        x_revs = sum(1 for r in vrev if r.get("axis") == "x")
        y_revs = sum(1 for r in vrev if r.get("axis") == "y")
        rev_parts = []
        if x_revs:
            rev_parts.append(f"{x_revs} horizontal")
        if y_revs:
            rev_parts.append(f"{y_revs} vertical")
        parts.append(f"Velocity reversals: " + ", ".join(rev_parts))
    if plateau_step is not None and not any(
        e.get("event") == "progress_plateau_detected" for e in events
    ):
        plateau_x = metrics.get("progress_plateau_x")
        plateau_dur = metrics.get("progress_plateau_duration", 0)
        parts.append(
            f"Progress stalled at step {plateau_step} "
            f"(x≈{_fmt(plateau_x)}, {plateau_dur}+ steps)"
        )
    return parts

def _section_forces(metrics: Dict[str, Any]) -> List[str]:
    parts: List[str] = []
    step_count = metrics.get("step_count", 0)
    if step_count <= 0:
        return parts
    net_fx = _safe_float(metrics, "net_magnetic_force_x")
    net_fy = _safe_float(metrics, "net_magnetic_force_y")
    net_mag = math.sqrt(net_fx * net_fx + net_fy * net_fy)
    thrust_cap = _safe_float(metrics, "max_thrust", 165.0)
    parts.append("### 3. Forces")
    parts.append(
        f"**Net magnetic**: ({_fmt(net_fx)}, {_fmt(net_fy)}) N, |F|={_fmt(net_mag)} N | "
        f"**Thrust cap**: {_fmt(thrust_cap)} N"
    )
    thrust_x = _safe_float(metrics, "thrust_applied_x")
    thrust_y = _safe_float(metrics, "thrust_applied_y")
    thrust_used = math.sqrt(thrust_x * thrust_x + thrust_y * thrust_y)
    if thrust_used > 0.01 and thrust_cap > 0:
        thrust_pct = _pct_of(thrust_used, thrust_cap)
        tier = ""
        if thrust_pct > 80:
            tier = " [CRITICAL]"
        elif thrust_pct > 50:
            tier = " [ELEVATED]"
        parts.append(
            f"**Thrust used**: {_fmt(thrust_used)} N ({thrust_pct:.1f}% of capacity){tier}"
        )
    net_total_x = _safe_float(metrics, "net_force_x_terminal")
    if abs(net_total_x) > 0.01:
        direction = "rightward" if net_total_x > 0 else "leftward"
        mag_fx_term = _safe_float(metrics, "net_magnetic_force_x_terminal")
        thrust_fx_term = _safe_float(metrics, "thrust_applied_x_terminal")
        parts.append(
            f"**Net horizontal**: {_fmt(net_total_x)} N {direction} "
            f"(magnetic {_fmt(mag_fx_term)} N + thrust {_fmt(thrust_fx_term)} N)"
        )
    contributors: List[dict] = metrics.get("top_magnet_contributors") or []
    if contributors:
        threshold = thrust_cap * 0.15 if thrust_cap > 0 else float("inf")
        significant = []
        for c in contributors:
            fx_c = float(c.get("fx", 0))
            fy_c = float(c.get("fy", 0))
            mag_c = math.sqrt(fx_c * fx_c + fy_c * fy_c)
            if mag_c > threshold:
                significant.append((c, mag_c))
        if significant:
            parts.append(
                f"**Significant magnet sources** ({len(significant)}/{len(contributors)} "
                f"above {_fmt(threshold)} N):"
            )
            for i, (c, mag_c) in enumerate(significant, 1):
                mx = c.get("mx", "?")
                my = c.get("my", "?")
                fx_c = float(c.get("fx", 0))
                fy_c = float(c.get("fy", 0))
                dist = float(c.get("distance", 0))
                if abs(fx_c) > abs(fy_c):
                    direction = "←" if fx_c < 0 else "→"
                else:
                    direction = "↓" if fy_c < 0 else "↑"
                parts.append(
                    f"  {i}. ({_fmt(mx, 1)}, {_fmt(my, 1)}): "
                    f"|F|={_fmt(mag_c)} N {direction}, dist={_fmt(dist)} m"
                )
        elif contributors:
            parts.append(f"All {len(contributors)} magnet sources nominal (<{_fmt(threshold)} N each).")
    magnet_count = metrics.get("magnet_count")
    if magnet_count is not None:
        parts.append(f"**Total magnet sources**: {magnet_count}")
    return parts

def _section_energy(metrics: Dict[str, Any]) -> List[str]:
    parts: List[str] = []
    step_count = metrics.get("step_count", 0)
    thrust_work = _safe_float(metrics, "cumulative_thrust_work")
    mag_work = _safe_float(metrics, "cumulative_magnetic_work")
    ke = _safe_float(metrics, "kinetic_energy")
    if step_count <= 0 or (thrust_work == 0 and mag_work == 0 and ke == 0):
        return parts
    parts.append("### 4. Energy")
    efficiency = _safe_float(metrics, "energy_efficiency_pct")
    damp_loss = _safe_float(metrics, "cumulative_damping_loss")
    parts.append(
        f"**KE**: {_fmt(ke)} J | "
        f"**Thrust work**: {_fmt(thrust_work)} J | "
        f"**Efficiency**: {_fmt(efficiency)}%"
    )
    if abs(mag_work) > thrust_work * 0.8 and mag_work < 0 and thrust_work > 0:
        ratio = abs(mag_work) / max(thrust_work, 0.001)
        parts.append(
            f"⚠ Magnetic work ({_fmt(mag_work)} J) opposes thrust "
            f"by {ratio:.1f}× — energy trap"
        )
    if damp_loss > thrust_work * 5 and thrust_work > 0:
        parts.append(
            f"⚠ Damping loss ({_fmt(damp_loss)} J) dominates thrust work "
            f"({_fmt(thrust_work)} J)"
        )
    speed = _safe_float(metrics, "speed")
    if speed < 0.1 and ke < 1.0 and thrust_work > 100:
        parts.append(
            f"⚠ Low KE ({_fmt(ke)} J) despite {_fmt(thrust_work)} J thrust — "
            f"energy dissipated faster than it accumulates"
        )
    return parts

def _section_constraints(metrics: Dict[str, Any]) -> List[str]:
    parts: List[str] = []
    parts.append("### 5. Constraints")
    x = _safe_float(metrics, "body_x")
    y = _safe_float(metrics, "body_y")
    step_count = metrics.get("step_count", 0)
    reached = metrics.get("reached_target", False)
    lines: List[str] = []
    if not reached:
        tx_min = _safe_float(metrics, "target_x_min", 28.0)
        tx_max = _safe_float(metrics, "target_x_max", 32.0)
        ty_min = _safe_float(metrics, "target_y_min", 6.0)
        ty_max = _safe_float(metrics, "target_y_max", 9.0)
        if x < tx_min:
            margin_x = tx_min - x
            label_x = "short"
        elif x > tx_max:
            margin_x = x - tx_max
            label_x = "past"
        else:
            margin_x = 0.0
            label_x = "in"
        if y < ty_min:
            margin_y = ty_min - y
            label_y = "below"
        elif y > ty_max:
            margin_y = y - ty_max
            label_y = "above"
        else:
            margin_y = 0.0
            label_y = "in"
        lines.append(
            f"✗ **Target zone**: FAIL — "
            f"Δx={_fmt(margin_x)} m {label_x}, Δy={_fmt(margin_y)} m {label_y}"
        )
    else:
        lines.append("✓ **Target zone**: REACHED")
    ceiling_y = metrics.get("ceiling_y")
    if ceiling_y is not None:
        cy = float(ceiling_y)
        in_ceiling = metrics.get("in_ceiling_zone", False)
        if in_ceiling:
            first_step = metrics.get("first_ceiling_entry_step")
            steps_in = metrics.get("steps_near_ceiling", 0)
            pct = _pct_of(steps_in, max(1, step_count))
            lines.append(
                f"✗ **Ceiling y≤{_fmt(cy, 1)}**: VIOLATED "
                f"at step {first_step} ({pct:.0f}% of run)"
            )
        else:
            margin = cy - y
            if margin < 3.0:
                lines.append(f"✓ **Ceiling y≤{_fmt(cy, 1)}**: margin {_fmt(margin)} m")
    ground_y = metrics.get("ground_y")
    if ground_y is not None:
        gy = float(ground_y)
        steps_ground = metrics.get("steps_in_ground_zone", 0)
        if steps_ground > 0:
            first_ground = metrics.get("first_ground_entry_step")
            pct = _pct_of(steps_ground, max(1, step_count))
            lines.append(
                f"⚠ **Ground y≥{_fmt(gy, 1)}**: CONTACT at step {first_ground} "
                f"({pct:.0f}% of run)"
            )
        else:
            margin = y - gy
            if margin < 3.0:
                lines.append(f"✓ **Ground y≥{_fmt(gy, 1)}**: margin {_fmt(margin)} m")
    in_pit = metrics.get("in_pit_zone", False)
    pit_x_min = metrics.get("pit_x_min")
    if pit_x_min is not None:
        steps_pit = metrics.get("steps_in_pit_zone", 0)
        if steps_pit > 0:
            first_pit = metrics.get("first_pit_entry_step")
            pct = _pct_of(steps_pit, max(1, step_count))
            lines.append(
                f"✗ **Pit zone**: ENTERED at step {first_pit} ({pct:.0f}% of run)"
            )
    thrust_cap = _safe_float(metrics, "max_thrust", 165.0)
    thrust_x = _safe_float(metrics, "thrust_applied_x")
    thrust_y = _safe_float(metrics, "thrust_applied_y")
    thrust_used = math.sqrt(thrust_x * thrust_x + thrust_y * thrust_y)
    if thrust_cap > 0 and thrust_used > 0.01:
        thrust_pct = _pct_of(thrust_used, thrust_cap)
        if thrust_pct > 50:
            tier = "CRITICAL" if thrust_pct > 80 else "ELEVATED"
            lines.append(
                f"⚠ **Thrust**: {thrust_pct:.0f}% of {_fmt(thrust_cap)} N cap [{tier}]"
            )
    stationary = metrics.get("steps_stationary", 0)
    if stationary is not None and step_count > 0:
        stationary_pct = _pct_of(stationary, step_count)
        if stationary_pct > 30:
            lines.append(f"⚠ **Stall**: stationary {stationary_pct:.0f}% of run")
    max_steps = metrics.get("max_steps", 10000)
    if step_count >= max_steps - 1 and max_steps > 0:
        lines.append(f"⏱ **Step budget**: EXHAUSTED ({step_count}/{max_steps})")
    if lines:
        parts.extend(lines)
    else:
        parts.append("All constraints nominal.")
    return parts

def _section_physics_health(metrics: Dict[str, Any]) -> List[str]:
    parts: List[str] = []
    parts.append("### 6. Physics & Health")
    magnet_count = metrics.get("magnet_count", "?")
    body_mass = _safe_float(metrics, "body_mass", 9.6)
    thrust_cap = _safe_float(metrics, "max_thrust", 165.0)
    parts.append(
        f"**Environment**: "
        f"{magnet_count} magnets | "
        f"thrust cap={_fmt(thrust_cap)} N | "
        f"body mass={_fmt(body_mass)} kg"
    )
    anomaly_count = 0
    bad_paths = _collect_bad_numeric_paths(metrics)
    if bad_paths:
        parts.append(
            "⚠ Non-finite values in: " + ", ".join(bad_paths[:8])
        )
        anomaly_count += 1
    max_spd = _safe_float(metrics, "max_speed")
    if max_spd > 100:
        parts.append(f"⚠ Extreme peak velocity: {_fmt(max_spd)} m/s (>100 m/s)")
        anomaly_count += 1
    elif max_spd > 50:
        parts.append(f"⚠ Elevated peak velocity: {_fmt(max_spd)} m/s (>50 m/s)")
        anomaly_count += 1
    peak_accel = _safe_float(metrics, "peak_vertical_accel")
    if peak_accel > 1000:
        parts.append(f"⚠ Extreme vertical accel: {_fmt(peak_accel)} m/s² (>100g)")
        anomaly_count += 1
    elif peak_accel > 100:
        parts.append(f"⚠ Elevated vertical accel: {_fmt(peak_accel)} m/s² (>10g)")
        anomaly_count += 1
    max_y = _safe_float(metrics, "max_body_y")
    if max_y > 100:
        parts.append(f"⚠ Extreme vertical excursion: max y={_fmt(max_y)} m")
        anomaly_count += 1
    elif max_y > 30:
        parts.append(f"⚠ Elevated vertical excursion: max y={_fmt(max_y)} m")
        anomaly_count += 1
    max_x = _safe_float(metrics, "max_body_x")
    if max_x > 100:
        parts.append(f"⚠ Extreme horizontal excursion: max x={_fmt(max_x)} m")
        anomaly_count += 1
    ke = _safe_float(metrics, "kinetic_energy")
    if ke > 100000:
        parts.append(f"⚠ Extreme KE: {_fmt(ke)} J")
        anomaly_count += 1
    damp_loss = _safe_float(metrics, "cumulative_damping_loss")
    thrust_work = _safe_float(metrics, "cumulative_thrust_work")
    if damp_loss > thrust_work * 10 and thrust_work > 0:
        parts.append(
            f"⚠ Damping dominance: loss ({_fmt(damp_loss)} J) "
            f">10× thrust work ({_fmt(thrust_work)} J)"
        )
        anomaly_count += 1
    if anomaly_count == 0:
        parts.append("No numerical anomalies detected.")
    return parts

def format_task_metrics(metrics: Dict[str, Any]) -> List[str]:
    parts: List[str] = []
    if not metrics:
        parts.append("**Metrics**: (empty — evaluator returned no data)")
        return parts
    if "error" in metrics:
        parts.append(f"**Evaluation Error**: {metrics['error']}")
        return parts
    success = metrics.get("success", False)
    failed = metrics.get("failed", False)
    reached = metrics.get("reached_target", False)
    step_count = metrics.get("step_count", 0)
    max_steps = metrics.get("max_steps", 10000)
    status = "SUCCESS" if success else ("FAILED" if failed else "INCOMPLETE")
    parts.append("### E-05 Diagnostic Report")
    header = (
        f"**Status**: {status} | "
        f"Target reached: {reached} | "
        f"Step {step_count}/{max_steps} ({_pct_of(step_count, max_steps):.1f}%)"
    )
    score = _safe_float(metrics, "score", -1) if "score" in metrics else None
    if score is not None and score >= 0:
        header += f" | Score {_fmt(score, 1)}"
    parts.append(header)
    for section_fn, label in (
        (_section_position, "Position"),
        (_section_events, "Events"),
        (_section_forces, "Forces"),
        (_section_energy, "Energy"),
        (_section_constraints, "Constraints"),
        (_section_physics_health, "Physics & Health"),
    ):
        try:
            result = section_fn(metrics)
            if result:
                parts.extend(result)
        except Exception as e:
            parts.append(f"*({label} diagnostics error: {e})*")
    return parts

def get_improvement_suggestions(
    metrics: Dict[str, Any],
    score: float,
    success: bool,
    failed: bool,
    failure_reason: Optional[str] = None,
    error: Optional[str] = None,

) -> List[str]:
    return []
