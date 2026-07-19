from __future__ import annotations

import math

from typing import Any, Dict, List, Optional

import sys as _sys

_STORE_ATTR = "_e03_feedback_prev_metrics"

def _as_float(x: Any) -> Optional[float]:
    try:
        return float(x)
    except (TypeError, ValueError):
        return None

def _finite(x: Optional[float]) -> bool:
    return x is not None and math.isfinite(x)

def _safe_fmt(x: Optional[float], decimals: int = 3) -> str:
    if x is None:
        return "N/A"
    if not math.isfinite(x):
        return str(x)
    return f"{x:.{decimals}f}"

def _format_events(metrics: Dict[str, Any]) -> List[str]:
    parts: List[str] = ["### 1. Events & Zones"]
    zone_data = metrics.get("zone_forensics")
    if not isinstance(zone_data, dict):
        return parts + ["No zone data.", ""]
    zone_manifest = [
        ("momentum_drain",   "Momentum-Drain"),
        ("checkpoint_a",     "Checkpoint A"),
        ("thrust_scale",     "Thrust-Scale"),
        ("oscillating_wind", "Oscillating-Wind"),
        ("speed_penalty",    "Speed-Penalty"),
        ("checkpoint_b",     "Checkpoint B"),
        ("vertical_reverse", "Vertical-Reverse"),
        ("target_zone",      "Target"),
    ]
    entered: List[str] = []
    unentered = 0
    for key, label in zone_manifest:
        z = zone_data.get(key)
        if not isinstance(z, dict):
            continue
        if bool(z.get("entered")):
            entry_step = z.get("entry_step", "?")
            x_at = _as_float(z.get("x_at_entry"))
            spd_at = _as_float(z.get("speed_at_entry"))
            info = f"step {entry_step}"
            if x_at is not None:
                info += f", x={_safe_fmt(x_at, 4)}"
            if spd_at is not None:
                info += f", v={_safe_fmt(spd_at, 3)} m/s"
            exited = bool(z.get("exited"))
            if exited:
                exit_step = z.get("exit_step", "?")
                spd_ex = _as_float(z.get("speed_at_exit"))
                exit_info = f"exited step {exit_step}"
                if spd_at is not None and spd_ex is not None and spd_at > 0.001:
                    delta = spd_ex - spd_at
                    exit_info += f", Δv={delta:+.3f} m/s"
                entered.append(f"- [{label}] ENTERED {info} → {exit_info}")
            else:
                entered.append(f"- [{label}] ENTERED {info} → still inside")
        else:
            unentered += 1
    if entered:
        parts.extend(entered)
    if unentered > 0:
        tail = f"{unentered} other zone{'s' if unentered > 1 else ''} not entered"
        if not entered:
            parts.append(f"- No zones entered ({unentered} total)")
        else:
            parts.append(f"- {tail}")
    peak_spd = _as_float(zone_data.get("peak_systemic_speed"))
    if peak_spd is not None:
        parts.append(f"- Peak speed: {_safe_fmt(peak_spd, 4)} m/s")
    return parts + [""]

