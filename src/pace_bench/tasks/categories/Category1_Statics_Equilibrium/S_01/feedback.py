from typing import Dict, Any, List, Optional

import math

import sys as _sys

_SIG_ATTR = "_davinci_fb_last_sig"

def _get_last_sig() -> Optional[str]:
    return getattr(_sys, _SIG_ATTR, None)

def _set_last_sig(sig: str) -> None:
    setattr(_sys, _SIG_ATTR, sig)

def _f(val: Any) -> Optional[float]:
    if val is None:
        return None
    try:
        fv = float(val)
        return fv if math.isfinite(fv) else None
    except (TypeError, ValueError):
        return None

def _pct(numer: float, denom: float) -> Optional[float]:
    if denom is None or not math.isfinite(denom) or denom == 0.0:
        return None
    n = _f(numer)
    if n is None:
        return None
    return (n / denom) * 100.0

def _margin(actual: float, limit: float) -> Optional[float]:
    a = _f(actual)
    l = _f(limit)
    if a is None or l is None:
        return None
    return l - a

def _fmt_pos(x: Any, y: Any) -> str:
    fx = _f(x)
    fy = _f(y)
    if fx is None or fy is None:
        return "(?,?)"
    return f"({fx:.2f}, {fy:.2f})"

def _fmt_lim(val: Any, lim: Any, unit: str = "") -> str:
    v = _f(val)
    l = _f(lim)
    if v is None:
        return "n/a"
    s = f"{v:.3f}"
    if l is not None and math.isfinite(l):
        m = l - v
        s += f" / {l:.3f}{unit} (margin {m:+.3f}{unit})"
    return s

def _stall_detected(metrics: Dict[str, Any]) -> tuple:
    vx = _f(metrics.get("velocity_x"))
    step = _f(metrics.get("step_count"))
    angle = _f(metrics.get("normalized_angle"))
    vehicle_x = _f(metrics.get("vehicle_x"))
    target_x = _f(metrics.get("target_x"))
    start_x = _f(metrics.get("vehicle_start_x"))
    stall_thresh = _f(metrics.get("stall_threshold_x"))
    failed = metrics.get("failed", False)
    if vx is None:
        return False, ""
    reasons = []
    if (step is not None and step > 300 and abs(vx) < 0.05
            and vehicle_x is not None and target_x is not None and vehicle_x < target_x
            and not failed):
        reasons.append(f"forward velocity {vx:.3f} m/s at step {int(step)}")
    if (vehicle_x is not None and stall_thresh is not None
            and vehicle_x < stall_thresh and step is not None and step > 400
            and not failed):
        reasons.append(f"vehicle at x={vehicle_x:.2f} has not reached stall-threshold x={stall_thresh:.2f} at step {int(step)}")
    if (angle is not None and abs(angle) > 0.2
            and vehicle_x is not None and start_x is not None
            and vehicle_x < start_x + 3.0 and step is not None and step > 200
            and not failed):
        reasons.append(f"vehicle tilted {math.degrees(abs(angle)):.1f}° near entry x={vehicle_x:.2f}")
    return bool(reasons), "; ".join(reasons)

def _moment_signature(metrics: Dict[str, Any]) -> str:
    step = int(_f(metrics.get("step_count")) or -1)
    failed = 1 if metrics.get("failed") else 0
    vx = _f(metrics.get("vehicle_x")) or 0.0
    return f"{step}|{failed}|{vx:.3f}"

def _format_numerical_health(metrics: Dict[str, Any]) -> List[str]:
    issues = []
    for key, label in [
        ("vehicle_x", "vehicle_x"), ("vehicle_y", "vehicle_y"),
        ("velocity_x", "velocity_x"), ("velocity_y", "velocity_y"),
        ("angular_velocity", "angular_velocity"),
        ("max_vertical_accel", "max_vertical_accel"),
    ]:
        v = _f(metrics.get(key))
        if v is not None and not math.isfinite(v):
            issues.append(f"{label} = {v}")
    for key, label, lim in [
        ("velocity_x", "vx", 100.0), ("velocity_y", "vy", 100.0),
        ("angular_velocity", "angular velocity", 50.0),
    ]:
        v = _f(metrics.get(key))
        if v is not None and abs(v) > lim:
            issues.append(f"{label} = {v:.2f} exceeds {lim:.1f}")
    mva = _f(metrics.get("max_vertical_accel"))
    if mva is not None and mva > 200.0:
        issues.append(f"max_vertical_accel = {mva:.2f} m/s² (>20g)")
    stalled, stall_reason = _stall_detected(metrics)
    if stalled:
        issues.append(f"vehicle stall detected: {stall_reason}")
    if issues:
        parts = ["## Numerical Health"]
        for iss in issues:
            parts.append(f"- ⚠️ {iss}")
        return parts
    else:
        return ["## Numerical Health: all finite ✓"]

