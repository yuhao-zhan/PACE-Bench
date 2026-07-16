import math

import Box2D

from Box2D import b2World, b2PolygonShape, b2CircleShape, b2FixtureDef, b2BodyDef, b2_dynamicBody, b2_staticBody

FPS = 60

TIME_STEP = 1.0 / FPS

VEL_ITERS, POS_ITERS = 10, 10

FORCE_HISTORY_CAP = 100

STATE_HISTORY_CAP = 300

MAX_STEPS = 250000

AGENT_MASS = 5.0

WHISKER_RANGE = 3.0

HOLD_STEPS = 5

LINEAR_DAMPING = 1.0

RESTITUTION = 0.1

MAZE_WALLS = [
    (0.0, 0.0, 20.0, 0.5),
    (0.0, 2.5, 20.0, 0.5),
    (0.0, 0.0, 0.5, 3.0),
    (20.0, 0.0, 0.5, 3.0),
    (5.0, 0.0, 0.2, 1.0),
    (9.0, 1.8, 0.2, 1.2),
    (14.0, 1.8, 0.2, 1.2),

]

WIND_OSCILLATION_AMP = 5.0

WIND_OSCILLATION_OMEGA = 0.05

SHEAR_WIND_REFERENCE_Y = 1.5

BACKWARD_FX_THRESHOLD = -34.0

BACKWARD_SPEED_MAX = 100.0

BACKWARD_STEPS_REQUIRED = HOLD_STEPS

STRUCTURAL_IMPULSE_SCALE_K = 25.0

ACTIVATION_X_MIN = 5.0

ACTIVATION_X_MAX = 10.0

SLIP_FRICTION = 0.5

ONEWAY_X = 10.2

ONEWAY_FORCE_RIGHT = 50.0

LOCK_GATE_X_MIN = 12.0

LOCK_GATE_X_MAX = 16.0

LOCK_GATE_FX = -1200.0

EXIT_X_MIN = 15.0

EXIT_Y_MIN = 0.5

EXIT_Y_MAX = 2.5