def _format_position(metrics: Dict[str, Any]) -> List[str]:
    parts: List[str] = ["### 2. Position & Margins"]
    sx = _as_float(metrics.get("sled_x"))
    sy = _as_float(metrics.get("sled_y"))
    if sx is None or sy is None:
        return parts + ["Position not available.", ""]
    parts.append(f"Sled: x={_safe_fmt(sx, 4)}, y={_safe_fmt(sy, 4)} m")
    tx0 = _as_float(metrics.get("target_x_min"))
    tx1 = _as_float(metrics.get("target_x_max"))
    ty0 = _as_float(metrics.get("target_y_min"))
    ty1 = _as_float(metrics.get("target_y_max"))
    if all(_finite(v) for v in (tx0, tx1, ty0, ty1)):
        margin_parts = []
        if sx < tx0:
            margin_parts.append(f"x={_safe_fmt(tx0 - sx, 3)} m short")
        elif sx > tx1:
            margin_parts.append(f"x={_safe_fmt(sx - tx1, 3)} m past")
        else:
            margin_parts.append("x OK")
        if sy < ty0:
            margin_parts.append(f"y={_safe_fmt(ty0 - sy, 3)} m below")
        elif sy > ty1:
            margin_parts.append(f"y={_safe_fmt(sy - ty1, 3)} m above")
        else:
            margin_parts.append("y OK")
        dt = _as_float(metrics.get("distance_to_target"))
        pp = _as_float(metrics.get("progress_pct"))
        extra = []
        if dt is not None:
            extra.append(f"dist={_safe_fmt(dt, 3)} m")
        if pp is not None:
            extra.append(f"{pp:.1f}%")
        parts.append(
            f"Target [{_safe_fmt(tx0, 2)},{_safe_fmt(tx1, 2)}]×[{_safe_fmt(ty0, 2)},{_safe_fmt(ty1, 2)}]: "
            + ", ".join(margin_parts)
            + (" | " + " | ".join(extra) if extra else "")
        )
    ca_reached = bool(metrics.get("checkpoint_a_reached"))
    cb_reached = bool(metrics.get("checkpoint_b_reached"))
    ca_lo = _as_float(metrics.get("checkpoint_a_x_lo"))
    ca_hi = _as_float(metrics.get("checkpoint_a_x_hi"))
    cb_lo = _as_float(metrics.get("checkpoint_b_x_lo"))
    cb_hi = _as_float(metrics.get("checkpoint_b_x_hi"))
    ca_ylo = _as_float(metrics.get("checkpoint_a_y_lo"))
    ca_yhi = _as_float(metrics.get("checkpoint_a_y_hi"))
    cb_ylo = _as_float(metrics.get("checkpoint_b_y_lo"))
    cb_yhi = _as_float(metrics.get("checkpoint_b_y_hi"))
    if ca_ylo is None or ca_yhi is None:
        tb = metrics.get("terrain_bounds", {}) or {}
        cpz = tb.get("checkpoint_zone", {}) or {}
        ca_ylo = _as_float(cpz.get("y_min", 3.8))
        ca_yhi = _as_float(cpz.get("y_max", 4.5))
    if cb_ylo is None or cb_yhi is None:
        tb = metrics.get("terrain_bounds", {}) or {}
        cpz_b = tb.get("checkpoint_b_zone", {}) or {}
        cb_ylo = _as_float(cpz_b.get("y_min", 2.5))
        cb_yhi = _as_float(cpz_b.get("y_max", 3.2))
    def _cp_line(label, reached, lo, hi, ylo, yhi):
        if reached:
            return f"{label}: REACHED"
        if lo is None:
            return f"{label}: bounds unknown"
        if sx < lo:
            y_str = ""
            if ylo is not None and yhi is not None:
                y_str = f" y∈[{_safe_fmt(ylo, 2)},{_safe_fmt(yhi, 2)}]"
            return f"{label} [{_safe_fmt(lo, 2)},{_safe_fmt(hi, 2) if hi else '?'}]{y_str}: {_safe_fmt(lo - sx, 3)} m ahead"
        if hi is not None and sx > hi:
            return f"{label}: OVERSHOT ({_safe_fmt(sx - hi, 3)} m past x_max)"
        if sy is not None and ylo is not None:
            if sy < ylo:
                return f"{label}: x in range but y={_safe_fmt(sy, 3)} below required [{_safe_fmt(ylo, 2)},{_safe_fmt(yhi, 2) if yhi else '?'}]"
            elif yhi is not None and sy > yhi:
                return f"{label}: x in range but y={_safe_fmt(sy, 3)} above required [{_safe_fmt(ylo, 2)},{_safe_fmt(yhi, 2)}]"
        return f"{label}: x in range, y status unknown"
    parts.append(_cp_line("Checkpoint A", ca_reached, ca_lo, ca_hi, ca_ylo, ca_yhi))
    if ca_reached or cb_reached or not ca_reached:
        parts.append(_cp_line("Checkpoint B", cb_reached, cb_lo, cb_hi, cb_ylo, cb_yhi))
    zone_data = metrics.get("zone_forensics") or {}
    zone_keys = [
        ("momentum_drain", "Momentum-Drain", "momentum_drain_x_lo"),
        ("thrust_scale", "Thrust-Scale", "thrust_scale_x_lo"),
        ("speed_penalty", "Speed-Penalty", "speed_penalty_x_lo"),
        ("vertical_reverse", "Vertical-Reverse", "vertical_reverse_x_lo"),
    ]
    best_label, best_dist = None, None
    for zkey, zlabel, lo_key in zone_keys:
        z = zone_data.get(zkey) if isinstance(zone_data, dict) else None
        if isinstance(z, dict) and bool(z.get("entered")):
            continue
        z_lo = _as_float(metrics.get(lo_key))
        if z_lo is None:
            continue
        if sx < z_lo:
            d = z_lo - sx
            if best_dist is None or d < best_dist:
                best_label, best_dist = zlabel, d
    if best_label is not None and best_dist is not None:
        parts.append(f"Nearest unentered zone: {best_label} at x={_safe_fmt(sx + best_dist, 2)} ({_safe_fmt(best_dist, 3)} m ahead)")
    return parts + [""]

