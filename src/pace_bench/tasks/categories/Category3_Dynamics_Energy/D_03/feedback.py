from typing import Dict, Any, List, Optional

import math

def _sf(val: Any, default: Optional[float] = None) -> Optional[float]:
    if val is None:
        return default
    try:
        f = float(val)
        return f if math.isfinite(f) else default
    except (TypeError, ValueError):
        return default

def _is_bad(val: Any) -> bool:
    try:
        return not math.isfinite(float(val))
    except (TypeError, ValueError):
        return False

def _fm(val: Any, digits: int = 2) -> str:
    v = _sf(val)
    if v is None:
        return "—"
    return f"{v:.{digits}f}"

def _pct(part, whole, default: Optional[float] = None) -> Optional[float]:
    p = _sf(part)
    w = _sf(whole)
    if p is None or w is None or abs(w) < 1e-12:
        return default
    return 100.0 * p / w

def _margin(val, limit) -> Optional[float]:
    v = _sf(val)
    li = _sf(limit)
    if v is None or li is None:
        return None
    return v - li

def _marginf(val, limit, unit: str = "") -> str:
    v = _sf(val)
    li = _sf(limit)
    if v is None or li is None:
        return f"{val} vs {limit}"
    diff = v - li
    sign = "+" if diff >= 0 else ""
    direction = "above" if diff >= 0 else "below"
    u = f" {unit}" if unit else ""
    return f"{sign}{diff:.3f}{u} {direction} limit ({li:.3f}{u})"

def _in_band(val, lo, hi) -> Optional[str]:
    v = _sf(val)
    l = _sf(lo)
    h = _sf(hi)
    if v is None or l is None or h is None:
        return None
    if v < l:
        return "BELOW"
    if v > h:
        return "ABOVE"
    return "WITHIN"

def format_task_metrics(metrics: Dict[str, Any]) -> List[str]:
    if not metrics:
        return ["**No metrics available**"]
    parts: List[str] = []
    parts.append("## D_03 Diagnostic Report — Phase-Locked Gate\n")
    success = bool(metrics.get("success", False))
    failed = bool(metrics.get("failed", False))
    fr = metrics.get("failure_reason")
    step_count = int(metrics.get("step_count", 0))
    max_steps = int(metrics.get("max_steps", 0))
    x = _sf(metrics.get("x"))
    speed = _sf(metrics.get("speed"))
    tx = _sf(metrics.get("target_x_min"), 11.75)
    status = "SUCCESS" if success else ("FAILED" if failed else "IN PROGRESS")
    lines = [f"**Status**: {status}"]
    if fr:
        lines.append(f"**Failure reason**: {fr}")
    lines.append(f"**Simulation steps**: {step_count}" + (f"/{max_steps}" if max_steps > 0 else ""))
    if x is not None and tx is not None and tx > 0:
        progress = min(x / tx * 100.0, 100.0)
        lines.append(f"**Progress**: {progress:.1f}% toward target (x={x:.2f} m, target x≥{tx:.2f} m)")
    if x is not None and speed is not None:
        lines.append(f"**Terminal state**: x={x:.2f} m, speed={speed:.2f} m/s")
    parts.extend(lines)
    parts.append("")
    parts.append("### 1. Temporal Event Chronology\n")
    _temporal_report(metrics, parts)
    parts.append("### 2. Spatial Diagnostics with Margins\n")
    _spatial_report(metrics, parts)
    parts.append("### 3. Load & Stress Distribution\n")
    _load_report(metrics, parts)
    parts.append("### 4. Energy & Power Flow\n")
    _energy_report(metrics, parts)
    parts.append("### 5. Constraint Satisfaction Profile\n")
    _constraint_report(metrics, parts)
    parts.append("### 6. Numerical Health\n")
    _numerical_health_report(metrics, parts)
    return parts

