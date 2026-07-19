from typing import Any, Dict, List

import math

def _is_finite(x: Any) -> bool:
    if x is None:
        return False
    try:
        f = float(x)
        return math.isfinite(f)
    except (TypeError, ValueError):
        return False

def _pct_str(numerator: Any, denominator: Any) -> str:
    if not _is_finite(numerator) or not _is_finite(denominator):
        return "N/A"
    d = float(denominator)
    if abs(d) < 1e-12:
        return "N/A"
    return f"{100.0 * float(numerator) / d:.1f}%"

def format_task_metrics(metrics: Dict[str, Any]) -> List[str]:
    parts: List[str] = []
    success = bool(metrics.get("success", False))
    failed = bool(metrics.get("failed", False))
    parts.append("## D-04 Swing — Diagnostic Report\n")
    if success:
        parts.append("**Outcome**: PASS — Target zone reached.\n")
    elif failed:
        parts.append("**Outcome**: FAIL — Did not reach target zone within step limit.\n")
    else:
        parts.append("**Outcome**: INCOMPLETE — Simulation ended without definitive pass/fail.\n")
    step_count = metrics.get("step_count")
    if _is_finite(step_count):
        parts.append(f"**Steps**: {int(float(step_count))}\n")
    parts.append("### 1. Temporal Event Chronology\n")
    apex_events = metrics.get("apex_events", [])
    target_y = metrics.get("target_y_min")
    tx_min = metrics.get("target_x_min")
    tx_max = metrics.get("target_x_max")
    apex_thresh = metrics.get("apex_speed_threshold", 1.0)
    if isinstance(apex_events, list) and apex_events:
        best = max(apex_events, key=lambda e: float(e[2]) if len(e) >= 3 else 0.0)
        ba_step, ba_x, ba_y, ba_spd = best[0], best[1], best[2], best[3]
        parts.append(
            f"**Best apex** (of {len(apex_events)}): step {int(ba_step)}, "
            f"x={float(ba_x):.3f} m, y={float(ba_y):.3f} m, speed={float(ba_spd):.4f} m/s\n"
        )
        if _is_finite(target_y):
            gap = max(0.0, float(target_y) - float(ba_y))
            if gap > 0:
                parts.append(f"  Gap to target y: {gap:.3f} m (needed y≥{float(target_y):.2f} m)\n")
            else:
                parts.append(f"  Altitude met target (y≥{float(target_y):.2f} m)\n")
        if _is_finite(tx_min) and _is_finite(tx_max):
            if float(ba_x) < float(tx_min):
                parts.append(f"  x outside zone: {float(tx_min) - float(ba_x):.3f} m left\n")
            elif float(ba_x) > float(tx_max):
                parts.append(f"  x outside zone: {float(ba_x) - float(tx_max):.3f} m right\n")
            else:
                parts.append(f"  x inside zone [{float(tx_min):.2f}, {float(tx_max):.2f}]\n")
    else:
        parts.append(f"No apex events. Speed never dropped below {apex_thresh:.2f} m/s.\n")
    parts.append("### 2. Spatial Diagnostics with Margins\n")
    sx = metrics.get("seat_x")
    sy = metrics.get("seat_y")
    if _is_finite(sx) and _is_finite(sy):
        parts.append(f"**Final position**: ({float(sx):.3f}, {float(sy):.3f}) m\n")
        if _is_finite(target_y):
            vm = float(sy) - float(target_y)
            parts.append(f"  Vertical margin to target: {'+' if vm >= 0 else ''}{vm:.3f} m\n")
        if _is_finite(tx_min) and _is_finite(tx_max):
            sx_f = float(sx)
            if sx_f < float(tx_min):
                parts.append(f"  Lateral offset: {float(tx_min) - sx_f:.3f} m left of zone "
                             f"[{float(tx_min):.2f}, {float(tx_max):.2f}]\n")
            elif sx_f > float(tx_max):
                parts.append(f"  Lateral offset: {sx_f - float(tx_max):.3f} m right of zone\n")
            else:
                parts.append(f"  Lateral: inside zone\n")
    if not _is_finite(sx) and not _is_finite(metrics.get("max_seat_y_reached")) and not _is_finite(metrics.get("seat_speed")):
        parts.append("No spatial data available.\n")
    max_y = metrics.get("max_seat_y_reached")
    if _is_finite(max_y):
        my = float(max_y)
        if _is_finite(target_y):
            gap = float(target_y) - my
            parts.append(f"**Peak altitude**: {my:.3f} m "
                         f"({'shortfall ' + f'{gap:.3f}' if gap > 0 else 'exceeded by ' + f'{abs(gap):.3f}'} m)\n")
        else:
            parts.append(f"**Peak altitude**: {my:.3f} m\n")
    sspeed = metrics.get("seat_speed")
    if _is_finite(sspeed):
        parts.append(f"**Final speed**: {float(sspeed):.3f} m/s\n")
    progress = metrics.get("progress_pct")
    if _is_finite(progress):
        parts.append(f"**Height progress**: {float(progress):.1f}%\n")
    parts.append("### 3. Force Delivery Audit\n")
    force_calls = metrics.get("force_calls", 0)
    if _is_finite(force_calls) and float(force_calls) > 0:
        fc = int(float(force_calls))
        applied = metrics.get("force_applied_count", 0)
        suppressed = metrics.get("force_suppressed_count", 0)
        delivery_pct = metrics.get("force_delivery_pct", 100.0)
        line = f"**{fc} force calls**: " \
               f"{int(float(applied)) if _is_finite(applied) else 0} delivered"
        if _is_finite(suppressed) and int(float(suppressed)) > 0:
            supp_dz = metrics.get("force_suppressed_deadzone", 0)
            supp_fault = metrics.get("force_suppressed_fault", 0)
            line += f", {int(float(suppressed))} suppressed" \
                    f" (deadzone={int(float(supp_dz)) if _is_finite(supp_dz) else 0}" \
                    f", fault={int(float(supp_fault)) if _is_finite(supp_fault) else 0})"
        if _is_finite(delivery_pct):
            line += f" — delivery efficiency {float(delivery_pct):.1f}%"
        parts.append(line + "\n")
    else:
        parts.append("No force/impulse calls were made to the seat.\n")
    parts.append("### 4. Energy & Power Flow\n")
    ke_final = metrics.get("kinetic_energy_final")
    pe_final = metrics.get("potential_energy_final")
    te_final = metrics.get("total_mechanical_energy_final")
    peak_ke = metrics.get("peak_kinetic_energy")
    peak_ke_step = metrics.get("peak_kinetic_energy_step")
    peak_pe = metrics.get("peak_potential_energy")
    has_energy = any(_is_finite(v) for v in [ke_final, pe_final, te_final, peak_ke, peak_pe])
    if has_energy:
        parts.append("| Energy Component | Value (J) |\n")
        parts.append("|------------------|-----------|\n")
        if _is_finite(ke_final):
            parts.append(f"| Kinetic (final) | {float(ke_final):.3f} |\n")
        if _is_finite(pe_final):
            parts.append(f"| Potential (final) | {float(pe_final):.3f} |\n")
        if _is_finite(te_final):
            parts.append(f"| Total mechanical | {float(te_final):.3f} |\n")
        if _is_finite(peak_ke):
            pk_str = f"| Peak kinetic | {float(peak_ke):.3f}"
            if _is_finite(peak_ke_step):
                pk_str += f" (step {int(float(peak_ke_step))})"
            pk_str += " |\n"
            parts.append(pk_str)
        if _is_finite(peak_pe):
            parts.append(f"| Peak potential | {float(peak_pe):.3f} |\n")
    else:
        parts.append("No energy data available.\n")
    wind_enabled = metrics.get("wind_enabled")
    if wind_enabled:
        w_str = metrics.get("wind_strength")
        w_mean = metrics.get("wind_mean_observed")
        w_period = metrics.get("wind_period")
        w_gusts = metrics.get("wind_gust_count_observed")
        wind_line = "\n**Wind**: enabled"
        if _is_finite(w_str):
            wind_line += f", strength={float(w_str):.3f} N"
        if _is_finite(w_period):
            wind_line += f", period={float(w_period):.2f} s"
        if _is_finite(w_mean):
            wind_line += f", mean={float(w_mean):.3f} N"
        if _is_finite(w_gusts) and int(float(w_gusts)) > 0:
            wind_line += f", gusts={int(float(w_gusts))}"
        parts.append(wind_line + "\n")
    parts.append("### 5. Constraint Satisfaction Profile\n")
    constraints = []
    for key in ["constraint_force_limit", "constraint_impulse_limit",
                "constraint_structure_mass", "constraint_build_zone",
                "constraint_apex_in_zone", "constraint_vertical_fall"]:
        c = metrics.get(key)
        if isinstance(c, dict) and c:
            constraints.append((key, c))
    if constraints:
        pass_count = sum(1 for _, c in constraints if c.get("pass") is True)
        fail_count = sum(1 for _, c in constraints if c.get("pass") is False)
        unknown_count = len(constraints) - pass_count - fail_count
        parts.append(f"**Summary**: {pass_count} passed, {fail_count} failed"
                     + (f", {unknown_count} unknown" if unknown_count else "")
                     + f" / {len(constraints)} checked.\n")
        for ckey, c in constraints:
            if c.get("pass") is not False:
                continue
            label = c.get("label", ckey)
            detail = c.get("detail", "")
            parts.append(f"  **FAIL** {label} — {detail}\n")
    else:
        parts.append("No constraint profile data available.\n")
    touched = metrics.get("touched_target", False)
    in_zone = metrics.get("in_zone_at_final", False)
    parts.append(f"**Touched target**: {'Yes' if touched else 'No'}"
                 f"  |  **In zone at final**: {'Yes' if in_zone else 'No'}\n")
    parts.append("### 6. Numerical Health\n")
    health_keys = [
        "seat_x", "seat_y", "seat_speed",
        "kinetic_energy_final", "potential_energy_final",
        "force_total_requested", "force_total_delivered",
    ]
    issues = []
    for k in health_keys:
        v = metrics.get(k)
        if v is not None and not _is_finite(v):
            issues.append(f"{k}={v}")
    if issues:
        parts.append(f"**Non-finite values**: {', '.join(issues)}\n")
    else:
        parts.append("All sampled metrics are finite (no NaN, Inf).\n")
    extreme = metrics.get("extreme_velocity_detected", False)
    if extreme:
        parts.append("⚠ **Extreme velocity detected** (>100 m/s). Solver may be diverging.\n")
    struct_mass = metrics.get("structure_mass")
    if _is_finite(struct_mass) and float(struct_mass) > 1e-9:
        parts.append(f"**Structure mass**: {float(struct_mass):.3f} kg (agent-built bodies present)\n")
    parts.append("### 7. Environment Configuration Reference\n")
    parts.append("| Parameter | Value |\n")
    parts.append("|-----------|-------|\n")
    for key, label in [
        ("pivot_x", "Pivot x (m)"),
        ("pivot_y", "Pivot y (m)"),
        ("rope_length", "Rope length (m)"),
        ("target_y_min", "Target y min (m)"),
        ("target_x_min", "Target x min (m)"),
        ("target_x_max", "Target x max (m)"),
        ("max_pump_force", "Max pump force (N)"),
        ("max_impulse", "Max impulse (N·s)"),
        ("max_structure_mass", "Max structure mass (kg)"),
        ("actuator_fault", "Actuator fault"),
        ("dead_zone", "Dead zone"),
        ("wind_enabled", "Wind enabled"),
        ("wind_strength", "Wind strength (N)"),
    ]:
        v = metrics.get(key)
        if v is not None:
            if isinstance(v, float):
                parts.append(f"| {label} | {v:.3f} |\n")
            elif isinstance(v, list):
                parts.append(f"| {label} | [{', '.join(f'{x:.2f}' if isinstance(x, float) else str(x) for x in v)}] |\n")
            else:
                parts.append(f"| {label} | {v} |\n")
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
        suggestions.append("- Code execution error — check syntax, undefined variables, and imports.")
        return suggestions
    if success:
        return suggestions
    force_pct = metrics.get("force_delivery_pct", 100.0)
    if _is_finite(force_pct) and float(force_pct) < 50.0:
        supp_dz = metrics.get("force_suppressed_deadzone", 0)
        supp_fault = metrics.get("force_suppressed_fault", 0)
        if _is_finite(supp_dz) and int(float(supp_dz)) > 0:
            suggestions.append(f"- Force suppressed by dead zone in {int(float(supp_dz))} calls. "
                               "Check whether the swing is spending time in spatial regions where thrust is unavailable.")
        if _is_finite(supp_fault) and int(float(supp_fault)) > 0:
            fault = metrics.get("actuator_fault", "unknown")
            suggestions.append(f"- Force suppressed by actuator fault ({fault}) in {int(float(supp_fault))} calls. "
                               "Check which force directions are being blocked.")
    max_y = metrics.get("max_seat_y_reached")
    target_y = metrics.get("target_y_min")
    if _is_finite(max_y) and _is_finite(target_y):
        if float(max_y) < float(target_y):
            gap = float(target_y) - float(max_y)
            suggestions.append(f"- Peak altitude {float(max_y):.2f} m is {gap:.2f} m below target {float(target_y):.2f} m.")
        else:
            suggestions.append(f"- Peak altitude {float(max_y):.2f} m exceeds target {float(target_y):.2f} m, "
                               "but may be outside x-zone at apex.")
    phase = metrics.get("phase_alignment_pct", 0.0)
    if _is_finite(phase) and float(phase) < 40.0:
        anti = metrics.get("phase_antialigned_pct", 0.0)
        suggestions.append(f"- Force aligned with velocity in only {float(phase):.1f}% of thrust actions "
                           f"({float(anti):.1f}% anti-aligned). Pumping may be fighting the natural swing.")
    peak_pe = metrics.get("peak_potential_energy")
    seat_mass = metrics.get("seat_mass")
    swing_bottom = metrics.get("swing_bottom_y")
    if _is_finite(peak_pe) and _is_finite(seat_mass) and _is_finite(target_y) and _is_finite(swing_bottom):
        g = 10.0
        needed = float(seat_mass) * g * (float(target_y) - float(swing_bottom))
        if float(peak_pe) < needed:
            deficit = needed - float(peak_pe)
            suggestions.append(f"- Energy deficit to target: {deficit:.1f} J (achieved {float(peak_pe):.1f} J "
                               f"of {needed:.1f} J required).")
    wind_mean = metrics.get("wind_mean_observed", 0.0)
    if _is_finite(wind_mean) and abs(float(wind_mean)) > 5.0:
        suggestions.append(f"- Observed mean wind: {float(wind_mean):.1f} N "
                           f"({'rightward' if float(wind_mean) > 0 else 'leftward'}).")
    if not suggestions:
        suggestions.append("- No specific diagnostic flags triggered. Check temporal chronology and spatial margins above.")
    return suggestions