def _format_thrust(metrics: Dict[str, Any]) -> List[str]:
    parts: List[str] = ["### 3. Thrust"]
    tf = metrics.get("thrust_forensics")
    if not isinstance(tf, dict):
        return parts + ["No thrust data.", ""]
    cmd_fx = _as_float(tf.get("commanded_fx"))
    cmd_fy = _as_float(tf.get("commanded_fy"))
    del_fx = _as_float(tf.get("delivered_fx"))
    del_fy = _as_float(tf.get("delivered_fy"))
    cmd_mag = _as_float(tf.get("commanded_magnitude"))
    del_mag = _as_float(tf.get("delivered_magnitude"))
    max_thrust = _as_float(tf.get("max_commandable_thrust"))
    sat_steps = tf.get("thrust_saturation_steps", 0)
    total_steps = tf.get("total_steps", 1)
    if all(_finite(v) for v in (cmd_fx, cmd_fy, del_fx, del_fy)):
        ratio = del_mag / cmd_mag if (cmd_mag and cmd_mag > 0.001) else 1.0
        parts.append(
            f"Cmd: ({_safe_fmt(cmd_fx, 1)},{_safe_fmt(cmd_fy, 1)}) mag={_safe_fmt(cmd_mag, 1)} N → "
            f"Del: ({_safe_fmt(del_fx, 1)},{_safe_fmt(del_fy, 1)}) mag={_safe_fmt(del_mag, 1)} N | "
            f"ratio={ratio:.3f}"
        )
    zone_data = metrics.get("zone_forensics") or {}
    peak_thrust = _as_float((zone_data or {}).get("peak_thrust_magnitude") if isinstance(zone_data, dict) else None)
    if peak_thrust is not None:
        line = f"Peak thrust: {_safe_fmt(peak_thrust, 1)} N"
        if max_thrust is not None and max_thrust > 0.01:
            line += f" ({100.0 * peak_thrust / max_thrust:.0f}% of max {_safe_fmt(max_thrust, 1)} N)"
        parts.append(line)
    if isinstance(sat_steps, (int, float)) and sat_steps > 0:
        total = max(int(total_steps), 1)
        sat_pct = 100.0 * float(sat_steps) / float(total)
        note = ""
        if sat_pct > 50:
            note = " — **ceiling contact > 50%**"
        elif sat_pct > 20:
            note = " — significant"
        parts.append(f"Saturation: {int(sat_steps)}/{total} steps ({sat_pct:.1f}%){note}")
    else:
        parts.append("Saturation: none")
    sx = _as_float(metrics.get("sled_x"))
    if sx is not None:
        ts_lo = _as_float(metrics.get("thrust_scale_x_lo"))
        ts_hi = _as_float(metrics.get("thrust_scale_x_hi"))
        vr_lo = _as_float(metrics.get("vertical_reverse_x_lo"))
        vr_hi = _as_float(metrics.get("vertical_reverse_x_hi"))
        active = []
        if ts_lo is not None and ts_hi is not None and ts_lo <= sx <= ts_hi:
            active.append("Thrust-Scale")
        if vr_lo is not None and vr_hi is not None and vr_lo <= sx <= vr_hi:
            active.append("Vertical-Reverse")
        if active:
            parts.append(f"Zone modifiers active at position: {', '.join(active)}")
    return parts + [""]

