from typing import Dict, Any, List, Optional

import math

def _f(x: Any) -> Optional[float]:
    if x is None:
        return None
    try:
        v = float(x)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None

def _fmt(v: Optional[float], dec: int = 4) -> str:
    if v is None:
        return "—"
    return f"{v:.{dec}f}"

def _pct(num: Optional[float], denom: Optional[float]) -> Optional[float]:
    n, d = _f(num), _f(denom)
    if n is None or d is None or d == 0.0:
        return None
    return n / d * 100.0

def _margin(val: Optional[float], limit: Optional[float]) -> Optional[float]:
    v, l = _f(val), _f(limit)
    if v is None or l is None:
        return None
    return l - v

def _severity_tier(pct: Optional[float]) -> str:
    if pct is None:
        return "unknown"
    if pct >= 95.0:
        return "CRITICAL"
    if pct >= 80.0:
        return "elevated"
    if pct >= 50.0:
        return "moderate"
    return "nominal"

def _pass_fail(margin: Optional[float]) -> str:
    if margin is None:
        return "UNKNOWN"
    return "PASS" if margin >= 0.0 else "FAIL"

def _near_limit(margin: Optional[float], limit: Optional[float]) -> bool:
    m, l = _f(margin), _f(limit)
    if m is None or l is None or l <= 0.0 or m < 0.0:
        return False
    return m / l < 0.30

def _dim_temporal_chronology(metrics: Dict[str, Any]) -> List[str]:
    lines: List[str] = ["### 1. Temporal Event Chronology"]
    step_count = _f(metrics.get("step_count"))
    max_steps = _f(metrics.get("max_steps"))
    reg_start = _f(metrics.get("regulation_start_step"))
    omega = _f(metrics.get("wheel_angular_velocity"))
    target = _f(metrics.get("target_speed"))
    success = metrics.get("success", False)
    failed = metrics.get("failed", False)
    failure_reason = metrics.get("failure_reason")
    pos_text = ""
    if step_count is not None and max_steps is not None and max_steps > 0:
        pct = step_count / max_steps * 100.0
        pos_text = f"step {int(step_count)}/{int(max_steps)} ({_fmt(pct, 1)}%)"
    elif step_count is not None:
        pos_text = f"step {int(step_count)}"
    phase_text = ""
    if step_count is not None and reg_start is not None:
        if step_count < reg_start:
            remaining = int(reg_start) - int(step_count)
            phase_text = f"PRE-REGULATION ({remaining} steps until regulation at step {int(reg_start)})"
        else:
            reg_elapsed = int(step_count) - int(reg_start)
            reg_total = max(0, int((max_steps or step_count)) - int(reg_start))
            phase_text = f"REGULATION ({reg_elapsed}/{reg_total} steps elapsed)"
    if pos_text or phase_text:
        parts = [p for p in [pos_text, phase_text] if p]
        lines.append(f"- **Episode**: {' — '.join(parts)}")
    if success:
        lines.append("- **Outcome**: SUCCESS")
    elif failed:
        fr = failure_reason if failure_reason else "(no reason recorded)"
        lines.append(f"- **Outcome**: FAILED — {fr}")
    else:
        lines.append("- **Outcome**: in progress")
    if omega is not None and target is not None:
        err = abs(omega - target)
        lines.append(f"- **Speed**: ω = {_fmt(omega, 4)}, target = {_fmt(target, 4)}, |error| = {_fmt(err, 4)} rad/s")
    if len(lines) == 1:
        lines.append("- State data unavailable")
    return lines

def _dim_speed_margins(metrics: Dict[str, Any]) -> List[str]:
    lines: List[str] = ["### 2. Speed Error Margins"]
    speed_error = _f(metrics.get("speed_error"))
    mean_err_thresh = _f(metrics.get("mean_speed_error_threshold"))
    target = _f(metrics.get("target_speed"))
    if speed_error is not None:
        line = f"- **|ω−target|** = {_fmt(speed_error, 4)} rad/s"
        if mean_err_thresh is not None:
            pct_vs = _pct(speed_error, mean_err_thresh)
            line += f" ({_fmt(pct_vs, 1)}% of mean-error threshold {_fmt(mean_err_thresh, 4)} rad/s)"
        lines.append(line)
    if speed_error is not None and target is not None and target > 0:
        rel = speed_error / target * 100.0
        lines.append(f"- **Relative error**: {_fmt(rel, 1)}% of target speed")
    delay = metrics.get("measurement_delay")
    if delay is not None:
        lines.append(f"- **Sensor delay**: {int(delay)} step(s) old")
    if len(lines) == 1:
        lines.append("- Speed margin data unavailable")
    return lines

