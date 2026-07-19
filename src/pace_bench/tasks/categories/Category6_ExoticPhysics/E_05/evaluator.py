import sys

import os

from typing import Dict, Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))

from pace_bench.simulator import TIME_STEP

class Evaluator:
    def __init__(self, terrain_bounds, environment=None):
        self.terrain_bounds = terrain_bounds
        self.environment = environment
        tz = terrain_bounds.get("target_zone", {})
        self.target_x_min = float(tz.get("x_min", 28.0))
        self.target_x_max = float(tz.get("x_max", 32.0))
        self.target_y_min = float(tz.get("y_min", 6.0))
        self.target_y_max = float(tz.get("y_max", 9.0))
        pz = terrain_bounds.get("pit_zone", {})
        self.pit_x_min = float(pz.get("x_min", 16.0))
        self.pit_x_max = float(pz.get("x_max", 24.0))
        self.pit_y_max = float(pz.get("y_max", 5.5))
        self.ground_y = float(terrain_bounds.get("ground_y", 1.0))
        self.body_start_x = float(terrain_bounds.get("body_start", {}).get("x", 8.0))
        self.body_start_y = float(terrain_bounds.get("body_start", {}).get("y", 5.0))
        self.reached_target = False
        if environment is None:
            raise ValueError("Evaluator requires environment instance")
    def evaluate(self, agent_body, step_count, max_steps):
        if not self.environment:
            return True, 0.0, {"error": "Environment not available"}
        pos = self.environment.get_body_position()
        if pos is None:
            return True, 0.0, {
                "success": False,
                "failed": True,
                "failure_reason": "Body not found",
                "step_count": step_count,
            }
        x, y = pos
        if (self.target_x_min <= x <= self.target_x_max and
                self.target_y_min <= y <= self.target_y_max):
            self.reached_target = True
        success = self.reached_target
        in_pit = (self.pit_x_min <= x <= self.pit_x_max) and y < self.pit_y_max
        if in_pit and not success:
            failed = True
            failure_reason = "Fell into pit zone; body entered forbidden region"
        else:
            failed = step_count >= max_steps - 1 and not success
            failure_reason = ("Stuck in local minimum: did not reach target zone before time ran out" if failed else None)
        if success:
            score = 100.0
        elif failed:
            score = 0.0
        else:
            start_x = self.body_start_x
            max_dist = self.target_x_min - start_x
            dist_traveled = x - start_x
            progress = min(max(dist_traveled / max_dist, 0.0), 1.0) if max_dist > 0 else 0.0
            score = progress * 80.0
        vel = self.environment.get_body_velocity() or (0.0, 0.0)
        vx, vy = vel[0], vel[1]
        speed = (vx * vx + vy * vy) ** 0.5
        start_x = self.body_start_x
        start_y = self.body_start_y
        closest_x = max(self.target_x_min, min(x, self.target_x_max))
        closest_y = max(self.target_y_min, min(y, self.target_y_max))
        dist_to_target = ((x - closest_x) ** 2 + (y - closest_y) ** 2) ** 0.5
        total_dist_x = self.target_x_min - start_x
        progress_x = (x - start_x) / total_dist_x if total_dist_x > 0 else 0.0
        progress_x = max(0.0, min(1.0, progress_x))
        in_target_x = self.target_x_min <= x <= self.target_x_max
        in_target_y = self.target_y_min <= y <= self.target_y_max
        forensic: Dict = {}
        env = self.environment
        if env is not None:
            fs = env.get_forensic_summary()
            forensic = {
                "max_body_x": fs.get("max_body_x"),
                "min_body_x": fs.get("min_body_x"),
                "max_body_y": fs.get("max_body_y"),
                "min_body_y": fs.get("min_body_y"),
                "max_speed": fs.get("max_speed"),
                "max_x_reached": fs.get("max_x_reached"),
                "total_dx": fs.get("total_dx"),
                "total_dy": fs.get("total_dy"),
                "steps_near_ceiling": fs.get("steps_near_ceiling", 0),
                "steps_in_pit_zone": fs.get("steps_in_pit_zone", 0),
                "steps_in_ground_zone": fs.get("steps_in_ground_zone", 0),
                "steps_stationary": fs.get("steps_stationary", 0),
                "first_ceiling_entry_step": fs.get("first_ceiling_entry_step"),
                "first_pit_entry_step": fs.get("first_pit_entry_step"),
                "first_ground_entry_step": fs.get("first_ground_entry_step"),
                "vertical_zone_samples": fs.get("vertical_zone_samples", {}),
                "temporal_events": env.get_temporal_events() if hasattr(env, 'get_temporal_events') else [],
                "velocity_reversal_events": env.get_velocity_reversals() if hasattr(env, 'get_velocity_reversals') else [],
                "peak_vertical_accel": env.get_peak_vertical_acceleration() if hasattr(env, 'get_peak_vertical_acceleration') else 0.0,
            }
            pp = env.get_physics_params()
            forensic["gravity_y"] = pp.get("gravity_y")
            forensic["linear_damping"] = pp.get("linear_damping")
            forensic["max_thrust"] = pp.get("max_thrust")
            forensic["magnet_count"] = pp.get("magnet_count")
            if hasattr(env, 'get_magnetic_force_summary'):
                forensic.update(env.get_magnetic_force_summary())
            if hasattr(env, 'get_energy_summary'):
                forensic.update(env.get_energy_summary())
            if hasattr(env, 'get_force_decomposition'):
                forensic.update(env.get_force_decomposition())
            if hasattr(env, 'get_progress_plateau_info'):
                forensic.update(env.get_progress_plateau_info())
        CEILING_Y = 9.7
        ceiling_clearance = CEILING_Y - y if y < CEILING_Y else 0.0
        ground_clearance = y - self.ground_y if y > self.ground_y else 0.0
        hx_remaining = max(self.target_x_min - x, 0.0)
        in_pit_evaluator = (self.pit_x_min <= x <= self.pit_x_max) and (y < self.pit_y_max)
        in_ceiling_zone = y > CEILING_Y
        magnetic_wall_clearance = None
        if env is not None and hasattr(env, '_magnets'):
            min_dist = float('inf')
            for m in env._magnets:
                mx, my = m[0], m[1]
                d = ((mx - x) ** 2 + (my - y) ** 2) ** 0.5
                if d < min_dist:
                    min_dist = d
            magnetic_wall_clearance = min_dist if min_dist < float('inf') else None
        net_mag_fx = forensic.get("net_magnetic_force_x", 0.0) if isinstance(forensic, dict) else 0.0
        thrust_fx = forensic.get("thrust_applied_x", 0.0) if isinstance(forensic, dict) else 0.0
        net_force_x = forensic.get("net_force_x", 0.0) if isinstance(forensic, dict) else 0.0
        metrics: Dict = {
            "step_count": step_count,
            "max_steps": max_steps,
            "success": success,
            "failed": failed,
            "failure_reason": failure_reason,
            "body_x": x,
            "body_y": y,
            "target_x_min": self.target_x_min,
            "target_x_max": self.target_x_max,
            "target_y_min": self.target_y_min,
            "target_y_max": self.target_y_max,
            "reached_target": self.reached_target,
            "velocity_x": vx,
            "velocity_y": vy,
            "speed": speed,
            "progress_x": progress_x,
            "dist_to_target": dist_to_target,
            "in_target_x": in_target_x,
            "in_target_y": in_target_y,
            "start_x": start_x,
            "start_y": start_y,
            "ceiling_clearance": ceiling_clearance,
            "ground_clearance": ground_clearance,
            "hx_remaining_to_target": hx_remaining,
            "in_pit_zone": in_pit_evaluator,
            "pit_x_min": self.pit_x_min,
            "pit_x_max": self.pit_x_max,
            "pit_y_max": self.pit_y_max,
            "ceiling_y": CEILING_Y,
            "ground_y": self.ground_y,
            "in_ceiling_zone": in_ceiling_zone,
            "magnetic_wall_clearance": magnetic_wall_clearance,
            "net_magnetic_force_x_terminal": net_mag_fx,
            "thrust_applied_x_terminal": thrust_fx,
            "net_force_x_terminal": net_force_x,
            **forensic,
        }
        done = success or failed or (step_count >= max_steps - 1)
        return done, score, metrics
    def get_task_description(self):
        return {
            "task": "E-05: The Magnet",
            "description": "Navigate body to target zone despite invisible repulsive/attractive force fields (avoid local minimum)",
            "terrain": self.terrain_bounds,
            "success_criteria": {
                "primary": f"Body center enters target zone (x in [{self.target_x_min:.1f}, {self.target_x_max:.1f}], y in [{self.target_y_min:.1f}, {self.target_y_max:.1f}])",
            },
            "evaluation": {
                "score_range": "0-100",
                "success_score": 100,
                "failure_score": 0,
            },
        }
