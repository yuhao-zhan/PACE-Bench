from __future__ import annotations

import math

from typing import Any, Dict, List, Optional, Tuple

def _f(v: Any) -> Optional[float]:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    return None

def _fmt(v: Any, decimals: int = 3) -> str:
    fv = _f(v)
    if fv is None:
        return str(v)
    if not math.isfinite(fv):
        return str(v)
    return f"{fv:.{decimals}f}"

def _fmt_pct(numer: Any, denom: Any) -> str:
    n = _f(numer)
    d = _f(denom)
    if n is None or d is None or d == 0.0:
        return "—"
    if not math.isfinite(n) or not math.isfinite(d):
        return "—"
    return f"{n / d * 100.0:.1f}%"

_NUMERIC_FIELDS = (
    "craft_x", "craft_y", "heat", "overheat_limit", "heat_remaining",
    "velocity_x", "velocity_y", "speed", "distance_to_target",
    "progress_x", "dist_traveled_x", "step_count",
    "gate1_x_margin_lo", "gate1_x_margin_hi", "gate1_y_margin_lo", "gate1_y_margin_hi",
    "gate2_x_margin_lo", "gate2_x_margin_hi", "gate2_y_margin_lo", "gate2_y_margin_hi",
    "ground_proximity", "heat_utilization_pct", "average_heat_rate",
    "step_budget_used_pct", "step_budget_remaining", "craft_mass",

)

def _nonfinite_fields(metrics: Dict[str, Any]) -> List[str]:
    bad: List[str] = []
    for key in _NUMERIC_FIELDS:
        if key not in metrics:
            continue
        v = _f(metrics.get(key))
        if v is not None and (math.isnan(v) or math.isinf(v)):
            bad.append(key)
    return bad

def _extreme_value_note(metrics: Dict[str, Any]) -> Optional[str]:
    flags: List[str] = []
    tx_max = _f(metrics.get("target_x_max"))
    arena_scale_x = tx_max * 3.0 if tx_max is not None and math.isfinite(tx_max) and tx_max > 0 else 100.0
    speed = _f(metrics.get("speed"))
    if speed is not None and math.isfinite(speed) and speed > arena_scale_x:
        flags.append(f"speed={speed:.1f} m/s > arena scale {arena_scale_x:.0f}")
    vx = _f(metrics.get("velocity_x"))
    vy = _f(metrics.get("velocity_y"))
    if vx is not None and math.isfinite(vx) and abs(vx) > arena_scale_x:
        flags.append(f"vx={vx:.1f} > arena scale")
    if vy is not None and math.isfinite(vy) and abs(vy) > arena_scale_x:
        flags.append(f"vy={vy:.1f} > arena scale")
    cx = _f(metrics.get("craft_x"))
    cy = _f(metrics.get("craft_y"))
    if cx is not None and math.isfinite(cx) and abs(cx) > arena_scale_x:
        flags.append(f"x={cx:.1f} > arena scale")
    if cy is not None and math.isfinite(cy) and abs(cy) > arena_scale_x:
        flags.append(f"y={cy:.1f} > arena scale")
    override_limit = _f(metrics.get("overheat_limit"))
    if override_limit is not None and math.isfinite(override_limit) and override_limit > 0:
        heat = _f(metrics.get("heat"))
        if heat is not None and math.isfinite(heat) and heat > override_limit * 2.0:
            flags.append(f"heat={heat:.1f} > 2× limit ({override_limit:.1f})")
    if not flags:
        return None
    return "Extreme values: " + " | ".join(flags)

def _status_line(metrics: Dict[str, Any]) -> str:
    parts: List[str] = []
    sc = _f(metrics.get("step_count"))
    ms = _f(metrics.get("step_budget_remaining"))
    sbu = _f(metrics.get("step_budget_used_pct"))
    if sc is not None and math.isfinite(sc):
        step_part = f"step {int(sc)}"
        if ms is not None and math.isfinite(ms):
            step_part += f" ({int(ms)} remaining)"
        elif sbu is not None and math.isfinite(sbu):
            step_part += f" ({sbu:.0f}% used)"
        parts.append(step_part)
    cx = _f(metrics.get("craft_x"))
    cy = _f(metrics.get("craft_y"))
    if cx is not None and cy is not None and math.isfinite(cx) and math.isfinite(cy):
        parts.append(f"x={cx:.3f} y={cy:.3f}")
    speed = _f(metrics.get("speed"))
    if speed is not None and math.isfinite(speed):
        parts.append(f"|v|={speed:.3f} m/s")
    heat = _f(metrics.get("heat"))
    limit = _f(metrics.get("overheat_limit"))
    if heat is not None and limit is not None and math.isfinite(heat) and math.isfinite(limit) and limit > 0:
        pct = heat / limit * 100.0
        parts.append(f"heat {heat:.1f}/{limit:.1f} N·s ({pct:.1f}%)")
    success = bool(metrics.get("success", False))
    failed = bool(metrics.get("failed", False))
    if success:
        parts.append("✅ REACHED TARGET")
    elif failed:
        fr = metrics.get("failure_reason")
        if fr:
            parts.append(f"❌ {fr}")
        else:
            parts.append("❌ FAILED")
    else:
        parts.append("⚠️ IN PROGRESS")
    return " | ".join(parts)

