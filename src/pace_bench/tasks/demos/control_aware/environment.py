import Box2D

from Box2D.b2 import (world, polygonShape, staticBody, dynamicBody, prismaticJoint)

import math

class DaVinciSandbox:
    def __init__(self, *, terrain_config=None, physics_config=None):
        terrain_config = terrain_config or {}
        physics_config = physics_config or {}
        self._terrain_config = dict(terrain_config)
        self._physics_config = dict(physics_config)
        gravity = tuple(physics_config.get("gravity", (0, -10)))
        self._default_linear_damping = float(physics_config.get("linear_damping", 0.0))
        self._default_angular_damping = float(physics_config.get("angular_damping", 0.0))
        self._world = world(gravity=gravity, doSleep=True)
        self._bodies = []
        self._joints = []
        self._slider = None
        self.world = self._world
        self.bodies = self._bodies
        self.joints = self._joints
        self._create_track(terrain_config)
    def _create_track(self, terrain_config: dict):
        track_friction = float(terrain_config.get("track_friction", 0.0))
        track_y = 3.0
        track_length = 30.0
        track_width = 0.3
        self.track = self._world.CreateStaticBody(
            position=(track_length/2, track_y),
            fixtures=Box2D.b2FixtureDef(
                shape=polygonShape(box=(track_length/2, track_width/2)),
                friction=float(track_friction),
            ),
        )
    TRACK_Y = 3.0
    TRACK_START_X = 0.0
    TRACK_END_X = 30.0
    SLIDER_MAX_SPEED = 5.0
    SLIDER_MIN_Y = 2.5
    SLIDER_MAX_Y = 3.5
    SPEED_ZONE_1_START = 0.0
    SPEED_ZONE_1_END = 10.0
    SPEED_ZONE_1_LIMIT = 1.5
    SPEED_ZONE_2_START = 10.0
    SPEED_ZONE_2_END = 20.0
    SPEED_ZONE_2_LIMIT = 3.0
    SPEED_ZONE_3_START = 20.0
    SPEED_ZONE_3_END = 30.0
    SPEED_ZONE_3_LIMIT = 2.0
    def add_slider(self, x, y, width, height, density=1.0):
        track_width = 0.3
        slider_y = self.TRACK_Y + track_width/2 + height/2
        body = self._world.CreateDynamicBody(
            position=(x, slider_y),
            fixtures=Box2D.b2FixtureDef(
                shape=polygonShape(box=(width/2, height/2)),
                density=density,
                friction=0.0,
            )
        )
        body.linearDamping = self._default_linear_damping
        body.angularDamping = self._default_angular_damping
        body.fixedRotation = True
        self._bodies.append(body)
        self._slider = body
        return body
    def get_slider_state(self, slider):
        if not slider:
            return 0.0, 0.0
        pos = slider.position
        vel = slider.linearVelocity
        return pos.x, vel.x
    def set_slider_velocity(self, slider, velocity_x):
        if not slider:
            return
        velocity_x = max(0.0, min(self.SLIDER_MAX_SPEED, velocity_x))
        slider._target_velocity_x = velocity_x
        slider.linearVelocity = (velocity_x, 0.0)
    def apply_force_to_slider(self, slider, force_x):
        if not slider:
            return
        max_force = slider.mass * 50.0
        force_x = max(0.0, min(max_force, force_x))
        slider.ApplyForce((force_x, 0), slider.position, True)
    def step(self, time_step):
        if self._slider:
            if hasattr(self._slider, '_target_velocity_x'):
                target_vel_x = self._slider._target_velocity_x
                self._slider.linearVelocity = (target_vel_x, 0.0)
            else:
                vel = self._slider.linearVelocity
                self._slider.linearVelocity = (vel.x, 0.0)
        self._world.Step(time_step, 10, 10)
        if self._slider:
            pos = self._slider.position
            track_width = 0.3
            slider_height = 0.3
            target_y = self.TRACK_Y + track_width/2 + slider_height/2
            if abs(pos.y - target_y) > 0.01:
                self._slider.position = (pos.x, target_y)
            if hasattr(self._slider, '_target_velocity_x'):
                target_vel_x = self._slider._target_velocity_x
                self._slider.linearVelocity = (target_vel_x, 0.0)
            else:
                vel = self._slider.linearVelocity
                self._slider.linearVelocity = (vel.x, 0.0)
    def get_terrain_bounds(self):
        return {
            "track_start": self.TRACK_START_X,
            "track_end": self.TRACK_END_X,
            "track_y": self.TRACK_Y,
        }
    def get_speed_zone_limits(self):
        return {
            "zone_1": {
                "start": self.SPEED_ZONE_1_START,
                "end": self.SPEED_ZONE_1_END,
                "limit": self.SPEED_ZONE_1_LIMIT
            },
            "zone_2": {
                "start": self.SPEED_ZONE_2_START,
                "end": self.SPEED_ZONE_2_END,
                "limit": self.SPEED_ZONE_2_LIMIT
            },
            "zone_3": {
                "start": self.SPEED_ZONE_3_START,
                "end": self.SPEED_ZONE_3_END,
                "limit": self.SPEED_ZONE_3_LIMIT
            }
        }
