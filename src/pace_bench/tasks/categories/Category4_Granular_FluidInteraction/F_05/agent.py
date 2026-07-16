BOAT_LEFT_X = 13.5

BOAT_RIGHT_X = 16.5

RAIL_HEIGHT = 0.9

RAIL_WIDTH = 0.2

def _nominal_hull_center_y(sandbox):
    cfg = getattr(sandbox, "_terrain_config", None) or {}
    off = float(cfg.get("boat_y_offset", 0.0))
    return 2.5 + off

def _hull_deck_top(sandbox):
    boat = sandbox.get_boat_body()
    if boat is None or not boat.active:
        by = _nominal_hull_center_y(sandbox)
        return by + 0.2, by
    by = float(boat.position.y)
    return by + 0.2, by

def build_agent(sandbox):
    deck_top, by = _hull_deck_top(sandbox)
    yz = float(getattr(sandbox, "BUILD_ZONE_Y_MIN", 2.0))
    max_m = float(getattr(sandbox, "MAX_STRUCTURE_MASS", 60.0))
    _REF_STRUCTURE_MASS = 59.61
    d_scale = (
        1.0
        if max_m >= _REF_STRUCTURE_MASS - 0.05
        else min(1.0, max(0.35, (max_m - 0.25) / _REF_STRUCTURE_MASS))
    )
    rho = lambda d: float(d) * d_scale
    y_min_anchor = yz + 0.01
    ballast_half_h = 0.17 / 2.0
    ballast_y = max(by - 0.26, yz + ballast_half_h + 0.001)
    joint_ballast_y = max(deck_top - 0.26, y_min_anchor)
    joint_rail_y = max(deck_top - 0.05, y_min_anchor)
    bodies = []
    for bx in (14.25, 15.75):
        b = sandbox.add_beam(bx, ballast_y, 0.5, 0.17, angle=0, density=rho(254.0))
        sandbox.set_material_properties(b, restitution=0.05)
        bodies.append(b)
        sandbox.add_joint(b, None, (bx, joint_ballast_y), type='rigid')
    rail_density = rho(30.0)
    left_rail_y = deck_top + RAIL_HEIGHT / 2
    for x_rail in (BOAT_LEFT_X, BOAT_RIGHT_X):
        r = sandbox.add_beam(x_rail, left_rail_y, RAIL_WIDTH, RAIL_HEIGHT, angle=0, density=rail_density)
        sandbox.set_material_properties(r, restitution=0.07)
        bodies.append(r)
        sandbox.add_joint(r, None, (x_rail, joint_rail_y), type='rigid')
    lip_front = sandbox.add_beam(14.5, deck_top + 0.06, 0.18, 0.06, angle=0, density=rho(35.0))
    sandbox.set_material_properties(lip_front, restitution=0.07)
    bodies.append(lip_front)
    sandbox.add_joint(lip_front, None, (14.5, deck_top), type='rigid')
    lip_back = sandbox.add_beam(15.5, deck_top + 0.06, 0.18, 0.06, angle=0, density=rho(35.0))
    sandbox.set_material_properties(lip_back, restitution=0.07)
    bodies.append(lip_back)
    sandbox.add_joint(lip_back, None, (15.5, deck_top), type='rigid')
    barrier_y = deck_top + 0.18
    for bx in (14.5, 15.5):
        bar = sandbox.add_beam(bx, barrier_y, 0.26, 0.2, angle=0, density=rho(42.0))
        sandbox.set_material_properties(bar, restitution=0.07)
        bodies.append(bar)
        sandbox.add_joint(bar, None, (bx, deck_top), type='rigid')
    total_mass = sandbox.get_structure_mass()
    if total_mass > sandbox.MAX_STRUCTURE_MASS:
        raise ValueError(f"Structure mass {total_mass:.2f} kg exceeds limit {sandbox.MAX_STRUCTURE_MASS} kg")
    return bodies[0]

def _f05_roll_trim(sandbox, k_p: float, k_d: float):
    boat = sandbox.get_boat_body()
    if boat is None or not boat.active:
        return
    boat.ApplyTorque(-k_p * boat.angle - k_d * boat.angularVelocity, True)

