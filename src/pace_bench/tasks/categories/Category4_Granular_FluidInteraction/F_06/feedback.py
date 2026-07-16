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

def _section_numerical_health(metrics: Dict[str, Any]) -> List[str]:
    numeric_keys = [
        "delivery_ratio", "delivery_ratio_percent",
        "structure_mass", "max_structure_mass",
        "particle_mean_x", "particle_mean_y", "particle_max_x",
        "closest_particle_distance_to_target",
    ]
    bad = []
    for k in numeric_keys:
        v = metrics.get(k)
        if v is None:
            continue
        try:
            fv = float(v)
            if not math.isfinite(fv):
                bad.append(f"{k}={fv}")
        except (TypeError, ValueError):
            pass
    if bad:
        return [f"### 0. Numerical Health — {len(bad)} non-finite value(s): " + ", ".join(bad)]
    return []

def _section_constraint_profile(metrics: Dict[str, Any]) -> List[str]:
    parts = ["### 1. Constraints"]
    viols = metrics.get("constraint_violations")
    if isinstance(viols, list) and viols:
        for v in viols:
            parts.append(f"- FAIL: {v}")
        parts.append("- Agent rejected before simulation.")
        return parts
    fail_near: List[str] = []
    pass_tags: List[str] = []
    delivery_pct = metrics.get("delivery_ratio_percent")
    target_pct = metrics.get("min_delivery_ratio_percent")
    if delivery_pct is not None and target_pct is not None:
        try:
            dp = float(delivery_pct)
            tp = float(target_pct)
            if math.isfinite(dp) and math.isfinite(tp) and tp > 0:
                margin = dp - tp
                if dp < tp:
                    fail_near.append(f"- Delivery: FAIL — {dp:.1f}% / {tp:.1f}% (gap: {abs(margin):.1f}%)")
                elif dp < tp * 1.1:
                    fail_near.append(f"- Delivery: PASS [NEAR] — {dp:.1f}% / {tp:.1f}% (margin: {margin:+.1f}%)")
                else:
                    pass_tags.append("delivery")
        except (TypeError, ValueError):
            pass
    mass = metrics.get("structure_mass")
    max_mass = metrics.get("max_structure_mass")
    mass_ok = False
    if mass is not None and max_mass is not None:
        try:
            m = float(mass)
            mm = float(max_mass)
            if math.isfinite(m) and math.isfinite(mm) and mm > 0:
                pct = m / mm * 100.0
                if m > mm:
                    fail_near.append(f"- Mass: FAIL — {m:.1f} kg / {mm:.1f} kg (over by {m - mm:.1f} kg)")
                elif pct > 80.0:
                    fail_near.append(f"- Mass: PASS [NEAR] — {m:.1f} kg / {mm:.1f} kg ({pct:.0f}%)")
                else:
                    mass_ok = True
        except (TypeError, ValueError):
            pass
    if mass_ok:
        pass_tags.append("mass")
    if "structure_broken" in metrics:
        if metrics["structure_broken"]:
            fail_near.append("- Structure: FAIL — joints lost during simulation")
    bx_min = metrics.get("build_zone_x_min")
    bx_max = metrics.get("build_zone_x_max")
    by_min = metrics.get("build_zone_y_min")
    by_max = metrics.get("build_zone_y_max")
    if bx_min is None or bx_max is None:
        cinfo = metrics.get("constraint_info", {}) or {}
        bx_min = cinfo.get("build_zone_x_min")
        bx_max = cinfo.get("build_zone_x_max")
        by_min = cinfo.get("build_zone_y_min")
        by_max = cinfo.get("build_zone_y_max")
    zone_ref = ""
    if bx_min is not None and bx_max is not None:
        zone_ref = f"Build zone: x=[{_f(bx_min, 1)},{_f(bx_max, 1)}] y=[{_f(by_min, 1)},{_f(by_max, 1)}]"
    if fail_near:
        parts.extend(fail_near)
    if pass_tags:
        parts.append("- PASS: " + " | ".join(pass_tags))
    if zone_ref:
        parts.append(f"- {zone_ref}")
    return parts

