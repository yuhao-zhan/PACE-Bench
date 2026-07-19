from __future__ import annotations

import math

from typing import Any, Dict, List, Optional, Tuple

def _f(x: Any, nd: int = 2) -> str:
    try:
        fv = float(x)
        if not math.isfinite(fv):
            return str(fv)
        return f"{fv:.{nd}f}"
    except (TypeError, ValueError):
        return str(x)

def _finite(v: Any) -> Optional[float]:
    try:
        fv = float(v)
        return fv if math.isfinite(fv) else None
    except (TypeError, ValueError):
        return None

def _pct(numerator: Any, denominator: Any, nd: int = 1) -> Optional[str]:
    n = _finite(numerator)
    d = _finite(denominator)
    if n is None or d is None or d == 0.0:
        return None
    return f"{100.0 * n / d:.{nd}f}%"

def _format_temporal_chronology(metrics: Dict[str, Any]) -> List[str]:
    parts: List[str] = []
    tracking = metrics.get("joint_tracking")
    if not isinstance(tracking, dict):
        return parts
    failures = tracking.get("joint_failure_events", []) or []
    history = tracking.get("joint_force_history", []) or []
    jfl = _finite(metrics.get("joint_force_limit", float("inf")))
    parts.append("── Temporal Event Chronology ──")
    step_count = metrics.get("step_count", 0)
    fr = metrics.get("failure_reason", "")
    if step_count == 0 and "design constraint" in str(fr).lower():
        parts.append("Simulation did not start — design constraints failed at build time.")
        return parts
    if not failures:
        if history:
            hp = max(history, key=lambda e: e.get("max_force", 0.0))
            parts.append(
                f"No joint breaks. "
                f"Peak force {_f(hp.get('max_force'), 2)} N at step {hp.get('step', '?')}."
            )
        else:
            if step_count == 0:
                return []
            parts.append("No joint breaks recorded.")
        return parts
    sorted_failures = sorted(failures, key=lambda e: e.get("step", 0))
    total_failures = len(sorted_failures)
    by_step: Dict[int, List[dict]] = {}
    for ev in sorted_failures:
        s = int(ev.get("step", 0))
        by_step.setdefault(s, []).append(ev)
    cascade_events = sorted(by_step.items())
    first_step = cascade_events[0][0]
    last_step = cascade_events[-1][0]
    first_ev = cascade_events[0][1][0]
    parts.append(
        f"**First failure**: Step {first_step} — "
        f"({_f(first_ev.get('anchor_x'))}, {_f(first_ev.get('anchor_y'))}) "
        f"{_f(first_ev.get('force_at_break'))} N"
        + (f" ({_pct(first_ev.get('force_at_break'), jfl)} of {_f(jfl, 0)} N limit)"
           if jfl and jfl < float('inf') else "")
    )
    if len(cascade_events) == 1 and len(cascade_events[0][1]) > 1:
        parts.append(
            f"**Cascade**: {len(cascade_events[0][1])} joints failed simultaneously "
            f"at step {first_step} — catastrophic collapse."
        )
    elif len(cascade_events) > 1:
        parts.append(
            f"**Cascade**: {last_step - first_step} steps "
            f"({first_step} → {last_step}, {len(cascade_events)} distinct moments)"
        )
    parts.append("**Failure timeline**:")
    max_show = 3
    for step_num, evs in cascade_events[:max_show]:
        if len(evs) == 1:
            ev = evs[0]
            parts.append(
                f"  Step {step_num}: ({_f(ev.get('anchor_x'))}, {_f(ev.get('anchor_y'))}) "
                f"{_f(ev.get('force_at_break'))} N"
                + (f" ({_pct(ev.get('force_at_break'), jfl)} of limit)"
                   if jfl and jfl < float('inf') else "")
            )
        else:
            peak_force = max(ev.get("force_at_break", 0.0) for ev in evs)
            parts.append(
                f"  Step {step_num}: {len(evs)} joints broke "
                f"(peak {_f(peak_force, 2)} N"
                + (f", {_pct(peak_force, jfl)} of limit)" if jfl and jfl < float('inf') else ")")
            )
            for i, ev in enumerate(evs[:2]):
                parts.append(
                    f"    [{i+1}] ({_f(ev.get('anchor_x'))}, {_f(ev.get('anchor_y'))}) "
                    f"{_f(ev.get('force_at_break'))} N"
                )
            if len(evs) > 2:
                parts.append(f"    ... and {len(evs) - 2} more at this step")
    remaining = len(cascade_events) - max_show
    if remaining > 0:
        parts.append(f"  ... {remaining} more step(s) with breaks (omitted).")
    parts.append(f"Total: {total_failures} joint break events")
    return parts