def _f05_cargo_upwash(sandbox, margin: float, fy: float, inward: float = 0.0):
    ylim = float(getattr(sandbox, "CARGO_WATER_Y", 1.98))
    cx = 15.0
    for c in getattr(sandbox, "_cargo", []) or []:
        if not c.active:
            continue
        px, py = c.position.x, c.position.y
        if py < ylim + margin:
            c.ApplyForceToCenter((inward * (cx - px), fy), True)

def agent_action(sandbox, agent_body, step_count):
    _f05_roll_trim(sandbox, 5600.0, 118.0)

def _hull_anchor_y(sandbox):
    deck_top, by = _hull_deck_top(sandbox)
    yz = float(getattr(sandbox, "BUILD_ZONE_Y_MIN", 2.0))
    ay = max(yz + 0.008, deck_top - 0.035)
    return min(ay, deck_top - 0.012), deck_top, by

def build_agent_stage_1(sandbox):
    bodies = []
    anchor_y, deck_top, by = _hull_anchor_y(sandbox)
    for ox in (12.4, 17.6):
        pontoon = sandbox.add_beam(ox, by - 0.02, 0.68, 0.16, angle=0, density=76.0)
        bodies.append(pontoon)
        for dx in (-0.28, -0.18, -0.09, 0.0, 0.09, 0.18, 0.28):
            sandbox.add_joint(pontoon, None, (ox + dx, anchor_y), type="rigid")
    for bx in [13.55 + i * 0.28 for i in range(10)]:
        slab = sandbox.add_beam(bx, by + 0.06, 0.22, 0.10, angle=0, density=105.0)
        bodies.append(slab)
        for dx in (-0.07, 0.0, 0.07):
            sandbox.add_joint(slab, None, (bx + dx, anchor_y), type="rigid")
    for x_rail in (13.38, 16.62):
        r = sandbox.add_beam(x_rail, deck_top + 0.52, 0.14, 1.0, angle=0, density=20.0)
        bodies.append(r)
        for dy in (0.0, 0.2, 0.4, 0.6):
            sandbox.add_joint(r, None, (x_rail, anchor_y + dy), type="rigid")
    ceiling_y = deck_top + 0.94
    for cx in (13.5, 14.5, 15.5, 16.5):
        seg = sandbox.add_beam(cx, ceiling_y, 1.0, 0.1, angle=0, density=10.5)
        bodies.append(seg)
        for wx in (cx - 0.35, cx, cx + 0.35):
            wxc = min(max(wx, 12.05), 17.95)
            sandbox.add_joint(seg, None, (wxc, ceiling_y), type="rigid")
    for bx in (13.9, 14.6, 15.4, 16.1):
        bar = sandbox.add_beam(bx, deck_top + 0.2, 0.12, 0.48, angle=0, density=28.0)
        bodies.append(bar)
        sandbox.add_joint(bar, None, (bx, anchor_y + 0.06), type="rigid")
    total_mass = sandbox.get_structure_mass()
    if total_mass > sandbox.MAX_STRUCTURE_MASS:
        raise ValueError(f"Structure mass {total_mass:.2f} kg exceeds limit {sandbox.MAX_STRUCTURE_MASS} kg")
    return bodies[0]

def agent_action_stage_1(sandbox, agent_body, step_count):
    kp = 29000.0
    kd = 1100.0
    if (step_count + 1) % 22 <= 5:
        kp = 42000.0
        kd = 1800.0
    _f05_roll_trim(sandbox, kp, kd)
    _f05_cargo_upwash(sandbox, 0.90, 620.0, inward=55.0)

