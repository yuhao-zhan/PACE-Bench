from __future__ import annotations

import re

from typing import Any, Dict, List, Optional

from pace_bench.tasks.categories.Category5_Cybernetics_Control.C_06.environment import (
    DEFAULT_WHEEL_MASS_KG,
    DEFAULT_WHEEL_RADIUS_M,
    MEAN_SPEED_ERROR_THRESHOLD,
    REGULATION_START_STEP,
    STALL_SPEED_THRESHOLD,
    STALL_STEPS_THRESHOLD,
    STEP_LOAD_AT_STEP,
    TARGET_SPEED_RAD_S,
    TORQUE_DEADZONE,
    TORQUE_LIMIT_AT_ZERO,

)

def _c06_mutated_curriculum_union_suffix() -> str:
    return """

Sensors indicate that this region exhibits non-standard physical properties.
While the following variables **MIGHT** have changed from the initial environment, **NOT ALL** of them will necessarily be mutated in any given task. You must use active interaction and environmental feedback to deduce which specific conditions apply:
- **Measurement delay**: Latency in the rotational speed measurements may occur.
- **Torque limit**: The maximum torque available at low speed may differ.
- **Sustained load onset**: The timing of additional load application may differ.
- **Torque deadzone**: The range of control inputs that yield zero motor response may differ.
- **Rotational resistance**: Speed-dependent resisting torque may differ.
- **Mechanical resistance profile**: Angle-dependent resisting torque may differ.
- **Static friction behavior**: Low-speed resisting torque behavior may differ.

**Discovery via feedback**: Your objective is to identify the underlying physical rules of this specific environment through trial and reasoning. Initial standard solutions may fail; analyze the failure mode (e.g., how the system stalls or oscillates) to infer the hidden constraints and adapt your control design.
"""

def _c06_wheel_line(
    target_mass: float,
    base_mass: float,
    target_radius: float,
    base_radius: float,

) -> str:
    if abs(target_mass - base_mass) < 1e-9:
        mass_part = f"{target_mass:g} kg"
    else:
        mass_part = f"{target_mass:g} kg (originally {base_mass:g} kg in the source environment)"
    if abs(target_radius - base_radius) < 1e-9:
        rad_part = f"{target_radius:g} m"
    else:
        rad_part = f"{target_radius:g} m (originally {base_radius:g} m in the source environment)"
    return f"Wheel: {mass_part}, {rad_part}"

_WHEEL_BLOCK_PATTERN = r"- \*\*Wheel\*\*:.*?\)"

def _c06_apply_target_speed_line(description: str, tt: float, bt: float) -> str:
    if abs(tt - bt) < 1e-12:
        return description
    pat = r"(-\ \*\*Target Speed\*\*:.*?)\d+\.?\d*(\s*rad/s)"
    if not re.search(pat, description):
        return description
    return re.sub(
        pat,
        rf"\g<1>{tt:g} (originally {bt:g} in the source environment)\2",
        description,
        count=1,
    )

def _c06_apply_regulation_start(description: str, tr: int, br: int) -> str:
    if tr == br:
        return description
    d = re.sub(
        r"A startup phase of \d+ steps(?: \(originally \d+ steps in the source environment\))? precedes",
        f"A startup phase of {tr} steps (originally {br} steps in the source environment) precedes",
        description,
        count=1,
    )
    d = re.sub(
        r"step index \u2265 \d+(?: \(originally \d+ in the source environment\))?(?= \(after startup\))",
        f"step index \u2265 {tr} (originally {br} in the source environment)",
        d,
        count=1,
    )
    return d

