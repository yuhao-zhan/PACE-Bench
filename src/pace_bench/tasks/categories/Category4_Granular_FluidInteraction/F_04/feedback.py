from __future__ import annotations

from typing import Any, Dict, List, Optional

import math

def _fm(x: float, decimals: int = 3) -> str:
    if not math.isfinite(x):
        return str(x)
    s = f"{float(x):.{decimals}f}".rstrip("0").rstrip(".")
    return s if s else "0"

def _g(metrics: Dict[str, Any], key: str, default: Any = None) -> Any:
    return metrics.get(key, default) if isinstance(metrics, dict) else default

def _ratio_str(num, denom) -> str:
    try:
        n, d = float(num), float(denom)
        if not math.isfinite(d) or d == 0:
            return "—"
        pct = 100.0 * n / d
        return f"{n}/{d} ({pct:.1f}%)"
    except (TypeError, ValueError):
        return "—"

def _pct_str(num, denom) -> str:
    try:
        n, d = float(num), float(denom)
        if not math.isfinite(d) or d == 0:
            return "—"
        return f"{100.0 * n / d:.1f}%"
    except (TypeError, ValueError):
        return "—"

def _section_temporal(metrics: Dict[str, Any]) -> List[str]:
    parts: List[str] = []
    step = _g(metrics, "step_count", None)
    max_steps_val = _g(metrics, "max_steps", None)
    progress = _g(metrics, "progress_pct", None)
    spawned = _g(metrics, "spawned_particle_count", None)
    planned = _g(metrics, "planned_total_particle_count", None)
    parts.append("### 1. Temporal Event Chronology")
    line = f"- **Step**: {step}" if step is not None else "- **Step**: N/A"
    if max_steps_val is not None:
        line += f" / {max_steps_val}"
    if progress is not None:
        try:
            line += f" ({float(progress):.1f}%)"
        except (TypeError, ValueError):
            pass
    parts.append(line)
    physics = _g(metrics, "physics_summary", {}) or {}
    sc = int(physics.get("step_count", step or 0))
    sec_wave = int(_g(metrics, "second_wave_step",
                 _g(physics, "second_wave_step", None)) or 0)
    thr_wave = int(_g(metrics, "third_wave_step",
                 _g(physics, "third_wave_step", None)) or 0)
    wave_notes = []
    if sec_wave:
        wave_notes.append(
            f"2nd-wave@{sec_wave}={'spawned' if sc >= sec_wave else 'pending'}"
        )
    if thr_wave:
        wave_notes.append(
            f"3rd-wave@{thr_wave}={'spawned' if sc >= thr_wave else 'pending'}"
        )
    if wave_notes:
        parts.append(f"- **Wave triggers**: {', '.join(wave_notes)}")
    if spawned is not None:
        line = f"- **Active particles**: {spawned}"
        if planned is not None and planned > 0:
            line += f" / {planned} ({100.0 * spawned / planned:.0f}%)"
        parts.append(line)
    if _g(metrics, "failed"):
        parts.append(f"- **Stopped**: {_g(metrics, 'failure_reason', '')}")
    elif _g(metrics, "success"):
        parts.append("- **Stopped**: success criteria met")
    return parts