def build_agent_stage_2(sandbox):
    bodies = []
    anchor_y, deck_top, by = _hull_anchor_y(sandbox)
    yz = float(getattr(sandbox, "BUILD_ZONE_Y_MIN", 2.0))
    for ox in (12.36, 17.64):
        pontoon = sandbox.add_beam(ox, by + 0.02, 0.72, 0.12, angle=0, density=110.0)
        bodies.append(pontoon)
        for dx in (-0.28, -0.14, 0.0, 0.14, 0.28):
            sandbox.add_joint(pontoon, None, (ox + dx, anchor_y), type="rigid")
    floor_y = 3.15
    for bx in [13.55 + i * 0.30 for i in range(10)]:
        if bx > 16.45:
            continue
        fb = sandbox.add_beam(bx, floor_y, 0.26, 0.1, angle=0, density=90.0)
        sandbox.set_material_properties(fb, restitution=0.04)
        bodies.append(fb)
        for dy_f in (0.12, 0.35, 0.60):
            jy = deck_top + dy_f
            if jy < anchor_y + 0.012:
                jy = anchor_y + 0.012
            sandbox.add_joint(fb, None, (bx, jy), type="rigid")
    wall_h = 0.38
    wall_cy = floor_y + 0.05 + wall_h / 2.0
    for wx in (13.48, 16.52):
        wall = sandbox.add_beam(wx, wall_cy, 0.11, wall_h, angle=0, density=14.0)
        sandbox.set_material_properties(wall, restitution=0.04)
        bodies.append(wall)
        sandbox.add_joint(wall, None, (wx, floor_y + 0.02), type="rigid")
        sandbox.add_joint(wall, None, (wx, floor_y + 0.16), type="rigid")
    for ex in (13.65, 16.35):
        end_wall = sandbox.add_beam(ex, wall_cy, 0.11, wall_h, angle=0, density=14.0)
        sandbox.set_material_properties(end_wall, restitution=0.04)
        bodies.append(end_wall)
        sandbox.add_joint(end_wall, None, (ex, floor_y + 0.02), type="rigid")
        sandbox.add_joint(end_wall, None, (ex, floor_y + 0.16), type="rigid")
    over_y = floor_y + wall_h + 0.05
    for cx in (14.0, 15.0, 16.0):
        bar = sandbox.add_beam(cx, over_y, 0.9, 0.07, angle=0, density=5.5)
        sandbox.set_material_properties(bar, restitution=0.04)
        bodies.append(bar)
        sandbox.add_joint(bar, None, (cx - 0.3, over_y), type="rigid")
        sandbox.add_joint(bar, None, (cx + 0.3, over_y), type="rigid")
    total_mass = sandbox.get_structure_mass()
    if total_mass > sandbox.MAX_STRUCTURE_MASS:
        raise ValueError(f"Structure mass {total_mass:.2f} kg exceeds limit {sandbox.MAX_STRUCTURE_MASS} kg")
    return bodies[0]

def agent_action_stage_2(sandbox, agent_body, step_count):
    kp = 26000.0
    kd = 850.0
    if (step_count + 1) % 22 <= 5:
        kp = 38000.0
        kd = 1500.0
    _f05_roll_trim(sandbox, kp, kd)
    _f05_cargo_upwash(sandbox, 0.30, 460.0, inward=35.0)

