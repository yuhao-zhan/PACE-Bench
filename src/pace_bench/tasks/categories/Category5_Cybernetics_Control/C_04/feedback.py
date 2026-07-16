import math

from typing import Dict, Any, List, Optional

_prev_metrics: Optional[Dict[str, Any]] = None

def reset_feedback_state():
    global _prev_metrics
    _prev_metrics = None

def _m(metrics: Dict[str, Any], key: str, default: float = 0.0) -> float:
    v = metrics.get(key, default)
    try:
        f = float(v)
        return f if math.isfinite(f) else float(default)
    except (TypeError, ValueError):
        return float(default)

def _mi(metrics: Dict[str, Any], key: str, default: int = 0) -> int:
    v = metrics.get(key, default)
    try:
        return int(v)
    except (TypeError, ValueError):
        return int(default)

def _mb(metrics: Dict[str, Any], key: str, default: bool = False) -> bool:
    v = metrics.get(key, default)
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.lower() in ("true", "yes", "1")
    try:
        return bool(v)
    except (TypeError, ValueError):
        return default

def _is_finite(x: Any) -> bool:
    if x is None:
        return True
    try:
        return math.isfinite(float(x))
    except (TypeError, ValueError):
        return True

def _fmt(val: float, decimals: int = 2) -> str:
    try:
        f = float(val)
        if not math.isfinite(f):
            return str(val)
        return f"{f:.{decimals}f}"
    except (TypeError, ValueError):
        return str(val)

def _exit_hold_required(metrics: Dict[str, Any]) -> int:
    return _mi(metrics, "consecutive_exit_steps_required", 5)

def _speed(vx: float, vy: float) -> float:
    return math.sqrt(vx * vx + vy * vy)

def _delta(metrics: Dict[str, Any], key: str, tol: float = 1e-6) -> bool:
    global _prev_metrics
    if _prev_metrics is None:
        return True
    prev = _prev_metrics.get(key)
    curr = metrics.get(key)
    if prev is None and curr is None:
        return False
    if prev is None or curr is None:
        return True
    try:
        return abs(float(curr) - float(prev)) > tol
    except (TypeError, ValueError):
        return str(curr) != str(prev)

def _delta_any(metrics: Dict[str, Any], keys: List[str], tol: float = 1e-6) -> bool:
    return any(_delta(metrics, k, tol) for k in keys)

def _is_first_moment() -> bool:
    return _prev_metrics is None

def _pos_changed(metrics: Dict[str, Any]) -> bool:
    return _delta_any(metrics, ["agent_x", "agent_y", "progress_x_pct"])

def _force_changed(metrics: Dict[str, Any]) -> bool:
    return _delta_any(metrics, ["force_ledger", "agent_vx", "agent_vy"])

