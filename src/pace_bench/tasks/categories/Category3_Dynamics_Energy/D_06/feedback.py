from typing import Any, Dict, List

import math

def _is_finite(x: Any) -> bool:
    if x is None:
        return False
    try:
        return math.isfinite(float(x))
    except (TypeError, ValueError):
        return False

def _safe_float(x: Any) -> float:
    return float(x)

def _section(header: str) -> str:
    return f"\n### {header}\n"

def _build_summary(metrics: Dict[str, Any]) -> List[str]:
    lines: List[str] = []
    lines.append(_section("Diagnostic Summary"))
    success = metrics.get("success", False)
    failed = metrics.get("failed", False)
    fr = metrics.get("failure_reason")
    smashed = metrics.get("structure_smashed", False)
    seq = metrics.get("sequential_violation", False)
    pit = metrics.get("pit_failure", False)
    caught = metrics.get("balls_caught_count")
    required = metrics.get("balls_required_count", 7)
    step = metrics.get("step_count")
    ci = int(caught) if _is_finite(caught) else 0
    ri = int(required) if _is_finite(required) else 7
    si = int(step) if _is_finite(step) else 0
    max_steps = metrics.get("max_steps", "?")
    parts = [f"Simulation ended after {si} steps with {ci}/{ri} balls caught"]
    if success:
        parts.append("— SUCCESS: all criteria satisfied.")
    elif smashed:
        parts.append("— failed: STRUCTURE SMASHED.")
    elif seq:
        parts.append("— failed: SEQUENTIAL VIOLATION.")
    elif pit:
        parts.append("— failed: PIT FAILURE.")
    elif ci < ri:
        parts.append("— failed: time limit reached before all balls caught.")
    else:
        parts.append(f"— failed: {str(fr) if fr else 'unknown reason'}.")
    lines.append(" ".join(parts))
    if smashed:
        peak = metrics.get("peak_joint_force")
        force_limit = metrics.get("max_joint_force_limit", 880.0)
        if _is_finite(peak) and _is_finite(force_limit):
            pk = _safe_float(peak)
            fl = _safe_float(force_limit)
            pct = (pk / fl * 100.0) if fl > 0 else 0.0
            lines.append(f"Peak joint force: {pk:.2f} N ({pct:.1f}% of {fl:.2f} N limit).")
    elif seq:
        seq_detail = metrics.get("sequential_detail")
        if isinstance(seq_detail, list) and seq_detail:
            for entry in seq_detail:
                preds = entry.get("predecessors_uncaught", [])
                if preds:
                    bi = entry.get("ball_idx", "?")
                    for p in preds:
                        pi = p.get("predecessor_idx", "?")
                        lines.append(f"Ball #{bi} arrived before Ball #{pi} was caught.")
        else:
            lines.append("A higher-index ball crossed the approach line before all lower-index balls were caught.")
    elif pit:
        lines.append("An uncaught ball fell below the pit threshold with excessive speed.")
    elif ci < ri:
        ball_margins = metrics.get("ball_margins")
        uncaptured = metrics.get("uncaptured_positions")
        if isinstance(ball_margins, list) and ball_margins:
            right_violations = []
            left_violations = []
            pit_violations = []
            near = []
            for bm in ball_margins:
                if not isinstance(bm, dict):
                    continue
                bi = bm.get("ball_idx", "?")
                mr = bm.get("margin_right")
                ml = bm.get("margin_left")
                mp = bm.get("margin_pit")
                x = bm.get("x", "?")
                if _is_finite(mr) and _safe_float(mr) < 0:
                    right_violations.append((bi, _safe_float(x), abs(_safe_float(mr))))
                elif _is_finite(ml) and _safe_float(ml) < 0:
                    left_violations.append((bi, _safe_float(x), abs(_safe_float(ml))))
                elif _is_finite(mp) and _safe_float(mp) < 0:
                    pit_violations.append((bi, _safe_float(bm.get("y", "?")), abs(_safe_float(mp))))
                else:
                    for key, label in [("margin_right", "right"), ("margin_left", "left"),
                                       ("margin_pit", "pit")]:
                        v = bm.get(key)
                        if _is_finite(v) and 0 < _safe_float(v) < 0.5:
                            near.append((bi, label, _safe_float(v)))
            if right_violations:
                by_x: Dict[float, List] = {}
                for bi, x, dist in right_violations:
                    x_rounded = round(x, 1)
                    by_x.setdefault(x_rounded, []).append((bi, dist))
                for x_pos, balls in sorted(by_x.items()):
                    dists = set(round(d, 2) for _, d in balls)
                    idxs = sorted(bi for bi, _ in balls)
                    if len(balls) == ri:
                        lines.append(
                            f"All {len(balls)} balls at x≈{x_pos:.2f} m are "
                            f"{max(dists):.2f} m past the right catch boundary."
                        )
                    elif len(balls) == 1:
                        lines.append(
                            f"Ball #{idxs[0]} at x≈{x_pos:.2f} m is "
                            f"{max(dists):.2f} m past the right catch boundary."
                        )
                    else:
                        lines.append(
                            f"Balls #{', #'.join(str(i) for i in idxs)} at x≈{x_pos:.2f} m are "
                            f"{max(dists):.2f} m past the right catch boundary."
                        )
            if left_violations:
                by_x: Dict[float, List] = {}
                for bi, x, dist in left_violations:
                    x_rounded = round(x, 1)
                    by_x.setdefault(x_rounded, []).append((bi, dist))
                for x_pos, balls in sorted(by_x.items()):
                    idxs = sorted(bi for bi, _ in balls)
                    if len(balls) == 1:
                        lines.append(f"Ball #{idxs[0]} at x≈{x_pos:.2f} m "
                                     f"is past the left catch boundary.")
                    else:
                        lines.append(f"Balls #{', #'.join(str(i) for i in idxs)} at x≈{x_pos:.2f} m "
                                     f"are past the left catch boundary.")
            if pit_violations:
                lines.append(f"{len(pit_violations)} ball(s) below pit threshold.")
    return lines

