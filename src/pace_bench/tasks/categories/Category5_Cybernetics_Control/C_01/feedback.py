from __future__ import annotations

import math

from typing import Any, Dict, List

def _f(key: str, metrics: Dict[str, Any], default: float = 0.0) -> float:
    v = metrics.get(key)
    if v is None:
        return float("nan")
    try:
        fv = float(v)
        return fv if math.isfinite(fv) else float("nan")
    except (TypeError, ValueError):
        return float("nan")

def _ok(x: float) -> bool:
    return math.isfinite(x)

def _fmt(x: float, decimals: int = 3) -> str:
    if not _ok(x):
        return "—"
    return f"{x:.{decimals}f}"

def _pct(part: float, whole: float) -> float:
    if not _ok(part) or not _ok(whole) or whole == 0.0:
        return float("nan")
    return part / whole * 100.0

def _margin_label(ratio: float) -> str:
    if not _ok(ratio):
        return "unknown"
    if ratio >= 1.0:
        return "VIOLATED"
    if ratio >= 0.90:
        return "CRITICAL"
    if ratio >= 0.70:
        return "elevated"
    return "nominal"

def _section_numerical_health(metrics: Dict[str, Any]) -> List[str]:
    flags: List[str] = []
    for key, label in [
        ("pole_angle_deg", "pole angle (reported)"),
        ("pole_angle_true_deg", "pole angle (true)"),
        ("pole_angular_velocity", "pole angular velocity (reported)"),
        ("pole_angular_velocity_true", "pole angular velocity (true)"),
        ("cart_x", "cart position"),
        ("cart_velocity_x", "cart velocity"),
        ("applied_force", "applied force"),
        ("force_limit", "force limit"),
    ]:
        v = metrics.get(key)
        if v is None:
            flags.append(f"{label}: MISSING (None)")
            continue
        try:
            fv = float(v)
            if not math.isfinite(fv):
                flags.append(f"{label}: NON-FINITE ({v})")
        except (TypeError, ValueError):
            flags.append(f"{label}: UNPARSABLE ({v})")
    omega_true = _f("pole_angular_velocity_true", metrics)
    if _ok(omega_true) and abs(omega_true) > 100.0:
        flags.append(
            f"pole true angular velocity {omega_true:.2f} rad/s "
            f"({math.degrees(omega_true):.1f} deg/s) — extreme"
        )
    cart_v = _f("cart_velocity_x", metrics)
    if _ok(cart_v) and abs(cart_v) > 100.0:
        flags.append(f"cart velocity {cart_v:.2f} m/s — extreme")
    sc = _f("step_count", metrics)
    ms = _f("max_steps", metrics)
    if _ok(sc) and _ok(ms) and sc >= ms:
        flags.append(f"step budget exhausted ({int(sc)}/{int(ms)} steps)")
    if flags:
        return ["### Numerical Health"] + [f"- ⚠ {f}" for f in flags]
    return ["### Numerical Health\n- OK (no anomalies)"]

def _section_physics_summary(metrics: Dict[str, Any]) -> List[str]:
    parts: List[str] = ["### Environment Physics"]
    pole_mass = _f("pole_mass", metrics, 1.0)
    cart_mass = _f("cart_mass", metrics, 10.0)
    pole_len = _f("pole_length", metrics, 2.0)
    force_lim = _f("force_limit", metrics, 450.0)
    delay_a = _f("sensor_delay_angle_steps", metrics, 0)
    delay_w = _f("sensor_delay_omega_steps", metrics, 0)
    items: List[str] = []
    if _ok(cart_mass):
        items.append(f"**Cart mass**: {cart_mass:.2f} kg")
    if _ok(pole_mass):
        items.append(f"**Pole mass**: {pole_mass:.2f} kg")
    if _ok(pole_len):
        items.append(f"**Pole length**: {pole_len:.2f} m")
        if _ok(pole_mass):
            inertia = (1.0 / 3.0) * pole_mass * pole_len * pole_len
            items.append(f"**Pole inertia (pivot)**: {inertia:.4f} kg·m²")
    if _ok(force_lim):
        items.append(f"**Force limit**: {force_lim:.4f} N")
    if _ok(delay_a) or _ok(delay_w):
        items.append(
            f"**Sensor delay**: angle={int(delay_a) if _ok(delay_a) else '—'} steps, "
            f"omega={int(delay_w) if _ok(delay_w) else '—'} steps"
        )
    for item in items:
        parts.append(f"- {item}")
    return parts