def _section_spatial_diagnostics(metrics: Dict[str, Any]) -> List[str]:
    parts = ["\n### 2. Spatial"]
    initial = metrics.get("initial_particle_count", 0)
    active = metrics.get("particle_active_count")
    if initial is not None and active is not None:
        try:
            ai = int(active)
            ri = int(initial)
            lost = ri - ai
            parts.append(f"- Particles: {ai}/{ri} active, {lost} lost")
        except (TypeError, ValueError):
            pass
    mean_x = metrics.get("particle_mean_x")
    mean_y = metrics.get("particle_mean_y")
    target_x_min = metrics.get("target_x_min")
    target_x_max = metrics.get("target_x_max")
    if mean_x is not None:
        try:
            mx = float(mean_x)
            if math.isfinite(mx):
                tmn = float(target_x_min) if target_x_min is not None else None
                tmx = float(target_x_max) if target_x_max is not None else None
                if tmn is not None and tmx is not None:
                    if mx < tmn:
                        parts.append(f"- Centroid: ({_f(mean_x)},{_f(mean_y)}) m — {tmn - mx:.1f} m behind target")
                    elif mx > tmx:
                        parts.append(f"- Centroid: ({_f(mean_x)},{_f(mean_y)}) m — {mx - tmx:.1f} m past target")
                    else:
                        parts.append(f"- Centroid: ({_f(mean_x)},{_f(mean_y)}) m — inside target x-range")
                else:
                    parts.append(f"- Centroid: ({_f(mean_x)},{_f(mean_y)}) m")
        except (TypeError, ValueError):
            pass
    max_x = metrics.get("particle_max_x")
    if max_x is not None:
        try:
            fx = float(max_x)
            if math.isfinite(fx) and target_x_min is not None:
                tmn = float(target_x_min)
                if fx < tmn:
                    parts.append(f"- Rightmost: x={fx:.1f} m ({tmn - fx:.1f} m short)")
                else:
                    parts.append(f"- Rightmost: x={fx:.1f} m (past target x={tmn:.1f})")
        except (TypeError, ValueError):
            pass
    closest_dist = metrics.get("closest_particle_distance_to_target")
    closest_pos = metrics.get("closest_particle_position")
    if closest_dist is not None:
        try:
            cd = float(closest_dist)
            if math.isfinite(cd):
                if cd <= 0:
                    parts.append("- Closest particle: INSIDE target zone")
                else:
                    pos_str = ""
                    if closest_pos and isinstance(closest_pos, (list, tuple)) and len(closest_pos) >= 2:
                        pos_str = f" at ({_f(closest_pos[0])},{_f(closest_pos[1])})"
                    parts.append(f"- Closest particle: {cd:.1f} m to target{pos_str}")
        except (TypeError, ValueError):
            pass
    in_target = metrics.get("particles_in_target")
    in_source = metrics.get("particles_in_source")
    in_build = metrics.get("particles_in_build_zone")
    tgt_y_min = metrics.get("target_y_min")
    tgt_y_max = metrics.get("target_y_max")
    zone_parts = []
    if in_source is not None:
        zone_parts.append(f"source={in_source}")
    if in_build is not None:
        zone_parts.append(f"build={in_build}")
    if in_target is not None:
        zone_parts.append(f"target={in_target}")
    try:
        tgt_str = (f"Target zone: x=[{float(target_x_min):.1f},{float(target_x_max):.1f}] "
                   f"y=[{float(tgt_y_min):.1f},{float(tgt_y_max):.1f}]")
    except (TypeError, ValueError):
        tgt_str = f"Target zone: x=[{target_x_min},{target_x_max}] y=[{tgt_y_min},{tgt_y_max}]"
    if zone_parts:
        parts.append(f"- Distribution: {', '.join(zone_parts)} | {tgt_str}")
    else:
        parts.append(f"- {tgt_str}")
    return parts