def _dim_load_stress(metrics: Dict[str, Any]) -> List[str]:
    lines: List[str] = ["### 3. Load & Stress Distribution"]
    commanded_t = _f(metrics.get("commanded_torque"))
    applied_t = _f(metrics.get("applied_torque"))
    load_t = _f(metrics.get("load_torque"))
    max_limit = _f(metrics.get("max_torque_limit"))
    deadzone = _f(metrics.get("torque_deadzone"))
    if deadzone is not None:
        lines.append(f"- **Deadzone**: ±{_fmt(deadzone, 4)} N·m")
    if commanded_t is not None and applied_t is not None:
        was_deadzoned = abs(commanded_t) > 0.001 and abs(applied_t) < 0.001
        was_clamped = abs(commanded_t) > abs(applied_t) + 0.001 and not was_deadzoned
        if was_deadzoned:
            lines.append(
                f"- **τ_cmd → τ_app**: {_fmt(commanded_t, 4)} → 0.0000 N·m (DEADZONED)"
            )
        elif was_clamped:
            pct_passthru = abs(applied_t) / (abs(commanded_t) + 1e-12) * 100.0
            lines.append(
                f"- **τ_cmd → τ_app**: {_fmt(commanded_t, 4)} → {_fmt(applied_t, 4)} N·m "
                f"(CLAMPED at {_fmt(pct_passthru, 1)}%, limit = {_fmt(max_limit, 4)} N·m)"
            )
    if applied_t is not None:
        if max_limit is not None and max_limit > 0:
            pct = abs(applied_t) / max_limit * 100.0
            tier = _severity_tier(pct)
            lines.append(
                f"- **τ_applied** = {_fmt(applied_t, 4)} N·m "
                f"({tier}: {_fmt(pct, 1)}% of limit {_fmt(max_limit, 4)})"
            )
        else:
            lines.append(f"- **τ_applied** = {_fmt(applied_t, 4)} N·m")
    if load_t is not None:
        if max_limit is not None and max_limit > 0:
            pct = load_t / max_limit * 100.0
            tier = _severity_tier(pct)
            lines.append(
                f"- **τ_load** = {_fmt(load_t, 4)} N·m "
                f"({tier}: {_fmt(pct, 1)}% of limit)"
            )
        else:
            lines.append(f"- **τ_load** = {_fmt(load_t, 4)} N·m")
    if applied_t is not None and load_t is not None:
        net_t = applied_t - load_t
        if net_t > 0.01:
            direction = "accelerating"
        elif net_t < -0.01:
            direction = "decelerating"
        else:
            direction = "neutral"
        lines.append(f"- **τ_net** = {_fmt(net_t, 4)} N·m ({direction})")
    if len(lines) == 1:
        lines.append("- Torque data unavailable")
    return lines

def _dim_energy_power(metrics: Dict[str, Any]) -> List[str]:
    lines: List[str] = ["### 4. Energy & Power Flow"]
    ke = _f(metrics.get("wheel_rotational_ke"))
    motor_pwr = _f(metrics.get("motor_power"))
    load_pwr = _f(metrics.get("load_power"))
    I_wheel = _f(metrics.get("wheel_moment_of_inertia"))
    omega = _f(metrics.get("wheel_angular_velocity"))
    if ke is not None:
        parts = [f"- **KE**: {_fmt(ke, 4)} J"]
        if I_wheel is not None and omega is not None:
            parts.append(f" (I = {_fmt(I_wheel, 4)} kg·m², ω = {_fmt(omega, 4)} rad/s)")
        lines.append("".join(parts))
    if motor_pwr is not None or load_pwr is not None:
        mp = _fmt(motor_pwr, 4) if motor_pwr is not None else "—"
        lp = _fmt(load_pwr, 4) if load_pwr is not None else "—"
        line = f"- **Power**: motor {mp} W, dissipation {lp} W"
        if motor_pwr is not None and load_pwr is not None:
            total = motor_pwr + load_pwr
            if abs(total) > 1e-12:
                eff = motor_pwr / total * 100.0
                line += f" (motor {_fmt(eff, 1)}% of total flow)"
        lines.append(line)
    if len(lines) == 1:
        lines.append("- Energy/power data unavailable")
    return lines