def _section_temporal_chronology(metrics: Dict[str, Any]) -> List[str]:
    parts = []
    step_count = _mi(metrics, "step_count", 0)
    max_steps_val = max(_mi(metrics, "max_steps", 0), 250000)
    x = _m(metrics, "agent_x")
    y = _m(metrics, "agent_y")
    vx = _m(metrics, "agent_vx")
    vy = _m(metrics, "agent_vy")
    spd = _speed(vx, vy)
    unlocked = _mb(metrics, "unlocked", False)
    reached_exit = _mb(metrics, "reached_exit", False)
    consec_in_exit = _mi(metrics, "consecutive_steps_in_exit", 0)
    exit_hold_need = _exit_hold_required(metrics)
    gate = "UNLOCKED" if unlocked else "LOCKED"
    exit_label = "IN EXIT" if reached_exit else "not at exit"
    parts.append(
        f"Step {step_count} | pos=({_fmt(x)}, {_fmt(y)}) | "
        f"speed={_fmt(spd, 3)} (vx={_fmt(vx, 3)}, vy={_fmt(vy, 3)}) | "
        f"gate={gate} | {exit_label} | dwell={consec_in_exit}/{exit_hold_need}"
    )
    events = []
    ucs = metrics.get("unlock_condition_status")
    if isinstance(ucs, dict) and not unlocked:
        conditions = ucs.get("conditions", [])
        for cond in conditions:
            if not cond.get("pass", False):
                name = cond.get("name", "?")
                margin = cond.get("margin", 0.0)
                try:
                    margin_f = float(margin)
                except (TypeError, ValueError):
                    margin_f = 0.0
                short_name = {
                    "reported_x_in_activation_zone": "x not in activation zone",
                    "commanded_fx_below_threshold": "Fx above threshold",
                    "physical_speed_below_max": "speed above max",
                }.get(name, name)
                events.append(f"Unlock FAIL: {short_name} (margin {_fmt(margin_f, 3)})")
    if ucs and isinstance(ucs, dict):
        cons = ucs.get("consecutive_count", 0)
        req = ucs.get("required_consecutive", 5)
        all_met = ucs.get("all_conditions_met", False)
        if all_met and cons < req:
            events.insert(0, f"Unlock progressing: {cons}/{req} consecutive steps met")
        elif not all_met and cons > 0:
            events.insert(0, f"Unlock counter reset (was {cons}/{req})")
    ledger = metrics.get("force_ledger")
    if isinstance(ledger, dict):
        ch = ledger.get("channels", {})
        mag = ch.get("magnetic_floor", {})
        if mag.get("active", False):
            events.append(
                f"Magnetic floor: {_fmt(mag.get('force_fy', 0))} N downward (y < {_fmt(mag.get('y_threshold', 0))} m)"
            )
        rev = ch.get("control_reversal", {})
        if rev.get("active", False):
            events.append("Control reversal: Fx sign flipped")
        turb = ch.get("turbulence", {})
        if turb.get("active", False):
            events.append(
                f"Turbulence: intensity {_fmt(turb.get('intensity', 0))} N, "
                f"last=({_fmt(turb.get('last_fx', 0), 1)}, {_fmt(turb.get('last_fy', 0), 1)})"
            )
        drag = ch.get("fluid_drag", {})
        if drag.get("active", False):
            events.append(f"Fluid drag: coeff {_fmt(drag.get('coefficient', 0))}")
    wh = metrics.get("whisker_health")
    if isinstance(wh, dict) and wh.get("agent_in_blind_zone", False):
        events.append("Whiskers BLIND (all report max range)")
    wcm = metrics.get("wall_clearance_map")
    if isinstance(wcm, dict):
        for w in wcm.get("walls", []):
            rel = w.get("agent_relative", {})
            if rel.get("at_wall_x", False):
                w_idx = w.get("wall_index", "?")
                above = w.get("clearance_needed_m", {}).get("to_pass_above", 0)
                events.append(f"Agent AT wall #{w_idx} — clearance above: {_fmt(above)} m")
    if events:
        parts.append("Events:")
        for i, ev in enumerate(events, 1):
            parts.append(f"  {i}. {ev}")
    failed = _mb(metrics, "failed", False)
    if failed and metrics.get("failure_reason"):
        fr = str(metrics["failure_reason"])
        if "Structural Failure" in fr or "Collision impulse" in fr:
            parts.append(f"  CRITICAL: {fr}")
    return parts