def _format_energy(metrics: Dict[str, Any]) -> List[str]:
    parts: List[str] = ["### 4. Energy"]
    vx = _as_float(metrics.get("velocity_x"))
    vy = _as_float(metrics.get("velocity_y"))
    vm = _as_float(metrics.get("velocity_magnitude"))
    zone_data = metrics.get("zone_forensics") or {}
    peak_spd = _as_float(
        (zone_data or {}).get("peak_systemic_speed") if isinstance(zone_data, dict) else None
    )
    if vm is not None:
        parts.append(f"Final speed: {_safe_fmt(vm, 4)} m/s (vx={_safe_fmt(vx, 3)}, vy={_safe_fmt(vy, 3)})")
    if peak_spd is not None:
        if vm is not None and peak_spd > 0.001:
            retention = 100.0 * vm / peak_spd
            parts.append(f"Peak speed: {_safe_fmt(peak_spd, 4)} m/s | Retention: {retention:.1f}%")
        else:
            parts.append(f"Peak speed: {_safe_fmt(peak_spd, 4)} m/s")
    if isinstance(zone_data, dict):
        energy_zones = [
            ("momentum_drain", "Momentum-Drain"),
            ("thrust_scale", "Thrust-Scale"),
            ("oscillating_wind", "Oscillating-Wind"),
            ("speed_penalty", "Speed-Penalty"),
            ("vertical_reverse", "Vertical-Reverse"),
        ]
        for key, label in energy_zones:
            z = zone_data.get(key)
            if not isinstance(z, dict) or not bool(z.get("entered")):
                continue
            spd_in = _as_float(z.get("speed_at_entry"))
            spd_out = _as_float(z.get("speed_at_exit"))
            exited = bool(z.get("exited"))
            if spd_in is None:
                continue
            if exited and spd_out is not None:
                delta = spd_out - spd_in
                parts.append(f"{label}: {_safe_fmt(spd_in, 3)}→{_safe_fmt(spd_out, 3)} m/s (Δ{delta:+.3f})")
            else:
                parts.append(f"{label}: entry {_safe_fmt(spd_in, 3)} m/s → still inside")
    return parts + [""]