def _section_state_snapshot(metrics: Dict[str, Any], *, is_first: bool = True) -> List[str]:
    parts: List[str] = ["### State Snapshot"]
    ang_true = _f("pole_angle_true_deg", metrics)
    ang_reported = _f("pole_angle_deg", metrics)
    omega_true = _f("pole_angular_velocity_true", metrics)
    omega_reported = _f("pole_angular_velocity", metrics)
    cart_x = _f("cart_x", metrics)
    cart_v = _f("cart_velocity_x", metrics)
    track_center = _f("track_center_x", metrics, 50.0)
    safe_half = _f("safe_half_range", metrics, 8.5)
    bal_deg = _f("grading_balance_angle_deg", metrics, 45.0)
    fail_deg = _f("grading_failure_angle_deg", metrics, 90.0)
    all_zero = (
        _ok(ang_true) and abs(ang_true) < 1e-9
        and _ok(omega_true) and abs(omega_true) < 1e-9
        and _ok(cart_v) and abs(cart_v) < 1e-9
    )
    if all_zero and is_first:
        parts.append(
            f"- **Pole**: θ=0.000°, ω=0 "
            f"(vertical equilibrium; band ±{bal_deg:.1f}°, fail ±{fail_deg:.1f}°) "
            f"— dynamics not excited, controller effectiveness not assessable from this moment"
        )
        if _ok(cart_x) and _ok(track_center) and _ok(safe_half):
            left = track_center - safe_half
            right = track_center + safe_half
            parts.append(
                f"- **Cart**: x={cart_x:.3f} m, v=0  "
                f"(track [{left:.3f}, {right:.3f}], ±{safe_half:.3f} m)"
            )
        return parts
    if all_zero and not is_first:
        parts.append(f"- Pole still at equilibrium; cart x={cart_x:.3f}, v={cart_v:.3f}")
        return parts
    if _ok(ang_true):
        abs_ang = abs(ang_true)
        margin_bal = bal_deg - abs_ang
        pct_bal = _pct(abs_ang, bal_deg)
        sev_bal = _margin_label(_pct(abs_ang, bal_deg) / 100.0 if bal_deg > 0 else 0.0)
        parts.append(
            f"- **Pole angle (true)**: {ang_true:.3f}° "
            f"(band ±{bal_deg:.1f}°, margin {margin_bal:.2f}°, "
            f"{_fmt(pct_bal, 1) if _ok(pct_bal) else '—'}% — {sev_bal})"
        )
        if abs_ang > fail_deg:
            parts.append(f"  ⚠ Exceeded failure threshold by {abs_ang - fail_deg:.2f}°")
        elif abs_ang > bal_deg:
            parts.append(f"  Outside balance band by {abs_ang - bal_deg:.2f}°")
    if _ok(ang_reported):
        if _ok(omega_reported):
            parts.append(
                f"- **Pole (reported)**: angle={ang_reported:.3f}°, ω={omega_reported:.4f} rad/s"
            )
        else:
            parts.append(f"- **Pole (reported)**: angle={ang_reported:.3f}°")
    if _ok(omega_true):
        omega_dps = math.degrees(omega_true)
        parts.append(f"- **Pole ang.vel (true)**: {omega_true:.4f} rad/s ({omega_dps:.2f} deg/s)")
    if _ok(cart_x) and _ok(track_center) and _ok(safe_half):
        left_edge = track_center - safe_half
        right_edge = track_center + safe_half
        left_margin = cart_x - left_edge
        right_margin = right_edge - cart_x
        offset = cart_x - track_center
        pct_used = _pct(abs(offset), safe_half)
        sev = _margin_label(_pct(abs(offset), safe_half) / 100.0 if safe_half > 0 else 0.0)
        v_str = f", v={cart_v:.3f} m/s" if _ok(cart_v) else ""
        parts.append(
            f"- **Cart**: x={cart_x:.3f} m (center {track_center:.3f}, offset {offset:+.3f}){v_str}"
        )
        parts.append(
            f"  Track [{left_edge:.3f}, {right_edge:.3f}] ±{safe_half:.3f}  |  "
            f"L: {left_margin:.3f}  R: {right_margin:.3f}  |  "
            f"{_fmt(pct_used, 1) if _ok(pct_used) else '—'}% — {sev}"
        )
    return parts

