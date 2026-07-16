from typing import Dict, Any, List, Optional

import math

def _safe_float(val: Any, default: Optional[float] = None) -> Optional[float]:
    if val is None:
        return default
    try:
        f = float(val)
        return f if math.isfinite(f) else default
    except (TypeError, ValueError):
        return default

def _is_nonfinite(x: Any) -> bool:
    try:
        return not math.isfinite(float(x))
    except (TypeError, ValueError):
        return False

def _fmt_margin(val: Any, limit: Any, unit: str = "m") -> str:
    try:
        v = float(val)
        li = float(limit)
        diff = v - li
        sign = "+" if diff >= 0 else ""
        direction = "above" if diff >= 0 else "below"
        return f"{sign}{diff:.3f} {unit} {direction} limit ({li:.3f} {unit})"
    except (TypeError, ValueError):
        return f"{val} vs limit {limit}"

def _fmt_pct(val: Any, limit: Any) -> str:
    try:
        v = float(val)
        li = float(limit)
        pct = v / li * 100.0 if li > 0 else 0.0
        return f"{pct:.1f}% of limit ({li:.2f} kg)"
    except (TypeError, ValueError):
        return f"{val} / {limit}"

def _safe_fmt(val: Any, fmt: str = ".3f") -> str:
    try:
        f = float(val)
        if not math.isfinite(f):
            return str(val)
        return format(f, fmt)
    except (TypeError, ValueError):
        return "—"

def _section_energy(metrics: Dict[str, Any]) -> List[str]:
    parts: List[str] = []
    parts.append("### 1. Energy Flow\n")
    init_tot = _safe_float(metrics.get("energy_initial_total"))
    cur_tot = _safe_float(metrics.get("energy_total"), 0.0) or 0.0
    loss_pct = _safe_float(metrics.get("energy_loss_pct"), 0.0) or 0.0
    if init_tot is not None and init_tot > 0:
        parts.append(
            f"Energy: {init_tot:.0f} J → {cur_tot:.0f} J, "
            f"lost {loss_pct:.0f}% (efficiency {100.0 - loss_pct:.0f}%)"
        )
    damp_coeff = _safe_float(metrics.get("energy_damping_coeff_est"))
    init_vx = _safe_float(metrics.get("initial_vx"))
    target_x = _safe_float(metrics.get("right_platform_start_x"), 26.0)
    spawn_x = _safe_float(metrics.get("jumper_spawn_x"), 5.0)
    if damp_coeff is not None and damp_coeff > 0.0001:
        t_half = math.log(2) / damp_coeff
        parts.append(
            f"Damping λ ≈ {damp_coeff:.4f} s⁻¹ (v halves every {t_half:.2f} s)"
        )
        if init_vx is not None and abs(init_vx) > 0.001 and target_x is not None:
            dist_needed = max(0.0, target_x - spawn_x)
            min_vx = dist_needed * damp_coeff
            vx_actual = abs(init_vx)
            parts.append(
                f"Required launch vx ≥ {min_vx:.1f} m/s to reach x={target_x:.0f} m "
                f"(actual initial vx = {vx_actual:.1f} m/s, "
                f"factor {vx_actual / max(min_vx, 0.001):.1f}×)"
            )
    elif damp_coeff is not None:
        parts.append(f"Damping near-zero — no significant viscous drag")
    peak_speed = _safe_float(metrics.get("peak_speed"))
    if peak_speed is not None:
        parts.append(f"Peak speed: {peak_speed:.1f} m/s")
    return parts