def _section_spatial(metrics: Dict[str, Any]) -> List[str]:
    parts = []
    x = _m(metrics, "agent_x")
    y = _m(metrics, "agent_y")
    exit_x = _m(metrics, "exit_x_min", 15.0)
    exit_ylo = _m(metrics, "exit_y_min", 0.5)
    exit_yhi = _m(metrics, "exit_y_max", 2.5)
    act_lo = _m(metrics, "activation_x_min", 5.0)
    act_hi = _m(metrics, "activation_x_max", 10.0)
    lock_lo = _m(metrics, "lock_gate_x_min", 12.0)
    lock_hi = _m(metrics, "lock_gate_x_max", 16.0)
    oneway_x = _m(metrics, "oneway_x_threshold", 10.2)
    unlocked = _mb(metrics, "unlocked", False)
    zone_parts = []
    exit_str = f"Exit: x≥{_fmt(exit_x)} y∈[{_fmt(exit_ylo)},{_fmt(exit_yhi)}]"
    if x < exit_x:
        exit_str += f" →{_fmt(exit_x - x)}m"
    else:
        exit_str += " ✓x"
    if y < exit_ylo:
        exit_str += f" y↓{_fmt(exit_ylo - y)}"
    elif y > exit_yhi:
        exit_str += f" y↑{_fmt(y - exit_yhi)}"
    else:
        exit_str += " ✓y"
    zone_parts.append(exit_str)
    act_str = f"Act: [{_fmt(act_lo)},{_fmt(act_hi)}]"
    if x < act_lo:
        act_str += f" →{_fmt(act_lo - x)}m"
    elif x > act_hi:
        act_str += f" ←past {_fmt(x - act_hi)}m"
    else:
        act_str += " IN"
    zone_parts.append(act_str)
    lock_str = f"Lock: [{_fmt(lock_lo)},{_fmt(lock_hi)}]"
    if x < lock_lo:
        lock_str += f" →{_fmt(lock_lo - x)}m"
    elif x > lock_hi:
        lock_str += " ←past"
    else:
        lock_str += " IN" + (" (unlocked)" if unlocked else " LOCKED")
    zone_parts.append(lock_str)
    if oneway_x > 0:
        ow_str = f"Oneway: x={_fmt(oneway_x)}"
        if x < oneway_x:
            ow_str += f" →{_fmt(oneway_x - x)}m"
        else:
            ow_str += " PAST"
        zone_parts.append(ow_str)
    parts.append(" | ".join(zone_parts))
    wcm = metrics.get("wall_clearance_map")
    if isinstance(wcm, dict):
        walls = wcm.get("walls", [])
        nearby = []
        for w in walls:
            pos = w.get("position", {})
            wx_min = pos.get("x_min", 0)
            wx_max = pos.get("x_max", 0)
            dist = wx_min - x
            rel = w.get("agent_relative", {})
            if dist < -2.0:
                continue
            if dist > 6.0:
                continue
            w_idx = w.get("wall_index", "?")
            gaps = w.get("gaps", {})
            ga = gaps.get("above", {})
            gb = gaps.get("below", {})
            gap_parts = []
            if ga.get("exists"):
                gap_parts.append(f"↑{_fmt(ga.get('size_m', 0))}m")
            if gb.get("exists"):
                gap_parts.append(f"↓{_fmt(gb.get('size_m', 0))}m")
            gap_str = ",".join(gap_parts) if gap_parts else "solid"
            if rel.get("at_wall_x"):
                status = "AT"
            elif rel.get("behind_wall"):
                status = f"ahead{_fmt(dist)}m"
            else:
                status = "past"
            nearby.append(f"#{w_idx}@{_fmt(wx_min)} gap:{gap_str} {status}")
        if nearby:
            parts.append("Walls: " + " | ".join(nearby))
    wf = _m(metrics, "whisker_front")
    wu = _m(metrics, "whisker_up")
    wd = _m(metrics, "whisker_down")
    wh = metrics.get("whisker_health")
    blind = isinstance(wh, dict) and wh.get("agent_in_blind_zone", False)
    whisk_str = f"f={_fmt(wf)} u={_fmt(wu)} d={_fmt(wd)}"
    if blind:
        whisk_str += " [BLIND]"
    progress = _m(metrics, "progress_x_pct")
    parts.append(f"Whiskers: {whisk_str} | Progress: {_fmt(progress, 1)}%")
    return parts

