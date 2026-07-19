from typing import Any, Dict, List

import math

def _f(v: Any, dec: int = 2) -> str:
    if v is None:
        return "N/A"
    try:
        fv = float(v)
        if not math.isfinite(fv):
            return str(v)
        return f"{fv:.{dec}f}"
    except (TypeError, ValueError):
        return str(v)

def _has(v: Any) -> bool:
    if v is None:
        return False
    try:
        fv = float(v)
        return math.isfinite(fv)
    except (TypeError, ValueError):
        return False

def _section_numerical_health(metrics: Dict[str, Any]) -> List[str]:
    lines: List[str] = []
    numeric_keys = [
        "boat_angle_rad", "boat_angle_deg", "boat_x", "boat_y",
        "structure_mass", "cargo_lowest_y", "cargo_loss_margin",
        "joint_peak_force_N", "joint_peak_torque_Nm",
        "peak_angular_velocity_rad_s", "restoring_coeff",
    ]
    non_finite = []
    for k in numeric_keys:
        v = metrics.get(k)
        if v is None:
            continue
        try:
            fv = float(v)
            if not math.isfinite(fv):
                non_finite.append(f"{k}={v}")
        except (TypeError, ValueError):
            pass
    ang_vel = metrics.get("peak_angular_velocity_rad_s")
    if _has(ang_vel):
        av = float(ang_vel)
        if av > 100.0:
            non_finite.append(
                f"peak_angular_velocity={av:.1f} rad/s (extreme, possible solver divergence)"
            )
    angle_deg = metrics.get("boat_angle_deg")
    if _has(angle_deg):
        ad = float(angle_deg)
        if abs(ad) > 360.0:
            non_finite.append(
                f"boat_angle={ad:.1f} deg (extreme, possible NaN/inf cascade)"
            )
    if non_finite:
        lines.append("### 0. Numerical Health — WARNINGS")
        for w in non_finite:
            lines.append(f"  - {w}")
        lines.append("")
    return lines

def _section_temporal_chronology(metrics: Dict[str, Any]) -> List[str]:
    lines = ["### 1. Temporal Event Chronology", ""]
    step_count = metrics.get("step_count")
    max_steps = metrics.get("max_steps", "?")
    if step_count is not None:
        try:
            s = int(step_count)
            ms_val = None
            if isinstance(max_steps, (int, float)):
                ms_val = int(max_steps)
            if ms_val and ms_val > 0:
                pct = s / ms_val * 100.0
                lines.append(
                    f"**Simulation terminated** at step {s}/{ms_val} ({pct:.1f}% of rollout)"
                )
            else:
                lines.append(f"**Simulation terminated** at step {s}")
        except (TypeError, ValueError):
            lines.append(f"**Simulation terminated** at step {step_count}")
    grace_steps = metrics.get("cargo_grace_steps")
    if grace_steps is not None:
        try:
            gs = int(grace_steps)
            lines.append(
                f"**Cargo loss grace period**: first {gs} steps (spawn/settling ignored)"
            )
        except (TypeError, ValueError):
            pass
    capsize_step = metrics.get("capsize_first_step")
    max_angle = metrics.get("boat_max_angle_deg")
    if capsize_step is not None:
        try:
            cs = int(capsize_step)
            ma = float(max_angle) if _has(max_angle) else 18.0
            lines.append(
                f"  **CAPSIZE** at step {cs} (limit = {ma:.0f} deg)"
            )
        except (TypeError, ValueError):
            lines.append(f"  **CAPSIZE** at step {capsize_step}")
    capsize_margin_grace = metrics.get("capsize_margin_at_grace_end_rad")
    if _has(capsize_margin_grace):
        try:
            cm = float(capsize_margin_grace)
            cm_deg = math.degrees(cm)
            if cm_deg >= 0:
                lines.append(
                    f"  At grace end: roll margin {cm_deg:.2f} deg (within limit)"
                )
            else:
                lines.append(
                    f"  At grace end: roll EXCEEDED by {-cm_deg:.2f} deg"
                )
        except (TypeError, ValueError):
            pass
    cargo_ever_below = metrics.get("cargo_ever_below_loss_plane")
    if cargo_ever_below:
        cargo_lowest_y = metrics.get("cargo_lowest_y")
        cargo_lowest_step = metrics.get("cargo_lowest_y_step")
        cwy = metrics.get("cargo_water_y")
        if _has(cargo_lowest_y) and _has(cwy):
            cl = float(cargo_lowest_y)
            clw = float(cwy)
            step_str = f" at step {int(cargo_lowest_step)}" if cargo_lowest_step is not None else ""
            below = clw - cl
            lines.append(
                f"  **Cargo breached loss plane**{step_str}: "
                f"lowest y = {cl:.2f} m ({below:.2f} m BELOW y = {clw:.2f} m)"
            )
    fr = metrics.get("failure_reason")
    if fr and str(fr).strip():
        lines.append("")
        lines.append(f"**Terminal failure**: {fr}")
    lines.append("")
    return lines

