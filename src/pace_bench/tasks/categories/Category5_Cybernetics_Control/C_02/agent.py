import math

_INITIAL_REF_BARRIER_Y_BOTTOM = 20.0

def _get_thrust_torque_limits(sandbox):
    return getattr(sandbox, '_max_thrust', 600.0), getattr(sandbox, '_max_torque', 120.0)

def _lander_mass(sandbox):
    return float(getattr(sandbox, '_lander_mass', 50.0))

def _sim_dt(sandbox):
    return float(getattr(sandbox, "_time_step", 1.0 / 60.0))

def _gravity_magnitude(sandbox):
    try:
        gy = float(sandbox.world.gravity[1])
        return abs(gy) if abs(gy) > 1e-6 else 10.0
    except (AttributeError, TypeError, ValueError, IndexError):
        return 10.0

def _platform_kinematics(sandbox, t):
    base = float(getattr(sandbox, "_platform_center_base", 17.0))
    amp = float(getattr(sandbox, "_platform_amplitude", 1.8))
    per = float(getattr(sandbox, "_platform_period", 6.0))
    if per <= 1e-6:
        per = 6.0
    w = 2.0 * math.pi / per
    plat_x = base + amp * math.sin(w * t)
    plat_vx = amp * w * math.cos(w * t)
    return plat_x, plat_vx

def _barrier_geometry(sandbox):
    xr = float(getattr(sandbox, "_barrier_x_right", 13.5))
    yt = float(getattr(sandbox, "_barrier_y_top", 6.0))
    yb = float(getattr(sandbox, "_barrier_y_bottom", 20.0))
    return xr, yt, yb

def _corridor_target_altitude(yt, yb, clearance_obstacle=2.5, clearance_ceiling=1.5):
    y_lo = yt + clearance_obstacle
    y_hi = yb - clearance_ceiling
    if y_hi <= y_lo:
        return 0.5 * (yt + yb)
    inner = y_hi - y_lo
    y_pref = y_lo + 0.35 * inner
    return max(y_lo, min(y_pref, y_hi))

def _thrust_delay_steps(sandbox):
    if hasattr(sandbox, "get_thrust_delay_steps"):
        return int(sandbox.get_thrust_delay_steps())
    return int(getattr(sandbox, "_thrust_delay_steps", 3))

class BaselineLanderAgent:
    def __init__(self, agent_body):
        self.agent_body = agent_body
    @property
    def position(self): return self.agent_body.position
    @property
    def linearVelocity(self): return self.agent_body.linearVelocity
    def act(self, sandbox, step_count):
        pos, vel = self.agent_body.position, self.agent_body.linearVelocity
        x, y, vx, vy = pos.x, pos.y, vel.x, vel.y
        angle, omega = self.agent_body.angle, self.agent_body.angularVelocity
        dt = _sim_dt(sandbox)
        t_sim = step_count * dt
        t_p = t_sim + 0.15
        plat_x, plat_vx = _platform_kinematics(sandbox, t_p)
        xr, yt, _yb_actual = _barrier_geometry(sandbox)
        if x < xr + 0.5:
            tx = xr + 1.5
            ty = _corridor_target_altitude(
                yt, _INITIAL_REF_BARRIER_Y_BOTTOM, clearance_obstacle=2.5, clearance_ceiling=1.5
            )
            tvx, tvy = 2.5, 0.0
        else:
            tx, ty = plat_x, 1.05
            tvx, tvy = plat_vx, -1.2
            if y < 4.0:
                tvy = -0.25
        g, m = _gravity_magnitude(sandbox), _lander_mass(sandbox)
        ay = 4.0 * (ty - y) + 10.0 * (tvy - vy)
        thrust = m * (g + ay)
        thrust /= max(0.5, math.cos(angle))
        max_thrust, max_torque = _get_thrust_torque_limits(sandbox)
        thrust = max(0.0, min(max_thrust, thrust))
        ax = 2.5 * (tx - x) + 5.0 * (tvx - vx)
        target_angle = max(-0.6, min(0.6, -0.2 * ax))
        if y < 3.0: target_angle = 0.0
        torque = 1000.0 * (target_angle - angle) - 250.0 * omega
        torque = max(-max_torque, min(max_torque, torque))
        sandbox.apply_thrust(thrust, torque)

def build_agent(sandbox): return BaselineLanderAgent(sandbox.get_lander_body())

def agent_action(sandbox, agent, step_count): agent.act(sandbox, step_count)

def build_agent_stage_1(sandbox): return sandbox.get_lander_body()