def _format_spatial_diagnostics(metrics: Dict[str, Any]) -> List[str]:
    parts: List[str] = []
    parts.append("── Spatial Diagnostics ──")
    arena_keys = ("arena_x_min", "arena_x_max", "arena_y_min", "arena_y_max")
    has_arena = all(k in metrics for k in arena_keys)
    body_keys = ("body_x_min", "body_x_max", "body_y_min", "body_y_max")
    has_body = all(k in metrics and metrics[k] is not None for k in body_keys)
    if has_arena:
        ax0, ax1 = metrics["arena_x_min"], metrics["arena_x_max"]
        ay0, ay1 = metrics["arena_y_min"], metrics["arena_y_max"]
        parts.append(
            f"Arena: x ∈ [{_f(ax0, 1)}, {_f(ax1, 1)}]  "
            f"y ∈ [{_f(ay0, 1)}, {_f(ay1, 1)}] m"
        )
    if has_body:
        bx0, bx1 = metrics["body_x_min"], metrics["body_x_max"]
        by0, by1 = metrics["body_y_min"], metrics["body_y_max"]
        parts.append(
            f"Body extent: x ∈ [{_f(bx0, 2)}, {_f(bx1, 2)}]  "
            f"y ∈ [{_f(by0, 2)}, {_f(by1, 2)}] m"
        )
    if has_arena and has_body:
        try:
            left = float(metrics["body_x_min"]) - float(metrics["arena_x_min"])
            right = float(metrics["arena_x_max"]) - float(metrics["body_x_max"])
            bottom = float(metrics["body_y_min"]) - float(metrics["arena_y_min"])
            top = float(metrics["arena_y_max"]) - float(metrics["body_y_max"])
            margin_parts = [
                f"L={_f(left, 2)}", f"R={_f(right, 2)}",
                f"B={_f(bottom, 2)}", f"T={_f(top, 2)}"
            ]
            tight_flags = []
            if _finite(left) is not None and left < 0.5:
                tight_flags.append(f"L={_f(left, 2)}")
            if _finite(right) is not None and right < 0.5:
                tight_flags.append(f"R={_f(right, 2)}")
            if _finite(bottom) is not None and bottom < 0.5:
                tight_flags.append(f"B={_f(bottom, 2)}")
            if _finite(top) is not None and top < 0.5:
                tight_flags.append(f"T={_f(top, 2)}")
            line = f"Arena margins: {'  '.join(margin_parts)} m"
            if tight_flags:
                line += f"  ⚠ tight: {', '.join(tight_flags)}"
            parts.append(line)
        except (TypeError, ValueError):
            pass
    bz_keys = ("build_zone_x_min", "build_zone_x_max",
               "build_zone_y_min", "build_zone_y_max")
    if all(k in metrics for k in bz_keys):
        bzx0, bzx1 = metrics["build_zone_x_min"], metrics["build_zone_x_max"]
        bzy0, bzy1 = metrics["build_zone_y_min"], metrics["build_zone_y_max"]
        bz_line = (
            f"Build zone: x ∈ [{_f(bzx0, 1)}, {_f(bzx1, 1)}]  "
            f"y ∈ [{_f(bzy0, 1)}, {_f(bzy1, 1)}] m"
        )
        bz_tightest = metrics.get("build_zone_tightest_margin")
        if bz_tightest is not None:
            bz_line += f"  tightest margin={_f(bz_tightest, 3)} m"
            if _finite(bz_tightest) is not None and bz_tightest < 0:
                bz_line += " ⚠ VIOLATED"
            elif _finite(bz_tightest) is not None and bz_tightest < 0.5:
                bz_line += " ⚠ near boundary"
        parts.append(bz_line)
        bz_body_margins = metrics.get("build_zone_body_margins", [])
        if bz_body_margins:
            violating = [bm for bm in bz_body_margins
                         if _finite(bm.get("tightest")) is not None
                         and _finite(bm.get("tightest")) < 0]
            if violating:
                parts.append(f"  Beams violating build zone ({len(violating)}):")
                for bm in violating[:5]:
                    bx, by = bm.get("pos", (None, None))
                    reasons = []
                    lm = _finite(bm.get("left_margin"))
                    rm = _finite(bm.get("right_margin"))
                    bm_b = _finite(bm.get("bottom_margin"))
                    tm = _finite(bm.get("top_margin"))
                    if lm is not None and lm < 0:
                        reasons.append(f"L={_f(lm, 2)}")
                    if rm is not None and rm < 0:
                        reasons.append(f"R={_f(rm, 2)}")
                    if bm_b is not None and bm_b < 0:
                        reasons.append(f"B={_f(bm_b, 2)}")
                    if tm is not None and tm < 0:
                        reasons.append(f"T={_f(tm, 2)}")
                    parts.append(
                        f"    ({_f(bx)}, {_f(by)}) — {' '.join(reasons)}"
                    )
                if len(violating) > 5:
                    parts.append(f"    ... and {len(violating) - 5} more")
    fz_min = metrics.get("forbidden_zone_min_margin")
    if fz_min is not None:
        fz_line = f"Forbidden-zone margin: {_f(fz_min, 3)} m"
        fz_all = metrics.get("forbidden_zone_all_margins", [])
        if fz_all:
            nearest = min(fz_all, key=lambda t: t[2] if len(t) > 2 else float('inf'))
            fz_line += f" (nearest body at ({_f(nearest[0])}, {_f(nearest[1])}))"
        if _finite(fz_min) is not None and fz_min < 0.3:
            fz_line += " ⚠ near forbidden zone"
        parts.append(fz_line)
    oz_min = metrics.get("obstacle_zone_min_margin")
    if oz_min is not None:
        oz_line = f"Obstacle-zone margin: {_f(oz_min, 3)} m"
        oz_all = metrics.get("obstacle_zone_all_margins", [])
        if oz_all:
            nearest = min(oz_all, key=lambda t: t[2] if len(t) > 2 else float('inf'))
            oz_line += f" (nearest body at ({_f(nearest[0])}, {_f(nearest[1])}))"
        if _finite(oz_min) is not None and oz_min < 0.3:
            oz_line += " ⚠ near obstacle"
        parts.append(oz_line)
    return parts