def _section_spatial_diagnostics(metrics: Dict[str, Any]) -> List[str]:
    lines = ["### 2. Spatial Diagnostics", ""]
    boat_x = metrics.get("boat_x")
    boat_y = metrics.get("boat_y")
    if _has(boat_x) and _has(boat_y):
        bx = float(boat_x)
        by = float(boat_y)
        lines.append(f"**Boat position**: ({bx:.2f}, {by:.2f}) m")
    initial_cargo = metrics.get("initial_cargo_count", 0)
    cargo_in_water = metrics.get("cargo_in_water", 0)
    cargo_retained = metrics.get("cargo_retained")
    cwy = metrics.get("cargo_water_y")
    cargo_lowest_y = metrics.get("cargo_lowest_y")
    if initial_cargo is not None:
        try:
            ic = int(initial_cargo)
            ciw = int(cargo_in_water) if cargo_in_water is not None else 0
            cr = int(cargo_retained) if cargo_retained is not None else (ic - ciw)
            parts = [f"**Cargo**: {cr}/{ic} retained"]
            if ciw > 0:
                parts.append(f"{ciw} in water (below y={_f(cwy, 2)} m)")
            if _has(cargo_lowest_y) and _has(cwy):
                cl = float(cargo_lowest_y)
                clw = float(cwy)
                margin = cl - clw
                status = "ABOVE" if margin >= 0 else "BELOW"
                parts.append(
                    f"lowest y={cl:.2f} m ({abs(margin):.2f} m {status} loss plane)"
                )
            lines.append(", ".join(parts))
        except (TypeError, ValueError):
            lines.append(f"**Cargo**: {cargo_retained}/{initial_cargo} retained")
    angle_deg = metrics.get("boat_angle_deg")
    max_angle_deg = metrics.get("boat_max_angle_deg")
    if _has(angle_deg) and _has(max_angle_deg):
        ad = float(angle_deg)
        mad = float(max_angle_deg)
        margin = mad - abs(ad)
        if margin >= 0:
            lines.append(
                f"**Roll**: |{ad:.2f}| deg / {mad:.1f} deg limit "
                f"(margin {margin:.2f} deg)"
            )
        else:
            lines.append(
                f"**Roll**: |{ad:.2f}| deg (EXCEEDS {mad:.1f} deg limit "
                f"by {-margin:.2f} deg)"
            )
    bzx_min = metrics.get("build_zone_x_min")
    bzx_max = metrics.get("build_zone_x_max")
    bzy_min = metrics.get("build_zone_y_min")
    bzy_max = metrics.get("build_zone_y_max")
    beam_floor_margin = metrics.get("lowest_beam_y_floor_margin")
    if bzx_min is not None:
        bz = (
            f"**Build zone**: x=[{_f(bzx_min, 1)}, {_f(bzx_max, 1)}], "
            f"y=[{_f(bzy_min, 1)}, {_f(bzy_max, 1)}]"
        )
        if _has(beam_floor_margin):
            bz += f"; beam-floor margin {float(beam_floor_margin):+.2f} m"
        lines.append(bz)
    lines.append("")
    return lines

