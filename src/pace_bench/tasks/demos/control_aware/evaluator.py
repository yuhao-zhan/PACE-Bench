import math

from pace_bench.primitives import compute_constraint_penalty

class Evaluator:
    def __init__(self, terrain_bounds, environment=None):
        self.terrain_bounds = terrain_bounds
        self.environment = environment
        self.start_x = 0.0
        self.target_x = 30.0
        self.max_distance = 0.0
        self.speed_violations = []
        self.speed_violation_count = 0
        if environment:
            speed_zones = environment.get_speed_zone_limits()
            self.SPEED_ZONE_1_START = speed_zones["zone_1"]["start"]
            self.SPEED_ZONE_1_END = speed_zones["zone_1"]["end"]
            self.SPEED_ZONE_1_LIMIT = speed_zones["zone_1"]["limit"]
            self.SPEED_ZONE_2_START = speed_zones["zone_2"]["start"]
            self.SPEED_ZONE_2_END = speed_zones["zone_2"]["end"]
            self.SPEED_ZONE_2_LIMIT = speed_zones["zone_2"]["limit"]
            self.SPEED_ZONE_3_START = speed_zones["zone_3"]["start"]
            self.SPEED_ZONE_3_END = speed_zones["zone_3"]["end"]
            self.SPEED_ZONE_3_LIMIT = speed_zones["zone_3"]["limit"]
        else:
            raise ValueError("Evaluator requires environment instance")
        self.max_x_reached = 0.0
    def _get_speed_limit(self, x_position):
        if self.SPEED_ZONE_1_START <= x_position < self.SPEED_ZONE_1_END:
            return self.SPEED_ZONE_1_LIMIT
        elif self.SPEED_ZONE_2_START <= x_position < self.SPEED_ZONE_2_END:
            return self.SPEED_ZONE_2_LIMIT
        elif self.SPEED_ZONE_3_START <= x_position < self.SPEED_ZONE_3_END:
            return self.SPEED_ZONE_3_LIMIT
        else:
            return self.SPEED_ZONE_1_LIMIT
    def _get_current_zone(self, x_position):
        if self.SPEED_ZONE_1_START <= x_position < self.SPEED_ZONE_1_END:
            return "Zone 1"
        elif self.SPEED_ZONE_2_START <= x_position < self.SPEED_ZONE_2_END:
            return "Zone 2"
        elif self.SPEED_ZONE_3_START <= x_position < self.SPEED_ZONE_3_END:
            return "Zone 3"
        else:
            return "Outside zones"
    def evaluate(self, agent_components, step_count, max_steps):
        if not agent_components or 'slider' not in agent_components:
            return False, 0.0, {'error': 'Missing slider in agent_components'}
        slider = agent_components['slider']
        if not self.environment:
            return False, 0.0, {'error': 'Environment not provided'}
        position_x, velocity_x = self.environment.get_slider_state(slider)
        position_y = slider.position.y
        if position_x > self.max_x_reached:
            self.max_x_reached = position_x
        distance_traveled = position_x - self.start_x
        if distance_traveled > self.max_distance:
            self.max_distance = distance_traveled
        speed_limit = self._get_speed_limit(position_x)
        speed_violated = False
        if position_x >= self.SPEED_ZONE_1_START and position_x < self.SPEED_ZONE_3_END:
            if velocity_x > speed_limit:
                speed_violated = True
                self.speed_violation_count += 1
                self.speed_violations.append({
                    'step': step_count,
                    'x_position': position_x,
                    'speed': velocity_x,
                    'limit': speed_limit,
                    'zone': self._get_current_zone(position_x)
                })
        success = position_x >= self.target_x
        failed = False
        failure_reason = None
        if speed_violated:
            failed = True
            current_zone = self._get_current_zone(position_x)
            failure_reason = f"Speed limit violated in {current_zone}: speed {velocity_x:.2f} m/s exceeds limit {speed_limit:.2f} m/s"
        if position_y < self.environment.SLIDER_MIN_Y or position_y > self.environment.SLIDER_MAX_Y:
            failed = True
            failure_reason = f"Slider fell off track (y={position_y:.2f}m, track y={self.environment.TRACK_Y}m)"
        if position_x < self.max_x_reached - 0.5:
            failed = True
            failure_reason = f"Slider moved backward (current x={position_x:.2f}m, max x={self.max_x_reached:.2f}m)"
        if step_count >= max_steps and not success:
            failed = True
            failure_reason = f"Timeout: did not reach target position within {max_steps} steps"
        if success and not failed:
            score = 100.0
        elif failed:
            score = 0.0
        else:
            progress = min(distance_traveled / (self.target_x - self.start_x), 1.0)
            score = progress * 80.0
        current_zone = self._get_current_zone(position_x)
        speed_limit = self._get_speed_limit(position_x)
        metrics = {
            'distance_traveled': distance_traveled,
            'current_x': position_x,
            'current_y': position_y,
            'target_x': self.target_x,
            'progress': min(distance_traveled / (self.target_x - self.start_x), 1.0) * 100,
            'success': success and not failed,
            'failed': failed,
            'failure_reason': failure_reason,
            'step_count': step_count,
            'max_distance': self.max_distance,
            'velocity_x': velocity_x,
            'current_zone': current_zone,
            'speed_limit': speed_limit,
            'speed_violated': speed_violated,
            'speed_violation_count': self.speed_violation_count,
            'max_x_reached': self.max_x_reached
        }
        return success or failed, score, metrics
    def compute_score_with_penalty(self, score: float, metrics: dict) -> float:
        if score > 0:
            return score
        constraint_info = self.get_constraint_info()
        penalty = compute_constraint_penalty("control_aware", score, metrics, constraint_info)
        return penalty
    def get_constraint_info(self):
        return {
            'start_x': self.start_x,
            'target_x': self.target_x,
            'speed_zone_1_start': self.SPEED_ZONE_1_START,
            'speed_zone_1_end': self.SPEED_ZONE_1_END,
            'speed_zone_1_limit': self.SPEED_ZONE_1_LIMIT,
            'speed_zone_2_start': self.SPEED_ZONE_2_START,
            'speed_zone_2_end': self.SPEED_ZONE_2_END,
            'speed_zone_2_limit': self.SPEED_ZONE_2_LIMIT,
            'speed_zone_3_start': self.SPEED_ZONE_3_START,
            'speed_zone_3_end': self.SPEED_ZONE_3_END,
            'speed_zone_3_limit': self.SPEED_ZONE_3_LIMIT,
        }
    def get_task_description(self):
        return {
            'task': 'Control slider speed based on position to comply with speed limits',
            'description': 'Agent needs to control a slider that dynamically adjusts speed based on position',
            'start_position': self.start_x,
            'target_position': self.target_x,
            'speed_zones': {
                'zone_1': {'start': self.SPEED_ZONE_1_START, 'end': self.SPEED_ZONE_1_END, 'limit': self.SPEED_ZONE_1_LIMIT},
                'zone_2': {'start': self.SPEED_ZONE_2_START, 'end': self.SPEED_ZONE_2_END, 'limit': self.SPEED_ZONE_2_LIMIT},
                'zone_3': {'start': self.SPEED_ZONE_3_START, 'end': self.SPEED_ZONE_3_END, 'limit': self.SPEED_ZONE_3_LIMIT},
            },
            'success_criteria': {
                'primary': f'Slider must reach position x={self.target_x}m',
                'speed_compliance': 'Slider must never exceed speed limits in any zone',
                'constraint_track': 'Slider cannot fall off track',
                'constraint_backward': 'Slider cannot move backward'
            },
            'evaluation': {
                'score_range': '0-100',
                'success_score': 100,
                'partial_score': 'Based on travel distance, max 80 points',
                'failure_score': 0
            }
        }
