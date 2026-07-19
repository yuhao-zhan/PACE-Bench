from typing import Any, Dict, List

import math

def _safe_float(value: Any, default: float = None) -> float:
    if value is None:
        return default
    try:
        num = float(value)
    except (TypeError, ValueError):
        return default
    return num if math.isfinite(num) else default

def _pct_margin_str(observed: float, limit: float) -> str:
    margin = limit - observed
    pct_of_limit = (observed / limit * 100.0) if limit > 0 else float('inf')
    if margin >= 0:
        return f'{observed:.2f}% / {limit:.2f}% limit ({100.0 - pct_of_limit:.1f}% margin remaining)'
    else:
        return f'{observed:.2f}% / {limit:.2f}% limit (EXCEEDED by {-margin:.2f} percentage points)'

def _section_design_violations(metrics: Dict[str, Any]) -> List[str]:
    lines: List[str] = []
    violations = metrics.get('constraint_violations') or []
    if not violations:
        return lines
    lines.append('### Design Violations')
    lines.append('')
    for i, v in enumerate(violations[:20], 1):
        lines.append(f'  {i}. {v}')
    if len(violations) > 20:
        lines.append(f'  ... and {len(violations) - 20} more')
    lines.append('')
    return lines

def _section_runtime_state(metrics: Dict[str, Any]) -> List[str]:
    lines: List[str] = []
    lines.append('### Runtime State')
    lines.append('')
    lpct = _safe_float(metrics.get('leakage_rate_percent'))
    limit_pct = _safe_float(metrics.get('leakage_limit_percent'))
    if lpct is not None:
        if limit_pct is not None:
            ok = lpct <= limit_pct
            status = 'PASS' if ok else 'FAIL'
            lines.append(f'**Leakage**: {_pct_margin_str(lpct, limit_pct)} — {status}')
        else:
            lines.append(f'**Leakage**: {lpct:.2f}%')
    broken = metrics.get('structure_broken')
    jc = metrics.get('joint_count')
    ijc = metrics.get('initial_joint_count')
    if broken is not None:
        status = 'BROKEN' if broken else 'INTACT'
        detail = ''
        if jc is not None and ijc is not None:
            try:
                lost = int(ijc) - int(jc)
                if lost > 0:
                    detail = f' ({lost} of {ijc} joints lost)'
            except (TypeError, ValueError):
                pass
        lines.append(f'**Structure**: {status}{detail}')
    init = metrics.get('initial_particle_count')
    leaked = metrics.get('leaked_particle_count')
    cp = _safe_float(metrics.get('containment_percent'))
    if init is not None:
        line = f'**Particles**: {init} initial'
        if leaked is not None:
            line += f', {leaked:.2f} leaked'
        if cp is not None:
            line += f', containment {cp:.1f}%'
        lines.append(line)
    coverage = metrics.get('beam_coverage_envelope')
    bc = metrics.get('beam_count', 0)
    if bc > 0 and isinstance(coverage, dict) and coverage:
        fill_height = _safe_float(metrics.get('reservoir_fill_height'), 7.0)
        min_bottom = _safe_float(metrics.get('min_beam_bottom_y'), 0.5)
        span = fill_height - min_bottom
        strips = []
        for sn in ['left', 'middle', 'right']:
            sd = coverage.get(sn, {})
            cnt = sd.get('beam_count', 0)
            cov_span = _safe_float(sd.get('coverage_span'), 0.0)
            if cnt > 0 and span > 0:
                pct = cov_span / span * 100.0
                strips.append(f'{sn}={cnt}b/{cov_span:.1f}m ({pct:.0f}%)')
            elif span > 0:
                strips.append(f'{sn}=0b')
        if strips:
            lines.append(f'**Coverage** ({bc} beams, y=[{min_bottom:.1f},{fill_height:.1f}]): ' + ', '.join(strips))
    elif bc == 0:
        max_bc = metrics.get('max_beam_count')
        min_bc = metrics.get('min_beam_count')
        if min_bc is not None and max_bc is not None:
            lines.append(f'**Coverage**: 0 beams placed (need {min_bc}–{max_bc})')
    mass = _safe_float(metrics.get('structure_mass'))
    max_mass = _safe_float(metrics.get('max_structure_mass'))
    if mass is not None and max_mass is not None and max_mass > 0:
        pct = mass / max_mass * 100.0
        jc_static = metrics.get('joint_count')
        max_jc = metrics.get('max_joint_count')
        line = f'**Mass**: {mass:.1f}/{max_mass:.1f} kg ({pct:.1f}%)'
        if jc_static is not None and max_jc is not None:
            line += f' | **Joints**: {jc_static}/{max_jc}'
        lines.append(line)
    break_events = metrics.get('joint_break_events')
    if isinstance(break_events, list) and break_events:
        lines.append('')
        lines.append(f'**Joint Failures** ({len(break_events)} total):')
        for i, be in enumerate(break_events[:8], 1):
            step = be.get('step', '?')
            force = _safe_float(be.get('force'))
            threshold = _safe_float(be.get('threshold'), 50000.0)
            anchor = be.get('anchor', ('?', '?'))
            pct = (force / threshold * 100.0) if force is not None and threshold > 0 else 0.0
            lines.append(
                f'  {i}. Step {step}: anchor ({anchor[0]:.2f}, {anchor[1]:.2f}) '
                f'broke at {force:.1f} N ({pct:.1f}% of {threshold:.0f} N)'
            )
        if len(break_events) > 8:
            lines.append(f'  ... and {len(break_events) - 8} more failures')
    joint_peak = metrics.get('joint_peak_forces')
    force_limit = _safe_float(metrics.get('joint_force_limit'), 50000.0)
    break_steps = metrics.get('joint_break_consecutive_steps', 3)
    if isinstance(joint_peak, list) and joint_peak:
        sorted_joints = sorted(joint_peak, key=lambda x: x.get('peak_force', 0.0), reverse=True)
        critical = []
        elevated = []
        nominal_count = 0
        for jp in sorted_joints:
            peak = _safe_float(jp.get('peak_force'), 0.0)
            pct = (peak / force_limit * 100.0) if force_limit > 0 else 0.0
            if pct >= 80.0:
                critical.append(jp)
            elif pct >= 50.0:
                elevated.append(jp)
            else:
                nominal_count += 1
        lines.append('')
        lines.append(f'**Joint Stress** ({len(sorted_joints)} joints, {force_limit:.0f} N limit, breaks after {break_steps} consecutive steps over):')
        tier_parts = []
        if critical:
            tier_parts.append(f'CRITICAL (>80%): {len(critical)}')
        if elevated:
            tier_parts.append(f'ELEVATED (50-80%): {len(elevated)}')
        if nominal_count:
            tier_parts.append(f'NOMINAL (<50%): {nominal_count}')
        lines.append('  Tiers: ' + ', '.join(tier_parts))
        for jp in critical + elevated:
            peak = _safe_float(jp.get('peak_force'), 0.0)
            pct = (peak / force_limit * 100.0) if force_limit > 0 else 0.0
            tier = 'CRITICAL' if pct >= 80.0 else 'ELEVATED'
            anchor = jp.get('anchor', ('?', '?'))
            margin = force_limit - peak
            lines.append(
                f'  [{tier}] {peak:.1f} N ({pct:.1f}%, margin {margin:+.1f} N) '
                f'at ({anchor[0]:.2f}, {anchor[1]:.2f})'
            )
        if not critical and not elevated and sorted_joints:
            highest = sorted_joints[0]
            hp = _safe_float(highest.get('peak_force'), 0.0)
            hpct = (hp / force_limit * 100.0) if force_limit > 0 else 0.0
            lines.append(f'  All nominal. Highest: {hp:.1f} N ({hpct:.1f}%)')
    leak_height = metrics.get('leak_height_distribution')
    if isinstance(leak_height, dict) and leak_height:
        total_leak = sum(v.get('count', 0.0) for v in leak_height.values())
        if total_leak > 0:
            lines.append('')
            parts = []
            for label, data in sorted(leak_height.items()):
                cnt = data.get('count', 0.0)
                yr = data.get('y_range', (0, 0))
                pct = cnt / total_leak * 100.0 if total_leak > 0 else 0.0
                parts.append(f'{label} y=[{yr[0]:.1f},{yr[1]:.1f})={cnt:.1f} ({pct:.0f}%)')
            lines.append(f'**Leak Distribution** ({total_leak:.1f} total): ' + ', '.join(parts))
    timeline = metrics.get('disturbance_timeline')
    if isinstance(timeline, list) and timeline:
        event_count = sum(len(entry.get('events', [])) for entry in timeline)
        if timeline:
            first_step = timeline[0].get('step', '?')
            last_step = timeline[-1].get('step', '?')
            lines.append(f'**Events scheduled**: {event_count} disturbances over steps {first_step}–{last_step}')
    fr = metrics.get('failure_reason')
    if fr and str(fr).strip():
        lines.append('')
        lines.append(f'**Terminal reason**: {fr}')
    return lines