def _section_spatial(metrics: Dict[str, Any]) -> List[str]:
    parts: List[str] = []
    y_stats = _g(metrics, "particle_y_stats", {}) or {}
    zone = _g(metrics, "zone_boundaries", {}) or {}
    beam_margins = _g(metrics, "beam_build_zone_margins", []) or []
    parts.append("### 2. Spatial Diagnostics with Margins")
    small_ceil = zone.get("small_zone_y_max", 1.92)
    medium_floor = zone.get("medium_zone_y_min", 1.92)
    medium_ceil = zone.get("medium_zone_y_max", 2.52)
    large_floor = zone.get("large_zone_y_min", 2.52)
    build_x0 = zone.get("build_zone_x_min", 5.20)
    build_x1 = zone.get("build_zone_x_max", 6.90)
    build_y0 = zone.get("build_zone_y_min", 1.72)
    build_y1 = zone.get("build_zone_y_max", 2.45)
    feed_y0 = zone.get("feed_y_min", 3.0)
    parts.append(f"\n**Zones**: Small y<{small_ceil} | "
                 f"Medium {medium_floor}≤y<{medium_ceil} | "
                 f"Large y≥{large_floor} | "
                 f"Build x∈[{build_x0},{build_x1}] y∈[{build_y0},{build_y1}] | "
                 f"Feed y≥{feed_y0}")
    parts.append("\n**Particle Y positions:**")
    for label, target_lo, target_hi in [
        ("small", None, small_ceil),
        ("medium", medium_floor, medium_ceil),
        ("large", large_floor, None),
    ]:
        stats = y_stats.get(label, {}) or {}
        cnt = stats.get("count", 0)
        if cnt == 0:
            parts.append(f"- {label.capitalize()}: 0 active")
            continue
        mn = stats.get("min")
        mx = stats.get("max")
        med = stats.get("median")
        mean = stats.get("mean")
        pos_str = (f"min={_fm(mn, 2)} med={_fm(med, 2)} "
                   f"mean={_fm(mean, 2)} max={_fm(mx, 2)}")
        margin_notes = []
        if label == "small" and target_hi is not None and mx is not None:
            m = target_hi - mx
            if m < 0:
                margin_notes.append(f"breached ceiling by {_fm(abs(m), 2)} m")
            elif m < 0.3:
                margin_notes.append(f"near ceiling ({_fm(m, 2)} m margin)")
        elif label == "medium":
            if target_lo is not None and mn is not None:
                m_below = mn - target_lo
                if m_below < 0:
                    margin_notes.append(f"breached floor by {_fm(abs(m_below), 2)} m")
                elif m_below < 0.3:
                    margin_notes.append(f"near floor ({_fm(m_below, 2)} m)")
            if target_hi is not None and mx is not None:
                m_above = target_hi - mx
                if m_above < 0:
                    margin_notes.append(f"breached ceiling by {_fm(abs(m_above), 2)} m")
                elif m_above < 0.3:
                    margin_notes.append(f"near ceiling ({_fm(m_above, 2)} m)")
        elif label == "large" and target_lo is not None and mn is not None:
            m = mn - target_lo
            if m < 0:
                margin_notes.append(f"below floor by {_fm(abs(m), 2)} m")
            elif m < 0.3:
                margin_notes.append(f"near floor ({_fm(m, 2)} m)")
        line = f"- {label.capitalize()} ({cnt}): {pos_str}"
        if margin_notes:
            line += f" [{', '.join(margin_notes)}]"
        parts.append(line)
    s_above = _g(metrics, "small_above_sieve")
    s_band = _g(metrics, "small_in_sieve_band")
    s_large = _g(metrics, "small_in_large_zone")
    m_small = _g(metrics, "medium_in_small_zone")
    m_ok = _g(metrics, "medium_in_medium_zone")
    m_large = _g(metrics, "medium_in_large_zone")
    l_small = _g(metrics, "large_in_small_zone")
    l_band = _g(metrics, "large_in_sieve_band")
    l_below = _g(metrics, "large_below_sieve")
    have_sieve = any(v is not None for v in [s_above, s_band, s_large,
                                              m_small, m_ok, m_large,
                                              l_small, l_band, l_below])
    if have_sieve:
        parts.append("\n**Sieve transit (zone counts):**")
        s_parts = []
        if s_above is not None:
            s_parts.append(f"above={s_above}")
        if s_band is not None:
            s_parts.append(f"band={s_band}")
        if s_large is not None:
            s_parts.append(f"large={s_large}")
        if s_parts:
            parts.append(f"- Small: {', '.join(s_parts)}")
        m_parts = []
        if m_small is not None:
            m_parts.append(f"small={m_small}")
        if m_ok is not None:
            m_parts.append(f"target={m_ok}")
        if m_large is not None:
            m_parts.append(f"large={m_large}")
        if m_parts:
            parts.append(f"- Medium: {', '.join(m_parts)}")
        l_parts = []
        if l_small is not None:
            l_parts.append(f"small={l_small}")
        if l_band is not None:
            l_parts.append(f"band={l_band}")
        if l_below is not None:
            l_parts.append(f"below={l_below}")
        if l_parts:
            parts.append(f"- Large: {', '.join(l_parts)}")
    if beam_margins:
        violated = sum(1 for bm in beam_margins
                       if bm.get("vertex_x_margin", 0) < 0 or bm.get("vertex_y_margin", 0) < 0)
        tight = sum(1 for bm in beam_margins
                    if (0 <= bm.get("vertex_x_margin", 0) < 0.05 or
                        0 <= bm.get("vertex_y_margin", 0) < 0.05)
                    and not (bm.get("vertex_x_margin", 0) < 0 or bm.get("vertex_y_margin", 0) < 0))
        total = len(beam_margins)
        status_parts = [f"{total} beams"]
        if violated:
            status_parts.append(f"{violated} VIOLATED")
        if tight:
            status_parts.append(f"{tight} TIGHT")
        parts.append(f"\n**Beam build-zone margins**: {', '.join(status_parts)}")
    else:
        parts.append("\n**Beam build-zone margins**: No beams placed.")
    return parts