def agent_action_stage_1(sandbox, agent, step_count):
    dt = _sim_dt(sandbox)
    pos, vel = agent.position, agent.linearVelocity
    x, y, vx, vy = pos.x, pos.y, vel.x, vel.y
    angle, omega = agent.angle, agent.angularVelocity
    plat_x, plat_vx = _platform_kinematics(sandbox, step_count * dt + 0.15)
    xr, yt, yb = _barrier_geometry(sandbox)
    if x < xr + 0.5:
        tx = xr + 1.5
        ty = max(yt + 2.5, min(13.0, yb - 1.5))
        tvx, tvy = 2.5, 0.0
    else:
        tx, ty, tvx, tvy = plat_x, 1.05, plat_vx, -0.3
        if y < 4.0: tvy = -0.15
        if y < 2.0: tvy = -0.1
    g, m = _gravity_magnitude(sandbox), _lander_mass(sandbox)
    ay = 10.0 * (ty - y) + 15.0 * (tvy - vy)
    thrust = m * (g + ay) / max(0.1, math.cos(angle))
    max_thrust, _ = _get_thrust_torque_limits(sandbox)
    thrust = max(0.0, min(max_thrust, thrust))
    ax = 10.0 * (tx - x) + 15.0 * (tvx - vx)
    target_angle = max(-0.4, min(0.4, -0.1 * ax))
    if y < 2.0: target_angle = 0.0
    torque = 3000.0 * (target_angle - angle) - 800.0 * omega
    max_torque = _get_thrust_torque_limits(sandbox)[1]
    torque = max(-max_torque, min(max_torque, torque))
    sandbox.apply_thrust(thrust, torque)

def build_agent_stage_2(sandbox): return sandbox.get_lander_body()

def agent_action_stage_2(sandbox, agent, step_count):
    if step_count == 0:
        import random; random.seed(42)
    dt = _sim_dt(sandbox)
    ds = _thrust_delay_steps(sandbox)
    g = _gravity_magnitude(sandbox)
    pos, vel = agent.position, agent.linearVelocity
    x, y, vx, vy = pos.x, pos.y, vel.x, vel.y
    angle, omega = agent.angle, agent.angularVelocity
    max_thrust, max_torque = _get_thrust_torque_limits(sandbox)
    m = _lander_mass(sandbox)
    plat_x, plat_vx = _platform_kinematics(sandbox, (step_count + ds) * dt + 0.15)
    xl = float(getattr(sandbox, "_barrier_x_left", 10.5))
    xr = float(getattr(sandbox, "_barrier_x_right", 13.5))
    yt = float(getattr(sandbox, "_barrier_y_top", 6.0))
    yb = float(getattr(sandbox, "_barrier_y_bottom", 20.0))
    corridor_centre = 0.5 * (yt + yb)
    in_barrier = (x >= xl - 0.9 and x <= xr + 0.8)
    if not hasattr(agent, '_vi'):
        agent._vi = 0.0
    if in_barrier:
        agent._vi += (corridor_centre - y) * dt
        agent._vi = max(-0.5, min(0.5, agent._vi))
    else:
        agent._vi = 0.0
    if in_barrier:
        tx = xr + 3.0
        tvx = 0.8
        ty = corridor_centre
        tvy = 0.0
        ay = 35.0 * (ty - y) + 55.0 * (tvy - vy) + 20.0 * agent._vi
        thrust = m * (g + ay) / max(0.3, math.cos(angle))
        thrust = max(0.0, min(max_thrust, thrust))
        target_angle = 0.0
        torque = 300.0 * (target_angle - angle) - 80.0 * omega
        torque = max(-max_torque, min(max_torque, torque))
        sandbox.apply_thrust(thrust, torque)
        return
    if x < xl - 0.9:
        # Hold before the obstacle until the complete hull fits inside the
        # one-metre Stage-2 corridor, then translate through at level flight.
        altitude_error = y - corridor_centre
        ready_for_corridor = abs(altitude_error) <= 0.08 and abs(vy) <= 0.25
        hover = m * g
        if not ready_for_corridor:
            tx = xl - 2.5; tvx = -0.2
            ty = corridor_centre
            tvy = 0.0
        else:
            tx = xl + 2.0; tvx = 3.0
            ty = corridor_centre; tvy = 0.0
        if altitude_error > 0.2:
            upward_acceleration = max(0.1, max_thrust / m - g)
            stopping_distance = max(0.0, -vy) ** 2 / (2.0 * upward_acceleration)
            thrust = max_thrust if stopping_distance + 1.95 >= altitude_error else 0.0
        else:
            thrust = (
                hover + m * 6.0 * (tvy - vy) + m * 3.0 * (ty - y)
            ) / max(0.3, math.cos(angle))
        thrust = max(0.0, min(max_thrust, thrust))
        ax = 1.5 * (tx - x) + 3.0 * (tvx - vx)
        target_angle = max(-0.10, min(0.10, -0.05 * ax))
        torque = 30.0 * (target_angle - angle) - 6.0 * omega
        torque = max(-max_torque, min(max_torque, torque))
        sandbox.apply_thrust(thrust, torque)
        return
    tx = plat_x
    tvx = plat_vx
    ty = 1.05
    if y > 3.5:
        tvy = -2.0
        vertical_position_gain = 0.0
        vertical_velocity_gain = 4.0
    else:
        tvy = -2.0
        vertical_position_gain = 1.0
        vertical_velocity_gain = 4.0
    ay = vertical_position_gain * (ty - y) + vertical_velocity_gain * (tvy - vy)
    thrust = m * (g + ay)
    thrust = max(0.0, min(max_thrust, thrust))
    ax = 3.0 * (tx - x) + 6.0 * (tvx - vx)
    target_angle = max(-0.15, min(0.15, -0.06 * ax))
    if y < 4.0:
        target_angle = 0.0
    torque = 80.0 * (target_angle - angle) - 20.0 * omega
    torque = max(-max_torque, min(max_torque, torque))
    sandbox.apply_thrust(thrust, torque)