def _build_chronology(metrics: Dict[str, Any]) -> List[str]:
    lines: List[str] = []
    lines.append(_section("1. Temporal Event Chronology"))
    step = metrics.get("step_count")
    failed = metrics.get("failed", False)
    smashed = metrics.get("structure_smashed", False)
    seq = metrics.get("sequential_violation", False)
    pit = metrics.get("pit_failure", False)
    max_steps = metrics.get("max_steps", "?")
    lines.append(f"Step {int(step) if _is_finite(step) else '?'} / {max_steps} max.")
    joint_forces = metrics.get("joint_force_data")
    force_limit = metrics.get("max_joint_force_limit", 880.0)
    if isinstance(joint_forces, list) and joint_forces:
        elevated = [j for j in joint_forces if len(j) > 4 and _is_finite(j[4]) and _safe_float(j[4]) >= 0.50]
        if elevated:
            lines.append(f"\n**Elevated/critical joints** (≥50% of {_safe_float(force_limit):.2f} N limit):")
            for entry in sorted(elevated, key=lambda x: _safe_float(x[4]) if len(x) > 4 else 0, reverse=True):
                ji, ax, ay, mag, ratio = entry[0], entry[1], entry[2], entry[3], entry[4]
                pct = _safe_float(ratio) * 100.0
                lines.append(f"  Joint #{int(ji)} at ({_safe_float(ax):.2f}, {_safe_float(ay):.2f}): "
                             f"{_safe_float(mag):.2f} N ({pct:.1f}%)")
        elif smashed:
            peak_force = metrics.get("peak_joint_force")
            if _is_finite(peak_force) and _is_finite(force_limit):
                pk = _safe_float(peak_force)
                fl = _safe_float(force_limit)
                pct = (pk / fl * 100.0) if fl > 0 else 0.0
                lines.append(f"Structure smashed (historical peak {pk:.2f} N = {pct:.1f}% of {fl:.2f} N limit). "
                             f"Remaining joints nominal.")
            else:
                lines.append("Structure smashed — remaining joints nominal.")
        else:
            peak_force = metrics.get("peak_joint_force")
            if _is_finite(peak_force) and _is_finite(force_limit):
                pk = _safe_float(peak_force)
                fl = _safe_float(force_limit)
                pct = (pk / fl * 100.0) if fl > 0 else 0.0
                lines.append(f"All joints nominal (peak {pk:.2f} N = {pct:.1f}% of {fl:.2f} N limit).")
    elif smashed:
        peak = metrics.get("peak_joint_force")
        if _is_finite(peak) and _is_finite(force_limit):
            pk = _safe_float(peak)
            fl = _safe_float(force_limit)
            pct = (pk / fl * 100.0) if fl > 0 else float('inf')
            lines.append(f"Structure smashed — peak joint force {pk:.2f} N ({pct:.1f}% of {fl:.2f} N limit).")
            lines.append("  (Per-joint breakdown unavailable — joints already destroyed.)")
    seq_detail = metrics.get("sequential_detail")
    if isinstance(seq_detail, list) and seq_detail:
        all_uncaught = all(e.get("caught", False) is False for e in seq_detail if isinstance(e, dict))
        if all_uncaught and len(seq_detail) >= (metrics.get("balls_required_count", 7) or 7):
            lines.append(f"\nAll {len(seq_detail)} balls processed: none caught within target zone.")
        else:
            lines.append(f"\n**Ball approach chronology (approach line: x < {metrics.get('approach_x_m', 7.4)} m):**")
            for entry in seq_detail:
                if not isinstance(entry, dict):
                    continue
                bi = entry.get("ball_idx", "?")
                at_step = entry.get("approach_step")
                at_speed = entry.get("speed_at_approach")
                caught = entry.get("caught", False)
                preds = entry.get("predecessors_uncaught", [])
                status = "CAUGHT" if caught else "UNCAUGHT"
                speed_str = f"{_safe_float(at_speed):.2f} m/s" if _is_finite(at_speed) else "?"
                step_str = f"step {int(at_step)}" if _is_finite(at_step) else "?"
                lines.append(f"  Ball #{bi}: crossed at {step_str}, speed={speed_str}, {status}")
                if preds:
                    for p in preds:
                        pi = p.get("predecessor_idx", "?")
                        ps = p.get("speed")
                        ps_str = f"{_safe_float(ps):.2f} m/s" if _is_finite(ps) else "?"
                        lines.append(f"    → Predecessor Ball #{pi} was still uncaught (speed={ps_str})")
    elif seq:
        lines.append(f"\n**Sequential violation** — a higher-index ball crossed approach line before lower-index balls were caught.")
    if pit:
        pit_y = metrics.get("pit_y_threshold", 0.72)
        lines.append(f"\n**Pit failure** — uncaught ball dropped below y={pit_y} m with excessive speed.")
    if failed and not smashed and not pit and not seq and not success:
        lines.append(f"\n**Run terminated**: step {int(step) if _is_finite(step) else '?'} / {max_steps} max.")
    return lines