def _section_load(metrics: Dict[str, Any]) -> List[str]:
    parts: List[str] = []
    force_est = _g(metrics, "env_force_estimates", {}) or {}
    parts.append("### 3. Load & Stress Distribution")
    if not force_est:
        parts.append("- Not available")
        return parts
    parts.append("\n**Per-class environmental forces:**")
    for label, display in [("small", "Small"), ("medium", "Medium"), ("large", "Large")]:
        fe = force_est.get(label, {})
        cnt = fe.get("count", 0)
        if cnt == 0:
            parts.append(f"- {display}: 0 active")
            continue
        fx = fe.get("fx_total", 0)
        wind_x = fe.get("wind_x", 0)
        avg_m = fe.get("avg_mass", 0)
        parts.append(f"- {display} ({cnt}, avg {_fm(avg_m, 2)} kg): "
                     f"fx_total={_fm(fx, 1)} N (wind_x={_fm(wind_x, 1)} N)")
    return parts

def _section_energy(metrics: Dict[str, Any]) -> List[str]:
    parts: List[str] = []
    ke = _g(metrics, "total_kinetic_energy", None)
    physics = _g(metrics, "physics_summary", {}) or {}
    parts.append("### 4. Energy & Power Flow")
    if ke is not None:
        parts.append(f"- **Total particle kinetic energy**: {_fm(ke, 2)} J")
    else:
        parts.append("- **Total particle kinetic energy**: not available")
    beam_fric = physics.get("beam_friction", 0.4)
    if beam_fric == 0:
        parts.append(f"- **Beam friction**: 0.0 — zero passive holding")
    return parts

def _section_constraints(metrics: Dict[str, Any]) -> List[str]:
    parts: List[str] = []
    parts.append("### 5. Constraint Satisfaction Profile")
    parts.append("\n**Build-time constraints:**")
    mass = _g(metrics, "structure_mass")
    max_mass = _g(metrics, "max_structure_mass")
    if mass is not None and max_mass is not None:
        margin = max_mass - mass
        if margin >= 0:
            pct = 100.0 * mass / max_mass if max_mass > 0 else 0
            status = "PASS"
            if pct > 70:
                status += f" (near-limit: {pct:.1f}% used)"
            parts.append(f"- **Mass budget**: {_fm(mass, 2)} / {_fm(max_mass, 2)} kg "
                         f"— margin {_fm(margin, 2)} kg [{status}]")
        else:
            parts.append(f"- **Mass budget**: {_fm(mass, 2)} / {_fm(max_mass, 2)} kg "
                         f"— exceeded by {_fm(abs(margin), 2)} kg [FAIL]")
    bc = _g(metrics, "beam_count")
    max_b = _g(metrics, "max_beams")
    if bc is not None and max_b is not None:
        margin = int(max_b) - int(bc)
        if margin >= 0:
            pct = 100.0 * int(bc) / int(max_b) if int(max_b) > 0 else 0
            status = "PASS"
            if pct > 70:
                status += f" (near-limit: {pct:.1f}% used)"
            parts.append(f"- **Beam count**: {bc} / {max_b} — margin {margin} beam(s) [{status}]")
        else:
            parts.append(f"- **Beam count**: {bc} / {max_b} — exceeded by {abs(margin)} [FAIL]")
    beam_margins = _g(metrics, "beam_build_zone_margins", []) or []
    if beam_margins:
        zone_ok = True
        tight_beams = []
        for bm in beam_margins:
            x_m = bm.get("vertex_x_margin", 0)
            y_m = bm.get("vertex_y_margin", 0)
            if x_m < 0 or y_m < 0:
                zone_ok = False
            elif x_m < 0.05 or y_m < 0.05:
                tight_beams.append((bm.get("beam_index", "?"), x_m, y_m))
        if zone_ok:
            parts.append(f"- **Build zone containment**: PASS — all {len(beam_margins)} beams within bounds")
            if tight_beams:
                for idx, xm, ym in tight_beams:
                    parts.append(f"  - Beam {idx}: TIGHT — x-margin={_fm(xm, 4)} m, y-margin={_fm(ym, 4)} m")
    else:
        parts.append("- **Build zone containment**: N/A — no beams placed")
    broken = _g(metrics, "structure_broken", False)
    jc = _g(metrics, "joint_count", 0)
    if broken:
        parts.append(f"- **Structure integrity**: FAILED — ({jc} joints)")
    else:
        parts.append(f"- **Structure integrity**: PASS — {jc} joints intact")
    parts.append("\n**Runtime constraints:**")
    purity = _g(metrics, "purity_percent")
    min_purity = _g(metrics, "min_purity_percent")
    if purity is not None and min_purity is not None:
        margin = purity - min_purity
        if margin >= 0:
            status = "PASS"
            if margin < 10:
                status += f" (near-limit: {purity:.1f}%, target ≥{min_purity:.1f}%)"
            parts.append(f"- **Classification purity**: {purity:.1f}% — "
                         f"margin +{_fm(margin, 1)} pp above {min_purity:.1f}% target [{status}]")
        else:
            parts.append(f"- **Classification purity**: {purity:.1f}% — "
                         f"shortfall {_fm(abs(margin), 1)} pp below {min_purity:.1f}% target [FAIL]")
    contaminated = _g(metrics, "contaminated", None)
    if contaminated is not None:
        parts.append(f"- **Cross-zone contamination below feed (y<{_g(metrics, 'feed_y_min', 3.0)} m)**: "
                     f"{'DETECTED' if contaminated else 'NONE'}")
    s_ok = _g(metrics, "small_in_small_zone", 0) or 0
    m_ok = _g(metrics, "medium_in_medium_zone", 0) or 0
    l_ok = _g(metrics, "large_in_large_zone", 0) or 0
    correct = s_ok + m_ok + l_ok
    spawned_c = _g(metrics, "spawned_particle_count", 0) or 0
    if spawned_c > 0:
        misrouted = spawned_c - correct
        parts.append(f"- **Correct/total**: {correct}/{spawned_c} ({_pct_str(correct, spawned_c)}) "
                     f"— {misrouted} misrouted")
    return parts

