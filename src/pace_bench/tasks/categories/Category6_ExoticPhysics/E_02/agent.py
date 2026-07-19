import math

TX_MIN, TX_MAX = 28.0, 32.0

TY_MIN, TY_MAX = 2.0, 5.0

TARGET_X, TARGET_Y = 30.0, 3.5

G1_X, G1_Y = 13.0, 2.0

G2_X, G2_Y = 23.0, 2.4

DRAIN_LO, DRAIN_HI = 14.5, 17.0

SLIP_LO, SLIP_HI = 17.5, 20.0

WIND_LO, WIND_HI = 20.5, 28.0

WIND_AMP = 20.0

WIND_OMEGA = 0.055

MAX_THRUST = 120.0

LOW_THRUST = 90.0

HEAT_SAFE_FRAC = 0.88

def build_agent(sandbox):
    return None

def _waypoint(x, y):
    if x < G1_X - 0.1:
        return (G1_X, G1_Y)
    if x < G2_X - 0.1:
        return (G2_X, G2_Y)
    return (TARGET_X, TARGET_Y)

def agent_action(sandbox, agent_body, step_count):
    if sandbox.is_overheated():
        return
    pos = sandbox.get_craft_position()
    if pos is None:
        return
    x, y = pos
    heat = sandbox.get_heat()
    overheat_limit = sandbox.get_overheat_limit()
    remaining = overheat_limit - heat
    step_idx = sandbox.get_step_count() if hasattr(sandbox, "get_step_count") else step_count
    if TX_MIN <= x <= TX_MAX and TY_MIN <= y <= TY_MAX:
        sandbox.apply_thrust(0.0, 75.0)
        return
    if x > 31.0 and y < 2.0:
        sandbox.apply_thrust(-150.0, 200.0)
        return
    if heat >= overheat_limit * HEAT_SAFE_FRAC:
        thrust_mag = min(LOW_THRUST, remaining * 0.25)
    else:
        thrust_mag = min(MAX_THRUST, remaining * 0.35)
    if overheat_limit <= 40000.0:
        heat_frac = heat / overheat_limit
        if heat_frac > 0.3:
            thrust_mag = 40.0
        else:
            thrust_mag = 60.0
    if x < 10.0:
        thrust_mag = min(100.0, thrust_mag)
    if 10.0 <= x <= 15.0:
        thrust_mag = min(MAX_THRUST, thrust_mag * 1.2)
    if DRAIN_LO <= x <= DRAIN_HI:
        thrust_mag = min(MAX_THRUST, thrust_mag * 1.4)
    if thrust_mag < 75.0 and overheat_limit > 40000.0:
        sandbox.apply_thrust(0.0, 75.0)
        return
    wx, wy = _waypoint(x, y)
    if x > 24.0:
        wy = 4.0
    if x < G1_X + 0.5 and y < 1.2:
        wy = max(wy, 1.3)
    if y < 1.4:
        wy = max(wy, 1.5)
    if G2_X - 1.0 <= x <= G2_X + 2.0 and y < 1.9:
        wy = max(wy, 2.2)
    if 20.5 <= x <= G2_X + 1.0 and y < 1.85:
        wx, wy = x + 0.3, 2.5
    dx = wx - x
    dy = wy - y
    dist = math.sqrt(dx * dx + dy * dy)
    if dist < 1e-6:
        sandbox.apply_thrust(0.0, 75.0)
        return
    ux = dx / dist
    uy = dy / dist
    fx = thrust_mag * ux
    fy = thrust_mag * uy
    if y < 1.4:
        fy += 100.0
    if x < G1_X + 1.0 and y < 1.1:
        fy += min(30.0, (1.2 - y) * 40.0)
    if 20.5 <= x <= G2_X + 2.0 and y < 1.9:
        fy += 110.0
    if x > 25.0 and y < 3.0:
        fy += 120.0
    if SLIP_LO <= x <= SLIP_HI:
        fx += 35.0
    if WIND_LO <= x <= WIND_HI:
        wind_fy = WIND_AMP * math.sin(WIND_OMEGA * step_idx)
        fy -= wind_fy
    total = math.sqrt(fx * fx + fy * fy)
    cap = thrust_mag * 2.5
    if y < 1.4:
        cap = max(cap, 180.0)
    if 20.5 <= x <= G2_X + 2.0 and y < 1.9:
        cap = max(cap, 250.0)
    if total > cap:
        scale = cap / total
        fx *= scale
        fy *= scale
    sandbox.apply_thrust(fx, fy)

