from __future__ import annotations

import importlib.util

import os

import re

import math

import warnings

from typing import Any, Dict, List, Optional

_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "environment.py")

_env_spec = importlib.util.spec_from_file_location(
    "davinci_category5_c02_environment_stages_only",
    _env_path,

)

_env_mod = importlib.util.module_from_spec(_env_spec)

assert _env_spec.loader is not None

_env_spec.loader.exec_module(_env_mod)

DEFAULT_BARRIER_X_LEFT = _env_mod.BARRIER_X_LEFT

DEFAULT_BARRIER_X_RIGHT = _env_mod.BARRIER_X_RIGHT

DEFAULT_BARRIER_Y_BOTTOM = _env_mod.BARRIER_Y_BOTTOM

DEFAULT_BARRIER_Y_TOP = _env_mod.BARRIER_Y_TOP

ENV_DEFAULT_MAX_LANDING_ANGLE_RAD = _env_mod.MAX_LANDING_ANGLE

DEFAULT_MAX_SAFE_VERTICAL_SPEED = _env_mod.MAX_SAFE_VERTICAL_SPEED

DEFAULT_MAX_THRUST = _env_mod.MAX_THRUST

DEFAULT_MAX_TORQUE = _env_mod.MAX_TORQUE

DEFAULT_MIN_FUEL_REMAINING_AT_LANDING = _env_mod.MIN_FUEL_REMAINING_AT_LANDING

DEFAULT_PLATFORM_AMPLITUDE = _env_mod.PLATFORM_AMPLITUDE

DEFAULT_PLATFORM_CENTER_BASE = _env_mod.PLATFORM_CENTER_BASE

DEFAULT_PLATFORM_HALF_WIDTH = _env_mod.PLATFORM_HALF_WIDTH

DEFAULT_PLATFORM_PERIOD = _env_mod.PLATFORM_PERIOD

DEFAULT_SPAWN_X = _env_mod.SPAWN_X

DEFAULT_SPAWN_Y = _env_mod.SPAWN_Y

DEFAULT_THRUST_DELAY_STEPS = _env_mod.THRUST_DELAY_STEPS

DEFAULT_TOTAL_FUEL_IMPULSE = _env_mod.TOTAL_FUEL_IMPULSE

DEFAULT_MAX_EPISODE_STEPS = _env_mod.MAX_EPISODE_STEPS

DEFAULT_TIME_STEP = _env_mod.DEFAULT_TIME_STEP

DEFAULT_TIME_STEP_LABEL = _env_mod.DEFAULT_TIME_STEP_LABEL

DEFAULT_LAND_TOLERANCE = _env_mod.LAND_TOLERANCE

DEFAULT_LANDER_MASS = _env_mod.LANDER_MASS

DEFAULT_LANDER_HALF_WIDTH = _env_mod.LANDER_HALF_WIDTH

DEFAULT_LANDER_HALF_HEIGHT = _env_mod.LANDER_HALF_HEIGHT

DEFAULT_GROUND_Y_TOP = _env_mod.GROUND_Y_TOP

DEFAULT_GROUND_LENGTH = _env_mod.GROUND_LENGTH

DEFAULT_GROUND_SLAB_HEIGHT = _env_mod.GROUND_SLAB_HEIGHT

CURRICULUM_STAGE2_MAX_LANDING_ANGLE_RAD = _env_mod.CURRICULUM_STAGE2_MAX_LANDING_ANGLE_RAD

del _env_path, _env_spec, _env_mod

_PROMPT_SCALAR = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"

_FRACTION_OR_SCALAR = r"(?:" + _PROMPT_SCALAR + r"/" + _PROMPT_SCALAR + r"|" + _PROMPT_SCALAR + r")"

_ORIG_ANY = r"(?: \(originally .+? in the source environment\))?"

def _format_time_step_for_prompt(seconds: float) -> str:
    common = ((1, 60), (1, 30), (1, 120), (1, 100), (1, 50))
    for num, den in common:
        if abs(seconds - num / float(den)) < 1e-9:
            return f"{num}/{den}"
    if abs(seconds - DEFAULT_TIME_STEP) < 1e-9:
        return DEFAULT_TIME_STEP_LABEL
    return f"{seconds:g}"