def _section_numerical_health(metrics: Dict[str, Any]) -> List[str]:
    lines: List[str] = []
    warnings = metrics.get('numerical_health_warnings')
    if not isinstance(warnings, list) or not warnings:
        return lines
    lines.append('### Numerical Health — WARNINGS')
    lines.append(f'  **{len(warnings)} warning(s)**:')
    for w in warnings[:10]:
        wtype = w.get('type', 'unknown')
        pos = w.get('body_pos', ('?', '?'))
        speed = w.get('speed')
        velocity = w.get('velocity')
        if 'non_finite' in wtype:
            lines.append(f'  - [{wtype}] at ({pos[0]:.3f}, {pos[1]:.3f})')
        elif speed is not None:
            lines.append(f'  - [{wtype}] speed {speed:.1f} m/s at ({pos[0]:.3f}, {pos[1]:.3f})')
        elif velocity is not None:
            lines.append(f'  - [{wtype}] vel ({velocity[0]:.3f}, {velocity[1]:.3f}) at ({pos[0]:.3f}, {pos[1]:.3f})')
        else:
            lines.append(f'  - [{wtype}] at ({pos[0]:.3f}, {pos[1]:.3f})')
    if len(warnings) > 10:
        lines.append(f'  ... and {len(warnings) - 10} more')
    return lines

