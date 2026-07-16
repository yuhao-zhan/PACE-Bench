import math

def build_agent(sandbox):
    col_l = sandbox.add_beam(8.0, 2.0, 0.4, 4.0, angle=0, density=10.0)
    col_r = sandbox.add_beam(12.0, 2.0, 0.4, 4.0, angle=0, density=10.0)
    sandbox.add_joint(col_l, None, (8.0, 0.0), type='rigid')
    sandbox.add_joint(col_r, None, (12.0, 0.0), type='rigid')
    roof = sandbox.add_beam(10.0, 4.2, 6.0, 0.4, angle=0, density=10.0)
    sandbox.add_joint(col_l, roof, (8.0, 4.0), type='rigid')
    sandbox.add_joint(col_r, roof, (12.0, 4.0), type='rigid')
    return col_l

def agent_action(sandbox, agent_body, step_count):
    pass

def build_agent_stage_1(sandbox):
    d = 0.06
    p1 = sandbox.add_beam(8.0, 2.0, 0.2, 3.5, angle=0, density=d)
    p2 = sandbox.add_beam(12.0, 2.0, 0.2, 3.5, angle=0, density=d)
    sandbox.add_joint(p1, None, (8.0, 0.0), type='rigid')
    sandbox.add_joint(p2, None, (12.0, 0.0), type='rigid')
    r1 = sandbox.add_beam(8.5, 3.9, 1.0, 0.15, angle=0, density=d)
    r2 = sandbox.add_beam(9.5, 3.9, 1.0, 0.15, angle=0, density=d)
    r3 = sandbox.add_beam(10.5, 3.9, 1.0, 0.15, angle=0, density=d)
    r4 = sandbox.add_beam(11.5, 3.9, 1.0, 0.15, angle=0, density=d)
    sandbox.add_joint(p1, r1, (8.0, 3.5), type='rigid')
    sandbox.add_joint(r1, r2, (9.0, 3.5), type='rigid')
    sandbox.add_joint(r2, r3, (10.0, 3.5), type='rigid')
    sandbox.add_joint(r3, r4, (11.0, 3.5), type='rigid')
    sandbox.add_joint(p2, r4, (12.0, 3.5), type='rigid')
    return p1

def build_agent_stage_2(sandbox):
    d = 0.035
    post_h = 2.0
    post_xs = [6.3, 6.9, 7.5, 8.1, 8.7, 9.3, 9.9, 10.5, 11.1]
    posts = []
    for px in post_xs:
        p = sandbox.add_beam(px, post_h / 2, 0.15, post_h, angle=0, density=d)
        sandbox.add_joint(p, None, (px, 0.0), type='rigid')
        posts.append(p)
    roof_w = 8.8
    roof_cx = 8.7
    roof_h = 0.10
    roof = sandbox.add_beam(roof_cx, post_h, roof_w, roof_h, angle=0, density=d)
    for px, p in zip(post_xs, posts):
        sandbox.add_joint(p, roof, (px, post_h - roof_h / 2), type='rigid')
    return posts[0]

def build_agent_stage_3(sandbox):
    d = 0.04
    post_xs = [6.5, 8.25, 9.0, 11.0, 11.75, 13.5]
    posts = []
    for px in post_xs:
        post = sandbox.add_beam(px, 2.0, 0.20, 3.5, angle=0, density=d)
        sandbox.add_joint(post, None, (px, 0.0), type='rigid')
        posts.append(post)
    roof = sandbox.add_beam(10.0, 3.55, 7.0, 0.2, angle=0, density=d)
    for px, post in zip(post_xs, posts):
        sandbox.add_joint(post, roof, (px, 3.5), type='rigid')
    return posts[0]

def build_agent_stage_4(sandbox):
    d = 0.066
    post_h = 4.5
    offset = 0.4
    post_cy = post_h / 2 + offset
    # Leave the core's physical footprint clear; the keep-out API checks beam
    # centers, while a full-height member near x=14 can still touch the core.
    post_xs = [5.1, 6.0, 6.9, 8.7573, 8.7, 9.6, 10.5, 11.4, 12.2]
    posts = []
    for px in post_xs:
        p = sandbox.add_beam(px, post_cy, 0.16, post_h, angle=0, density=d)
        sandbox.add_joint(p, None, (px, 0.0), type='rigid')
        posts.append(p)
    roof_cy = post_h + offset + 0.12
    roof = sandbox.add_beam(10.0, roof_cy, 10.0, 0.16, angle=0, density=d)
    for px, p in zip(post_xs, posts):
        sandbox.add_joint(p, roof, (px, post_h + offset - 0.08), type='rigid')
    wall_h = post_h + offset + 0.4
    wall_cy = wall_h / 2
    rwall = sandbox.add_beam(14.9, wall_cy, 0.16, wall_h, angle=0, density=d)
    for ay in [0.0, 0.55, 1.1, 1.65, 2.2, 2.75, 3.3, 3.85, 4.4]:
        sandbox.add_joint(rwall, None, (14.9, ay), type='rigid')
    inner_wall = sandbox.add_beam(13.2, wall_cy, 0.16, wall_h, angle=0, density=0.0035)
    for ay in [0.0, 0.55, 1.1, 1.65, 2.2, 2.75, 3.3, 3.85, 4.4]:
        sandbox.add_joint(inner_wall, None, (13.2, ay), type='rigid')
    return posts[0]

def agent_action_stage_1(sandbox, agent_body, step_count):
    pass

def agent_action_stage_2(sandbox, agent_body, step_count):
    pass

def agent_action_stage_3(sandbox, agent_body, step_count):
    pass

def agent_action_stage_4(sandbox, agent_body, step_count):
    pass
