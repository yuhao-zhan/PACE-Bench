from __future__ import annotations

import math

from typing import Any, Dict, List, Optional, Tuple

_KNOWN_SCALAR_KEYS = frozenset({
    "step_count", "joint_count", "beam_count", "initial_joint_count",
    "structure_mass", "max_structure_mass",
    "max_joint_reaction_force", "max_joint_reaction_torque",
    "joint_break_force_limit", "joint_break_torque_limit",
    "effective_joint_force_limit", "effective_joint_torque_limit",
    "simulation_time_s", "wind_pressure", "fatigue_factor",
    "fatigue_tau", "peak_body_speed",
    "mass_freq_1", "mass_amp_1", "mass_freq_2", "mass_amp_2",
    "mass_phase_gradient",
    "base_exc_horiz_amp", "base_exc_vert_amp", "base_exc_freq",
    "joint_break_force_nominal", "joint_break_torque_nominal",
    "fatigue_tau_nominal", "wind_pressure_nominal",
    "mass_freq_1_nominal", "mass_amp_1_nominal",
    "mass_freq_2_nominal", "mass_amp_2_nominal",
    "mass_phase_gradient_nominal",
    "base_exc_vert_amp_nominal", "base_exc_horiz_amp_nominal",
    "base_exc_freq_nominal",

})

_KNOWN_LIST_KEYS = frozenset({"joints_ever_broken"})

_KNOWN_DICT_KEYS = frozenset({
    "per_joint_peaks", "joint_anchor_positions", "beam_areas",
    "gravity", "base_excitation_params", "mass_variation_params",

})

def _as_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x

def _is_bad_number(x: float) -> bool:
    return not math.isfinite(x)

def _metrics_have_nonfinite_values(metrics: Dict[str, Any]) -> bool:
    for key in _KNOWN_SCALAR_KEYS:
        if key not in metrics:
            continue
        v = _as_float(metrics.get(key))
        if v is not None and _is_bad_number(v):
            return True
    for key in _KNOWN_DICT_KEYS:
        d = metrics.get(key)
        if not isinstance(d, dict):
            continue
        for v in d.values():
            if isinstance(v, (int, float)) and _is_bad_number(float(v)):
                return True
    return False

def _effective_force_limit(metrics: Dict[str, Any]) -> Optional[float]:
    v = _as_float(metrics.get("effective_joint_force_limit"))
    if v is not None:
        return v
    return _as_float(metrics.get("joint_break_force_limit"))

def _effective_torque_limit(metrics: Dict[str, Any]) -> Optional[float]:
    v = _as_float(metrics.get("effective_joint_torque_limit"))
    if v is not None:
        return v
    return _as_float(metrics.get("joint_break_torque_limit"))

def _utilization(peak: Optional[float], limit: Optional[float]) -> Optional[float]:
    if peak is None or limit is None:
        return None
    if _is_bad_number(peak) or _is_bad_number(limit):
        return None
    eps = max(abs(limit) * 1e-12, 1e-15)
    if abs(limit) < eps:
        return None
    return peak / limit

def _fmt_util_pct(u: Optional[float]) -> str:
    if u is None:
        return "n/a"
    pct = u * 100.0
    if _is_bad_number(pct):
        return "n/a"
    return f"{pct:.1f}%"

def _fmt_margin_pct(u: Optional[float]) -> str:
    if u is None:
        return "n/a"
    margin = (1.0 - u) * 100.0
    if _is_bad_number(margin):
        return "n/a"
    sign = "+" if margin >= 0 else ""
    return f"{sign}{margin:.1f}%"

def _tier_label(u: Optional[float]) -> str:
    if u is None:
        return "UNKNOWN"
    pct = u * 100.0
    if pct > 100.0:
        return "FAILED"
    if pct > 80.0:
        return "CRITICAL"
    if pct > 50.0:
        return "ELEVATED"
    return "NOMINAL"