def _dim_constraint_profile(metrics: Dict[str, Any]) -> List[str]:
    lines: List[str] = ["### 5. Constraint Satisfaction Profile"]
    step_count = _f(metrics.get("step_count"))
    max_steps = _f(metrics.get("max_steps"))
    reg_start = _f(metrics.get("regulation_start_step"))
    stall_thresh = _f(metrics.get("stall_speed_threshold"))
    stall_steps_thresh = _f(metrics.get("stall_steps_threshold"))
    mean_err_thresh = _f(metrics.get("mean_speed_error_threshold"))
    omega = _f(metrics.get("wheel_angular_velocity"))
    stall_count = _f(metrics.get("stall_count"))
    mean_speed_err = _f(metrics.get("mean_speed_error"))
    failed = metrics.get("failed", False)
    failure_reason = metrics.get("failure_reason")
    if step_count is not None and reg_start is not None:
        if step_count < reg_start:
            lines.append(
                f"- **Regulation horizon**: NOT REACHED "
                f"(regulation at step {int(reg_start)}, currently at step {int(step_count)}, "
                f"{int(reg_start - step_count)} steps remaining)"
            )
        else:
            reg_elapsed = int(step_count - reg_start)
            reg_total = max(0, int((max_steps or step_count)) - reg_start)
            pct = _pct(reg_elapsed, reg_total)
            lines.append(
                f"- **Regulation horizon**: IN PROGRESS — "
                f"{reg_elapsed}/{reg_total} steps ({_fmt(pct, 1)}% elapsed)"
            )
    if omega is not None and stall_thresh is not None:
        stall_margin = _margin(stall_thresh, abs(omega))
        stall_pct = _pct(abs(omega), stall_thresh)
        stalling = stall_count is not None and stall_count > 0
        status = "FAIL" if (stall_count is not None and stall_steps_thresh is not None
                          and stall_count >= stall_steps_thresh) else "PASS"
        line = f"- **Stall** (|ω| ≥ {_fmt(stall_thresh, 4)} rad/s): {status}"
        if stalling:
            line += f" — STALLING: {int(stall_count or 0)}/{int(stall_steps_thresh or 0)} consecutive steps"
        else:
            line += f" — |ω| = {_fmt(abs(omega), 4)}, margin = {_fmt(stall_margin, 4)} rad/s, {_fmt(stall_pct, 1)}% of threshold"
        if _near_limit(stall_margin, stall_thresh):
            line += " ⚠"
        lines.append(line)
    if mean_speed_err is not None and mean_err_thresh is not None:
        mse_margin = _margin(mean_err_thresh, mean_speed_err)
        mse_status = _pass_fail(mse_margin)
        mse_pct = _pct(mean_speed_err, mean_err_thresh)
        line = f"- **Mean speed error** (≤ {_fmt(mean_err_thresh, 4)} rad/s): {mse_status}"
        if reg_start is not None and step_count is not None and step_count < reg_start:
            line += " — not yet evaluated (pre-regulation)"
        else:
            line += f" — mean = {_fmt(mean_speed_err, 4)}, margin = {_fmt(mse_margin, 4)} rad/s, {_fmt(mse_pct, 1)}% of threshold"
        if _near_limit(mse_margin, mean_err_thresh):
            line += " ⚠"
        lines.append(line)
    if failed:
        if failure_reason:
            lines.append(f"- **Failure**: {failure_reason}")
        else:
            if step_count is not None and reg_start is not None and step_count < reg_start:
                w_str = _fmt(abs(omega), 4) if omega is not None else "—"
                lines.append(
                    f"- **Failure**: episode ended pre-regulation at step {int(step_count)}. "
                    f"Final |ω| = {w_str} rad/s."
                )
            else:
                lines.append("- **Failure**: no explicit reason recorded")
    return lines

def _dim_numerical_health(metrics: Dict[str, Any]) -> List[str]:
    lines: List[str] = ["### 6. Numerical Health"]
    numeric_keys = [
        ("wheel_angular_velocity", "Wheel angular velocity", 100.0),
        ("target_speed", "Target speed", 10.0),
        ("speed_error", "Speed error", 10.0),
        ("mean_speed_error", "Mean speed error", 10.0),
        ("commanded_torque", "Commanded torque", 500.0),
        ("applied_torque", "Applied torque", 500.0),
        ("load_torque", "Load torque", 500.0),
        ("max_torque_limit", "Torque limit", 500.0),
        ("motor_power", "Motor power", 5000.0),
        ("load_power", "Load power", 5000.0),
        ("wheel_rotational_ke", "Rotational KE", 10000.0),
    ]
    flags: List[str] = []
    for key, label, extreme in numeric_keys:
        v = metrics.get(key)
        if v is None:
            continue
        fv = _f(v)
        if fv is None:
            flags.append(f"**Non-finite {label}**: {v}")
        elif abs(fv) > extreme:
            flags.append(f"**Extreme {label}**: {fv:.2f} (threshold {extreme:.0f})")
    if flags:
        for fl in flags:
            lines.append(f"- {fl}")
    else:
        lines.append("- All tracked values finite and within expected ranges")
    return lines