def _target_proximity(metrics: Dict[str, Any]) -> List[str]:
    lines: List[str] = []
    cx = _f(metrics.get("craft_x"))
    cy = _f(metrics.get("craft_y"))
    x0 = _f(metrics.get("target_x_min"))
    x1 = _f(metrics.get("target_x_max"))
    y0 = _f(metrics.get("target_y_min"))
    y1 = _f(metrics.get("target_y_max"))
    if None in (cx, cy, x0, x1, y0, y1):
        return lines
    if x1 is not None and x0 is not None and x1 < x0:
        x0, x1 = x1, x0
    if y1 is not None and y0 is not None and y1 < y0:
        y0, y1 = y1, y0
    inside = (x0 <= cx <= x1) and (y0 <= cy <= y1)
    if inside:
        inset = min(cx - x0, x1 - cx, cy - y0, y1 - cy)
        lines.append(f"Target zone [{x0:.1f}≤x≤{x1:.1f}, {y0:.1f}≤y≤{y1:.1f}]: INSIDE (inset {inset:.3f} m)")
    else:
        gaps: List[str] = []
        if cx < x0:
            gaps.append(f"Δx={x0 - cx:.1f} m to x≥{x0:.1f}")
        elif cx > x1:
            gaps.append(f"Δx={cx - x1:.1f} m past x≤{x1:.1f}")
        if cy < y0:
            gaps.append(f"Δy={y0 - cy:.1f} m to y≥{y0:.1f}")
        elif cy > y1:
            gaps.append(f"Δy={cy - y1:.1f} m past y≤{y1:.1f}")
        dt = _f(metrics.get("distance_to_target"))
        dist_str = f" (centroid dist {dt:.1f} m)" if dt is not None and math.isfinite(dt) else ""
        lines.append(f"Target zone [{x0:.1f}≤x≤{x1:.1f}, {y0:.1f}≤y≤{y1:.1f}]: OUTSIDE — {'; '.join(gaps)}{dist_str}")
    px = _f(metrics.get("progress_x"))
    if px is not None and math.isfinite(px) and not inside:
        lines.append(f"Horizontal progress: {px:.1f}% of required distance")
    return lines

def _gate_clearance_compact(metrics: Dict[str, Any]) -> List[str]:
    lines: List[str] = []
    for gk, glabel in [("gate1", "Gate 1"), ("gate2", "Gate 2")]:
        x_lo = _f(metrics.get(f"{gk}_x_margin_lo"))
        x_hi = _f(metrics.get(f"{gk}_x_margin_hi"))
        y_lo = _f(metrics.get(f"{gk}_y_margin_lo"))
        y_hi = _f(metrics.get(f"{gk}_y_margin_hi"))
        if None in (x_lo, x_hi, y_lo, y_hi):
            continue
        if not all(math.isfinite(v) for v in (x_lo, x_hi, y_lo, y_hi)):
            continue
        parts: List[str] = []
        if x_lo >= 0 and x_hi >= 0:
            parts.append(f"x ✓ (+{min(x_lo, x_hi):.1f}m)")
        else:
            if x_lo < 0:
                parts.append(f"x ✗ ({abs(x_lo):.1f}m short)")
            if x_hi < 0:
                parts.append(f"x ✗ ({abs(x_hi):.1f}m short)")
        if y_lo >= 0 and y_hi >= 0:
            parts.append(f"y ✓ (+{min(y_lo, y_hi):.1f}m)")
        else:
            if y_lo < 0:
                parts.append(f"y ✗ ({abs(y_lo):.1f}m below)")
            if y_hi < 0:
                parts.append(f"y ✗ ({abs(y_hi):.1f}m below)")
        all_ok = x_lo >= 0 and x_hi >= 0 and y_lo >= 0 and y_hi >= 0
        status = "CLEAR" if all_ok else "VIOLATED"
        lines.append(f"{glabel} [{status}]: " + " | ".join(parts))
    return lines

def _ground_status(metrics: Dict[str, Any]) -> Optional[str]:
    gp = _f(metrics.get("ground_proximity"))
    if gp is None or not math.isfinite(gp):
        return None
    if gp < 0.0:
        return f"Ground: {abs(gp):.3f} m BELOW surface ⚠"
    if gp < 0.25:
        return f"Ground: {gp:.3f} m (contact — ground friction active)"
    if gp < 0.6:
        return f"Ground: {gp:.3f} m (marginal)"
    return None