def _temporal_report(metrics: Dict[str, Any], parts: List[str]):
    timeline: List[Dict[str, Any]] = []
    for ev in metrics.get("gate_arrival_events", []) or []:
        timeline.append({
            "step": int(ev.get("step", 0)),
            "type": "gate_arrival",
            "gate": int(ev.get("gate", 0)),
            "open": ev.get("gate_open", False),
        })
    for ev in metrics.get("gate_collision_details", []) or []:
        timeline.append({
            "step": int(ev.get("step", 0)),
            "type": "gate_collision",
            "gate": int(ev.get("gate", 0)),
        })
    for ev in metrics.get("zone_crossings", []) or []:
        timeline.append({
            "step": int(ev.get("step", 0)),
            "type": "zone_transition",
            "from_zone": ev.get("from_zone", "?"),
            "to_zone": ev.get("to_zone", "?"),
            "x": _sf(ev.get("x")),
        })
    step_count = int(metrics.get("step_count", 0))
    fr = metrics.get("failure_reason", "")
    failed = bool(metrics.get("failed"))
    success = bool(metrics.get("success"))
    if success:
        timeline.append({"step": step_count, "type": "terminal_success"})
    elif failed and fr:
        timeline.append({"step": step_count, "type": "terminal_failure", "reason": str(fr)})
    timeline.sort(key=lambda e: int(e.get("step", 0)))
    if not timeline:
        parts.append("No events recorded (simulation too brief).")
        _trace_snapshot(metrics, parts)
        return
    lines: List[str] = []
    ev_idx = 0
    for ev in timeline:
        ev_idx += 1
        t = ev["type"]
        step = ev["step"]
        if t == "gate_arrival":
            gid = ev.get("gate", "?")
            is_open = ev.get("open", False)
            status = "OPEN" if is_open else "CLOSED"
            lines.append(
                f"{ev_idx}. **Step {step}**: Reached Gate #{gid} — {status}."
            )
        elif t == "gate_collision":
            gid = ev.get("gate", "?")
            lines.append(
                f"{ev_idx}. **Step {step}**: COLLISION with Gate #{gid} (gate was CLOSED)."
            )
        elif t == "zone_transition":
            fz = ev.get("from_zone", "?")
            tz = ev.get("to_zone", "?")
            zx = ev.get("x")
            x_str = f" at x={zx:.2f} m" if zx is not None else ""
            lines.append(
                f"{ev_idx}. **Step {step}**: [{fz}] → [{tz}]{x_str}."
            )
        elif t == "terminal_success":
            lines.append(f"{ev_idx}. **Step {step}**: SUCCESS — target reached with speed in band.")
        elif t == "terminal_failure":
            lines.append(f"{ev_idx}. **Step {step}**: FAILURE — {ev.get('reason', 'unknown')}.")
    for line in lines:
        parts.append(line)
    _trace_snapshot(metrics, parts)

def _trace_snapshot(metrics: Dict[str, Any], parts: List[str]):
    trace = metrics.get("speed_trace", []) or []
    if len(trace) < 1:
        return
    first = trace[0]
    last = trace[-1]
    parts.append("\n**Speed trace endpoints**:")
    for label, pt in [("Start", first), ("End", last)]:
        s = pt.get("step", "?")
        xp = _fm(pt.get("x"), 2)
        sp = _fm(pt.get("speed"), 2)
        zn = pt.get("zone", "?")
        parts.append(f"  {label}: step={s}, x={xp} m, speed={sp} m/s, zone={zn}")