def format_task_metrics(
    metrics: Dict[str, Any],
    previous_metrics: Optional[Dict[str, Any]] = None,

) -> List[str]:
    if not metrics:
        return []
    numeric_keys = [
        "wheel_angular_velocity", "target_speed", "speed_error", "mean_speed_error",
        "commanded_torque", "applied_torque", "load_torque", "max_torque_limit",
        "motor_power", "load_power", "wheel_rotational_ke",
    ]
    nf_alerts: List[str] = []
    for key in numeric_keys:
        v = metrics.get(key)
        if v is not None:
            fv = _f(v)
            if fv is None:
                nf_alerts.append(f"**Non-finite value in `{key}`**: {v} — solver may have diverged")
    parts: List[str] = []
    if nf_alerts:
        parts.append("### ⚠ Numerical Anomaly Detected")
        parts.extend(nf_alerts)
        parts.append("")
    prev = previous_metrics if isinstance(previous_metrics, dict) and previous_metrics else None
    dimension_specs = [
        ("1. Temporal Event Chronology", _dim_temporal_chronology, _dim_temporal_chronology_delta, True),
        ("2. Speed Error Margins",      _dim_speed_margins,       _dim_speed_margins_delta,       False),
        ("3. Load & Stress Distribution", _dim_load_stress,       _dim_load_stress_delta,         False),
        ("4. Energy & Power Flow",      _dim_energy_power,        _dim_energy_power_delta,        False),
        ("5. Constraint Satisfaction Profile", _dim_constraint_profile, _dim_constraint_profile_delta, True),
        ("6. Numerical Health",         _dim_numerical_health,    _dim_numerical_health,           True),
    ]
    for section_name, full_fn, delta_fn, always_emit in dimension_specs:
        try:
            emitted = False
            if prev is None:
                parts.extend(full_fn(metrics))
                emitted = True
            elif always_emit:
                if full_fn is delta_fn:
                    parts.extend(delta_fn(metrics))
                else:
                    parts.extend(delta_fn(metrics, prev))
                emitted = True
            else:
                delta_lines = delta_fn(metrics, prev)
                if delta_lines:
                    parts.extend(delta_lines)
                    emitted = True
            if emitted:
                parts.append("")
        except Exception:
            if prev is None:
                parts.append(f"### {section_name}")
                parts.append("- Data unavailable for this snapshot")
                parts.append("")
    return parts

def _delta_changed(current_val, previous_val, tolerance=1e-6) -> bool:
    cv = _f(current_val)
    pv = _f(previous_val)
    if cv is None and pv is None:
        return False
    if cv is None or pv is None:
        return True
    return abs(cv - pv) > tolerance

