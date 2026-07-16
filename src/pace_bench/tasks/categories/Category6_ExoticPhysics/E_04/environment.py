import math

import Box2D

from Box2D.b2 import world, polygonShape, staticBody, dynamicBody, weldJoint, revoluteJoint

_kinematicBody = getattr(Box2D.b2, "kinematicBody", 1)

class Sandbox:
    BUILD_ZONE_X_MIN = 5.0
    BUILD_ZONE_X_MAX = 15.0
    BUILD_ZONE_Y_MIN = 1.5
    BUILD_ZONE_Y_MAX = 8.0
    MAX_STRUCTURE_MASS = 400.0
    MIN_BEAM_SIZE = 0.1
    MAX_BEAM_SIZE = 4.0
    MIN_BEAMS = 5
    MIN_JOINTS = 6
    SPAN_LEFT_X = 6.0
    SPAN_RIGHT_X = 14.0
    MASS_FREQ_1 = 0.5
    MASS_AMP_1 = 0.2
    MASS_FREQ_2 = 1.0
    MASS_AMP_2 = 0.16
    MASS_PHASE_GRADIENT = 0.4
    BASE_EXCITATION_VERTICAL_AMPLITUDE = 0.06
    BASE_EXCITATION_HORIZONTAL_AMPLITUDE = 0.04
    BASE_EXCITATION_FREQUENCY = 0.45
    JOINT_BREAK_FORCE = 6.0
    JOINT_BREAK_TORQUE = 10.0
    FATIGUE_TAU_SECONDS = 100.0
    WIND_PRESSURE = 0.0
    MAX_STEPS = 12000
    def __init__(self, *, terrain_config=None, physics_config=None):
        terrain_config = terrain_config or {}
        physics_config = physics_config or {}
        self._terrain_config = dict(terrain_config)
        self._physics_config = dict(physics_config)
        gravity = tuple(physics_config.get("gravity", (0, -10)))
        self._linear_damping = float(physics_config.get("linear_damping", 0.0))
        self._angular_damping = float(physics_config.get("angular_damping", 0.0))
        self.MASS_FREQ_1 = physics_config.get("mass_freq_1", self.MASS_FREQ_1)
        self.MASS_AMP_1 = physics_config.get("mass_amp_1", self.MASS_AMP_1)
        self.MASS_FREQ_2 = physics_config.get("mass_freq_2", self.MASS_FREQ_2)
        self.MASS_AMP_2 = physics_config.get("mass_amp_2", self.MASS_AMP_2)
        self.MASS_PHASE_GRADIENT = physics_config.get("mass_phase_gradient", self.MASS_PHASE_GRADIENT)
        self.BASE_EXCITATION_VERTICAL_AMPLITUDE = physics_config.get(
            "base_excitation_vertical_amplitude", self.BASE_EXCITATION_VERTICAL_AMPLITUDE
        )
        self.BASE_EXCITATION_HORIZONTAL_AMPLITUDE = physics_config.get(
            "base_excitation_horizontal_amplitude", self.BASE_EXCITATION_HORIZONTAL_AMPLITUDE
        )
        self.BASE_EXCITATION_FREQUENCY = physics_config.get(
            "base_excitation_frequency", self.BASE_EXCITATION_FREQUENCY
        )
        self.JOINT_BREAK_FORCE = float(physics_config.get("joint_break_force", self.JOINT_BREAK_FORCE))
        self.JOINT_BREAK_TORQUE = float(physics_config.get("joint_break_torque", self.JOINT_BREAK_TORQUE))
        self.FATIGUE_TAU_SECONDS = float(physics_config.get("fatigue_tau_seconds", self.FATIGUE_TAU_SECONDS))
        self.WIND_PRESSURE = float(physics_config.get("wind_pressure", 0.0))
        self._build_zone_x_min = float(terrain_config.get("build_zone_x_min", self.BUILD_ZONE_X_MIN))
        self._build_zone_x_max = float(terrain_config.get("build_zone_x_max", self.BUILD_ZONE_X_MAX))
        self._build_zone_y_min = float(terrain_config.get("build_zone_y_min", self.BUILD_ZONE_Y_MIN))
        self._build_zone_y_max = float(terrain_config.get("build_zone_y_max", self.BUILD_ZONE_Y_MAX))
        self._max_structure_mass = float(terrain_config.get("max_structure_mass", self.MAX_STRUCTURE_MASS))
        self._span_left_x = float(terrain_config.get("span_left_x", self.SPAN_LEFT_X))
        self._span_right_x = float(terrain_config.get("span_right_x", self.SPAN_RIGHT_X))
        self._min_beams = int(terrain_config.get("min_beams", self.MIN_BEAMS))
        self._min_joints = int(terrain_config.get("min_joints", self.MIN_JOINTS))
        self._world = world(gravity=(0, -10), doSleep=True)
        self._world.gravity = gravity
        self._bodies = []
        self._joints = []
        self._terrain_bodies = {}
        self._time = 0.0
        self._joint_peak_forces = {}
        self._joint_peak_torques = {}
        self._joint_types = {}
        self._joint_first_failure_step = {}
        self._joint_anchor_positions = {}
        self._joints_ever_broken = []
        self._beam_areas = {}
        self._beam_widths = {}
        self._beam_heights = {}
        self._peak_body_speed = 0.0
        self.world = self._world
        self.bodies = self._bodies
        self.joints = self._joints
        self._create_terrain(terrain_config)
    def _create_terrain(self, terrain_config: dict):
        ground_length = 40.0
        ground_height = 1.0
        self._ground_y = ground_height
        self._ground_y_base = ground_height / 2.0
        body_def = Box2D.b2BodyDef()
        body_def.type = _kinematicBody
        body_def.position = (ground_length / 2, self._ground_y_base)
        ground = self._world.CreateBody(body_def)
        ground.CreateFixture(Box2D.b2FixtureDef(
            shape=polygonShape(box=(ground_length / 2, ground_height / 2)),
            friction=0.6,
        ))
        self._terrain_bodies["ground"] = ground
    def _mass_factor_for_phase(self, t, phase):
        return (1.0
                + self.MASS_AMP_1 * math.sin(2.0 * math.pi * self.MASS_FREQ_1 * t + phase)
                + self.MASS_AMP_2 * math.sin(2.0 * math.pi * self.MASS_FREQ_2 * t + 2.0 * phase))
    def _effective_joint_force_limit(self, t):
        return self.JOINT_BREAK_FORCE * math.exp(-t / self.FATIGUE_TAU_SECONDS)
    def _effective_joint_torque_limit(self, t):
        return self.JOINT_BREAK_TORQUE * math.exp(-t / self.FATIGUE_TAU_SECONDS)
    def step(self, time_step):
        t = self._time
        for body in self._bodies:
            base = getattr(body, "_base_density", None)
            phase = getattr(body, "_mass_phase", 0.0)
            if base is not None:
                factor = self._mass_factor_for_phase(t, phase)
                for fixture in body.fixtures:
                    fixture.density = base * factor
                body.ResetMassData()
            if self.WIND_PRESSURE != 0.0:
                area = getattr(body, "_area", 0.1)
                force_x = self.WIND_PRESSURE * area
                body.ApplyForceToCenter((force_x, 0.0), True)
            speed = math.sqrt(body.linearVelocity.x**2 + body.linearVelocity.y**2)
            if speed > self._peak_body_speed:
                self._peak_body_speed = speed
        ground = self._terrain_bodies.get("ground")
        if ground is not None:
            omega = 2.0 * math.pi * self.BASE_EXCITATION_FREQUENCY
            vx = self.BASE_EXCITATION_HORIZONTAL_AMPLITUDE * omega * math.cos(omega * t)
            vy = self.BASE_EXCITATION_VERTICAL_AMPLITUDE * omega * math.cos(omega * t)
            ground.linearVelocity = (vx, vy)
        self._time += time_step
        try:
            self._world.Step(time_step, 10, 10)
        except Exception as e:
            print(f"CRASH at step {t}: {e}")
            raise e
        force_limit = self._effective_joint_force_limit(self._time)
        torque_limit = self._effective_joint_torque_limit(self._time)
        joints_to_remove = []
        current_step_index = len(self._bodies) * 1000 + 999999
        for joint in list(self._joints):
            try:
                if hasattr(joint, "GetReactionForce"):
                    force = joint.GetReactionForce(1.0 / 60.0)
                    force_mag = math.sqrt(force.x**2 + force.y**2)
                    self._joint_peak_forces[joint] = max(
                        self._joint_peak_forces.get(joint, 0.0), force_mag
                    )
                    torque_mag = 0.0
                    if hasattr(joint, "GetReactionTorque"):
                        torque_mag = abs(joint.GetReactionTorque(1.0 / 60.0))
                    self._joint_peak_torques[joint] = max(
                        self._joint_peak_torques.get(joint, 0.0), torque_mag
                    )
                    exceeded = (self._joint_peak_forces[joint] > force_limit or
                                self._joint_peak_torques[joint] > torque_limit)
                    if exceeded and self._joint_first_failure_step.get(joint) is None:
                        self._joint_first_failure_step[joint] = int(round(self._time * 60.0))
                    if exceeded:
                        joints_to_remove.append(joint)
            except Exception:
                continue
        for joint in joints_to_remove:
            try:
                joint_type = self._joint_types.get(joint, "unknown")
                anchor = self._joint_anchor_positions.get(joint, (None, None))
                break_step = self._joint_first_failure_step.get(joint, None)
                self._joints_ever_broken.append({
                    "joint_type": joint_type,
                    "anchor_x": anchor[0],
                    "anchor_y": anchor[1],
                    "break_step": break_step,
                    "peak_force_at_break": self._joint_peak_forces.get(joint, None),
                    "peak_torque_at_break": self._joint_peak_torques.get(joint, None),
                })
                self._world.DestroyJoint(joint)
                self._joints.remove(joint)
                self._joint_peak_forces.pop(joint, None)
                self._joint_peak_torques.pop(joint, None)
                self._joint_types.pop(joint, None)
                self._joint_first_failure_step.pop(joint, None)
                self._joint_anchor_positions.pop(joint, None)
            except Exception:
                pass
    def add_beam(self, x, y, width, height, angle=0, density=1.0):
        width = max(self.MIN_BEAM_SIZE, min(width, self.MAX_BEAM_SIZE))
        height = max(self.MIN_BEAM_SIZE, min(height, self.MAX_BEAM_SIZE))
        body = self._world.CreateDynamicBody(
            position=(x, y),
            angle=angle,
            fixtures=Box2D.b2FixtureDef(
                shape=polygonShape(box=(width / 2, height / 2)),
                density=density,
                friction=0.5,
            ),
        )
        body._base_density = density
        body._mass_phase = (x - self._build_zone_x_min) * self.MASS_PHASE_GRADIENT
        body._area = width * height
        body.linearDamping = self._linear_damping
        body.angularDamping = self._angular_damping
        self._bodies.append(body)
        body_id = id(body)
        self._beam_areas[body_id] = width * height
        self._beam_widths[body_id] = width
        self._beam_heights[body_id] = height
        return body
    def add_joint(self, body_a, body_b, anchor_point, type="rigid"):
        if body_a is None:
            raise ValueError("add_joint: body_a cannot be None.")
        anchor_x, anchor_y = anchor_point[0], anchor_point[1]
        if body_b is None:
            body_b = self._terrain_bodies.get("ground")
            if body_b is None:
                raise ValueError("add_joint: Cannot anchor to ground.")
        if type == "rigid":
            joint = self._world.CreateWeldJoint(
                bodyA=body_a, bodyB=body_b,
                anchor=(anchor_x, anchor_y), collideConnected=False,
            )
        elif type == "pivot":
            joint = self._world.CreateRevoluteJoint(
                bodyA=body_a, bodyB=body_b,
                anchor=(anchor_x, anchor_y), collideConnected=False,
            )
        else:
            raise ValueError(f"Unknown joint type: {type}")
        self._joints.append(joint)
        self._joint_peak_forces[joint] = 0.0
        self._joint_peak_torques[joint] = 0.0
        self._joint_types[joint] = type
        self._joint_anchor_positions[joint] = (anchor_x, anchor_y)
        self._joint_first_failure_step[joint] = None
        return joint
    def get_structure_mass(self):
        total = 0.0
        for body in self._bodies:
            total += body.mass
        return total
    def get_max_joint_reaction_force(self):
        if not self._joint_peak_forces:
            return 0.0
        return max(self._joint_peak_forces.values())
    def get_max_joint_reaction_torque(self):
        if not self._joint_peak_torques:
            return 0.0
        return max(self._joint_peak_torques.values())
    def get_effective_joint_force_limit(self):
        return self._effective_joint_force_limit(self._time)
    def get_effective_joint_torque_limit(self):
        return self._effective_joint_torque_limit(self._time)
    def set_material_properties(self, body, restitution=0.2):
        for fixture in body.fixtures:
            fixture.restitution = float(restitution)
    def get_ground_y_top(self):
        return self._ground_y
    def get_build_zone(self):
        return (self._build_zone_x_min, self._build_zone_x_max, self._build_zone_y_min, self._build_zone_y_max)
    def get_span_bounds(self):
        return (self._span_left_x, self._span_right_x)
    def get_structure_mass_limit(self):
        return self._max_structure_mass
    def get_joint_anchor_positions(self):
        return {
            id(joint): list(self._joint_anchor_positions.get(joint, (None, None)))
            for joint in self._joints
        }
    def get_joints_ever_broken(self):
        return list(self._joints_ever_broken)
    def get_per_joint_peaks(self):
        result = {}
        for joint in self._joints:
            jid = id(joint)
            result[jid] = {
                "force": self._joint_peak_forces.get(joint, 0.0),
                "torque": self._joint_peak_torques.get(joint, 0.0),
                "type": self._joint_types.get(joint, "unknown"),
                "anchor_x": self._joint_anchor_positions.get(joint, (None, None))[0],
                "anchor_y": self._joint_anchor_positions.get(joint, (None, None))[1],
            }
        return result
    def get_beam_areas(self):
        return dict(self._beam_areas)
    def get_wind_pressure(self):
        return self.WIND_PRESSURE
    def get_peak_body_speed(self):
        return self._peak_body_speed
    def get_gravity(self):
        return self._physics_config.get("gravity", (0, -10))
    def get_current_fatigue_factor(self):
        return math.exp(-self._time / self.FATIGUE_TAU_SECONDS)
    def get_joints_first_failure_step(self):
        return dict(self._joint_first_failure_step)
    def get_base_excitation_params(self):
        return (
            self.BASE_EXCITATION_HORIZONTAL_AMPLITUDE,
            self.BASE_EXCITATION_VERTICAL_AMPLITUDE,
            self.BASE_EXCITATION_FREQUENCY,
        )
    def get_mass_variation_params(self):
        return (
            self.MASS_FREQ_1,
            self.MASS_AMP_1,
            self.MASS_FREQ_2,
            self.MASS_AMP_2,
            self.MASS_PHASE_GRADIENT,
        )
    def get_min_beams(self):
        return self._min_beams
    def get_min_joints(self):
        return self._min_joints
    def get_terrain_bounds(self):
        return {
            "ground_y": self._ground_y,
            "build_zone": {
                "x": [self._build_zone_x_min, self._build_zone_x_max],
                "y": [self._build_zone_y_min, self._build_zone_y_max],
            },
            "max_structure_mass": self._max_structure_mass,
            "span_left_x": self._span_left_x,
            "span_right_x": self._span_right_x,
            "min_beams": self._min_beams,
            "min_joints": self._min_joints,
        }