def _build_spatial(metrics: Dict[str, Any]) -> List[str]:
    lines: List[str] = []
    lines.append(_section("2. Spatial Diagnostics with Margins"))
    target_x_min = metrics.get("target_x_min", 7.0)
    target_x_max = metrics.get("target_x_max", 11.0)
    target_y_min = metrics.get("target_y_min", 0.5)
    target_y_max = metrics.get("target_y_max", 5.5)
    pit_y = 0.72
    txmin = _safe_float(target_x_min) if _is_finite(target_x_min) else 7.0
    txmax = _safe_float(target_x_max) if _is_finite(target_x_max) else 11.0
    tymin = _safe_float(target_y_min) if _is_finite(target_y_min) else 0.5
    tymax = _safe_float(target_y_max) if _is_finite(target_y_max) else 5.5
    lines.append(f"**Target zone**: x ∈ [{txmin:.2f}, {txmax:.2f}] m, y ∈ [{tymin:.2f}, {tymax:.2f}] m  |  "
                 f"**Pit threshold**: y < {pit_y:.2f} m (speed > 1.0 m/s)")
    per_pos = metrics.get("per_ball_positions", {})
    per_speed = metrics.get("per_ball_speeds", {})
    per_caught = metrics.get("per_ball_caught", {})
    if not isinstance(per_pos, dict) or not per_pos:
        return lines
    uncaptured_positions = []
    caught_positions = []
    for i in sorted(per_pos.keys()):
        pos_i = per_pos.get(i)
        if pos_i is None:
            continue
        caught_i = per_caught.get(i, False) if isinstance(per_caught, dict) else False
        bx_i = round(_safe_float(pos_i[0]), 2)
        by_i = round(_safe_float(pos_i[1]), 2)
        if caught_i:
            caught_positions.append((i, bx_i, by_i))
        else:
            sp_i = per_speed.get(i) if isinstance(per_speed, dict) else None
            m_right = txmax - bx_i
            uncaptured_positions.append((i, bx_i, by_i, sp_i, m_right))
    if uncaptured_positions:
        x_vals = [x for _, x, _, _, _ in uncaptured_positions]
        all_same_x = max(x_vals) - min(x_vals) < 0.1 if x_vals else False
        if all_same_x and len(uncaptured_positions) >= 3:
            bx = uncaptured_positions[0][1]
            m_right = uncaptured_positions[0][4]
            speed_vals = [s for _, _, _, s, _ in uncaptured_positions if _is_finite(s)]
            max_speed = max(speed_vals) if speed_vals else 0.0
            past_str = f"**{m_right:.2f}** m past right boundary" if m_right < 0 else f"{m_right:.2f} m from right boundary"
            lines.append(
                f"\nAll {len(uncaptured_positions)} balls uncaptured at x≈{bx:.2f} m, y ranging "
                f"{min(y for _, _, y, _, _ in uncaptured_positions):.2f}–"
                f"{max(y for _, _, y, _, _ in uncaptured_positions):.2f} m; "
                f"{past_str}. Max speed: {max_speed:.2f} m/s."
            )
        else:
            lines.append(f"\n**Per-ball spatial status** (+, positive margin = inside/above limit):")
            lines.append(f"  {'Ball':>6s}  {'Position (x,y)':>18s}  {'Speed':>8s}  "
                         f"{'R-margin':>10s}  {'L-margin':>10s}  {'T-margin':>10s}  "
                         f"{'B-margin':>10s}  {'Pit-margin':>11s}  {'Status':>10s}")
            lines.append(f"  {'-'*6}  {'-'*18}  {'-'*8}  {'-'*10}  {'-'*10}  "
                         f"{'-'*10}  {'-'*10}  {'-'*11}  {'-'*10}")
            def _mstr(v, dec=2):
                if not math.isfinite(v):
                    return f"{'?':>{dec+6}s}"
                s = f"{v:+.{dec}f}"
                return f"**{s}**" if v < 0 else s
            for i, bx_i, by_i, sp_i, _ in uncaptured_positions:
                m_right = txmax - bx_i
                m_left = bx_i - txmin
                m_top = tymax - by_i
                m_bottom = by_i - tymin
                m_pit = by_i - pit_y
                sp_str = f"{_safe_float(sp_i):.2f}" if _is_finite(sp_i) else "?"
                lines.append(
                    f"  #{i+1:5d}  ({bx_i:.2f}, {by_i:.2f})  {sp_str:>8s}  "
                    f"{_mstr(m_right):>10s}  {_mstr(m_left):>10s}  {_mstr(m_top):>10s}  "
                    f"{_mstr(m_bottom):>10s}  {_mstr(m_pit):>11s}  {'UNCGT':>10s}"
                )
    if caught_positions:
        lines.append(f"\n{len(caught_positions)} ball(s) caught: " +
                     ", ".join(f"#{i+1}" for i, _, _ in caught_positions))
    ball_margins = metrics.get("ball_margins")
    if isinstance(ball_margins, list) and ball_margins:
        near_items = []
        for bm in ball_margins:
            if not isinstance(bm, dict):
                continue
            bi = bm.get("ball_idx", "?")
            for key, label in [("margin_right", "right boundary"), ("margin_left", "left boundary"),
                               ("margin_bottom", "bottom boundary"), ("margin_pit", "pit line")]:
                v = bm.get(key)
                if _is_finite(v):
                    fv = _safe_float(v)
                    if 0 < fv < 0.5:
                        near_items.append(f"Ball #{bi}: {fv:.3f} m from {label}")
        if near_items:
            lines.append(f"\n**Near-boundary balls** (<0.5 m):")
            for item in near_items:
                lines.append(f"  {item}")
    return lines