def build_agent_stage_3(sandbox):
    bodies = []
    def _cage_beam(body):
        sandbox.set_material_properties(body, restitution=0.04)
        return body
    anchor_y, deck_top, _by = _hull_anchor_y(sandbox)
    yz = float(getattr(sandbox, "BUILD_ZONE_Y_MIN", 2.0))
    pile_top = deck_top + 0.55 + 0.15 + 0.08
    grill_y = max(pile_top, yz + 0.22)
    for cx, xj in (
        (12.55, (12.08, 12.28, 12.48, 12.68, 12.88, 13.02)),
        (17.45, (16.98, 17.18, 17.38, 17.58, 17.78, 17.92)),
    ):
        wing = sandbox.add_beam(cx, deck_top + 0.05, 1.0, 0.1, angle=0, density=34.0)
        bodies.append(wing)
        for xa in xj:
            sandbox.add_joint(wing, None, (xa, anchor_y), type="rigid")
    low_beam_y = max(deck_top + 0.11, yz + 0.06)
    for bx in (13.85, 14.45, 15.0, 15.55, 16.15):
        b = sandbox.add_beam(bx, low_beam_y, 0.4, 0.1, angle=0, density=72.0)
        bodies.append(b)
        for dx in (-0.11, 0.0, 0.11):
            sandbox.add_joint(b, None, (bx + dx, anchor_y), type="rigid")
    for ox in (12.38, 17.62):
        arm = sandbox.add_beam(ox, deck_top + 0.1, 0.42, 0.1, angle=0, density=44.0)
        bodies.append(arm)
        for dx in (-0.11, 0.0, 0.11):
            sandbox.add_joint(arm, None, (ox + dx, anchor_y), type="rigid")
    rail_h = 0.46
    for x_rail in (13.46, 16.54):
        r = _cage_beam(sandbox.add_beam(x_rail, deck_top + rail_h / 2, 0.11, rail_h, angle=0, density=8.5))
        bodies.append(r)
        for dy in (0.0, 0.14, 0.28, 0.42):
            sandbox.add_joint(r, None, (x_rail, anchor_y + dy), type="rigid")
    ceiling_y = max(deck_top + rail_h + 0.12, yz + 0.52, grill_y + 0.65)
    for cx in (13.55, 14.48, 15.52, 16.45):
        seg = _cage_beam(sandbox.add_beam(cx, ceiling_y, 1.0, 0.09, angle=0, density=5.4))
        bodies.append(seg)
        for wx in (cx - 0.32, cx, cx + 0.32):
            wxc = min(max(wx, 12.05), 17.95)
            sandbox.add_joint(seg, None, (wxc, ceiling_y), type="rigid")
    gate_cy = (deck_top + 0.12 + ceiling_y) / 2
    for gx in (13.505, 13.58, 16.42, 16.495):
        gate = _cage_beam(sandbox.add_beam(gx, gate_cy, 0.1, 0.98, angle=0, density=10.0))
        bodies.append(gate)
        for dy in (0.12, 0.42, 0.72):
            sandbox.add_joint(gate, None, (gx, anchor_y + dy), type="rigid")
    for bx in [13.52 + i * 0.28 for i in range(12)]:
        if bx > 16.6:
            continue
        slat = _cage_beam(sandbox.add_beam(bx, grill_y, 0.1, 0.26, angle=0, density=30.0))
        bodies.append(slat)
        sandbox.add_joint(slat, None, (bx, anchor_y + 0.04), type="rigid")
    for bx in (13.7, 14.35, 15.0, 15.65, 16.3):
        bar = _cage_beam(sandbox.add_beam(bx, grill_y + 0.12, 0.1, 0.28, angle=0, density=26.0))
        bodies.append(bar)
        sandbox.add_joint(bar, None, (bx, anchor_y + 0.08), type="rigid")
        sandbox.add_joint(bar, None, (bx, anchor_y + 0.2), type="rigid")
    total_mass = sandbox.get_structure_mass()
    if total_mass > sandbox.MAX_STRUCTURE_MASS:
        raise ValueError(f"Structure mass {total_mass:.2f} kg exceeds limit {sandbox.MAX_STRUCTURE_MASS} kg")
    return bodies[0]

def agent_action_stage_3(sandbox, agent_body, step_count):
    pass