def _format_state_snapshot(metrics: Dict[str, Any]) -> List[str]:
    parts = ["## State"]
    vx = _f(metrics.get("vehicle_x"))
    vy = _f(metrics.get("vehicle_y"))
    tx = _f(metrics.get("target_x"))
    sx = _f(metrics.get("vehicle_start_x"))
    if vx is not None and vy is not None:
        pos_str = f"- Position: ({vx:.2f}, {vy:.2f}) m"
        if tx is not None and sx is not None:
            total = tx - sx
            covered = vx - sx
            if total > 0:
                pct = (covered / total) * 100.0
                pos_str += f" | target x={tx:.2f}, remaining {tx - vx:.2f}m, covered {pct:.1f}%"
            else:
                pos_str += f" | target x={tx:.2f}"
        parts.append(pos_str)
    vx_vel = _f(metrics.get("velocity_x"))
    vy_vel = _f(metrics.get("velocity_y"))
    if vx_vel is not None and vy_vel is not None:
        speed = math.hypot(vx_vel, vy_vel)
        parts.append(f"- Velocity: ({vx_vel:.2f}, {vy_vel:.2f}) m/s, |v|={speed:.2f}")
    nang = _f(metrics.get("normalized_angle"))
    av = _f(metrics.get("angular_velocity"))
    avl = _f(metrics.get("max_angular_velocity_limit"))
    if nang is not None:
        att_str = f"- Tilt: {math.degrees(nang):.1f}°"
        if av is not None:
            att_str += f" | angular vel: {av:.3f} rad/s"
            if avl is not None:
                att_str += f" (limit {avl:.2f})"
        parts.append(att_str)
    sm = _f(metrics.get("structure_mass"))
    msm = _f(metrics.get("max_structure_mass"))
    if sm is not None and msm is not None:
        pct = (sm / msm * 100.0) if msm > 0 else 0.0
        parts.append(f"- Mass: {sm:.2f}/{msm:.2f} kg ({pct:.1f}% used)")
    fzy = _f(metrics.get("fail_zone_y"))
    if vy is not None and fzy is not None:
        margin = vy - fzy
        sev = "CRITICAL" if margin < 1.0 else ("WARNING" if margin < 3.0 else "SAFE")
        parts.append(f"- Altitude vs fail-zone y={fzy:.2f}: margin {margin:+.2f}m [{sev}]")
    stall_x = _f(metrics.get("stall_threshold_x"))
    if vx is not None and stall_x is not None:
        to_stall = stall_x - vx
        parts.append(f"- Gap threshold x={stall_x:.2f}: distance {to_stall:+.2f}m")
    jf = _f(metrics.get("joint_max_force_limit"))
    jt = _f(metrics.get("joint_max_torque_limit"))
    af = _f(metrics.get("anchor_max_force_limit"))
    at = _f(metrics.get("anchor_max_torque_limit"))
    limit_parts = []
    if jf is not None:
        limit_parts.append(f"struct F={jf:.1f}N")
    if jt is not None:
        limit_parts.append(f"struct T={jt:.3f}Nm")
    if af is not None:
        limit_parts.append(f"anchor F={af:.1f}N")
    if at is not None:
        limit_parts.append(f"anchor T={at:.3f}Nm")
    if limit_parts:
        parts.append(f"- Joint limits: {', '.join(limit_parts)}")
    return parts