def build_agent_stage_3(sandbox): return sandbox.get_lander_body()

def agent_action_stage_3(sandbox, agent, step_count, _vert_integral=[0.0],
                         _horiz_integral=[0.0]):
    dt = _sim_dt(sandbox)
    ds = _thrust_delay_steps(sandbox)
    g = _gravity_magnitude(sandbox)
    pos, vel = agent.position, agent.linearVelocity
    x, y, vx, vy = pos.x, pos.y, vel.x, vel.y
    angle, omega = agent.angle, agent.angularVelocity
    max_thrust, max_torque = _get_thrust_torque_limits(sandbox)
    m = _lander_mass(sandbox)
    plat_x, plat_vx = _platform_kinematics(sandbox, (step_count + ds) * dt + 0.15)
    pred_t = ds * dt
    yp = y + vy * pred_t + 0.5 * (-g) * pred_t * pred_t
    vyp = vy - g * pred_t
    xp = x + vx * pred_t
    xl = float(getattr(sandbox, "_barrier_x_left", 10.5))
    xr = float(getattr(sandbox, "_barrier_x_right", 13.5))
    yt = float(getattr(sandbox, "_barrier_y_top", 6.0))
    yb = float(getattr(sandbox, "_barrier_y_bottom", 20.0))
    corridor_centre = 0.5 * (yt + yb)
    in_barrier = (x >= xl - 0.9 and x <= xr + 0.8)
    if in_barrier:
        vert_err = corridor_centre - y
        _vert_integral[0] += vert_err * dt
        _vert_integral[0] = max(-0.5, min(0.5, _vert_integral[0]))
    else:
        _vert_integral[0] = 0.0
    if in_barrier:
        tx = xr + 2.0
        tvx = 1.0
        ty = corridor_centre
        tvy = 0.0
        ay = 25.0 * (ty - y) + 40.0 * (tvy - vy) + 15.0 * _vert_integral[0]
        thrust = m * (g + ay) / max(0.3, math.cos(angle))
        thrust = max(0.0, min(max_thrust, thrust))
        ax = 1.5 * (tx - x) + 3.0 * (tvx - vx)
        target_angle = max(-0.03, min(0.03, -0.02 * ax))
        torque = 60.0 * (target_angle - angle) - 8.0 * omega
        torque = max(-max_torque, min(max_torque, torque))
    elif x < xl - 0.9:
        tx = xl + 1.0
        ty = corridor_centre
        tvy = -1.0
        ay = 4.0 * (ty - y) + 8.0 * (tvy - vy)
        thrust = m * (g + ay) / max(0.4, math.cos(angle))
        thrust = max(0.0, min(max_thrust, thrust))
        ax = 1.5 * (tx - x) + 3.0 * (1.5 - vx)
        target_angle = max(-0.08, min(0.08, -0.04 * ax))
        torque = 45.0 * (target_angle - angle) - 6.0 * omega
        torque = max(-max_torque, min(max_torque, torque))
    else:
        alt = max(0.0, y - 1.0)
        if alt > 4.0:
            tx = plat_x - 5.0
            tvx = plat_vx
        elif alt > 2.5:
            blend = (4.0 - alt) / 1.5
            tx = plat_x - 5.0 * (1.0 - blend)
            tvx = plat_vx
        elif alt > 1.5:
            tx = plat_x - 1.0
            tvx = plat_vx
        else:
            tx = plat_x
            tvx = plat_vx
        if alt > 2.0:
            _horiz_integral[0] += (tx - x) * dt
            _horiz_integral[0] = max(-5.0, min(5.0, _horiz_integral[0]))
        else:
            _horiz_integral[0] = 0.0
        ax = 4.0 * (tx - x) + 8.0 * (tvx - vx) + 2.0 * _horiz_integral[0]
        if alt > 2.0:
            target_angle = max(-0.08, min(0.08, -0.05 * ax))
        elif alt > 0.5:
            blend_ang = (alt - 0.5) / 1.5
            raw = max(-0.04, min(0.04, -0.03 * ax))
            target_angle = blend_ang * raw
        else:
            target_angle = 0.0
        hover_thrust = m * g
        if alt > 4.0:
            ff_thrust = hover_thrust - 75.0
            tvy = -2.5;  v_kd = 4.0
        elif alt > 3.0:
            ff_thrust = hover_thrust + 10.0
            tvy = -1.8;  v_kd = 6.0
        elif alt > 2.0:
            ff_thrust = hover_thrust + 30.0
            tvy = -1.2;  v_kd = 8.0
        else:
            if alt > 1.5:
                ff_thrust = hover_thrust
                tvy = -0.10;  v_kd = 15.0
            elif alt > 1.0:
                ff_thrust = hover_thrust + 35.0
                tvy = -0.05;  v_kd = 22.0
            elif alt > 0.5:
                ff_thrust = hover_thrust + 55.0
                tvy = -0.02;  v_kd = 30.0
            elif alt > 0.2:
                ff_thrust = max_thrust
                tvy = -0.01;  v_kd = 36.0
            else:
                ff_thrust = max_thrust
                tvy = -0.005;  v_kd = 42.0
        if alt > 2.0:
            pd_ay = v_kd * (tvy - vy)
            thrust = (ff_thrust + m * pd_ay) / max(0.4, math.cos(angle))
            tkp, tkd = 60.0, 8.0
        else:
            pd_ay = v_kd * (tvy - vy)
            thrust = (ff_thrust + m * pd_ay) / max(0.3, math.cos(angle))
            if alt > 0.8:
                tkp, tkd = 150.0, 18.0
            else:
                tkp, tkd = 300.0, 35.0
        thrust = max(0.0, min(max_thrust, thrust))
        torque = tkp * (target_angle - angle) - tkd * omega
        torque = max(-max_torque, min(max_torque, torque))
    sandbox.apply_thrust(thrust, torque)