def _section_load_distribution(metrics: Dict[str, Any]) -> List[str]:
    parts = []
    ledger = metrics.get("force_ledger")
    if not isinstance(ledger, dict):
        parts.append("No force ledger data.")
        return parts
    ch = ledger.get("channels", {})
    if not ch:
        parts.append("No channel data.")
        return parts
    cmd = ledger.get("commanded_force", {})
    cfx = _m(cmd, "fx")
    cfy = _m(cmd, "fy")
    rev = ch.get("control_reversal", {})
    if rev.get("active", False):
        eff_fx = _m(rev, "effective_commanded_fx_after_reversal", cfx)
        cli = metrics.get("control_lag_info")
        lag = _mi(cli, "control_lag_steps", 0) if isinstance(cli, dict) else 0
        lag_suffix = f" lag={lag}" if lag > 0 else ""
        parts.append(f"Cmd: ({_fmt(cfx)}, {_fmt(cfy)}) [REVERSED Fx→{_fmt(eff_fx)}{lag_suffix}]")
    else:
        cli = metrics.get("control_lag_info")
        lag = _mi(cli, "control_lag_steps", 0) if isinstance(cli, dict) else 0
        lag_suffix = f" lag={lag}" if lag > 0 else ""
        parts.append(f"Cmd: ({_fmt(cfx)}, {_fmt(cfy)}){lag_suffix}")
    active_env = []
    mag = ch.get("magnetic_floor", {})
    if mag.get("active", False):
        mfy = _m(mag, "force_fy")
        if abs(mfy) > 0.01:
            active_env.append(f"MagFloor: {_fmt(mfy)}N ↓")
    lock = ch.get("lock_gate", {})
    if lock.get("active", False):
        lfx = _m(lock, "force_fx")
        if abs(lfx) > 0.01:
            active_env.append(f"LockGate: {_fmt(lfx)}N ←")
    wind = ch.get("wind", {})
    wfx = _m(wind, "fx_total")
    if abs(wfx) > 0.01:
        active_env.append(f"Wind: {_fmt(wfx)}N")
    turb = ch.get("turbulence", {})
    if turb.get("active", False):
        tfx = _m(turb, "last_fx")
        tfy = _m(turb, "last_fy")
        if abs(tfx) > 0.01 or abs(tfy) > 0.01:
            active_env.append(f"Turb: ({_fmt(tfx, 1)}, {_fmt(tfy, 1)})")
    drag = ch.get("fluid_drag", {})
    if drag.get("active", False):
        dfx = _m(drag, "drag_fx")
        dfy = _m(drag, "drag_fy")
        if abs(dfx) > 0.001 or abs(dfy) > 0.001:
            active_env.append(f"Drag: ({_fmt(dfx, 3)}, {_fmt(dfy, 3)})")
    oneway = ch.get("oneway_assist", {})
    if oneway.get("active", False):
        ofx = _m(oneway, "force_fx")
        if abs(ofx) > 0.01:
            active_env.append(f"Oneway: +{_fmt(ofx)}N →")
    if active_env:
        parts.append("Env: " + " | ".join(active_env))
    net = ledger.get("net_forces", {})
    nfx = _m(net, "net_total_fx")
    nfy = _m(net, "net_total_fy")
    efx = _m(net, "environmental_fx")
    efy = _m(net, "environmental_fy")
    cefx = _m(net, "commanded_effective_fx")
    cefy = _m(net, "commanded_effective_fy")
    nfy_safe = float(nfy)
    if abs(nfy_safe) < 1e-9:
        nfy_safe = 0.0
    vy_sym = "↑" if nfy_safe > 0 else ("↓" if nfy_safe < 0 else "=")
    parts.append(f"Net: Σ=({_fmt(nfx)}, {_fmt(nfy)}) {vy_sym}")
    return parts

def _section_energy_power(metrics: Dict[str, Any]) -> List[str]:
    return []

def _section_constraint_profile(metrics: Dict[str, Any]) -> List[str]:
    parts = []
    unlocked = _mb(metrics, "unlocked", False)
    reached_exit = _mb(metrics, "reached_exit", False)
    consec_in_exit = _mi(metrics, "consecutive_steps_in_exit", 0)
    exit_hold_need = _exit_hold_required(metrics)
    ucs = metrics.get("unlock_condition_status")
    if isinstance(ucs, dict):
        conds = ucs.get("conditions", [])
        passed = sum(1 for c in conds if c.get("pass", False))
        total = len(conds)
        cons = ucs.get("consecutive_count", 0)
        req = ucs.get("required_consecutive", 5)
        parts.append(
            f"Unlock: {'PASS' if unlocked else 'FAIL'} "
            f"({passed}/{total} conds met, {cons}/{req} consecutive)"
        )
    else:
        parts.append(f"Unlock: {'PASS' if unlocked else 'FAIL'}")
    if reached_exit:
        dwell_ok = consec_in_exit >= exit_hold_need
        parts.append(
            f"Exit: {'PASS' if dwell_ok else 'FAIL'} "
            f"(in zone, dwell {consec_in_exit}/{exit_hold_need})"
        )
    else:
        x = _m(metrics, "agent_x")
        exit_x = _m(metrics, "exit_x_min", 15)
        exit_ylo = _m(metrics, "exit_y_min", 0.5)
        exit_yhi = _m(metrics, "exit_y_max", 2.5)
        y = _m(metrics, "agent_y")
        reasons = []
        if x < exit_x:
            reasons.append(f"x={_fmt(x)} < {_fmt(exit_x)}")
        if y < exit_ylo:
            reasons.append(f"y={_fmt(y)} < {_fmt(exit_ylo)}")
        elif y > exit_yhi:
            reasons.append(f"y={_fmt(y)} > {_fmt(exit_yhi)}")
        parts.append(f"Exit: FAIL ({'; '.join(reasons) if reasons else 'not reached'})")
    failed = _mb(metrics, "failed", False)
    fr = metrics.get("failure_reason", "")
    if failed and fr:
        parts.append(f"Terminal: {fr}")
    return parts

