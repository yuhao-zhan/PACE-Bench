import sys

import os

import math

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

from pace_bench.primitives import compute_constraint_penalty

class Evaluator:
    def __init__(self, terrain_bounds, environment=None):
        self.terrain_bounds = terrain_bounds
        self.environment = environment
        self.initial_joint_count = 0
        self.structure_broken = False
        self.design_constraints_checked = False
        if not environment:
            raise ValueError("Evaluator requires environment instance")
        env_class = type(environment)
        self.MAX_STRUCTURE_MASS = getattr(environment, 'MAX_STRUCTURE_MASS', getattr(env_class, 'MAX_STRUCTURE_MASS', 60.0))
        self.BUILD_ZONE_X_MIN = getattr(environment, 'BUILD_ZONE_X_MIN', getattr(env_class, 'BUILD_ZONE_X_MIN', 12.0))
        self.BUILD_ZONE_X_MAX = getattr(environment, 'BUILD_ZONE_X_MAX', getattr(env_class, 'BUILD_ZONE_X_MAX', 18.0))
        self.BUILD_ZONE_Y_MIN = getattr(environment, 'BUILD_ZONE_Y_MIN', getattr(env_class, 'BUILD_ZONE_Y_MIN', 2.0))
        self.BUILD_ZONE_Y_MAX = getattr(environment, 'BUILD_ZONE_Y_MAX', getattr(env_class, 'BUILD_ZONE_Y_MAX', 4.5))
        self.BOAT_MAX_ANGLE_RAD = getattr(environment, 'BOAT_MAX_ANGLE_RAD', math.radians(18.0))
        self.CARGO_WATER_Y = getattr(environment, 'CARGO_WATER_Y', 1.98)
    def evaluate(self, agent_body, step_count, max_steps):
        if not self.environment:
            return True, 0.0, {"error": "Environment not available"}
        if not self.design_constraints_checked and step_count == 0:
            violations = self._check_design_constraints()
            if violations:
                self.design_constraints_checked = True
                return True, 0.0, {
                    "success": False,
                    "failed": True,
                    "failure_reason": "Design constraint violated: " + "; ".join(violations),
                    "step_count": step_count,
                    "constraint_violations": violations,
                }
            self.design_constraints_checked = True
            self.initial_joint_count = len(self.environment._joints)
        current_joint_count = len(self.environment._joints)
        if current_joint_count < self.initial_joint_count:
            self.structure_broken = True
        done = step_count >= max_steps
        if not done:
            metrics = self._collect_metrics(step_count, success=False, failed=False, failure_reason=None)
            return False, 0.0, metrics
        cargo_in_water = self.environment.get_cargo_in_water_count()
        initial_cargo = self.environment.get_initial_cargo_count()
        boat_angle = self.environment.get_boat_angle()
        angle_deg = math.degrees(abs(boat_angle)) if boat_angle is not None else 0.0
        max_angle_deg = math.degrees(self.BOAT_MAX_ANGLE_RAD)
        failed = False
        failure_reason = None
        if cargo_in_water > 0:
            failed = True
            failure_reason = f"{cargo_in_water}/{initial_cargo} cargo in water (y < {self.CARGO_WATER_Y}m)"
        if boat_angle is not None and abs(boat_angle) > self.BOAT_MAX_ANGLE_RAD:
            failed = True
            failure_reason = (failure_reason or "") + ("; " if failure_reason else "") + f"Boat capsized (angle {angle_deg:.1f}° > {max_angle_deg:.0f}° limit)"
        if self.structure_broken:
            failed = True
            failure_reason = (failure_reason or "") + ("; " if failure_reason else "") + "Structure integrity lost (joints broke)"
        success = (cargo_in_water == 0 and
                   (boat_angle is None or abs(boat_angle) <= self.BOAT_MAX_ANGLE_RAD) and
                   not self.structure_broken and not failed)
        if success:
            score = 100.0
        elif failed:
            score = 0.0
        else:
            cargo_ok = initial_cargo - cargo_in_water
            score = max(0.0, 80.0 * (cargo_ok / initial_cargo) if initial_cargo > 0 else 0.0)
        metrics = self._collect_metrics(
            step_count,
            success=success,
            failed=failed,
            failure_reason=failure_reason,
            cargo_in_water=cargo_in_water,
            initial_cargo=initial_cargo,
            boat_angle_rad=boat_angle,
            boat_angle_deg=angle_deg,
        )
        return True, score, metrics
    def _collect_metrics(self, step_count, success=False, failed=False, failure_reason=None,
                         cargo_in_water=None, initial_cargo=None, boat_angle_rad=None, boat_angle_deg=None):
        if cargo_in_water is None:
            cargo_in_water = self.environment.get_cargo_in_water_count()
        if initial_cargo is None:
            initial_cargo = self.environment.get_initial_cargo_count()
        if boat_angle_rad is None:
            boat_angle_rad = self.environment.get_boat_angle()
        if boat_angle_deg is None and boat_angle_rad is not None:
            boat_angle_deg = math.degrees(abs(boat_angle_rad))
        boat_pos = self.environment.get_boat_position() if hasattr(self.environment, 'get_boat_position') else None
        boat_x = boat_pos[0] if boat_pos else None
        boat_y = boat_pos[1] if boat_pos else None
        cargo_retained = (initial_cargo - cargo_in_water) if initial_cargo is not None else None
        cargo_retained_ratio = (cargo_retained / initial_cargo) if (initial_cargo and initial_cargo > 0) else None
        capsize_first_step = (self.environment.get_capsize_first_step()
                              if hasattr(self.environment, 'get_capsize_first_step') else None)
        cargo_retention_milestones = (self.environment.get_cargo_retention_milestones()
                                      if hasattr(self.environment, 'get_cargo_retention_milestones') else {})
        cargo_ever_below = (self.environment.get_cargo_ever_below_loss_plane()
                            if hasattr(self.environment, 'get_cargo_ever_below_loss_plane') else False)
        capsize_margin_at_grace = (self.environment.get_capsize_margin_at_grace_end()
                                   if hasattr(self.environment, 'get_capsize_margin_at_grace_end') else None)
        lowest_beam_y_floor_margin = (self.environment.get_lowest_beam_y_floor_margin()
                                       if hasattr(self.environment, 'get_lowest_beam_y_floor_margin') else None)
        cargo_lowest_y = (self.environment.get_cargo_lowest_y()
                          if hasattr(self.environment, 'get_cargo_lowest_y') else None)
        cargo_lowest_y_step = (self.environment.get_cargo_lowest_y_step()
                               if hasattr(self.environment, 'get_cargo_lowest_y_step') else None)
        cargo_loss_margin = None
        if cargo_lowest_y is not None and math.isfinite(cargo_lowest_y):
            cargo_loss_margin = cargo_lowest_y - self.CARGO_WATER_Y
        joint_peak_force = (self.environment.get_joint_peak_force()
                            if hasattr(self.environment, 'get_joint_peak_force') else 0.0)
        joint_max_force = (self.environment.get_joint_max_force()
                           if hasattr(self.environment, 'get_joint_max_force') else float('inf'))
        joint_peak_torque = (self.environment.get_joint_peak_torque()
                             if hasattr(self.environment, 'get_joint_peak_torque') else 0.0)
        joint_peak_force_pct = None
        if joint_max_force < float('inf') and joint_max_force > 0:
            joint_peak_force_pct = (joint_peak_force / joint_max_force) * 100.0
        peak_angular_velocity = (self.environment.get_peak_angular_velocity_rad_s()
                                  if hasattr(self.environment, 'get_peak_angular_velocity_rad_s') else 0.0)
        restoring_coeff = (self.environment.get_restoring_coeff()
                           if hasattr(self.environment, 'get_restoring_coeff') else None)
        wave_amplitude = (self.environment.get_wave_amplitude()
                          if hasattr(self.environment, 'get_wave_amplitude') else None)
        wave2_amplitude = (self.environment.get_wave2_amplitude()
                           if hasattr(self.environment, 'get_wave2_amplitude') else None)
        rogue_amplitude = (self.environment.get_rogue_amplitude()
                           if hasattr(self.environment, 'get_rogue_amplitude') else None)
        lateral_impulse_amp = (self.environment.get_lateral_impulse_amplitude()
                               if hasattr(self.environment, 'get_lateral_impulse_amplitude') else None)
        wind_amplitude = (self.environment.get_wind_amplitude()
                          if hasattr(self.environment, 'get_wind_amplitude') else None)
        initial_joint_count = max(self.initial_joint_count, len(self.environment._joints))
        cargo_grace_steps = (self.environment.get_grace_steps()
                             if hasattr(self.environment, 'get_grace_steps') else None)
        world = getattr(self.environment, '_world', None)
        gravity_current = None
        if world is not None and hasattr(world, 'gravity'):
            g = world.gravity
            gravity_current = (float(g[0]), float(g[1])) if len(g) >= 2 else None
        return {
            "step_count": step_count,
            "initial_cargo_count": initial_cargo,
            "cargo_in_water": cargo_in_water,
            "cargo_retained": cargo_retained,
            "cargo_retained_ratio": cargo_retained_ratio,
            "cargo_water_y": self.CARGO_WATER_Y,
            "boat_angle_rad": boat_angle_rad,
            "boat_angle_deg": boat_angle_deg,
            "boat_max_angle_deg": math.degrees(self.BOAT_MAX_ANGLE_RAD),
            "boat_x": boat_x,
            "boat_y": boat_y,
            "success": success,
            "failed": failed,
            "failure_reason": failure_reason,
            "structure_mass": self.environment.get_structure_mass(),
            "max_structure_mass": self.MAX_STRUCTURE_MASS,
            "structure_broken": self.structure_broken,
            "joint_count": len(self.environment._joints),
            "capsize_first_step": capsize_first_step,
            "cargo_retention_milestones": cargo_retention_milestones,
            "cargo_ever_below_loss_plane": cargo_ever_below,
            "capsize_margin_at_grace_end_rad": capsize_margin_at_grace,
            "lowest_beam_y_floor_margin": lowest_beam_y_floor_margin,
            "cargo_lowest_y": cargo_lowest_y,
            "cargo_lowest_y_step": cargo_lowest_y_step,
            "cargo_loss_margin": cargo_loss_margin,
            "build_zone_x_min": self.BUILD_ZONE_X_MIN,
            "build_zone_x_max": self.BUILD_ZONE_X_MAX,
            "build_zone_y_min": self.BUILD_ZONE_Y_MIN,
            "build_zone_y_max": self.BUILD_ZONE_Y_MAX,
            "joint_peak_force_N": joint_peak_force,
            "joint_max_force_N": joint_max_force,
            "joint_peak_force_pct": joint_peak_force_pct,
            "joint_peak_torque_Nm": joint_peak_torque,
            "peak_angular_velocity_rad_s": peak_angular_velocity,
            "restoring_coeff": restoring_coeff,
            "wave_amplitude_N": wave_amplitude,
            "wave2_amplitude_N": wave2_amplitude,
            "rogue_amplitude_N": rogue_amplitude,
            "lateral_impulse_amplitude_N": lateral_impulse_amp,
            "wind_amplitude_N": wind_amplitude,
            "initial_joint_count": initial_joint_count,
            "cargo_grace_steps": cargo_grace_steps,
            "gravity_current": gravity_current,
            "constraint_info": self.get_constraint_info(),
        }
    def _check_design_constraints(self):
        violations = []
        if not self.environment:
            return ["Environment not available"]
        structure_mass = self.environment.get_structure_mass()
        if structure_mass > self.MAX_STRUCTURE_MASS:
            violations.append(f"Structure mass {structure_mass:.2f} kg exceeds maximum {self.MAX_STRUCTURE_MASS} kg")
        for body in self.environment._bodies:
            x, y = body.position.x, body.position.y
            if not (self.BUILD_ZONE_X_MIN <= x <= self.BUILD_ZONE_X_MAX and
                    self.BUILD_ZONE_Y_MIN <= y <= self.BUILD_ZONE_Y_MAX):
                violations.append(
                    f"Beam at ({x:.2f}, {y:.2f}) is outside build zone "
                    f"x=[{self.BUILD_ZONE_X_MIN}, {self.BUILD_ZONE_X_MAX}], y=[{self.BUILD_ZONE_Y_MIN}, {self.BUILD_ZONE_Y_MAX}]"
                )
        return violations
    def compute_score_with_penalty(self, score: float, metrics: dict) -> float:
        if score > 0:
            return score
        constraint_info = self.get_constraint_info()
        penalty = compute_constraint_penalty("F_05", score, metrics, constraint_info)
        return penalty
    def get_constraint_info(self):
        return {
            'max_structure_mass': self.MAX_STRUCTURE_MASS,
            'build_zone_x_min': self.BUILD_ZONE_X_MIN,
            'build_zone_x_max': self.BUILD_ZONE_X_MAX,
            'build_zone_y_min': self.BUILD_ZONE_Y_MIN,
            'build_zone_y_max': self.BUILD_ZONE_Y_MAX,
            'boat_max_angle_rad': self.BOAT_MAX_ANGLE_RAD,
            'cargo_water_y': self.CARGO_WATER_Y,
        }
    def get_task_description(self):
        return {
            "task": "F-05: The Boat",
            "description": "Keep cargo on boat in rough water; boat must not capsize (angle <= 18°)",
            "terrain": self.terrain_bounds,
            "success_criteria": {
                "primary": "No cargo in water (all above y={:.2f}m)".format(self.CARGO_WATER_Y),
                "secondary": f"Boat angle <= {math.degrees(self.BOAT_MAX_ANGLE_RAD):.0f}°",
                "tertiary": "Structure remains intact",
            },
            "evaluation": {"score_range": "0-100", "success_score": 100, "failure_score": 0},
        }
