import sys

import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))

from pace_bench.primitives import compute_constraint_penalty

from environment import (
    MEAN_SPEED_ERROR_THRESHOLD,
    REGULATION_START_STEP,
    STALL_SPEED_THRESHOLD,
    STALL_STEPS_THRESHOLD,
    TARGET_SPEED_RAD_S,

)

def _stall_steps_from_bounds(terrain_bounds):
    return int(terrain_bounds.get("stall_steps_threshold", STALL_STEPS_THRESHOLD))

class Evaluator:
    def __init__(self, terrain_bounds, environment=None):
        self.terrain_bounds = terrain_bounds
        self.environment = environment
        self._target_speed_time_varying = bool(terrain_bounds.get("target_speed_time_varying", False))
        self._regulation_start = int(terrain_bounds.get("regulation_start_step", REGULATION_START_STEP))
        self._stall_threshold = float(terrain_bounds.get("stall_speed_threshold", STALL_SPEED_THRESHOLD))
        self._stall_steps_threshold = _stall_steps_from_bounds(terrain_bounds)
        self._mean_speed_error_threshold = float(terrain_bounds.get("mean_speed_error_threshold", MEAN_SPEED_ERROR_THRESHOLD))
        self._stall_count = 0
        self._speed_error_sum = 0.0
        self._speed_error_count = 0
    def evaluate(self, agent_body, step_count, max_steps):
        if not self.environment:
            return True, 0.0, {"error": "Environment not available"}
        omega = self.environment.get_wheel_angular_velocity_actual()
        target = self.environment.get_target_speed()
        speed_error = abs(omega - target)
        if step_count >= self._regulation_start:
            self._speed_error_sum += speed_error
            self._speed_error_count += 1
        if abs(omega) < self._stall_threshold:
            self._stall_count += 1
        else:
            self._stall_count = 0
        failed = False
        failure_reason = None
        if self._stall_count >= self._stall_steps_threshold:
            failed = True
            failure_reason = (
                f"Wheel stalled: |ω| below {self._stall_threshold} rad/s for "
                f"{self._stall_steps_threshold} consecutive steps"
            )
        mean_speed_error = (
            self._speed_error_sum / self._speed_error_count
            if self._speed_error_count > 0
            else 0.0
        )
        if (step_count >= max_steps - 1) and not failed:
            if max_steps <= self._regulation_start:
                failed = True
                failure_reason = (
                    f"Simulation horizon ({max_steps} steps) does not exceed "
                    f"regulation start step ({self._regulation_start}); "
                    f"regulation phase was never reached."
                )
            elif self._speed_error_count == 0:
                failed = True
                failure_reason = (
                )
            elif mean_speed_error > self._mean_speed_error_threshold:
                failed = True
                failure_reason = (
                    f"Mean speed tracking error {mean_speed_error:.4f} rad/s exceeds threshold "
                    f"{self._mean_speed_error_threshold:.4f} rad/s"
                )
        success = (step_count >= max_steps - 1) and not failed
        if success and not failed:
            score = 100.0
        elif failed:
            score = 0.0
        else:
            progress = step_count / max_steps if max_steps > 0 else 0.0
            score = progress * 80.0
        metrics = {
            "wheel_angular_velocity": omega,
            "target_speed": target,
            "speed_error": speed_error,
            "mean_speed_error": mean_speed_error,
            "stall_count": self._stall_count,
            "stall_speed_threshold": self._stall_threshold,
            "stall_steps_threshold": self._stall_steps_threshold,
            "mean_speed_error_threshold": self._mean_speed_error_threshold,
            "regulation_start_step": self._regulation_start,
            "step_count": step_count,
            "max_steps": max_steps,
            "success": success,
            "failed": failed,
            "failure_reason": failure_reason,
        }
        if self.environment is not None:
            try:
                metrics["commanded_torque"] = self.environment.get_last_commanded_torque()
            except (AttributeError, Exception):
                pass
            try:
                metrics["applied_torque"] = self.environment.get_last_applied_torque()
            except (AttributeError, Exception):
                pass
            try:
                metrics["load_torque"] = self.environment.get_last_load_torque()
            except (AttributeError, Exception):
                pass
            try:
                metrics["max_torque_limit"] = self.environment.get_last_max_torque()
            except (AttributeError, Exception):
                pass
            try:
                metrics["torque_deadzone"] = self.environment.get_torque_deadzone()
            except (AttributeError, Exception):
                pass
            try:
                metrics["measurement_delay"] = self.environment.get_measurement_delay()
            except (AttributeError, Exception):
                pass
            try:
                metrics["wheel_angle"] = self.environment.get_wheel_angle()
            except (AttributeError, Exception):
                pass
            try:
                I_wheel = self.environment.get_wheel_moment_of_inertia()
                metrics["wheel_moment_of_inertia"] = I_wheel
                metrics["wheel_rotational_ke"] = 0.5 * I_wheel * omega * omega
            except (AttributeError, Exception):
                pass
            try:
                app_torque = metrics.get("applied_torque", 0.0)
                if app_torque is not None and hasattr(app_torque, '__float__'):
                    metrics["motor_power"] = float(app_torque) * omega
            except (AttributeError, Exception):
                pass
            try:
                ld_torque = metrics.get("load_torque", 0.0)
                if ld_torque is not None and hasattr(ld_torque, '__float__'):
                    metrics["load_power"] = float(ld_torque) * abs(omega)
            except (AttributeError, Exception):
                pass
        done = failed or (step_count >= max_steps - 1)
        return done, score, metrics
    def compute_score_with_penalty(self, score: float, metrics: dict) -> float:
        if score > 0:
            return score
        constraint_info = self.get_constraint_info()
        penalty = compute_constraint_penalty("C_06", score, metrics, constraint_info)
        return penalty
    def get_constraint_info(self):
        return {
            'target_speed_rad_s': float(self.terrain_bounds.get("target_speed_rad_s", TARGET_SPEED_RAD_S)),
            'target_speed_time_varying': self._target_speed_time_varying,
            'regulation_start': self._regulation_start,
            'stall_threshold': self._stall_threshold,
            'stall_steps_threshold': self._stall_steps_threshold,
            'mean_speed_error_threshold': self._mean_speed_error_threshold,
        }
    def get_task_description(self):
        initial_target = float(self.terrain_bounds.get("target_speed_rad_s", TARGET_SPEED_RAD_S))
        return {
            "task": "C-06: The Governor",
            "description": "Maintain wheel speed at the commanded target under load (load may vary with speed and time).",
            "target_speed_rad_s": initial_target,
            "target_speed_time_varying": self._target_speed_time_varying,
            "stall_speed_threshold": self._stall_threshold,
            "stall_steps_threshold": self._stall_steps_threshold,
            "mean_speed_error_threshold_rad_s": self._mean_speed_error_threshold,
            "regulation_start_step": self._regulation_start,
            "success_criteria": {
                "primary": (
                    f"Through the episode after regulation start, keep mean |ω−target| below "
                    f"{self._mean_speed_error_threshold} rad/s and avoid prolonged stall"
                ),
                "failure": (
                    f"Mean |ω−target| exceeds {self._mean_speed_error_threshold} rad/s over "
                    f"the regulation phase, or wheel stalls (|ω| below "
                    f"{self._stall_threshold} rad/s for {self._stall_steps_threshold} consecutive steps)."
                ),
            },
            "evaluation": {
                "score_range": "0-100",
                "success_score": 100,
                "failure_score": 0,
            },
        }