def _format_constraints(metrics: Dict[str, Any]) -> List[str]:
    parts = ["## Constraints"]
    failed_flag = metrics.get("failed", False)
    failure_reason = metrics.get("failure_reason", "")
    active_lines: List[str] = []
    passive_count = 0
    sm = _f(metrics.get("structure_mass"))
    msm = _f(metrics.get("max_structure_mass"))
    if sm is not None and msm is not None:
        pct_used = (sm / msm * 100.0) if msm > 0 else 0.0
        mar = msm - sm
        if sm > msm:
            active_lines.append(
                f"- ❌ FAIL Mass: {sm:.2f}/{msm:.2f} kg "
                f"({pct_used:.0f}% used, over by {-mar:.2f} kg)"
            )
        elif pct_used > 80.0:
            active_lines.append(
                f"- ⚠️ NEAR Mass: {sm:.2f}/{msm:.2f} kg "
                f"({pct_used:.0f}% used, margin {mar:.2f} kg)"
            )
        else:
            passive_count += 1
    bx_min = _f(metrics.get("build_zone_x_min", 10.0))
    bx_max = _f(metrics.get("build_zone_x_max", 30.0))
    by_min = _f(metrics.get("build_zone_y_min", 5.0))
    by_max = _f(metrics.get("build_zone_y_max", 15.0))
    body_positions = metrics.get("body_positions_and_angles") or []
    zone_ok = True
    if body_positions:
        for bp in body_positions:
            if len(bp) >= 2:
                xx, yy = _f(bp[0]), _f(bp[1])
                if xx is not None and yy is not None:
                    if not (bx_min <= xx <= bx_max and by_min <= yy <= by_max):
                        zone_ok = False
                        break
    if not zone_ok:
        active_lines.append("- ❌ FAIL Build zone: beams outside allowed area")
    else:
        passive_count += 1
    design_violated = (failed_flag and failure_reason and
                       "Design constraint" in str(failure_reason))
    if design_violated:
        active_lines.append("- ❌ FAIL Design constraints")
    else:
        passive_count += 1
    jc = metrics.get("joint_count")
    ijc = metrics.get("initial_joint_count")
    structure_broken = metrics.get("structure_broken", False)
    if ijc is not None and int(ijc) > 0:
        broken = int(ijc) - int(jc) if jc is not None else 0
        pct_broken = (broken / int(ijc)) * 100.0
        if broken > 0:
            active_lines.append(
                f"- ❌ FAIL Structural integrity: {broken}/{int(ijc)} joints broken "
                f"({pct_broken:.0f}%)"
            )
        else:
            passive_count += 1
    elif structure_broken:
        active_lines.append("- ❌ FAIL Structural integrity")
    elif ijc is not None:
        passive_count += 1
    vy = _f(metrics.get("vehicle_y"))
    fzy = _f(metrics.get("fail_zone_y"))
    if vy is not None and fzy is not None:
        alt_margin = vy - fzy
        if alt_margin <= 0:
            active_lines.append(
                f"- ❌ FAIL Altitude: y={vy:.2f}m below fail-zone {fzy:.2f}m "
                f"(by {-alt_margin:.2f}m)"
            )
        elif alt_margin < 2.0:
            active_lines.append(
                f"- ⚠️ NEAR Altitude: margin {alt_margin:+.2f}m above fail-zone"
            )
        else:
            passive_count += 1
    mva = _f(metrics.get("max_vertical_accel"))
    mval = _f(metrics.get("max_vertical_acceleration_limit"))
    if mva is not None and mval is not None:
        acc_pct = (mva / mval * 100.0) if mval > 0 else 0.0
        acc_margin = mval - mva
        if acc_margin < 0:
            active_lines.append(
                f"- ❌ FAIL Vertical accel: {mva:.2f}/{mval:.2f} m/s² "
                f"(over by {-acc_margin:.2f})"
            )
        elif acc_pct > 50.0:
            active_lines.append(
                f"- ⚠️ NEAR Vertical accel: {mva:.2f}/{mval:.2f} m/s² ({acc_pct:.0f}%)"
            )
        else:
            passive_count += 1
    havc = metrics.get("high_angular_velocity_count", 0)
    ut = _f(metrics.get("unstable_threshold_limit", 5))
    if havc is not None and ut is not None:
        if int(havc) >= int(ut):
            active_lines.append(
                f"- ❌ FAIL Angular stability: {havc}/{int(ut)} unstable steps"
            )
        elif int(havc) > int(ut) * 0.5 and int(havc) > 0:
            active_lines.append(
                f"- ⚠️ NEAR Angular stability: {havc}/{int(ut)} unstable steps"
            )
        else:
            passive_count += 1
    nangle = _f(metrics.get("normalized_angle"))
    flip_limit = _f(metrics.get("flip_angle_limit_rad", math.pi / 2))
    if nangle is not None and flip_limit is not None:
        abs_angle = abs(nangle)
        flip_margin = flip_limit - abs_angle
        if flip_margin < 0:
            active_lines.append(
                f"- ❌ FAIL Flip angle: |{math.degrees(abs_angle):.0f}°| "
                f"> {math.degrees(flip_limit):.0f}°"
            )
        elif math.degrees(flip_margin) < 20.0:
            active_lines.append(
                f"- ⚠️ NEAR Flip angle: |{math.degrees(abs_angle):.0f}°|, "
                f"margin {math.degrees(flip_margin):.0f}°"
            )
        else:
            passive_count += 1
    arb_rot = _f(metrics.get("airborne_rotation_accumulated"))
    arb_lim = _f(metrics.get("max_airborne_rotation_limit"))
    if arb_rot is not None and arb_lim is not None:
        arb_pct = (arb_rot / arb_lim * 100.0) if arb_lim > 0 else 0.0
        arb_margin = arb_lim - arb_rot
        if arb_margin < 0:
            active_lines.append(
                f"- ❌ FAIL Airborne rotation: {math.degrees(arb_rot):.0f}°/"
                f"{math.degrees(arb_lim):.0f}°"
            )
        elif arb_pct > 50.0:
            active_lines.append(
                f"- ⚠️ NEAR Airborne rotation: {math.degrees(arb_rot):.0f}°/"
                f"{math.degrees(arb_lim):.0f}° ({arb_pct:.0f}%)"
            )
        else:
            passive_count += 1
    if active_lines:
        parts.extend(active_lines)
        if passive_count > 0:
            parts.append(f"- All {passive_count} other constraints: PASS ✓")
    elif passive_count > 0:
        parts.append(f"- All {passive_count} constraints: PASS ✓")
    return parts