def _build_load(metrics: Dict[str, Any]) -> List[str]:
    lines: List[str] = []
    lines.append(_section("3. Load & Stress Distribution"))
    joint_forces = metrics.get("joint_force_data")
    force_limit = metrics.get("max_joint_force_limit", 880.0)
    fatigue_limit = metrics.get("joint_fatigue_threshold", 760.0)
    peak = metrics.get("peak_joint_force")
    joint_count = metrics.get("joint_count")
    beam_count = metrics.get("beam_count")
    jc_str = f"{joint_count}" if joint_count is not None else "?"
    bc_str = f"{beam_count}" if beam_count is not None else "?"
    lines.append(f"**{jc_str} joints, {bc_str} beams**  |  "
                 f"**Force limits**: peak={_safe_float(force_limit):.2f} N, fatigue={_safe_float(fatigue_limit):.2f} N")
    if _is_finite(peak):
        pk = _safe_float(peak)
        fl = _safe_float(force_limit)
        pct = (pk / fl * 100.0) if fl > 0 else float('inf')
        lines.append(f"**Peak joint force**: {pk:.2f} N ({pct:.1f}% of limit)")
    if isinstance(joint_forces, list) and joint_forces:
        critical = [j for j in joint_forces if len(j) > 4 and _is_finite(j[4]) and _safe_float(j[4]) >= 0.80]
        elevated = [j for j in joint_forces if len(j) > 4 and _is_finite(j[4]) and 0.50 <= _safe_float(j[4]) < 0.80]
        nominal = [j for j in joint_forces if len(j) > 4 and _is_finite(j[4]) and _safe_float(j[4]) < 0.50]
        lines.append(f"\n**Stress tiers**: CRITICAL={len(critical)}, ELEVATED={len(elevated)}, "
                     f"NOMINAL={len(nominal)}")
        for label, group in [("CRITICAL", critical), ("ELEVATED", elevated)]:
            if group:
                for j in sorted(group, key=lambda x: _safe_float(x[4]) if len(x) > 4 else 0, reverse=True):
                    ji, ax, ay, mag, ratio = j[0], j[1], j[2], j[3], j[4]
                    lines.append(f"  {label} Joint #{int(ji)} at ({_safe_float(ax):.2f}, {_safe_float(ay):.2f}): "
                                 f"{_safe_float(mag):.2f} N = {_safe_float(ratio)*100:.1f}% of limit")
        if critical or elevated:
            sorted_forces = sorted(joint_forces, key=lambda x: float(x[4]) if len(x) > 4 and _is_finite(x[4]) else 0.0, reverse=True)
            lines.append(f"\n**Full joint force table:**")
            lines.append(f"  {'Joint':>6s}  {'Anchor (x,y)':>16s}  {'Force (N)':>10s}  {'%Limit':>8s}  {'Tier':>20s}")
            lines.append(f"  {'-'*6}  {'-'*16}  {'-'*10}  {'-'*8}  {'-'*20}")
            for entry in sorted_forces:
                if len(entry) < 5:
                    continue
                ji, ax, ay, mag, ratio = entry[0], entry[1], entry[2], entry[3], entry[4]
                if not all(_is_finite(v) for v in (ax, ay, mag, ratio)):
                    continue
                pct = _safe_float(ratio) * 100.0
                tier = (
                    "CRITICAL (>=100%)" if _safe_float(ratio) >= 1.0 else
                    "CRITICAL (>80%)" if _safe_float(ratio) >= 0.80 else
                    "ELEVATED (50-80%)" if _safe_float(ratio) >= 0.50 else
                    "NORMAL (<50%)"
                )
                lines.append(f"  {int(ji):6d}  ({_safe_float(ax):.2f}, {_safe_float(ay):.2f})  "
                             f"{_safe_float(mag):10.2f}  {pct:7.1f}%  {tier:>20s}")
    elif joint_count is not None and int(joint_count) > 0:
        lines.append(f"\n**Joint force data unavailable** — {int(joint_count)} joint(s) exist "
                      "but force data could not be read.")
    fat_data = metrics.get("joint_fatigue_data")
    if isinstance(fat_data, list) and fat_data:
        lines.append(f"\n**Joints exceeding fatigue threshold ({_safe_float(fatigue_limit):.2f} N):**")
        for entry in fat_data:
            if len(entry) < 5:
                continue
            ji, ax, ay, mag, ratio = entry[0], entry[1], entry[2], entry[3], entry[4]
            lines.append(f"  Joint #{int(ji)} at ({_safe_float(ax):.2f}, {_safe_float(ay):.2f}): "
                         f"{_safe_float(mag):.2f} N ({_safe_float(ratio)*100:.1f}% of fatigue limit)")
    return lines