def _section_temporal(metrics: Dict[str, Any]) -> List[str]:
    parts: List[str] = []
    parts.append("### 2. Temporal Event Chronology\n")
    events = metrics.get("trajectory_events")
    if not isinstance(events, list) or not events:
        parts.append("No temporal events recorded (simulation duration may be too brief).")
        return parts
    parts.append("| Step | Event | Details |")
    parts.append("|------|-------|---------|")
    for ev in events:
        step = ev.get("step", "?")
        ev_type = ev.get("event", "?")
        if ev_type == "launch":
            details = (
                f"Jumper launched: v = ({_safe_fmt(ev.get('vx'), '.3f')}, "
                f"{_safe_fmt(ev.get('vy'), '.3f')}) m/s "
                f"from ({_safe_fmt(ev.get('px'), '.3f')}, "
                f"{_safe_fmt(ev.get('py'), '.3f')}) m"
            )
        elif ev_type == "vx_reversal":
            details = (
                f"Horizontal velocity reversed: "
                f"{_safe_fmt(ev.get('prev_vx'), '.3f')} → "
                f"{_safe_fmt(ev.get('new_vx'), '.3f')} m/s "
                f"at ({_safe_fmt(ev.get('px'), '.3f')}, "
                f"{_safe_fmt(ev.get('py'), '.3f')}) m"
            )
        elif ev_type == "vy_reversal":
            details = (
                f"Vertical velocity reversed: "
                f"{_safe_fmt(ev.get('prev_vy'), '.3f')} → "
                f"{_safe_fmt(ev.get('new_vy'), '.3f')} m/s "
                f"at ({_safe_fmt(ev.get('px'), '.3f')}, "
                f"{_safe_fmt(ev.get('py'), '.3f')}) m"
            )
        elif ev_type == "tumbling_onset":
            details = (
                f"Angular velocity crossed 3.0 rad/s threshold: "
                f"{_safe_fmt(ev.get('angular_vel'), '.3f')} rad/s"
            )
        else:
            details = str(ev)
        parts.append(f"| {step} | {ev_type} | {details} |")
    parts.append("\n**Event cascade interpretation**:")
    cascade_steps: List[str] = []
    cascade_idx = 0
    launch_ev = None
    vy_rev = None
    vx_rev = None
    tumble = None
    for ev in events:
        t = ev.get("event")
        if t == "launch":
            launch_ev = ev
        elif t == "vy_reversal" and vy_rev is None:
            vy_rev = ev
        elif t == "vx_reversal" and vx_rev is None:
            vx_rev = ev
        elif t == "tumbling_onset" and tumble is None:
            tumble = ev
    final_step = metrics.get("step_count", 0)
    init_step = _safe_float(metrics.get("initial_step"))
    fr = metrics.get("failure_reason", "")
    failed = metrics.get("failed", False)
    success = metrics.get("success", False)
    if launch_ev:
        cascade_idx += 1
        lstep = launch_ev.get("step", "?")
        cascade_steps.append(
            f"{cascade_idx}. **Launch** at step {lstep}: "
            f"v = ({_safe_fmt(launch_ev.get('vx'), '.3f')}, "
            f"{_safe_fmt(launch_ev.get('vy'), '.3f')}) m/s"
        )
    if vy_rev:
        cascade_idx += 1
        vstep = vy_rev.get("step", "?")
        cascade_steps.append(
            f"{cascade_idx}. **Apex** at step {vstep}: "
            f"vertical velocity reversed "
            f"({_safe_fmt(vy_rev.get('prev_vy'), '.3f')} → "
            f"{_safe_fmt(vy_rev.get('new_vy'), '.3f')} m/s) — "
            f"jumper begins descending at "
            f"({_safe_fmt(vy_rev.get('px'), '.3f')}, "
            f"{_safe_fmt(vy_rev.get('py'), '.3f')}) m"
        )
    if vx_rev:
        cascade_idx += 1
        vstep = vx_rev.get("step", "?")
        cascade_steps.append(
            f"{cascade_idx}. **Forward motion reversal** at step {vstep}: "
            f"horizontal velocity reversed "
            f"({_safe_fmt(vx_rev.get('prev_vx'), '.3f')} → "
            f"{_safe_fmt(vx_rev.get('new_vx'), '.3f')} m/s) — "
            f"jumper moving backward at "
            f"({_safe_fmt(vx_rev.get('px'), '.3f')}, "
            f"{_safe_fmt(vx_rev.get('py'), '.3f')}) m"
        )
    if tumble:
        cascade_idx += 1
        tstep = tumble.get("step", "?")
        cascade_steps.append(
            f"{cascade_idx}. **Tumbling onset** at step {tstep}: "
            f"angular velocity = {_safe_fmt(tumble.get('angular_vel'), '.3f')} rad/s"
        )
    cascade_idx += 1
    if failed and fr:
        cascade_steps.append(
            f"{cascade_idx}. **Terminal failure** at step {final_step}: "
            f"{fr}"
        )
    elif success:
        cascade_steps.append(
            f"{cascade_idx}. **Success** at step {final_step}: "
            f"jumper reached right platform"
        )
    else:
        cascade_steps.append(
            f"{cascade_idx}. **Stop** at step {final_step}: "
            f"simulation ended without explicit success or failure"
        )
    for cs in cascade_steps:
        parts.append(cs)
    if init_step is not None:
        elapsed = final_step - init_step
        parts.append(
            f"\n**Timeline span**: step {int(init_step)} → step {final_step} "
            f"({elapsed} steps, {elapsed / 60.0:.3f} s at 60 FPS)"
        )
    return parts