def _section_load_stress(metrics: Dict[str, Any]) -> List[str]:
    lines = ["### 3. Load & Stress Distribution", ""]
    structure_broken = metrics.get("structure_broken")
    joint_count = metrics.get("joint_count")
    initial_joint_count = metrics.get("initial_joint_count")
    if structure_broken:
        broken_count = "?"
        if initial_joint_count is not None and joint_count is not None:
            try:
                broken_count = int(initial_joint_count) - int(joint_count)
            except (TypeError, ValueError):
                pass
        lines.append(
            f"**Structure**: BROKEN — {broken_count} joints lost "
            f"({joint_count}/{initial_joint_count} remaining)"
        )
    else:
        lines.append(
            f"**Structure**: INTACT — {joint_count}/{initial_joint_count} joints survive"
        )
    peak_force = metrics.get("joint_peak_force_N")
    max_force = metrics.get("joint_max_force_N")
    joint_reported = False
    if _has(peak_force):
        pf = float(peak_force)
        mf = float(max_force) if _has(max_force) else float('inf')
        peak_torque = metrics.get("joint_peak_torque_Nm")
        has_torque = _has(peak_torque) and float(peak_torque) > 0
        if mf >= float('inf'):
            if has_torque:
                lines.append(
                    f"  **Joints**: unbreakable (no force limit); "
                    f"peak torque {float(peak_torque):.1f} Nm"
                )
                joint_reported = True
        else:
            peak_force_pct = metrics.get("joint_peak_force_pct")
            pfp = None
            if _has(peak_force_pct):
                pfp = float(peak_force_pct)
            elif mf > 0:
                pfp = pf / mf * 100.0
            if pfp is not None:
                if pfp >= 80.0:
                    tier = "CRITICAL"
                elif pfp >= 50.0:
                    tier = "ELEVATED"
                else:
                    tier = None
                if tier is not None:
                    lines.append(
                        f"  **Peak joint force**: {pf:.1f}/{mf:.1f} N "
                        f"({pfp:.1f}%) — {tier}"
                    )
                    joint_reported = True
                elif has_torque:
                    lines.append(
                        f"  **Peak joint force**: {pf:.1f}/{mf:.1f} N "
                        f"({pfp:.1f}%)"
                    )
                    joint_reported = True
            else:
                lines.append(f"  **Peak joint force**: {pf:.1f}/{mf:.1f} N")
                joint_reported = True
            if has_torque:
                pt = float(peak_torque)
                torque_limit = mf * 0.4
                if torque_limit > 0:
                    t_pct = pt / torque_limit * 100.0
                    if t_pct >= 50.0:
                        lines.append(
                            f"  **Peak joint torque**: {pt:.1f}/{torque_limit:.1f} Nm "
                            f"({t_pct:.1f}%)"
                        )
                    elif not joint_reported:
                        lines.append(
                            f"  **Peak joint torque**: {pt:.1f}/{torque_limit:.1f} Nm "
                            f"({t_pct:.1f}%)"
                        )
    mass = metrics.get("structure_mass")
    max_mass = metrics.get("max_structure_mass")
    if _has(mass) and _has(max_mass):
        m = float(mass)
        mm = float(max_mass)
        if mm > 0:
            pct = m / mm * 100.0
            if pct >= 80.0:
                m_tier = " — CRITICAL"
            elif pct >= 50.0:
                m_tier = " — ELEVATED"
            else:
                m_tier = ""
            lines.append(
                f"**Mass**: {m:.2f}/{mm:.2f} kg ({pct:.1f}%){m_tier}"
            )
    lines.append("")
    return lines

