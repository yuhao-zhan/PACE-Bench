import sys

import os

import math

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))

from pace_bench.simulator import TIME_STEP

class Evaluator:
    def __init__(self, terrain_bounds, environment=None):
        self.terrain_bounds = terrain_bounds
        self.environment = environment
        arena = terrain_bounds.get("arena", {})
        self.arena_x_min = float(arena.get("x_min", 0.0))
        self.arena_x_max = float(arena.get("x_max", 40.0))
        self.arena_y_min = float(arena.get("y_min", 0.0))
        self.arena_y_max = float(arena.get("y_max", 20.0))
        self.initial_joint_count = 0
        self.structure_broken = False
        self.design_constraints_checked = False
        if environment is None:
            raise ValueError("Evaluator requires environment instance")
        self.MAX_STRUCTURE_MASS = getattr(environment, "MAX_STRUCTURE_MASS", type(environment).MAX_STRUCTURE_MASS)
        build_zone = terrain_bounds.get("build_zone", {})
        build_y = build_zone.get("y", [6.0, 18.0])
        self.BUILD_ZONE_X_MIN = float(build_zone.get("x", [12.0, 28.0])[0])
        self.BUILD_ZONE_X_MAX = float(build_zone.get("x", [12.0, 28.0])[1])
        self.BUILD_ZONE_Y_MIN = float(build_y[0])
        self.BUILD_ZONE_Y_MAX = float(build_y[1])
        self.MAX_BEAM_COUNT = getattr(environment, "MAX_BEAM_COUNT", getattr(type(environment), "MAX_BEAM_COUNT", 99))
        self.JOINT_FORCE_LIMIT = getattr(environment, "_joint_force_limit", float('inf'))
        obs_list = terrain_bounds.get("obstacles", [])
        self.obstacle_zones = []
        for obs in obs_list:
            self.obstacle_zones.append({
                "x_min": float(obs.get("x_min", 0)),
                "x_max": float(obs.get("x_max", 0)),
                "y_min": float(obs.get("y_min", 0)),
                "y_max": float(obs.get("y_max", 0)),
            })
        fz_list = terrain_bounds.get("forbidden_zones", [])
        self.forbidden_zones = []
        for fz in fz_list:
            self.forbidden_zones.append({
                "x_min": float(fz.get("x_min", 0)),
                "x_max": float(fz.get("x_max", 0)),
                "y_min": float(fz.get("y_min", 0)),
                "y_max": float(fz.get("y_max", 0)),
            })
    def _get_all_dynamic_bodies(self):
        bodies = list(self.environment._bodies)
        for key, body in self.environment._terrain_bodies.items():
            if key.startswith("demonstrator_"):
                bodies.append(body)
        return bodies
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
                    "out_of_bounds": False,
                    "structure_broken": False,
                    "joint_count": len(self.environment._joints),
                    "beam_count": len(self.environment._bodies),
                    "max_beam_count": self.MAX_BEAM_COUNT,
                    "structure_mass": self.environment.get_structure_mass(),
                    "max_structure_mass": self.MAX_STRUCTURE_MASS,
                    "arena_x_min": self.arena_x_min,
                    "arena_x_max": self.arena_x_max,
                    "arena_y_min": self.arena_y_min,
                    "arena_y_max": self.arena_y_max,
                    "offending_positions": [],
                    "joint_force_limit": self.JOINT_FORCE_LIMIT,
                    "joint_tracking": None,
                    "forbidden_zone_min_margin": None,
                    "forbidden_zone_all_margins": [],
                    "obstacle_zone_min_margin": None,
                    "obstacle_zone_all_margins": [],
                    "build_zone_tightest_margin": None,
                    "build_zone_body_margins": [],
                    "build_zone_x_min": self.BUILD_ZONE_X_MIN,
                    "build_zone_x_max": self.BUILD_ZONE_X_MAX,
                    "build_zone_y_min": self.BUILD_ZONE_Y_MIN,
                    "build_zone_y_max": self.BUILD_ZONE_Y_MAX,
                    "gravity_magnitude": None,
                    "kinetic_energy_history": None,
                    "peak_body_velocity": None,
                    "peak_reaction_force_ever": None,
                    "linear_damping": None,
                    "angular_damping": None,
                    "joint_capacity_total": None,
                    "initial_joint_count": len(self.environment._joints),
                }
            self.design_constraints_checked = True
        if step_count == 0:
            self.initial_joint_count = len(self.environment._joints)
        current_joint_count = len(self.environment._joints)
        if current_joint_count < self.initial_joint_count:
            self.structure_broken = True
        out_of_bounds = False
        offending_positions = []
        for body in self._get_all_dynamic_bodies():
            try:
                x, y = body.position.x, body.position.y
                if x < self.arena_x_min or x > self.arena_x_max or y < self.arena_y_min or y > self.arena_y_max:
                    out_of_bounds = True
                    offending_positions.append((x, y))
            except Exception:
                continue
        obstacle_overlap = False
        obstacle_offending = []
        for body in self.environment._bodies:
            try:
                x, y = body.position.x, body.position.y
                for zone in self.obstacle_zones:
                    if (zone["x_min"] <= x <= zone["x_max"] and
                            zone["y_min"] <= y <= zone["y_max"]):
                        obstacle_overlap = True
                        obstacle_offending.append((x, y))
                        break
            except Exception:
                continue
        forbidden_zone_violation = False
        forbidden_offending = []
        for body in self.environment._bodies:
            try:
                x, y = body.position.x, body.position.y
                for zone in self.forbidden_zones:
                    if (zone["x_min"] <= x <= zone["x_max"] and
                            zone["y_min"] <= y <= zone["y_max"]):
                        forbidden_zone_violation = True
                        forbidden_offending.append((x, y))
                        break
            except Exception:
                continue
        failed = out_of_bounds or self.structure_broken or obstacle_overlap or forbidden_zone_violation
        success = (not failed) and (step_count >= max_steps - 1)
        if out_of_bounds:
            failure_reason = f"Flying out of bounds: at least one body left the arena (x in [{self.arena_x_min:.1f}, {self.arena_x_max:.1f}], y in [{self.arena_y_min:.1f}, {self.arena_y_max:.1f}])"
        elif forbidden_zone_violation:
            failure_reason = "Structure enters a forbidden zone; no beam center may lie there (infer from feedback)"
        elif obstacle_overlap:
            failure_reason = "Structure overlaps an obstacle; design must avoid all obstacle zones"
        elif self.structure_broken:
            failure_reason = "Structure integrity lost (joints broke)"
        else:
            failure_reason = None
        if success and not failed:
            score = 100.0
        elif failed:
            score = 0.0
        else:
            progress = step_count / max(max_steps, 1)
            score = progress * 80.0
        body_positions = []
        for body in self._get_all_dynamic_bodies():
            try:
                body_positions.append((body.position.x, body.position.y))
            except Exception:
                continue
        x_min_b = min(p[0] for p in body_positions) if body_positions else None
        x_max_b = max(p[0] for p in body_positions) if body_positions else None
        y_min_b = min(p[1] for p in body_positions) if body_positions else None
        y_max_b = max(p[1] for p in body_positions) if body_positions else None
        gravity_current = None
        if hasattr(self.environment, "get_gravity_at_time"):
            gravity_current = self.environment.get_gravity_at_time()
        joint_tracking = None
        if hasattr(self.environment, "get_joint_force_tracking"):
            joint_tracking = self.environment.get_joint_force_tracking()
        fz_margins = []
        fz_zone_list = list(self.forbidden_zones)
        for (bx, by) in body_positions:
            min_margin = None
            for fz in fz_zone_list:
                if fz["x_min"] <= bx <= fz["x_max"]:
                    dist_top = float("inf") if by <= fz["y_max"] else by - fz["y_max"]
                    dist_bot = float("inf") if by >= fz["y_min"] else fz["y_min"] - by
                    m = min(dist_top, dist_bot) if (math.isfinite(dist_top) or math.isfinite(dist_bot)) else min(dist_top, dist_bot)
                elif fz["y_min"] <= by <= fz["y_max"]:
                    dist_left = float("inf") if bx >= fz["x_min"] else fz["x_min"] - bx
                    dist_right = float("inf") if bx <= fz["x_max"] else bx - fz["x_max"]
                    m = min(dist_left, dist_right) if (math.isfinite(dist_left) or math.isfinite(dist_right)) else min(dist_left, dist_right)
                else:
                    cx = max(fz["x_min"], min(bx, fz["x_max"]))
                    cy = max(fz["y_min"], min(by, fz["y_max"]))
                    dx = bx - cx
                    dy = by - cy
                    m = math.hypot(dx, dy)
                if min_margin is None or m < min_margin:
                    min_margin = m
            if min_margin is not None:
                fz_margins.append((bx, by, float(min_margin)))
        fz_min_margin = min(m[2] for m in fz_margins) if fz_margins else None
        obs_margins = []
        obs_zone_list = list(self.obstacle_zones)
        for (bx, by) in body_positions:
            min_margin = None
            for oz in obs_zone_list:
                if oz["x_min"] <= bx <= oz["x_max"]:
                    dist_top = float("inf") if by <= oz["y_max"] else by - oz["y_max"]
                    dist_bot = float("inf") if by >= oz["y_min"] else oz["y_min"] - by
                    m = min(dist_top, dist_bot) if (math.isfinite(dist_top) or math.isfinite(dist_bot)) else min(dist_top, dist_bot)
                elif oz["y_min"] <= by <= oz["y_max"]:
                    dist_left = float("inf") if bx >= oz["x_min"] else oz["x_min"] - bx
                    dist_right = float("inf") if bx <= oz["x_max"] else bx - oz["x_max"]
                    m = min(dist_left, dist_right) if (math.isfinite(dist_left) or math.isfinite(dist_right)) else min(dist_left, dist_right)
                else:
                    cx = max(oz["x_min"], min(bx, oz["x_max"]))
                    cy = max(oz["y_min"], min(by, oz["y_max"]))
                    dx = bx - cx
                    dy = by - cy
                    m = math.hypot(dx, dy)
                if min_margin is None or m < min_margin:
                    min_margin = m
            if min_margin is not None:
                obs_margins.append((bx, by, float(min_margin)))
        obs_min_margin = min(m[2] for m in obs_margins) if obs_margins else None
        bz_body_margins = []
        for body in self.environment._bodies:
            try:
                bx, by = body.position.x, body.position.y
                left_m = bx - self.BUILD_ZONE_X_MIN
                right_m = self.BUILD_ZONE_X_MAX - bx
                bot_m = by - self.BUILD_ZONE_Y_MIN
                top_m = self.BUILD_ZONE_Y_MAX - by
                bz_body_margins.append({
                    "pos": (bx, by),
                    "left_margin": left_m,
                    "right_margin": right_m,
                    "bottom_margin": bot_m,
                    "top_margin": top_m,
                    "tightest": min(left_m, right_m, bot_m, top_m),
                })
            except Exception:
                continue
        bz_tightest = min(b["tightest"] for b in bz_body_margins) if bz_body_margins else None
        gravity_magnitude = math.hypot(gravity_current[0], gravity_current[1]) if gravity_current and len(gravity_current) >= 2 else None
        ke_history = None
        peak_velocity = None
        peak_reaction_force = None
        linear_damping = None
        angular_damping = None
        if self.environment:
            if hasattr(self.environment, "get_kinetic_energy_history"):
                ke_history = self.environment.get_kinetic_energy_history()
            if hasattr(self.environment, "get_peak_body_velocity"):
                peak_velocity = self.environment.get_peak_body_velocity()
            if hasattr(self.environment, "get_peak_reaction_force_ever"):
                peak_reaction_force = self.environment.get_peak_reaction_force_ever()
            if hasattr(self.environment, "get_linear_damping"):
                linear_damping = self.environment.get_linear_damping()
            if hasattr(self.environment, "get_angular_damping"):
                angular_damping = self.environment.get_angular_damping()
        joint_capacity_total = None
        jfl = self.JOINT_FORCE_LIMIT
        if math.isfinite(jfl):
            joint_capacity_total = jfl * max(self.initial_joint_count, 1)
        metrics = {
            "step_count": step_count,
            "success": success and not failed,
            "failed": failed,
            "failure_reason": failure_reason,
            "out_of_bounds": out_of_bounds,
            "obstacle_overlap": obstacle_overlap,
            "obstacle_offending": obstacle_offending[:5],
            "forbidden_zone_violation": forbidden_zone_violation,
            "forbidden_offending": forbidden_offending[:5],
            "structure_broken": self.structure_broken,
            "joint_count": current_joint_count,
            "beam_count": len(self.environment._bodies),
            "max_beam_count": self.MAX_BEAM_COUNT,
            "structure_mass": self.environment.get_structure_mass(),
            "max_structure_mass": self.MAX_STRUCTURE_MASS,
            "arena_x_min": self.arena_x_min,
            "arena_x_max": self.arena_x_max,
            "arena_y_min": self.arena_y_min,
            "arena_y_max": self.arena_y_max,
            "offending_positions": offending_positions[:5],
            "body_count": len(body_positions),
            "body_x_min": x_min_b,
            "body_x_max": x_max_b,
            "body_y_min": y_min_b,
            "body_y_max": y_max_b,
            "gravity_current": gravity_current,
            "progress_pct": 100.0 * step_count / max(max_steps, 1),
            "joint_force_limit": self.JOINT_FORCE_LIMIT,
            "joint_tracking": joint_tracking,
            "forbidden_zone_min_margin": fz_min_margin,
            "forbidden_zone_all_margins": fz_margins[:5] if fz_margins else [],
            "obstacle_zone_min_margin": obs_min_margin,
            "obstacle_zone_all_margins": obs_margins[:5] if obs_margins else [],
            "build_zone_tightest_margin": bz_tightest,
            "build_zone_body_margins": bz_body_margins[:5] if bz_body_margins else [],
            "build_zone_x_min": self.BUILD_ZONE_X_MIN,
            "build_zone_x_max": self.BUILD_ZONE_X_MAX,
            "build_zone_y_min": self.BUILD_ZONE_Y_MIN,
            "build_zone_y_max": self.BUILD_ZONE_Y_MAX,
            "gravity_magnitude": gravity_magnitude,
            "kinetic_energy_history": ke_history,
            "peak_body_velocity": peak_velocity,
            "peak_reaction_force_ever": peak_reaction_force,
            "linear_damping": linear_damping,
            "angular_damping": angular_damping,
            "joint_capacity_total": joint_capacity_total,
            "initial_joint_count": self.initial_joint_count,
        }
        return success or failed, score, metrics
    def _check_design_constraints(self):
        violations = []
        if not self.environment:
            return ["Environment not available"]
        mass = self.environment.get_structure_mass()
        if mass > self.MAX_STRUCTURE_MASS:
            violations.append(f"Structure mass {mass:.2f} kg exceeds maximum {self.MAX_STRUCTURE_MASS} kg")
        beam_count = len(self.environment._bodies)
        if beam_count > self.MAX_BEAM_COUNT:
            violations.append(f"Structure has {beam_count} beams, exceeds maximum {self.MAX_BEAM_COUNT} beams")
        for body in self.environment._bodies:
            x, y = body.position.x, body.position.y
            if not (self.BUILD_ZONE_X_MIN <= x <= self.BUILD_ZONE_X_MAX and
                    self.BUILD_ZONE_Y_MIN <= y <= self.BUILD_ZONE_Y_MAX):
                violations.append(f"Beam at ({x:.2f}, {y:.2f}) is outside build zone")
        return violations
    def get_task_description(self):
        return {
            "task": "E-01: Inverted Gravity",
            "description": "Design a structure that stays within the arena under time-varying or inverted gravity",
            "terrain": self.terrain_bounds,
            "success_criteria": {
                "primary": f"No body leaves the arena (x in [{self.arena_x_min:.1f}, {self.arena_x_max:.1f}], y in [{self.arena_y_min:.1f}, {self.arena_y_max:.1f}])",
                "secondary": "Structure joints remain intact",
            },
            "evaluation": {
                "score_range": "0-100",
                "success_score": 100,
                "failure_score": 0,
            },
        }