def _section_spatial(metrics: Dict[str, Any]) -> List[str]:
    parts: List[str] = []
    parts.append("### 3. Spatial Margin Analysis\n")
    px = _safe_float(metrics.get("jumper_x"), 0.0) or 0.0
    py = _safe_float(metrics.get("jumper_y"), 0.0) or 0.0
    vx = _safe_float(metrics.get("jumper_vx"), 0.0) or 0.0
    vy = _safe_float(metrics.get("jumper_vy"), 0.0) or 0.0
    spawn_x = _safe_float(metrics.get("jumper_spawn_x"), 5.0) or 5.0
    jhw = _safe_float(metrics.get("jumper_half_w"), 0.4) or 0.4
    jhh = _safe_float(metrics.get("jumper_half_h"), 0.3) or 0.3
    parts.append(
        f"**Jumper center**: ({px:.3f}, {py:.3f}) m "
        f"(half-extents: ±{jhw:.3f} m horiz, ±{jhh:.3f} m vert)"
    )
    parts.append(
        f"**Jumper velocity**: ({vx:.3f}, {vy:.3f}) m/s, "
        f"speed = {math.hypot(vx, vy):.3f} m/s"
    )
    pit_fail_y = _safe_float(metrics.get("pit_fail_y"), 0.0)
    if pit_fail_y is not None:
        pit_margin = py - pit_fail_y
        bottom_edge = py - jhh
        bottom_margin = bottom_edge - pit_fail_y
        if pit_margin <= 0:
            status = "⚠ IN PIT"
        else:
            status = "SAFE"
        parts.append(
            f"\n**Pit clearance (y)**: {status} — "
            f"jumper center y = {py:.3f} m, "
            f"bottom edge y = {bottom_edge:.3f} m, "
            f"pit failure at y < {pit_fail_y:.2f} m — "
            f"center margin: {pit_margin:+.3f} m, "
            f"edge margin: {bottom_margin:+.3f} m"
        )
    slot_approach = metrics.get("slot_closest_approach")
    slot_defs = metrics.get("slot_definitions")
    if isinstance(slot_defs, list) and slot_defs:
        sorted_slots = sorted(
            slot_defs,
            key=lambda sd: _safe_float(sd.get("x_min"), 9999.0) or 9999.0,
        )
        reached_slots: List[str] = []
        unreached_slots: List[str] = []
        for sd in sorted_slots:
            sn = sd.get("slot_num", "?")
            fx = _safe_float(sd.get("floor_y"))
            cx = _safe_float(sd.get("ceil_y"))
            xmin = _safe_float(sd.get("x_min"))
            xmax = _safe_float(sd.get("x_max"))
            sa = None
            if isinstance(slot_approach, dict):
                sa = slot_approach.get(f"slot_{sn}")
            if sa is not None:
                fm = _safe_float(sa.get("floor_margin"))
                cm = _safe_float(sa.get("ceil_margin"))
                floor_status = "PASS" if fm is not None and fm >= 0 else "FAIL"
                ceil_status = "PASS" if cm is not None and cm >= 0 else "FAIL"
                overall = "PASS" if floor_status == "PASS" and ceil_status == "PASS" else "FAIL"
                near_thresh = jhh * 0.2
                f_near = " ⚠ NEAR" if fm is not None and 0 <= fm < near_thresh else ""
                c_near = " ⚠ NEAR" if cm is not None and 0 <= cm < near_thresh else ""
                reached_slots.append(
                    f"Slot {sn} [{fx:.1f}-{cx:.1f}m]: {overall} "
                    f"(floor {fm:+.2f}m{f_near}, ceil {cm:+.2f}m{c_near})"
                )
            elif xmin is not None:
                if px < xmin:
                    unreached_slots.append(
                        f"Slot {sn} [{fx:.1f}-{cx:.1f}m]: UNTESTED "
                        f"(at x={xmin:.1f}m, {xmin - px:.1f}m ahead)"
                    )
                elif px > (xmax or float("inf")):
                    reached_slots.append(f"Slot {sn} [{fx:.1f}-{cx:.1f}m]: PASSED (behind jumper)")
                else:
                    reached_slots.append(f"Slot {sn}: IN PROGRESS")
        if reached_slots:
            parts.append("\n**Slot clearance**:")
            for s in reached_slots:
                parts.append(f"  - {s}")
        if unreached_slots:
            distances = []
            for us in unreached_slots:
                import re
                m = re.search(r'([\d.]+)m ahead', us)
                if m:
                    distances.append(float(m.group(1)))
            dist_range = ""
            if distances:
                dist_range = f" ({min(distances):.0f}-{max(distances):.0f} m ahead)"
            parts.append(
                f"  - {len(unreached_slots)}/{len(sorted_slots)} slots untested{dist_range}"
            )
    target_x = _safe_float(metrics.get("right_platform_start_x"), 26.0)
    if target_x is not None:
        tmargin = px - target_x
        if tmargin >= 0:
            parts.append(
                f"\n**Target (right platform)**: REACHED — "
                f"jumper x = {px:.3f} m ≥ {target_x:.2f} m "
                f"(margin: {tmargin:+.3f} m)"
            )
        else:
            dist_remaining = -tmargin
            parts.append(
                f"\n**Target (right platform)**: NOT REACHED — "
                f"jumper x = {px:.3f} m, target x ≥ {target_x:.2f} m "
                f"({dist_remaining:.3f} m remaining, "
                f"{px - spawn_x:.3f} m traveled from spawn)"
            )
    return parts

