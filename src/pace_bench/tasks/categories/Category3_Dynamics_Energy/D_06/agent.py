import math

GROUND_TOP = 0.5

def build_agent(sandbox):
    density = 0.05
    pillar_w = 0.1
    rest = 0.0
    slab_y = 2.65
    p1 = sandbox.add_beam(7.08, 1.75, pillar_w, 2.5, 0, density)
    sandbox.set_material_properties(p1, restitution=rest)
    sandbox.add_joint(p1, None, (7.08, GROUND_TOP), type="rigid")
    p2 = sandbox.add_beam(7.16, 1.75, pillar_w, 2.5, 0, density)
    sandbox.set_material_properties(p2, restitution=rest)
    sandbox.add_joint(p2, None, (7.16, GROUND_TOP), type="rigid")
    slab_left = sandbox.add_beam(7.12, slab_y, 0.2, 0.22, 0, density)
    sandbox.set_material_properties(slab_left, restitution=0.0)
    sandbox.add_joint(p1, slab_left, (7.08, slab_y), type="rigid")
    sandbox.add_joint(p2, slab_left, (7.16, slab_y), type="rigid")
    p5 = sandbox.add_beam(9.75, 1.75, pillar_w, 2.0, 0, density)
    sandbox.set_material_properties(p5, restitution=rest)
    sandbox.add_joint(p5, None, (9.75, GROUND_TOP), type="rigid")
    slab_right_a = sandbox.add_beam(9.75, slab_y, 0.35, 0.25, 0, density)
    sandbox.set_material_properties(slab_right_a, restitution=0.0)
    sandbox.add_joint(p5, slab_right_a, (9.75, slab_y), type="rigid")
    slab_right_b = sandbox.add_beam(10.75, 1.7, 0.45, 0.3, 0, density)
    sandbox.set_material_properties(slab_right_b, restitution=0.0)
    sandbox.add_joint(slab_right_b, None, (10.75, GROUND_TOP), type="rigid")
    n = len(sandbox.bodies)
    if n > sandbox.MAX_BEAM_COUNT:
        raise ValueError(f"Beam count {n} > {sandbox.MAX_BEAM_COUNT}")
    mass = sandbox.get_structure_mass()
    if mass >= sandbox.MAX_STRUCTURE_MASS:
        raise ValueError(f"Mass {mass:.2f} must be < {sandbox.MAX_STRUCTURE_MASS} kg")
    return slab_right_a

def agent_action(sandbox, agent_body, step_count):
    pass

def _horizontal_grid_absorber(
    sandbox,
    *,
    density: float,
    damping: float,
    x_inner: float,
    x_outer: float,
    anchor_density: float = 1.0,
    width: float = 0.4,

):
    anchor = sandbox.add_beam(7.1, 5.4, 0.1, 0.1, 0, anchor_density)
    sandbox.add_joint(anchor, None, (7.1, 5.5), type="rigid")
    y_safe = [0.75, 1.75, 2.75, 3.85]
    for y in y_safe:
        b_out = sandbox.add_beam(x_outer, y, width, 0.1, 0, density)
        sandbox.set_damping(b_out, damping, damping)
        sandbox.set_material_properties(b_out, restitution=0.0)
        b_in = sandbox.add_beam(x_inner, y, width, 0.1, 0, density)
        sandbox.set_damping(b_in, damping, damping)
        sandbox.set_material_properties(b_in, restitution=0.0)
    return anchor

def _dual_column_absorber(sandbox, *, right_x: float, density: float, damping: float):
    anchor = sandbox.add_beam(7.12, 5.42, 0.1, 0.1, 0, max(0.12, density * 0.02))
    sandbox.add_joint(anchor, None, (7.12, 5.52), type="rigid")
    sandbox.set_material_properties(anchor, restitution=0.0)
    y_safe = [0.78, 1.72, 2.78, 3.82]
    for y in y_safe:
        br = sandbox.add_beam(right_x, y, 0.1, 0.88, 0, density)
        sandbox.set_damping(br, damping, damping)
        sandbox.set_material_properties(br, restitution=0.0)
        bl = sandbox.add_beam(7.14, y, 0.1, 0.88, 0, density)
        sandbox.set_damping(bl, damping, damping)
        sandbox.set_material_properties(bl, restitution=0.0)
    return anchor

def build_agent_stage_1(sandbox):
    density = 0.1
    rest = 0.0
    damp = 0.1
    anchor = sandbox.add_beam(7.08, 5.42, 0.08, 0.08, 0, density)
    sandbox.set_material_properties(anchor, restitution=rest)
    sandbox.add_joint(anchor, None, (7.08, 5.5), type="rigid")
    spectator_ys = [0.55, 0.62, 1.55, 1.82, 2.55, 2.88, 3.60, 4.05]
    for y in spectator_ys:
        b = sandbox.add_beam(7.06, y, 0.06, 0.06, 0, density)
        sandbox.set_damping(b, damp, damp)
        sandbox.set_material_properties(b, restitution=rest)
    return anchor

def build_agent_stage_2(sandbox):
    return _horizontal_grid_absorber(
        sandbox, density=10.0, damping=220.0, x_inner=7.77, x_outer=9.65,
        width=1.0,
    )

def build_agent_stage_3(sandbox):
    return _horizontal_grid_absorber(
        sandbox, density=8.0, damping=220.0, x_inner=7.77, x_outer=9.98,
        anchor_density=0.1, width=1.2,
    )

def build_agent_stage_4(sandbox):
    return _horizontal_grid_absorber(
        sandbox,
        density=10.0,
        damping=220.0,
        x_inner=7.77,
        x_outer=9.55,
        anchor_density=1.0,
        width=1.0,
    )

def agent_action_stage_1(sandbox, agent_body, step_count):
    pass

def agent_action_stage_2(sandbox, agent_body, step_count):
    pass

def agent_action_stage_3(sandbox, agent_body, step_count):
    pass

def agent_action_stage_4(sandbox, agent_body, step_count):
    pass