def build_agent_stage_4(sandbox): return sandbox.get_lander_body()

def agent_action_stage_4(sandbox, agent, step_count):
    dt = _sim_dt(sandbox)
    delay_t = 0.22
    g = _gravity_magnitude(sandbox)
    pos, vel = agent.position, agent.linearVelocity
    x, y, vx, vy = pos.x, pos.y, vel.x, vel.y
    angle, omega = agent.angle, agent.angularVelocity
    angle = angle + omega * delay_t
    vx_p = vx
    vy_p = vy - g * delay_t
    x_p = x + vx * delay_t
    y_p = y + vy * delay_t - 0.5 * g * delay_t**2
    ds = _thrust_delay_steps(sandbox)
    plat_x, plat_vx = _platform_kinematics(sandbox, (step_count + ds) * dt + 0.15)
    xr, yt, yb = _barrier_geometry(sandbox)
    if x < xr + 1.7:
        tx = xr + 3.0
        ty = max(yt + 2.5, min(13.5, yb - 1.5))
        tvx, tvy = 0.4, 0.0
    else:
        tx, ty, tvx, tvy = plat_x, 1.05, plat_vx, -0.2
        if y < 4.0:
            tvy = -0.10
            tvx = plat_vx
    m = _lander_mass(sandbox)
    ay = 15.0 * (ty - y_p) + 20.0 * (tvy - vy_p)
    acc_y = max(3.0, g + ay)
    thrust = m * acc_y / max(0.1, math.cos(angle))
    max_thrust, max_torque = _get_thrust_torque_limits(sandbox)
    thrust = max(0.0, min(max_thrust, thrust))
    ax = 2.0 * (tx - x_p) + 6.0 * (tvx - vx_p)
    target_angle = max(-0.35, min(0.35, -0.1 * ax))
    if y < 3.0: target_angle = 0.0
    tkp, tkd = 4000.0, 1200.0
    if y < 3.0:
        tkp, tkd = 2000.0, 800.0
    torque = tkp * (target_angle - angle) - tkd * omega
    torque = max(-max_torque, min(max_torque, torque))
    sandbox.apply_thrust(thrust, torque)
