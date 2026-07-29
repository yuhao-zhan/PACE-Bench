import math

def _rendezvous_slot_intervals(sandbox):
    return sandbox.get_rendezvous_slots()

def build_agent(sandbox):
    return sandbox.get_seeker_body()

def agent_action(sandbox, agent_body, step_count):
    if not hasattr(agent_body, '_state'):
        agent_body._state = {'last_tx': 0.0, 'last_ty': 0.0, 'tvx': 0.0, 'tvy': 0.0}
    state = agent_body._state
    tx, ty = sandbox.get_target_position()
    sx, sy = sandbox.get_seeker_position()
    svx, svy = sandbox.get_seeker_velocity()
    if step_count % 5 == 0 and step_count > 5:
        dt = 5.0 / 60.0
        state['tvx'] = 0.5 * state['tvx'] + 0.5 * (tx - state['last_tx']) / dt
        state['tvy'] = 0.5 * state['tvy'] + 0.5 * (ty - state['last_ty']) / dt
        state['last_tx'], state['last_ty'] = tx, ty
    elif step_count <= 5:
        state['last_tx'], state['last_ty'] = tx, ty
    slots = _rendezvous_slot_intervals(sandbox)
    in_slot = any(lo <= step_count <= hi for (lo, hi) in slots)
    if step_count < 110: gx, gy = 11.95, 1.35
    elif in_slot: gx, gy = tx, ty
    else:
        gx = 13.1 if (step_count // 120) % 2 == 0 else 13.5
        gy = 1.35
    if in_slot:
        fx = 300.0 * (gx - sx) + 60.0 * (state['tvx'] - svx)
        fy = 300.0 * (gy - sy) + 60.0 * (state['tvy'] - svy)
    else:
        fx = 300.0 * (gx - sx) - 60.0 * svx
        fy = 180.0 * (gy - sy) - 45.0 * svy
    if step_count >= 110 and abs(gx - sx) > 0.05:
        if abs(fx) < 110.0: fx = 110.0 if (gx - sx) > 0 else -110.0
    mag = math.sqrt(fx*fx + fy*fy)
    if mag > 119.0: fx, fy = fx * 119.0 / mag, fy * 119.0 / mag
    sandbox.apply_seeker_force(fx, fy)

def build_agent_stage_1(sandbox):
    return sandbox.get_seeker_body()

def agent_action_stage_1(sandbox, agent_body, step_count):
    if not hasattr(agent_body, "s1"):
        tx, ty = sandbox.get_target_position()
        agent_body.s1 = {
            "mode": "climb",
            "activation_steps": 0,
            "last_tx": tx,
            "last_ty": ty,
            "last_sample_step": step_count,
            "tvx": 0.0,
            "tvy": 0.0,
            "ix": 0.0,
            "iy": 0.0,
        }
    state = agent_body.s1
    tx, ty = sandbox.get_target_position()
    sx, sy = sandbox.get_seeker_position()
    vx, vy = sandbox.get_seeker_velocity()
    slots = _rendezvous_slot_intervals(sandbox)
    c_lo, c_hi = sandbox.get_corridor_bounds()

    if (tx, ty) != (state["last_tx"], state["last_ty"]):
        elapsed = max(1, step_count - state["last_sample_step"]) / 60.0
        raw_tvx = (tx - state["last_tx"]) / elapsed
        raw_tvy = (ty - state["last_ty"]) / elapsed
        if math.hypot(raw_tvx, raw_tvy) < 3.2:
            state["tvx"] = 0.55 * state["tvx"] + 0.45 * raw_tvx
            state["tvy"] = 0.55 * state["tvy"] + 0.45 * raw_tvy
        state["last_tx"], state["last_ty"] = tx, ty
        state["last_sample_step"] = step_count

    phase1_slots = [slot for slot in slots if slot[0] < 5500]
    phase2_slots = [slot for slot in slots if slot[0] >= 5500]
    in_phase1 = any(lo <= step_count <= hi for lo, hi in phase1_slots)
    in_phase2 = any(lo <= step_count <= hi for lo, hi in phase2_slots)
    in_slot = in_phase1 or in_phase2
    first_phase_done = step_count > max(hi for _, hi in phase1_slots)
    second_phase_done = step_count > max(hi for _, hi in phase2_slots)

    if state["mode"] == "climb" and sy >= 2.55:
        state["mode"] = "activate"
    if state["mode"] == "activate":
        if 13.0 <= sx <= 13.35:
            state["activation_steps"] += 1
        else:
            state["activation_steps"] = 0
        if state["activation_steps"] >= 95:
            state["mode"] = "pursuit"

    safe_lo = max(12.4, c_lo + 0.8)
    safe_hi = min(17.6, c_hi - 0.8)
    if state["mode"] == "climb":
        goal_x, goal_y = 11.15, 2.65
        desired_vx = 0.0
        desired_vy = 0.9 if sy < 2.35 else 0.25
    elif state["mode"] == "activate":
        goal_x, goal_y = 13.18, 2.65
        desired_vx = max(-0.7, min(0.7, 0.75 * (goal_x - sx)))
        desired_vy = max(-0.5, min(0.5, 0.8 * (goal_y - sy)))
    else:
        lead = 0.35 if in_slot else 0.18
        goal_x = tx + lead * state["tvx"]
        goal_y = ty + lead * state["tvy"]
        goal_x = max(safe_lo, min(safe_hi, goal_x))
        goal_y = max(2.45, min(3.05, goal_y))
        position_gain = 0.32 if in_slot else 0.22
        velocity_gain = 0.70 if in_slot else 0.45
        if first_phase_done:
            position_gain = max(position_gain, 0.26)
            velocity_gain = max(velocity_gain, 0.55)
        if second_phase_done:
            goal_y = 2.55
            position_gain = 0.15
            velocity_gain = 0.0
        desired_vx = position_gain * (goal_x - sx) + velocity_gain * state["tvx"]
        desired_vy = position_gain * (goal_y - sy) + velocity_gain * state["tvy"]
        speed_limit = 1.65 if in_slot else 1.35
        desired_speed = math.hypot(desired_vx, desired_vy)
        if desired_speed > speed_limit:
            desired_vx *= speed_limit / desired_speed
            desired_vy *= speed_limit / desired_speed

    ex = goal_x - sx
    ey = goal_y - sy
    state["ix"] = max(-1.2, min(1.2, state["ix"] + ex / 60.0))
    state["iy"] = max(-1.5, min(1.5, state["iy"] + ey / 60.0))
    force_x = 34.0 * (desired_vx - vx) + 4.0 * state["ix"]
    force_y = 34.0 * (desired_vy - vy) + 16.0 * state["iy"]

    if sx < 12.2:
        force_x += 70.0 * (12.2 - sx)
    elif sx > 17.8:
        force_x -= 70.0 * (sx - 17.8)
    if sy < 2.30:
        force_y += 55.0 * (2.30 - sy)

    force_mag = math.hypot(force_x, force_y)
    if force_mag > 88.0:
        force_x *= 88.0 / force_mag
        force_y *= 88.0 / force_mag
    sandbox.apply_seeker_force(force_x, force_y)

def build_agent_stage_2(sandbox):
    return sandbox.get_seeker_body()

def agent_action_stage_2(sandbox, agent_body, step_count):
    if not hasattr(agent_body, 's2'):
        agent_body.s2 = {
            'phase': 0,
            'act_steps': 0,
            'last_tx': 0.0, 'last_ty': 0.0,
            'tvx': 0.0, 'tvy': 0.0,
            'sample_timer': 0,
            'p1_done': False,
            'p2_done': False,
        }
    s = agent_body.s2
    tx, ty = sandbox.get_target_position()
    sx, sy = sandbox.get_seeker_position()
    vx, vy = sandbox.get_seeker_velocity()
    slots = _rendezvous_slot_intervals(sandbox)
    c_lo, c_hi = sandbox.get_corridor_bounds()
    s['sample_timer'] += 1
    if s['sample_timer'] >= 5:
        s['sample_timer'] = 0
        dt = 5.0 / 60.0
        if s['last_tx'] != 0.0 or s['last_ty'] != 0.0:
            raw_vx = (tx - s['last_tx']) / max(dt, 1e-6)
            raw_vy = (ty - s['last_ty']) / max(dt, 1e-6)
            s['tvx'] = 0.35 * s['tvx'] + 0.65 * raw_vx
            s['tvy'] = 0.35 * s['tvy'] + 0.65 * raw_vy
        s['last_tx'], s['last_ty'] = tx, ty
    GRAV_COMP_X = 70.0
    THRUST_CEILING = 119.0
    p1_slots = [sl for sl in slots if sl[0] < 5500]
    p2_slots = [sl for sl in slots if sl[0] >= 5500]
    in_p1 = any(lo <= step_count <= hi for (lo, hi) in p1_slots)
    in_p2 = any(lo <= step_count <= hi for (lo, hi) in p2_slots)
    in_slot = in_p1 or in_p2
    gx, gy = sx, sy
    if s['phase'] == 0:
        gx, gy = 14.5, 1.35
        if 13.0 <= sx <= 17.0:
            s['act_steps'] += 1
        else:
            s['act_steps'] = 0
        if s['act_steps'] >= 80:
            s['phase'] = 1
    elif s['phase'] == 1:
        if in_p1:
            s['phase'] = 2
        else:
            gx = 0.5 * (c_lo + c_hi)
            gy = 1.35
    elif s['phase'] == 2:
        if not in_p1:
            s['phase'] = 3
            s['p1_done'] = True
        else:
            lead = 0.40
            gx = tx + s['tvx'] * lead
            gy = ty + s['tvy'] * lead
            gx = max(10.0, min(20.0, gx))
            gy = max(1.5, min(3.5, gy))
    elif s['phase'] == 3:
        if in_p2:
            s['phase'] = 4
        else:
            gx = 0.5 * (c_lo + c_hi)
            gy = 1.8
    elif s['phase'] == 4:
        if not in_p2:
            s['phase'] = 5
            s['p2_done'] = True
        else:
            lead = 0.35
            gx = tx + s['tvx'] * lead
            gy = ty + s['tvy'] * lead
            gx = max(10.0, min(20.0, gx))
            gy = max(1.5, min(3.5, gy))
    else:
        dist = math.hypot(tx - sx, ty - sy)
        if dist > 7.0:
            gx, gy = tx, ty
    kp = 45.0
    kd = 15.0
    raw_fx = kp * (gx - sx) - kd * vx
    raw_fy = kp * (gy - sy) - kd * vy
    if in_slot:
        raw_fx += 35.0 * (s['tvx'] - vx)
        raw_fy += 35.0 * (s['tvy'] - vy)
    corridor_margin = 1.5
    corridor_push = 0.0
    if sx < c_lo + corridor_margin:
        corridor_push = 80.0 * (c_lo + corridor_margin - sx)
    elif sx > c_hi - corridor_margin:
        corridor_push = -80.0 * (sx - (c_hi - corridor_margin))
    raw_fx += corridor_push
    if raw_fx < GRAV_COMP_X:
        raw_fx = GRAV_COMP_X
    mag = math.hypot(raw_fx, raw_fy)
    if mag > THRUST_CEILING:
        scale = THRUST_CEILING / mag
        raw_fx *= scale
        raw_fy *= scale
        if raw_fx < GRAV_COMP_X:
            remaining_for_y = math.sqrt(max(0, THRUST_CEILING**2 - GRAV_COMP_X**2))
            raw_fx = GRAV_COMP_X
            if raw_fy > remaining_for_y:
                raw_fy = remaining_for_y
            elif raw_fy < -remaining_for_y:
                raw_fy = -remaining_for_y
    sandbox.apply_seeker_force(raw_fx, raw_fy)

def build_agent_stage_3(sandbox):
    return sandbox.get_seeker_body()

def agent_action_stage_3(sandbox, agent_body, step_count):
    if not hasattr(agent_body, "_s3"):
        agent_body._s3 = {
            "phase": 0,
            "act_steps": 0,
            "last_tx": 0.0, "last_ty": 0.0,
            "tvx": 0.0, "tvy": 0.0,
            "sample_timer": 0,
            "p1_done": False,
            "p2_done": False,
            "rv_est": 0,
            "close_timer": 0,
            "last_blind_free_tx": 0.0,
            "last_blind_free_ty": 0.0,
            "last_blind_free_tvx": 0.0,
            "last_blind_free_tvy": 0.0,
            "blind_timer": 0,
            "blind_entered_step": 0,
            "_was_blind": False,
            "_blind_entry": 0,
        }
    s = agent_body._s3
    tx, ty = sandbox.get_target_position()
    sx, sy = sandbox.get_seeker_position()
    vx, vy = sandbox.get_seeker_velocity()
    slots = _rendezvous_slot_intervals(sandbox)
    c_lo, c_hi = sandbox.get_corridor_bounds()
    blind_zone = 12.5 <= sx <= 17.0
    s["sample_timer"] += 1
    if s["sample_timer"] >= 3:
        s["sample_timer"] = 0
        dt = 3.0 / 60.0
        if not blind_zone:
            if s["last_tx"] != 0.0 or s["last_ty"] != 0.0:
                raw_vx = (tx - s["last_tx"]) / max(dt, 1e-6)
                raw_vy = (ty - s["last_ty"]) / max(dt, 1e-6)
                s["tvx"] = 0.25 * s["tvx"] + 0.75 * raw_vx
                s["tvy"] = 0.25 * s["tvy"] + 0.75 * raw_vy
            s["last_tx"], s["last_ty"] = tx, ty

            s["last_blind_free_tx"] = tx
            s["last_blind_free_ty"] = ty
            s["last_blind_free_tvx"] = s["tvx"]
            s["last_blind_free_tvy"] = s["tvy"]
            s["blind_timer"] = 0
        else:
            if s["blind_timer"] == 0:
                s["blind_entered_step"] = step_count
            s["blind_timer"] += 1

    use_tx, use_ty = tx, ty
    if blind_zone and s["last_blind_free_tx"] != 0.0:
        dt_est = min(s["blind_timer"] * 3.0 / 60.0, 0.7)
        use_tx = s["last_blind_free_tx"] + s["last_blind_free_tvx"] * dt_est
        use_ty = s["last_blind_free_ty"] + s["last_blind_free_tvy"] * dt_est
        use_tx = max(6.0, min(26.0, use_tx))
        use_ty = max(1.5, min(3.5, use_ty))

    dist = math.hypot(use_tx - sx, use_ty - sy)
    dx, dy = use_tx - sx, use_ty - sy

    if blind_zone and not s.get("_was_blind", False):
        s["_blind_entry"] = step_count
    s["_was_blind"] = blind_zone
    GRAV_X = 70.0
    THRUST_CEILING = 189.0
    DAMP = 40.0
    p1_slots = [sl for sl in slots if sl[0] < 5500]
    p2_slots = [sl for sl in slots if sl[0] >= 5500]
    in_p1 = any(lo <= step_count <= hi for (lo, hi) in p1_slots)
    in_p2 = any(lo <= step_count <= hi for (lo, hi) in p2_slots)
    in_slot = in_p1 or in_p2
    in_rz = 10.0 <= sx <= 20.0
    rel_spd = math.hypot(vx - s["tvx"], vy - s["tvy"])
    near_target = dist < 6.0 and rel_spd < 2.0 and in_rz
    if near_target and in_slot:
        s["close_timer"] += 1
    else:
        s["close_timer"] = 0
    if s["close_timer"] >= 5 and s["rv_est"] < 1 and in_p1:
        s["rv_est"] = 1; s["close_timer"] = 0
    if s["close_timer"] >= 5 and s["rv_est"] == 1 and in_p2:
        s["rv_est"] = 2; s["close_timer"] = 0
    if in_slot:
        mode = "chase"
    elif s["rv_est"] >= 1 or step_count > 6900:
        mode = "track"
    else:
        mode = "chase"
    gx, gy = sx, sy
    if s["phase"] == 0:
        gx, gy = 14.0, 1.55
        if 13.0 <= sx <= 17.0:
            s["act_steps"] += 1
        else:
            s["act_steps"] = 0
        if s["act_steps"] >= 80:
            s["phase"] = 1
    elif s["phase"] == 1:
        if in_p1: s["phase"] = 2
        else: gx = 0.5 * (c_lo + c_hi); gy = 1.55
    elif s["phase"] == 2:
        if not in_p1:
            s["phase"] = 3; s["p1_done"] = True
        else:
            lead = 0.40
            gx = use_tx + s["tvx"] * lead; gy = use_ty + s["tvy"] * lead
            gx = max(10.0, min(20.0, gx)); gy = max(1.5, min(3.5, gy))
    elif s["phase"] == 3:
        if in_p2: s["phase"] = 4
        elif s["rv_est"] >= 1:
            gx, gy = use_tx, use_ty
        else:
            gx = 0.5 * (c_lo + c_hi); gy = 1.8
    elif s["phase"] == 4:
        if not in_p2:
            s["phase"] = 5; s["p2_done"] = True
        else:
            lead = 0.35
            gx = use_tx + s["tvx"] * lead; gy = use_ty + s["tvy"] * lead
            gx = max(10.0, min(20.0, gx)); gy = max(1.5, min(3.5, gy))
    else:
        if in_p2:
            lead = 0.35
            gx = use_tx + s["tvx"] * lead; gy = use_ty + s["tvy"] * lead
            gx = max(10.0, min(20.0, gx)); gy = max(1.5, min(3.5, gy))
        else:
            gx, gy = use_tx, use_ty
    safe_margin = 2.0
    safe_lo = c_lo + safe_margin
    safe_hi = c_hi - safe_margin
    if safe_lo < safe_hi:
        gx = max(safe_lo, min(safe_hi, gx))
    dx_g = gx - sx
    dy_g = gy - sy
    if mode == "track":
        if s.get("_blind_entry", 0) > 0 and step_count - s["_blind_entry"] > 600:
            if sx < c_lo + 3.0:
                raw_fx = THRUST_CEILING
            elif sx > c_hi - 3.0:
                raw_fx = 0.0
            elif sx > 15.5:
                raw_fx = THRUST_CEILING
            else:
                raw_fx = 15.0
            raw_fy = 0.0
        elif 14.0 <= sx <= 17.0:
            wind_ff = 65.0
            if dx_g > 0:
                raw_fx = DAMP * s["tvx"] + GRAV_X + wind_ff + 40.0 * dx_g + 20.0 * (s["tvx"] - vx)
            else:
                raw_fx = 0.0 + 40.0 * dx_g + 15.0 * (s["tvx"] - vx)
            raw_fy = 0.0
        else:
            if dx_g > 0:
                raw_fx = DAMP * s["tvx"] + GRAV_X + 40.0 * dx_g + 20.0 * (s["tvx"] - vx)
                raw_fy = 40.0 * dy_g - 15.0 * vy + 15.0 * (s["tvy"] - vy)
            else:
                raw_fx = 0.0 + 40.0 * dx_g + 15.0 * (s["tvx"] - vx)
                raw_fy = 0.0
    elif in_slot:
        kp = 55.0; kd = 18.0
        raw_fx = kp * dx_g - kd * vx + 40.0 * (s["tvx"] - vx)
        raw_fy = kp * dy_g - kd * vy + 40.0 * (s["tvy"] - vy)
    else:
        kp = 45.0; kd = 15.0
        raw_fx = kp * dx_g - kd * vx
        raw_fy = kp * dy_g - kd * vy
    if mode == "track":
        em = 1.5
        if sx < c_lo + em:
            deficit = c_lo + em - sx
            raw_fx = max(raw_fx, 70.0 + 350.0 * deficit)
        elif sx > c_hi - em:
            deficit = sx - (c_hi - em)
            max_fx = max(0.0, 70.0 - 350.0 * deficit)
            raw_fx = min(raw_fx, max_fx)
    else:
        cs_margin = 2.5
        if sx < c_lo + cs_margin:
            deficit = c_lo + cs_margin - sx
            min_fx_needed = 70.0 + 250.0 * deficit
            if raw_fx < min_fx_needed:
                raw_fx = min_fx_needed
            if vx < -0.1:
                raw_fx += 180.0 * abs(vx)
        elif sx > c_hi - cs_margin:
            deficit = sx - (c_hi - cs_margin)
            max_fx_allowed = 70.0 - 250.0 * deficit
            if max_fx_allowed < 0.0:
                max_fx_allowed = 0.0
            if raw_fx > max_fx_allowed:
                raw_fx = max_fx_allowed
            if vx > 0.1:
                raw_fx -= 180.0 * abs(vx)
                if raw_fx < 0.0:
                    raw_fx = 0.0
    if (mode == "chase" and in_slot) and raw_fx < GRAV_X:
        raw_fx = GRAV_X
    elif mode == "chase" and not in_slot and raw_fx < 5.0:
        raw_fx = 5.0
    for ox, oy, ohw, ohh in [(7.5, 1.3, 0.3, 0.3), (20.5, 1.3, 0.3, 0.3)]:
        odx = sx - ox; ody = sy - oy
        odist = math.hypot(odx, ody)
        safe_r = 0.35 + max(ohw, ohh) + 0.5
        if odist < safe_r and odist > 0.001:
            repulse = 200.0 * (safe_r - odist) / odist
            raw_fx += repulse * odx
            if mode != "track":
                raw_fy += repulse * ody
    if raw_fx < 0.0:
        raw_fx = 0.0

    if mode == "track" and raw_fx < 0.1:
        raw_fx = 0.1
    mag = math.hypot(raw_fx, raw_fy)
    if mag > THRUST_CEILING:
        scale = THRUST_CEILING / mag
        raw_fx *= scale
        raw_fy *= scale
        if raw_fx < 0.0:
            raw_fx = 0.0
            max_fy = THRUST_CEILING
            if raw_fy > max_fy: raw_fy = max_fy
            elif raw_fy < -max_fy: raw_fy = -max_fy
    sandbox.apply_seeker_force(raw_fx, raw_fy)

def build_agent_stage_4(sandbox):
    return sandbox.get_seeker_body()

def agent_action_stage_4(sandbox, agent_body, step_count):
    if not hasattr(agent_body, 's4'):
        agent_body.s4 = {
            'phase': 0,
            'act_steps': 0,
            'last_tx': 0.0,
            'last_ty': 0.0,
            'tvx': 0.0,
            'tvy': 0.0,
            'sample_timer': 0,
            'rv1_done': False,
            'rv2_done': False,
        }
    s = agent_body.s4
    THRUST_MAX = 63.0
    tx, ty = sandbox.get_target_position()
    sx, sy = sandbox.get_seeker_position()
    vx, vy = sandbox.get_seeker_velocity()
    slots = _rendezvous_slot_intervals(sandbox)
    c_lo, c_hi = sandbox.get_corridor_bounds()
    dist = math.hypot(tx - sx, ty - sy)
    s['sample_timer'] += 1
    if (tx, ty) != (s['last_tx'], s['last_ty']):
        if s['last_tx'] != 0.0 or s['last_ty'] != 0.0:
            dt_est = max(s['sample_timer'], 5) / 60.0
            raw_vx = (tx - s['last_tx']) / dt_est
            raw_vy = (ty - s['last_ty']) / dt_est
            s['tvx'] = 0.35 * s['tvx'] + 0.65 * raw_vx
            s['tvy'] = 0.35 * s['tvy'] + 0.65 * raw_vy
        s['last_tx'], s['last_ty'] = tx, ty
        s['sample_timer'] = 0
    elif s['sample_timer'] > 25:
        s['tvx'] *= 0.92
        s['tvy'] *= 0.92
    p1_slots = [sl for sl in slots if sl[0] < 5500]
    p2_slots = [sl for sl in slots if sl[0] >= 5500]
    in_p1 = any(lo <= step_count <= hi for (lo, hi) in p1_slots)
    in_p2 = any(lo <= step_count <= hi for (lo, hi) in p2_slots)
    in_slot = in_p1 or in_p2
    p1_next = None
    p2_next = None
    if not in_p1:
        for lo, hi in p1_slots:
            if lo > step_count:
                if p1_next is None or lo < p1_next:
                    p1_next = lo
    if not in_p2:
        for lo, hi in p2_slots:
            if lo > step_count:
                if p2_next is None or lo < p2_next:
                    p2_next = lo
    mode = 'position'
    gx, gy = sx, sy
    if s['phase'] == 0:
        gx, gy = 14.2, 1.45
        if 13.0 <= sx <= 17.0:
            s['act_steps'] += 1
        else:
            s['act_steps'] = 0
        if s['act_steps'] >= 80:
            s['phase'] = 1
    elif s['phase'] == 1:
        if in_p1:
            s['phase'] = 2
            mode = 'slot'
        else:
            mode = 'standoff'
            standoff = 5.0
            if p1_next is not None:
                steps_to = p1_next - step_count
                if steps_to < 80:
                    standoff = 3.5
                elif steps_to < 200:
                    standoff = 4.5
            if dist > 0.05:
                ux = (sx - tx) / dist
                uy = (sy - ty) / dist
                gx = tx + ux * standoff
                gy = ty + uy * standoff
            else:
                gx, gy = tx, ty + standoff
    elif s['phase'] == 2:
        if not in_p1:
            s['phase'] = 3
            s['rv1_done'] = True
            mode = 'standoff'
        else:
            mode = 'slot'
    elif s['phase'] == 3:
        if in_p1:
            s['phase'] = 2
            mode = 'slot'
        elif in_p2:
            s['phase'] = 4
            mode = 'slot'
        else:
            mode = 'standoff'
            standoff = 5.0
            if p2_next is not None:
                steps_to = p2_next - step_count
                if steps_to < 80:
                    standoff = 3.5
                elif steps_to < 200:
                    standoff = 4.5
            if dist > 0.05:
                ux = (sx - tx) / dist
                uy = (sy - ty) / dist
                gx = tx + ux * standoff
                gy = ty + uy * standoff
            else:
                gx, gy = tx, ty + standoff
    elif s['phase'] == 4:
        if not in_p2:
            s['phase'] = 5
            s['rv2_done'] = True
            mode = 'track'
        else:
            mode = 'slot'
    else:
        if in_p2:
            s['phase'] = 4
            mode = 'slot'
        else:
            mode = 'track'
            if dist > 5.5:
                gx, gy = tx, ty
            else:
                gx, gy = sx, sy
    margin = 2.5
    safe_lo = c_lo + margin
    safe_hi = c_hi - margin
    if safe_lo < safe_hi:
        gx = max(safe_lo, min(safe_hi, gx))
    gy = max(1.45, min(3.5, gy))
    raw_fx = raw_fy = 0.0
    if mode == 'position':
        dx_g = gx - sx
        dy_g = gy - sy
        raw_fx = 40.0 * dx_g - 8.0 * vx
        raw_fy = 35.0 * dy_g - 5.0 * vy
    elif mode == 'standoff':
        dx_g = gx - sx
        dy_g = gy - sy
        raw_fx = 50.0 * dx_g - 5.0 * vx
        raw_fy = 50.0 * dy_g - 5.0 * vy
    elif mode == 'slot':
        dx = tx - sx
        dy = ty - sy
        d_mag = math.hypot(dx, dy)
        tv_mag = math.hypot(s['tvx'], s['tvy'])
        if tv_mag > 0.15 and d_mag > 0.01:
            dot = dx * s['tvx'] + dy * s['tvy']
            if dot < -0.2 * d_mag * tv_mag:
                raw_fx = s['tvx'] / tv_mag * THRUST_MAX
                raw_fy = s['tvy'] / tv_mag * THRUST_MAX
            else:
                raw_fx = dx / d_mag * THRUST_MAX
                raw_fy = dy / d_mag * THRUST_MAX
        else:
            if d_mag > 0.01:
                raw_fx = dx / d_mag * THRUST_MAX
                raw_fy = dy / d_mag * THRUST_MAX
    elif mode == 'track':
        WIND_LO = 14.0
        WIND_HI = 17.0
        trk_margin = 2.5
        safe_lo = c_lo + trk_margin
        safe_hi = c_hi - trk_margin
        if safe_lo >= safe_hi:
            safe_lo = safe_hi = 0.5 * (c_lo + c_hi)
        if not hasattr(agent_body, '_trk_tx_smooth'):
            agent_body._trk_tx_smooth = tx
            agent_body._trk_side = 0
        agent_body._trk_tx_smooth = 0.7 * agent_body._trk_tx_smooth + 0.3 * tx
        corridor_center = 0.5 * (c_lo + c_hi)
        clamped_tx = max(safe_lo, min(safe_hi, tx))
        chase_tx = 0.6 * clamped_tx + 0.4 * corridor_center
        chase_ty = max(1.5, min(3.0, ty))
        dx = chase_tx - sx
        dy = chase_ty - sy
        d = math.hypot(dx, dy)
        if d > 0.01:
            raw_fx = dx / d * THRUST_MAX - 3.0 * vx
            raw_fy = dy / d * THRUST_MAX - 3.0 * vy
    cs_m = 2.5
    if sx < c_lo + cs_m:
        deficit = c_lo + cs_m - sx
        raw_fx = max(raw_fx, 250.0 * deficit)
    elif sx > c_hi - cs_m:
        deficit = sx - (c_hi - cs_m)
        raw_fx = min(raw_fx, -250.0 * deficit)
    if mode != 'track':
        rz_margin = 1.5
        if sx < 10.0 + rz_margin:
            raw_fx = max(raw_fx, 250.0 * (10.0 + rz_margin - sx))
        elif sx > 20.0 - rz_margin:
            raw_fx = min(raw_fx, -250.0 * (sx - (20.0 - rz_margin)))
    mag = math.hypot(raw_fx, raw_fy)
    if mag > THRUST_MAX:
        raw_fx *= THRUST_MAX / mag
        raw_fy *= THRUST_MAX / mag
    sandbox.apply_seeker_force(raw_fx, raw_fy)