def _section_forcing_environment(metrics: Dict[str, Any]) -> List[str]:
    lines = ["### 4. Forcing Environment", ""]
    restoring_coeff = metrics.get("restoring_coeff")
    if _has(restoring_coeff):
        rc = float(restoring_coeff)
        if rc < 0:
            lines.append(
                f"**Roll restoring**: {rc:.1f} Nm/rad — DESTABILIZING (amplifies roll)"
            )
        elif rc == 0:
            lines.append(
                f"**Roll restoring**: {rc:.1f} Nm/rad — NEUTRAL"
            )
        else:
            lines.append(
                f"**Roll restoring**: {rc:.1f} Nm/rad — stabilizing"
            )
    wave_amp = metrics.get("wave_amplitude_N")
    wave2_amp = metrics.get("wave2_amplitude_N")
    rogue_amp = metrics.get("rogue_amplitude_N")
    if any(_has(v) for v in [wave_amp, wave2_amp, rogue_amp]):
        parts = []
        if _has(wave_amp):
            parts.append(f"primary {float(wave_amp):.1f} N")
        if _has(wave2_amp):
            parts.append(f"secondary {float(wave2_amp):.1f} N")
        if _has(rogue_amp):
            parts.append(f"rogue {float(rogue_amp):.1f} N")
        lines.append(f"**Waves**: " + ", ".join(parts))
    lateral_amp = metrics.get("lateral_impulse_amplitude_N")
    if _has(lateral_amp):
        lines.append(f"**Lateral**: impulse {float(lateral_amp):.1f} N")
    ang_vel = metrics.get("peak_angular_velocity_rad_s")
    if _has(ang_vel):
        av = float(ang_vel)
        if av > 50.0:
            lines.append(
                f"**Peak angular velocity**: {av:.1f} rad/s — HIGH (possible solver stress)"
            )
        elif av > 1.0:
            lines.append(f"**Peak angular velocity**: {av:.1f} rad/s")
    lines.append("")
    return lines

