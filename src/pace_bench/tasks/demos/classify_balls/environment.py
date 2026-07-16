import Box2D

from Box2D.b2 import (world, polygonShape, circleShape, staticBody, dynamicBody,
                      revoluteJoint, prismaticJoint, weldJoint)

import math

import random

class BallClassificationSandbox:
    def __init__(self, terrain_config=None, physics_config=None):
        self.world = world(gravity=(0, -9.8), doSleep=True)
        self.bodies = []
        self.joints = []
        self.sensors = []
        self.actuators = []
        self.logic_gates = []
        self.wires = []
        self.balls = []
        CONVEYOR_START_X = -5.0
        CONVEYOR_END_X = 0.0
        CONVEYOR_Y = 5.0
        CONVEYOR_LENGTH = 5.0
        CONVEYOR_WIDTH = 0.3
        self.conveyor = self.world.CreateStaticBody(
            position=((CONVEYOR_START_X + CONVEYOR_END_X) / 2, CONVEYOR_Y),
            fixtures=Box2D.b2FixtureDef(
                shape=polygonShape(box=(CONVEYOR_LENGTH/2, CONVEYOR_WIDTH/2)),
                friction=0.8,
                restitution=0.0
            )
        )
        self.conveyor_speed = 2.0
        self.conveyor_start_x = CONVEYOR_START_X
        self.conveyor_end_x = CONVEYOR_END_X
        self.conveyor_y = CONVEYOR_Y
        self.spawn_point = (-4.0, 6.0)
        self.build_zone = {
            'min_x': 0.5,
            'max_x': 5.0,
            'min_y': 0.0,
            'max_y': 5.0
        }
        self.blue_basket = {
            'x': 0.5,
            'y': 0.0,
            'width': 3.5,
            'height': 4.0,
            'color': 'blue'
        }
        self.red_basket = {
            'x': 4.0,
            'y': 0.0,
            'width': 3.0,
            'height': 4.0,
            'color': 'red'
        }
        basket_wall_height = 0.2
        self.world.CreateStaticBody(
            position=(self.blue_basket['x'] - self.blue_basket['width']/2,
                     self.blue_basket['y'] + basket_wall_height/2),
            shapes=polygonShape(box=(0.05, basket_wall_height/2))
        )
        self.world.CreateStaticBody(
            position=(self.blue_basket['x'] + self.blue_basket['width']/2,
                     self.blue_basket['y'] + basket_wall_height/2),
            shapes=polygonShape(box=(0.05, basket_wall_height/2))
        )
        self.world.CreateStaticBody(
            position=(self.red_basket['x'] - self.red_basket['width']/2,
                     self.red_basket['y'] + basket_wall_height/2),
            shapes=polygonShape(box=(0.05, basket_wall_height/2))
        )
        self.world.CreateStaticBody(
            position=(self.red_basket['x'] + self.red_basket['width']/2,
                     self.red_basket['y'] + basket_wall_height/2),
            shapes=polygonShape(box=(0.05, basket_wall_height/2))
        )
        self.ball_radius = 0.3
        self.ball_spawn_timer = 0
        self.ball_spawn_interval_base = 900
        self.balls_to_spawn = 4
        self.balls_spawned = 0
        self.ball_spawn_order = ['red', 'blue'] * 2
        self.ground = self.world.CreateStaticBody(
            position=(0, -1),
            shapes=polygonShape(box=(20, 0.5))
        )
    MAX_BEAM_LENGTH = 5.0
    MIN_BEAM_LENGTH = 0.1
    MAX_PLATE_SIZE = 2.0
    MAX_PISTON_LENGTH = 5.0
    MAX_MOTOR_TORQUE = 3000.0
    SENSOR_MAX_LENGTH = 5.0
    def add_beam(self, start_pos, end_pos, material='steel', density=1.0):
        if not (self.build_zone['min_x'] <= start_pos[0] <= self.build_zone['max_x'] and
                self.build_zone['min_y'] <= start_pos[1] <= self.build_zone['max_y']):
            raise ValueError(f"Start position {start_pos} not in build area")
        if not (self.build_zone['min_x'] <= end_pos[0] <= self.build_zone['max_x'] and
                self.build_zone['min_y'] <= end_pos[1] <= self.build_zone['max_y']):
            raise ValueError(f"End position {end_pos} not in build area")
        length = math.sqrt((end_pos[0] - start_pos[0])**2 + (end_pos[1] - start_pos[1])**2)
        if length < self.MIN_BEAM_LENGTH or length > self.MAX_BEAM_LENGTH:
            raise ValueError(f"Beam length {length} out of range [{self.MIN_BEAM_LENGTH}, {self.MAX_BEAM_LENGTH}]")
        center_x = (start_pos[0] + end_pos[0]) / 2
        center_y = (start_pos[1] + end_pos[1]) / 2
        angle = math.atan2(end_pos[1] - start_pos[1], end_pos[0] - start_pos[0])
        beam_width = 0.05
        body = self.world.CreateDynamicBody(
            position=(center_x, center_y),
            angle=angle,
            fixtures=Box2D.b2FixtureDef(
                shape=polygonShape(box=(length/2, beam_width/2)),
                density=density,
                friction=0.5,
            )
        )
        self.bodies.append(body)
        return body
    def add_plate(self, center, width, height, angle=0, density=1.0):
        if not (self.build_zone['min_x'] <= center[0] <= self.build_zone['max_x'] and
                self.build_zone['min_y'] <= center[1] <= self.build_zone['max_y']):
            raise ValueError(f"Center position {center} not in build area")
        if width > self.MAX_PLATE_SIZE or height > self.MAX_PLATE_SIZE:
            raise ValueError(f"Plate size exceeds maximum limit {self.MAX_PLATE_SIZE}")
        body = self.world.CreateDynamicBody(
            position=center,
            angle=angle,
            fixtures=Box2D.b2FixtureDef(
                shape=polygonShape(box=(width/2, height/2)),
                density=density,
                friction=0.3,
            )
        )
        self.bodies.append(body)
        return body
    def add_joint(self, body_a, body_b, anchor_point, joint_type='revolute'):
        if joint_type == 'revolute':
            joint = self.world.CreateRevoluteJoint(
                bodyA=body_a,
                bodyB=body_b,
                anchor=anchor_point,
                collideConnected=False
            )
        else:
            try:
                joint = self.world.CreateWeldJoint(
                    bodyA=body_a,
                    bodyB=body_b,
                    anchor=anchor_point
                )
            except:
                joint = self.world.CreateRevoluteJoint(
                    bodyA=body_a,
                    bodyB=body_b,
                    anchor=anchor_point,
                    enableLimit=True,
                    lowerAngle=0.0,
                    upperAngle=0.0,
                    collideConnected=False
                )
        self.joints.append(joint)
        return joint
    def add_piston(self, base_pos, direction, max_length, speed, density=1.0):
        min_x_allowed = -0.5
        if not (min_x_allowed <= base_pos[0] <= self.build_zone['max_x'] and
                self.build_zone['min_y'] <= base_pos[1] <= self.build_zone['max_y']):
            raise ValueError(f"Base position {base_pos} not in allowed build area (allow x>={min_x_allowed})")
        if max_length > self.MAX_PISTON_LENGTH:
            raise ValueError(f"Piston maximum length {max_length} exceeds limit {self.MAX_PISTON_LENGTH}")
        dir_len = math.sqrt(direction[0]**2 + direction[1]**2)
        if dir_len < 0.01:
            raise ValueError("Direction vector cannot be zero")
        direction = (direction[0] / dir_len, direction[1] / dir_len)
        piston_width = 0.15
        piston_head_length = 0.5
        piston_center = (base_pos[0] + direction[0] * piston_head_length/2,
                        base_pos[1] + direction[1] * piston_head_length/2)
        piston_angle = math.atan2(direction[1], direction[0])
        piston_body = self.world.CreateDynamicBody(
            position=piston_center,
            angle=piston_angle,
            fixtures=Box2D.b2FixtureDef(
                shape=polygonShape(box=(piston_head_length/2, piston_width/2)),
                density=density,
                friction=0.3,
                restitution=0.1
            )
        )
        base_body = self.world.CreateStaticBody(position=base_pos)
        joint = self.world.CreatePrismaticJoint(
            bodyA=base_body,
            bodyB=piston_body,
            anchor=base_pos,
            axis=direction,
            lowerTranslation=0.0,
            upperTranslation=max_length,
            enableLimit=True,
            maxMotorForce=10000.0,
            motorSpeed=0.0,
            enableMotor=True
        )
        piston = {
            'body': piston_body,
            'base': base_body,
            'joint': joint,
            'direction': direction,
            'max_length': max_length,
            'speed': speed,
            'current_length': 0.0,
            'target_length': 0.0,
            'active': False
        }
        self.actuators.append(piston)
        self.bodies.append(piston_body)
        self.joints.append(joint)
        return piston
    def activate_piston(self, piston, activate=True):
        piston['active'] = activate
        if activate:
            piston['target_length'] = piston['max_length']
            piston['joint'].motorSpeed = piston['speed']
            if hasattr(piston['joint'], 'enableMotor'):
                piston['joint'].enableMotor = True
        else:
            piston['target_length'] = 0.0
            piston['joint'].motorSpeed = -piston['speed']
            if hasattr(piston['joint'], 'enableMotor'):
                piston['joint'].enableMotor = True
        try:
            if hasattr(piston['joint'], 'GetJointTranslation'):
                piston['current_length'] = piston['joint'].GetJointTranslation()
            else:
                pos_diff = (piston['body'].position.x - piston['base'].position.x,
                           piston['body'].position.y - piston['base'].position.y)
                piston['current_length'] = math.sqrt(pos_diff[0]**2 + pos_diff[1]**2)
        except:
            piston['current_length'] = 0.0
    def add_motor(self, body, anchor_point, torque, speed):
        if torque > self.MAX_MOTOR_TORQUE:
            raise ValueError(f"Torque {torque} exceeds maximum limit {self.MAX_MOTOR_TORQUE}")
        base_body = self.world.CreateStaticBody(position=anchor_point)
        joint = self.world.CreateRevoluteJoint(
            bodyA=base_body,
            bodyB=body,
            anchor=anchor_point,
            enableMotor=True,
            maxMotorTorque=torque,
            motorSpeed=0.0
        )
        motor = {
            'body': body,
            'joint': joint,
            'torque': torque,
            'target_speed': 0.0,
            'current_speed': speed
        }
        self.actuators.append(motor)
        self.joints.append(joint)
        return motor
    def set_motor_speed(self, motor, speed):
        motor['target_speed'] = speed
        motor['joint'].motorSpeed = speed
    def add_raycast_sensor(self, origin, direction, length):
        if length > self.SENSOR_MAX_LENGTH:
            raise ValueError(f"Sensor length {length} exceeds maximum limit {self.SENSOR_MAX_LENGTH}")
        dir_len = math.sqrt(direction[0]**2 + direction[1]**2)
        if dir_len < 0.01:
            raise ValueError("Direction vector cannot be zero")
        direction = (direction[0] / dir_len, direction[1] / dir_len)
        sensor = {
            'origin': origin,
            'direction': direction,
            'length': length,
            'detected_object': None,
            'detected_color': 'NONE',
            'last_raycast_result': None
        }
        self.sensors.append(sensor)
        return sensor
    def get_detected_object_color(self, sensor):
        return sensor['detected_color']
    def add_logic_and(self, input_a, input_b):
        gate = {
            'type': 'AND',
            'input_a': input_a,
            'input_b': input_b,
            'output': False
        }
        self.logic_gates.append(gate)
        return gate
    def add_logic_or(self, input_a, input_b):
        gate = {
            'type': 'OR',
            'input_a': input_a,
            'input_b': input_b,
            'output': False
        }
        self.logic_gates.append(gate)
        return gate
    def add_logic_not(self, input_a):
        gate = {
            'type': 'NOT',
            'input_a': input_a,
            'output': False
        }
        self.logic_gates.append(gate)
        return gate
    def add_delay(self, input_signal, delay_seconds, output_duration=0.1):
        delay = {
            'type': 'DELAY',
            'input': input_signal,
            'delay': delay_seconds,
            'output_duration': output_duration,
            'buffer': [],
            'output': False,
            'last_input': False
        }
        self.logic_gates.append(delay)
        return delay
    def add_wire(self, source, target):
        wire = {
            'source': source,
            'target': target
        }
        self.wires.append(wire)
        return wire
    def spawn_ball(self, color):
        if self.balls_spawned >= self.balls_to_spawn:
            return None
        spawn_x, spawn_y = self.spawn_point
        CONVEYOR_TOP_Y = self.conveyor_y + 0.15
        spawn_y = CONVEYOR_TOP_Y + self.ball_radius + 0.001
        ball_body = self.world.CreateDynamicBody(
            position=(spawn_x, spawn_y),
            fixtures=Box2D.b2FixtureDef(
                shape=circleShape(radius=self.ball_radius),
                density=0.5,
                friction=0.0,
                restitution=0.2
            )
        )
        ball_body.linearVelocity = (self.conveyor_speed * 1.5, 0.0)
        ball_data = {
            'body': ball_body,
            'color': color,
            'classified': False,
            'in_basket': False
        }
        self.balls.append(ball_data)
        self.balls_spawned += 1
        return ball_body
    def step(self, time_step):
        CONVEYOR_TOP_Y = self.conveyor_y + 0.15
        for ball_data in self.balls:
            ball = ball_data['body']
            ball_x = ball.position.x
            ball_y = ball.position.y
            if (self.conveyor_start_x <= ball_x <= self.conveyor_end_x and
                ball_y >= CONVEYOR_TOP_Y and ball_y <= CONVEYOR_TOP_Y + 1.0):
                ball.linearVelocity = (self.conveyor_speed * 1.2, 0.0)
                ball.angularVelocity = 0.0
                if ball_y > CONVEYOR_TOP_Y + self.ball_radius + 0.01:
                    ball.position = (ball_x, CONVEYOR_TOP_Y + self.ball_radius)
        self.world.Step(time_step, 10, 10)
        for sensor in self.sensors:
            self._update_sensor(sensor)
        self._update_logic_gates(time_step)
        self._update_actuators()
    def _update_sensor(self, sensor):
        origin = sensor['origin']
        direction = sensor['direction']
        length = sensor['length']
        end_point = (origin[0] + direction[0] * length,
                    origin[1] + direction[1] * length)
        min_distance = float('inf')
        closest_ball = None
        for ball_data in self.balls:
            ball = ball_data['body']
            ball_pos = ball.position
            dx = end_point[0] - origin[0]
            dy = end_point[1] - origin[1]
            if dx == 0 and dy == 0:
                continue
            t = max(0, min(1, ((ball_pos.x - origin[0]) * dx + (ball_pos.y - origin[1]) * dy) / (dx*dx + dy*dy)))
            proj_x = origin[0] + t * dx
            proj_y = origin[1] + t * dy
            dist = math.sqrt((ball_pos.x - proj_x)**2 + (ball_pos.y - proj_y)**2)
            if dist < self.ball_radius + 1.0:
                if 0 <= t <= 1:
                    if dist < min_distance:
                        min_distance = dist
                        closest_ball = ball_data
        if closest_ball:
            sensor['detected_object'] = closest_ball['body']
            sensor['detected_color'] = closest_ball['color'].upper()
        else:
            sensor['detected_object'] = None
            sensor['detected_color'] = 'NONE'
    def _update_logic_gates(self, time_step):
        for gate in self.logic_gates:
            if gate['type'] == 'AND':
                input_a_val = self._get_signal_value(gate['input_a'])
                input_b_val = self._get_signal_value(gate['input_b'])
                gate['output'] = input_a_val and input_b_val
            elif gate['type'] == 'OR':
                input_a_val = self._get_signal_value(gate['input_a'])
                input_b_val = self._get_signal_value(gate['input_b'])
                gate['output'] = input_a_val or input_b_val
            elif gate['type'] == 'NOT':
                input_val = self._get_signal_value(gate['input_a'])
                gate['output'] = not input_val
            elif gate['type'] == 'DELAY':
                if 'input_signal_value' in gate:
                    input_val = gate['input_signal_value']
                else:
                    input_val = self._get_signal_value(gate['input'])
                last_input = gate.get('last_input', False)
                if input_val and not last_input:
                    gate['buffer'].append((True, gate['delay']))
                gate['last_input'] = input_val
                new_buffer = []
                gate['output'] = False
                output_duration = gate.get('output_duration', 0.3)
                for val, remaining_time in gate['buffer']:
                    remaining_time -= time_step
                    if remaining_time <= 0:
                        elapsed = -remaining_time
                        if elapsed <= output_duration:
                            gate['output'] = val
                            new_buffer.append((val, remaining_time))
                    else:
                        new_buffer.append((val, remaining_time))
                gate['buffer'] = new_buffer
    def _get_signal_value(self, source):
        if isinstance(source, dict):
            if 'detected_color' in source:
                return source['detected_color'] == 'RED'
            elif 'output' in source:
                return source['output']
            elif 'input_signal_value' in source:
                return source['input_signal_value']
            elif 'active' in source:
                return source['active']
        return False
    def _update_actuators(self):
        for wire in self.wires:
            source_val = self._get_signal_value(wire['source'])
            target = wire['target']
            if isinstance(target, dict) and 'active' in target:
                self.activate_piston(target, source_val)
            elif isinstance(target, dict) and 'target_speed' in target:
                speed = target['current_speed'] if source_val else 0.0
                self.set_motor_speed(target, speed)
    def get_basket_bounds(self):
        return {
            'red': self.red_basket,
            'blue': self.blue_basket
        }