def _spatial_report(metrics: Dict[str, Any], parts: List[str]):
    x = _sf(metrics.get("x"))
    speed = _sf(metrics.get("speed"))
    tx = _sf(metrics.get("target_x_min"), 11.75)
    ts_min = _sf(metrics.get("target_speed_min"), 0.45)
    ts_max = _sf(metrics.get("target_speed_max"), 2.6)
    if x is not None and tx is not None:
        target_margin = x - tx
        if target_margin >= 0:
            parts.append(
                f"**Target (x≥{tx:.2f} m)**: REACHED (margin {target_margin:+.3f} m)."
            )
        else:
            parts.append(
                f"**Target (x≥{tx:.2f} m)**: {abs(target_margin):.3f} m remaining (at x={x:.2f} m)."
            )
    if speed is not None and ts_min is not None and ts_max is not None:
        band_status = _in_band(speed, ts_min, ts_max)
        if band_status == "WITHIN":
            parts.append(
                f"**Speed band [{ts_min:.2f}, {ts_max:.2f}] m/s**: WITHIN (v={speed:.2f} m/s)."
            )
        elif band_status == "BELOW":
            parts.append(
                f"**Speed band [{ts_min:.2f}, {ts_max:.2f}] m/s**: BELOW by {ts_min - speed:.2f} m/s (v={speed:.2f} m/s)."
            )
        else:
            parts.append(
                f"**Speed band [{ts_min:.2f}, {ts_max:.2f}] m/s**: ABOVE by {speed - ts_max:.2f} m/s (v={speed:.2f} m/s)."
            )
    st_x = _sf(metrics.get("speed_trap_x"), 9.0)
    st_min = _sf(metrics.get("speed_trap_min"), 2.8)
    st_actual = _sf(metrics.get("speed_trap_actual_speed"))
    if st_actual is not None:
        st_ok = st_actual >= (st_min or 0)
        parts.append(
            f"**Speed trap (x={st_x:.2f} m, v≥{st_min:.2f})**: "
            f"{'PASS' if st_ok else 'FAIL'} — measured v={st_actual:.2f} m/s."
        )
    elif x is not None and x < (st_x or 0):
        parts.append(
            f"**Speed trap (x={st_x:.2f} m)**: not yet reached ({st_x - x:.2f} m ahead)."
        )
    else:
        parts.append(f"**Speed trap (x={st_x:.2f} m)**: data not recorded.")
    cp_x = _sf(metrics.get("checkpoint_11_x"), 11.0)
    cp_lo = _sf(metrics.get("checkpoint_11_speed_min"), 1.1)
    cp_hi = _sf(metrics.get("checkpoint_11_speed_max"), 2.7)
    cp_actual = _sf(metrics.get("checkpoint_11_actual_speed"))
    if cp_actual is not None:
        cp_ok = (cp_lo or 0) <= cp_actual <= (cp_hi or 999)
        parts.append(
            f"**Checkpoint (x={cp_x:.2f} m, v∈[{cp_lo:.2f}, {cp_hi:.2f}])**: "
            f"{'PASS' if cp_ok else 'FAIL'} — measured v={cp_actual:.2f} m/s."
        )
    elif x is not None and x < (cp_x or 0):
        parts.append(
            f"**Checkpoint (x={cp_x:.2f} m)**: not yet reached ({cp_x - x:.2f} m ahead)."
        )
    else:
        parts.append(f"**Checkpoint (x={cp_x:.2f} m)**: data not recorded.")
    _gate_spatial_summary(metrics, parts, x)

def _gate_spatial_summary(metrics: Dict[str, Any], parts: List[str], cart_x):
    gate_defs = [
        (1, "gate_x"),
        (2, "gate2_x"),
        (3, "gate3_x"),
        (4, "gate4_x"),
    ]
    arrivals = {ev.get("gate"): ev for ev in (metrics.get("gate_arrival_events", []) or [])}
    collisions = {ev.get("gate"): ev for ev in (metrics.get("gate_collision_details", []) or [])}
    if cart_x is None:
        cart_x = 0.0
    reached = 0
    collided = 0
    closest_gate = None
    closest_dist = float("inf")
    for gid, gkey in gate_defs:
        gx = _sf(metrics.get(gkey))
        if gx is None:
            continue
        if gid in collisions:
            collided += 1
        elif gid in arrivals:
            reached += 1
        elif cart_x < gx:
            dist = gx - cart_x
            if dist < closest_dist:
                closest_dist = dist
                closest_gate = gid
    total = len([1 for _, gk in gate_defs if _sf(metrics.get(gk)) is not None])
    if total == 0:
        return
    pieces = []
    if collided > 0:
        pieces.append(f"{collided} collision(s)")
    if reached > 0:
        pieces.append(f"{reached} passed")
    if closest_gate is not None:
        pieces.append(f"next: Gate #{closest_gate} at {closest_dist:.2f} m ahead")
    if not pieces:
        pieces.append("all passed or not configured")
    parts.append(f"\n**Gates summary** ({total} total): " + ", ".join(pieces) + ".")
    for gid, gkey in gate_defs:
        gx = _sf(metrics.get(gkey))
        if gx is None:
            continue
        col = collisions.get(gid)
        arr = arrivals.get(gid)
        if col is not None:
            parts.append(
                f"  Gate #{gid} (x={gx:.2f} m): COLLISION at step {col.get('step', '?')}."
            )
        elif arr is not None:
            is_open = arr.get("gate_open", False)
            status = "OPEN" if is_open else "CLOSED (contact-filter)"
            parts.append(
                f"  Gate #{gid} (x={gx:.2f} m): passed at step {arr.get('step', '?')} ({status})."
            )