def _format_load_distribution(metrics: Dict[str, Any]) -> List[str]:
    parts: List[str] = []
    tracking = metrics.get("joint_tracking")
    jfl = _finite(metrics.get("joint_force_limit", float("inf")))
    parts.append("── Load & Stress Distribution ──")
    step_count = metrics.get("step_count", 0)
    fr = metrics.get("failure_reason", "")
    if step_count == 0 and "design constraint" in str(fr).lower():
        sm = _finite(metrics.get("structure_mass"))
        if sm is not None:
            parts.append(f"Mass: {_f(sm, 3)} kg (simulation did not run)")
        else:
            parts.append("(simulation did not run — design constraints failed)")
        return parts
    if not isinstance(tracking, dict):
        parts.append("No force tracking data available.")
        return parts
    history = tracking.get("joint_force_history", []) or []
    if history:
        non_zero = [h for h in history if h.get("max_force", 0.0) > 1e-9]
        zero_count = len(history) - len(non_zero)
        if non_zero:
            ranked = sorted(non_zero, key=lambda e: e.get("max_force", 0.0), reverse=True)
            parts.append(f"**Force history** ({len(history)} steps, {len(non_zero)} with force):")
            show = min(3, len(ranked))
            for i, rec in enumerate(ranked[:show]):
                s = rec.get("step", "?")
                mxf = rec.get("max_force", 0.0)
                jcnt = rec.get("joint_count_at_step", "?")
                if jfl and jfl < float('inf') and jfl > 0:
                    ratio = mxf / jfl
                    if ratio >= 0.8:
                        tier = "🔴 CRITICAL"
                    elif ratio >= 0.5:
                        tier = "🟡 ELEVATED"
                    else:
                        tier = "🟢 NOMINAL"
                    ratio_str = f" ({_f(100.0 * ratio, 1)}% of {_f(jfl, 0)} N limit)"
                else:
                    tier = ""
                    ratio_str = ""
                parts.append(
                    f"  Step {s}: peak {_f(mxf, 2)} N{ratio_str}  "
                    f"joints: {jcnt}  {tier}"
                )
            if zero_count > 0:
                parts.append(f"  ... {zero_count} more step(s) with zero force")
            elif len(ranked) > show:
                parts.append(f"  ... {len(ranked) - show} more step(s)")
        else:
            parts.append(f"**Force history**: {len(history)} steps, all zero force.")
    else:
        parts.append("**Force history**: no data recorded.")
    failures = tracking.get("joint_failure_events", []) or []
    if failures:
        ranked_f = sorted(failures, key=lambda e: e.get("force_at_break", 0.0), reverse=True)
        parts.append(f"\n**Top joint failures** ({len(ranked_f)} total):")
        show_f = min(5, len(ranked_f))
        for i, ev in enumerate(ranked_f[:show_f]):
            s = ev.get("step", "?")
            ax, ay = ev.get("anchor_x"), ev.get("anchor_y")
            fbr = ev.get("force_at_break", 0.0)
            parts.append(
                f"  [{i+1}] Step {s}: ({_f(ax)}, {_f(ay)}) "
                f"{_f(fbr, 2)} N"
                + (f" ({_pct(fbr, jfl)} of limit)"
                   if jfl and jfl < float('inf') else "")
            )
        if len(ranked_f) > show_f:
            parts.append(f"  ... {len(ranked_f) - show_f} more")
    prf = _finite(metrics.get("peak_reaction_force_ever"))
    if prf is not None and prf > 1e3:
        parts.append(f"\n**Peak reaction force**: {_f(prf, 2)} N ⚠ unusually high")
    return parts

