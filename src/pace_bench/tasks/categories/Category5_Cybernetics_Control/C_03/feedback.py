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

def format_task_metrics(metrics: Dict[str, Any]) -> List[str]:
    parts: List[str] = []
    for key in ("seeker_x", "seeker_y", "seeker_vx", "seeker_vy",
                "target_x", "target_y", "distance_to_target"):
        val = metrics.get(key)
        if val is not None and not _is_finite(val):
            parts.append(
                f"**NUMERICAL FAULT**: {key} is non-finite ({val}) — "
                f"solver divergence suspected."
            )
            return parts
    sx = _fval(metrics, "seeker_x")
    sy = _fval(metrics, "seeker_y")
    tx = _fval(metrics, "target_x")
    ty = _fval(metrics, "target_y")
    svx = _fval(metrics, "seeker_vx")
    svy = _fval(metrics, "seeker_vy")
    seeker_speed = _fval(metrics, "seeker_speed_current")
    distance = _fval(metrics, "distance_to_target")
    rel_speed = _fval(metrics, "relative_speed")
    step_count = int(metrics.get("step_count", 0))
    max_steps_raw = int(metrics.get("max_steps", 0))
    max_steps = max_steps_raw if max_steps_raw > 0 else step_count
    elapsed_pct = (float(step_count) / float(max_steps) * 100.0) if max_steps > 0 else 0.0
    rdz_dist = _fval(metrics, "rendezvous_distance", 6.0)
    rdz_rel = _fval(metrics, "rendezvous_rel_speed", 1.8)
    heading_error_deg = _fval(metrics, "heading_error_deg")
    heading_tol = _fval(metrics, "heading_tolerance_deg", 55.0)
    heading_margin = _fval(metrics, "heading_margin_deg")
    aligned = metrics.get("heading_aligned", False)
    activation_achieved = metrics.get("activation_achieved", False)
    az_min = _fval(metrics, "activation_zone_x_min", 13.0)
    az_max = _fval(metrics, "activation_zone_x_max", 17.0)
    rz_min = _fval(metrics, "rendezvous_zone_x_min", 10.0)
    rz_max = _fval(metrics, "rendezvous_zone_x_max", 20.0)
    c_lo = metrics.get("corridor_x_lo")
    c_hi = metrics.get("corridor_x_hi")
    corridor_violation = metrics.get("corridor_violation", False)
    obstacle_collision = metrics.get("obstacle_collision", False)
    out_of_fuel = metrics.get("out_of_fuel", False)
    parts.append("═══ STATE ═══")
    nonfinite = metrics.get("numerical_nonfinite_detected", False)
    vel_warn = metrics.get("numerical_velocity_warning", False)
    peak_speed = _fval(metrics, "peak_seeker_speed")
    if nonfinite:
        parts.append("NUMERICAL FAULT: Non-finite state values — solver instability.")
    elif vel_warn:
        parts.append(
            f"NUMERICAL WARNING: |v| > 5 m/s bound "
            f"(vx={svx:.2f}, vy={svy:.2f}, peak={peak_speed:.2f} m/s)"
        )
    else:
        parts.append(
            f"Numerical: OK  |  peak speed={peak_speed:.2f} m/s  |  "
            f"mass={_fval(metrics, 'mass', 20.0):.1f} kg"
        )
    parts.append(
        f"Seeker: ({sx:.3f}, {sy:.3f})  vel=({svx:+.3f}, {svy:+.3f})  |v|={seeker_speed:.3f} m/s"
    )
    parts.append(f"Target: ({tx:.3f}, {ty:.3f})")
    dist_margin = rdz_dist - distance
    rel_margin = rdz_rel - rel_speed
    parts.append(
        f"Distance: {distance:.3f} m  (limit {rdz_dist:.1f}, margin {dist_margin:+.3f})  |  "
        f"Rel speed: {rel_speed:.3f} m/s  (limit {rdz_rel:.2f}, margin {rel_margin:+.3f})"
    )
    if c_lo is not None and c_hi is not None and _is_finite(c_lo) and _is_finite(c_hi):
        c_lo_f, c_hi_f = float(c_lo), float(c_hi)
        margin_lo = sx - c_lo_f
        margin_hi = c_hi_f - sx
        cm_min = min(margin_lo, margin_hi)
        if corridor_violation:
            status = "VIOLATED"
        elif cm_min < 1.0:
            status = "TIGHT"
        else:
            status = "OK"
        parts.append(
            f"Corridor: [{c_lo_f:.2f}, {c_hi_f:.2f}]  "
            f"margin min={cm_min:+.3f} m  ({status})"
        )
    if corridor_violation:
        v_sx = metrics.get("violation_seeker_x", sx)
        v_lo = metrics.get("violation_bound_lo", 0)
        v_hi = metrics.get("violation_bound_hi", 0)
        v_bnd = metrics.get("violation_boundary", "unknown")
        v_of = metrics.get("violation_overflow", 0)
        parts.append(
            f"  VIOLATION: x={float(v_sx):.3f}, bounds=[{float(v_lo):.3f},{float(v_hi):.3f}], "
            f"{v_bnd} by {float(v_of):.3f} m"
        )
    act_status = "ACHIEVED" if activation_achieved else (
        "in zone" if az_min <= sx <= az_max else "outside"
    )
    rz_status = "in" if rz_min <= sx <= rz_max else "outside"
    parts.append(
        f"Zones: activation [{az_min:.1f},{az_max:.1f}] → {act_status}  |  "
        f"rendezvous [{rz_min:.1f},{rz_max:.1f}] → {rz_status}"
    )
    parts.append("")
    parts.append("═══ HEADING ═══")
    target_speed = _fval(metrics, "target_speed_mps")
    href_min = _fval(metrics, "heading_reference_min_target_speed", 0.15)
    ref_source = "target velocity" if target_speed >= href_min else "seeker→target"
    parts.append(
        f"Error: {heading_error_deg:.1f}° / tol: {heading_tol:.1f}°  "
        f"margin: {heading_margin:+.1f}°  aligned: {'YES' if aligned else 'NO'}"
    )
    parts.append(
        f"Reference: {ref_source}  "
        f"(target speed={target_speed:.2f} m/s, threshold={href_min:.2f})"
    )
    parts.append("")
    parts.append("═══ EVENTS ═══")
    parts.append(f"Step: {step_count}/{max_steps} ({elapsed_pct:.1f}%)")
    failure_events = metrics.get("failure_events") or []
    if failure_events:
        parts.append(f"Events ({len(failure_events)}):")
        for ev in reversed(failure_events[-20:]):
            ev_step = ev.get("step", "?")
            ev_type = ev.get("type", "?")
            ev_detail = ev.get("detail", "")
            prefix = "→" if ev == failure_events[-1] else " "
            parts.append(f"  {prefix} Step {ev_step}: [{ev_type}] {ev_detail}")
    else:
        parts.append("No events recorded.")
    if metrics.get("failed") and metrics.get("failure_reason"):
        parts.append(f"Terminal failure: {metrics['failure_reason']}")
    parts.append("")
    parts.append("═══ CONSTRAINTS ═══")
    rdz_count = int(metrics.get("rendezvous_count", 0))
    imp_budget = _fval(metrics, "impulse_budget", 18500.0)
    imp_used_pct = _fval(metrics, "impulse_used_pct")
    constraints: List[tuple] = []
    if c_lo is not None and c_hi is not None:
        cmin = float(metrics.get("corridor_min_margin", 0))
        if corridor_violation:
            cu_pct = 100.0
        elif cmin <= 0.02:
            cu_pct = 100.0
        else:
            cu_pct = max(0.0, min(100.0, 100.0 * (1.0 - cmin / 1.0)))
        constraints.append(
            ("corridor", not corridor_violation, cu_pct,
             f"x={sx:.3f}, bounds=[{float(c_lo):.3f},{float(c_hi):.3f}], margin={cmin:+.3f} m")
        )
    constraints.append(
        ("activation", activation_achieved,
         0.0 if activation_achieved else 100.0,
         f"{'achieved' if activation_achieved else 'not achieved'} "
         f"(need {int(metrics.get('activation_required_steps', 80))} consecutive steps in [{az_min:.1f},{az_max:.1f}])")
    )
    constraints.append(
        ("obstacle", not obstacle_collision,
         100.0 if obstacle_collision else 0.0,
         "collision" if obstacle_collision else "clear")
    )
    constraints.append(
        ("fuel", not out_of_fuel,
         imp_used_pct,
         f"used {imp_used_pct:.0f}% of {imp_budget:.0f} N·s")
    )
    constraints.append(
        ("rdz-1", rdz_count >= 1,
         100.0 if rdz_count < 1 else 0.0,
         f"count={rdz_count} (need ≥1)")
    )
    constraints.append(
        ("rdz-2", rdz_count >= 2,
         100.0 if rdz_count < 2 else 0.0,
         f"count={rdz_count} (need ≥2)")
    )
    failed = [(n, d) for n, ok, p, d in constraints if not ok]
    at_risk = [(n, p, d) for n, ok, p, d in constraints if ok and p >= 50.0]
    if failed:
        for name, detail in failed:
            parts.append(f"  FAIL ✗  {name}: {detail}")
    if at_risk:
        for name, pct, detail in at_risk:
            parts.append(f"  RISK ⚠  {name} ({pct:.0f}%): {detail}")
    if not failed and not at_risk:
        parts.append("All constraints nominal.")
    parts.append("")
    parts.append("═══ RENDEZVOUS & SLOTS ═══")
    rdz_conds = metrics.get("rendezvous_conditions_met") or {}
    parts.append(f"Rendezvous achieved: {rdz_count}/2")
    cond_keys = [
        ("activation", "Activation achieved"),
        ("distance_ok", f"Distance ≤ {rdz_dist:.1f} m"),
        ("rel_speed_ok", f"Relative speed < {rdz_rel:.2f} m/s"),
        ("in_zone", f"Seeker x in [{rz_min:.1f}, {rz_max:.1f}]"),
        ("heading_aligned", f"Heading within {heading_tol:.1f}°"),
        ("in_slot", "Inside a slot window"),
    ]
    missing = [label for key, label in cond_keys if not rdz_conds.get(key, False)]
    if missing:
        parts.append("Not met: " + "  |  ".join(missing))
    else:
        parts.append("All rendezvous conditions met.")
    slots_p1 = metrics.get("slots_phase1", [])
    slots_p2 = metrics.get("slots_phase2", [])
    in_slot = metrics.get("in_active_slot", False)
    steps_to_p1 = metrics.get("steps_until_next_p1_slot", -1)
    steps_to_p2 = metrics.get("steps_until_next_p2_slot", -1)
    parts.append(f"In slot: {'YES' if in_slot else 'NO'}")
    if steps_to_p1 >= 0:
        parts.append(f"Next phase-1 slot: {steps_to_p1} steps")
    if steps_to_p2 >= 0:
        parts.append(f"Next phase-2 slot: {steps_to_p2} steps")
    parts.append("")
    parts.append("═══ CONTROL ═══")
    mtm = _fval(metrics, "max_thrust_magnitude", 200.0)
    imp_used = _fval(metrics, "impulse_used")
    fuel_remaining = _fval(metrics, "remaining_impulse_budget")
    parts.append(
        f"Impulse: {imp_used:.0f}/{imp_budget:.0f} N·s used ({imp_used_pct:.0f}%)  "
        f"remaining={fuel_remaining:.0f} N·s"
    )
    cth = _fval(metrics, "cooldown_threshold", 120.0)
    cmt = _fval(metrics, "cooldown_max_thrust", 40.0)
    csteps = int(metrics.get("cooldown_steps", 80))
    bz_min = _fval(metrics, "blind_zone_x_min", 12.0)
    bz_max = _fval(metrics, "blind_zone_x_max", 15.0)
    sb_thresh = _fval(metrics, "speed_blind_threshold_mps", 2.0)
    seeker_in_blind = bz_min <= sx <= bz_max
    speed_blind = seeker_speed > sb_thresh
    parts.append(
        f"Thrust: max={mtm:.0f} N  cooldown: >{cth:.0f} N → {cmt:.0f} N for {csteps} steps"
    )
    blind_parts = []
    if seeker_in_blind:
        blind_parts.append("in blind zone")
    if speed_blind:
        blind_parts.append("speed-blind")
    if blind_parts:
        parts.append(f"Sensors: {' + '.join(blind_parts)} (zone=[{bz_min:.1f},{bz_max:.1f}], threshold={sb_thresh:.1f} m/s)")
    else:
        parts.append(f"Sensors: clear (blind zone=[{bz_min:.1f},{bz_max:.1f}])")
    return parts