def _safe_div(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None:
        return None
    if _is_bad_number(a) or _is_bad_number(b):
        return None
    if abs(b) < 1e-15:
        return None
    return a / b

def _spatial_context(ax: Optional[float], ay: Optional[float],
                     span_left: float = 6.0, span_right: float = 14.0,
                     ground_y: float = 1.0, deck_y: float = 2.0) -> str:
    if ax is None or ay is None:
        return ""
    parts = []
    if ax <= span_left + 0.5:
        parts.append("LEFT-EDGE")
    elif ax >= span_right - 0.5:
        parts.append("RIGHT-EDGE")
    elif ax <= span_left + 2.0:
        parts.append("LEFT-SPAN")
    elif ax >= span_right - 2.0:
        parts.append("RIGHT-SPAN")
    elif abs(ax - (span_left + span_right) / 2) < 1.0:
        parts.append("CENTER-SPAN")
    else:
        parts.append("MID-SPAN")
    if ay <= ground_y + 0.3:
        parts.append("GROUND-LEVEL")
    elif ay <= deck_y + 0.3:
        parts.append("DECK-LEVEL")
    else:
        parts.append("ELEVATED")
    return "  [" + ", ".join(parts) + "]"

def _compute_joint_entries(
    metrics: Dict[str, Any],
    f_eff: Optional[float],
    t_eff: Optional[float],

) -> List[Dict]:
    per_joint = metrics.get("per_joint_peaks")
    if not isinstance(per_joint, dict) or len(per_joint) == 0:
        return []
    entries = []
    for jid, data in per_joint.items():
        if not isinstance(data, dict):
            continue
        jtype = data.get("type", "?")
        fj = _as_float(data.get("force"))
        tj = _as_float(data.get("torque"))
        ax = _as_float(data.get("anchor_x"))
        ay = _as_float(data.get("anchor_y"))
        uf = _utilization(fj, f_eff)
        ut = _utilization(tj, t_eff)
        worst_u = None
        if uf is not None and ut is not None:
            worst_u = max(uf, ut)
        elif uf is not None:
            worst_u = uf
        elif ut is not None:
            worst_u = ut
        entries.append({
            "jid": jid, "type": jtype, "ax": ax, "ay": ay,
            "fj": fj, "tj": tj, "uf": uf, "ut": ut,
            "worst_u": worst_u,
        })
    entries.sort(key=lambda je: -(je["worst_u"] or -1.0))
    return entries

def _section_constraint_profile(metrics: Dict[str, Any]) -> List[str]:
    parts: List[str] = []
    parts.append("## 1. Constraint Satisfaction\n")
    max_mass = _as_float(metrics.get("max_structure_mass", 400.0))
    struct_mass = _as_float(metrics.get("structure_mass"))
    min_beams = int(metrics.get("min_beams", _as_float(metrics.get("MIN_BEAMS", 5)) or 5))
    min_joints = int(metrics.get("min_joints", _as_float(metrics.get("MIN_JOINTS", 6)) or 6))
    beam_count = int(_as_float(metrics.get("beam_count", 0)) or 0)
    joint_count_init = int(_as_float(metrics.get("initial_joint_count", 0)) or 0)
    failures: List[str] = []
    if struct_mass is not None and max_mass is not None and math.isfinite(max_mass) and max_mass > 0:
        ratio = struct_mass / max_mass
        if struct_mass > max_mass:
            failures.append(f"Mass budget: {struct_mass:.3f} / {max_mass:.3f} kg ({ratio*100:.1f}% — EXCEEDED)")
        elif ratio > 0.5:
            failures.append(f"Mass budget: {ratio*100:.1f}% used ({struct_mass:.3f} / {max_mass:.3f} kg)")
    if beam_count < min_beams:
        failures.append(f"Beam count: {beam_count} / min {min_beams} (short by {min_beams - beam_count})")
    if joint_count_init < min_joints:
        failures.append(f"Joint count: {joint_count_init} / min {min_joints} (short by {min_joints - joint_count_init})")
    per_joint = metrics.get("per_joint_peaks")
    has_pivot = False
    if isinstance(per_joint, dict):
        for data in per_joint.values():
            if isinstance(data, dict) and data.get("type") == "pivot":
                has_pivot = True
                break
    if not has_pivot:
        failures.append("Missing pivot joint (revolute)")
    if failures:
        for f in failures:
            parts.append(f"  [FAIL]  {f}")
    else:
        parts.append(f"  Build constraints all pass "
                     f"(mass {struct_mass:.3f}/{max_mass:.3f} kg, "
                     f"{beam_count} beams ≥ {min_beams}, "
                     f"{joint_count_init} joints ≥ {min_joints}, pivot present)")
    jc = int(_as_float(metrics.get("joint_count", 0)) or 0)
    jc_init = int(_as_float(metrics.get("initial_joint_count", 0)) or 0)
    broken_count = max(0, jc_init - jc)
    structure_broken = metrics.get("structure_broken", False)
    if broken_count > 0 or structure_broken:
        parts.append(f"  [FAIL]  Joint integrity: {broken_count} of {jc_init} joints broken")
    else:
        parts.append(f"  [PASS]  Joint integrity: all {jc_init} intact")
    f_eff = _effective_force_limit(metrics)
    t_eff = _effective_torque_limit(metrics)
    entries = _compute_joint_entries(metrics, f_eff, t_eff)
    if entries:
        stressed = [je for je in entries if (je["worst_u"] or 0) > 0.01]
        if stressed:
            closest = stressed[0]
            parts.append(f"  Closest survivor margin: {_fmt_margin_pct(closest['worst_u'])} "
                         f"(utilization {_fmt_util_pct(closest['worst_u'])})")
    return parts

def _section_temporal_chronology(metrics: Dict[str, Any]) -> List[str]:
    parts: List[str] = []
    parts.append("## 2. Temporal Events\n")
    joints_broken = metrics.get("joints_ever_broken")
    f_eff = _effective_force_limit(metrics)
    t_eff = _effective_torque_limit(metrics)
    if not isinstance(joints_broken, list) or len(joints_broken) == 0:
        sc = _as_float(metrics.get("step_count", 0))
        parts.append(f"  No joint failures (terminated at step {int(sc) if sc is not None else '?'}).")
        return parts
    sorted_broken = sorted(
        joints_broken,
        key=lambda bj: (
            _as_float(bj.get("break_step")) if isinstance(bj, dict)
            and bj.get("break_step") is not None else float('inf')
        )
    )
    parts.append(f"  {len(sorted_broken)} joint failure(s):\n")
    prev_step = None
    for idx, bj in enumerate(sorted_broken, start=1):
        if not isinstance(bj, dict):
            continue
        jtype = bj.get("joint_type", "?")
        ax = bj.get("anchor_x")
        ay = bj.get("anchor_y")
        bstep = bj.get("break_step")
        pf = _as_float(bj.get("peak_force_at_break"))
        pt = _as_float(bj.get("peak_torque_at_break"))
        pos_str = ""
        if ax is not None and ay is not None:
            try:
                pos_str = f"anchor=({float(ax):.2f}, {float(ay):.2f})"
            except (TypeError, ValueError):
                pos_str = "anchor=?"
        else:
            pos_str = "anchor=?"
        ctx = _spatial_context(_as_float(ax), _as_float(ay))
        uf = _utilization(pf, f_eff)
        ut = _utilization(pt, t_eff)
        line = f"  [{idx}] {jtype}  {pos_str}{ctx}  step={bstep if bstep is not None else '?'}"
        if prev_step is not None and bstep is not None:
            try:
                delta = int(bstep) - int(prev_step)
                line += f"  (+{delta} steps)"
            except (TypeError, ValueError):
                pass
        if pf is not None and math.isfinite(pf):
            line += f"  force={pf:.6g} N"
            if uf is not None:
                line += f" [{_fmt_util_pct(uf)} of limit]"
        if pt is not None and math.isfinite(pt):
            line += f"  torque={pt:.6g} N·m"
            if ut is not None:
                line += f" [{_fmt_util_pct(ut)} of limit]"
        parts.append(line)
        if bstep is not None:
            try:
                prev_step = int(bstep)
            except (TypeError, ValueError):
                pass
    if len(sorted_broken) >= 2:
        first_step = sorted_broken[0].get("break_step") if isinstance(sorted_broken[0], dict) else None
        last_step = sorted_broken[-1].get("break_step") if isinstance(sorted_broken[-1], dict) else None
        if first_step is not None and last_step is not None:
            try:
                cascade_duration = int(last_step) - int(first_step)
                if cascade_duration == 0:
                    parts.append(f"  Cascade: all {len(sorted_broken)} failures same step (simultaneous collapse).")
                else:
                    avg_interval = cascade_duration / max(1, len(sorted_broken) - 1)
                    parts.append(f"  Cascade: {len(sorted_broken)} failures over {cascade_duration} steps "
                                 f"(avg interval {avg_interval:.1f} steps).")
            except (TypeError, ValueError):
                pass
    return parts

def _section_spatial_load(metrics: Dict[str, Any]) -> List[str]:
    parts: List[str] = []
    parts.append("## 3. Joint Stress Profile\n")
    f_eff = _effective_force_limit(metrics)
    t_eff = _effective_torque_limit(metrics)
    entries = _compute_joint_entries(metrics, f_eff, t_eff)
    if not entries:
        parts.append("  No per-joint peak data available.")
        return parts
    f_nom = _as_float(metrics.get("joint_break_force_limit"))
    if f_eff is not None and math.isfinite(f_eff):
        nom_str = f"(nominal {f_nom:.6g} N)" if (f_nom is not None and math.isfinite(f_nom)) else ""
        parts.append(f"  Force limit: {f_eff:.6g} N {nom_str}".rstrip())
    t_nom = _as_float(metrics.get("joint_break_torque_limit"))
    if t_eff is not None and math.isfinite(t_eff):
        nom_str = f"(nominal {t_nom:.6g} N·m)" if (t_nom is not None and math.isfinite(t_nom)) else ""
        parts.append(f"  Torque limit: {t_eff:.6g} N·m {nom_str}".rstrip())
    tiers: Dict[str, List[Dict]] = {"FAILED": [], "CRITICAL": [], "ELEVATED": [], "NOMINAL": []}
    for je in entries:
        tier = _tier_label(je["worst_u"])
        tiers.setdefault(tier, []).append(je)
    tier_summary_parts = []
    for tier_name in ("FAILED", "CRITICAL", "ELEVATED", "NOMINAL"):
        count = len(tiers.get(tier_name, []))
        if count > 0:
            tier_summary_parts.append(f"{tier_name}: {count}")
    parts.append(f"  {len(entries)} joints — " + "  |  ".join(tier_summary_parts))
    nonzero_entries = [je for je in entries if (je["worst_u"] or 0) > 1e-12]
    zero_count = len(entries) - len(nonzero_entries)
    if not nonzero_entries:
        parts.append(f"  All {len(entries)} joints at zero stress (no load applied).")
        return parts
    if zero_count > 0:
        parts.append(f"  {zero_count} joints at zero stress (omitted).")
        parts.append(f"  {len(nonzero_entries)} joints with measurable stress:\n")
    else:
        parts.append("")
    for rank, je in enumerate(nonzero_entries, start=1):
        ax = je["ax"]
        ay = je["ay"]
        jtype = je["type"]
        fj = je["fj"]
        tj = je["tj"]
        uf = je["uf"]
        ut = je["ut"]
        tier = _tier_label(je["worst_u"])
        pos_str = f"({ax:.2f}, {ay:.2f})" if (ax is not None and ay is not None) else "(?,?)"
        ctx = _spatial_context(ax, ay)
        line = f"  [{rank}] {jtype} @ {pos_str}{ctx}  [{tier}]"
        parts.append(line)
        if fj is not None and math.isfinite(fj):
            fm = _fmt_margin_pct(uf) if uf is not None else "n/a"
            parts.append(f"        force: peak={fj:.6g} N  util={_fmt_util_pct(uf)}  margin={fm}")
        if tj is not None and math.isfinite(tj):
            tm = _fmt_margin_pct(ut) if ut is not None else "n/a"
            parts.append(f"        torque: peak={tj:.6g} N·m  util={_fmt_util_pct(ut)}  margin={tm}")
    critical_entries = tiers.get("CRITICAL", []) + tiers.get("FAILED", [])
    if len(critical_entries) >= 2:
        xs = [je["ax"] for je in critical_entries if je["ax"] is not None]
        ys = [je["ay"] for je in critical_entries if je["ay"] is not None]
        if xs and ys:
            parts.append(f"\n  Stress concentration: "
                         f"x ∈ [{min(xs):.2f}, {max(xs):.2f}], "
                         f"y ∈ [{min(ys):.2f}, {max(ys):.2f}] "
                         f"({len(critical_entries)} joints critical/failed)")
    return parts

def _section_energy_fatigue(metrics: Dict[str, Any]) -> List[str]:
    parts: List[str] = []
    parts.append("## 4. Energy & Fatigue\n")
    mf1 = _as_float(metrics.get("mass_freq_1"))
    ma1 = _as_float(metrics.get("mass_amp_1"))
    mf2 = _as_float(metrics.get("mass_freq_2"))
    ma2 = _as_float(metrics.get("mass_amp_2"))
    mpg = _as_float(metrics.get("mass_phase_gradient"))
    mass_parts = []
    if mf1 is not None:
        mass_parts.append(f"f1={mf1:.3f} Hz (amp={ma1:.3f})" if ma1 is not None else f"f1={mf1:.3f} Hz")
    if mf2 is not None:
        mass_parts.append(f"f2={mf2:.3f} Hz (amp={ma2:.3f})" if ma2 is not None else f"f2={mf2:.3f} Hz")
    if mpg is not None:
        mass_parts.append(f"phase_gradient={mpg:.3f} rad/m")
    if mass_parts:
        parts.append("  Mass variation: " + "  ".join(mass_parts))
    ff = _as_float(metrics.get("fatigue_factor"))
    tau = _as_float(metrics.get("fatigue_tau"))
    t_sim = _as_float(metrics.get("simulation_time_s"))
    if ff is not None and math.isfinite(ff):
        tau_str = f"τ={tau:.1f} s" if (tau is not None and math.isfinite(tau)) else "τ=?"
        parts.append(f"  Fatigue: {ff*100:.1f}% capacity retained "
                     f"(after {t_sim:.2f} s, {tau_str})" if t_sim is not None
                     else f"  Fatigue: {ff*100:.1f}% capacity retained")
    wp = _as_float(metrics.get("wind_pressure", 0.0))
    if wp is not None and abs(wp) > 1e-9:
        parts.append(f"  Wind pressure: {wp:.4g} Pa (active)")
        beam_areas = metrics.get("beam_areas")
        if isinstance(beam_areas, dict) and beam_areas:
            total_area = sum(float(a) for a in beam_areas.values() if math.isfinite(float(a)))
            parts.append(f"  Wind force: ~{wp * total_area:.4g} N "
                         f"(area {total_area:.4f} m²)")
    return parts

def _section_parameter_delta(metrics: Dict[str, Any]) -> List[str]:
    parts: List[str] = []
    parts.append("## 5. Parameter Deviations\n")
    param_specs = [
        ("Joint break force", "joint_break_force_limit", "joint_break_force_nominal", "N"),
        ("Joint break torque", "joint_break_torque_limit", "joint_break_torque_nominal", "N·m"),
        ("Fatigue time constant τ", "fatigue_tau", "fatigue_tau_nominal", "s"),
        ("Wind pressure", "wind_pressure", "wind_pressure_nominal", "Pa"),
        ("Mass freq 1", "mass_freq_1", "mass_freq_1_nominal", "Hz"),
        ("Mass amp 1", "mass_amp_1", "mass_amp_1_nominal", ""),
        ("Mass freq 2", "mass_freq_2", "mass_freq_2_nominal", "Hz"),
        ("Mass amp 2", "mass_amp_2", "mass_amp_2_nominal", ""),
        ("Mass phase gradient", "mass_phase_gradient", "mass_phase_gradient_nominal", "rad/m"),
    ]
    deltas: List[str] = []
    for label, actual_key, nominal_key, unit in param_specs:
        actual = _as_float(metrics.get(actual_key))
        nominal = _as_float(metrics.get(nominal_key))
        if actual is None or nominal is None:
            continue
        if not (math.isfinite(actual) and math.isfinite(nominal)):
            continue
        if abs(nominal) < 1e-15:
            if abs(actual) > 1e-15:
                deltas.append(f"  {label}: {actual:.6g} {unit}  (was nominal {nominal:.6g} {unit})")
            continue
        ratio = _safe_div(actual, nominal)
        if ratio is None:
            continue
        if abs(ratio - 1.0) < 1e-9:
            continue
        if ratio >= 1000.0:
            delta_str = f"{ratio:.1f}× nominal ({nominal:.6g} → {actual:.6g} {unit})"
        elif ratio <= 0.001:
            delta_str = f"{ratio:.6g}× nominal ({nominal:.6g} → {actual:.6g} {unit})"
        elif ratio > 1.0:
            pct = (ratio - 1.0) * 100.0
            delta_str = f"+{pct:.1f}% vs nominal ({nominal:.6g} → {actual:.6g} {unit})"
        else:
            pct = (1.0 - ratio) * 100.0
            delta_str = f"-{pct:.1f}% vs nominal ({nominal:.6g} → {actual:.6g} {unit})"
        deltas.append(f"  {label}: {delta_str}")
    if not deltas:
        parts.append("  All physics parameters match nominal defaults.")
    else:
        parts.extend(deltas)
    return parts

def _section_numerical_health(metrics: Dict[str, Any]) -> List[str]:
    parts: List[str] = []
    parts.append("## 6. Numerical Health\n")
    has_nonfinite = _metrics_have_nonfinite_values(metrics)
    if has_nonfinite:
        parts.append("  **WARNING**: Non-finite (NaN/Inf) values detected in metrics.")
    pbs = _as_float(metrics.get("peak_body_speed"))
    if pbs is not None and math.isfinite(pbs):
        if pbs > 100.0:
            parts.append(f"  **WARNING**: Peak body speed {pbs:.2f} m/s — possible solver instability.")
        elif pbs > 50.0:
            parts.append(f"  **CAUTION**: Peak body speed {pbs:.2f} m/s.")
    else:
        parts.append("  Peak body speed: not available.")
    sc = _as_float(metrics.get("step_count", 0))
    if sc is not None and sc <= 1:
        parts.append("  **NOTE**: Terminated at step ≤ 1 — check for immediate structural failure or build error.")
    jc = int(_as_float(metrics.get("joint_count", 0)) or 0)
    ijc = int(_as_float(metrics.get("initial_joint_count", 0)) or 0)
    if ijc > 0 and jc == 0:
        parts.append("  **NOTE**: All joints destroyed — complete structural collapse.")
    sm = _as_float(metrics.get("structure_mass"))
    if sm is not None and math.isfinite(sm) and sm <= 0:
        parts.append("  **WARNING**: Structure mass is zero or negative.")
    if not parts[1:]:
        if not has_nonfinite:
            return []
        return ["## 6. Numerical Health\n  No anomalies detected."]
    return parts

def format_task_metrics(metrics: Dict[str, Any]) -> List[str]:
    parts: List[str] = []
    if not metrics:
        return parts
    if "error" in metrics:
        parts.append(f"**Evaluation error**: {metrics['error']}")
        return parts
    parts.append("## Diagnostic Report — E-04 Variable Mass\n")
    success = metrics.get("success", False)
    failed = metrics.get("failed", False)
    fr = metrics.get("failure_reason")
    if success:
        parts.append("**Outcome**: SUCCESS")
    elif failed:
        parts.append(f"**Outcome**: FAILED — {fr}" if fr else "**Outcome**: FAILED")
    else:
        parts.append("**Outcome**: INCOMPLETE (simulation ended before full duration)")
    sc = int(_as_float(metrics.get("step_count", 0)) or 0)
    max_steps = 12000
    progress_pct = sc / max(max_steps, 1) * 100.0
    parts.append(f"**Step**: {sc} / {max_steps} ({progress_pct:.1f}%)")
    st = _as_float(metrics.get("simulation_time_s"))
    if st is not None and math.isfinite(st):
        parts.append(f"**Time**: {st:.3f} s")
    jc = int(_as_float(metrics.get("joint_count", 0)) or 0)
    bc = int(_as_float(metrics.get("beam_count", 0)) or 0)
    ijc = int(_as_float(metrics.get("initial_joint_count", 0)) or 0)
    broken = max(0, ijc - jc)
    topo = f"**Topology**: {bc} beams, {jc}/{ijc} joints" + (f" ({broken} broken)" if broken > 0 else "")
    parts.append(topo)
    sm = _as_float(metrics.get("structure_mass"))
    if sm is not None and math.isfinite(sm):
        parts.append(f"**Mass**: {sm:.4f} kg")
    ff = _as_float(metrics.get("fatigue_factor"))
    if ff is not None and math.isfinite(ff):
        parts.append(f"**Fatigue**: {ff*100:.1f}% capacity retained")
    parts.append("")
    parts.extend(_section_constraint_profile(metrics))
    parts.append("")
    parts.extend(_section_temporal_chronology(metrics))
    parts.append("")
    parts.extend(_section_spatial_load(metrics))
    parts.append("")
    parts.extend(_section_energy_fatigue(metrics))
    parts.append("")
    parts.extend(_section_parameter_delta(metrics))
    parts.append("")
    nh = _section_numerical_health(metrics)
    if nh:
        parts.extend(nh)
    return parts
