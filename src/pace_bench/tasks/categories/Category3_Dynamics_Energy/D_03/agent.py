import math

def build_agent(sandbox):
    cabin = sandbox.get_vehicle_cabin()
    if cabin is None:
        raise ValueError("Cart not found")
    beams = []
    for (xx, yy) in [(4.8, 2.6), (4.9, 2.6), (5.0, 2.6), (5.1, 2.6)]:
        b = sandbox.add_beam(xx, yy, 0.08, 0.16, angle=0, density=5.0)
        sandbox.add_joint(cabin, b, (xx, yy), type="rigid")
        beams.append(b)
    return cabin

def agent_action(sandbox, agent_body, step_count):
    pass

def build_agent_stage_1(sandbox):
    cabin = sandbox.get_vehicle_cabin()
    beams = []
    for (xx, yy) in [(4.8, 2.6), (4.9, 2.6), (5.0, 2.6), (5.1, 2.6)]:
        b = sandbox.add_beam(xx, yy, 0.08, 0.16, angle=0, density=1.0)
        sandbox.add_joint(cabin, b, (xx, yy), type="rigid")
        beams.append(b)
    return cabin

def agent_action_stage_1(sandbox, agent_body, step_count):
    if agent_body is None:
        return
    pos = sandbox.get_vehicle_position()
    vel = sandbox.get_vehicle_velocity()
    if pos is None or vel is None:
        return
    x, vx, vy = pos[0], vel[0], vel[1]
    speed = math.sqrt(vx * vx + vy * vy)
    if x < 8.0:
        return
    if x < 9.0:
        sandbox.apply_force(agent_body, (700.0, 0.0))
    elif x < 11.0:
        target_v = 2.2
        force_mag = (target_v - speed) * 350.0
        force_mag = max(-1200.0, min(1200.0, force_mag))
        sandbox.apply_force(agent_body, (force_mag, 0.0))
    else:
        target_v = 1.6
        force_mag = (target_v - speed) * 300.0
        force_mag = max(-500.0, min(500.0, force_mag))
        sandbox.apply_force(agent_body, (force_mag, 0.0))

def build_agent_stage_2(sandbox):
    cabin = sandbox.get_vehicle_cabin()
    if cabin is None:
        raise ValueError("Cart not found")
    beams = []
    for (xx, yy) in [(4.8, 2.6), (4.9, 2.6), (5.0, 2.6), (5.1, 2.6)]:
        b = sandbox.add_beam(xx, yy, 0.08, 0.16, angle=0, density=5.0)
        sandbox.add_joint(cabin, b, (xx, yy), type="rigid")
        beams.append(b)
    return cabin

def agent_action_stage_2(sandbox, agent_body, step_count):
    if agent_body is None:
        return
    pos = sandbox.get_vehicle_position()
    vel = sandbox.get_vehicle_velocity()
    if pos is None or vel is None:
        return
    x, vx, vy = pos[0], vel[0], vel[1]
    speed = math.sqrt(vx * vx + vy * vy)
    if x < 8.0:
        thrust = 1200.0
        target_v = 7.5
    elif x < 11.0:
        thrust = 280.0
        target_v = 3.0
    else:
        thrust = 150.0
        target_v = 1.8
    kp = 400.0
    correction = kp * (target_v - vx)
    force_x = thrust + correction
    force_x = max(0.0, min(2500.0, force_x))
    sandbox.apply_force(agent_body, (force_x, 0.0))

def build_agent_stage_3(sandbox):
    cabin = sandbox.get_vehicle_cabin()
    beams = []
    for (xx, yy) in [(4.8, 2.6), (4.9, 2.6), (5.0, 2.6), (5.1, 2.6)]:
        b = sandbox.add_beam(xx, yy, 0.08, 0.16, angle=0, density=60.0)
        sandbox.add_joint(cabin, b, (xx, yy), type="rigid")
        beams.append(b)
    return cabin

def agent_action_stage_3(sandbox, agent_body, step_count):
    if agent_body is None:
        return
    pos = sandbox.get_vehicle_position()
    vel = sandbox.get_vehicle_velocity()
    if pos is None or vel is None:
        return
    x, vx, vy = pos[0], vel[0], vel[1]
    speed = math.sqrt(vx * vx + vy * vy)

    if x < 8.0:
        target_v = 7.0
        kp = 600.0
        ff = 800.0
        force = (target_v - vx) * kp + ff
        force = max(0.0, min(5000.0, force))
    elif x < 9.0:
        force = 5000.0
    elif x < 10.5:
        target_v = 3.2
        kp = 500.0
        ff = 200.0
        force = (target_v - vx) * kp + ff
        force = max(-1000.0, min(3000.0, force))
    else:
        target_v = 1.8
        kp = 400.0
        force = (target_v - vx) * kp
        force = max(-800.0, min(1200.0, force))

    sandbox.apply_force(agent_body, (force, 0.0))

def build_agent_stage_4(sandbox):
    cabin = sandbox.get_vehicle_cabin()
    beams = []
    for (xx, yy) in [(4.8, 2.6), (4.9, 2.6), (5.0, 2.6), (5.1, 2.6), (5.2, 2.6)]:
        b = sandbox.add_beam(xx, yy, 0.08, 0.16, angle=0, density=1.0)
        sandbox.add_joint(cabin, b, (xx, yy), type="rigid")
        beams.append(b)
    return cabin

def agent_action_stage_4(sandbox, agent_body, step_count):
    if agent_body:
        pos = sandbox.get_vehicle_position()
        vel = sandbox.get_vehicle_velocity()
        if pos is None or vel is None:
            return
        x, v = pos[0], vel[0]
        if x < 9.0:
            target_v = 10.0
        elif x < 11.0:
            target_v = 2.0
        else:
            target_v = 1.5
        force_mag = (target_v - v) * 500.0
        sandbox.apply_force(agent_body, (force_mag, 0.0))
