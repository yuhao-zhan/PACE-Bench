import os

import json

import sys

import importlib.util

_prompt_dir = os.path.dirname(os.path.abspath(__file__))

_spec_c03_env = importlib.util.spec_from_file_location(
    "c03_environment_prompt", os.path.join(_prompt_dir, "environment.py")

)

_c03_env = importlib.util.module_from_spec(_spec_c03_env)

_spec_c03_env.loader.exec_module(_c03_env)

_HREF = _c03_env.HEADING_REFERENCE_MIN_TARGET_SPEED

_ACT_X0 = _c03_env.ACTIVATION_ZONE_X_MIN

_ACT_X1 = _c03_env.ACTIVATION_ZONE_X_MAX

_ACT_STEPS = _c03_env.ACTIVATION_REQUIRED_STEPS

_RDIST = _c03_env.RENDEZVOUS_DISTANCE_DEFAULT

_RZX0 = _c03_env.RENDEZVOUS_ZONE_X_MIN

_RZX1 = _c03_env.RENDEZVOUS_ZONE_X_MAX

_WIND_X0, _WIND_X1 = _c03_env.WIND_ZONE_X

_IMPULSE = _c03_env.IMPULSE_BUDGET

_EVASIVE_DIST = _c03_env.EVASIVE_DISTANCE

_ICE_FRICTION = _c03_env.ICE_PATCH_FRICTION_DEFAULT

_REL_SPD = _c03_env.RENDEZVOUS_REL_SPEED_DEFAULT

_TRACK = _c03_env.TRACK_DISTANCE_DEFAULT

_HEAD_TOL_DEG = _c03_env.RENDEZVOUS_HEADING_TOLERANCE_DEG_DEFAULT

_MAX_ANG_RATE = _c03_env.MAX_ANGULAR_RATE

_BZ0 = _c03_env.BLIND_ZONE_X_MIN

_BZ1 = _c03_env.BLIND_ZONE_X_MAX

_SPD_BLIND = _c03_env.SPEED_BLIND_THRESHOLD

_JUMP_IV = _c03_env.JUMP_INTERVAL_STEPS

_JUMP_MAG = _c03_env.JUMP_MAG

_COOLDOWN_THRESH = _c03_env.COOLDOWN_THRESHOLD

_COOLDOWN_MAX_THRUST = _c03_env.COOLDOWN_MAX_THRUST

_COOLDOWN_STEPS = _c03_env.COOLDOWN_STEPS

_GY_TOP = _c03_env.DEFAULT_GROUND_Y_TOP

_TGT_Y_MIN = _GY_TOP + 0.5

_TGT_Y_MAX = _GY_TOP + 2.0

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from pace_bench.tasks.primitives_api import API_INTRO

with open(os.path.join(os.path.dirname(__file__), '..', '..', 'primitives_api.json'), 'r') as f:
    _api_data = json.load(f)

if 'C_03' in _api_data and 'API_INTRO' in _api_data['C_03']:
    del _api_data['C_03']['API_INTRO']