def _format_stress_distribution(metrics: Dict[str, Any]) -> List[str]:
    parts = ["## Stress Distribution"]
    stress_records = metrics.get("joint_stress_summary") or []
    if not stress_records:
        parts.append("- No joint stress records available")
        return parts
    try:
        entries = []
        for rec in stress_records:
            if not isinstance(rec, dict):
                continue
            fl = _f(rec.get("force_limit")) or 0.0
            tl = _f(rec.get("torque_limit")) or 0.0
            pf = _f(rec.get("peak_force")) or 0.0
            pt = _f(rec.get("peak_torque")) or 0.0
            force_pct = (pf / fl * 100.0) if fl > 0 else 0.0
            torque_pct = (pt / tl * 100.0) if tl > 0 else 0.0
            max_pct = max(force_pct, torque_pct)
            is_anchor = bool(rec.get("is_anchor", False))
            ba = rec.get("body_a_pos", (0.0, 0.0))
            idx = rec.get("joint_idx", -1)
            entries.append({
                "idx": idx,
                "pos_a": (float(ba[0]), float(ba[1])),
                "force_pct": force_pct,
                "torque_pct": torque_pct,
                "max_pct": max_pct,
                "peak_force": pf,
                "force_limit": fl,
                "peak_torque": pt,
                "torque_limit": tl,
                "is_anchor": is_anchor,
            })
        if not entries:
            parts.append("- No stress entries computable")
            return parts
        entries.sort(key=lambda e: e["max_pct"], reverse=True)
        critical = [e for e in entries if e["max_pct"] > 80.0]
        elevated = [e for e in entries if 50.0 < e["max_pct"] <= 80.0]
        nominal = [e for e in entries if e["max_pct"] <= 50.0]
        parts.append(
            f"- Tiers: {len(critical)} critical (>80%), "
            f"{len(elevated)} elevated (50-80%), "
            f"{len(nominal)} nominal (≤50%)"
        )
        parts.append("- Top 5 by severity:")
        for rank, e in enumerate(entries[:5], 1):
            role = "anchor" if e["is_anchor"] else "struct"
            parts.append(
                f"  #{rank} Joint #{e['idx']} ({role}) at "
                f"{_fmt_pos(e['pos_a'][0], e['pos_a'][1])}: "
                f"force {e['force_pct']:.0f}%/F, torque {e['torque_pct']:.0f}%/T"
            )
        if critical:
            parts.append(f"- Critical joints (>{80.0:.0f}% of limit):")
            for e in critical:
                role = "anchor" if e["is_anchor"] else "struct"
                parts.append(
                    f"  - Joint #{e['idx']} ({role}): "
                    f"{_fmt_pos(e['pos_a'][0], e['pos_a'][1])}; "
                    f"force {e['force_pct']:.0f}%F, torque {e['torque_pct']:.0f}%T"
                )
        if elevated:
            if len(elevated) <= 3:
                parts.append(f"- Elevated-stress joints (50–80% of limit):")
                for e in elevated:
                    role = "anchor" if e["is_anchor"] else "struct"
                    parts.append(
                        f"  - Joint #{e['idx']} ({role}): "
                        f"{_fmt_pos(e['pos_a'][0], e['pos_a'][1])}; "
                        f"force {e['force_pct']:.0f}%F, torque {e['torque_pct']:.0f}%T"
                    )
            else:
                parts.append(
                    f"- Elevated-stress joints (50–80%): {len(elevated)} total, top 3:"
                )
                for e in elevated[:3]:
                    role = "anchor" if e["is_anchor"] else "struct"
                    parts.append(
                        f"  - Joint #{e['idx']} ({role}): "
                        f"{_fmt_pos(e['pos_a'][0], e['pos_a'][1])}; "
                        f"force {e['force_pct']:.0f}%F, torque {e['torque_pct']:.0f}%T"
                    )
                if len(elevated) > 3:
                    parts.append(f"  ... and {len(elevated) - 3} more elevated-stress joints")
        anchor_entries = [e for e in entries if e["is_anchor"]]
        struct_entries = [e for e in entries if not e["is_anchor"]]
        if anchor_entries:
            avg_anchor = sum(e["max_pct"] for e in anchor_entries) / len(anchor_entries)
            parts.append(
                f"- Anchor stress: {len(anchor_entries)} joints, avg {avg_anchor:.0f}% of limit"
            )
        if struct_entries:
            avg_struct = sum(e["max_pct"] for e in struct_entries) / len(struct_entries)
            parts.append(
                f"- Structural joint stress: {len(struct_entries)} joints, avg {avg_struct:.0f}% of limit"
            )
    except (TypeError, ValueError, KeyError, IndexError, ZeroDivisionError) as exc:
        parts.append(f"- Error computing stress: {type(exc).__name__}: {exc}")
    return parts

