import sys

import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))

import math as _math

def _add_nominal(metrics, actual_key, env_cls, cls_attr, nominal_key):
    actual = metrics.get(actual_key)
    if actual is None:
        return
    try:
        nominal = float(getattr(env_cls, cls_attr, None))
    except (TypeError, ValueError):
        return
    try:
        if not _math.isfinite(float(actual)) or not _math.isfinite(nominal):
            return
    except (TypeError, ValueError):
        return
    metrics[nominal_key] = nominal

class Evaluator:
    def __init__(self, terrain_bounds, environment=None):
        self.terrain_bounds = terrain_bounds
        self.environment = environment
        self.initial_joint_count = 0
        self.structure_broken = False
        self.design_constraints_checked = False
        if environment is None:
            raise ValueError("Evaluator requires environment instance")
        self.MAX_STRUCTURE_MASS = float(terrain_bounds.get("max_structure_mass", environment.MAX_STRUCTURE_MASS))
        bz = terrain_bounds.get("build_zone", {})
        self.BUILD_ZONE_X_MIN = float(bz.get("x", [environment.BUILD_ZONE_X_MIN, environment.BUILD_ZONE_X_MAX])[0])
        self.BUILD_ZONE_X_MAX = float(bz.get("x", [environment.BUILD_ZONE_X_MIN, environment.BUILD_ZONE_X_MAX])[1])
        self.BUILD_ZONE_Y_MIN = float(bz.get("y", [environment.BUILD_ZONE_Y_MIN, environment.BUILD_ZONE_Y_MAX])[0])
        self.BUILD_ZONE_Y_MAX = float(bz.get("y", [environment.BUILD_ZONE_Y_MIN, environment.BUILD_ZONE_Y_MAX])[1])
        self.MIN_BEAMS = int(terrain_bounds.get("min_beams", getattr(environment, "MIN_BEAMS", 1)))
        self.MIN_JOINTS = int(terrain_bounds.get("min_joints", getattr(environment, "MIN_JOINTS", 1)))
        self.SPAN_LEFT_X = float(terrain_bounds.get("span_left_x", getattr(environment, "SPAN_LEFT_X", 6.0)))
        self.SPAN_RIGHT_X = float(terrain_bounds.get("span_right_x", getattr(environment, "SPAN_RIGHT_X", 14.0)))
    def evaluate(self, agent_body, step_count, max_steps):
        if not self.environment:
            return True, 0.0, {"error": "Environment not available"}
        if not self.design_constraints_checked and step_count == 0:
            violations = self._check_design_constraints()
            if violations:
                return True, 0.0, {
                    "success": False,
                    "failed": True,
                    "failure_reason": "Design constraint violated: " + "; ".join(violations),
                    "step_count": step_count,
                    "structure_broken": False,
                    "joint_count": len(self.environment._joints),
                    "beam_count": len(self.environment._bodies),
                    "structure_mass": self.environment.get_structure_mass(),
                    "max_structure_mass": self.MAX_STRUCTURE_MASS,
                }
            self.design_constraints_checked = True
        if step_count == 0:
            self.initial_joint_count = len(self.environment._joints)
        current_joint_count = len(self.environment._joints)
        if current_joint_count < self.initial_joint_count:
            self.structure_broken = True
        failed = self.structure_broken
        success = (not failed) and (step_count >= max_steps - 1)
        if failed:
            failure_reason = "Structure disintegrated: one or more joints broke (reaction force or torque exceeded limit)"
        else:
            failure_reason = None
        if success:
            score = 100.0
        elif failed:
            score = 0.0
        else:
            progress = step_count / max(max_steps, 1)
            score = progress * 80.0
        metrics = {
            "step_count": step_count,
            "success": success and not failed,
            "failed": failed,
            "failure_reason": failure_reason,
            "structure_broken": self.structure_broken,
            "joint_count": current_joint_count,
            "beam_count": len(self.environment._bodies),
            "initial_joint_count": self.initial_joint_count,
            "structure_mass": self.environment.get_structure_mass(),
            "max_structure_mass": self.MAX_STRUCTURE_MASS,
        }
        if hasattr(self.environment, "get_max_joint_reaction_force"):
            metrics["max_joint_reaction_force"] = self.environment.get_max_joint_reaction_force()
        if hasattr(self.environment, "get_max_joint_reaction_torque"):
            metrics["max_joint_reaction_torque"] = self.environment.get_max_joint_reaction_torque()
        if hasattr(self.environment, "JOINT_BREAK_FORCE"):
            metrics["joint_break_force_limit"] = self.environment.JOINT_BREAK_FORCE
        if hasattr(self.environment, "JOINT_BREAK_TORQUE"):
            metrics["joint_break_torque_limit"] = self.environment.JOINT_BREAK_TORQUE
        if hasattr(self.environment, "get_effective_joint_force_limit"):
            metrics["effective_joint_force_limit"] = self.environment.get_effective_joint_force_limit()
        if hasattr(self.environment, "get_effective_joint_torque_limit"):
            metrics["effective_joint_torque_limit"] = self.environment.get_effective_joint_torque_limit()
        if hasattr(self.environment, "_time"):
            metrics["simulation_time_s"] = self.environment._time
        if hasattr(self.environment, "get_joints_ever_broken"):
            metrics["joints_ever_broken"] = self.environment.get_joints_ever_broken()
        if hasattr(self.environment, "get_per_joint_peaks"):
            metrics["per_joint_peaks"] = self.environment.get_per_joint_peaks()
        if hasattr(self.environment, "get_joint_anchor_positions"):
            metrics["joint_anchor_positions"] = self.environment.get_joint_anchor_positions()
        if hasattr(self.environment, "get_beam_areas"):
            metrics["beam_areas"] = self.environment.get_beam_areas()
        if hasattr(self.environment, "get_wind_pressure"):
            metrics["wind_pressure"] = self.environment.get_wind_pressure()
        if hasattr(self.environment, "get_gravity"):
            metrics["gravity"] = self.environment.get_gravity()
        if hasattr(self.environment, "get_current_fatigue_factor"):
            metrics["fatigue_factor"] = self.environment.get_current_fatigue_factor()
        if hasattr(self.environment, "get_base_excitation_params"):
            metrics["base_excitation_params"] = self.environment.get_base_excitation_params()
        if hasattr(self.environment, "get_mass_variation_params"):
            metrics["mass_variation_params"] = self.environment.get_mass_variation_params()
        if hasattr(self.environment, "get_peak_body_speed"):
            metrics["peak_body_speed"] = self.environment.get_peak_body_speed()
        if hasattr(self.environment, "FATIGUE_TAU_SECONDS"):
            metrics["fatigue_tau"] = self.environment.FATIGUE_TAU_SECONDS
        if "mass_variation_params" in metrics:
            mvp = metrics["mass_variation_params"]
            if isinstance(mvp, (list, tuple)) and len(mvp) >= 5:
                metrics["mass_freq_1"] = mvp[0]
                metrics["mass_amp_1"] = mvp[1]
                metrics["mass_freq_2"] = mvp[2]
                metrics["mass_amp_2"] = mvp[3]
                metrics["mass_phase_gradient"] = mvp[4]
        if "base_excitation_params" in metrics:
            bep = metrics["base_excitation_params"]
            if isinstance(bep, (list, tuple)) and len(bep) >= 3:
                metrics["base_exc_horiz_amp"] = bep[0]
                metrics["base_exc_vert_amp"] = bep[1]
                metrics["base_exc_freq"] = bep[2]
        env_cls = type(self.environment)
        _add_nominal(metrics, "joint_break_force_limit", env_cls, "JOINT_BREAK_FORCE",
                     "joint_break_force_nominal")
        _add_nominal(metrics, "joint_break_torque_limit", env_cls, "JOINT_BREAK_TORQUE",
                     "joint_break_torque_nominal")
        _add_nominal(metrics, "fatigue_tau", env_cls, "FATIGUE_TAU_SECONDS",
                     "fatigue_tau_nominal")
        _add_nominal(metrics, "wind_pressure", env_cls, "WIND_PRESSURE",
                     "wind_pressure_nominal")
        _add_nominal(metrics, "mass_freq_1", env_cls, "MASS_FREQ_1",
                     "mass_freq_1_nominal")
        _add_nominal(metrics, "mass_amp_1", env_cls, "MASS_AMP_1",
                     "mass_amp_1_nominal")
        _add_nominal(metrics, "mass_freq_2", env_cls, "MASS_FREQ_2",
                     "mass_freq_2_nominal")
        _add_nominal(metrics, "mass_amp_2", env_cls, "MASS_AMP_2",
                     "mass_amp_2_nominal")
        _add_nominal(metrics, "mass_phase_gradient", env_cls, "MASS_PHASE_GRADIENT",
                     "mass_phase_gradient_nominal")
        _add_nominal(metrics, "base_exc_vert_amp", env_cls, "BASE_EXCITATION_VERTICAL_AMPLITUDE",
                     "base_exc_vert_amp_nominal")
        _add_nominal(metrics, "base_exc_horiz_amp", env_cls, "BASE_EXCITATION_HORIZONTAL_AMPLITUDE",
                     "base_exc_horiz_amp_nominal")
        _add_nominal(metrics, "base_exc_freq", env_cls, "BASE_EXCITATION_FREQUENCY",
                     "base_exc_freq_nominal")
        return failed or (step_count >= max_steps - 1), score, metrics
    def _check_design_constraints(self):
        violations = []
        if not self.environment:
            return ["Environment not available"]
        mass = self.environment.get_structure_mass()
        if mass > self.MAX_STRUCTURE_MASS:
            violations.append(f"Structure mass {mass:.2f} kg exceeds maximum {self.MAX_STRUCTURE_MASS} kg")
        n_bodies = len(self.environment._bodies)
        if n_bodies < self.MIN_BEAMS:
            violations.append(f"Structure has {n_bodies} beam(s); at least {self.MIN_BEAMS} beams required")
        n_joints = len(self.environment._joints)
        if n_joints < self.MIN_JOINTS:
            violations.append(f"Structure has {n_joints} joint(s); at least {self.MIN_JOINTS} joints required")
        if self.SPAN_LEFT_X is not None and self.SPAN_RIGHT_X is not None:
            xs = [body.position.x for body in self.environment._bodies]
            if not xs or min(xs) > self.SPAN_LEFT_X:
                violations.append(f"Structure must span left: at least one beam center at x ≤ {self.SPAN_LEFT_X}")
            if not xs or max(xs) < self.SPAN_RIGHT_X:
                violations.append(f"Structure must span right: at least one beam center at x ≥ {self.SPAN_RIGHT_X}")
        joint_types = getattr(self.environment, "_joint_types", {})
        if joint_types and not any(jt == "pivot" for jt in joint_types.values()):
            violations.append("At least one joint must be a pivot (revolute); use type='pivot' for one joint")
        for body in self.environment._bodies:
            x, y = body.position.x, body.position.y
            if not (self.BUILD_ZONE_X_MIN <= x <= self.BUILD_ZONE_X_MAX and
                    self.BUILD_ZONE_Y_MIN <= y <= self.BUILD_ZONE_Y_MAX):
                violations.append(f"Beam at ({x:.2f}, {y:.2f}) is outside build zone")
        return violations
    def get_task_description(self):
        return {
            "task": "E-04: Variable Mass",
            "description": "Design a structure that remains intact under sinusoidally varying mass (avoid resonance)",
            "terrain": self.terrain_bounds,
            "success_criteria": {
                "primary": "All joints remain intact (no disintegration due to vibration)",
                "span": f"Structure spans from at least x <= {self.SPAN_LEFT_X:.1f} to x >= {self.SPAN_RIGHT_X:.1f}",
                "complexity": f"At least {self.MIN_BEAMS} beams and {self.MIN_JOINTS} joints",
            },
            "evaluation": {
                "score_range": "0-100",
                "success_score": 100,
                "failure_score": 0,
            },
        }