def build_agent_stage_1(sandbox): return None

def agent_action_stage_1(sandbox, agent_body, step_count):
    if sandbox.is_overheated(): return
    pos = sandbox.get_craft_position()
    if pos is None: return
    x, y = pos
    if TX_MIN <= x <= TX_MAX and TY_MIN <= y <= TY_MAX:
        sandbox.apply_thrust(0.0, 75.0)
        return
    thrust_mag = 200.0
    wx, wy = _waypoint(x, y)
    wy = 3.5 if x > 20.0 else wy
    dx, dy = wx - x, wy - y
    dist = math.sqrt(dx*dx + dy*dy)
    if dist < 1e-6: return
    fx = (thrust_mag * (dx/dist)) + 80.0
    fy = (thrust_mag * (dy/dist))
    if y < 2.2: fy += 180.0
    if 21.0 <= x <= 24.5 and y < 2.8: fy += 200.0
    if x > 27.0 and y < 2.5: fy += 100.0
    sandbox.apply_thrust(fx, fy)

def build_agent_stage_2(sandbox):
    pos = sandbox.get_craft_position()
    py = pos[1] if pos else 2.0
    return {"reached_target_once": False, "prev_y": py}

def agent_action_stage_2(sandbox, agent_body, step_count):
    if sandbox.is_overheated(): return
    pos = sandbox.get_craft_position()
    if pos is None: return
    x, y = pos
    step_idx = sandbox.get_step_count() if hasattr(sandbox, "get_step_count") else step_count

    if agent_body.get("reached_target_once"):
        sandbox.apply_thrust(0.0, 0.0)
        return
    if TX_MIN <= x <= TX_MAX and TY_MIN <= y <= TY_MAX:
        agent_body["reached_target_once"] = True
        sandbox.apply_thrust(0.0, 0.0)
        return

    prev_y = agent_body.get("prev_y", y)
    dy_step = y - prev_y
    agent_body["prev_y"] = y
    COUNTER_BASE = 425.0
    VEL_GAIN = 2400.0
    vel_correction = VEL_GAIN * dy_step
    heat = sandbox.get_heat()
    overheat_limit = sandbox.get_overheat_limit()
    remaining = overheat_limit - heat
    if heat >= overheat_limit * 0.85:
        thrust_mag = 50.0
    else:
        thrust_mag = 220.0
    wx, wy = _waypoint(x, y)

    if x < 15.0:
        wy = 1.8
    elif x < 24.5:
        wy = 2.3
    else:
        wy = 3.5

    if y < 1.5:
        wy = max(wy, 2.4)
    if G2_X - 1.0 <= x <= G2_X + 2.0 and y < 2.1:
        wy = max(wy, 2.8)
    if x > 25.0 and y < 2.5:
        wy = max(wy, 3.0)
    dx, dy = wx - x, wy - y
    dist = math.sqrt(dx*dx + dy*dy)
    if dist < 1e-6:
        fy = -COUNTER_BASE - vel_correction
        sandbox.apply_thrust(0.0, fy)
        return
    ux = dx / dist
    uy = dy / dist
    fx = thrust_mag * ux
    fy = thrust_mag * uy - COUNTER_BASE - vel_correction

    cap = max(thrust_mag * 12.0, 2000.0)

    if DRAIN_LO <= x <= DRAIN_HI:
        fx += 2200.0
        cap = max(cap, 3200.0)

    if SLIP_LO <= x <= SLIP_HI:
        fx += 55.0

    if WIND_LO <= x <= WIND_HI:
        wind_fy = 20.0 * math.sin(0.055 * step_idx)
        fy -= wind_fy
        fx += 20.0

    if y < 1.6:
        fy += 450.0
        cap = max(cap, 1800.0)
    if x < G1_X + 1.0 and y < 1.3:
        fy += min(220.0, (1.6 - y) * 450.0)
    if x > 25.0 and y < 2.8:
        fy += 220.0
    total = math.sqrt(fx*fx + fy*fy)
    if total > cap:
        scale = cap / total
        fx *= scale; fy *= scale
    sandbox.apply_thrust(fx, fy)

def build_agent_stage_3(sandbox): return {"target_reached": False}