def _format_failure_timeline(metrics: Dict[str, Any]) -> List[str]:
    parts = ["## Failure Timeline"]
    failure_events = metrics.get("joint_failure_events") or []
    if not failure_events:
        if metrics.get("structure_broken"):
            parts.append("- Structure reported broken but no failure events recorded")
        else:
            parts.append("- No joint failure events — structure intact throughout simulation")
        return parts
    parts.append(f"- **{len(failure_events)} joint failure events**")
    sorted_events = sorted(failure_events, key=lambda e: int(e.get("step", 0)))
    waves = []
    current_wave = []
    last_step = -100
    for ev in sorted_events:
        step = int(ev.get("step", 0))
        if current_wave and (step - last_step > 10):
            waves.append(current_wave)
            current_wave = []
        current_wave.append(ev)
        last_step = step
    if current_wave:
        waves.append(current_wave)
    if len(waves) == 1 and len(waves[0]) <= 3:
        parts.append("- Individual events:")
        for ev in waves[0]:
            step = ev.get("step", -1)
            pos = ev.get("body_a_pos", (None, None))
            is_anchor = ev.get("is_anchor", False)
            pf = ev.get("peak_force", 0.0)
            pt = ev.get("peak_torque", 0.0)
            role = "anchor" if is_anchor else "struct"
            parts.append(
                f"  Step {step}: {role} joint at {_fmt_pos(pos[0], pos[1])}; "
                f"force={float(pf):.2f} N, torque={float(pt):.3f} Nm"
            )
    else:
        parts.append(f"- **{len(waves)} cascade wave(s)**:")
        for wi, wave in enumerate(waves):
            w_start = int(wave[0].get("step", 0))
            w_end = int(wave[-1].get("step", 0))
            n_anchor = sum(1 for e in wave if e.get("is_anchor"))
            n_struct = len(wave) - n_anchor
            xs = []
            for ev in wave:
                pos = ev.get("body_a_pos", (None, None))
                if pos[0] is not None:
                    try:
                        xs.append(float(pos[0]))
                    except (TypeError, ValueError):
                        pass
            x_range = f"x=[{min(xs):.2f}, {max(xs):.2f}]" if xs else "unknown"
            first = wave[0]
            fp = first.get("body_a_pos", (None, None))
            parts.append(
                f"  Wave {wi+1}: steps {w_start}–{w_end}, {len(wave)} failures "
                f"({n_anchor} anchor, {n_struct} struct), {x_range}"
            )
            parts.append(
                f"    Initiated: step {w_start}, joint at {_fmt_pos(fp[0], fp[1])}"
            )
            if len(wave) <= 5:
                for ev in wave:
                    step = ev.get("step", -1)
                    pos = ev.get("body_a_pos", (None, None))
                    is_anchor = ev.get("is_anchor", False)
                    pf = ev.get("peak_force", 0.0)
                    pt = ev.get("peak_torque", 0.0)
                    role = "anchor" if is_anchor else "struct"
                    parts.append(
                        f"    Step {step}: {role} joint at {_fmt_pos(pos[0], pos[1])}; "
                        f"force={float(pf):.2f} N, torque={float(pt):.3f} Nm"
                    )
            else:
                for ev in wave[:2]:
                    step = ev.get("step", -1)
                    pos = ev.get("body_a_pos", (None, None))
                    is_anchor = ev.get("is_anchor", False)
                    pf = ev.get("peak_force", 0.0)
                    pt = ev.get("peak_torque", 0.0)
                    role = "anchor" if is_anchor else "struct"
                    parts.append(
                        f"    Step {step}: {role} joint at {_fmt_pos(pos[0], pos[1])}; "
                        f"force={float(pf):.2f} N, torque={float(pt):.3f} Nm"
                    )
                last_ev = wave[-1]
                lstep = last_ev.get("step", -1)
                lpos = last_ev.get("body_a_pos", (None, None))
                lis_anchor = last_ev.get("is_anchor", False)
                lpf = last_ev.get("peak_force", 0.0)
                lpt = last_ev.get("peak_torque", 0.0)
                lrole = "anchor" if lis_anchor else "struct"
                parts.append(
                    f"    ... {len(wave) - 3} more failures ..."
                )
                parts.append(
                    f"    Step {lstep}: {lrole} joint at {_fmt_pos(lpos[0], lpos[1])}; "
                    f"force={float(lpf):.2f} N, torque={float(lpt):.3f} Nm"
                )
    first_ev = sorted_events[0]
    first_step = first_ev.get("step", -1)
    fpos = first_ev.get("body_a_pos", (None, None))
    fis_anchor = first_ev.get("is_anchor", False)
    fpf = first_ev.get("peak_force", 0.0)
    fpt = first_ev.get("peak_torque", 0.0)
    jf_lim = _f(metrics.get("joint_max_force_limit", 80.0))
    jt_lim = _f(metrics.get("joint_max_torque_limit", 300.0))
    af_lim = _f(metrics.get("anchor_max_force_limit", 100.0))
    at_lim = _f(metrics.get("anchor_max_torque_limit", 500.0))
    if fis_anchor:
        force_lim, torque_lim = af_lim, at_lim
    else:
        force_lim, torque_lim = jf_lim, jt_lim
    force_exceeded = fpf > force_lim if force_lim is not None else False
    torque_exceeded = fpt > torque_lim if torque_lim is not None else False
    exceed_str = []
    if force_exceeded:
        exceed_str.append(
            f"force {float(fpf):.2f} N > limit {force_lim:.2f} N "
            f"(by {float(fpf) - force_lim:+.2f} N)"
        )
    if torque_exceeded:
        exceed_str.append(
            f"torque {float(fpt):.3f} Nm > limit {torque_lim:.3f} Nm "
            f"(by {float(fpt) - torque_lim:+.3f} Nm)"
        )
    role = "anchor" if fis_anchor else "struct"
    parts.append(
        f"- **First failure**: step {first_step}, {role} joint at "
        f"{_fmt_pos(fpos[0], fpos[1])}; "
        f"{' & '.join(exceed_str) if exceed_str else 'limit exceeded'}"
    )
    return parts