def _section_sensor_divergence(metrics: Dict[str, Any], *, is_first: bool = True) -> List[str]:
    parts: List[str] = ["### Sensor Divergence"]
    ang_reported = _f("pole_angle_deg", metrics)
    ang_true = _f("pole_angle_true_deg", metrics)
    omega_reported = _f("pole_angular_velocity", metrics)
    omega_true = _f("pole_angular_velocity_true", metrics)
    have_ang = _ok(ang_true) and _ok(ang_reported)
    have_om = _ok(omega_true) and _ok(omega_reported)
    delta_ang = abs(ang_true - ang_reported) if have_ang else float("nan")
    delta_om = abs(omega_true - omega_reported) if have_om else float("nan")
    both_zero = (_ok(delta_ang) and delta_ang < 1e-9 and _ok(delta_om) and abs(delta_om) < 1e-9)
    if both_zero:
        parts.append("- No divergence (sensor buffers fully primed, no dynamics to create lag).")
        return parts
    if have_ang:
        parts.append(
            f"- |true−reported| angle: {delta_ang:.4f}° "
            f"(true={ang_true:.3f}°, reported={ang_reported:.3f}°)"
        )
    else:
        parts.append("- Angle divergence: insufficient data")
    if have_om:
        parts.append(
            f"- |true−reported| omega: {delta_om:.4f} rad/s "
            f"(true={omega_true:.4f}, reported={omega_reported:.4f})"
        )
    else:
        parts.append("- Omega divergence: insufficient data")
    return parts

def _section_control_diagnostics(metrics: Dict[str, Any]) -> List[str]:
    parts: List[str] = ["### Control Diagnostics"]
    force_limit = _f("force_limit", metrics, 450.0)
    applied = _f("applied_force", metrics, 0.0)
    ang_true_deg = _f("pole_angle_true_deg", metrics)
    all_zero = (
        _ok(applied) and abs(applied) < 1e-9
        and _ok(ang_true_deg) and abs(ang_true_deg) < 1e-9
    )
    if all_zero and _ok(force_limit) and force_limit > 0:
        parts.append(
            f"- **Force**: 0.0000 N / {force_limit:.4f} N (0.0% — nominal)"
        )
        return parts
    if _ok(force_limit) and force_limit > 0:
        pct_force = _pct(abs(applied), force_limit)
        sev = _margin_label(abs(applied) / force_limit if force_limit > 0 else 0.0)
        parts.append(
            f"- **Applied force**: {applied:.4f} N / {force_limit:.4f} N "
            f"({_fmt(pct_force, 1) if _ok(pct_force) else '—'}% — {sev})"
        )
    else:
        parts.append(f"- **Applied force**: {_fmt(applied, 4)} N (force limit unknown)")
    return parts

def _section_energy_audit(metrics: Dict[str, Any], *, is_first: bool = True) -> List[str]:
    parts: List[str] = ["### Energy Audit (Kinetic Only)"]
    pole_mass = _f("pole_mass", metrics, 1.0)
    cart_mass = _f("cart_mass", metrics, 10.0)
    pole_len = _f("pole_length", metrics, 2.0)
    cart_v = _f("cart_velocity_x", metrics)
    omega_true = _f("pole_angular_velocity_true", metrics)
    ke_cart = 0.5 * cart_mass * cart_v * cart_v if _ok(cart_mass) and _ok(cart_v) else 0.0
    ke_pole = 0.0
    if _ok(pole_mass) and _ok(cart_v) and _ok(omega_true) and _ok(pole_len):
        ke_trans = 0.5 * pole_mass * cart_v * cart_v
        inertia = (1.0 / 3.0) * pole_mass * pole_len * pole_len
        ke_rot = 0.5 * inertia * omega_true * omega_true
        ke_pole = ke_trans + ke_rot
    if abs(ke_cart) < 1e-12 and abs(ke_pole) < 1e-12:
        parts.append("- All kinetic energies zero (pole at vertical equilibrium).")
        return parts
    components: List[str] = []
    if _ok(cart_mass) and _ok(cart_v):
        components.append(f"KE_cart = {ke_cart:.4f} J")
    if _ok(pole_mass) and _ok(cart_v) and _ok(omega_true) and _ok(pole_len):
        components.append(f"KE_pole = {ke_pole:.4f} J (trans {ke_trans:.4f} + rot {ke_rot:.4f})")
    components.append(f"Total kinetic energy: {ke_cart + ke_pole:.4f} J")
    if components:
        for c in components:
            parts.append(f"- {c}")
    else:
        parts.append("- Insufficient data for energy computation.")
    return parts