def _format_energy_flow(metrics: Dict[str, Any]) -> List[str]:
    parts: List[str] = []
    ke_hist = metrics.get("kinetic_energy_history")
    parts.append("── Energy & Power Flow ──")
    if isinstance(ke_hist, list) and ke_hist:
        last_ke = ke_hist[-1].get("kinetic_energy", 0.0)
        first_ke = ke_hist[0].get("kinetic_energy", 0.0) if len(ke_hist) > 1 else 0.0
        parts.append(f"KE at terminal step: {_f(last_ke, 4)} J")
        if len(ke_hist) > 1:
            ke_delta = last_ke - first_ke
            n_steps = len(ke_hist) - 1 if len(ke_hist) > 1 else 1
            avg_dke = ke_delta / max(n_steps, 1)
            parts.append(f"  ΔKE = {_f(ke_delta, 4)} J over {n_steps} steps "
                         f"(avg {_f(avg_dke, 6)} J/step)")
            if avg_dke > 1e-6:
                parts.append("  ⚠ Net energy INJECTION")
            elif avg_dke < -1e-6:
                parts.append("  Net energy DECAY")
            else:
                parts.append("  Energy STABLE")
    else:
        parts.append("KE history: not available.")
    return parts

def _format_constraint_profile(metrics: Dict[str, Any]) -> List[str]:
    parts: List[str] = []
    parts.append("── Constraint Satisfaction ──")
    fr = metrics.get("failure_reason", "")
    design_failed = "design constraint" in str(fr).lower()
    build_parts: List[str] = []
    build_fails: List[str] = []
    build_warns: List[str] = []
    sm = _finite(metrics.get("structure_mass"))
    msm = _finite(metrics.get("max_structure_mass"))
    if sm is not None and msm is not None:
        mass_pct = 100.0 * sm / msm if msm > 0 else 999.0
        if sm > msm:
            build_fails.append(f"Mass {_f(mass_pct, 1)}%")
        elif mass_pct > 70.0:
            build_warns.append(f"Mass {_f(mass_pct, 1)}% ⚠ near limit")
        else:
            build_parts.append(f"Mass {_f(mass_pct, 1)}%")
    elif sm is not None:
        build_parts.append(f"Mass={_f(sm, 2)} kg")
    bc = metrics.get("beam_count")
    mbc = metrics.get("max_beam_count")
    if bc is not None and mbc is not None:
        try:
            bc_int = int(bc)
            mbc_int = int(mbc)
            beam_pct = 100.0 * bc_int / mbc_int if mbc_int > 0 else 999.0
            if bc_int > mbc_int:
                build_fails.append(f"Beams {_f(beam_pct, 1)}%")
            elif beam_pct > 70.0:
                build_warns.append(f"Beams {_f(beam_pct, 1)}% ⚠ near limit")
            else:
                build_parts.append(f"Beams {_f(beam_pct, 1)}%")
        except (ValueError, TypeError):
            build_parts.append(f"Beams={bc}/{mbc}")
    bz_tightest = metrics.get("build_zone_tightest_margin")
    if bz_tightest is not None:
        if bz_tightest < 0:
            build_fails.append("Build zone")
        elif bz_tightest < 0.5:
            build_warns.append("Build zone ⚠ near boundary")
        else:
            build_parts.append("Build zone")
    elif design_failed:
        build_fails.append("Build zone")
    if build_fails or build_warns:
        parts.append("Build-time: " + " | ".join(
            [f"❌ {f}" for f in build_fails] +
            [f"✅ {w}" for w in build_warns] +
            [f"✅ {p}" for p in build_parts]
        ))
    elif build_parts:
        parts.append("Build-time: ✅ " + ", ".join(build_parts))
    else:
        parts.append("Build-time: ✅ all passed")
    if design_failed and metrics.get("step_count", 0) == 0:
        parts.append("Runtime: (not reached — simulation did not start)")
        return parts
    runtime_parts: List[str] = []
    runtime_fails: List[str] = []
    oob = metrics.get("out_of_bounds", False)
    if oob:
        runtime_fails.append("Arena containment")
    else:
        runtime_parts.append("Arena")
    sb = metrics.get("structure_broken", False)
    if sb:
        jc = metrics.get("joint_count")
        ijc = metrics.get("initial_joint_count")
        broken = int(ijc) - int(jc) if ijc is not None and jc is not None else "?"
        runtime_fails.append(f"Integrity ({jc}/{ijc} joints, {broken} broken)")
    else:
        runtime_parts.append("Integrity")
    fzv = metrics.get("forbidden_zone_violation", False)
    if fzv:
        runtime_fails.append("Forbidden zone")
    else:
        fz_m = metrics.get("forbidden_zone_min_margin")
        if fz_m is not None and _finite(fz_m) is not None and fz_m < 0.3:
            runtime_parts.append(f"Forbidden ⚠ margin {_f(fz_m, 3)} m")
        else:
            runtime_parts.append("Forbidden")
    oo = metrics.get("obstacle_overlap", False)
    if oo:
        runtime_fails.append("Obstacle")
    else:
        oz_m = metrics.get("obstacle_zone_min_margin")
        if oz_m is not None and _finite(oz_m) is not None and oz_m < 0.3:
            runtime_parts.append(f"Obstacle ⚠ margin {_f(oz_m, 3)} m")
        else:
            runtime_parts.append("Obstacle")
    if runtime_fails:
        parts.append("Runtime: " + " | ".join(
            [f"❌ {f}" for f in runtime_fails] +
            [f"✅ {p}" for p in runtime_parts]
        ))
    else:
        parts.append("Runtime: ✅ " + ", ".join(runtime_parts))
    return parts