def _config_float(
    physics: Dict[str, Any],
    terrain: Dict[str, Any],
    key: str,
    default: float,

) -> float:
    if key in physics and physics[key] is not None:
        return float(physics[key])
    if key in terrain and terrain[key] is not None:
        return float(terrain[key])
    return float(default)

def update_task_description_for_visible_changes(
    base_description: str,
    target_terrain_config: Dict[str, Any],
    base_terrain_config: Dict[str, Any],
    target_physics_config: Dict[str, Any] = None,
    base_physics_config: Dict[str, Any] = None,
    *,
    stage: Optional[Dict[str, Any]] = None,

) -> str:
    description = base_description
    target_terrain_config = dict(target_terrain_config or {})
    base_terrain_config = dict(base_terrain_config or {})
    if stage is not None:
        target_terrain_config = {
            **(stage.get("terrain_config") or {}),
            **target_terrain_config,
        }
    target_physics_config = dict(target_physics_config or {})
    base_physics_config = dict(base_physics_config or {})
    if stage is not None:
        sp = stage.get("physics_config") or {}
        target_physics_config = {**sp, **target_physics_config}
    target_sx = float(target_terrain_config.get("spawn_x", DEFAULT_SPAWN_X))
    base_sx = float(base_terrain_config.get("spawn_x", DEFAULT_SPAWN_X))
    target_sy = float(target_terrain_config.get("spawn_y", DEFAULT_SPAWN_Y))
    base_sy = float(base_terrain_config.get("spawn_y", DEFAULT_SPAWN_Y))
    if target_sx != base_sx or target_sy != base_sy:
        _spawn_orig_m = rf"(?: \(originally {_PROMPT_SCALAR} m in the source environment\))?"
        p_spawn = (
            r"spawn x=" + _PROMPT_SCALAR + r", y=" + _PROMPT_SCALAR + r" m" + _spawn_orig_m
        )
        if re.search(p_spawn, description):
            def _spawn_repl(m: re.Match) -> str:
                ox = (
                    f" (originally x={base_sx:g} m in the source environment)"
                    if abs(target_sx - base_sx) > 1e-9
                    else ""
                )
                oy = (
                    f" (originally y={base_sy:g} m in the source environment)"
                    if abs(target_sy - base_sy) > 1e-9
                    else ""
                )
                return f"(spawn x={target_sx:g} m, y={target_sy:g} m){ox}{oy}"
            description = re.sub(p_spawn, _spawn_repl, description)
        else:
            warnings.warn(
                "task_description left unchanged.",
                RuntimeWarning,
                stacklevel=2,
            )
    target_mass = float(target_terrain_config.get("lander_mass", DEFAULT_LANDER_MASS))
    base_mass = float(base_terrain_config.get("lander_mass", DEFAULT_LANDER_MASS))
    if target_mass != base_mass:
        p_mass = (
            r"Mass " + _PROMPT_SCALAR + r" kg"
        )
        if re.search(p_mass, description):
            description = re.sub(
                p_mass,
                lambda m: f"Mass {target_mass:.0f} kg (originally {base_mass:.0f} kg in the source environment)",
                description,
            )
        else:
            warnings.warn(
                "task_description left unchanged.",
                RuntimeWarning,
                stacklevel=2,
            )
    target_lhw = float(target_terrain_config.get("lander_half_width", DEFAULT_LANDER_HALF_WIDTH))
    base_lhw = float(base_terrain_config.get("lander_half_width", DEFAULT_LANDER_HALF_WIDTH))
    target_lhh = float(target_terrain_config.get("lander_half_height", DEFAULT_LANDER_HALF_HEIGHT))
    base_lhh = float(base_terrain_config.get("lander_half_height", DEFAULT_LANDER_HALF_HEIGHT))
    if target_lhw != base_lhw or target_lhh != base_lhh:
        target_fw, target_fh = 2.0 * target_lhw, 2.0 * target_lhh
        base_fw, base_fh = 2.0 * base_lhw, 2.0 * base_lhh
        def _hull_m_seg(target: float, base: float) -> str:
            if abs(target - base) > 1e-9:
                return f"{target:.1f} m (originally {base:.1f} m in the source environment)"
            return f"{target:.1f} m"
        p_hull = re.compile(
            r"(rectangular hull ).+?(\)\.)( Starting position \(spawn x=)",
        )
        if p_hull.search(description):
            core = f"{target_fw:.1f} m × {target_fh:.1f} m (half-width {target_lhw:.1f} m, half-height {target_lhh:.1f} m)"
            description = p_hull.sub(
                lambda m: f"{m.group(1)}{core}{m.group(2)}{m.group(3)}",
                description,
                count=1,
            )
        else:
            warnings.warn(
                "task_description left unchanged.",
                RuntimeWarning,
                stacklevel=2,
            )
    target_gy = float(target_terrain_config.get("ground_y_top", DEFAULT_GROUND_Y_TOP))
    base_gy = float(base_terrain_config.get("ground_y_top", DEFAULT_GROUND_Y_TOP))
    target_glen = float(target_terrain_config.get("ground_length", DEFAULT_GROUND_LENGTH))
    base_glen = float(base_terrain_config.get("ground_length", DEFAULT_GROUND_LENGTH))
    target_gslab = float(
        target_terrain_config.get("ground_slab_height", DEFAULT_GROUND_SLAB_HEIGHT)
    )
    base_gslab = float(
        base_terrain_config.get("ground_slab_height", DEFAULT_GROUND_SLAB_HEIGHT)
    )
    if target_gy != base_gy or target_glen != base_glen or target_gslab != base_gslab:
        p_ground = (
            r"- \*\*Ground\*\*: The landing surface \(ground and platform\) is at y=" + _PROMPT_SCALAR + r" m; the static ground fixture extends downward from that plane by " + _PROMPT_SCALAR + r" m \(slab thickness\)\. The terrain extends horizontally over roughly " + _PROMPT_SCALAR + r" m\."
        )
        if re.search(p_ground, description):
            def _ground_repl(m: re.Match) -> str:
                y_o = (
                    f" (originally {base_gy:.1f} m in the source environment)"
                    if abs(target_gy - base_gy) > 1e-9
                    else ""
                )
                slab_o = (
                    f" (originally {base_gslab:.1f} m in the source environment)"
                    if abs(target_gslab - base_gslab) > 1e-9
                    else ""
                )
                len_o = (
                    f" (originally {base_glen:.0f} m in the source environment)"
                    if abs(target_glen - base_glen) > 1e-9
                    else ""
                )
                return (
                    f"- **Ground**: The landing surface (ground and platform) is at y={target_gy:.1f} m{y_o}; "
                    f"the static ground fixture extends downward from that plane by {target_gslab:.1f} m (slab thickness){slab_o}. "
                    f"The terrain extends horizontally over roughly {target_glen:.0f} m{len_o}. "
                    f"Touchdown is detected when the craft's lowest point is within {DEFAULT_LAND_TOLERANCE:.2f} m of the ground surface."
                )
            description = re.sub(p_ground, _ground_repl, description)
        else:
            warnings.warn(
                "regex did not match; task_description left unchanged.",
                RuntimeWarning,
                stacklevel=2,
            )
    target_bl = _config_float(
        target_physics_config,
        target_terrain_config,
        "barrier_x_left",
        DEFAULT_BARRIER_X_LEFT,
    )
    base_bl = _config_float(
        base_physics_config,
        base_terrain_config,
        "barrier_x_left",
        DEFAULT_BARRIER_X_LEFT,
    )
    target_br = _config_float(
        target_physics_config,
        target_terrain_config,
        "barrier_x_right",
        DEFAULT_BARRIER_X_RIGHT,
    )
    base_br = _config_float(
        base_physics_config,
        base_terrain_config,
        "barrier_x_right",
        DEFAULT_BARRIER_X_RIGHT,
    )
    if target_bl != base_bl or target_br != base_br:
        p_bx = (
            r"x in \[(" + _PROMPT_SCALAR + r", " + _PROMPT_SCALAR + r")\] m"
        )
        if re.search(p_bx, description):
            new_interior = f"{target_bl:.1f}, {target_br:.1f}"
            orig = (
                f" (originally {base_bl:.1f}, {base_br:.1f} in the source environment)"
            )
            description = re.sub(
                p_bx,
                f"x in [{new_interior}] m{orig}.",
                description,
            )
        else:
            warnings.warn(
                "task_description left unchanged.",
                RuntimeWarning,
                stacklevel=2,
            )
    target_barrier_bottom = _config_float(
        target_physics_config,
        target_terrain_config,
        "barrier_y_bottom",
        DEFAULT_BARRIER_Y_BOTTOM,
    )
    base_barrier_bottom = _config_float(
        base_physics_config,
        base_terrain_config,
        "barrier_y_bottom",
        DEFAULT_BARRIER_Y_BOTTOM,
    )
    target_barrier_top = _config_float(
        target_physics_config,
        target_terrain_config,
        "barrier_y_top",
        DEFAULT_BARRIER_Y_TOP,
    )
    base_barrier_top = _config_float(
        base_physics_config,
        base_terrain_config,
        "barrier_y_top",
        DEFAULT_BARRIER_Y_TOP,
    )
    if target_barrier_top != base_barrier_top:
        p_lower = (
            r"lower bound is y=" + _PROMPT_SCALAR + r" m"
        )
        if re.search(p_lower, description):
            description = re.sub(
                p_lower,
                lambda m: f"lower bound is y={target_barrier_top:.1f} m (originally {base_barrier_top:.1f} m in the source environment)",
                description,
            )
        else:
            warnings.warn(
                "task_description left unchanged.",
                RuntimeWarning,
                stacklevel=2,
            )
    if target_barrier_bottom != base_barrier_bottom:
        p_upper = (
            r"upper bound is y=" + _PROMPT_SCALAR + r" m"
        )
        if re.search(p_upper, description):
            description = re.sub(
                p_upper,
                lambda m: f"upper bound is y={target_barrier_bottom:.1f} m (originally {base_barrier_bottom:.1f} m in the source environment)",
                description,
            )
        else:
            warnings.warn(
                "task_description left unchanged.",
                RuntimeWarning,
                stacklevel=2,
            )
    target_pc = float(
        target_physics_config.get("platform_center_base", DEFAULT_PLATFORM_CENTER_BASE)
    )
    base_pc = float(
        base_physics_config.get("platform_center_base", DEFAULT_PLATFORM_CENTER_BASE)
    )
    target_pa = float(
        target_physics_config.get("platform_amplitude", DEFAULT_PLATFORM_AMPLITUDE)
    )
    base_pa = float(
        base_physics_config.get("platform_amplitude", DEFAULT_PLATFORM_AMPLITUDE)
    )
    target_pp = float(
        target_physics_config.get("platform_period", DEFAULT_PLATFORM_PERIOD)
    )
    base_pp = float(base_physics_config.get("platform_period", DEFAULT_PLATFORM_PERIOD))
    def _plat_seg(t: float, b: float, unit: str) -> str:
        if abs(t - b) < 1e-9:
            return f"{t:.1f}{unit}"
        return f"{t:.1f}{unit} (originally {b:.1f}{unit} in the source environment)"
    if target_pc != base_pc or target_pa != base_pa or target_pp != base_pp:
        p_plat = re.compile(
            r"(Its center oscillates around x=.*?)(?=\s*The valid landing area is)",
            re.DOTALL,
        )
        if p_plat.search(description):
            new_plat = (
                f"Its center oscillates around x={target_pc:.1f} m with an amplitude of {target_pa:.1f} m and a period of {target_pp:.1f} s"
            )
            description = p_plat.sub(new_plat, description, count=1)
        else:
            warnings.warn(
                "task_description left unchanged.",
                RuntimeWarning,
                stacklevel=2,
            )
    target_hw = target_physics_config.get(
        "platform_half_width", DEFAULT_PLATFORM_HALF_WIDTH
    )
    base_hw = base_physics_config.get(
        "platform_half_width", DEFAULT_PLATFORM_HALF_WIDTH
    )
    if target_hw != base_hw:
        target_width = 2.0 * target_hw
        base_width = 2.0 * base_hw
        pattern = (
            r"valid landing area is .*? total \(center ± " + _PROMPT_SCALAR + r" m\)"
        )
        if re.search(pattern, description):
            description = re.sub(
                pattern,
                lambda m: f"valid landing area is {target_width:.1f} m total (center ± {target_hw:.1f} m) (originally {base_width:.1f} m total in the source environment)",
                description,
            )
        else:
            warnings.warn(
                "task_description left unchanged.",
                RuntimeWarning,
                stacklevel=2,
            )
    target_fuel = target_physics_config.get(
        "total_fuel_impulse", DEFAULT_TOTAL_FUEL_IMPULSE
    )
    base_fuel = base_physics_config.get(
        "total_fuel_impulse", DEFAULT_TOTAL_FUEL_IMPULSE
    )
    if target_fuel != base_fuel:
        def _fmt_ns(v: float) -> str:
            v = float(v)
            return str(int(v)) if abs(v - round(v)) < 1e-9 else f"{v:g}"
        pattern = (
            r"Total fuel impulse is " + _PROMPT_SCALAR + r" N·s"
        )
        if re.search(pattern, description):
            description = re.sub(
                pattern,
                lambda m: f"Total fuel impulse is {_fmt_ns(target_fuel)} N·s (originally {_fmt_ns(base_fuel)} N·s in the source environment)",
                description,
            )
        else:
            warnings.warn(
                "task_description left unchanged.",
                RuntimeWarning,
                stacklevel=2,
            )
    target_max_thrust = target_physics_config.get("max_thrust", DEFAULT_MAX_THRUST)
    base_max_thrust = base_physics_config.get("max_thrust", DEFAULT_MAX_THRUST)
    if target_max_thrust != base_max_thrust:
        pattern = (
            r"max " + _PROMPT_SCALAR + r" N\);"
        )
        if re.search(pattern, description):
            description = re.sub(
                pattern,
                lambda m: f"max {target_max_thrust:g} N); (originally {base_max_thrust:g} N in the source environment)",
                description,
            )
        else:
            warnings.warn(
                "task_description left unchanged.",
                RuntimeWarning,
                stacklevel=2,
            )
    target_max_torque = target_physics_config.get("max_torque", DEFAULT_MAX_TORQUE)
    base_max_torque = base_physics_config.get("max_torque", DEFAULT_MAX_TORQUE)
    if target_max_torque != base_max_torque:
        pattern = (
            r"max " + _PROMPT_SCALAR + r" N·m"
        )
        if re.search(pattern, description):
            description = re.sub(
                pattern,
                lambda m: f"max {target_max_torque:g} N·m (originally {base_max_torque:g} N·m in the source environment)",
                description,
            )
        else:
            warnings.warn(
                "task_description left unchanged.",
                RuntimeWarning,
                stacklevel=2,
            )
    target_delay = int(
        target_physics_config.get("thrust_delay_steps", DEFAULT_THRUST_DELAY_STEPS)
    )
    base_delay = int(
        base_physics_config.get("thrust_delay_steps", DEFAULT_THRUST_DELAY_STEPS)
    )
    if target_delay != base_delay:
        p_delay = (
            r"Pipeline delay is \*\*" + _PROMPT_SCALAR + r"\*\* simulation steps"
        )
        if re.search(p_delay, description):
            description = re.sub(
                p_delay,
                lambda m: f"Pipeline delay is **{target_delay}** simulation steps (originally {base_delay} in the source environment)",
                description,
            )
        else:
            warnings.warn(
                "description left unchanged.",
                RuntimeWarning,
                stacklevel=2,
            )
    target_steps = int(
        target_physics_config.get("max_episode_steps", DEFAULT_MAX_EPISODE_STEPS)
    )
    base_steps = int(
        base_physics_config.get("max_episode_steps", DEFAULT_MAX_EPISODE_STEPS)
    )
    if target_steps != base_steps:
        p_eps = (
            r"limited to \*\*" + _PROMPT_SCALAR + r" simulation steps\*\*"
        )
        if re.search(p_eps, description):
            description = re.sub(
                p_eps,
                lambda m: f"limited to **{target_steps}** simulation steps (originally {base_steps} in the source environment)",
                description,
            )
        else:
            warnings.warn(
                "task_description left unchanged.",
                RuntimeWarning,
                stacklevel=2,
            )
    target_ts = float(target_physics_config.get("time_step", DEFAULT_TIME_STEP))
    base_ts = float(base_physics_config.get("time_step", DEFAULT_TIME_STEP))
    if abs(target_ts - base_ts) > 1e-12:
        p_ts = (
            r"Fixed time step " + _FRACTION_OR_SCALAR + r" s per step"
        )
        if re.search(p_ts, description):
            nl = _format_time_step_for_prompt(target_ts)
            ol = _format_time_step_for_prompt(base_ts)
            description = re.sub(
                p_ts,
                lambda m: f"Fixed time step {nl} s per step (originally {ol} in the source environment)",
                description,
                count=1,
            )
        else:
            warnings.warn(
                "task_description left unchanged.",
                RuntimeWarning,
                stacklevel=2,
            )
    target_lt = float(target_physics_config.get("land_tolerance", DEFAULT_LAND_TOLERANCE))
    base_lt = float(base_physics_config.get("land_tolerance", DEFAULT_LAND_TOLERANCE))
    if abs(target_lt - base_lt) > 1e-12:
        def _fmt_lt(x: float) -> str:
            return f"{int(round(x))}" if abs(x - round(x)) < 1e-9 else f"{x:g}"
        p_lt = (
            r"within " + _PROMPT_SCALAR + r" m of the ground surface" + _ORIG_ANY
        )
        if re.search(p_lt, description):
            t_s, b_s = _fmt_lt(target_lt), _fmt_lt(base_lt)
            description = re.sub(
                p_lt,
                lambda m: f"within {t_s} m of the ground surface (originally {b_s} m in the source environment)",
                description,
            )
        else:
            warnings.warn(
                "task_description left unchanged.",
                RuntimeWarning,
                stacklevel=2,
            )
    return description