def _section_perturbation_check(metrics: Dict[str, Any]) -> List[str]:
    parts: List[str] = ["### Perturbation Detection"]
    ang_true_deg = _f("pole_angle_true_deg", metrics)
    omega_true = _f("pole_angular_velocity_true", metrics)
    applied = _f("applied_force", metrics, 0.0)
    cart_v = _f("cart_velocity_x", metrics)
    ang_true_rad = math.radians(ang_true_deg) if _ok(ang_true_deg) else float("nan")
    if not _ok(ang_true_rad):
        parts.append("- Pole angle unavailable for perturbation check.")
        return parts
    if abs(ang_true_rad) < 1e-6:
        if _ok(omega_true) and abs(omega_true) < 1e-6:
            if _ok(applied) and abs(applied) < 1e-6:
                if _ok(cart_v) and abs(cart_v) < 1e-6:
                    parts.append(
                    )
                else:
                    parts.append(
                        f"- ⚠ Near-equilibrium: pole < 1 μrad, cart v={cart_v:.4f} m/s"
                    )
            else:
                parts.append(
                    f"- ℹ Pole at equilibrium (θ<1 μrad), active force {applied:.4f} N"
                )
        else:
            parts.append(
                f"- ℹ Pole near vertical, ω={omega_true:.4f} rad/s — dynamics active"
            )
    elif abs(ang_true_rad) < math.radians(0.01):
        parts.append(
            f"- ℹ Pole within 0.01° of vertical ({abs(ang_true_deg):.4f}°) — near-equilibrium"
        )
    else:
        parts.append(
            f"- ✓ Pole deviated from vertical ({abs(ang_true_deg):.4f}°) — "
        )
    return parts