def _format_numerical_health(metrics: Dict[str, Any]) -> List[str]:
    parts: List[str] = []
    parts.append("── Numerical Health ──")
    warnings: List[str] = []
    bad_fields: List[str] = []
    for k in ("step_count", "structure_mass", "joint_count", "beam_count",
              "body_count", "peak_body_velocity", "peak_reaction_force_ever",
              "body_x_min", "body_x_max", "body_y_min", "body_y_max"):
        v = metrics.get(k)
        if v is not None:
            try:
                fv = float(v)
                if not math.isfinite(fv):
                    bad_fields.append(f"{k}={fv}")
            except (TypeError, ValueError):
                pass
    prf = _finite(metrics.get("peak_reaction_force_ever"))
    if prf is not None:
        if prf > 1e5:
            warnings.append(
                f"⚠ SOLVER DIVERGENCE: peak reaction force {_f(prf, 1)} N — "
                f"physically implausible, numerical instability."
            )
        elif prf > 1e4:
            warnings.append(
                f"⚠ Unusually high forces: peak reaction force {_f(prf, 1)} N — "
                f"may indicate near-divergence."
            )
    pv = _finite(metrics.get("peak_body_velocity"))
    if pv is not None:
        if pv > 100.0:
            warnings.append(
                f"⚠ Extreme velocity: peak {_f(pv, 1)} m/s — unconstrained bodies or numerical blowup."
            )
        elif pv > 50.0:
            warnings.append(
                f"⚠ High velocity: peak {_f(pv, 1)} m/s — possible unconstrained drift."
            )
    gv = metrics.get("gravity_current")
    if gv and isinstance(gv, (list, tuple)) and len(gv) >= 2:
        try:
            if not math.isfinite(float(gv[0])) or not math.isfinite(float(gv[1])):
                warnings.append("⚠ Non-finite gravity detected.")
        except (TypeError, ValueError):
            pass
    tracking = metrics.get("joint_tracking")
    if isinstance(tracking, dict):
        failures = tracking.get("joint_failure_events", []) or []
        nan_failures = 0
        for ev in failures:
            fb = ev.get("force_at_break", 0.0)
            try:
                if not math.isfinite(float(fb)):
                    nan_failures += 1
            except (TypeError, ValueError):
                nan_failures += 1
        if nan_failures > 0:
            warnings.append(f"⚠ {nan_failures} joint failure(s) with non-finite force_at_break.")
        history = tracking.get("joint_force_history", []) or []
        for rec in history:
            try:
                if not math.isfinite(float(rec.get("max_force", 0.0))):
                    warnings.append(
                        f"⚠ Non-finite max_force at step {rec.get('step', '?')}"
                    )
                    break
            except (TypeError, ValueError):
                pass
    if warnings:
        parts.append("**Warnings**:")
        for w in warnings:
            parts.append(f"  {w}")
        if not bad_fields:
            parts.append("Key scalars: all finite.")
    elif bad_fields:
        parts.append(f"⚠ Non-finite values: {', '.join(bad_fields)}")
    else:
        parts.append("✅ All metrics finite.")
        if pv is not None:
            parts.append(f"Peak velocity: {_f(pv, 2)} m/s ✅")
    return parts