def get_improvement_suggestions(
    metrics: Dict[str, Any],
    score: float,
    success: bool,
    failed: bool,
    failure_reason: Optional[str],
    error: Optional[str],

) -> List[str]:
    suggestions = []
    if error:
        suggestions.append(
        )
        return suggestions
    if success:
        suggestions.append("- All objectives met. Analyze the constraint profile "
                          "for robustness margins.")
        return suggestions
    if not failed:
        suggestions.append("- Task is in progress; review the constraint checklist "
                          "to verify all rendezvous conditions can be met.")
        return suggestions
    rdz_count_val = metrics.get("rendezvous_count", 0)
    corridor_vio = metrics.get("corridor_violation", False)
    obs_coll = metrics.get("obstacle_collision", False)
    out_fuel = metrics.get("out_of_fuel", False)
    activation = metrics.get("activation_achieved", False)
    heading_err = _fval(metrics, "heading_error_deg", 0)
    heading_tol = _fval(metrics, "heading_tolerance_deg", 55)
    rel_speed_val = _fval(metrics, "relative_speed")
    rel_limit = _fval(metrics, "rendezvous_rel_speed", 1.8)
    dist_val = _fval(metrics, "distance_to_target")
    dist_limit = _fval(metrics, "rendezvous_distance", 6.0)
    if corridor_vio:
        suggestions.append(
            f"- Corridor violation occurred. The seeker left the allowed "
            f"moving corridor that varies with sin(ωt) and pinch dynamics."
        )
    if obs_coll:
        suggestions.append(
            f"- Obstacle collision occurred. Review obstacle positions "
            f"and the seeker's trajectory near contact bodies."
        )
    if out_fuel:
        suggestions.append(
            f"- Impulse budget exhausted. Total thrust impulse exceeded "
            f"the allocation before mission completion."
        )
    if not activation:
        suggestions.append(
            f"- Activation not achieved. The seeker must remain in "
            f"the activation zone for the required consecutive steps."
        )
    if heading_err > heading_tol:
        suggestions.append(
            f"- Heading misaligned (error={heading_err:.1f}°, "
            f"tolerance={heading_tol:.1f}°). The seeker heading does not "
            f"match the reference direction during rendezvous attempts."
        )
    if rel_speed_val >= rel_limit:
        suggestions.append(
            f"- Relative speed exceeds limit ({rel_speed_val:.2f} vs "
            f"{rel_limit:.2f} m/s). The speed difference between seeker "
            f"and target is too high for rendezvous."
        )
    if dist_val > dist_limit and activation:
        suggestions.append(
            f"- Distance to target exceeds rendezvous limit "
            f"({dist_val:.2f} vs {dist_limit:.1f} m)."
        )
    if rdz_count_val >= 1 and rdz_count_val < 2:
        suggestions.append(
            f"- Only {int(rdz_count_val)}/2 rendezvous achieved. "
            f"A second rendezvous is required during phase-2 slot windows."
        )
    if not suggestions:
        suggestions.append(
        )
    return suggestions