def update_success_criteria_for_visible_changes(
    base_success_criteria: str,
    target_terrain_config: Dict[str, Any],
    base_terrain_config: Dict[str, Any],
    target_physics_config: Dict[str, Any] = None,
    base_physics_config: Dict[str, Any] = None,
    *,
    stage: Optional[Dict[str, Any]] = None,

) -> str:
    criteria = base_success_criteria
    target_terrain_config = dict(target_terrain_config or {})
    base_terrain_config = dict(base_terrain_config or {})
    if stage is not None:
        target_terrain_config = {
            **(stage.get("terrain_config") or {}),
            **target_terrain_config,
        }
    target_physics_config = dict(target_physics_config or {})
    base_physics_config = dict(base_physics_config or {})
    if stage is not None:
        sp = stage.get("physics_config") or {}
        target_physics_config = {**sp, **target_physics_config}
    target_vy = target_terrain_config.get(
        "max_safe_vertical_speed", DEFAULT_MAX_SAFE_VERTICAL_SPEED
    )
    base_vy = base_terrain_config.get(
        "max_safe_vertical_speed", DEFAULT_MAX_SAFE_VERTICAL_SPEED
    )
    if target_vy != base_vy:
        pattern = (
            r"\|vy\| <= " + _PROMPT_SCALAR + r" m/s" + _ORIG_ANY
            + r"(\. Measurement uses world-frame vertical velocity \(\+y upward; evaluator uses \|vy\| at first ground contact\)\.)"
        )
        if re.search(pattern, criteria):
            criteria = re.sub(
                pattern,
                lambda m: f"|vy| <= {target_vy:.2f} m/s (originally {base_vy:.2f} m/s in the source environment){m.group(1)}",
                criteria,
            )
        else:
            warnings.warn(
                "success_criteria left unchanged.",
                RuntimeWarning,
                stacklevel=2,
            )
    target_angle_rad = target_terrain_config.get(
        "max_landing_angle", ENV_DEFAULT_MAX_LANDING_ANGLE_RAD
    )
    base_angle_rad = base_terrain_config.get(
        "max_landing_angle", ENV_DEFAULT_MAX_LANDING_ANGLE_RAD
    )
    if target_angle_rad != base_angle_rad:
        target_angle_deg = math.degrees(target_angle_rad)
        base_angle_deg = math.degrees(base_angle_rad)
        pattern = (
            r"\(\|angle\| <= " + _PROMPT_SCALAR + r" degrees" + _ORIG_ANY + r"(\)\.)"
        )
        if re.search(pattern, criteria):
            criteria = re.sub(
                pattern,
                lambda m: f"(|angle| <= {target_angle_deg:.2f} degrees (originally {base_angle_deg:.2f} degrees in the source environment){m.group(1)}",
                criteria,
            )
        else:
            warnings.warn(
                "success_criteria left unchanged.",
                RuntimeWarning,
                stacklevel=2,
            )
        dc_pat = r"\*\*Landing Orientation\*\*: \|angle\| <= " + _PROMPT_SCALAR + r" degrees\."
        if re.search(dc_pat, criteria):
            criteria = re.sub(
                dc_pat,
                f"**Landing Orientation**: |angle| <= {target_angle_deg:.2f} degrees (originally {base_angle_deg:.2f} degrees in the source environment).",
                criteria,
            )
    target_min_fuel = target_physics_config.get(
        "min_fuel_remaining_at_landing", DEFAULT_MIN_FUEL_REMAINING_AT_LANDING
    )
    base_min_fuel = base_physics_config.get(
        "min_fuel_remaining_at_landing", DEFAULT_MIN_FUEL_REMAINING_AT_LANDING
    )
    if target_min_fuel != base_min_fuel:
        def _fmt_min(v: float) -> str:
            v = float(v)
            return str(int(v)) if abs(v - round(v)) < 1e-9 else f"{v:g}"
        pattern = (
            r"Land with at least " + _PROMPT_SCALAR + r" N·s of impulse budget remaining" + _ORIG_ANY
        )
        if re.search(pattern, criteria):
            criteria = re.sub(
                pattern,
                lambda m: f"Land with at least {_fmt_min(target_min_fuel)} N·s of impulse budget remaining (originally {_fmt_min(base_min_fuel)} N·s in the source environment)",
                criteria,
            )
        else:
            warnings.warn(
                "success_criteria left unchanged.",
                RuntimeWarning,
                stacklevel=2,
            )
    target_hw = target_physics_config.get(
        "platform_half_width", DEFAULT_PLATFORM_HALF_WIDTH
    )
    base_hw = base_physics_config.get(
        "platform_half_width", DEFAULT_PLATFORM_HALF_WIDTH
    )
    if target_hw != base_hw:
        tw = 2.0 * target_hw
        bw = 2.0 * base_hw
        pattern = (
            r"\*\*" + _PROMPT_SCALAR + r" m total \(center ± " + _PROMPT_SCALAR + r" m\)\*\*( at the instant of landing \(zone position at that time; not only the center x\)\.)"
        )
        if re.search(pattern, criteria):
            criteria = re.sub(
                pattern,
                lambda m: f"**{tw:.1f} m total (center ± {target_hw:.1f} m)**{m.group(1)} (originally {bw:.1f} m total in the source environment)",
                criteria,
            )
        else:
            warnings.warn(
                "success_criteria left unchanged.",
                RuntimeWarning,
                stacklevel=2,
            )
    return criteria