def _zone_status(metrics: Dict[str, Any]) -> str:
    zones: List[str] = []
    if metrics.get("craft_in_drain_zone"):
        zones.append("DRAIN (velocity damped)")
    if metrics.get("craft_in_slip_zone"):
        zones.append("SLIP (backward force)")
    if metrics.get("craft_in_wind_zone"):
        zones.append("WIND (oscillating vertical)")
    if metrics.get("craft_in_gate1_x"):
        zones.append("Gate 1 x-range")
    if metrics.get("craft_in_gate2_x"):
        zones.append("Gate 2 x-range")
    if not zones:
        return "Zones: free (none active)"
    return "Zones: " + " | ".join(zones)

def _constraint_summary_compact(metrics: Dict[str, Any]) -> List[str]:
    lines: List[str] = []
    pass_count = 0
    fail_entries: List[str] = []
    near_entries: List[str] = []
    overheated = bool(metrics.get("overheated", False))
    heat = _f(metrics.get("heat"))
    limit = _f(metrics.get("overheat_limit"))
    if overheated:
        fail_entries.append("Thermal: OVERHEATED")
    elif heat is not None and limit is not None and math.isfinite(heat) and math.isfinite(limit) and limit > 0:
        pct = heat / limit * 100.0
        if pct >= 50.0:
            near_entries.append(f"Thermal: {pct:.1f}% of {limit:.0f} N·s limit")
        else:
            pass_count += 1
    else:
        pass_count += 1
    if metrics.get("reached_target"):
        pass_count += 1
    else:
        fail_entries.append("Target reach: not reached")
    sbu = _f(metrics.get("step_budget_used_pct"))
    sbr = _f(metrics.get("step_budget_remaining"))
    if sbr is not None and math.isfinite(sbr) and sbr <= 0:
        fail_entries.append("Step budget: exhausted")
    elif sbu is not None and math.isfinite(sbu) and sbu >= 90.0:
        near_entries.append(f"Step budget: {sbu:.1f}% used")
    else:
        pass_count += 1
    g1_ok = _gate_all_clear(metrics, "gate1")
    if g1_ok:
        pass_count += 1
    else:
        fail_entries.append("Gate 1: clearance violated")
    g2_ok = _gate_all_clear(metrics, "gate2")
    if g2_ok:
        pass_count += 1
    else:
        fail_entries.append("Gate 2: clearance violated")
    gp = _f(metrics.get("ground_proximity"))
    if gp is not None and math.isfinite(gp):
        if gp < 0.0:
            fail_entries.append("Ground: terrain penetration")
        elif gp < 0.25:
            near_entries.append(f"Ground: {gp:.3f} m (contact)")
        else:
            pass_count += 1
    else:
        pass_count += 1
    total = pass_count + len(fail_entries) + len(near_entries)
    lines.append(f"Pass: {pass_count} | Fail: {len(fail_entries)} | Near-limit: {len(near_entries)} | Total: {total}")
    for e in fail_entries + near_entries:
        lines.append(f"  [{e.split(':')[0]}] {e.split(':', 1)[1].strip() if ':' in e else e}")
    return lines

def _gate_all_clear(metrics: Dict[str, Any], gate_key: str) -> bool:
    for ax in ("x", "y"):
        lo = _f(metrics.get(f"{gate_key}_{ax}_margin_lo"))
        hi = _f(metrics.get(f"{gate_key}_{ax}_margin_hi"))
        if lo is None or hi is None:
            continue
        if not math.isfinite(lo) or not math.isfinite(hi):
            continue
        if lo < 0.0 or hi < 0.0:
            return False
    return True

