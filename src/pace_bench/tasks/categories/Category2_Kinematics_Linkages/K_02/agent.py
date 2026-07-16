import math

def build_agent(sandbox):
    start_x = 4.5
    top = sandbox.add_beam(start_x, 21.5, 0.4, 1.0, density=5.0)
    prev_b = top
    for i in range(6, -1, -1):
        y = 1.5 + i * 3.0
        b = sandbox.add_beam(start_x, y, 0.4, 3.0, density=5.0)
        joint_y = y + 1.5
        sandbox.add_joint(prev_b, b, (start_x, joint_y), type='rigid')
        prev_b = b
    return top

def agent_action(sandbox, agent_body, step_count):
    pass

def _apply_climb_action(sandbox, step_count):
    c = getattr(sandbox, '_climber_joints', {})
    if not c: return
    cycle = c['cycle']
    phase = step_count % (2 * cycle)
    overlap = c.get('overlap', 10)
    speed = c.get('speed', 10.0)
    torque = c.get('torque', 1000.0)
    if phase < cycle:
        for p in c['p_torso']: sandbox.set_pad_active(p, True)
        if phase > overlap:
            for p in c['p_arm']: sandbox.set_pad_active(p, False)
        else:
            for p in c['p_arm']: sandbox.set_pad_active(p, True)
        sandbox.set_motor(c['joint'], speed, torque)
    else:
        for p in c['p_arm']: sandbox.set_pad_active(p, True)
        if (phase - cycle) > overlap:
            for p in c['p_torso']: sandbox.set_pad_active(p, False)
        else:
            for p in c['p_torso']: sandbox.set_pad_active(p, True)
        sandbox.set_motor(c['joint'], -speed, torque)

def build_agent_stage_1(sandbox):
    x_pos = 4.9
    base_y = 1.5
    torso = sandbox.add_beam(x_pos, base_y, 0.05, 0.4, density=0.03)
    p1 = sandbox.add_pad(x_pos + 0.1, base_y - 0.12, radius=0.06, density=0.03)
    p2 = sandbox.add_pad(x_pos + 0.1, base_y + 0.12, radius=0.06, density=0.03)
    sandbox.add_joint(torso, p1, (x_pos + 0.1, base_y - 0.12), type='rigid')
    sandbox.add_joint(torso, p2, (x_pos + 0.1, base_y + 0.12), type='rigid')
    arm = sandbox.add_beam(x_pos, base_y + 0.6, 0.04, 0.8, density=0.03)
    p3 = sandbox.add_pad(x_pos + 0.1, base_y + 0.9, radius=0.06, density=0.03)
    p4 = sandbox.add_pad(x_pos + 0.1, base_y + 1.0, radius=0.06, density=0.03)
    sandbox.add_joint(arm, p3, (x_pos + 0.1, base_y + 0.9), type='rigid')
    sandbox.add_joint(arm, p4, (x_pos + 0.1, base_y + 1.0), type='rigid')
    joint = sandbox.add_joint(torso, arm, (x_pos, base_y + 0.2), type='pivot', lower_limit=-0.05, upper_limit=2.0)
    sandbox._climber_joints = {
        'p_torso': [p1, p2],
        'p_arm': [p3, p4],
        'joint': joint,
        'cycle': 100,
        'speed': 1.5,
        'torque': 2.0,
        'overlap': 15
    }
    return torso

def agent_action_stage_1(sandbox, agent_body, step_count):
    _apply_climb_action(sandbox, step_count)