def _dim_temporal_chronology_delta(metrics: Dict[str, Any], prev: Dict[str, Any]) -> List[str]:
    lines: List[str] = ["### 1. Temporal Event Chronology (Δ from previous moment)"]
    step_count = _f(metrics.get("step_count"))
    max_steps = _f(metrics.get("max_steps"))
    reg_start = _f(metrics.get("regulation_start_step"))
    omega = _f(metrics.get("wheel_angular_velocity"))
    target = _f(metrics.get("target_speed"))
    success = metrics.get("success", False)
    failed = metrics.get("failed", False)
    failure_reason = metrics.get("failure_reason")
    prev_step = _f(prev.get("step_count"))
    prev_failed = prev.get("failed", False)
    prev_success = prev.get("success", False)
    if step_count is not None:
        pct = step_count / max_steps * 100.0 if (max_steps is not None and max_steps > 0) else 0.0
        lines.append(f"- **Episode**: step {int(step_count)}/{int(max_steps or 0)} ({_fmt(pct, 1)}%) (+{int(step_count - (prev_step or 0))} steps)")
    prev_phase = "regulation" if (prev_step is not None and reg_start is not None and prev_step >= reg_start) else "pre"
    cur_phase = "regulation" if (step_count is not None and reg_start is not None and step_count >= reg_start) else "pre"
    if cur_phase != prev_phase:
        if cur_phase == "regulation":
            lines.append(f"- **Phase**: entered REGULATION at step {int(reg_start)}")
        else:
            lines.append(f"- **Phase**: PRE-REGULATION")
    if failed != prev_failed or success != prev_success:
        if success:
            lines.append("- **Outcome**: SUCCESS")
        elif failed:
            fr = failure_reason if failure_reason else "(no reason recorded)"
            lines.append(f"- **Outcome**: FAILED — {fr}")
    if omega is not None and target is not None:
        err = abs(omega - target)
        prev_omega = _f(prev.get("wheel_angular_velocity"))
        delta_str = ""
        if prev_omega is not None:
            dω = omega - prev_omega
            delta_str = f", Δω = {_fmt(dω, 4)}"
        lines.append(f"- **Speed**: ω = {_fmt(omega, 4)}, target = {_fmt(target, 4)}, |error| = {_fmt(err, 4)} rad/s{delta_str}")
    return lines

def _dim_speed_margins_delta(metrics: Dict[str, Any], prev: Dict[str, Any]) -> Optional[List[str]]:
    speed_error = _f(metrics.get("speed_error"))
    prev_error = _f(prev.get("speed_error"))
    delay = metrics.get("measurement_delay")
    prev_delay = prev.get("measurement_delay")
    if not _delta_changed(speed_error, prev_error, 0.01) and delay == prev_delay:
        return None
    return _dim_speed_margins(metrics)

def _dim_load_stress_delta(metrics: Dict[str, Any], prev: Dict[str, Any]) -> Optional[List[str]]:
    keys = ["commanded_torque", "applied_torque", "load_torque", "max_torque_limit"]
    for k in keys:
        if _delta_changed(metrics.get(k), prev.get(k), 0.01):
            return _dim_load_stress(metrics)
    return None

def _dim_energy_power_delta(metrics: Dict[str, Any], prev: Dict[str, Any]) -> Optional[List[str]]:
    keys = ["wheel_rotational_ke", "motor_power", "load_power"]
    for k in keys:
        if _delta_changed(metrics.get(k), prev.get(k), 0.1):
            return _dim_energy_power(metrics)
    return None