def _build_energy(metrics: Dict[str, Any]) -> List[str]:
    lines: List[str] = []
    lines.append(_section("4. Energy & Power Flow"))
    total_ke = metrics.get("ball_kinetic_energy_total")
    initial_ke = metrics.get("initial_kinetic_energy")
    absorbed_pct = metrics.get("energy_absorbed_pct")
    ball_masses = metrics.get("ball_masses")
    per_speed = metrics.get("per_ball_speeds", {})
    if _is_finite(total_ke):
        tke = _safe_float(total_ke)
        lines.append(f"**Total KE**: {tke:.1f} J  |  **Absorbed**: "
                     f"{_safe_float(absorbed_pct):.1f}% " if _is_finite(absorbed_pct) else
                     f"**Total KE**: {tke:.1f} J")
    if _is_finite(absorbed_pct):
        ap = _safe_float(absorbed_pct)
        lines[-1] = f"**Total KE**: {tke:.1f} J  |  **Absorbed**: {ap:.1f}%  |  **Remaining**: {100.0 - ap:.1f}%"
    if _is_finite(total_ke) and _is_finite(initial_ke):
        tke = _safe_float(total_ke)
        ike = _safe_float(initial_ke)
        absorbed = ike - tke
        if ike > 1e-9:
            if absorbed >= 0:
                lines.append(f"**Energy flow**: {ike:.1f} J initial → {absorbed:.1f} J dissipated → {tke:.1f} J remaining")
            else:
                lines.append(f"**Energy flow**: {ike:.1f} J initial → KE +{abs(absorbed):.1f} J → {tke:.1f} J remaining "
                             f"(collisions raised KE above initial level)")
    if isinstance(ball_masses, list) and ball_masses and isinstance(per_speed, dict) and per_speed:
        mass_list = ball_masses
        tke = _safe_float(total_ke) if _is_finite(total_ke) else 1e-9
        ball_ke_list = []
        for i in sorted(per_speed.keys()):
            sp_i = _safe_float(per_speed[i]) if _is_finite(per_speed.get(i)) else 0.0
            mass_i = _safe_float(mass_list[i]) if i < len(mass_list) else 0.0
            ke_i = 0.5 * mass_i * sp_i * sp_i
            pct_i = (ke_i / tke * 100.0) if tke > 1e-9 else 0.0
            ball_ke_list.append((i, mass_i, sp_i, ke_i, pct_i))
        active_balls = [(i, m, s, k, p) for i, m, s, k, p in ball_ke_list if p > 1.0]
        zero_balls = [(i, m, s, k, p) for i, m, s, k, p in ball_ke_list if p <= 1.0 and k < 1e-6]
        if len(active_balls) <= 2 and len(ball_ke_list) > 3:
            dom = max(ball_ke_list, key=lambda x: x[4])
            lines.append(f"\n**Per-ball KE**: Ball #{dom[0]+1} holds {dom[4]:.1f}% of total ({dom[3]:.1f} J at "
                         f"{dom[2]:.1f} m/s, {dom[1]:.1f} kg). "
                         f"{len(zero_balls)} ball(s) stationary.")
            for i, m, s, k, p in active_balls:
                if i != dom[0]:
                    lines.append(f"  Ball #{i+1}: {k:.1f} J ({p:.1f}%) at {s:.1f} m/s")
        else:
            lines.append(f"\n**Per-ball kinetic energy:**")
            lines.append(f"  {'Ball':>6s}  {'Mass (kg)':>10s}  {'Speed (m/s)':>12s}  {'KE (J)':>12s}  {'%Total':>8s}")
            lines.append(f"  {'-'*6}  {'-'*10}  {'-'*12}  {'-'*12}  {'-'*8}")
            for i, m, s, k, p in ball_ke_list:
                lines.append(f"  #{i+1:5d}  {m:10.2f}  {s:12.3f}  {k:12.1f}  {p:7.1f}%")
    return lines