def _format_interaction(metrics: Dict[str, Any]) -> List[str]:
    parts = ["## Interaction"]
    vx = _f(metrics.get("vehicle_x"))
    vy = _f(metrics.get("vehicle_y"))
    sx = _f(metrics.get("vehicle_start_x"))
    nang = _f(metrics.get("normalized_angle"))
    step = _f(metrics.get("step_count"))
    has_content = False
    if (vx is not None and sx is not None and step is not None
            and vx < sx + 2.0 and step > 200 and vx > 0):
        nang_deg = math.degrees(abs(nang)) if nang is not None else None
        parts.append(
            f"- Vehicle near entry: x={vx:.2f} m, "
            f"{('tilted ' + f'{nang_deg:.1f}°' if nang_deg is not None else 'attitude unknown')}, "
            f"at step {int(step)}"
        )
        has_content = True
    body_positions = metrics.get("body_positions_and_angles") or []
    entry_bodies = []
    if body_positions:
        for bp in body_positions:
            if len(bp) >= 3:
                xx, yy, aa = _f(bp[0]), _f(bp[1]), _f(bp[2])
                if xx is not None and 8.0 <= xx <= 12.0:
                    entry_bodies.append((xx, yy, aa))
    if entry_bodies:
        entry_bodies.sort(key=lambda b: b[1], reverse=True)
        top_beam = entry_bodies[0]
        beam_angle_deg = math.degrees(abs(top_beam[2])) % 180.0
        if beam_angle_deg > 90.0:
            beam_angle_deg = 180.0 - beam_angle_deg
        parts.append(
            f"- Bridge entry (x≈10m): {len(entry_bodies)} beams, "
            f"highest at ({top_beam[0]:.2f}, {top_beam[1]:.2f}), "
            f"slope {beam_angle_deg:.1f}°"
        )
        has_content = True
    closest_dist = float('inf')
    if vx is not None and vy is not None and body_positions:
        for bp in body_positions:
            if len(bp) >= 2:
                bx, by = _f(bp[0]), _f(bp[1])
                if bx is not None and by is not None:
                    dist = math.hypot(vx - bx, vy - by)
                    if dist < closest_dist:
                        closest_dist = dist
        if math.isfinite(closest_dist) and closest_dist < 3.0:
            parts.append(f"- Closest beam: {closest_dist:.2f}m from vehicle")
            has_content = True
    vx_vel = _f(metrics.get("velocity_x"))
    vy_vel = _f(metrics.get("velocity_y"))
    if vx_vel is not None and vy_vel is not None:
        speed = math.hypot(vx_vel, vy_vel)
        if speed < 0.01 and step is not None and step > 100:
            parts.append(f"- Vehicle nearly stationary: speed {speed:.4f} m/s at step {int(step)}")
            has_content = True
        elif vx_vel < -0.1:
            parts.append(f"- Vehicle moving backward: vx={vx_vel:.3f} m/s")
            has_content = True
    if not has_content:
        parts.append("- No notable vehicle-structure interactions detected")
    return parts