def _format_constraints(metrics: Dict[str, Any]) -> List[str]:
    parts: List[str] = ["### 5. Constraints"]
    ca = bool(metrics.get("checkpoint_a_reached"))
    cb = bool(metrics.get("checkpoint_b_reached"))
    seq = bool(metrics.get("checkpoint_reached"))
    tgt = bool(metrics.get("reached_target"))
    success_flag = bool(metrics.get("success"))
    ca_ylo = _as_float(metrics.get("checkpoint_a_y_lo"))
    ca_yhi = _as_float(metrics.get("checkpoint_a_y_hi"))
    cb_ylo = _as_float(metrics.get("checkpoint_b_y_lo"))
    cb_yhi = _as_float(metrics.get("checkpoint_b_y_hi"))
    tb = metrics.get("terrain_bounds", {}) or {}
    if ca_ylo is None or ca_yhi is None:
        cpz = tb.get("checkpoint_zone", {}) or {}
        ca_ylo = _as_float(cpz.get("y_min", 3.8))
        ca_yhi = _as_float(cpz.get("y_max", 4.5))
    if cb_ylo is None or cb_yhi is None:
        cpz_b = tb.get("checkpoint_b_zone", {}) or {}
        cb_ylo = _as_float(cpz_b.get("y_min", 2.5))
        cb_yhi = _as_float(cpz_b.get("y_max", 3.2))
    rows: List[str] = []
    has_failures = False
    if not ca:
        has_failures = True
        y_str = ""
        if ca_ylo is not None and ca_yhi is not None:
            y_str = f" y∈[{_safe_fmt(ca_ylo, 2)},{_safe_fmt(ca_yhi, 2)}]"
        rows.append(f"| Checkpoint A | FAIL | Not entered{y_str} at x∈[17.5,19.0] |")
    if not cb:
        has_failures = True
        y_str_b = ""
        if cb_ylo is not None and cb_yhi is not None:
            y_str_b = f" y∈[{_safe_fmt(cb_ylo, 2)},{_safe_fmt(cb_yhi, 2)}]"
        rows.append(f"| Checkpoint B | FAIL | Not entered{y_str_b} at x∈[23.0,24.5] |")
    if not seq:
        has_failures = True
        if not ca:
            reason = "Alpha not passed"
        elif not cb:
            reason = "Beta not passed"
        else:
            reason = "sequence broken"
        rows.append(f"| Sequence | FAIL | {reason} |")
    if not tgt:
        has_failures = True
        sx = _as_float(metrics.get("sled_x"))
        sy = _as_float(metrics.get("sled_y"))
        tx0 = _as_float(metrics.get("target_x_min"))
        tx1 = _as_float(metrics.get("target_x_max"))
        ty0 = _as_float(metrics.get("target_y_min"))
        ty1 = _as_float(metrics.get("target_y_max"))
        margin_parts = []
        if sx is not None and tx0 is not None and sx < tx0:
            margin_parts.append(f"x -{_safe_fmt(tx0 - sx, 2)} m")
        elif sx is not None and tx1 is not None and sx > tx1:
            margin_parts.append(f"x +{_safe_fmt(sx - tx1, 2)} m")
        if sy is not None and ty0 is not None and sy < ty0:
            margin_parts.append(f"y -{_safe_fmt(ty0 - sy, 2)} m")
        elif sy is not None and ty1 is not None and sy > ty1:
            margin_parts.append(f"y +{_safe_fmt(sy - ty1, 2)} m")
        margin_str = "; ".join(margin_parts) if margin_parts else "outside"
        rows.append(f"| Target | FAIL | {margin_str} |")
    if rows:
        parts.append("| Constraint | Status | Detail |")
        parts.append("|-----------|--------|--------|")
        parts.extend(rows)
    if success_flag:
        parts.append("| OVERALL | PASS | All constraints satisfied |")
    elif has_failures:
        parts.append(f"| OVERALL | FAIL | {len(rows)} constraint(s) not met |")
    else:
        parts.append("| OVERALL | FAIL | |")
    zone_data = metrics.get("zone_forensics") or {}
    near: List[str] = []
    if ca and isinstance(zone_data, dict):
        z_ca = zone_data.get("checkpoint_a")
        if isinstance(z_ca, dict):
            y_entry = _as_float(z_ca.get("y_at_entry"))
            if y_entry is not None and ca_ylo is not None and ca_yhi is not None:
                y_range = ca_yhi - ca_ylo
                if y_range > 0:
                    lo_margin = (y_entry - ca_ylo) / y_range
                    hi_margin = (ca_yhi - y_entry) / y_range
                    if lo_margin < 0.30:
                        near.append(f"Checkpoint A entry y={_safe_fmt(y_entry, 3)} only {lo_margin:.0%} above y_min ({_safe_fmt(ca_ylo, 3)})")
                    elif hi_margin < 0.30:
                        near.append(f"Checkpoint A entry y={_safe_fmt(y_entry, 3)} only {hi_margin:.0%} below y_max ({_safe_fmt(ca_yhi, 3)})")
    if cb and isinstance(zone_data, dict):
        z_cb = zone_data.get("checkpoint_b")
        if isinstance(z_cb, dict):
            y_entry_b = _as_float(z_cb.get("y_at_entry"))
            if y_entry_b is not None and cb_ylo is not None and cb_yhi is not None:
                y_range_b = cb_yhi - cb_ylo
                if y_range_b > 0:
                    lo_margin_b = (y_entry_b - cb_ylo) / y_range_b
                    hi_margin_b = (cb_yhi - y_entry_b) / y_range_b
                    if lo_margin_b < 0.30:
                        near.append(f"Checkpoint B entry y={_safe_fmt(y_entry_b, 3)} only {lo_margin_b:.0%} above y_min ({_safe_fmt(cb_ylo, 3)})")
                    elif hi_margin_b < 0.30:
                        near.append(f"Checkpoint B entry y={_safe_fmt(y_entry_b, 3)} only {hi_margin_b:.0%} below y_max ({_safe_fmt(cb_yhi, 3)})")
    if near:
        parts.append("")
        for n in near:
            parts.append(f"- Near-limit: {n}")
    return parts + [""]