class Sandbox:
    def __init__(self, terrain_config: dict = None, physics_config: dict = None):
        if physics_config is None: physics_config = {}
        if terrain_config is None: terrain_config = {}
        self.physics_config = physics_config
        self.terrain_config = terrain_config
        g_val = physics_config.get("gravity", -9.8)
        if isinstance(g_val, (list, tuple)):
            g_y = float(g_val[1])
        else:
            g_y = float(g_val)
        self._world = b2World(gravity=(0, g_y))
        self._terrain_bodies = {}
        self._current_step = 0
        self._current_force_back = float(physics_config.get("current_force_back", 0.0))
        self._shear_wind_gradient = float(physics_config.get("shear_wind_gradient", 0.0))
        self._whisker_delay_steps = int(terrain_config.get("whisker_delay_steps", 0))
        self._position_delay_steps = int(terrain_config.get("position_delay_steps", 0))
        self._whisker_blind_front_x_lo = float(terrain_config.get("whisker_blind_front_x_lo", -999.0))
        self._whisker_blind_front_x_hi = float(terrain_config.get("whisker_blind_front_x_hi", -999.0))
        self._control_reversal_x_min = float(physics_config.get("control_reversal_x_min", -999.0))
        self._control_reversal_x_max = float(physics_config.get("control_reversal_x_max", -999.0))
        self._fluid_drag_x_min = float(physics_config.get("fluid_drag_x_min", -999.0))
        self._fluid_drag_x_max = float(physics_config.get("fluid_drag_x_max", -999.0))
        self._fluid_drag_coeff = float(physics_config.get("fluid_drag_coeff", 0.0))
        self._magnetic_floor_y_max = float(physics_config.get("magnetic_floor_y_max", -999.0))
        self._magnetic_floor_force = float(physics_config.get("magnetic_floor_force", 0.0))
        self._control_lag_steps = int(physics_config.get("control_lag_steps", 0))
        self._turbulence_intensity = float(physics_config.get("turbulence_intensity", 0.0))
        self._slip_friction = float(physics_config.get("slip_friction", SLIP_FRICTION))
        self._oneway_x = float(terrain_config.get("oneway_x", ONEWAY_X))
        self._oneway_force_right = float(physics_config.get("oneway_force_right", ONEWAY_FORCE_RIGHT))
        self._lock_gate_fx = float(physics_config.get("lock_gate_fx", LOCK_GATE_FX))
        self._lock_gate_x_min = float(physics_config.get("lock_gate_x_min", LOCK_GATE_X_MIN))
        self._lock_gate_x_max = float(physics_config.get("lock_gate_x_max", LOCK_GATE_X_MAX))
        self._activation_x_min = float(physics_config.get("activation_x_min", ACTIVATION_X_MIN))
        self._activation_x_max = float(physics_config.get("activation_x_max", ACTIVATION_X_MAX))
        self._wind_oscillation_amp = float(physics_config.get("wind_oscillation_amp", WIND_OSCILLATION_AMP))
        self._wind_oscillation_omega = float(physics_config.get("wind_oscillation_omega", WIND_OSCILLATION_OMEGA))
        self._shear_wind_reference_y = float(
            physics_config.get("shear_wind_reference_y", SHEAR_WIND_REFERENCE_Y)
        )
        self._structural_impulse_scale_k = float(
            physics_config.get(
                "structural_impulse_scale_k",
                physics_config.get("collision_velocity_limit", STRUCTURAL_IMPULSE_SCALE_K),
            )
        )
        self._backward_fx_threshold = float(
            physics_config.get("backward_fx_threshold", BACKWARD_FX_THRESHOLD)
        )
        self._backward_speed_max = float(
            physics_config.get("backward_speed_max", BACKWARD_SPEED_MAX)
        )
        self._backward_steps_required = int(
            physics_config.get("backward_steps_required", BACKWARD_STEPS_REQUIRED)
        )
        self._force_history = []
        self._behavioral_unlock = False
        self._backward_steps = 0
        self._is_destroyed = False
        self._destruction_reason = None
        self._create_maze(terrain_config)
        self._create_agent(terrain_config)
        p_init = (self._terrain_bodies["agent"].position.x, self._terrain_bodies["agent"].position.y)
        self._position_history = [p_init]
        self._whisker_readings_history = [tuple(self.get_whisker_readings())]
        self._force_x = 0.0
        self._force_y = 0.0
        self._last_turbulence_x = 0.0
        self._last_turbulence_y = 0.0
        self.MAX_STEPS = int(physics_config.get("max_steps", MAX_STEPS))
    def _create_maze(self, terrain_config: dict):
        walls = list(MAZE_WALLS)
        overrides = terrain_config.get("wall_overrides", {})
        for idx_str, val in overrides.items():
            walls[int(idx_str)] = val
        for i, (x, y, w, h) in enumerate(walls):
            body = self._world.CreateStaticBody(
                position=(x + w/2, y + h/2),
                shapes=b2PolygonShape(box=(w/2, h/2)),
            )
            body.fixtures[0].friction = self._slip_friction
            self._terrain_bodies[f"wall_{i}"] = body
    def _create_agent(self, terrain_config: dict):
        self._agent_radius = 0.2
        body_def = b2BodyDef(
            type=b2_dynamicBody,
            position=(2.0, 1.5),
            fixedRotation=True,
            linearDamping=LINEAR_DAMPING,
        )
        agent = self._world.CreateBody(body_def)
        shape = b2CircleShape(radius=self._agent_radius)
        fixture_def = b2FixtureDef(
            shape=shape,
            density=AGENT_MASS / (math.pi * self._agent_radius**2),
            friction=self._slip_friction,
            restitution=RESTITUTION,
        )
        agent.CreateFixture(fixture_def)
        self._terrain_bodies["agent"] = agent
        class MyContactListener(Box2D.b2ContactListener):
            def __init__(self, sandbox):
                super().__init__()
                self.sandbox = sandbox
            def PostSolve(self, contact, impulse):
                for i in range(contact.manifold.pointCount):
                    if impulse.normalImpulses[i] > self.sandbox._structural_impulse_scale_k * AGENT_MASS:
                        self.sandbox._is_destroyed = True
                        self.sandbox._destruction_reason = f"Structural Failure: Collision impulse {impulse.normalImpulses[i]:.1f} exceeded limit."
        self._world.contactListener = MyContactListener(self)
    def _raycast(self, p1, p2, ignore_body):
        class RayCastCallback(Box2D.b2RayCastCallback):
            def __init__(self, ignore):
                super().__init__()
                self.ignore = ignore
                self.hit_fraction = 1.0
            def ReportFixture(self, fixture, point, normal, fraction):
                if fixture.body == self.ignore:
                    return -1
                self.hit_fraction = fraction
                return 0
        callback = RayCastCallback(ignore_body)
        self._world.RayCast(callback, p1, p2)
        return callback.hit_fraction
    def get_agent_position(self):
        agent = self._terrain_bodies.get("agent")
        if agent is None: return (0.0, 0.0)
        p = (agent.position.x, agent.position.y)
        delay = max(0, self._position_delay_steps)
        if delay > 0:
            if len(self._position_history) > delay:
                return self._position_history[-(delay + 1)]
            return self._position_history[0]
        return p
    def get_agent_velocity(self):
        agent = self._terrain_bodies.get("agent")
        if agent is None: return (0.0, 0.0)
        return (agent.linearVelocity.x, agent.linearVelocity.y)
    def get_whisker_readings(self):
        agent = self._terrain_bodies.get("agent")
        if agent is None: return [WHISKER_RANGE] * 3
        x, y = agent.position.x, agent.position.y
        if self._whisker_blind_front_x_lo <= x <= self._whisker_blind_front_x_hi:
            return [WHISKER_RANGE] * 3
        delay = max(0, self._whisker_delay_steps)
        if delay > 0:
            if len(self._whisker_readings_history) > delay:
                return list(self._whisker_readings_history[-(delay + 1)])
            return list(self._whisker_readings_history[0])
        r = WHISKER_RANGE
        directions = [(1, 0), (0, 1), (0, -1)]
        out = []
        for dx, dy in directions:
            p2 = (x + dx * r, y + dy * r)
            frac = self._raycast((x, y), p2, agent)
            out.append(frac * r)
        return out
    def apply_agent_force(self, force_x, force_y):
        self._force_history.append((float(force_x), float(force_y)))
        if len(self._force_history) > FORCE_HISTORY_CAP:
            self._force_history.pop(0)
        delay = max(0, self._control_lag_steps)
        if delay > 0 and len(self._force_history) > delay:
            fx, fy = self._force_history[-(delay + 1)]
        else:
            fx, fy = float(force_x), float(force_y)
        self._force_x, self._force_y = fx, fy
    def step(self, time_step):
        import random
        if self._is_destroyed:
            self._world.Step(time_step, VEL_ITERS, POS_ITERS)
            self._current_step += 1
            return
        agent = self._terrain_bodies.get("agent")
        if agent is not None:
            x, y = agent.position.x, agent.position.y
            px, py = self.get_agent_position()
            vx, vy = agent.linearVelocity.x, agent.linearVelocity.y
            speed = math.sqrt(vx * vx + vy * vy)
            self._position_history.append((x, y))
            if len(self._position_history) > STATE_HISTORY_CAP:
                self._position_history.pop(0)
            r = WHISKER_RANGE
            directions = [(1, 0), (0, 1), (0, -1)]
            true_whiskers = []
            for dx, dy in directions:
                p2 = (x + dx * r, y + dy * r)
                frac = self._raycast((x, y), p2, agent)
                true_whiskers.append(frac * r)
            self._whisker_readings_history.append(tuple(true_whiskers))
            if len(self._whisker_readings_history) > STATE_HISTORY_CAP:
                self._whisker_readings_history.pop(0)
            if (
                self._activation_x_min <= px <= self._activation_x_max
                and self._force_x < self._backward_fx_threshold
                and speed < self._backward_speed_max
            ):
                self._backward_steps += 1
                if self._backward_steps >= self._backward_steps_required:
                    self._behavioral_unlock = True
            else:
                self._backward_steps = 0
            force_x_applied = self._force_x
            force_y_applied = self._force_y
            if self._control_reversal_x_min <= px <= self._control_reversal_x_max:
                force_x_applied *= -1.0
            agent.ApplyForceToCenter((force_x_applied, force_y_applied), True)
            if self._fluid_drag_x_min <= px <= self._fluid_drag_x_max:
                drag_x = -self._fluid_drag_coeff * vx * abs(vx)
                drag_y = -self._fluid_drag_coeff * vy * abs(vy)
                agent.ApplyForceToCenter((drag_x, drag_y), True)
            if y < self._magnetic_floor_y_max:
                agent.ApplyForceToCenter((0.0, self._magnetic_floor_force), True)
            if self._turbulence_intensity > 0:
                tx = (random.random() - 0.5) * self._turbulence_intensity
                ty_turb = (random.random() - 0.5) * self._turbulence_intensity
                agent.ApplyForceToCenter((tx, ty_turb), True)
                self._last_turbulence_x = tx
                self._last_turbulence_y = ty_turb
            else:
                self._last_turbulence_x = 0.0
                self._last_turbulence_y = 0.0
            osc = self._wind_oscillation_amp * math.sin(self._wind_oscillation_omega * self._current_step)
            wind_x = (
                -self._current_force_back
                + self._shear_wind_gradient * (y - self._shear_wind_reference_y)
                + osc
            )
            agent.ApplyForceToCenter((wind_x, 0), True)
            if px > self._oneway_x:
                agent.ApplyForceToCenter((self._oneway_force_right, 0), True)
            if not self._behavioral_unlock and self._lock_gate_x_min <= px <= self._lock_gate_x_max:
                agent.ApplyForceToCenter((self._lock_gate_fx, 0.0), True)
        self._world.Step(time_step, VEL_ITERS, POS_ITERS)
        self._current_step += 1
    def get_metrics(self):
        agent = self._terrain_bodies.get("agent")
        if agent is None:
            return {}
        px, py = self.get_agent_position()
        return {"x": px, "y": py, "unlocked": self._behavioral_unlock, "step": self._current_step}
    def get_agent_body(self): return self._terrain_bodies.get("agent")
    def get_terrain_bounds(self):
        return {
            "x_min": 0.0,
            "x_max": 20.0,
            "y_min": 0.0,
            "y_max": 3.0,
            "exit_x_min": EXIT_X_MIN,
            "exit_y_min": EXIT_Y_MIN,
            "exit_y_max": EXIT_Y_MAX,
        }
    def get_agent_components(self):
        return {
            "agent": self.get_agent_body(),
            "exit_x_min": EXIT_X_MIN,
            "exit_y_min": EXIT_Y_MIN,
            "exit_y_max": EXIT_Y_MAX,
        }
    def has_reached_exit(self):
        if self._is_destroyed:
            return False
        b = self.get_terrain_bounds()
        ex, ey0, ey1 = b["exit_x_min"], b["exit_y_min"], b["exit_y_max"]
        x, y = self.get_agent_position()
        return x >= ex and ey0 <= y <= ey1
    def get_whisker_max_range(self): return WHISKER_RANGE
    def is_destroyed(self): return self._is_destroyed
    def get_force_ledger(self):
        import math as _m
        agent = self._terrain_bodies.get("agent")
        if agent is None:
            return {}
        x, y = agent.position.x, agent.position.y
        px, py = self.get_agent_position()
        vx, vy = agent.linearVelocity.x, agent.linearVelocity.y
        ledger = {
            "agent_physical_x": x,
            "agent_physical_y": y,
            "agent_reported_x": px,
            "agent_reported_y": py,
            "agent_velocity_x": vx,
            "agent_velocity_y": vy,
            "channels": {},
        }
        cmd_fx = float(self._force_x)
        cmd_fy = float(self._force_y)
        ledger["commanded_force"] = {"fx": cmd_fx, "fy": cmd_fy}
        ch = ledger["channels"]
        ch["commanded"] = {
            "fx": cmd_fx,
            "fy": cmd_fy,
            "description": "Effective commanded force after control lag",
        }
        reversal_active = self._control_reversal_x_min <= px <= self._control_reversal_x_max
        effective_fx_cmd = -cmd_fx if reversal_active else cmd_fx
        ch["control_reversal"] = {
            "active": reversal_active,
            "zone_x": [self._control_reversal_x_min, self._control_reversal_x_max],
            "description": "Control reversal flips sign of commanded Fx" if reversal_active else "Control reversal inactive",
            "effective_commanded_fx_after_reversal": effective_fx_cmd,
        }
        osc = self._wind_oscillation_amp * _m.sin(self._wind_oscillation_omega * self._current_step)
        wind_x = (-self._current_force_back
                  + self._shear_wind_gradient * (y - self._shear_wind_reference_y)
                  + osc)
        ch["wind"] = {
            "fx_total": wind_x,
            "constant_back": -self._current_force_back,
            "shear_component": self._shear_wind_gradient * (y - self._shear_wind_reference_y),
            "oscillation_component": osc,
            "oscillation_amplitude": self._wind_oscillation_amp,
            "oscillation_omega": self._wind_oscillation_omega,
            "shear_gradient": self._shear_wind_gradient,
            "shear_reference_y": self._shear_wind_reference_y,
            "description": "Environmental horizontal wind forcing",
        }
        drag_active = self._fluid_drag_x_min <= px <= self._fluid_drag_x_max
        drag_x = -self._fluid_drag_coeff * vx * abs(vx) if drag_active else 0.0
        drag_y = -self._fluid_drag_coeff * vy * abs(vy) if drag_active else 0.0
        ch["fluid_drag"] = {
            "active": drag_active,
            "zone_x": [self._fluid_drag_x_min, self._fluid_drag_x_max],
            "coefficient": self._fluid_drag_coeff,
            "drag_fx": drag_x,
            "drag_fy": drag_y,
            "description": "Quadratic fluid drag: F = -c * v * |v|" if drag_active else "Fluid drag inactive",
        }
        mag_active = y < self._magnetic_floor_y_max
        mag_fy = self._magnetic_floor_force if mag_active else 0.0
        ch["magnetic_floor"] = {
            "active": mag_active,
            "y_threshold": self._magnetic_floor_y_max,
            "force_fy": mag_fy,
            "description": f"Magnetic floor: {mag_fy:.1f} N downward bias when y < {self._magnetic_floor_y_max:.1f} m" if mag_active else "Magnetic floor inactive",
        }
        turb_active = self._turbulence_intensity > 0.0
        ch["turbulence"] = {
            "active": turb_active,
            "intensity": self._turbulence_intensity,
            "last_fx": self._last_turbulence_x,
            "last_fy": self._last_turbulence_y,
            "description": f"Random turbulence: force ∈ [{-0.5 * self._turbulence_intensity:.1f}, {0.5 * self._turbulence_intensity:.1f}] N per axis" if turb_active else "Turbulence inactive",
        }
        oneway_active = px > self._oneway_x
        ch["oneway_assist"] = {
            "active": oneway_active,
            "threshold_x": self._oneway_x,
            "force_fx": self._oneway_force_right if oneway_active else 0.0,
            "description": f"Oneway rightward assist: +{self._oneway_force_right:.1f} N when reported x > {self._oneway_x:.1f} m" if oneway_active else "Oneway assist inactive (reported x not past threshold)",
        }
        lock_active = (not self._behavioral_unlock) and self._lock_gate_x_min <= px <= self._lock_gate_x_max
        ch["lock_gate"] = {
            "active": lock_active,
            "zone_x": [self._lock_gate_x_min, self._lock_gate_x_max],
            "force_fx": self._lock_gate_fx if lock_active else 0.0,
            "description": f"Lock gate repulsion: {self._lock_gate_fx:.1f} N in -x" if lock_active else "Lock gate inactive (unlocked or outside zone)",
        }
        net_non_cmd_fx = (
            wind_x + drag_x + (self._oneway_force_right if oneway_active else 0.0)
            + (self._lock_gate_fx if lock_active else 0.0)
            + self._last_turbulence_x
        )
        net_non_cmd_fy = (
            drag_y + mag_fy + self._last_turbulence_y
        )
        net_applied_fx = effective_fx_cmd + net_non_cmd_fx
        net_applied_fy = cmd_fy + net_non_cmd_fy
        ledger["net_forces"] = {
            "commanded_effective_fx": effective_fx_cmd,
            "commanded_effective_fy": cmd_fy,
            "environmental_fx": net_non_cmd_fx,
            "environmental_fy": net_non_cmd_fy,
            "net_total_fx": net_applied_fx,
            "net_total_fy": net_applied_fy,
        }
        if self._is_destroyed:
            ledger["agent_destroyed"] = True
            ledger["destruction_reason"] = self._destruction_reason
        return ledger
    def get_unlock_condition_status(self):
        agent = self._terrain_bodies.get("agent")
        if agent is None:
            return {"error": "No agent"}
        x, y = agent.position.x, agent.position.y
        px, py = self.get_agent_position()
        vx, vy = agent.linearVelocity.x, agent.linearVelocity.y
        speed = (vx * vx + vy * vy) ** 0.5
        x_in_act = self._activation_x_min <= px <= self._activation_x_max
        x_margin = 0.0
        if px < self._activation_x_min:
            x_margin = px - self._activation_x_min
        elif px > self._activation_x_max:
            x_margin = px - self._activation_x_max
        fx_ok = self._force_x < self._backward_fx_threshold
        fx_margin = self._force_x - self._backward_fx_threshold
        speed_ok = speed < self._backward_speed_max
        speed_margin = speed - self._backward_speed_max
        all_ok = x_in_act and fx_ok and speed_ok
        return {
            "unlocked": self._behavioral_unlock,
            "consecutive_count": self._backward_steps,
            "required_consecutive": self._backward_steps_required,
            "conditions": [
                {
                    "name": "reported_x_in_activation_zone",
                    "value": px,
                    "zone": [self._activation_x_min, self._activation_x_max],
                    "pass": x_in_act,
                    "margin": x_margin,
                },
                {
                    "name": "commanded_fx_below_threshold",
                    "value": self._force_x,
                    "limit": self._backward_fx_threshold,
                    "pass": fx_ok,
                    "margin": fx_margin,
                },
                {
                    "name": "physical_speed_below_max",
                    "value": speed,
                    "limit": self._backward_speed_max,
                    "pass": speed_ok,
                    "margin": speed_margin,
                },
            ],
            "all_conditions_met": all_ok,
        }
    def get_whisker_health(self):
        agent = self._terrain_bodies.get("agent")
        if agent is None:
            return {"error": "No agent"}
        x, y = agent.position.x, agent.position.y
        px, py = self.get_agent_position()
        in_blind_zone = self._whisker_blind_front_x_lo <= x <= self._whisker_blind_front_x_hi
        blind_zone_active = self._whisker_blind_front_x_lo > -500.0 and self._whisker_blind_front_x_hi > -500.0
        has_delay = self._whisker_delay_steps > 0
        has_pos_delay = self._position_delay_steps > 0
        return {
            "physical_x": x,
            "physical_y": y,
            "reported_x": px,
            "reported_y": py,
            "blind_zone_active": blind_zone_active,
            "blind_zone_x_range": [self._whisker_blind_front_x_lo, self._whisker_blind_front_x_hi] if blind_zone_active else None,
            "agent_in_blind_zone": in_blind_zone,
            "whisker_delay_steps": self._whisker_delay_steps,
            "position_delay_steps": self._position_delay_steps,
            "status_front": "BLIND (all whiskers return max range regardless of obstacles)" if in_blind_zone else "NOMINAL",
            "status_up": "BLIND" if in_blind_zone else "NOMINAL",
            "status_down": "BLIND" if in_blind_zone else "NOMINAL",
            "description": (
                f"Agent physical x={x:.2f} m in whisker blind zone [{self._whisker_blind_front_x_lo:.1f}, {self._whisker_blind_front_x_hi:.1f}] m. "
                f"All whisker readings show max range ({WHISKER_RANGE:.1f} m) regardless of actual obstacles. "
                f"Use last known position and internal model for navigation."
            ) if in_blind_zone else "Whisker sensors nominal.",
        }
    def get_wall_clearance_map(self):
        import math as _m
        agent = self._terrain_bodies.get("agent")
        if agent is None:
            return {"error": "No agent"}
        x, y = agent.position.x, agent.position.y
        walls = []
        for idx in [4, 5, 6]:
            body = self._terrain_bodies.get(f"wall_{idx}")
            if body is None:
                continue
            wx = float(body.position.x)
            wy = float(body.position.y)
            for fixture in body.fixtures:
                shape = fixture.shape
                if hasattr(shape, "vertices"):
                    verts = shape.vertices
                    xs = [v[0] + wx for v in verts]
                    ys = [v[1] + wy for v in verts]
                    w_half_w = (max(xs) - min(xs)) / 2.0
                    w_half_h = (max(ys) - min(ys)) / 2.0
                elif hasattr(shape, "m_centroid"):
                    w_half_w = float(getattr(shape, "m_vertices", [(0,0)])) if hasattr(shape, "m_vertices") else 0.0
                    continue
                else:
                    continue
                wall_x_min = wx - w_half_w
                wall_x_max = wx + w_half_w
                wall_y_min = wy - w_half_h
                wall_y_max = wy + w_half_h
                break
            else:
                continue
            y_range = [wall_y_min, wall_y_max]
            x_range = [wall_x_min, wall_x_max]
            arena_y_max = 3.0
            arena_y_min = 0.0
            gap_above_y = [wall_y_max, arena_y_max]
            gap_above_exists = gap_above_y[1] > gap_above_y[0]
            gap_above_size = gap_above_y[1] - gap_above_y[0] if gap_above_exists else 0.0
            gap_below_y = [arena_y_min, wall_y_min]
            gap_below_exists = gap_below_y[1] > gap_below_y[0]
            gap_below_size = gap_below_y[1] - gap_below_y[0] if gap_below_exists else 0.0
            agent_behind_wall = x < wall_x_min
            agent_past_wall = x > wall_x_max
            agent_at_wall_x = wall_x_min <= x <= wall_x_max
            agent_above_wall = y > wall_y_max
            agent_below_wall = y < wall_y_min
            clearance_above = wall_y_max - y if y < wall_y_max else 0.0
            clearance_below = y - wall_y_min if y > wall_y_min else 0.0
            dist_to_wall_x = wall_x_min - x if x < wall_x_min else 0.0
            walls.append({
                "wall_index": idx,
                "position": {"x_min": wall_x_min, "x_max": wall_x_max, "y_min": wall_y_min, "y_max": wall_y_max},
                "dimensions": {"width": wall_x_max - wall_x_min, "height": wall_y_max - wall_y_min},
                "agent_relative": {
                    "behind_wall": agent_behind_wall,
                    "at_wall_x": agent_at_wall_x,
                    "past_wall": agent_past_wall,
                    "above_wall": agent_above_wall,
                    "below_wall": agent_below_wall,
                    "distance_to_wall_x": dist_to_wall_x,
                },
                "gaps": {
                    "above": {"exists": gap_above_exists, "y_range": gap_above_y, "size_m": gap_above_size},
                    "below": {"exists": gap_below_exists, "y_range": gap_below_y, "size_m": gap_below_size},
                },
                "clearance_needed_m": {
                    "to_pass_above": clearance_above,
                    "to_pass_below": clearance_below,
                },
            })
        return {
            "agent_y": y,
            "arena_limits": {"y_min": 0.0, "y_max": 3.0},
            "walls": walls,
        }
    def get_control_lag_info(self):
        return {
            "control_lag_steps": self._control_lag_steps,
            "command_history_length": len(self._force_history),
            "command_history_cap": FORCE_HISTORY_CAP,
            "current_effective_force": (float(self._force_x), float(self._force_y)),
            "description": (
                f"Control lag: {self._control_lag_steps} step(s). "
                f"Commanded force at step T takes effect at step T+{self._control_lag_steps}. "
                f"Current effective force ({self._force_x:.2f}, {self._force_y:.2f}) N was commanded "
                f"{self._control_lag_steps} step(s) ago."
            ) if self._control_lag_steps > 0 else (
            ),
        }
    def get_wind_params(self):
        return {
            "current_force_back": self._current_force_back,
            "shear_wind_gradient": self._shear_wind_gradient,
            "shear_reference_y": self._shear_wind_reference_y,
            "oscillation_amplitude": self._wind_oscillation_amp,
            "oscillation_omega": self._wind_oscillation_omega,
            "current_step": self._current_step,
        }
    def get_destruction_reason(self): return self._destruction_reason
    @property
    def world(self): return self._world