def _section_constraint_profile(metrics: Dict[str, Any]) -> List[str]:
    lines = ["### 5. Constraint Summary", ""]
    viols = metrics.get("constraint_violations")
    if isinstance(viols, list) and viols:
        for v in viols:
            lines.append(f"- FAIL: {v}")
        lines.append("\n**Outcome**: REJECTED (build-time)")
        lines.append("")
        return lines
    fail_items = []
    near_items = []
    pass_items = []
    initial_cargo = metrics.get("initial_cargo_count", 0)
    cargo_in_water = metrics.get("cargo_in_water", 0)
    try:
        ic = int(initial_cargo)
        ciw = int(cargo_in_water)
        if ciw > 0:
            fail_items.append(f"cargo ({ciw}/{ic} in water)")
        else:
            pass_items.append("cargo")
    except (TypeError, ValueError):
        pass
    angle_deg = metrics.get("boat_angle_deg")
    max_angle_deg = metrics.get("boat_max_angle_deg")
    if _has(angle_deg) and _has(max_angle_deg):
        ad = float(angle_deg)
        mad = float(max_angle_deg)
        pct = abs(ad) / mad * 100.0 if mad > 0 else 0.0
        if abs(ad) > mad:
            margin = mad - abs(ad)
            fail_items.append(
                f"roll (|{ad:.2f}| > {mad:.1f} deg, by {-margin:.2f} deg)"
            )
        elif pct > 70.0:
            near_items.append(f"roll ({pct:.0f}% of limit)")
        else:
            pass_items.append("roll")
    structure_broken = metrics.get("structure_broken")
    jc = metrics.get("joint_count")
    ijc = metrics.get("initial_joint_count")
    if structure_broken:
        broken = "?"
        try:
            broken = int(ijc) - int(jc) if ijc is not None and jc is not None else "?"
        except (TypeError, ValueError):
            pass
        fail_items.append(f"structure ({broken} joints broken)")
    else:
        pass_items.append("structure")
    mass = metrics.get("structure_mass")
    max_mass = metrics.get("max_structure_mass")
    if _has(mass) and _has(max_mass):
        m = float(mass)
        mm = float(max_mass)
        pct = m / mm * 100.0 if mm > 0 else 0.0
        if m > mm:
            fail_items.append(f"mass ({m:.2f} > {mm:.2f} kg)")
        elif pct > 70.0:
            near_items.append(f"mass ({pct:.0f}%)")
        else:
            pass_items.append("mass")
    max_force = metrics.get("joint_max_force_N")
    peak_force = metrics.get("joint_peak_force_N")
    peak_pct = metrics.get("joint_peak_force_pct")
    if _has(max_force) and float(max_force) < float('inf'):
        mf = float(max_force)
        if _has(peak_force):
            pf = float(peak_force)
            pp = None
            if _has(peak_pct):
                pp = float(peak_pct)
            elif mf > 0:
                pp = pf / mf * 100.0
            if pp is not None:
                if pp > 100.0:
                    fail_items.append(
                        f"joint force ({pf:.1f} > {mf:.1f} N, {pp:.1f}%)"
                    )
                elif pp > 70.0:
                    near_items.append(f"joint force ({pp:.0f}%)")
                else:
                    pass_items.append("joint force")
            else:
                pass_items.append("joint force")
        else:
            pass_items.append("joint force")
    if fail_items:
        lines.append("FAIL: " + ", ".join(fail_items))
    if near_items:
        lines.append("NEAR LIMIT: " + ", ".join(near_items))
    if pass_items:
        lines.append("PASS: " + ", ".join(pass_items))
    success = metrics.get("success", False)
    failed = metrics.get("failed", False)
    if failed:
        lines.append("\n**Outcome**: FAILED (score 0.0/100)")
    elif success:
        lines.append("\n**Outcome**: SUCCESS (score 100.0/100)")
    else:
        lines.append("\n**Outcome**: INCOMPLETE")
    lines.append("")
    return lines

def format_task_metrics(metrics: Dict[str, Any]) -> List[str]:
    if not metrics:
        return ["(No evaluation metrics available.)"]
    viols = metrics.get("constraint_violations")
    if isinstance(viols, list) and viols:
        parts = ["### Design Constraint Violations (Build Phase)"]
        for v in viols:
            parts.append(f"- {v}")
        if "failure_reason" in metrics:
            parts.append(f"- Outcome: {metrics['failure_reason']}")
        return parts
    all_lines: List[str] = []
    health_lines = _section_numerical_health(metrics)
    if health_lines:
        all_lines.extend(health_lines)
    all_lines.extend(_section_temporal_chronology(metrics))
    all_lines.extend(_section_spatial_diagnostics(metrics))
    all_lines.extend(_section_load_stress(metrics))
    all_lines.extend(_section_forcing_environment(metrics))
    all_lines.extend(_section_constraint_profile(metrics))
    return all_lines

def get_improvement_suggestions(
    metrics: Dict[str, Any],
    score: float,
    success: bool,
    failed: bool,
    failure_reason: str = None,
    error: str = None,

) -> List[str]:
    if error:
        return ["- Fix the code error reported above before tuning the design."]
    if metrics.get("constraint_violations"):
        return ["- Resolve the design constraint violation(s) listed above."]
    suggestions = []
    if not metrics:
        suggestions.append(
        )
        return suggestions
    if metrics.get("structure_broken"):
        suggestions.append(
        )
    if metrics.get("failed") and not metrics.get("structure_broken"):
        fr = metrics.get("failure_reason", "")
        if "cargo" in str(fr).lower():
            suggestions.append(
            )
        if "capsize" in str(fr).lower() or "angle" in str(fr).lower():
            suggestions.append(
            )
    if not suggestions:
        suggestions.append(
        )
    return suggestions