def build_agent_stage_2(sandbox):
    x_pos = 4.85
    base_y = 1.0
    torso = sandbox.add_beam(x_pos, base_y, 0.05, 0.6, density=0.4)
    p1 = sandbox.add_pad(x_pos + 0.1, base_y - 0.2, radius=0.1, density=0.2)
    p2 = sandbox.add_pad(x_pos + 0.1, base_y + 0.2, radius=0.1, density=0.2)
    sandbox.add_joint(torso, p1, (x_pos + 0.1, base_y - 0.2), type='rigid')
    sandbox.add_joint(torso, p2, (x_pos + 0.1, base_y + 0.2), type='rigid')
    arm = sandbox.add_beam(x_pos, 4.0, 0.1, 8.0, density=0.4)
    p3 = sandbox.add_pad(x_pos + 0.1, 7.8, radius=0.1, density=0.2)
    p4 = sandbox.add_pad(x_pos + 0.1, 8.0, radius=0.1, density=0.2)
    sandbox.add_joint(arm, p3, (x_pos + 0.1, 7.8), type='rigid')
    sandbox.add_joint(arm, p4, (x_pos + 0.1, 8.0), type='rigid')
    joint = sandbox.add_joint(torso, arm, (x_pos, 1.3), type='pivot', lower_limit=-0.1, upper_limit=5.0)
    sandbox._climber_joints = {
        'p_torso': [p1, p2],
        'p_arm': [p3, p4],
        'joint': joint,
        'cycle': 200,
        'speed': 10.0,
        'torque': 100000.0,
        'overlap': 50
    }
    return torso

def agent_action_stage_2(sandbox, agent_body, step_count):
    _apply_climb_action(sandbox, step_count)

def build_agent_stage_3(sandbox):
    wall_x = 5.0
    base_y = 1.0
    torso = sandbox.add_beam(wall_x - 0.15, base_y, 0.16, 0.8, density=290.0)
    p_torso = sandbox.add_pad(wall_x, base_y, radius=0.10, density=48.0)
    sandbox.add_joint(torso, p_torso, (wall_x, base_y), type='rigid')
    arm = sandbox.add_beam(wall_x - 0.15, base_y + 0.8, 0.05, 0.4, density=215.0)
    p_arm = sandbox.add_pad(wall_x, base_y + 1.0, radius=0.06, density=22.0)
    sandbox.add_joint(arm, p_arm, (wall_x, base_y + 1.0), type='rigid')
    joint = sandbox.add_joint(torso, arm, (wall_x - 0.15, base_y + 0.4), type='pivot', lower_limit=-0.1, upper_limit=4.0)
    sandbox._climber_joints = {
        'p_torso': [p_torso],
        'p_arm': [p_arm],
        'joint': joint,
        'cycle': 60,
        'speed': 3.5,
        'torque': 500.0,
        'overlap': 25
    }
    return torso

def agent_action_stage_3(sandbox, agent_body, step_count):
    _apply_climb_action(sandbox, step_count)

def build_agent_stage_4(sandbox):
    x_pos = 4.8
    base_y = 1.0
    torso = sandbox.add_beam(x_pos, base_y, 0.2, 0.8, density=100.0)
    p1 = sandbox.add_pad(x_pos + 0.1, base_y - 0.2, radius=0.12, density=10.0)
    p2 = sandbox.add_pad(x_pos + 0.1, base_y + 0.2, radius=0.12, density=10.0)
    sandbox.add_joint(torso, p1, (x_pos + 0.1, base_y - 0.2), type='rigid')
    sandbox.add_joint(torso, p2, (x_pos + 0.1, base_y + 0.2), type='rigid')
    arm = sandbox.add_beam(x_pos, base_y + 1.2, 0.2, 1.8, density=50.0)
    p3 = sandbox.add_pad(x_pos + 0.1, base_y + 1.8, radius=0.12, density=10.0)
    p4 = sandbox.add_pad(x_pos + 0.1, base_y + 2.0, radius=0.12, density=10.0)
    sandbox.add_joint(arm, p3, (x_pos + 0.1, base_y + 1.8), type='rigid')
    sandbox.add_joint(arm, p4, (x_pos + 0.1, base_y + 2.0), type='rigid')
    joint = sandbox.add_joint(torso, arm, (x_pos, base_y + 0.4), type='pivot', lower_limit=-0.1, upper_limit=3.5)
    sandbox._climber_joints = {
        'p_torso': [p1, p2],
        'p_arm': [p3, p4],
        'joint': joint,
        'cycle': 150,
        'speed': 8.0,
        'torque': 150000.0,
        'overlap': 40
    }
    return torso

def agent_action_stage_4(sandbox, agent_body, step_count):
    _apply_climb_action(sandbox, step_count)
