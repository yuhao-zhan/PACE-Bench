from __future__ import annotations

import math

from typing import Any, Dict, List

try:
    from .environment import (
        BALANCE_ANGLE_DEG,
        BALANCE_HOLD_STEPS_REQUIRED,
        FAILURE_ANGLE_DEG,
    )

except ImportError:
    from environment import (
        BALANCE_ANGLE_DEG,
        BALANCE_HOLD_STEPS_REQUIRED,
        FAILURE_ANGLE_DEG,
    )

BALANCE_HOLD_EVALS_REQUIRED = BALANCE_HOLD_STEPS_REQUIRED

from pace_bench.primitives import compute_constraint_penalty

class Evaluator:
    def __init__(self, sandbox: Any):
        self.sandbox = sandbox
        self.balance_angle_rad = math.radians(
            float(getattr(self.sandbox, "balance_angle_deg", BALANCE_ANGLE_DEG))
        )
        self.failure_angle_rad = math.radians(
            float(getattr(self.sandbox, "failure_angle_deg", FAILURE_ANGLE_DEG))
        )
        self._balance_hold_required = int(
            getattr(self.sandbox, "balance_hold_steps_required", BALANCE_HOLD_STEPS_REQUIRED)
        )
        self._balance_achieved = False
    def evaluate(self, agent_body: Any, step_count: int, max_steps: int) -> tuple[bool, float, dict]:
        pole_angle_true = self.sandbox.get_true_pole_angle()
        pole_omega_true = self.sandbox.get_true_pole_angular_velocity()
        pole_angle_reported = self.sandbox.get_pole_angle()
        pole_omega_reported = self.sandbox.get_pole_angular_velocity()
        cart_pos = self.sandbox.get_cart_position()
        cart_vel = self.sandbox.get_cart_velocity()
        track_center = self.sandbox.TRACK_CENTER_X
        safe_range = self.sandbox.SAFE_HALF_RANGE
        dist_from_center = abs(cart_pos - track_center)
        env_limit = getattr(self.sandbox, "MAX_STEPS", max_steps)
        step_limit = min(max_steps, env_limit)
        _force_limit = getattr(self.sandbox, "cart_force_limit_newtons", 450.0)
        _applied_force = getattr(self.sandbox, "_last_applied_force", 0.0)
        _pole_mass_val = getattr(self.sandbox, "_pole_mass", 1.0)
        _cart_mass_val = getattr(self.sandbox, "_cart_mass", 10.0)
        _pole_length_val = getattr(self.sandbox, "_pole_length", 2.0)
        _sensor_delay_a = getattr(self.sandbox, "_sensor_delay_angle_steps", 0)
        _sensor_delay_w = getattr(self.sandbox, "_sensor_delay_omega_steps", 0)
        _grav_y = float(self.sandbox.world.gravity[1]) if hasattr(self.sandbox, "world") else -10.0
        metrics = {
            "pole_angle_deg": math.degrees(pole_angle_reported),
            "pole_angular_velocity": pole_omega_reported,
            "pole_angle_true_deg": math.degrees(pole_angle_true),
            "pole_angular_velocity_true": pole_omega_true,
            "cart_x": cart_pos,
            "cart_velocity_x": cart_vel,
            "dist_from_center": dist_from_center,
            "safe_half_range": safe_range,
            "track_center_x": track_center,
            "step_count": step_count,
            "balance_achieved": self._balance_achieved,
            "consecutive_upright_sim_steps": self.sandbox.get_consecutive_upright_sim_steps(),
            "balance_hold_steps_required": self._balance_hold_required,
            "max_steps": step_limit,
            "grading_balance_angle_deg": float(
                getattr(self.sandbox, "balance_angle_deg", BALANCE_ANGLE_DEG)
            ),
            "grading_failure_angle_deg": float(
                getattr(self.sandbox, "failure_angle_deg", FAILURE_ANGLE_DEG)
            ),
            "force_limit": float(_force_limit),
            "applied_force": float(_applied_force),
            "pole_mass": float(_pole_mass_val),
            "cart_mass": float(_cart_mass_val),
            "pole_length": float(_pole_length_val),
            "sensor_delay_angle_steps": int(_sensor_delay_a),
            "sensor_delay_omega_steps": int(_sensor_delay_w),
            "gravity_y": float(_grav_y),
            "success": False,
            "failed": False
        }
        if dist_from_center > safe_range:
            metrics.update({"failed": True, "reason": "Cart left safe zone", "failure_reason": "Cart left safe zone"})
            return True, 0.0, metrics
        is_upright = abs(pole_angle_true) <= self.balance_angle_rad
        if step_count > 0:
            if not self._balance_achieved:
                n_up = self.sandbox.get_consecutive_upright_sim_steps()
                if n_up >= self._balance_hold_required:
                    self._balance_achieved = True
                    metrics["balance_achieved"] = True
            else:
                if abs(pole_angle_true) > self.failure_angle_rad:
                    metrics.update(
                        {
                            "failed": True,
                            "reason": "Pole fell after balancing",
                            "failure_reason": "Pole fell after balancing",
                        }
                    )
                    return True, 0.0, metrics
        done = step_count >= step_limit
        if done:
            if self._balance_achieved and is_upright:
                metrics["success"] = True
                return True, 100.0, metrics
            elif not self._balance_achieved:
                metrics.update({"failed": True, "reason": "Time limit reached without balancing", "failure_reason": "Time limit reached without balancing"})
                return True, 0.0, metrics
            else:
                metrics.update({"failed": True, "reason": "Pole not in upright region at end", "failure_reason": "Pole not in upright region at end"})
                return True, 0.0, metrics
        return False, 0.0, metrics
    def compute_score_with_penalty(self, score: float, metrics: dict) -> float:
        if score > 0:
            return score
        constraint_info = self.get_constraint_info()
        penalty = compute_constraint_penalty("C_01", score, metrics, constraint_info)
        return penalty
    def get_constraint_info(self):
        return {
            'balance_angle_rad': self.balance_angle_rad,
            'failure_angle_rad': self.failure_angle_rad,
            'balance_hold_steps_required': self._balance_hold_required,
        }
    def get_task_description(self):
        return {
            "task_name": "Cart-Pole Balance",
            "description": (
            ),
            "metrics": {
                "balance_achieved": f"≥{int(BALANCE_HOLD_EVALS_REQUIRED)} consecutive in-band (≤{int(BALANCE_ANGLE_DEG)}°) true-angle steps",
                "success": f"Lock-in achieved, on track, terminal |true angle| ≤ {int(BALANCE_ANGLE_DEG)}° at horizon",
            },
            "evaluation": {"score_range": "0-100", "success_score": 100, "failure_score": 0},
        }

def get_evaluator(sandbox: Any) -> Evaluator:
    return Evaluator(sandbox)

def score_to_metrics(score: float, metrics: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "score": score,
        "success": metrics.get("success", False),
        "balance_achieved": metrics.get("balance_achieved", False),
    }