def _format_geometry(metrics: Dict[str, Any]) -> List[str]:
    parts = ["## Geometry"]
    right_cliff_x = _f(metrics.get("terrain_right_cliff_x_start", 25.0))
    right_cliff_end = _f(metrics.get("terrain_right_cliff_x_end", 100.0))
    gap_width = _f(metrics.get("terrain_gap_width", 15.0))
    bx_max = _f(metrics.get("build_zone_x_max", 30.0))
    cliff_top_y = _f(metrics.get("cliff_top_y", 10.0))
    parts.append(
        f"- Terrain: gap {gap_width:.1f}m (x=10.0–{right_cliff_x:.1f}), "
        f"cliff top y={cliff_top_y:.1f}, "
        f"right cliff x=[{right_cliff_x:.1f}, {right_cliff_end:.1f}], "
        f"build zone x=[10.0, {bx_max:.1f}]"
    )
    anchor_positions = metrics.get("anchor_positions") or []
    if anchor_positions:
        left_count = 0
        right_on_cliff = 0
        right_past_cliff = 0
        for ap in anchor_positions:
            if len(ap) < 5:
                continue
            awx = _f(ap[0])
            is_left = bool(ap[4])
            if is_left:
                left_count += 1
            elif right_cliff_x is not None and right_cliff_end is not None and awx is not None:
                if awx > right_cliff_end + 1.0:
                    right_past_cliff += 1
                elif right_cliff_x - 1.0 <= awx <= right_cliff_end + 1.0:
                    right_on_cliff += 1
        parts.append(
            f"- Anchors: {len(anchor_positions)} total "
            f"({left_count} left cliff, {right_on_cliff} right cliff"
            + (f", {right_past_cliff} past cliff — unsupported" if right_past_cliff else "")
            + ")"
        )
        if right_past_cliff:
            for ap in anchor_positions:
                if len(ap) < 5:
                    continue
                awx = _f(ap[0])
                awy = _f(ap[1])
                is_left = bool(ap[4])
                if not is_left and awx is not None and right_cliff_end is not None and awx > right_cliff_end + 1.0:
                    overhang = awx - right_cliff_end
                    parts.append(
                        f"  - Anchor at ({awx:.2f}, {awy:.2f}), "
                        f"{overhang:.1f}m past right cliff end"
                    )
    else:
        parts.append("- No anchor position data available")
    body_positions = metrics.get("body_positions_and_angles") or []
    if body_positions and right_cliff_end is not None:
        beams_past = sum(
            1 for bp in body_positions
            if len(bp) >= 1 and _f(bp[0]) is not None and _f(bp[0]) > right_cliff_end + 1.0
        )
        if beams_past > 0:
            max_overhang = max(
                (_f(bp[0]) - right_cliff_end)
                for bp in body_positions
                if len(bp) >= 1 and _f(bp[0]) is not None and _f(bp[0]) > right_cliff_end + 1.0
            )
            parts.append(
                f"- Beams past right cliff (x={right_cliff_end:.1f}): "
                f"{beams_past}, max overhang {max_overhang:.2f}m"
            )
        else:
            parts.append("- All beams within terrain bounds ✓")
    return parts