def _build_constraints(metrics: Dict[str, Any]) -> List[str]:
    lines: List[str] = []
    lines.append(_section("5. Constraint Satisfaction Profile"))
    reportable: List[str] = []
    beam_count = metrics.get("beam_count")
    max_beams = metrics.get("max_beam_count", 9)
    if beam_count is not None:
        bc = int(beam_count)
        mb = int(max_beams) if _is_finite(max_beams) else 9
        margin = mb - bc
        pct = (bc / mb * 100.0) if mb > 0 else 0.0
        if bc > mb:
            reportable.append(f"FAIL  Beam count: {bc}/{mb} (over by {abs(margin)})")
        elif pct >= 80.0:
            reportable.append(f"NEAR  Beam count: {bc}/{mb} ({pct:.0f}% used, margin: {margin})")
    structure_mass = metrics.get("structure_mass")
    max_mass = metrics.get("max_structure_mass", 10.0)
    if _is_finite(structure_mass):
        sm = _safe_float(structure_mass)
        mm = _safe_float(max_mass) if _is_finite(max_mass) else 10.0
        pct = (sm / mm * 100.0) if mm > 0 else 0.0
        if sm >= mm:
            reportable.append(f"FAIL  Structure mass: {sm:.2f}/{mm:.2f} kg (over)")
        elif pct >= 80.0:
            reportable.append(f"NEAR  Structure mass: {sm:.2f}/{mm:.2f} kg ({pct:.0f}% used)")
    has_anchor = metrics.get("has_rigid_ground_anchor")
    if has_anchor is False:
        reportable.append("FAIL  Rigid ground anchor: MISSING")
    caught = metrics.get("balls_caught_count")
    required = metrics.get("balls_required_count", 7)
    if _is_finite(caught):
        ci = int(caught)
        ri = int(required) if _is_finite(required) else 7
        if ci < ri:
            reportable.append(f"FAIL  Balls caught: {ci}/{ri} (gap: {ri - ci})")
    smashed = metrics.get("structure_smashed", False)
    if smashed:
        reportable.append("FAIL  Structure integrity: SMASHED")
    seq = metrics.get("sequential_violation", False)
    if seq:
        reportable.append("FAIL  Sequential order: VIOLATED")
    pit = metrics.get("pit_failure", False)
    if pit:
        reportable.append("FAIL  Pit safety: FAILURE")
    if not reportable:
        lines.append("All constraints PASS with comfortable margins.")
    else:
        for item in reportable:
            lines.append(f"  {item}")
        pass_count = 0
        bc = metrics.get("beam_count")
        mb = metrics.get("max_beam_count", 9)
        if bc is not None and int(bc) <= (int(mb) if _is_finite(mb) else 9):
            pct = (int(bc) / (int(mb) if _is_finite(mb) else 9) * 100.0)
            if pct < 80.0:
                pass_count += 1
        sm = metrics.get("structure_mass")
        mm = metrics.get("max_structure_mass", 10.0)
        if _is_finite(sm) and _is_finite(mm) and _safe_float(sm) < _safe_float(mm) * 0.80:
            pass_count += 1
        if not smashed:
            pass_count += 1
        if not seq:
            pass_count += 1
        if not pit:
            pass_count += 1
        if _is_finite(caught) and int(caught) >= int(metrics.get("balls_required_count", 7)):
            pass_count += 1
        if pass_count > 0:
            lines.append(f"  ({pass_count} additional constraint(s) PASS with comfortable margin)")
    return lines