def format_task_metrics(metrics: Dict[str, Any]) -> List[str]:
    if not metrics:
        return ["**Metrics**: (empty — no evaluation data available)"]
    if "error" in metrics:
        return [f"**Evaluator error**: {metrics.get('error')!s}"]
    nf = _nonfinite_fields(metrics)
    critical_nf = [k for k in nf if k in ("craft_x", "craft_y", "heat", "overheat_limit", "speed")]
    if critical_nf:
        return [
            f"### Diagnostic Abort",
            f"Critical fields non-finite: {', '.join(critical_nf)}. "
            "All tracked non-finite keys: " + (", ".join(nf) if nf else "none") + ".",
        ]
    parts: List[str] = []
    parts.append("### Status")
    parts.append(_status_line(metrics))
    parts.append("")
    if nf:
        parts.append(f"⚠ Non-finite fields: {', '.join(f'`{k}`' for k in nf)}")
    else:
        extreme_note = _extreme_value_note(metrics)
        if extreme_note:
            parts.append(f"⚠ {extreme_note}")
        else:
            parts.append("Data health: OK (all finite, no extremes)")
    parts.append("")
    parts.append("### Target Proximity")
    parts.extend(_target_proximity(metrics))
    parts.append("")
    parts.append("### Gate Clearance")
    parts.extend(_gate_clearance_compact(metrics))
    gs = _ground_status(metrics)
    if gs:
        parts.append(gs)
    parts.append("")
    parts.append("### Zone Status")
    parts.append(_zone_status(metrics))
    parts.append("")
    parts.append("### Constraints")
    parts.extend(_constraint_summary_compact(metrics))
    parts.append("")
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
        suggestions.append(f"- Code execution error encountered: {error[:200]}")
        return suggestions
    if not metrics or "error" in metrics:
        return suggestions
    if success:
        return suggestions
    overheated = bool(metrics.get("overheated", False))
    reached = bool(metrics.get("reached_target", False))
    if overheated:
        heat = _f(metrics.get("heat"))
        limit = _f(metrics.get("overheat_limit"))
        if heat is not None and limit is not None and math.isfinite(heat) and math.isfinite(limit):
            pct = heat / limit * 100.0
            suggestions.append(
                f"- Overheat occurred at {pct:.1f}% of the {limit:.1f} N·s limit "
                f"(cumulative thrust-time: {heat:.1f} N·s). "
                f"The craft can no longer apply thrust after overheat."
            )
        else:
            suggestions.append("- Overheat occurred. Craft thrust system is permanently disabled.")
    sbu = _f(metrics.get("step_budget_used_pct"))
    sbr = _f(metrics.get("step_budget_remaining"))
    if not reached and not overheated and sbr is not None and math.isfinite(sbr) and sbr <= 0:
        suggestions.append(
            f"- Step budget exhausted ({sbu:.1f}% used). The craft ran out of time before reaching the target."
        )
    dt = _f(metrics.get("distance_to_target"))
    if not reached and dt is not None and math.isfinite(dt):
        suggestions.append(f"- At termination, craft was {dt:.3f} m from target zone centroid.")
    dx = _f(metrics.get("dist_traveled_x"))
    px = _f(metrics.get("progress_x"))
    if not reached and px is not None and math.isfinite(px):
        suggestions.append(f"- Horizontal progress was {px:.1f}% of the required distance.")
    in_drain = bool(metrics.get("craft_in_drain_zone", False))
    if in_drain:
        speed = _f(metrics.get("speed"))
        spd_str = f" with speed {speed:.3f} m/s" if speed is not None and math.isfinite(speed) else ""
        suggestions.append(
            f"- Craft was inside the drain zone{spd_str} at snapshot — "
            f"velocity is reduced each step while inside this zone."
        )
    in_slip = bool(metrics.get("craft_in_slip_zone", False))
    vx = _f(metrics.get("velocity_x"))
    if in_slip and vx is not None and math.isfinite(vx) and vx <= 0.0:
        suggestions.append(
            f"- Craft had zero or negative forward velocity ({vx:.3f} m/s) while inside slip zone — "
            f"a backward horizontal force is applied in this region."
        )
    gp = _f(metrics.get("ground_proximity"))
    if gp is not None and math.isfinite(gp) and gp < 0.0:
        suggestions.append(
            f"- Craft center was {abs(gp):.3f} m below ground surface — terrain penetration detected."
        )
    elif gp is not None and math.isfinite(gp) and gp < 0.5:
        suggestions.append(
            f"- Craft center was {gp:.3f} m above ground surface (craft half-height is ≈0.25 m) — "
            f"ground friction may be impeding motion."
        )
    dx_max = _f(metrics.get("target_x_min"))
    if dx_max is not None and math.isfinite(dx_max) and dx is not None and math.isfinite(dx):
        min_expected = (dx_max - 8.0) * 0.01
        if dx < min_expected and not reached:
            sc = _f(metrics.get("step_count"))
            steps_str = f" after {int(sc)} steps" if sc is not None and math.isfinite(sc) else ""
            suggestions.append(
                f"- Craft showed minimal horizontal displacement ({dx:.3f} m){steps_str} — "
                f"forward progress is below 1% of the required distance to target."
            )
    rate = _f(metrics.get("average_heat_rate"))
    limit = _f(metrics.get("overheat_limit"))
    if rate is not None and limit is not None and math.isfinite(rate) and math.isfinite(limit) and rate > 0 and limit > 0:
        steps_to_oh = limit / rate
        suggestions.append(
            f"- Average heat accumulation rate was {rate:.3f} N·s per step. "
            f"At this rate, overheat would occur at approximately step {steps_to_oh:.0f}."
        )
    return suggestions
