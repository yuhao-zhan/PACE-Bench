from __future__ import annotations

import math

from typing import Any, Dict, List, Optional, Tuple

def _is_finite_number(x: Any) -> bool:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return False
    return math.isfinite(v)

def _fmt_float(x: Any, nd: int = 2) -> str:
    if not _is_finite_number(x):
        return "non-finite"
    return f"{float(x):.{nd}f}"

def _ratio(numer: float, denom: float) -> Optional[float]:
    if not _is_finite_number(denom) or float(denom) == 0.0:
        return None
    if not _is_finite_number(numer):
        return None
    return float(numer) / float(denom)

def _margin_pct(peak: float, limit: float) -> Optional[float]:
    r = _ratio(peak, limit)
    if r is None:
        return None
    return (1.0 - r) * 100.0

def _margin_str(peak: float, limit: float, unit: str = "") -> str:
    mp = _margin_pct(peak, limit)
    if mp is None:
        return "margin unknown"
    if mp >= 0:
        return f"+{mp:.1f}% headroom ({_fmt_float(peak)} / {_fmt_float(limit)}{unit})"
    else:
        return f"{mp:.1f}% exceeded ({_fmt_float(peak)} / {_fmt_float(limit)}{unit})"

def _band_margin_y(y: float, band: Any) -> Optional[Tuple[str, float]]:
    if not isinstance(band, (list, tuple)) or len(band) != 2:
        return None
    lo, hi = float(band[0]), float(band[1])
    if not (math.isfinite(lo) and math.isfinite(hi) and lo < hi):
        return None
    if y < lo:
        return ("below_band", lo - y)
    if y > hi:
        return ("above_band", y - hi)
    return ("inside_band", min(y - lo, hi - y))

def _tier_label(ratio_pct: float) -> str:
    if ratio_pct > 100.0:
        return "FAILED"
    elif ratio_pct >= 80.0:
        return "CRITICAL"
    elif ratio_pct >= 50.0:
        return "ELEVATED"
    else:
        return "NOMINAL"

def _is_missing_or_empty(val: Any) -> bool:
    if val is None:
        return True
    if isinstance(val, (list, dict)) and len(val) == 0:
        return True
    return False

def _format_env_line(metrics: Dict[str, Any]) -> str:
    env_parts = []
    for key, label, nd in (
        ("noise_strength", "noise", 1),
        ("coherent_pulse_interval", "pulse_int", None),
        ("coherent_pulse_force", "pulse_force", 1),
        ("phased_storm_mult", "storm", 1),
    ):
        v = metrics.get(key)
        if v is not None and (nd is None or _is_finite_number(v)):
            if nd is None:
                env_parts.append(f"{label}={v}")
            else:
                env_parts.append(f"{label}={_fmt_float(v, nd)}")
    if not env_parts:
        return ""
    return "Env: " + ", ".join(env_parts) + "."

def _format_mass_line(metrics: Dict[str, Any]) -> str:
    sm = metrics.get("structure_mass")
    mm = metrics.get("max_structure_mass")
    if sm is not None and _is_finite_number(sm) and mm is not None and _is_finite_number(mm):
        return f"Mass: {_fmt_float(sm, 2)} / {_fmt_float(mm, 1)} kg ({_margin_str(float(sm), float(mm))})."
    return ""

def _format_topo_line(metrics: Dict[str, Any]) -> str:
    parts = []
    bc = metrics.get("body_count")
    ibc = metrics.get("initial_body_count")
    if bc is not None and ibc is not None:
        parts.append(f"Beams: {bc}/{ibc} ({max(0, int(ibc) - int(bc))} lost)")
    jc = metrics.get("joint_count")
    ijc = metrics.get("initial_joint_count")
    if jc is not None and ijc is not None:
        parts.append(f"Joints: {jc}/{ijc} ({max(0, int(ijc) - int(jc))} lost)")
    return ". ".join(parts) + "." if parts else ""