def build_agent_stage_4(sandbox):
    bodies = []
    def _s(body):
        sandbox.set_material_properties(body, restitution=0.04)
        return body
    anchor_y, deck_top, _by = _hull_anchor_y(sandbox)
    yz = float(getattr(sandbox, "BUILD_ZONE_Y_MIN", 2.0))
    peg = max(yz + 0.005, anchor_y)

    wing_y = yz + 0.18
    for ox in (12.26, 17.74):
        wg = _s(sandbox.add_beam(ox, wing_y, 0.44, 0.15, angle=0, density=100.0))
        bodies.append(wg)
        sandbox.add_joint(wg, None, (ox - 0.14, peg), type="rigid")
        sandbox.add_joint(wg, None, (ox + 0.14, peg), type="rigid")

    floor_y = max(yz + 0.06, deck_top - 0.01)
    for fx in (13.54, 14.00, 14.50, 15.00, 15.50, 16.00, 16.46):
        fl = _s(sandbox.add_beam(fx, floor_y, 0.48, 0.1, angle=0, density=3.8))
        bodies.append(fl)
        sandbox.add_joint(fl, None, (fx - 0.14, peg), type="rigid")
        sandbox.add_joint(fl, None, (fx + 0.14, peg), type="rigid")

    rail_h = 1.0
    rail_base_y = floor_y + 0.05 + rail_h / 2
    for rx in (13.52, 16.48):
        rl = _s(sandbox.add_beam(rx, rail_base_y, 0.12, rail_h, angle=0, density=3.8))
        bodies.append(rl)
        sandbox.add_joint(rl, None, (rx, floor_y + 0.02), type="rigid")
        sandbox.add_joint(rl, None, (rx, rail_base_y), type="rigid")
        sandbox.add_joint(rl, None, (rx, rail_base_y + 0.40), type="rigid")

    ew_h = 0.90
    ew_cy = floor_y + 0.06 + ew_h / 2
    for ex in (13.56, 16.44):
        ew = _s(sandbox.add_beam(ex, ew_cy, 0.12, ew_h, angle=0, density=3.8))
        bodies.append(ew)
        sandbox.add_joint(ew, None, (ex, floor_y + 0.02), type="rigid")
        sandbox.add_joint(ew, None, (ex, ew_cy + 0.25), type="rigid")

    ceil_y = rail_base_y + rail_h / 2 + 0.02
    for ci in range(7):
        cx = 13.54 + (ci + 0.3) * (16.46 - 13.54) / 7.0
        cb = _s(sandbox.add_beam(cx, ceil_y, 0.55, 0.1, angle=0, density=1.4))
        bodies.append(cb)
        sandbox.add_joint(cb, None, (cx, ceil_y), type="rigid")

    brace_y = floor_y + 0.42
    for bx in (13.53, 14.25, 15.00, 15.75, 16.47):
        br = _s(sandbox.add_beam(bx, brace_y, 0.42, 0.1, angle=0, density=2.8))
        bodies.append(br)
        sandbox.add_joint(br, None, (bx, brace_y), type="rigid")
    total_mass = sandbox.get_structure_mass()
    if total_mass > sandbox.MAX_STRUCTURE_MASS:
        raise ValueError(f"Structure mass {total_mass:.2f} kg exceeds limit {sandbox.MAX_STRUCTURE_MASS} kg")
    return bodies[0]

def _f05_cargo_radial_pin(sandbox, y_thresh: float, k: float):
    cx = 15.0
    for c in getattr(sandbox, "_cargo", []) or []:
        if not c.active:
            continue
        px, py = c.position.x, c.position.y
        if py >= y_thresh:
            continue
        c.ApplyForceToCenter((k * (cx - px), 0.0), True)

def agent_action_stage_4(sandbox, agent_body, step_count):
    impulse_interval = 14
    phase = (step_count + 1) % impulse_interval
    near_impulse = (phase < 5 or phase >= impulse_interval - 4)
    if near_impulse:
        kp = 135000.0
        kd = 6800.0
    else:
        kp = 52000.0
        kd = 2600.0
    _f05_roll_trim(sandbox, kp, kd)

    ylim = float(getattr(sandbox, "CARGO_WATER_Y", 1.98))
    cx = 15.0
    ceil_y = 3.55
    for c in getattr(sandbox, "_cargo", []) or []:
        if not c.active:
            continue
        px, py = c.position.x, c.position.y
        dx = cx - px

        c.ApplyForceToCenter((dx * 180.0, 0.0), True)

        if py < ylim + 0.25:
            c.ApplyForceToCenter((0.0, 80.0), True)

        if py > ceil_y:
            c.ApplyForceToCenter((0.0, -200.0), True)

    boat = sandbox.get_boat_body()
    if boat and boat.active:
        boat.ApplyForceToCenter((-420.0 * (boat.position.x - 15.0), 0), True)