def format_task_metrics(metrics: Dict[str, Any]) -> List[str]:
    if not metrics:
        return ["**Metrics**: (empty)"]
    parts: List[str] = []
    success = metrics.get("success", False)
    failed = metrics.get("failed", False)
    fr = metrics.get("failure_reason")
    step = metrics.get("step_count", "?")
    pp = metrics.get("progress_pct")
    parts.append(f"**Outcome**: {'SUCCESS' if success else 'FAILED' if failed else 'INCOMPLETE'}")
    if fr:
        parts.append(f"**Failure reason**: {fr}")
    parts.append(f"**Simulation step**: {step}"
                 + (f"  ({_f(pp, 1)}% of rollout)" if pp is not None else ""))
    sm = _finite(metrics.get("structure_mass"))
    msm = _finite(metrics.get("max_structure_mass"))
    bc = metrics.get("beam_count")
    mbc = metrics.get("max_beam_count")
    jc = metrics.get("joint_count")
    ijc = metrics.get("initial_joint_count")
    if sm is not None:
        line = f"**Mass**: {_f(sm, 3)} kg"
        if msm is not None:
            line += f" / {_f(msm, 1)} kg budget ({_f(100.0 * sm / msm if msm > 0 else 999, 1)}%)"
        parts.append(line)
    if bc is not None:
        line = f"**Beams**: {bc}"
        if mbc is not None:
            line += f" / {mbc} max"
        parts.append(line)
    if jc is not None:
        line = f"**Joints**: {jc}"
        if ijc is not None:
            try:
                line += f" / {int(ijc)} initial ({int(ijc) - int(jc)} broken)"
            except (TypeError, ValueError):
                pass
        parts.append(line)
    jfl = _finite(metrics.get("joint_force_limit", float("inf")))
    if jfl and jfl < float('inf'):
        parts.append(f"**Joint force limit**: {_f(jfl, 0)} N (finite — joints break above this)")
    elif jfl is not None:
        parts.append("**Joint force limit**: ∞ (joints do not break)")
    has_energy_data = bool(metrics.get("kinetic_energy_history"))
    parts.append("\n" + "─" * 52)
    temporal_parts = _format_temporal_chronology(metrics)
    if temporal_parts:
        parts.extend(temporal_parts)
        parts.append("")
    parts.extend(_format_spatial_diagnostics(metrics))
    parts.append("")
    load_parts = _format_load_distribution(metrics)
    if load_parts:
        parts.extend(load_parts)
        parts.append("")
    if has_energy_data:
        parts.extend(_format_energy_flow(metrics))
        parts.append("")
    parts.extend(_format_constraint_profile(metrics))
    parts.append("")
    parts.extend(_format_numerical_health(metrics))
    return parts