def agent_action_stage_3(sandbox, agent_body, step_count):
    if sandbox.is_overheated(): return
    pos = sandbox.get_craft_position()
    if pos is None: return
    x, y = pos
    step_idx = sandbox.get_step_count() if hasattr(sandbox, "get_step_count") else step_count
    if TX_MIN <= x <= TX_MAX and TY_MIN <= y <= TY_MAX:
        agent_body["target_reached"] = True
    if agent_body.get("target_reached"):
        sandbox.apply_thrust(0.0, 0.0)
        return
    heat_limit = sandbox.get_overheat_limit()
    heat_used = sandbox.get_heat()
    remaining = heat_limit - heat_used

    if heat_used >= heat_limit * 0.55:
        thrust_mag = 80.0
    else:
        thrust_mag = min(600.0, remaining * 0.42)

    if DRAIN_LO <= x <= DRAIN_HI:
        if heat_used < heat_limit * 0.55:
            thrust_mag = 850.0
        else:
            thrust_mag = 200.0

    slip_bonus = 120.0 if SLIP_LO <= x <= SLIP_HI else 0.0
    wx, wy = _waypoint(x, y)

    if x < 14.0:
        wy = min(wy, 2.5)
    else:
        wy = min(wy, 2.7)
    if x > 24.0: wy = 4.0

    if y < 1.8: wy = max(wy, 2.2)
    if x < G1_X + 1.0 and y < 1.3: wy = max(wy, 2.0)
    if G2_X - 1.5 <= x <= G2_X + 1.0 and y < 2.0: wy = max(wy, 2.4)
    dx, dy = wx - x, wy - y
    dist = math.sqrt(dx*dx + dy*dy)
    if dist < 1e-6: return
    ux = dx / dist
    uy = dy / dist
    fx = thrust_mag * ux + slip_bonus
    fy = thrust_mag * uy

    if y < 1.6: fy += 200.0
    if x < G1_X + 1.0 and y < 1.5: fy += min(80.0, (1.8 - y) * 150.0)
    if G2_X - 1.0 <= x <= G2_X + 2.0 and y < 2.0: fy += 160.0
    if x > 25.0 and y < 3.0: fy += 140.0

    if WIND_LO <= x <= WIND_HI:
        wind_fy = 50.0 * math.sin(0.20 * step_idx)
        fy -= wind_fy
        fx += 30.0
    total = math.sqrt(fx*fx + fy*fy)
    cap = thrust_mag * 3.0
    if y < 1.6: cap = max(cap, 300.0)
    if G2_X - 1.0 <= x <= G2_X + 2.0 and y < 2.0: cap = max(cap, 400.0)
    if total > cap:
        scale = cap / total
        fx *= scale; fy *= scale
    sandbox.apply_thrust(fx, fy)

def build_agent_stage_4(sandbox): return {"reached_target_once": False}

def agent_action_stage_4(sandbox, agent_body, step_count):
    if sandbox.is_overheated(): return
    pos = sandbox.get_craft_position()
    if pos is None: return
    x, y = pos
    step_idx = sandbox.get_step_count() if hasattr(sandbox, "get_step_count") else step_count

    if agent_body.get("reached_target_once"):
        sandbox.apply_thrust(0.0, 0.0)
        return
    if TX_MIN <= x <= TX_MAX and TY_MIN <= y <= TY_MAX:
        agent_body["reached_target_once"] = True
        sandbox.apply_thrust(0.0, 0.0)
        return

    thrust_mag = 260.0

    if DRAIN_LO <= x <= DRAIN_HI:
        thrust_mag = 400.0
    wx, wy = _waypoint(x, y)

    if x < 22.0:
        wy = 2.4
    elif x < 25.0:
        wy = 2.6
    else:
        wy = 4.0
    if y < 1.7:
        wy = max(wy, 2.3)
    if 22.0 <= x <= 24.0:
        wy = min(wy, 2.7)
    dx, dy = wx - x, wy - y
    dist = math.sqrt(dx*dx + dy*dy)
    if dist < 1e-6: return
    ux = dx / dist
    uy = dy / dist
    fx = thrust_mag * ux
    fy = thrust_mag * uy

    fy += 75.0

    if y < 1.6: fy += 180.0
    if G2_X - 1.0 <= x <= G2_X + 2.0 and y < 2.2: fy += 140.0
    if x > 25.0 and y < 3.2: fy += 120.0

    if SLIP_LO <= x <= SLIP_HI:
        fx += 85.0

    if WIND_LO <= x <= WIND_HI:
        wind_fy = 105.0 * math.sin(0.48 * step_idx)
        fy -= wind_fy
        fx += 40.0
    sandbox.apply_thrust(fx, fy)