def _section_hazard_losses(metrics: Dict[str, Any]) -> List[str]:
    parts = ["\n### 3. Hazards"]
    hazard_losses = metrics.get("hazard_losses", {}) or {}
    initial = metrics.get("initial_particle_count", 0)
    if not hazard_losses:
        parts.append("- No hazard data available.")
        return parts
    total_lost = (hazard_losses.get("pit1", 0) + hazard_losses.get("pit2", 0) +
                  hazard_losses.get("pit3", 0) + hazard_losses.get("out_of_bounds", 0) +
                  hazard_losses.get("floor", 0))
    if total_lost == 0:
        parts.append("- No particles lost to hazards (pits, floor, OOB).")
    else:
        parts.append(f"- Lost: {total_lost}/{initial} particles")
        for pit_name, pit_label in [
            ("pit1", "Pit 1 (x=13.5-15.5)"),
            ("pit2", "Pit 2 (x=16.0-17.5)"),
            ("pit3", "Pit 3 (x=11.0-12.5)"),
        ]:
            count = hazard_losses.get(pit_name, 0)
            if count > 0:
                parts.append(f"  - {pit_label}: {count}")
        oob = hazard_losses.get("out_of_bounds", 0)
        if oob > 0:
            parts.append(f"  - Out of bounds: {oob}")
        floor = hazard_losses.get("floor", 0)
        if floor > 0:
            parts.append(f"  - Fell below floor: {floor}")
    hw = hazard_losses.get("headwind", 0)
    gw = hazard_losses.get("gravwell", 0)
    if hw > 0:
        parts.append(f"- Headwind (y>3.0m): {hw} particle-steps affected")
    if gw > 0:
        parts.append(f"- Gravity well (x=10-14, y=1.5-3.5): {gw} particle-steps affected")
    elif "gravwell" in hazard_losses and hw == 0:
        pass
    return parts

def _section_force_utilization(metrics: Dict[str, Any]) -> List[str]:
    parts = ["\n### 4. Force Utilization"]
    budget = metrics.get("force_budget")
    peak_pct = metrics.get("force_budget_peak_utilization_pct")
    last_pct = metrics.get("force_budget_last_utilization_pct")
    if budget is None:
        parts.append("- No force budget data available.")
        return parts
    try:
        b = float(budget)
        if math.isfinite(b) and b > 0:
            line = f"- Budget: {b:.0f} N/step"
            if peak_pct is not None:
                try:
                    pp = float(peak_pct)
                    if math.isfinite(pp):
                        tier = ""
                        if pp > 90.0:
                            tier = " [SATURATED]"
                        elif pp > 70.0:
                            tier = " [high]"
                        elif pp < 30.0:
                            tier = " [underused]"
                        line += f" | peak: {pp:.0f}%{tier}"
                except (TypeError, ValueError):
                    pass
            if last_pct is not None:
                try:
                    lp = float(last_pct)
                    if math.isfinite(lp):
                        line += f" | last: {lp:.0f}%"
                except (TypeError, ValueError):
                    pass
            parts.append(line)
    except (TypeError, ValueError):
        pass
    zone_stats = metrics.get("zone_velocity_stats", {}) or {}
    if zone_stats:
        active_zones = []
        zone_order = [
            "source", "build_pre_pit3", "pit3_zone", "build_mid",
            "pit1_zone", "pit2_zone", "build_post_pit2", "target",
            "headwind", "gravwell",
        ]
        for zone_name in zone_order:
            zs = zone_stats.get(zone_name)
            if zs is None:
                continue
            count = zs.get("count", 0)
            if count == 0:
                continue
            mvx = zs.get("mean_vx", 0.0)
            mvy = zs.get("mean_vy", 0.0)
            try:
                if abs(float(mvx)) > 0.01 or abs(float(mvy)) > 0.01:
                    active_zones.append(f"{zone_name}: vx={_f(mvx)} vy={_f(mvy)} ({count}p)")
            except (TypeError, ValueError):
                pass
        if active_zones:
            parts.append("- Zone velocities (non-trivial):")
            for z in active_zones:
                parts.append(f"  - {z}")
    return parts