def _dim_constraint_profile_delta(metrics: Dict[str, Any], prev: Dict[str, Any]) -> List[str]:
    lines: List[str] = ["### 5. Constraint Satisfaction Profile (Δ from previous moment)"]
    step_count = _f(metrics.get("step_count"))
    max_steps = _f(metrics.get("max_steps"))
    reg_start = _f(metrics.get("regulation_start_step"))
    stall_thresh = _f(metrics.get("stall_speed_threshold"))
    stall_steps_thresh = _f(metrics.get("stall_steps_threshold"))
    mean_err_thresh = _f(metrics.get("mean_speed_error_threshold"))
    omega = _f(metrics.get("wheel_angular_velocity"))
    stall_count = _f(metrics.get("stall_count"))
    mean_speed_err = _f(metrics.get("mean_speed_error"))
    failed = metrics.get("failed", False)
    failure_reason = metrics.get("failure_reason")
    prev_step = _f(prev.get("step_count"))
    if step_count is not None and reg_start is not None:
        prev_was_pre = prev_step is not None and prev_step < reg_start
        cur_is_pre = step_count < reg_start
        if cur_is_pre != prev_was_pre:
            if cur_is_pre:
                lines.append(
                    f"- **Regulation horizon**: still PRE-REGULATION "
                    f"({int(reg_start - step_count)} steps remaining)"
                )
            else:
                reg_elapsed = int(step_count - reg_start)
                reg_total = max(0, int((max_steps or step_count)) - int(reg_start))
                lines.append(
                    f"- **Regulation horizon**: entered REGULATION — "
                    f"{reg_elapsed}/{reg_total} steps elapsed"
                )
        elif cur_is_pre:
            remaining = int(reg_start - step_count)
            if remaining <= 50:
                lines.append(
                    f"- **Regulation horizon**: approaching — {remaining} steps until regulation"
                )
        else:
            reg_elapsed = int(step_count - reg_start)
            reg_total = max(0, int((max_steps or step_count)) - int(reg_start))
            lines.append(
                f"- **Regulation horizon**: {reg_elapsed}/{reg_total} steps elapsed"
            )
    if omega is not None and stall_thresh is not None:
        stall_margin = _margin(stall_thresh, abs(omega))
        stall_pct = _pct(abs(omega), stall_thresh)
        stalling = stall_count is not None and stall_count > 0
        prev_stalling = _f(prev.get("stall_count")) is not None and _f(prev.get("stall_count")) > 0
        status = "FAIL" if (stall_count is not None and stall_steps_thresh is not None
                          and stall_count >= stall_steps_thresh) else "PASS"
        if stalling != prev_stalling or _near_limit(stall_margin, stall_thresh):
            line = f"- **Stall** (|ω| ≥ {_fmt(stall_thresh, 4)} rad/s): {status}"
            if stalling:
                line += f" — STALLING: {int(stall_count or 0)}/{int(stall_steps_thresh or 0)} consecutive steps"
            else:
                line += f" — |ω| = {_fmt(abs(omega), 4)}, margin = {_fmt(stall_margin, 4)} rad/s, {_fmt(stall_pct, 1)}% of threshold"
            if _near_limit(stall_margin, stall_thresh):
                line += " ⚠"
            lines.append(line)
    if mean_speed_err is not None and mean_err_thresh is not None:
        mse_margin = _margin(mean_err_thresh, mean_speed_err)
        mse_status = _pass_fail(mse_margin)
        mse_pct = _pct(mean_speed_err, mean_err_thresh)
        line = f"- **Mean speed error** (≤ {_fmt(mean_err_thresh, 4)} rad/s): {mse_status}"
        if reg_start is not None and step_count is not None and step_count < reg_start:
            line += " — not yet evaluated (pre-regulation)"
        else:
            prev_mse = _f(prev.get("mean_speed_error"))
            if prev_mse is not None:
                dmse = mean_speed_err - prev_mse
                line += f" — mean = {_fmt(mean_speed_err, 4)}, Δ = {_fmt(dmse, 4)}, margin = {_fmt(mse_margin, 4)}"
            else:
                line += f" — mean = {_fmt(mean_speed_err, 4)}, margin = {_fmt(mse_margin, 4)}"
        if _near_limit(mse_margin, mean_err_thresh):
            line += " ⚠"
        lines.append(line)
    if failed:
        prev_was_failed = prev.get("failed", False)
        if not prev_was_failed or failure_reason != prev.get("failure_reason"):
            if failure_reason:
                lines.append(f"- **Failure**: {failure_reason}")
            else:
                lines.append(f"- **Failure**: episode ended at step {int(step_count)}")
    return lines

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
        suggestions.append("- The code failed to execute. Review the error traceback above.")
        return suggestions
    if success:
        suggestions.append("- The controller met all criteria. No further changes needed.")
        return suggestions
    omega = _f(metrics.get("wheel_angular_velocity"))
    target = _f(metrics.get("target_speed"))
    stall_count = _f(metrics.get("stall_count"))
    mean_speed_err = _f(metrics.get("mean_speed_error"))
    mean_err_thresh = _f(metrics.get("mean_speed_error_threshold"))
    step_count = _f(metrics.get("step_count"))
    reg_start = _f(metrics.get("regulation_start_step"))
    max_steps = _f(metrics.get("max_steps"))
    if step_count is not None and reg_start is not None and max_steps is not None:
        if max_steps <= reg_start and step_count >= max_steps - 1:
            suggestions.append(
            )
    if stall_count is not None and stall_count > 0:
        suggestions.append(
        )
    if mean_speed_err is not None and mean_err_thresh is not None:
        if mean_speed_err > mean_err_thresh:
            suggestions.append(
                f"- The mean speed tracking error ({mean_speed_err:.4f} rad/s) exceeds the "
                f"threshold ({mean_err_thresh:.4f} rad/s). Review the feedback dimensions above "
                f"to understand which constraint dimensions are driving the error."
            )
    if omega is not None and target is not None:
        err = abs(omega - target)
        if err > 0.3:
            suggestions.append(
                f"- The instantaneous speed error ({err:.4f} rad/s) indicates the wheel speed is "
                f"significantly offset from the target ({target:.4f} rad/s). "
                f"The Load & Stress Distribution section above reports torque components "
                f"that may help diagnose whether the offset is from insufficient drive torque "
                f"or from the torque limit capping output."
            )
    if not suggestions:
        suggestions.append("- Review the diagnostic dimensions above to identify failure root causes.")
    return suggestions