def update_task_description_for_visible_changes(
    base_description: str,
    target_terrain_config: Dict[str, Any],
    base_terrain_config: Dict[str, Any],
    target_physics_config: Optional[Dict[str, Any]] = None,
    base_physics_config: Optional[Dict[str, Any]] = None,
    *,
    stage: Optional[Dict[str, Any]] = None,

) -> str:
    target_terrain_config = dict(target_terrain_config or {})
    base_terrain_config = dict(base_terrain_config or {})
    tp = dict(target_physics_config or {})
    bp = dict(base_physics_config or {})
    if stage is not None:
        tp = {**tp, **(stage.get("physics_config") or {})}
    description = base_description
    bm = float(base_terrain_config.get("wheel_mass", DEFAULT_WHEEL_MASS_KG))
    brad = float(base_terrain_config.get("wheel_radius", DEFAULT_WHEEL_RADIUS_M))
    tm = float(target_terrain_config.get("wheel_mass", DEFAULT_WHEEL_MASS_KG))
    trad = float(target_terrain_config.get("wheel_radius", DEFAULT_WHEEL_RADIUS_M))
    if abs(tm - bm) >= 1e-9 or abs(trad - brad) >= 1e-9:
        description = re.sub(_WHEEL_BLOCK_PATTERN, _c06_wheel_line(tm, bm, trad, brad), description, count=1, flags=re.DOTALL)
    bt = float(base_terrain_config.get("target_speed_rad_s", TARGET_SPEED_RAD_S))
    tt = float(target_terrain_config.get("target_speed_rad_s", TARGET_SPEED_RAD_S))
    description = _c06_apply_target_speed_line(description, tt, bt)
    brs = int(base_terrain_config.get("regulation_start_step", REGULATION_START_STEP))
    trs = int(target_terrain_config.get("regulation_start_step", REGULATION_START_STEP))
    description = _c06_apply_regulation_start(description, trs, brs)
    btl = float(bp.get("torque_limit_at_zero", TORQUE_LIMIT_AT_ZERO))
    ttl = float(tp.get("torque_limit_at_zero", TORQUE_LIMIT_AT_ZERO))
    if abs(btl - ttl) > 1e-9:
        description = re.sub(r"at rest, the limit is \d+\.?\d* N·m", f"at rest, the limit is {ttl:g} N·m (originally {btl:g} N·m in the source environment)", description)
    btd = float(bp.get("torque_deadzone", TORQUE_DEADZONE))
    ttd = float(tp.get("torque_deadzone", TORQUE_DEADZONE))
    if abs(btd - ttd) > 1e-9:
        description = re.sub(r"\*\*deadzone\*\* of \d+\.?\d* N·m", f"**deadzone** of {ttd:g} N·m (originally {btd:g} N·m in the source environment)", description)
    bsl = int(bp.get("step_load_at_step", STEP_LOAD_AT_STEP))
    tsl = int(tp.get("step_load_at_step", STEP_LOAD_AT_STEP))
    if bsl != tsl:
        description = re.sub(
            rf"(at simulation step ){bsl}(, beyond the nominal)",
            rf"\g<1>{tsl} (originally {bsl} in the source environment)\2",
            description,
            count=1,
        )
        description = re.sub(
            rf"(activates at step ){bsl}(\.)",
            rf"\g<1>{tsl} (originally {bsl} in the source environment)\2",
            description,
            count=1,
        )
    return description

def _c06_stall_success_line(ts: float, bs: float, tst: int, bst: int) -> str:
    sp = (
        f"{ts} rad/s"
        if abs(ts - bs) < 1e-12
        else f"{ts} rad/s (originally {bs} rad/s in the source environment)"
    )
    if tst == bst:
        step_clause = f"{tst} or more consecutive steps"
    else:
        step_clause = (
            f"{tst} or more consecutive steps (originally {bst} in the source environment)"
        )
    return (
        f"2. **No Stall**: From the start of the episode through the end, sustained **true** instantaneous angular "
        f"speed below {sp} for {step_clause} counts as failure."
    )