def _section_constraints(metrics: Dict[str, Any]) -> List[str]:
    parts: List[str] = []
    parts.append("### 4. Constraints\n")
    mass = _safe_float(metrics.get("structure_mass"), 0.0) or 0.0
    max_mass = _safe_float(metrics.get("max_structure_mass"), 180.0) or 180.0
    mass_pct = (mass / max_mass * 100.0) if max_mass > 0 else 0.0
    mass_status = "PASS" if mass <= max_mass else "FAIL"
    parts.append(
        f"Mass: {mass_status} — {mass:.1f}/{max_mass:.0f} kg "
        f"({mass_pct:.0f}% used, {max_mass - mass:.0f} kg remaining)"
    )
    success = metrics.get("success", False)
    failed = metrics.get("failed", False)
    fr = metrics.get("failure_reason")
    if success:
        parts.append("Result: ✅ SUCCESS")
    elif failed:
        parts.append(f"Result: ❌ FAILURE — {fr}")
    else:
        parts.append("Result: ⏳ IN PROGRESS")
    return parts

def _section_health(metrics: Dict[str, Any]) -> List[str]:
    parts: List[str] = []
    parts.append("### 5. Numerical Health\n")
    vx = _safe_float(metrics.get("jumper_vx"))
    vy = _safe_float(metrics.get("jumper_vy"))
    speed = _safe_float(metrics.get("jumper_speed"), 0.0) or 0.0
    ang_vel = _safe_float(metrics.get("angular_velocity"), 0.0) or 0.0
    peak_speed = _safe_float(metrics.get("peak_speed"), speed)
    peak_ang = _safe_float(metrics.get("peak_angular_vel"), abs(ang_vel))
    peak_speed_step = metrics.get("peak_speed_step")
    peak_ang_step = metrics.get("peak_angular_vel_step")
    flags: List[str] = []
    for label, val in [
        ("jumper_x", metrics.get("jumper_x")),
        ("jumper_y", metrics.get("jumper_y")),
        ("jumper_vx", metrics.get("jumper_vx")),
        ("jumper_vy", metrics.get("jumper_vy")),
        ("angular_velocity", metrics.get("angular_velocity")),
        ("angle", metrics.get("angle")),
    ]:
        if _is_nonfinite(val):
            flags.append(f"🔴 **NaN/Inf detected** in `{label}` = {val}")
    if peak_speed is not None:
        if peak_speed > 500.0:
            flags.append(
                f"🔴 **EXTREME SPEED**: peak = {peak_speed:.1f} m/s (> 500) "
                f"at step {peak_speed_step}"
            )
        elif peak_speed > 100.0:
            flags.append(
                f"🟡 **VERY HIGH SPEED**: peak = {peak_speed:.1f} m/s (> 100) "
                f"at step {peak_speed_step}"
            )
        elif peak_speed > 50.0:
            flags.append(
                f"🟢 **HIGH SPEED**: peak = {peak_speed:.1f} m/s (> 50) "
                f"at step {peak_speed_step}"
            )
    if peak_ang is not None:
        if peak_ang > 10.0:
            flags.append(
                f"🔴 **EXTREME TUMBLING**: peak |ω| = {peak_ang:.1f} rad/s (> 10) "
                f"at step {peak_ang_step}"
            )
        elif peak_ang > 5.0:
            flags.append(
                f"🟡 **SIGNIFICANT TUMBLING**: peak |ω| = {peak_ang:.1f} rad/s (> 5) "
                f"at step {peak_ang_step}"
            )
        elif peak_ang > 3.0:
            flags.append(
                f"🟢 **TUMBLING OBSERVED**: peak |ω| = {peak_ang:.1f} rad/s (> 3) "
                f"at step {peak_ang_step}"
            )
    step_count = metrics.get("step_count", 0)
    max_steps = metrics.get("max_steps")
    if (
        max_steps is not None
        and isinstance(max_steps, (int, float))
        and max_steps > 0
        and step_count >= max_steps - 1
        and not metrics.get("success")
        and not metrics.get("failed")
    ):
        vx_f = _safe_float(metrics.get("jumper_vx"), 0.0) or 0.0
        vy_f = _safe_float(metrics.get("jumper_vy"), 0.0) or 0.0
        speed_f = math.hypot(vx_f, vy_f)
        if speed_f < 0.01:
            flags.append(
                f"🔴 **SOLVER STALL**: simulation exhausted {max_steps} steps. "
                f"Jumper nearly stationary (speed = {speed_f:.3f} m/s) — "
                f"combined wind + damping forces have pinned the jumper."
            )
        else:
            flags.append(
                f"🟡 **STEP LIMIT EXHAUSTED**: {step_count}/{max_steps} steps "
                f"without terminal outcome. Jumper still moving "
                f"(speed = {speed_f:.3f} m/s)."
            )
    traj_events = metrics.get("trajectory_events")
    if isinstance(traj_events, list):
        for ev in traj_events:
            if ev.get("event") == "vx_reversal":
                flags.append(
                    f"🟡 **FORWARD MOTION REVERSED**: "
                    f"horizontal velocity changed sign at step {ev.get('step')} — "
                    f"wind or extreme damping is pushing jumper backward"
                )
                break
    if flags:
        for f in flags:
            parts.append(f"- {f}")
    else:
        parts.append("- ✅ No numerical anomalies")
    return parts