def _section_numerical_health(metrics: Dict[str, Any]) -> List[str]:
    issues = []
    for key, label in [
        ("agent_x", "x"), ("agent_y", "y"),
        ("agent_vx", "vx"), ("agent_vy", "vy"),
    ]:
        v = metrics.get(key)
        if v is not None and not _is_finite(v):
            issues.append(f"{label}={v}")
    vx = _m(metrics, "agent_vx")
    vy = _m(metrics, "agent_vy")
    spd = _speed(vx, vy)
    if spd > 2000.0:
        issues.append(f"speed={spd:.0f} extreme")
    elif spd > 100.0:
        issues.append(f"speed={spd:.0f} elevated")
    for key, label in [
        ("whisker_front", "wf"), ("whisker_up", "wu"), ("whisker_down", "wd"),
    ]:
        v = metrics.get(key)
        if v is not None and not _is_finite(v):
            issues.append(f"{label}={v}")
    ledger = metrics.get("force_ledger")
    if isinstance(ledger, dict):
        net = ledger.get("net_forces", {})
        for k, lbl in [("net_total_fx", "ΣFx"), ("net_total_fy", "ΣFy")]:
            try:
                if abs(float(net.get(k, 0))) > 5000.0:
                    issues.append(f"{lbl}={_fmt(net[k])} extreme")
            except (TypeError, ValueError):
                pass
    if issues:
        return ["Health: ISSUES — " + "; ".join(issues)]
    return ["Health: OK"]

def format_task_metrics(metrics: Dict[str, Any]) -> List[str]:
    global _prev_metrics
    if not metrics:
        return ["**No metrics available**"]
    if metrics.get("error"):
        return [f"**Error**: {metrics.get('error')}"]
    is_delta = _prev_metrics is not None
    all_parts: List[str] = []
    all_parts.append("## 1. Events")
    all_parts.extend(_section_temporal_chronology(metrics))
    if not is_delta or _pos_changed(metrics):
        all_parts.append("")
        all_parts.append("## 2. Spatial")
        all_parts.extend(_section_spatial(metrics))
    elif is_delta:
        all_parts.append("")
        all_parts.append("## 2. Spatial — unchanged from previous moment")
    if not is_delta or _force_changed(metrics):
        all_parts.append("")
        all_parts.append("## 3. Forces")
        all_parts.extend(_section_load_distribution(metrics))
    elif is_delta:
        all_parts.append("")
        all_parts.append("## 3. Forces — unchanged from previous moment")
    all_parts.append("")
    all_parts.append("## 5. Constraints")
    all_parts.extend(_section_constraint_profile(metrics))
    all_parts.append("")
    all_parts.append("## 6. Health")
    all_parts.extend(_section_numerical_health(metrics))
    all_parts.append("")
    success = _mb(metrics, "success", False)
    failed = _mb(metrics, "failed", False)
    fr = metrics.get("failure_reason", "")
    if success:
        all_parts.append("**Status**: SUCCESS")
    elif failed:
        all_parts.append(f"**Status**: FAILED — {fr}")
    else:
        pct = _m(metrics, "progress_x_pct")
        all_parts.append(f"**Status**: IN PROGRESS ({_fmt(pct, 1)}%)")
    _prev_metrics = dict(metrics)
    return all_parts

def get_improvement_suggestions(
    metrics: Dict[str, Any],
    score: float,
    success: bool,
    failed: bool,
    failure_reason: str = None,
    error: str = None,

) -> List[str]:
    return []