def format_task_metrics(
    metrics: Dict[str, Any],
    prev_metrics: Optional[Dict[str, Any]] = None,

) -> List[str]:
    if not metrics:
        return ["**No metrics available**"]
    sig = _moment_signature(metrics)
    if _get_last_sig() is not None and sig == _get_last_sig():
        step_count = int(_f(metrics.get("step_count")) or 0)
        return [f"## Summary: *(State unchanged from previous moment, step {step_count})*"]
    _set_last_sig(sig)
    parts: List[str] = []
    score = _f(metrics.get("score", 0.0))
    success = metrics.get("success", False)
    failed = metrics.get("failed", False)
    failure_reason = metrics.get("failure_reason", "")
    step_count = metrics.get("step_count", 0)
    status = "SUCCESS ✓" if success else ("FAILED ❌" if failed else "IN PROGRESS")
    parts.append(f"## Summary: {status} | score={score:.1f} | step={step_count}")
    if failure_reason:
        parts.append(f"**Failure reason**: {failure_reason}")
    parts.extend(_format_numerical_health(metrics))
    parts.extend(_format_state_snapshot(metrics))
    parts.extend(_format_constraints(metrics))
    parts.extend(_format_stress_distribution(metrics))
    parts.extend(_format_failure_timeline(metrics))
    parts.extend(_format_interaction(metrics))
    parts.extend(_format_geometry(metrics))
    return parts

def get_improvement_suggestions(
    metrics: Dict[str, Any],
    score: float,
    success: bool,
    failed: bool,
    failure_reason: Optional[str] = None,
    error: Optional[str] = None,

) -> List[str]:
    suggestions = []
    if error:
        suggestions.append("- Code execution failed. Review error details above.")
        return suggestions
    if success:
        return suggestions
    if failed and failure_reason:
        fr_lower = failure_reason.lower()
        if "design constraint" in fr_lower:
            suggestions.append("- Build-time constraint violated. Review constraint profile above.")
        elif "water" in fr_lower or "fail zone" in fr_lower:
            suggestions.append("- Vehicle or structural component entered the fail zone.")
        elif "integrity" in fr_lower or "joint" in fr_lower:
            suggestions.append("- Structure lost integrity. Review temporal chronology for failure cascade details.")
            suggestions.append("- Review load distribution section for stress concentration points.")
        elif "acceleration" in fr_lower:
            suggestions.append("- Vertical acceleration exceeded limit. Review constraint profile.")
        elif "unstable" in fr_lower:
            suggestions.append("- Vehicle angular stability exceeded. Review constraint profile.")
        elif "flipped" in fr_lower:
            suggestions.append("- Vehicle flipped past 90° limit. Review vehicle-structure interaction section.")
        elif "airborne" in fr_lower:
            suggestions.append("- Excessive airborne rotation detected.")
        else:
            suggestions.append("- Review constraint profile for specific violation details.")
    jc = metrics.get("joint_count")
    ijc = metrics.get("initial_joint_count")
    if ijc is not None and jc is not None and int(ijc) > 0 and int(jc) < int(ijc):
        broken = int(ijc) - int(jc)
        suggestions.append(
            f"- {broken}/{int(ijc)} joints failed. Review temporal chronology for failure order."
        )
    stress_records = metrics.get("joint_stress_summary") or []
    if stress_records:
        try:
            critical_count = 0
            for rec in stress_records:
                if not isinstance(rec, dict):
                    continue
                fl = _f(rec.get("force_limit")) or 0.0
                tl = _f(rec.get("torque_limit")) or 0.0
                pf = _f(rec.get("peak_force")) or 0.0
                pt = _f(rec.get("peak_torque")) or 0.0
                fp = (pf / fl * 100.0) if fl > 0 else 0.0
                tp = (pt / tl * 100.0) if tl > 0 else 0.0
                if max(fp, tp) > 80.0:
                    critical_count += 1
            if critical_count > 0:
                suggestions.append(
                    f"- {critical_count} joints at >80% of limit. Review stress concentration ranking."
                )
        except (TypeError, ValueError):
            pass
    return suggestions