def _load_report(metrics: Dict[str, Any], parts: List[str]):
    structure_mass = _sf(metrics.get("structure_mass"))
    max_mass = _sf(metrics.get("max_structure_mass"), 14.0)
    beam_count = metrics.get("beam_count")
    min_beams = metrics.get("min_beam_count", 4)
    max_beams = metrics.get("max_beam_count", 5)
    mass_items = []
    if structure_mass is not None and max_mass is not None and max_mass > 0:
        mass_pct = _pct(structure_mass, max_mass, 0.0) or 0.0
        if mass_pct > 80:
            mass_items.append(
                f"mass {structure_mass:.2f}/{max_mass:.2f} kg ({mass_pct:.0f}%) ⚠ HIGH"
            )
        elif mass_pct > 50:
            mass_items.append(
                f"mass {structure_mass:.2f}/{max_mass:.2f} kg ({mass_pct:.0f}%) ⚠ elevated"
            )
        else:
            mass_items.append(
                f"mass {structure_mass:.2f}/{max_mass:.2f} kg ({mass_pct:.0f}%)"
            )
    elif structure_mass is not None:
        mass_items.append(f"mass {structure_mass:.2f} kg")
    beam_items = []
    if beam_count is not None:
        bc = int(beam_count)
        if bc < int(min_beams):
            beam_items.append(f"beams {bc} (UNDER min {min_beams})")
        elif bc > int(max_beams):
            beam_items.append(f"beams {bc} (OVER max {max_beams})")
        elif bc == min_beams or bc == max_beams:
            beam_items.append(f"beams {bc} (at limit, range [{min_beams}, {max_beams}])")
        else:
            beam_items.append(f"beams {bc} [allowed {min_beams}–{max_beams}]")
    all_items = mass_items + beam_items
    if all_items:
        parts.append("**Structural load**: " + ", ".join(all_items) + ".")
    else:
        parts.append("**Structural load**: data unavailable.")
    parts.append("**Joints**: N/A (no agent-created structural joints).")

def _energy_report(metrics: Dict[str, Any], parts: List[str]):
    ke_init = _sf(metrics.get("energy_initial_ke"))
    ke_final = _sf(metrics.get("energy_final_ke"))
    speed = _sf(metrics.get("speed"))
    if ke_init is not None and ke_final is not None:
        parts.append(f"**KE**: initial={ke_init:.1f} J → final={ke_final:.1f} J")
        if ke_init > 0:
            eff = _pct(ke_final, ke_init, 0.0) or 0.0
            loss_pct = 100.0 - eff
            parts.append(f"**Energy retention**: {eff:.1f}% (lost {loss_pct:.1f}% = {ke_init - ke_final:.1f} J).")
    elif ke_init is not None:
        parts.append(f"**KE**: initial={ke_init:.1f} J, final=not recorded.")
    elif ke_final is not None:
        parts.append(f"**KE**: final={ke_final:.1f} J, initial=not recorded.")
    else:
        total_mass = _sf(metrics.get("total_mass"))
        if total_mass is not None and speed is not None and total_mass > 0:
            ke_est = 0.5 * total_mass * speed * speed
            parts.append(f"**KE** (estimated): {ke_est:.1f} J (mass={total_mass:.2f} kg, v={speed:.2f} m/s).")
        else:
            parts.append("**KE**: not recorded.")
    _loss_channel_report(metrics, parts)