def _collect_constraints(metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
    constraints: List[Dict[str, Any]] = []
    span_ok = metrics.get("span_check_passed")
    span_msg = metrics.get("span_check_message", "")
    constraints.append({
        "label": "Span / height requirement",
        "phase": "build-time",
        "pass": bool(span_ok),
        "status_str": "✅" if span_ok else "❌",
        "detail": str(span_msg),
    })
    mass = metrics.get("structure_mass")
    max_mass = metrics.get("max_structure_mass")
    if mass is not None and _is_finite_number(mass) and max_mass is not None and _is_finite_number(max_mass):
        mf, ml = float(mass), float(max_mass)
        mp = _margin_pct(mf, ml)
        constraints.append({
            "label": "Mass budget",
            "phase": "build-time",
            "pass": mf <= ml,
            "status_str": "✅" if mf <= ml else "❌",
            "pct": mp,
            "margin_str": f"+{mp:.1f}%" if mp is not None and mp >= 0 else f"{mp:.1f}%" if mp is not None else "—",
        })
    mjf = metrics.get("max_joint_force")
    jbf = metrics.get("joint_break_force")
    if mjf is not None and _is_finite_number(mjf) and jbf is not None and _is_finite_number(jbf):
        mp = _margin_pct(float(mjf), float(jbf))
        constraints.append({
            "label": "Joint reaction force",
            "phase": "runtime",
            "pass": float(mjf) <= float(jbf),
            "status_str": "✅" if float(mjf) <= float(jbf) else "❌",
            "pct": mp,
            "margin_str": f"+{mp:.1f}%" if mp is not None and mp >= 0 else f"{mp:.1f}%" if mp is not None else "—",
        })
    mjt = metrics.get("max_joint_torque")
    jbt = metrics.get("joint_break_torque")
    if mjt is not None and _is_finite_number(mjt) and jbt is not None and _is_finite_number(jbt):
        mp = _margin_pct(float(mjt), float(jbt))
        constraints.append({
            "label": "Joint reaction torque",
            "phase": "runtime",
            "pass": float(mjt) <= float(jbt),
            "status_str": "✅" if float(mjt) <= float(jbt) else "❌",
            "pct": mp,
            "margin_str": f"+{mp:.1f}%" if mp is not None and mp >= 0 else f"{mp:.1f}%" if mp is not None else "—",
        })
    dmg = metrics.get("max_joint_damage")
    dlim = metrics.get("damage_limit")
    if dmg is not None and _is_finite_number(dmg) and dlim is not None and _is_finite_number(dlim):
        mp = _margin_pct(float(dmg), float(dlim))
        constraints.append({
            "label": "Cumulative joint damage",
            "phase": "runtime",
            "pass": float(dmg) < float(dlim),
            "status_str": "✅" if float(dmg) < float(dlim) else "❌",
            "pct": mp,
            "margin_str": f"+{mp:.1f}%" if mp is not None and mp >= 0 else f"{mp:.1f}%" if mp is not None else "—",
        })
    pav = metrics.get("peak_body_angvel")
    avt = metrics.get("beam_angvel_thresh")
    if pav is not None and _is_finite_number(pav) and avt is not None and _is_finite_number(avt):
        mp = _margin_pct(float(pav), float(avt))
        n_spin = metrics.get("num_bodies_destroyed_spin", 0)
        passed = float(pav) <= float(avt) or n_spin == 0
        constraints.append({
            "label": "Beam angular velocity",
            "phase": "runtime",
            "pass": passed,
            "status_str": "✅" if passed else "❌",
            "pct": mp,
            "margin_str": f"+{mp:.1f}%" if mp is not None and mp >= 0 else f"{mp:.1f}%" if mp is not None else "—",
        })
    tsr = metrics.get("tip_stability_ratio")
    tsq = metrics.get("tip_stability_required")
    if tsr is not None and _is_finite_number(tsr):
        required = float(tsq) if tsq is not None and _is_finite_number(tsq) else 0.0
        passed = float(tsr) >= required
        constraints.append({
            "label": "Tip vertical band stability",
            "phase": "runtime",
            "pass": passed,
            "status_str": "✅" if passed else "❌",
            "pct": (float(tsr) - required) * 100.0,
            "margin_str": (
                f"+{(float(tsr) - required) * 100:.1f}%"
                if float(tsr) >= required
                else f"{(float(tsr) - required) * 100:.1f}%"
            ),
        })
    ijc = metrics.get("initial_joint_count", 0)
    jc = metrics.get("joint_count", 0)
    ibc = metrics.get("initial_body_count", 0)
    bc = metrics.get("body_count", 0)
    nj_removed = max(0, int(ijc) - int(jc))
    nb_removed = max(0, int(ibc) - int(bc))
    constraints.append({
        "label": "Structural integrity",
        "phase": "runtime",
        "pass": nj_removed == 0 and nb_removed == 0,
        "status_str": "✅" if nj_removed == 0 and nb_removed == 0 else "❌",
        "pct": 0.0 if (nj_removed == 0 and nb_removed == 0) else -100.0,
        "margin_str": "PASS" if (nj_removed == 0 and nb_removed == 0) else "FAIL",
    })
    return constraints

def _format_failure_timeline(metrics: Dict[str, Any]) -> List[str]:
    parts: List[str] = []
    timeline = metrics.get("failure_event_timeline")
    if _is_missing_or_empty(timeline):
        return parts
    parts.append("**Failure Timeline** (ordered by step):")
    parts.append("")
    parts.append("| Step | Event | Position (x, y) | Dist (m) | Detail |")
    parts.append("|------|-------|-----------------|-----------|--------|")
    max_events = min(15, len(timeline))
    for ev in timeline[:max_events]:
        step = ev.get("step", "?")
        etype = ev.get("event_type", "unknown")
        px = ev.get("pos_x")
        py = ev.get("pos_y")
        dist = ev.get("dist_from_support")
        detail = ev.get("fail_type") or ev.get("fail_reason") or "—"
        pos_str = f"({_fmt_float(px)}, {_fmt_float(py)})" if px is not None and py is not None else "—"
        dist_str = f"{_fmt_float(dist, 2)}" if dist is not None else "—"
        emoji = "🔗" if etype == "joint_failure" else "💥"
        parts.append(f"| {step} | {emoji} {etype} | {pos_str} | {dist_str} | {detail} |")
    if len(timeline) > max_events:
        parts.append(f"| ... | ... | ... | ... | (+ {len(timeline) - max_events} more) |")
    jf_events = [e for e in timeline if e.get("event_type") == "joint_failure"]
    bd_events = [e for e in timeline if e.get("event_type") == "body_destroy"]
    summary_parts = []
    if jf_events:
        summary_parts.append(f"{len(jf_events)} joint failure(s)")
    if bd_events:
        bd_spin = sum(1 for e in bd_events if e.get("fail_reason") == "spin")
        bd_orphan = len(bd_events) - bd_spin
        body_detail = f"{len(bd_events)} body destruction(s)"
        if bd_spin > 0 and bd_orphan > 0:
            body_detail += f" ({bd_spin} spin, {bd_orphan} orphan)"
        elif bd_spin > 0:
            body_detail += " (all spin)"
        elif bd_orphan > 0:
            body_detail += " (all orphan)"
        summary_parts.append(body_detail)
    if summary_parts:
        parts.append("Summary: " + "; ".join(summary_parts) + ".")
    return parts

def _format_spatial_diagnostics(metrics: Dict[str, Any]) -> List[str]:
    parts: List[str] = []
    parts.append("**Spatial Diagnostics**:")
    tip_y = metrics.get("tip_y_last")
    band = metrics.get("tip_y_band")
    if tip_y is not None and _is_finite_number(tip_y):
        bm = _band_margin_y(float(tip_y), band)
        if bm:
            state, dist = bm
            parts.append(
                f"Tip y = {_fmt_float(tip_y, 3)} m. "
                f"Band {band}: **{state}**, clearance {_fmt_float(dist, 3)} m."
            )
    worst_pos = metrics.get("worst_spin_body_pos")
    worst_peak = metrics.get("worst_spin_body_peak")
    av_thresh = metrics.get("beam_angvel_thresh")
    if (worst_pos is not None and isinstance(worst_pos, (list, tuple))
            and len(worst_pos) >= 2 and worst_peak is not None
            and _is_finite_number(worst_peak) and float(worst_peak) > 0.0):
        dx = float(worst_pos[0]) - 5.75
        margin_str = ""
        if av_thresh is not None and _is_finite_number(av_thresh):
            margin_str = f" ({_margin_str(float(worst_peak), float(av_thresh))})"
        parts.append(
            f"Worst spin: beam at ({_fmt_float(worst_pos[0])}, {_fmt_float(worst_pos[1])}), "
            f"{_fmt_float(dx, 2)} m from support, "
            f"peak |ω| = {_fmt_float(worst_peak, 3)} rad/s{margin_str}."
        )
    fj_pos = metrics.get("first_joint_fail_pos")
    fj_step = metrics.get("first_joint_fail_step")
    if fj_pos is not None and fj_step is not None:
        dx = float(fj_pos[0]) - 5.75 if isinstance(fj_pos, (list, tuple)) and len(fj_pos) >= 1 else None
        dist_str = f" ({_fmt_float(dx, 2)} m from support)" if dx is not None else ""
        parts.append(
            f"First joint failure: step {fj_step}, "
            f"({_fmt_float(fj_pos[0])}, {_fmt_float(fj_pos[1])}){dist_str}."
        )
    fb_pos = metrics.get("first_body_fail_pos")
    fb_step = metrics.get("first_body_fail_step")
    if fb_pos is not None and fb_step is not None:
        dx = float(fb_pos[0]) - 5.75 if isinstance(fb_pos, (list, tuple)) and len(fb_pos) >= 1 else None
        dist_str = f" ({_fmt_float(dx, 2)} m from support)" if dx is not None else ""
        parts.append(
            f"First body destruction: step {fb_step}, "
            f"({_fmt_float(fb_pos[0])}, {_fmt_float(fb_pos[1])}){dist_str}."
        )
    return parts if len(parts) > 1 else []

def _format_load_stress(metrics: Dict[str, Any]) -> List[str]:
    parts: List[str] = []
    parts.append("**Load & Stress**:")
    jbf = metrics.get("joint_break_force")
    jbt = metrics.get("joint_break_torque")
    dlimit = metrics.get("damage_limit")
    av_thresh = metrics.get("beam_angvel_thresh")
    per_joint = metrics.get("per_joint_stress_data")
    per_body = metrics.get("per_body_angvel_data")
    joint_output: List[str] = []
    if not _is_missing_or_empty(per_joint):
        active_joints = [
            j for j in per_joint
            if j.get("status") == "active" and "peak_force" in j
            and _is_finite_number(j.get("peak_force"))
        ]
        all_zero = all(float(j.get("peak_force", 0.0)) < 0.001 for j in active_joints)
        if all_zero:
            joint_output.append(
                f"No joint stress ({len(active_joints)} active joints, all forces < 0.001 N)."
            )
        else:
            force_limit = float(jbf) if jbf is not None and _is_finite_number(jbf) and float(jbf) > 0 else None
            torque_limit = float(jbt) if jbt is not None and _is_finite_number(jbt) and float(jbt) > 0 else None
            stressed_joints = []
            nominal_joints = []
            for j in active_joints:
                f = float(j.get("peak_force", 0.0))
                t = float(j.get("peak_torque", 0.0))
                if force_limit and _ratio(f, force_limit) is not None:
                    ratio = _ratio(f, force_limit)
                    tier = _tier_label(ratio * 100.0)
                else:
                    ratio, tier = None, "—"
                if tier in ("FAILED", "CRITICAL", "ELEVATED"):
                    stressed_joints.append((f, j, ratio, tier, t))
                else:
                    nominal_joints.append((f, j, ratio, tier, t))
            by_force = sorted(stressed_joints + nominal_joints, key=lambda x: x[0], reverse=True)
            display_joints = list(stressed_joints)
            shown_ids = {id(j) for _, j, _, _, _ in display_joints}
            for f, j, r, tier, t in by_force[:5]:
                if id(j) not in shown_ids:
                    display_joints.append((f, j, r, tier, t))
                    shown_ids.add(id(j))
            if display_joints:
                joint_output.append("")
                joint_output.append("| # | Position (x, y) | Dist (m) | Force (N) | Torque (N·m) | Force% | Torque% | Tier | Ground? |")
                joint_output.append("|---|-----------------|-----------|-----------|--------------|--------|---------|------|---------|")
                for rank, (f, j, fr, tier, t) in enumerate(display_joints[:15], 1):
                    px = _fmt_float(j.get("anchor_x"))
                    py = _fmt_float(j.get("anchor_y"))
                    dist = _fmt_float(j.get("dist_from_support"), 2)
                    f_str = _fmt_float(f)
                    t_str = _fmt_float(t)
                    fr_str = f"{fr * 100:.1f}%" if fr is not None else "—"
                    tr = _ratio(t, torque_limit) if torque_limit else None
                    tr_str = f"{tr * 100:.1f}%" if tr is not None else "—"
                    ground = "yes" if j.get("is_ground") else "no"
                    joint_output.append(
                        f"| {rank} | ({px}, {py}) | {dist} | {f_str} | {t_str} | {fr_str} | {tr_str} | {tier} | {ground} |"
                    )
                if len(display_joints) > 15:
                    joint_output.append(f"| ... | ... | ... | ... | ... | ... | ... | ... | (+ {len(display_joints) - 15} more) |")
            if force_limit:
                n_failed = sum(1 for _, _, r, _, _ in stressed_joints + nominal_joints
                              if r is not None and _ratio(r, 1.0) is not None and r >= 1.0)
                n_crit = sum(1 for _, _, r, _, _ in stressed_joints + nominal_joints
                            if r is not None and 0.80 <= r < 1.0)
                n_elev = sum(1 for _, _, r, _, _ in stressed_joints + nominal_joints
                            if r is not None and 0.50 <= r < 0.80)
                n_nom = len(active_joints) - n_failed - n_crit - n_elev
                tier_parts = []
                if n_failed: tier_parts.append(f"{n_failed} FAILED")
                if n_crit: tier_parts.append(f"{n_crit} CRITICAL")
                if n_elev: tier_parts.append(f"{n_elev} ELEVATED")
                tier_parts.append(f"{n_nom} NOMINAL")
                joint_output.append("Tiers: " + ", ".join(tier_parts) + f" (of {len(active_joints)} joints).")
            failed_joints = [j for j in per_joint if j.get("status") == "failed"]
            if failed_joints:
                joint_output.append(f"{len(failed_joints)} joint(s) previously failed (see Failure Timeline).")
        dmg = metrics.get("max_joint_damage")
        if dmg is not None and _is_finite_number(dmg) and float(dmg) > 0 and dlimit is not None and _is_finite_number(dlimit):
            mp = _margin_pct(float(dmg), float(dlimit))
            if mp is not None:
                joint_output.append(f"Max joint damage: {_fmt_float(dmg, 1)} / {_fmt_float(dlimit, 1)} ({_margin_str(float(dmg), float(dlimit))}).")
    if not joint_output:
        joint_output.append("No joint stress data available.")
    parts.extend(joint_output)
    if not _is_missing_or_empty(per_body) and av_thresh is not None and _is_finite_number(av_thresh):
        thresh = float(av_thresh)
        parts.append("")
        all_still = all(float(b.get("peak_angvel", 0.0)) < 0.001 for b in per_body)
        if all_still:
            parts.append(f"Beam stability: all {len(per_body)} beams at rest (peak |ω| < 0.001 rad/s, threshold {_fmt_float(thresh, 2)} rad/s).")
        else:
            sorted_bodies = sorted(per_body, key=lambda b: float(b.get("peak_angvel", 0.0)), reverse=True)
            n_critical = sum(1 for b in sorted_bodies if float(b.get("peak_angvel", 0.0)) >= thresh * 0.80)
            n_exceeded = sum(1 for b in sorted_bodies if float(b.get("peak_angvel", 0.0)) > thresh)
            if n_critical == 0:
                parts.append(
                    f"Beam stability: all {len(sorted_bodies)} NOMINAL "
                    f"(peak |ω| = {_fmt_float(sorted_bodies[0].get('peak_angvel', 0.0), 3)} rad/s "
                    f"< {_fmt_float(thresh, 2)} rad/s threshold)."
                )
            else:
                parts.append("| # | Position (x, y) | Dist (m) | Peak |ω| (r/s) | vs thresh | Tier | Mass (kg) |")
                parts.append("|---|-----------------|-----------|----------------|--------------|------|-----------|")
                max_rows = min(10, len(sorted_bodies))
                for rank, b in enumerate(sorted_bodies[:max_rows], 1):
                    px = _fmt_float(b.get("pos_x"))
                    py = _fmt_float(b.get("pos_y"))
                    dist = _fmt_float(b.get("dist_from_support"), 2)
                    av = float(b.get("peak_angvel", 0.0))
                    av_str = _fmt_float(av, 3)
                    mass = _fmt_float(b.get("mass"), 2)
                    r = _ratio(av, thresh)
                    ratio_str = f"{r * 100:.1f}%" if r is not None else "—"
                    tier = _tier_label(r * 100.0) if r is not None else "—"
                    flag = " ⚠" if av > thresh else ""
                    parts.append(
                        f"| {rank} | ({px}, {py}) | {dist} | {av_str}{flag} | {ratio_str} | {tier} | {mass} |"
                    )
                if len(sorted_bodies) > max_rows:
                    parts.append(f"| ... | ... | ... | ... | ... | ... | (+ {len(sorted_bodies) - max_rows} more) |")
                spin_parts = []
                if n_exceeded: spin_parts.append(f"{n_exceeded} exceeded threshold")
                if n_critical - n_exceeded > 0: spin_parts.append(f"{n_critical - n_exceeded} critical")
                spin_parts.append(f"{len(sorted_bodies) - n_critical} nominal")
                parts.append("Spin: " + ", ".join(spin_parts) + ".")
    elif av_thresh is None or not _is_finite_number(av_thresh):
        parts.append("")
        parts.append("Beam stability: no angular velocity threshold configured.")
    return parts

def _format_energy(metrics: Dict[str, Any]) -> List[str]:
    return ["**Energy & Power Flow**: N/A (structural endurance task — no energy conversion chain)."]

def _format_constraint_profile(metrics: Dict[str, Any]) -> List[str]:
    parts: List[str] = []
    parts.append("**Constraints**:")
    constraints = _collect_constraints(metrics)
    if not constraints:
        parts.append("No constraint data available.")
        return parts
    n_pass = sum(1 for c in constraints if c["pass"])
    n_fail = len(constraints) - n_pass
    if n_fail == 0:
        parts.append(f"{n_pass}/{len(constraints)} PASS.")
    else:
        parts.append(f"{n_pass}/{len(constraints)} PASS, {n_fail} FAIL.")
    failures = [c for c in constraints if not c["pass"]]
    if failures:
        fail_lines = []
        for c in failures:
            fail_lines.append(f"{c['label']} ({c.get('margin_str', 'FAIL')})")
        parts.append("FAIL: " + "; ".join(fail_lines) + ".")
    near_limit = []
    for c in constraints:
        if c["pass"]:
            pct = c.get("pct")
            if pct is not None and _is_finite_number(pct):
                if c["label"] == "Structural integrity":
                    continue
                if c["label"] == "Tip vertical band stability":
                    if 0 <= float(pct) < 30.0:
                        near_limit.append(f"{c['label']} ({c.get('margin_str', '?')})")
                elif c["label"] == "Span / height requirement":
                    continue
                elif 0 <= float(pct) < 30.0:
                    near_limit.append(f"{c['label']} ({c.get('margin_str', '?')})")
    if near_limit:
        parts.append("Near-limit (<30% headroom): " + "; ".join(near_limit) + ".")
    return parts

def _format_numerical_health(metrics: Dict[str, Any]) -> List[str]:
    parts: List[str] = []
    parts.append("**Numerical Health**:")
    issues: List[str] = []
    for label, key in (
        ("structure mass", "structure_mass"),
        ("peak joint force", "max_joint_force"),
        ("peak joint torque", "max_joint_torque"),
        ("max joint damage", "max_joint_damage"),
        ("tip y", "tip_y_last"),
        ("peak angular velocity", "peak_body_angvel"),
        ("worst-spin body peak", "worst_spin_body_peak"),
        ("tip stability ratio", "tip_stability_ratio"),
    ):
        v = metrics.get(key)
        if v is not None and not _is_finite_number(v):
            issues.append(f"Non-finite value: '{label}' ({key}) = {v}")
    pav = metrics.get("peak_body_angvel")
    if pav is not None and _is_finite_number(pav) and float(pav) > 50.0:
        issues.append(
            f"Extreme peak |ω| = {_fmt_float(pav, 1)} rad/s — solver may be unreliable above ~50 rad/s."
        )
    elif pav is not None and _is_finite_number(pav) and float(pav) > 10.0:
        issues.append(
            f"Elevated peak |ω| = {_fmt_float(pav, 1)} rad/s — solver near stability limits."
        )
    tip_y = metrics.get("tip_y_last")
    if tip_y is not None and _is_finite_number(tip_y):
        if float(tip_y) > 20.0:
            issues.append(f"Extreme tip y = {_fmt_float(tip_y, 2)} m — runaway rotational instability likely.")
        elif float(tip_y) < 0.0:
            issues.append(f"Tip y = {_fmt_float(tip_y, 2)} m below ground — structure collapsed through terrain.")
    per_body = metrics.get("per_body_angvel_data")
    if not _is_missing_or_empty(per_body):
        n_extreme = sum(
            1 for b in per_body
            if _is_finite_number(b.get("peak_angvel")) and float(b.get("peak_angvel", 0.0)) > 50.0
        )
        if n_extreme > 0:
            issues.append(f"{n_extreme} beam(s) with peak |ω| > 50 rad/s — possible numerical instability.")
    jc = metrics.get("joint_count")
    if jc is not None and jc == 0:
        issues.append("Zero joints remaining — total structural collapse.")
    elif jc is not None:
        ij = metrics.get("initial_joint_count")
        if ij is not None and ij > 0 and jc < ij * 0.3:
            issues.append(f">70% of joints lost ({jc}/{ij} remain) — structure near total disintegration.")
    bc = metrics.get("body_count")
    sm = metrics.get("structure_mass")
    if (bc is not None and bc > 0 and sm is not None
            and _is_finite_number(sm) and float(sm) < 0.01):
        issues.append(f"Structure mass {_fmt_float(sm)} kg with {bc} bodies — possible zero-density anomaly.")
    if issues:
        for issue in issues:
            parts.append(f"⚠ {issue}")
    else:
        parts.append("✅ No anomalies detected.")
    return parts

def format_task_metrics(metrics: Dict[str, Any]) -> List[str]:
    parts: List[str] = []
    if not metrics:
        return parts
    if metrics.get("error"):
        parts.append(f"**Evaluator status**: {metrics['error']}")
        return parts
    success = metrics.get("success")
    failed = metrics.get("failed")
    if success:
        parts.append("✅ Outcome: **PASS** — structure survived all constraints.")
    elif failed:
        parts.append("❌ Outcome: **FAIL** — structure disintegrated or violated constraints.")
        fr = metrics.get("failure_reason")
        if fr and str(fr).strip():
            parts.append(f"Failure: {fr}")
    else:
        parts.append("⚠ Outcome: **INCOMPLETE** — simulation stopped before max steps.")
    sc = metrics.get("step_count")
    phase = metrics.get("current_phase", "UNKNOWN")
    parts.append(f"Step: {sc}. Phase: **{phase}**.")
    topo = _format_topo_line(metrics)
    if topo:
        parts.append(topo)
    mass = _format_mass_line(metrics)
    if mass:
        parts.append(mass)
    env = _format_env_line(metrics)
    if env:
        parts.append(env)
    parts.append("")
    sections = [
        ("", _format_failure_timeline(metrics)),
        ("", _format_spatial_diagnostics(metrics)),
        ("", _format_load_stress(metrics)),
        ("", _format_energy(metrics)),
        ("", _format_constraint_profile(metrics)),
        ("", _format_numerical_health(metrics)),
    ]
    for _label, content in sections:
        if content:
            parts.append("---")
            parts.extend(content)
            parts.append("")
    return parts

def get_improvement_suggestions(
    metrics: Dict[str, Any],
    score: float,
    success: bool,
    failed: bool,
    failure_reason: Optional[str],
    error: Optional[str],

) -> List[str]:
    suggestions: List[str] = []
    if error:
        suggestions.append("- Fix the execution error before iterating on design.")
        return suggestions
    if success:
        return suggestions
    peak_av = metrics.get("peak_body_angvel")
    av_thresh = metrics.get("beam_angvel_thresh")
    if peak_av is not None and av_thresh is not None and _is_finite_number(peak_av) and _is_finite_number(av_thresh):
        if float(peak_av) > float(av_thresh):
            suggestions.append("- Angular speed exceeded the spin-destruction limit; note the spatial distribution of spin failures.")
    jbf = metrics.get("joint_break_force")
    mjf = metrics.get("max_joint_force")
    if (jbf is not None and mjf is not None
            and _is_finite_number(jbf) and _is_finite_number(mjf)
            and float(mjf) > float(jbf) * 0.9):
        suggestions.append("- Joint reaction force near or above the structural limit; identify overloaded joints from stress data.")
    jbt = metrics.get("joint_break_torque")
    mjt = metrics.get("max_joint_torque")
    if (jbt is not None and mjt is not None
            and _is_finite_number(jbt) and _is_finite_number(mjt)
            and float(mjt) > float(jbt) * 0.9):
        suggestions.append("- Joint reaction torque near or above the structural limit; identify overloaded joints from stress data.")
    dmg = metrics.get("max_joint_damage")
    dlim = metrics.get("damage_limit")
    if (dmg is not None and dlim is not None
            and _is_finite_number(dmg) and _is_finite_number(dlim)
            and float(dmg) >= float(dlim) * 0.9):
        suggestions.append("- Cumulative damage near or at failure limit; check damage hotspot regions.")
    sm = metrics.get("structure_mass")
    mm = metrics.get("max_structure_mass")
    if sm is not None and mm is not None and _is_finite_number(sm) and _is_finite_number(mm):
        if float(sm) > float(mm):
            suggestions.append("- Structure mass exceeds the budget limit.")
        elif float(sm) < float(mm) * 0.3:
            suggestions.append(f"- Mass headroom is {float(mm) - float(sm):.1f} kg ({_margin_str(float(sm), float(mm))}); the mass budget is largely unused.")
    if metrics.get("span_check_passed") is False:
        suggestions.append("- Span or height requirement not met; verify beam positions cover the required build zone.")
    return suggestions