TASK_PROMPT = {
    "task_description": f"""
Design a controller for a seeker craft to achieve multiple heading-aligned rendezvous with a dynamic target.

- **Seeker**: Single thrust vector along current heading (max {_c03_env.MAX_THRUST_MAGNITUDE:g} N). Spawns at (11.0, 1.35) m (x, y). exhibits drag and rotational resistance on the seeker body (Box2D). **Heading rotation rate** is limited to {_MAX_ANG_RATE:.2f} rad per simulation step (heading tracks commanded thrust direction at this max rate). Follow the numerics printed for your specific run. **Thrust cooldown**: Exceeding {_COOLDOWN_THRESH:.0f} N thrust triggers a cooldown; during the next {_COOLDOWN_STEPS} steps, maximum thrust is reduced to {_COOLDOWN_MAX_THRUST:.0f} N.
- **Ground**: Top surface at y = {_GY_TOP:.1f} m; ground body has half-height 0.5 m.
- **Target**: Starts at (12.0, 2.0) m. Moves with default speed 1.5 m/s; direction changes roughly every 1.2 s. Clamped to x ∈ [6, 26] m, y ∈ [{_TGT_Y_MIN:.1f}, {_TGT_Y_MAX:.1f}] m. Evasive boosts when seeker distance < {_EVASIVE_DIST:.1f} m. Periodic random position jumps occur every {_JUMP_IV} steps with magnitude up to {_JUMP_MAG:.1f} m.
- **Ice patches**: Low-friction surfaces (friction coefficient ≈ {_ICE_FRICTION:.2f}) may be present in the corridor.
- **Static boxes**: at (7.5, 1.5, 0.3, 0.5); at (14.0, 1.5, 0.3, 0.5); at (20.5, 1.5, 0.3, 0.5).
- **Moving obstacles**: Kinematic boxes oscillating horizontally in the corridor at (10.5, 1.5) and (17.0, 1.5); query `sandbox.get_terrain_obstacles()` for real-time positions.
- **Wind zone**: While seeker x ∈ [{_WIND_X0:.1f}, {_WIND_X1:.1f}] m, additional environmental forcing may act; infer from motion.
- **Moving corridor**: Allowed seeker x shifts over time (x_lo, x_hi); violation if seeker center leaves corridor by >0.02 m. Corridor may pinch inward under certain time conditions.
- **Sensing**: `get_target_position()` delivers a new sample every 5 simulation steps (otherwise repeats last reading) with an additional randomized delay of 2–6 steps. If seeker x is in [{_BZ0:.1f}, {_BZ1:.1f}] m (blind band) OR seeker speed > {_SPD_BLIND:.1f} m/s, the reading does not update (stale). Infer target velocity from position history.
- **Activation Gate**: Rendezvous only counts after the seeker "activates" by staying at least {_ACT_STEPS} consecutive steps with seeker x in [{_ACT_X0:.1f}, {_ACT_X1:.1f}] m.
- **Rendezvous slots**: Two phase windows — phase-1 and phase-2 — with designated time slots (use `sandbox.get_rendezvous_slots()` for authoritative intervals).
- **Fuel**: Total thrust impulse is limited to {_IMPULSE:.0f} N·s.

Design a multi-phase control strategy:
1. **Activation**: Position and hold the seeker in the activation zone until activated.
2. **Slotted Rendezvous**: Complete the first rendezvous in a phase-1 slot and the second in a phase-2 slot; rendezvous requires: distance to target ≤ {_RDIST:.1f} m, relative speed < {_REL_SPD:g} m/s, AND seeker heading within {_HEAD_TOL_DEG:.1f}° of the reference direction (target velocity direction when target speed ≥ {_HREF:g} m/s, else seeker-to-target direction).
3. **Tracking**: Maintain distance <= {_TRACK:g} m from target after the second rendezvous until the end.
""",
    "success_criteria": f"""

1. **Rendezvous Completion**: Achieve rendezvous in both phase-1 and phase-2 designated time slots (verify via `sandbox.get_rendezvous_slots()`).
2. **Capture envelope**: Activation already achieved (≥{_ACT_STEPS} consecutive steps with seeker x ∈ [{_ACT_X0:.1f}, {_ACT_X1:.1f}] m); seeker x ∈ [{_RZX0:.1f}, {_RZX1:.1f}] m; distance to **true** target ≤ {_RDIST:.1f} m; relative speed < {_REL_SPD:g} m/s; heading within {_HEAD_TOL_DEG:.1f}° of target velocity direction if target speed ≥ {_HREF:g} m/s, else seeker-to-target direction.
3. **Tracking**: Maintain distance <= {_TRACK:g} m from target after the second rendezvous until the end.
4. **Safety**: No collisions with corridor obstacles; stay within the moving corridor.
5. **Efficiency**: Total thrust impulse must not exceed **{_IMPULSE:.0f} N·s**.

- **Fuel budget**: {_IMPULSE:.0f} N·s total thrust impulse; reaching or exceeding fails the run.
- **Corridor**: Seeker center must stay within shifting bounds (violation margin >0.02 m fails).
- **Obstacle collision**: Seeker must not penetrate any corridor box (static or kinematic) by ≥0.05 m.
- **Thrust cooldown**: Exceeding {_COOLDOWN_THRESH:.0f} N thrust triggers cooldown; max thrust reduced to {_COOLDOWN_MAX_THRUST:.0f} N for {_COOLDOWN_STEPS} steps.
- **APIs**: Use only the primitives documented below.
""",
    'primitives_api': API_INTRO + '\n' + '\n\n'.join(_api_data['C_03'].values()),

}