def _section_constraint_dashboard(metrics: Dict[str, Any]) -> List[str]:
    parts: List[str] = ["### Constraint Dashboard"]
    success = metrics.get("success", False)
    failed = metrics.get("failed", False)
    failure_reason = metrics.get("failure_reason") or metrics.get("reason") or ""
    entries: List[Dict[str, Any]] = []
    dist = _f("dist_from_center", metrics)
    safe = _f("safe_half_range", metrics, 8.5)
    cart_x = _f("cart_x", metrics)
    track_cx = _f("track_center_x", metrics, 50.0)
    if _ok(dist) and _ok(safe):
        track_ok = dist <= safe
        track_margin = safe - dist
        track_pct = _pct(dist, safe)
        entries.append({
            "label": "Track limits",
            "ok": track_ok,
            "pct": track_pct,
            "detail": (
                f"|x−{track_cx:.3f}| = {dist:.4f} m ≤ {safe:.4f} m  "
                f"(margin: {track_margin:.4f} m, {_fmt(track_pct, 1) if _ok(track_pct) else '—'}%)"
            ),
            "extra": None,
        })
    bal_achieved = metrics.get("balance_achieved", False)
    n_up = _f("consecutive_upright_sim_steps", metrics, 0)
    hold_req = _f("balance_hold_steps_required", metrics, 200)
    lock_pct = _pct(n_up, hold_req)
    if bal_achieved:
        entries.append({
            "label": "Balance lock-in",
            "ok": True,
            "pct": 0.0,
            "detail": "PASS — achieved and maintained",
            "extra": None,
        })
    else:
        entries.append({
            "label": "Balance lock-in",
            "ok": False,
            "pct": lock_pct if _ok(lock_pct) else 0.0,
            "detail": (
                f"NOT ACHIEVED  ({int(n_up) if _ok(n_up) else '—'}/"
                f"{int(hold_req) if _ok(hold_req) else '—'} "
                f"upright steps, {_fmt(lock_pct, 1) if _ok(lock_pct) else '—'}%)"
            ),
            "extra": None,
        })
    bal_deg = _f("grading_balance_angle_deg", metrics, 45.0)
    fail_deg = _f("grading_failure_angle_deg", metrics, 90.0)
    ang_true = _f("pole_angle_true_deg", metrics)
    if _ok(ang_true) and _ok(bal_deg) and _ok(fail_deg):
        in_balance = abs(ang_true) <= bal_deg
        in_fail = abs(ang_true) <= fail_deg
        margin_bal = bal_deg - abs(ang_true)
        margin_fail = fail_deg - abs(ang_true)
        pct_bal = _pct(abs(ang_true), bal_deg)
        pct_fail = _pct(abs(ang_true), fail_deg)
        applicable = "active" if bal_achieved else "pre-lock-in"
        bal_ok = in_balance
        fail_ok = in_fail
        combined_ok = bal_ok and fail_ok
        worst_pct = max(
            pct_bal if _ok(pct_bal) else 0.0,
            pct_fail if _ok(pct_fail) else 0.0,
        )
        entries.append({
            "label": f"Pole angle (bal ±{bal_deg:.0f}°/fail ±{fail_deg:.0f}°, {applicable})",
            "ok": combined_ok,
            "pct": worst_pct,
            "detail": (
                f"|θ| = {abs(ang_true):.3f}°  "
                f"(bal margin: {margin_bal:.2f}°  |  fail margin: {margin_fail:.2f}°)"
            ),
            "extra": None,
        })
    sc = _f("step_count", metrics)
    ms = _f("max_steps", metrics)
    if _ok(sc) and _ok(ms):
        pct_done = _pct(sc, ms)
        remaining = max(0, int(ms) - int(sc))
        budget_ok = sc < ms or success
        entries.append({
            "label": "Step budget",
            "ok": budget_ok,
            "pct": pct_done if _ok(pct_done) else 0.0,
            "detail": (
                f"{int(sc)}/{int(ms)} steps "
                f"({_fmt(pct_done, 1) if _ok(pct_done) else '—'}% used, {remaining} left)"
            ),
            "extra": None,
        })
    force_lim = _f("force_limit", metrics, 450.0)
    applied_f = _f("applied_force", metrics, 0.0)
    if _ok(force_lim):
        pct_f = _pct(abs(applied_f), force_lim)
        sat_label = "SATURATED" if abs(applied_f) >= force_lim * 0.999 else "within range"
        entries.append({
            "label": "Actuator",
            "ok": abs(applied_f) <= force_lim,
            "pct": pct_f if _ok(pct_f) else 0.0,
            "detail": (
                f"{sat_label}  |F|={abs(applied_f):.4f} N ≤ {force_lim:.4f} N "
                f"({_fmt(pct_f, 1) if _ok(pct_f) else '—'}%)"
            ),
            "extra": None,
        })
    expanded: List[Dict[str, Any]] = []
    collapsed: List[Dict[str, Any]] = []
    for e in entries:
        p = e["pct"] if _ok(e["pct"]) else 0.0
        if not e["ok"] or p >= 50.0:
            expanded.append(e)
        else:
            collapsed.append(e)
    for e in expanded:
        status = "PASS" if e["ok"] else "FAIL"
        parts.append(f"- **{e['label']}**: {status}  {e['detail']}")
        if e["label"] == "Track limits" and not e["ok"] and _ok(cart_x) and _ok(track_cx) and _ok(safe):
            left_edge = track_cx - safe
            right_edge = track_cx + safe
            if cart_x < left_edge:
                parts.append(f"  Cart exited LEFT by {left_edge - cart_x:.4f} m")
            else:
                parts.append(f"  Cart exited RIGHT by {cart_x - right_edge:.4f} m")
    if collapsed:
        labels = ", ".join(e["label"] for e in collapsed)
        parts.append(f"- **{labels}**: all PASS (low utilization, <50%)")
    if success:
        parts.append("\n**Overall**: ALL constraints PASSED")
    elif failed:
        parts.append(f"\n**Overall**: FAILED — {failure_reason}")
    else:
        parts.append("\n**Overall**: INCOMPLETE — no terminal determination")
    return parts