def format_task_metrics(metrics: Dict[str, Any]) -> List[str]:
    if not metrics:
        return ["**No metrics available**."]
    parts: List[str] = []
    parts.append("## D-02 Jumper — Forensic Diagnostic Report\n")
    success = metrics.get("success", False)
    failed = metrics.get("failed", False)
    fr = metrics.get("failure_reason")
    sc = metrics.get("step_count")
    progress = _safe_float(metrics.get("progress"), 0.0) or 0.0
    max_steps = metrics.get("max_steps")
    step_info = f"{sc}"
    if max_steps is not None:
        step_info += f"/{max_steps}"
    if success:
        parts.append(f"**Outcome**: ✅ SUCCESS (score 100.0) at step {step_info}")
    elif failed:
        parts.append(f"**Outcome**: ❌ FAILURE at step {step_info} — {fr}")
    else:
        parts.append(
            f"**Outcome**: ⏳ IN PROGRESS at step {step_info}, "
            f"{progress:.1f}% horizontal progress toward target"
        )
    px = _safe_float(metrics.get("jumper_x"))
    py = _safe_float(metrics.get("jumper_y"))
    vx = _safe_float(metrics.get("jumper_vx"))
    vy = _safe_float(metrics.get("jumper_vy"))
    if px is not None and py is not None:
        vx_s = f"{vx:.3f}" if vx is not None else "—"
        vy_s = f"{vy:.3f}" if vy is not None else "—"
        parts.append(
            f"**Terminal state**: pos = ({px:.3f}, {py:.3f}) m, "
            f"vel = ({vx_s}, {vy_s}) m/s"
        )
    spawn_x = _safe_float(metrics.get("jumper_spawn_x"), 5.0)
    if px is not None and spawn_x is not None:
        traveled = px - spawn_x
        parts.append(
            f"**Horizontal travel**: {traveled:+.3f} m from spawn "
            f"(start at x = {spawn_x:.2f} m, current x = {px:.3f} m)"
        )
    section_builders = [
        ("energy", _section_energy),
        ("temporal", _section_temporal),
        ("spatial", _section_spatial),
        ("constraints", _section_constraints),
        ("health", _section_health),
    ]
    for name, builder in section_builders:
        try:
            result = builder(metrics)
            if result:
                parts.extend(result)
        except Exception as e:
            parts.append(f"*(Diagnostic section `{name}` unavailable: {type(e).__name__}: {e})*")
    return parts