def format_task_metrics(metrics: Dict[str, Any]) -> List[str]:
    if not metrics:
        return ['(No evaluation metrics available.)']
    all_lines: List[str] = []
    violations_lines = _section_design_violations(metrics)
    all_lines.extend(violations_lines)
    runtime_lines = _section_runtime_state(metrics)
    all_lines.extend(runtime_lines)
    health_lines = _section_numerical_health(metrics)
    if health_lines:
        all_lines.append('')
        all_lines.extend(health_lines)
    return all_lines

def get_improvement_suggestions(
    metrics: Dict[str, Any],
    score: float,
    success: bool,
    failed: bool,
    failure_reason: str = None,
    error: str = None,

) -> List[str]:
    suggestions: List[str] = []
    if not metrics:
        return suggestions
    if error:
        return suggestions
    violations = metrics.get('constraint_violations') or []
    if violations:
        num = len(violations)
        if num <= 3:
            suggestions.append(
                f'- Design validation failed with {num} constraint violation(s). '
                f'Review the Design Constraint Validation section above for exact limits and margins.'
            )
        else:
            suggestions.append(
                f'- Design validation failed with {num} constraint violations. '
                f'The most impactful violations (earliest in the list) should be resolved first.'
            )
        return suggestions
    broken = metrics.get('structure_broken')
    if broken:
        suggestions.append(
        )
    lpct = _safe_float(metrics.get('leakage_rate_percent'))
    limit_pct = _safe_float(metrics.get('leakage_limit_percent'))
    if lpct is not None and limit_pct is not None and lpct > limit_pct:
        suggestions.append(
            f'- Leakage rate {lpct:.2f}% exceeded the {limit_pct:.2f}% limit. '
        )
    return suggestions