def _section_temporal_chronology(metrics: Dict[str, Any]) -> List[str]:
    parts = ["\n### 5. Timeline"]
    step_count = metrics.get("step_count")
    max_steps = metrics.get("max_steps")
    if step_count is not None:
        if max_steps is not None:
            try:
                s = int(step_count)
                ms = int(max_steps)
                if ms > 0:
                    parts.append(f"- Terminated at step {s}/{ms} ({s / ms * 100:.0f}%)")
                else:
                    parts.append(f"- Terminated at step {s}")
            except (TypeError, ValueError):
                parts.append(f"- Terminated at step {step_count}")
        else:
            parts.append(f"- Terminated at step {step_count}")
    snapshots = metrics.get("granular_snapshots")
    if isinstance(snapshots, list) and snapshots:
        prev = None
        changes = []
        for snap in snapshots:
            if not isinstance(snap, dict):
                continue
            snap_metrics = snap.get("metrics", {}) or {}
            step = snap.get("step_count", "?")
            delivery = snap_metrics.get("delivery_ratio_percent")
            if delivery is not None:
                try:
                    d = float(delivery)
                    if prev is None or abs(d - prev) > 0.5:
                        in_target = snap_metrics.get("particles_in_target")
                        total_p = snap_metrics.get("initial_particle_count")
                        line = f"  - Step {step}: {d:.0f}%"
                        if in_target is not None and total_p is not None:
                            line += f" ({in_target}/{total_p} in target)"
                        changes.append(line)
                        prev = d
                except (TypeError, ValueError):
                    pass
        if changes:
            parts.append("- Delivery trajectory:")
            parts.extend(changes)
    return parts

def format_task_metrics(metrics: Dict[str, Any]) -> List[str]:
    if not metrics:
        return ["**No evaluation metrics available.**"]
    viols = metrics.get("constraint_violations")
    if isinstance(viols, list) and viols:
        parts = ["### Design Constraint Violations (Build Phase)"]
        for v in viols:
            parts.append(f"- {v}")
        if "failure_reason" in metrics:
            parts.append(f"- Outcome: {metrics['failure_reason']}")
        return parts
    parts: List[str] = []
    parts.extend(_section_numerical_health(metrics))
    parts.extend(_section_constraint_profile(metrics))
    parts.extend(_section_spatial_diagnostics(metrics))
    parts.extend(_section_hazard_losses(metrics))
    parts.extend(_section_force_utilization(metrics))
    parts.extend(_section_temporal_chronology(metrics))
    return parts

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
    delivery_pct = metrics.get("delivery_ratio_percent")
    target_pct = metrics.get("min_delivery_ratio_percent")
    if delivery_pct is not None and target_pct is not None:
        try:
            dp = float(delivery_pct)
            tp = float(target_pct)
            if dp < tp:
                shortfall = tp - dp
                suggestions.append(
                    f"- Delivery efficiency is {shortfall:.1f}% below the {tp:.1f}% threshold. "
                    f"Review the hazard loss accounting (Section 3) to identify where particles are being lost."
                )
        except (TypeError, ValueError):
            pass
    if metrics.get("structure_broken"):
        suggestions.append("- Structure integrity was lost during simulation. Inspect joint anchoring.")
    peak_pct = metrics.get("force_budget_peak_utilization_pct")
    if peak_pct is not None:
        try:
            pp = float(peak_pct)
            if pp > 100.0:
                suggestions.append(
                    f"- Force budget peak utilization ({pp:.1f}%) exceeded 100%. "
                    f"Some force commands were truncated."
                )
        except (TypeError, ValueError):
            pass
    if not suggestions:
        suggestions.append("- Review the diagnostic sections above for detailed forensic data.")
    return suggestions