def _section_numerical(metrics: Dict[str, Any]) -> List[str]:
    parts: List[str] = []
    nh = _g(metrics, "numerical_health", {}) or {}
    parts.append("### 6. Numerical Health")
    nan_flag = nh.get("nan_detected", False)
    inf_flag = nh.get("inf_detected", False)
    extreme = nh.get("extreme_velocity_events", []) or []
    if not nan_flag and not inf_flag and not extreme:
        parts.append("- All clean: no NaN, Inf, or extreme velocity events")
        return parts
    if nan_flag:
        parts.append("- **NaN detected**: YES")
    else:
        parts.append("- **NaN detected**: No")
    if inf_flag:
        parts.append("- **Inf detected**: YES")
    else:
        parts.append("- **Inf detected**: No")
    if extreme:
        parts.append(f"\n**Extreme velocity events (>100 m/s):** {len(extreme)} detected")
        for ev in extreme[:6]:
            parts.append(f"- {ev.get('class', '?').capitalize()}: "
                         f"speed={_fm(ev.get('speed', 0), 1)} m/s "
                         f"v=({_fm(ev.get('vx', 0), 1)}, {_fm(ev.get('vy', 0), 1)})")
        if len(extreme) > 6:
            parts.append(f"  ... and {len(extreme) - 6} more")
    else:
        parts.append("- **Extreme velocity events (>100 m/s)**: None")
    if nan_flag or inf_flag or extreme:
        vel_stats = _g(metrics, "particle_velocity_stats", {}) or {}
        parts.append("\n**Velocity statistics:**")
        for label, display in [("small", "Small"), ("medium", "Medium"), ("large", "Large")]:
            vs = vel_stats.get(label, {}) or {}
            cnt = vs.get("count", 0)
            if cnt == 0:
                parts.append(f"- {display}: 0 active")
            else:
                extreme_count = sum(1 for ev in extreme if ev.get("class") == label)
                flag = f" ({extreme_count} extreme)" if extreme_count > 0 else ""
                parts.append(f"- {display} ({cnt}): "
                             f"min={_fm(vs.get('min', 0), 2)} m/s, "
                             f"median={_fm(vs.get('median', 0), 2)} m/s, "
                             f"max={_fm(vs.get('max', 0), 2)} m/s{flag}")
    return parts