def apply_visible_prompt_updates(
    task_description: str,
    success_criteria: str,
    target_terrain_config: Dict[str, Any],
    base_terrain_config: Dict[str, Any],
    target_physics_config: Dict[str, Any] = None,
    base_physics_config: Dict[str, Any] = None,
    *,
    stage: Optional[Dict[str, Any]] = None,

) -> tuple[str, str]:
    td = update_task_description_for_visible_changes(
        task_description,
        target_terrain_config,
        base_terrain_config,
        target_physics_config,
        base_physics_config,
        stage=stage,
    )
    sc = update_success_criteria_for_visible_changes(
        success_criteria,
        target_terrain_config,
        base_terrain_config,
        target_physics_config,
        base_physics_config,
        stage=stage,
    )
    return td, sc

def get_c02_curriculum_stages() -> List[Dict[str, Any]]:
    task_description_suffix = """

Sensors indicate that this region exhibits non-standard physical properties.
While the following variables **MIGHT** have changed from the initial environment, **NOT ALL** of them will necessarily be mutated in any given task. You must use active interaction and environmental feedback to deduce which specific conditions apply:
 - **Structural Integrity Threshold**: The allowed magnitude of world-frame vertical speed |vy| at touchdown may be different.
 - **Upright Orientation Tolerance**: The maximum allowed landing angle (deviation from vertical) may be different.
 - **Landing Zone Extent**: The horizontal width of the valid landing platform may be different.
 - **Actuation Latency**: The time delay between issuing a control command and the engine's physical response may be different.
 - **Flight Corridor Constraints**: Vertical limits of the no-fly corridor in the barrier region may be different.
 - **Engine Thrust Limit**: The maximum thrust the main engine can produce may be different.
 - **Effective Gravity**: The effective gravitational influence on the craft may be different.
 - **Resource Availability**: The total fuel impulse available for the mission may be different.
 - **Operational Safety Margins**: The minimum required fuel that must remain after landing may be different.
 - **Atmospheric Disturbances**: Lateral environmental forcing (including gust-like effects) may be different.

Discovery via feedback: Your objective is to identify the underlying physical rules of this specific environment through trial and reasoning. Use simulator feedback to refine your controller.
"""
    return [
        {
            "stage_id": "Stage-1",
            "title": "Fragile Touchdown",
            "mutation_description": "Log only: curriculum stage mutation (Stage-1).",
            "task_description_suffix": task_description_suffix,
            "terrain_config": {
                "max_safe_vertical_speed": 0.8,
            },
            "physics_config": {
                "max_thrust": 800.0,
                "total_fuel_impulse": 7000.0,
                "platform_half_width": 1.0,
            },
        },
        {
            "stage_id": "Stage-2",
            "title": "Micro-Corridor",
            "mutation_description": "Log only: curriculum stage mutation (Stage-2).",
            "task_description_suffix": task_description_suffix,
            "terrain_config": {},
            "physics_config": {
                "barrier_y_bottom": 7.0,
            },
        },
        {
            "stage_id": "Stage-3",
            "title": "The Squeeze",
            "mutation_description": "Log only: curriculum stage mutation (Stage-3).",
            "task_description_suffix": task_description_suffix,
            "terrain_config": {
                "max_safe_vertical_speed": 1.0,
                "max_landing_angle": math.radians(4.5),
            },
            "physics_config": {
                "barrier_y_bottom": 8.5,
                "total_fuel_impulse": 5000.0,
                "max_thrust": 650.0,
                "min_fuel_remaining_at_landing": 650.0,
                "wind_amplitude": 38.0,
                "gust_amplitude": 75.0,
                "platform_half_width": 1.2,
                "thrust_delay_steps": 6,
                "gravity_mutation": {
                    "at_step": 250,
                    "gravity_after": (0, -11.8),
                },
            },
        },
        {
            "stage_id": "Stage-4",
            "title": "The Perfect Storm",
            "mutation_description": "Log only: curriculum stage mutation (Stage-4).",
            "task_description_suffix": task_description_suffix,
            "terrain_config": {
                "max_safe_vertical_speed": 2.6,
                "max_landing_angle": math.radians(7.0),
            },
            "physics_config": {
                "thrust_delay_steps": 12,
                "total_fuel_impulse": 100000.0,
                "max_thrust": 1200.0,
                "min_fuel_remaining_at_landing": 500.0,
                "wind_amplitude": 15.0,
                "gust_amplitude": 20.0,
                "platform_half_width": 1.5,
                "barrier_y_bottom": 15.5,
                "gravity_mutation": {
                    "at_step": 150,
                    "gravity_after": (0, -11.5),
                },
            },
        },
    ]