def _loss_channel_report(metrics: Dict[str, Any], parts: List[str]):
    zones = []
    mud = metrics.get("mud_zone")
    if mud and len(mud) == 2:
        zones.append(f"mud [{mud[0]:.1f}–{mud[1]:.1f}] m (damping)")
    imp = metrics.get("impulse_zone")
    if imp and len(imp) == 2:
        zones.append(f"impulse [{imp[0]:.1f}–{imp[1]:.1f}] m")
    imp2 = metrics.get("impulse2_zone")
    if imp2 and len(imp2) == 2:
        zones.append(f"impulse2 [{imp2[0]:.1f}–{imp2[1]:.1f}] m")
    dec = metrics.get("decel_zone")
    if dec and len(dec) == 2:
        zones.append(f"decel [{dec[0]:.1f}–{dec[1]:.1f}] m (damping)")
    brk = metrics.get("brake_zone")
    if brk and len(brk) == 2:
        zones.append(f"brake [{brk[0]:.1f}–{brk[1]:.1f}] m (damping)")
    if zones:
        parts.append("**Loss zones**: " + ", ".join(zones) + "; gate collision=failure, open gate=no velocity change.")
    else:
        parts.append("**Loss zones**: gate collision=failure, open gate=no velocity change.")

def _constraint_report(metrics: Dict[str, Any], parts: List[str]):
    sm = _sf(metrics.get("structure_mass"))
    max_sm = _sf(metrics.get("max_structure_mass"), 14.0)
    beam_count = metrics.get("beam_count")
    min_beams = metrics.get("min_beam_count", 4)
    max_beams = metrics.get("max_beam_count", 5)
    build_items = []
    if beam_count is not None:
        bc = int(beam_count)
        build_items.append(f"beams={bc} [{min_beams}–{max_beams}] {'✓' if min_beams <= bc <= max_beams else '✗'}")
    if sm is not None and max_sm is not None:
        build_items.append(f"mass={sm:.2f}/{max_sm:.2f} kg {'✓' if sm <= max_sm else '✗'}")
    if build_items:
        parts.append("**Build**: " + ", ".join(build_items) + ".")
    else:
        parts.append("**Build**: data unavailable.")
    fr = (metrics.get("failure_reason") or "")
    if "outside build zone" in fr.lower():
        parts.append("  → Build zone violation detected.")
    parts.append("")
    st_x = _sf(metrics.get("speed_trap_x"), 9.0)
    st_min = _sf(metrics.get("speed_trap_min"), 2.8)
    st_actual = _sf(metrics.get("speed_trap_actual_speed"))
    x = _sf(metrics.get("x"), 0) or 0
    if st_actual is not None:
        st_ok = st_actual >= (st_min or 0)
        margin = st_actual - (st_min or 0)
        near = " ⚠ near limit" if st_ok and 0 <= margin < 0.3 else ""
        parts.append(
            f"  Speed trap (x={st_x:.1f}, v≥{st_min:.2f}): "
            f"{'✓' if st_ok else '✗'} v={st_actual:.2f}{near}."
        )
    elif "speed trap" in fr.lower():
        parts.append(f"  Speed trap (x={st_x:.1f}, v≥{st_min:.2f}): ✗ FAIL.")
    elif x < (st_x or 0):
        pass
    else:
        parts.append(f"  Speed trap (x={st_x:.1f}): passed (no failure triggered).")
    cp_x = _sf(metrics.get("checkpoint_11_x"), 11.0)
    cp_lo = _sf(metrics.get("checkpoint_11_speed_min"), 1.1)
    cp_hi = _sf(metrics.get("checkpoint_11_speed_max"), 2.7)
    cp_actual = _sf(metrics.get("checkpoint_11_actual_speed"))
    if cp_actual is not None:
        cp_ok = (cp_lo or 0) <= cp_actual <= (cp_hi or 999)
        near_cp = ""
        if cp_ok:
            lo_margin = cp_actual - (cp_lo or 0)
            hi_margin = (cp_hi or 0) - cp_actual
            if 0 <= lo_margin < 0.3 or 0 <= hi_margin < 0.3:
                near_cp = " ⚠ near limit"
        parts.append(
            f"  Checkpoint (x={cp_x:.1f}, v∈[{cp_lo:.2f}, {cp_hi:.2f}]): "
            f"{'✓' if cp_ok else '✗'} v={cp_actual:.2f}{near_cp}."
        )
    elif "checkpoint" in fr.lower():
        parts.append(f"  Checkpoint (x={cp_x:.1f}, v∈[{cp_lo:.2f}, {cp_hi:.2f}]): ✗ FAIL.")
    elif x < (cp_x or 0) and (cp_x - x) < 5.0:
        parts.append(f"  Checkpoint (x={cp_x:.1f}): approaching ({cp_x - x:.1f} m ahead).")
    elif x >= (cp_x or 0):
        parts.append(f"  Checkpoint (x={cp_x:.1f}): passed (no failure triggered).")
    gate_defs = [
        (1, "gate_x"),
        (2, "gate2_x"),
        (3, "gate3_x"),
        (4, "gate4_x"),
    ]
    arrivals = {ev.get("gate"): ev for ev in (metrics.get("gate_arrival_events", []) or [])}
    collisions = {ev.get("gate"): ev for ev in (metrics.get("gate_collision_details", []) or [])}
    gate_parts = []
    for gid, gkey in gate_defs:
        gx = _sf(metrics.get(gkey))
        if gx is None:
            continue
        if gid in collisions:
            gate_parts.append(f"G{gid}✗")
        elif gid in arrivals:
            gate_parts.append(f"G{gid}✓")
        elif x < gx:
            pass
        else:
            gate_parts.append(f"G{gid}✓")
    if gate_parts:
        parts.append("  Gates: " + " ".join(gate_parts) + ".")
    tx = _sf(metrics.get("target_x_min"), 11.75)
    ts_min = _sf(metrics.get("target_speed_min"), 0.45)
    ts_max = _sf(metrics.get("target_speed_max"), 2.6)
    speed = _sf(metrics.get("speed"))
    if x is not None and tx is not None:
        target_ok = x >= tx
        if not target_ok and (tx - x) < 3.0:
            parts.append(f"  Target (x≥{tx:.2f}): approaching ({tx - x:.2f} m remaining).")
    success = bool(metrics.get("success"))
    failed = bool(metrics.get("failed"))
    if success:
        parts.append("  → All constraints satisfied.")
    elif failed:
        parts.append(f"  → FAILURE: {fr or 'constraint violated'}.")