def update_success_criteria_for_visible_changes(
    base_success_criteria: str,
    target_terrain_config: Dict[str, Any],
    base_terrain_config: Dict[str, Any],
    target_physics_config: Optional[Dict[str, Any]] = None,
    base_physics_config: Optional[Dict[str, Any]] = None,
    *,
    stage: Optional[Dict[str, Any]] = None,

) -> str:
    target_terrain_config = target_terrain_config or {}
    base_terrain_config = base_terrain_config or {}
    tp = dict(target_physics_config or {})
    bp = dict(base_physics_config or {})
    if stage is not None:
        tp = {**tp, **(stage.get("physics_config") or {})}
    c = base_success_criteria
    bm = float(base_terrain_config.get("mean_speed_error_threshold", MEAN_SPEED_ERROR_THRESHOLD))
    tm = float(target_terrain_config.get("mean_speed_error_threshold", MEAN_SPEED_ERROR_THRESHOLD))
    if abs(tm - bm) > 1e-15:
        pat = r"1\. \*\*Speed Regulation\*\*:.*?must stay <= [\d.]+ rad/s\."
        if re.search(pat, c, flags=re.DOTALL):
            rep = (
                f"1. **Speed Regulation**: Mean absolute deviation of the wheel's **true** instantaneous angular velocity from the commanded target during the regulation phase (after startup) must stay <= {tm:g} rad/s (originally {bm:g} rad/s in the source environment)."
            )
            c = re.sub(pat, rep, c, count=1, flags=re.DOTALL)
    bs = float(base_terrain_config.get("stall_speed_threshold", STALL_SPEED_THRESHOLD))
    ts = float(target_terrain_config.get("stall_speed_threshold", STALL_SPEED_THRESHOLD))
    bst = int(base_terrain_config.get("stall_steps_threshold", STALL_STEPS_THRESHOLD))
    tst = int(target_terrain_config.get("stall_steps_threshold", STALL_STEPS_THRESHOLD))
    if abs(ts - bs) > 1e-12 or tst != bst:
        stall_pat = r"2\. \*\*No Stall\*\*:.*counts as failure\."
        if re.search(stall_pat, c, flags=re.DOTALL):
            c = re.sub(
                stall_pat,
                _c06_stall_success_line(ts, bs, tst, bst),
                c,
                count=1,
                flags=re.DOTALL,
            )
    bp_td = float(bp.get("torque_deadzone", TORQUE_DEADZONE))
    tp_td = float(tp.get("torque_deadzone", TORQUE_DEADZONE))
    if abs(bp_td - tp_td) > 1e-9:
        td_pat = r"\*\*Torque Deadzone\*\*: TORQUE_DEADZONE = \d+\.?\d* N·m\."
        if re.search(td_pat, c):
            c = re.sub(
                td_pat,
                f"**Torque Deadzone**: TORQUE_DEADZONE = {tp_td:g} N·m (originally {bp_td:g} N·m in the source environment).",
                c,
            )
    return c

def get_c06_curriculum_stages() -> List[Dict[str, Any]]:
    task_description_suffix = _c06_mutated_curriculum_union_suffix()
    return [
        {
            "stage_id": "Stage-1",
            "title": "Curriculum variant 1",
            "mutation_description": "Curriculum Stage-1 physics overrides.",
            "task_description_suffix": task_description_suffix,
            "terrain_config": {},
            "physics_config": {
                "k_drag": 2.7,
            },
        },
        {
            "stage_id": "Stage-2",
            "title": "Curriculum variant 2",
            "mutation_description": "Curriculum Stage-2 physics overrides.",
            "task_description_suffix": task_description_suffix,
            "terrain_config": {},
            "physics_config": {
                "k_drag": 2.6,
            },
        },
        {
            "stage_id": "Stage-3",
            "title": "Curriculum variant 3",
            "mutation_description": "Curriculum Stage-3 physics overrides.",
            "task_description_suffix": task_description_suffix,
            "terrain_config": {},
            "physics_config": {
                "step_load_at_step": 500,
                "torque_limit_at_zero": 2.9,
                "k_drag": 2.4,
                "torque_deadzone": 2.6,
                "measure_delay_steps": 7,
                "cogging_amplitude": 2.2,
            },
        },
        {
            "stage_id": "Stage-4",
            "title": "Curriculum variant 4",
            "mutation_description": "Curriculum Stage-4 physics overrides.",
            "task_description_suffix": task_description_suffix,
            "terrain_config": {},
            "physics_config": {
                "measure_delay_steps": 7,
                "torque_deadzone": 3.0,
                "torque_limit_at_zero": 3.5,
                "k_drag": 1.0,
                "cogging_amplitude": 4.0,
                "stiction_factor": 2.2,
            },
        },
    ]