def _section_constraint_violations(metrics: Dict[str, Any]) -> List[str]:
    parts: List[str] = []
    violations = _g(metrics, "constraint_violations", []) or []
    parts.append("### 1. Design Constraint Violations (Build Phase)")
    parts.append(f"- Step: {_g(metrics, 'step_count', 'N/A')}")
    for v in violations:
        parts.append(f"- Violation: {v}")
    if not violations:
        parts.append("- No violations recorded")
    return parts

def format_task_metrics(metrics: Dict[str, Any]) -> List[str]:
    if not isinstance(metrics, dict):
        return ["**Error**: metrics is not a dict"]
    if _g(metrics, "constraint_violations"):
        return _section_constraint_violations(metrics)
    if "error" in metrics:
        parts = ["### 1. Evaluation Error"]
        parts.append(f"- Error: {metrics.get('error', 'Unknown')}")
        parts.append(f"- Step: {_g(metrics, 'step_count', 'N/A')}")
        return parts
    parts: List[str] = []
    purity = _g(metrics, "purity_percent")
    min_p = _g(metrics, "min_purity_percent")
    parts.append("## Forensic Diagnostic Report — F_04 (Three-way Filter)")
    if _g(metrics, "failed"):
        parts.append(f"**Status**: FAILED — {_g(metrics, 'failure_reason', 'unknown reason')}")
    elif _g(metrics, "success"):
        parts.append("**Status**: SUCCESS")
    else:
        parts.append("**Status**: INCOMPLETE (intermediate snapshot)")
    if purity is not None:
        parts.append(f"**Purity**: {purity:.1f}% / {min_p:.1f}% target "
                     f"({'ABOVE' if purity >= (min_p or 0) else 'BELOW'} threshold)")
    try:
        temporal = _section_temporal(metrics)
        if temporal:
            parts.append("")
            parts.extend(temporal)
    except Exception:
        parts.append("")
        parts.append("### 1. Temporal Event Chronology")
        parts.append("- Error generating temporal section")
    try:
        spatial = _section_spatial(metrics)
        if spatial:
            parts.append("")
            parts.extend(spatial)
    except Exception:
        parts.append("")
        parts.append("### 2. Spatial Diagnostics with Margins")
        parts.append("- Error generating spatial section")
    try:
        load = _section_load(metrics)
        if load:
            parts.append("")
            parts.extend(load)
    except Exception:
        parts.append("")
        parts.append("### 3. Load & Stress Distribution")
        parts.append("- Error generating load section")
    try:
        energy = _section_energy(metrics)
        if energy:
            parts.append("")
            parts.extend(energy)
    except Exception:
        parts.append("")
        parts.append("### 4. Energy & Power Flow")
        parts.append("- Error generating energy section")
    try:
        constraints = _section_constraints(metrics)
        if constraints:
            parts.append("")
            parts.extend(constraints)
    except Exception:
        parts.append("")
        parts.append("### 5. Constraint Satisfaction Profile")
        parts.append("- Error generating constraints section")
    try:
        numerical = _section_numerical(metrics)
        if numerical:
            parts.append("")
            parts.extend(numerical)
    except Exception:
        parts.append("")
        parts.append("### 6. Numerical Health")
        parts.append("- Error generating numerical-health section")
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
        error_lower = str(error).lower()
        if "unexpected keyword argument" in error_lower:
            suggestions.append("- A function was called with an unsupported keyword argument. "
                               "Check the API documentation for allowed parameters.")
        if "prohibited" in error_lower or "attribute" in error_lower:
            suggestions.append("- An operation was blocked or an attribute was accessed that is not "
                               "exposed by the sandbox API. Only use the documented primitives.")
        if "build zone" in error_lower or "footprint extends" in error_lower:
            suggestions.append("- One or more beams extend outside the build zone. "
                               "Stay within the allowed region.")
    if failed and failure_reason:
        fr = str(failure_reason).lower()
        if "build zone" in fr:
            suggestions.append("- Beams must be fully contained in the build zone. "
                               "Check beam widths, heights, and placement.")
        if "constraint violat" in fr or "exceeds maximum" in fr:
            suggestions.append("- A design constraint was breached (mass, beam count, or build zone). "
                               "Reduce structure size or rebalance the design.")
        if "structure integrity" in fr or "structure broken" in fr:
            suggestions.append("- The structure collapsed or shifted. Use only static beams "
                               "and ensure rigid connections.")
        if "purity" in fr:
            suggestions.append("- Classification purity is below the required threshold. "
                               "Review per-zone counts and particle height distributions in the diagnostic report.")
    return suggestions