def _build_numerical(metrics: Dict[str, Any]) -> List[str]:
    lines: List[str] = []
    issues: List[str] = []
    per_pos = metrics.get("per_ball_positions", {})
    if isinstance(per_pos, dict):
        for i, pos_i in per_pos.items():
            if pos_i is None:
                continue
            try:
                bx, by = float(pos_i[0]), float(pos_i[1])
                if not math.isfinite(bx) or not math.isfinite(by):
                    issues.append(f"Ball #{i+1} position non-finite: ({bx}, {by})")
                if abs(bx) > 1000 or abs(by) > 1000:
                    issues.append(f"Ball #{i+1} position out of bounds: ({bx:.1f}, {by:.1f})")
            except (TypeError, ValueError):
                issues.append(f"Ball #{i+1} position unparseable")
    per_speed = metrics.get("per_ball_speeds", {})
    if isinstance(per_speed, dict):
        for i, sp in per_speed.items():
            if not _is_finite(sp):
                issues.append(f"Ball #{i+1} speed non-finite: {sp}")
            elif _safe_float(sp) > 500.0:
                issues.append(f"Ball #{i+1} speed extreme: {_safe_float(sp):.1f} m/s")
    joint_forces = metrics.get("joint_force_data")
    if isinstance(joint_forces, list):
        for entry in joint_forces:
            if len(entry) < 4:
                continue
            mag = entry[3]
            if not _is_finite(mag):
                issues.append(f"Joint #{entry[0]} force non-finite")
            elif _safe_float(mag) > 1e7:
                issues.append(f"Joint #{entry[0]} force extreme: {_safe_float(mag):.1f} N")
    total_ke = metrics.get("ball_kinetic_energy_total")
    if _is_finite(total_ke) and _safe_float(total_ke) < 0:
        issues.append(f"Negative KE: {_safe_float(total_ke):.1f} J")
    sm = metrics.get("structure_mass")
    if _is_finite(sm) and _safe_float(sm) < 0:
        issues.append(f"Negative structure mass: {_safe_float(sm):.2f} kg")
    sc = metrics.get("step_count")
    if _is_finite(sc) and int(sc) < 0:
        issues.append(f"Negative step count: {int(sc)}")
    if issues:
        lines.append(_section("6. Numerical Health"))
        lines.append(f"⚠ WARNING: {len(issues)} numerical issue(s):")
        for issue in issues:
            lines.append(f"  - {issue}")
    else:
        lines.append(_section("6. Numerical Health"))
        lines.append("All values nominal.")
    return lines