def _format_health(metrics: Dict[str, Any]) -> List[str]:
    parts: List[str] = ["### 6. Health"]
    issues: List[str] = []
    for key in ("velocity_x", "velocity_y", "sled_x", "sled_y", "distance_to_target"):
        v = _as_float(metrics.get(key))
        if v is not None and not math.isfinite(v):
            issues.append(f"Non-finite: {key}={v}")
    vm = _as_float(metrics.get("velocity_magnitude"))
    if vm is not None and math.isfinite(vm) and vm > 50.0:
        issues.append(f"High speed: {_safe_fmt(vm, 1)} m/s")
    if vm is not None and math.isfinite(vm) and vm < 0.001:
        issues.append("Stationary (Box2D sleep possible)")
    stuck = metrics.get("stuck_forensics")
    if isinstance(stuck, dict):
        longest = stuck.get("longest_stuck_duration", 0)
        if isinstance(longest, (int, float)) and longest > 100:
            issues.append(
                f"Stuck for {int(longest)} steps "
                f"(x={_safe_fmt(_as_float(stuck.get('longest_stuck_x')), 2)})"
            )
        if stuck.get("still_stuck_at_end"):
            consec = stuck.get("consecutive_stuck_steps_at_end", 0)
            issues.append(f"Still stuck at end ({int(consec)} consecutive steps)")
    sc = metrics.get("step_count", 0)
    if isinstance(sc, (int, float)) and int(sc) >= 9999:
        issues.append(f"Step limit reached ({int(sc)})")
    if issues:
        for i in issues:
            parts.append(f"- {i}")
    else:
        parts.append("OK — no anomalies detected.")
    return parts + [""]

def _format_full_report(metrics: Dict[str, Any]) -> List[str]:
    if not metrics:
        return ["**No metrics available**"]
    if "error" in metrics:
        return [f"**Evaluator state**: {metrics['error']}"]
    parts: List[str] = ["## E-03 Slippery World — Diagnostic Report"]
    success_flag = bool(metrics.get("success"))
    failed_flag = bool(metrics.get("failed"))
    sc = metrics.get("step_count", "?")
    fr = metrics.get("failure_reason")
    if success_flag:
        parts.append(f"**OUTCOME**: PASS (step {sc})")
    elif failed_flag:
        reason_str = f" — {fr}" if fr else ""
        parts.append(f"**OUTCOME**: FAIL (step {sc}){reason_str}")
    else:
        parts.append(f"**OUTCOME**: INCOMPLETE (step {sc})")
    parts.append("")
    for fn in (_format_events, _format_position, _format_thrust,
               _format_energy, _format_constraints, _format_health):
        try:
            parts.extend(fn(metrics))
        except Exception:
            pass
    return parts