def _section_failure_chronology(metrics: Dict[str, Any]) -> List[str]:
    parts: List[str] = []
    failed = metrics.get("failed", False)
    if not failed:
        return parts
    parts.append("### Failure Chronology")
    failure_reason = metrics.get("failure_reason") or metrics.get("reason") or ""
    sc = _f("step_count", metrics)
    ms = _f("max_steps", metrics)
    reason_lower = failure_reason.lower()
    events: List[str] = []
    if "cart left safe zone" in reason_lower or "track" in reason_lower:
        cart_x = _f("cart_x", metrics)
        track_cx = _f("track_center_x", metrics, 50.0)
        safe = _f("safe_half_range", metrics, 8.5)
        if _ok(cart_x) and _ok(track_cx) and _ok(safe):
            left_edge = track_cx - safe
            if cart_x < left_edge:
                events.append(
                    f"1. Step {int(sc) if _ok(sc) else '?'}: Cart at x={cart_x:.4f} m "
                    f"exceeded LEFT track limit ({left_edge:.4f} m) "
                    f"by {left_edge - cart_x:.4f} m"
                )
            else:
                events.append(
                    f"1. Step {int(sc) if _ok(sc) else '?'}: Cart at x={cart_x:.4f} m "
                    f"exceeded RIGHT track limit ({track_cx + safe:.4f} m) "
                    f"by {cart_x - (track_cx + safe):.4f} m"
                )
        ang_true = _f("pole_angle_true_deg", metrics)
        if _ok(ang_true):
            bal_deg = _f("grading_balance_angle_deg", metrics, 45.0)
            in_band = abs(ang_true) <= bal_deg
            events.append(
                f"   Pole at {ang_true:.3f}° "
                f"({'within' if in_band else 'outside'} ±{bal_deg:.1f}° balance band)"
            )
    elif "pole fell after balancing" in reason_lower:
        ang_true = _f("pole_angle_true_deg", metrics)
        fail_deg = _f("grading_failure_angle_deg", metrics, 90.0)
        if _ok(ang_true) and _ok(fail_deg):
            events.append(
                f"1. Step {int(sc) if _ok(sc) else '?'}: Pole at {ang_true:.3f}° "
                f"exceeded post-lock-in threshold ±{fail_deg:.1f}° "
                f"by {abs(ang_true) - fail_deg:.2f}°"
            )
        events.append("   Balance lock-in had been achieved — pole destabilized after stabilization")
    elif "time limit" in reason_lower:
        events.append(
            f"1. Step {int(sc) if _ok(sc) else '?'}/{int(ms) if _ok(ms) else '?'}: "
        )
        n_up = _f("consecutive_upright_sim_steps", metrics, 0)
        hold_req = _f("balance_hold_steps_required", metrics, 200)
        if _ok(n_up) and _ok(hold_req):
            events.append(
                f"   Balance progress: {int(n_up)}/{int(hold_req)} upright steps "
                f"({_fmt(_pct(n_up, hold_req), 1)}%)"
            )
    elif "not in upright region" in reason_lower:
        ang_true = _f("pole_angle_true_deg", metrics)
        bal_deg = _f("grading_balance_angle_deg", metrics, 45.0)
        if _ok(ang_true) and _ok(bal_deg):
            events.append(
                f"1. Step {int(sc) if _ok(sc) else '?'}: Lock-in achieved but "
                f"terminal |θ|={abs(ang_true):.3f}° exceeds ±{bal_deg:.1f}° "
                f"by {abs(ang_true) - bal_deg:.2f}°"
            )
    else:
        events.append(f"1. Step {int(sc) if _ok(sc) else '?'}: Failure — {failure_reason}")
    ang_true = _f("pole_angle_true_deg", metrics)
    omega_true = _f("pole_angular_velocity_true", metrics)
    applied = _f("applied_force", metrics, 0.0)
    force_lim = _f("force_limit", metrics, 450.0)
    if _ok(ang_true) and _ok(omega_true):
        events.append(
            f"   θ_true={ang_true:.3f}°, ω_true={omega_true:.4f} rad/s "
            f"({math.degrees(omega_true):.1f} deg/s)"
        )
    if _ok(applied) and _ok(force_lim):
        events.append(
            f"   Force: {applied:.4f} N / {force_lim:.4f} N "
            f"({_fmt(_pct(abs(applied), force_lim), 1)}% utilized)"
        )
    for e in events:
        parts.append(f"- {e}")
    return parts

def format_task_metrics(metrics: Dict[str, Any]) -> List[str]:
    if not metrics:
        return ["**No metrics available**"]
    is_first = _f("step_count", metrics) == 0
    parts: List[str] = []
    parts.extend(_section_numerical_health(metrics))
    parts.append("")
    if is_first:
        parts.extend(_section_physics_summary(metrics))
        parts.append("")
    parts.extend(_section_state_snapshot(metrics, is_first=is_first))
    parts.append("")
    parts.extend(_section_sensor_divergence(metrics, is_first=is_first))
    parts.append("")
    parts.extend(_section_control_diagnostics(metrics))
    parts.append("")
    parts.extend(_section_energy_audit(metrics, is_first=is_first))
    parts.append("")
    if not is_first:
        parts.extend(_section_perturbation_check(metrics))
        parts.append("")
    parts.extend(_section_constraint_dashboard(metrics))
    parts.append("")
    chrono = _section_failure_chronology(metrics)
    if chrono:
        parts.extend(chrono)
        parts.append("")
    return parts