def _numerical_health_report(metrics: Dict[str, Any], parts: List[str]):
    issues: List[str] = []
    for key, label in [
        ("x", "cart x"),
        ("speed", "cart speed"),
        ("vx", "cart vx"),
        ("vy", "cart vy"),
        ("energy_initial_ke", "initial KE"),
        ("speed_trap_actual_speed", "speed trap speed"),
        ("checkpoint_11_actual_speed", "checkpoint speed"),
    ]:
        val = metrics.get(key)
        if val is not None and _is_bad(val):
            issues.append(f"NaN/Inf in `{label}` = {val}")
    peak = _sf(metrics.get("peak_speed"))
    speed = _sf(metrics.get("speed"))
    if (peak is not None and peak > 100.0) or (speed is not None and speed > 100.0):
        v = peak if (peak is not None and peak > 100.0) else speed
        issues.append(f"Extreme speed: {v:.1f} m/s > 100 m/s — possible solver divergence.")
    for col in (metrics.get("gate_collision_details", []) or []):
        ang = col.get("gate_angle_rad")
        if ang is not None and _is_bad(ang):
            issues.append(f"Gate #{col.get('gate', '?')} collision angle is NaN.")
    step_count = int(metrics.get("step_count", 0))
    max_steps = int(metrics.get("max_steps", 0))
    if (
        max_steps > 0
        and step_count >= max_steps - 1
        and not metrics.get("success")
        and not metrics.get("failed")
    ):
        spd = _sf(metrics.get("speed"), 0.0) or 0.0
        x = _sf(metrics.get("x"), 0.0) or 0.0
        if spd < 0.01:
            issues.append(
                f"Solver stall: {max_steps} steps exhausted, cart nearly stationary "
                f"(v={spd:.4f} m/s, x={x:.2f} m)."
            )
        else:
            issues.append(
                f"Step limit exhausted: {step_count}/{max_steps} steps without terminal outcome "
                f"(v={spd:.3f} m/s, x={x:.2f} m)."
            )
    trace = metrics.get("speed_trace", []) or []
    for pt in trace:
        for field in ("x", "speed"):
            v = pt.get(field)
            if v is not None and _is_bad(v):
                issues.append(
                    f"Trace NaN at step {pt.get('step', '?')}: `{field}` = {v}."
                )
                break
    if not issues:
        parts.append("No numerical anomalies detected.")
    else:
        parts.append(f"{len(issues)} issue(s):")
        for issue in issues:
            parts.append(f"  • {issue}")