def _format_delta_report(metrics: Dict[str, Any], prev: Dict[str, Any]) -> List[str]:
    parts: List[str] = []
    sc = metrics.get("step_count", "?")
    prev_sc = prev.get("step_count", "?")
    parts.append(f"## E-03 Slippery World — Δ step {prev_sc}→{sc}")
    zone_data = metrics.get("zone_forensics") or {}
    prev_zone = prev.get("zone_forensics") or {}
    new_events: List[str] = []
    zone_manifest = [
        ("momentum_drain", "Momentum-Drain"),
        ("checkpoint_a", "Checkpoint A"),
        ("thrust_scale", "Thrust-Scale"),
        ("oscillating_wind", "Oscillating-Wind"),
        ("speed_penalty", "Speed-Penalty"),
        ("checkpoint_b", "Checkpoint B"),
        ("vertical_reverse", "Vertical-Reverse"),
        ("target_zone", "Target"),
    ]
    if isinstance(zone_data, dict) and isinstance(prev_zone, dict):
        for key, label in zone_manifest:
            z = zone_data.get(key)
            pz = prev_zone.get(key)
            was_entered = isinstance(pz, dict) and bool(pz.get("entered"))
            now_entered = isinstance(z, dict) and bool(z.get("entered"))
            if now_entered and not was_entered:
                entry_step = z.get("entry_step", "?")
                x_at = _as_float(z.get("x_at_entry"))
                spd = _safe_fmt(_as_float(z.get("speed_at_entry")), 3)
                detail = f"step {entry_step}"
                if x_at is not None:
                    detail += f", x={_safe_fmt(x_at, 4)}"
                detail += f", v={spd} m/s"
                new_events.append(f"[{label}] entered {detail}")
            elif now_entered and was_entered:
                was_exited = bool(pz.get("exited"))
                now_exited = bool(z.get("exited"))
                if now_exited and not was_exited:
                    exit_step = z.get("exit_step", "?")
                    spd_ex = _safe_fmt(_as_float(z.get("speed_at_exit")), 3)
                    new_events.append(f"[{label}] exited step {exit_step}, v={spd_ex} m/s")
    if new_events:
        parts.append("New events:")
        for e in new_events:
            parts.append(f"  {e}")
    else:
        parts.append("No new zone events.")
    sx = _as_float(metrics.get("sled_x"))
    sy = _as_float(metrics.get("sled_y"))
    prev_sx = _as_float(prev.get("sled_x"))
    prev_sy = _as_float(prev.get("sled_y"))
    if all(_finite(v) for v in (sx, sy, prev_sx, prev_sy)):
        dx = sx - prev_sx
        dy = sy - prev_sy
        parts.append(
            f"Position Δ: x {_safe_fmt(prev_sx, 3)}→{_safe_fmt(sx, 3)} ({dx:+.3f} m), "
            f"y {_safe_fmt(prev_sy, 3)}→{_safe_fmt(sy, 3)} ({dy:+.3f} m)"
        )
    dt = _as_float(metrics.get("distance_to_target"))
    prev_dt = _as_float(prev.get("distance_to_target"))
    pp = _as_float(metrics.get("progress_pct"))
    prev_pp = _as_float(prev.get("progress_pct"))
    if dt is not None and prev_dt is not None:
        ddt = dt - prev_dt
        pp_str = ""
        if pp is not None and prev_pp is not None:
            pp_str = f", progress {prev_pp:.1f}%→{pp:.1f}%"
        parts.append(f"Target: {_safe_fmt(prev_dt, 3)}→{_safe_fmt(dt, 3)} m (Δ{ddt:+.3f} m){pp_str}")
    vm = _as_float(metrics.get("velocity_magnitude"))
    prev_vm = _as_float(prev.get("velocity_magnitude"))
    if vm is not None and prev_vm is not None:
        parts.append(f"Speed: {_safe_fmt(prev_vm, 3)}→{_safe_fmt(vm, 3)} m/s")
    peak_spd = _as_float((zone_data or {}).get("peak_systemic_speed") if isinstance(zone_data, dict) else None)
    prev_peak = _as_float((prev_zone or {}).get("peak_systemic_speed") if isinstance(prev_zone, dict) else None)
    if peak_spd is not None and prev_peak is not None and peak_spd != prev_peak:
        parts.append(f"Peak speed: {_safe_fmt(prev_peak, 3)}→{_safe_fmt(peak_spd, 3)} m/s")
    tf = metrics.get("thrust_forensics") or {}
    prev_tf = prev.get("thrust_forensics") or {}
    thrust_changes: List[str] = []
    if isinstance(tf, dict) and isinstance(prev_tf, dict):
        cmd_mag = _as_float(tf.get("commanded_magnitude"))
        del_mag = _as_float(tf.get("delivered_magnitude"))
        prev_cmd = _as_float(prev_tf.get("commanded_magnitude"))
        prev_del = _as_float(prev_tf.get("delivered_magnitude"))
        if cmd_mag and cmd_mag > 0.001 and prev_cmd and prev_cmd > 0.001:
            ratio = (del_mag or 0) / cmd_mag
            prev_ratio = (prev_del or 0) / prev_cmd
            if abs(ratio - prev_ratio) > 0.02:
                thrust_changes.append(f"delivery ratio {prev_ratio:.3f}→{ratio:.3f}")
        sat = tf.get("thrust_saturation_steps", 0)
        prev_sat = prev_tf.get("thrust_saturation_steps", 0)
        if sat != prev_sat:
            thrust_changes.append(f"saturation steps {prev_sat}→{sat}")
    if thrust_changes:
        parts.append(f"Thrust Δ: {', '.join(thrust_changes)}")
    ca = bool(metrics.get("checkpoint_a_reached"))
    prev_ca = bool(prev.get("checkpoint_a_reached"))
    cb = bool(metrics.get("checkpoint_b_reached"))
    prev_cb = bool(prev.get("checkpoint_b_reached"))
    tgt_flag = bool(metrics.get("reached_target"))
    prev_tgt = bool(prev.get("reached_target"))
    constraint_changes: List[str] = []
    if ca != prev_ca:
        constraint_changes.append(f"Checkpoint A: {'REACHED' if ca else 'lost'}")
    if cb != prev_cb:
        constraint_changes.append(f"Checkpoint B: {'REACHED' if cb else 'lost'}")
    if tgt_flag != prev_tgt:
        constraint_changes.append(f"Target: {'REACHED' if tgt_flag else 'lost'}")
    if constraint_changes:
        parts.append(f"Constraints Δ: {', '.join(constraint_changes)}")
    else:
        parts.append("All constraint statuses unchanged.")
    health_issues: List[str] = []
    vm2 = _as_float(metrics.get("velocity_magnitude"))
    if vm2 is not None and math.isfinite(vm2) and vm2 > 50.0:
        health_issues.append(f"high speed {_safe_fmt(vm2, 1)} m/s")
    if vm2 is not None and math.isfinite(vm2) and vm2 < 0.001:
        health_issues.append("stationary (sleep possible)")
    stuck2 = metrics.get("stuck_forensics")
    if isinstance(stuck2, dict) and stuck2.get("still_stuck_at_end"):
        health_issues.append("still stuck at end")
    if health_issues:
        parts.append(f"Health: {', '.join(health_issues)}")
    return parts + [""]

def format_task_metrics(metrics: Dict[str, Any]) -> List[str]:
    if not metrics:
        return ["**No metrics available**"]
    if "error" in metrics:
        return [f"**Evaluator state**: {metrics['error']}"]
    prev = getattr(_sys, _STORE_ATTR, None)
    setattr(_sys, _STORE_ATTR, dict(metrics))
    sc = metrics.get("step_count", 0)
    prev_sc = prev.get("step_count", -1) if prev else -1
    is_new_run = prev is None or (
        isinstance(sc, (int, float)) and isinstance(prev_sc, (int, float)) and int(sc) < int(prev_sc)
    )
    if is_new_run:
        return _format_full_report(metrics)
    else:
        return _format_delta_report(metrics, prev)

def get_improvement_suggestions(
    metrics: Dict[str, Any],
    score: float,
    success: bool,
    failed: bool,
    failure_reason: Optional[str] = None,
    error: Optional[str] = None,

) -> List[str]:
    return []