def format_task_metrics(metrics: Dict[str, Any]) -> List[str]:
    if not metrics:
        return ["**No metrics available**"]
    out: List[str] = []
    parts = []
    caught = metrics.get("balls_caught_count")
    required = metrics.get("balls_required_count")
    if _is_finite(caught) and _is_finite(required):
        ci = int(caught)
        ri = int(required)
        parts.append(f"Balls: {ci}/{ri}")
    if _is_finite(metrics.get("ball_speed")):
        parts.append(f"Speed: {_safe_float(metrics['ball_speed']):.1f} m/s")
    sm = metrics.get("structure_mass")
    ms = metrics.get("max_structure_mass")
    if _is_finite(sm):
        s = f"Mass: {_safe_float(sm):.2f}"
        if _is_finite(ms):
            s += f"/{_safe_float(ms):.2f} kg"
        parts.append(s)
    bc = metrics.get("beam_count")
    jc = metrics.get("joint_count")
    if bc is not None or jc is not None:
        bits = []
        if bc is not None:
            bits.append(f"beams={bc}")
        if jc is not None:
            bits.append(f"joints={jc}")
        parts.append(", ".join(bits))
    smashed = metrics.get("structure_smashed")
    if smashed:
        parts.append("SMASHED")
    seq = metrics.get("sequential_violation")
    if seq:
        parts.append("SEQ_VIOL")
    pit = metrics.get("pit_failure")
    if pit:
        parts.append("PIT_FAIL")
    out.append(" | ".join(parts))
    out.append("")
    try:
        out.extend(_build_summary(metrics))
    except Exception:
        pass
    try:
        out.extend(_build_chronology(metrics))
    except Exception:
        pass
    try:
        out.extend(_build_spatial(metrics))
    except Exception:
        pass
    try:
        out.extend(_build_load(metrics))
    except Exception:
        pass
    try:
        out.extend(_build_energy(metrics))
    except Exception:
        pass
    try:
        out.extend(_build_constraints(metrics))
    except Exception:
        pass
    try:
        out.extend(_build_numerical(metrics))
    except Exception:
        pass
    return out

def get_improvement_suggestions(
    metrics: Dict[str, Any],
    score: float,
    success: bool,
    failed: bool,
    failure_reason: str = None,
    error: str = None,

) -> List[str]:
    return []
